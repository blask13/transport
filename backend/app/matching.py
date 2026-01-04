# backend\app\matching.py
from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import text
from .osrm import osrm_route
from .models import RouteParcelMatch, Parcel
from .models import Route
import json

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
            p.status = 'pending'
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

        variant = osrm_route([
            (coords["start_lng"], coords["start_lat"]),
            (pcoords["pickup_lng"], pcoords["pickup_lat"]),
            (pcoords["drop_lng"],   pcoords["drop_lat"]),
            (coords["end_lng"], coords["end_lat"]),
        ])

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
        results.append({
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
