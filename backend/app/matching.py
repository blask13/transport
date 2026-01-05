# backend\app\matching.py
from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import text, select
from .osrm import osrm_route
from .models import RouteParcelMatch, Parcel
from .models import Route
import json
from geoalchemy2.elements import WKTElement


def propose_matches_for_route(
    route_id: int,
    db: Session,
    buffer_m: float = 2000000.0,  # 2 km – MVP
):
    """
    ETAP 2 – PROPOZYCJE:
    - wybór paczek w buforze trasy (PostGIS)
    - brak odrzucania na podstawie kolejności
    - liczenie kosztu wpięcia (Δ km / Δ czasu) przez OSRM
    - sortowanie od najbardziej do najmniej opłacalnej
    - decyzję podejmuje kurier
    """

    # --- 1) Sprawdź trasę ---
    route = db.get(Route, route_id)
    if not route or not route.is_active:
        return []
    # --- 1b) Wyciągnij współrzędne start/end z PostGIS (bez .x/.y na WKBElement) ---
    coords_sql = text(
        """
        SELECT
          ST_X(start_point) AS start_lng,
          ST_Y(start_point) AS start_lat,
          ST_X(end_point)   AS end_lng,
          ST_Y(end_point)   AS end_lat
        FROM routes
        WHERE id = :route_id
        """
    )
    coords = db.execute(coords_sql, {"route_id": route_id}).mappings().first()
    if not coords or coords["start_lng"] is None or coords["end_lng"] is None:
        return []  # albo raise, ale na MVP zwróć pusto jeśli trasa uszkodzona

    # --- 2) Zapytanie PostGIS ---
    # Uwaga:
    # - geometrie są w SRID 4326 (stopnie)
    # - bufor liczymy w metrach -> rzut do geography
    sql = text(
        """
        SELECT
            p.id AS parcel_id,
            ST_Distance(
                p.pickup_point::geography,
                r.geom::geography
            ) AS pickup_to_route_m,
            ST_Distance(
                p.drop_point::geography,
                r.geom::geography
            ) AS drop_to_route_m
        FROM parcels p
        JOIN routes r ON r.id = :route_id
        WHERE
            -- paczka ma być widoczna dla wielu kurierów aż do ACCEPT albo CANCEL
            -- więc proponujemy zarówno pending jak i offered (jeśli już masz takie w DB)
            p.status = ANY(ARRAY['pending'::text, 'offered'::text])
            AND NOT EXISTS (
                SELECT 1
                FROM route_parcel_matches m
                WHERE m.route_id = :route_id
                  AND m.parcel_id = p.id
                  -- nie dubluj aktywnych propozycji dla tej samej trasy
                  AND m.status IN ('proposed', 'accepted')
            )
            AND ST_DWithin(            
                p.pickup_point::geography,
                r.geom::geography,
                :buffer_m
            )
            AND ST_DWithin(
                p.drop_point::geography,
                r.geom::geography,
                :buffer_m
            )
        """
    )

    rows = db.execute(
        sql,
        {
            "route_id": route_id,
            "buffer_m": buffer_m,
        },
    ).all()

    # --- 3) Zwróć TYLKO identyfikatory kandydatów ---
    if not rows:
        return []

    # --- 3) OSRM: trasa bazowa (1x) ---
    base = osrm_route([
        (coords["start_lng"], coords["start_lat"]),
        (coords["end_lng"], coords["end_lat"]),
    ])

    results = []

    for r in rows:
        parcel = db.get(Parcel, r.parcel_id)
        if not parcel:
            continue

        # pickup/drop też mogą być WKBElement -> bierzemy współrzędne przez SQL
        pcoords_sql = text(
            """
            SELECT
              ST_X(pickup_point) AS pickup_lng,
              ST_Y(pickup_point) AS pickup_lat,
              ST_X(drop_point)   AS drop_lng,
              ST_Y(drop_point)   AS drop_lat
            FROM parcels
            WHERE id = :parcel_id
            """
        )
        pcoords = db.execute(pcoords_sql, {"parcel_id": parcel.id}).mappings().first()
        if not pcoords:
            continue

        variant = osrm_route(
            [
                (coords["start_lng"], coords["start_lat"]),
                (pcoords["pickup_lng"], pcoords["pickup_lat"]),
                (pcoords["drop_lng"],   pcoords["drop_lat"]),
                (coords["end_lng"],     coords["end_lat"]),
            ],
        )

        delta_distance = variant["distance_m"] - base["distance_m"]
        delta_duration = variant["duration_s"] - base["duration_s"]

        match = RouteParcelMatch(
            route_id=route.id,
            parcel_id=parcel.id,
            delta_distance_m=delta_distance,
            delta_duration_s=delta_duration,
            base_distance_m=base["distance_m"],
            base_duration_s=base["duration_s"],
            new_distance_m=variant["distance_m"],
            new_duration_s=variant["duration_s"],
            pickup_to_route_m=r.pickup_to_route_m,
            drop_to_route_m=r.drop_to_route_m,
            debug=json.dumps({
                "buffer_m": buffer_m,
                "base": base,
                "variant": variant,
            }),
            status="proposed",
        )

        db.add(match)
        db.flush()  # <-- dostajemy match.id bez commit
        results.append({
            "match_id": match.id,
            "parcel_id": parcel.id,
            "delta_distance_m": round(delta_distance),
            "delta_duration_s": round(delta_duration),
        })
    # --- 4) Sortowanie: najbardziej -> najmniej opłacalna ---
    results.sort(
        key=lambda r: (r["delta_distance_m"], r["delta_duration_s"])
    )
    db.commit()

    return results





def accept_match(match_id: int, db: Session):
    """
    ETAP 5.1 – ACCEPT (utwardzenie):
    - transakcja + FOR UPDATE (RouteParcelMatch + Route + Parcel)
    - blokady logiczne
    - idempotencja (kontrolowany błąd)
    """

    # Całość w transakcji – jak cokolwiek padnie, to rollback
    with db.begin():
        # --- 1) Lock match ---
        match = db.execute(
            select(RouteParcelMatch)
            .where(RouteParcelMatch.id == match_id)
            .with_for_update()
        ).scalar_one_or_none()

        if not match:
            raise ValueError("match_not_found")

        # Idempotencja / kontrolowany błąd
        if match.status == "accepted":
            raise ValueError("match_already_accepted")
        if match.status != "proposed":
            raise ValueError(f"match_not_proposed:{match.status}")

        # --- 2) Lock route ---
        route = db.execute(
            select(Route)
            .where(Route.id == match.route_id)
            .with_for_update()
        ).scalar_one_or_none()
        if not route:
            raise ValueError("route_not_found")
        if not route.is_active:
            raise ValueError("route_inactive")

        # --- 3) Lock parcel ---
        parcel = db.execute(
            select(Parcel)
            .where(Parcel.id == match.parcel_id)
            .with_for_update()
        ).scalar_one_or_none()
        if not parcel:
            raise ValueError("parcel_not_found")

        # Bezpiecznik: paczka już zaakceptowana/anulowana
        if parcel.status in ("accepted", "cancelled", "rejected"):
            raise ValueError(f"parcel_not_pending:{parcel.status}")

        # --- 4) Pobierz współrzędne start / pickup / drop / end ---
        coords_sql = text(
            """
            SELECT
              ST_X(r.start_point) AS start_lng,
              ST_Y(r.start_point) AS start_lat,
              ST_X(p.pickup_point) AS pickup_lng,
              ST_Y(p.pickup_point) AS pickup_lat,
              ST_X(p.drop_point) AS drop_lng,
              ST_Y(p.drop_point) AS drop_lat,
              ST_X(r.end_point) AS end_lng,
              ST_Y(r.end_point) AS end_lat
            FROM routes r
            JOIN parcels p ON p.id = :parcel_id
            WHERE r.id = :route_id
            """
        )
        coords = db.execute(
            coords_sql, {"route_id": route.id, "parcel_id": parcel.id}
        ).mappings().first()
        if not coords:
            raise ValueError("coords_not_found")

        # --- 5) OSRM: wariant (start→pickup→drop→end) + PEŁNA GEOMETRIA ---
        variant = osrm_route([
            (coords["start_lng"], coords["start_lat"]),
            (coords["pickup_lng"], coords["pickup_lat"]),
            (coords["drop_lng"],   coords["drop_lat"]),
            (coords["end_lng"],   coords["end_lat"]),
        ], with_geometry=True)

        # --- 6) Trasa = jeden stan prawdy (nadpisanie) ---
        geometry = variant.get("geometry")
        if not geometry or geometry["type"] != "LineString":
            raise ValueError("invalid_osrm_geometry")

        coords_list = geometry["coordinates"]  # [[lng, lat], ...]
        route.geom = WKTElement(
            "LINESTRING(" + ", ".join(
                f"{lng} {lat}" for lng, lat in coords_list
            ) + ")",
            srid=4326,
        )

        route.distance_m = float(variant["distance_m"])
        route.duration_s = float(variant["duration_s"])

        # --- 7) Statusy ---
        match.status = "accepted"
        parcel.status = "accepted"

        # --- 8) Unieważnij inne match’e tej paczki (rejected) ---
        db.query(RouteParcelMatch).filter(
            RouteParcelMatch.parcel_id == parcel.id,
            RouteParcelMatch.id != match.id,
        ).update({"status": "rejected"}, synchronize_session=False)

        # --- 9) NIE kasuj innych propozycji tej trasy ---
        # W MVP trasa może mieć wiele proponowanych paczek równolegle.
        # Kasujemy tylko te propozycje, które dotyczą tej paczki (pkt 8).

        return {
            "route_id": int(route.id),
            "parcel_id": int(parcel.id),
            "new_distance_m": float(route.distance_m),
            "new_duration_s": float(route.duration_s),
        }
