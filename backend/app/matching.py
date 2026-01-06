# backend/app/matching.py - WITH SEQUENTIAL OPTIMIZATION
from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import text, select
from .osrm import osrm_route
from .models import RouteParcelMatch, Parcel, Route
from .history import log_route_change
from .waypoint_optimizer import optimize_waypoints_greedy_forward  # ZMIANA!
import json
from geoalchemy2.elements import WKTElement


def propose_matches_for_route(
    route_id: int,
    db: Session,
    buffer_m: float = 50000.0,
):
    """
    Propozycje z SEKWENCYJNĄ optymalizacją.
    
    Nowa paczka jest wstawiana w najlepsze miejsce w istniejącej trasie,
    BEZ zmiany kolejności już zaakceptowanych paczek.
    """

    route = db.get(Route, route_id)
    if not route or not route.is_active:
        return []
    
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
    if not coords or coords["start_lng"] is None:
        return []

    sql = text(
        """
        SELECT
            p.id AS parcel_id,
            ST_Distance(p.pickup_point::geography, r.geom::geography) AS pickup_to_route_m,
            ST_Distance(p.drop_point::geography, r.geom::geography) AS drop_to_route_m
        FROM parcels p
        JOIN routes r ON r.id = :route_id
        WHERE
            p.status = ANY(ARRAY['pending'::text, 'offered'::text])
            AND NOT EXISTS (
                SELECT 1 FROM route_parcel_matches m
                WHERE m.route_id = :route_id AND m.parcel_id = p.id
                  AND m.status IN ('proposed', 'accepted')
            )
            AND ST_DWithin(p.pickup_point::geography, r.geom::geography, :buffer_m)
            AND ST_DWithin(p.drop_point::geography, r.geom::geography, :buffer_m)
        """
    )

    rows = db.execute(sql, {"route_id": route_id, "buffer_m": buffer_m}).all()
    if not rows:
        return []

    # Pobierz zaakceptowane paczki
    accepted_parcels_ids = db.execute(
        select(RouteParcelMatch.parcel_id)
        .where(RouteParcelMatch.route_id == route_id)
        .where(RouteParcelMatch.status == "accepted")
    ).scalars().all()

    # Przygotuj dane zaakceptowanych paczek
    accepted_parcels_data = []
    for pid in accepted_parcels_ids:
        pcoords = db.execute(
            text("""
                SELECT
                  ST_X(pickup_point) AS pickup_lng,
                  ST_Y(pickup_point) AS pickup_lat,
                  ST_X(drop_point) AS drop_lng,
                  ST_Y(drop_point) AS drop_lat
                FROM parcels WHERE id = :pid
            """),
            {"pid": pid}
        ).mappings().first()
        if pcoords:
            accepted_parcels_data.append({
                "id": pid,
                "pickup": (pcoords["pickup_lng"], pcoords["pickup_lat"]),
                "drop": (pcoords["drop_lng"], pcoords["drop_lat"]),
            })

    # Trasa bazowa (z już zaakceptowanymi paczkami)
    start = (coords["start_lng"], coords["start_lat"])
    end = (coords["end_lng"], coords["end_lat"])
    
    base_waypoints = optimize_waypoints_greedy_forward(start, end, accepted_parcels_data)
    base = osrm_route(base_waypoints)

    results = []

    for r in rows:
        parcel = db.get(Parcel, r.parcel_id)
        if not parcel:
            continue

        pcoords = db.execute(
            text("""
                SELECT
                  ST_X(pickup_point) AS pickup_lng,
                  ST_Y(pickup_point) AS pickup_lat,
                  ST_X(drop_point) AS drop_lng,
                  ST_Y(drop_point) AS drop_lat
                FROM parcels WHERE id = :pid
            """),
            {"pid": parcel.id}
        ).mappings().first()
        if not pcoords:
            continue

        # NOWA paczka do dodania (NA KOŃCU listy!)
        new_parcel_data = {
            "id": parcel.id,
            "pickup": (pcoords["pickup_lng"], pcoords["pickup_lat"]),
            "drop": (pcoords["drop_lng"], pcoords["drop_lat"]),
        }

        # Trasa z nową paczką (dodana NA KOŃCU sekwencji)
        variant_parcels = accepted_parcels_data + [new_parcel_data]
        variant_waypoints = optimize_waypoints_greedy_forward(start, end, variant_parcels)
        variant = osrm_route(variant_waypoints)

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
                "accepted_parcels_count": len(accepted_parcels_data),
                "optimizer": "greedy_forward",
            }),
            status="proposed",
        )

        db.add(match)
        db.flush()
        
        results.append({
            "match_id": match.id,
            "parcel_id": parcel.id,
            "delta_distance_m": round(delta_distance),
            "delta_duration_s": round(delta_duration),
        })
    
    results.sort(key=lambda r: (r["delta_distance_m"], r["delta_duration_s"]))
    db.commit()

    return results


def accept_match(match_id: int, db: Session, changed_by: str = "system"):
    """
    Accept z SEKWENCYJNĄ optymalizacją.
    
    Nowa paczka dodawana NA KOŃCU sekwencji, bez zmiany kolejności
    wcześniej zaakceptowanych paczek.
    """

    with db.begin():
        match = db.execute(
            select(RouteParcelMatch)
            .where(RouteParcelMatch.id == match_id)
            .with_for_update()
        ).scalar_one_or_none()

        if not match:
            raise ValueError("match_not_found")
        if match.status == "accepted":
            raise ValueError("match_already_accepted")
        if match.status != "proposed":
            raise ValueError(f"match_not_proposed:{match.status}")

        route = db.execute(
            select(Route)
            .where(Route.id == match.route_id)
            .with_for_update()
        ).scalar_one_or_none()
        
        if not route or not route.is_active:
            raise ValueError("route_not_found_or_inactive")

        old_snapshot = {
            "geom": route.geom,
            "distance_m": float(route.distance_m),
            "duration_s": float(route.duration_s),
        }

        parcel = db.execute(
            select(Parcel)
            .where(Parcel.id == match.parcel_id)
            .with_for_update()
        ).scalar_one_or_none()
        
        if not parcel:
            raise ValueError("parcel_not_found")
        if parcel.status in ("accepted", "cancelled", "rejected"):
            raise ValueError(f"parcel_not_pending:{parcel.status}")

        # Pobierz start/end trasy
        route_coords = db.execute(
            text("""
                SELECT
                  ST_X(start_point) AS start_lng, ST_Y(start_point) AS start_lat,
                  ST_X(end_point) AS end_lng, ST_Y(end_point) AS end_lat
                FROM routes WHERE id = :route_id
            """),
            {"route_id": route.id}
        ).mappings().first()
        
        if not route_coords:
            raise ValueError("route_coords_not_found")

        # Pobierz zaakceptowane paczki (w kolejności akceptacji)
        accepted_matches = db.execute(
            select(RouteParcelMatch)
            .where(RouteParcelMatch.route_id == route.id)
            .where(RouteParcelMatch.status == "accepted")
            .order_by(RouteParcelMatch.id)  # Kolejność akceptacji!
        ).scalars().all()

        # Przygotuj dane paczek (w kolejności akceptacji)
        parcels_data = []
        for m in accepted_matches:
            pcoords = db.execute(
                text("""
                    SELECT
                      ST_X(pickup_point) AS pickup_lng, ST_Y(pickup_point) AS pickup_lat,
                      ST_X(drop_point) AS drop_lng, ST_Y(drop_point) AS drop_lat
                    FROM parcels WHERE id = :pid
                """),
                {"pid": m.parcel_id}
            ).mappings().first()
            if pcoords:
                parcels_data.append({
                    "id": m.parcel_id,
                    "pickup": (pcoords["pickup_lng"], pcoords["pickup_lat"]),
                    "drop": (pcoords["drop_lng"], pcoords["drop_lat"]),
                })
        
        # Dodaj NOWĄ paczkę NA KOŃCU
        new_parcel_coords = db.execute(
            text("""
                SELECT
                  ST_X(pickup_point) AS pickup_lng, ST_Y(pickup_point) AS pickup_lat,
                  ST_X(drop_point) AS drop_lng, ST_Y(drop_point) AS drop_lat
                FROM parcels WHERE id = :pid
            """),
            {"pid": parcel.id}
        ).mappings().first()
        
        if not new_parcel_coords:
            raise ValueError("new_parcel_coords_not_found")
        
        parcels_data.append({
            "id": parcel.id,
            "pickup": (new_parcel_coords["pickup_lng"], new_parcel_coords["pickup_lat"]),
            "drop": (new_parcel_coords["drop_lng"], new_parcel_coords["drop_lat"]),
        })

        # SEKWENCYJNA optymalizacja
        start = (route_coords["start_lng"], route_coords["start_lat"])
        end = (route_coords["end_lng"], route_coords["end_lat"])
        
        optimized_waypoints = optimize_waypoints_greedy_forward(start, end, parcels_data)
        
        # OSRM z optymalną kolejnością
        variant = osrm_route(optimized_waypoints, with_geometry=True)

        geometry = variant.get("geometry")
        if not geometry or geometry["type"] != "LineString":
            raise ValueError("invalid_osrm_geometry")

        coords_list = geometry["coordinates"]
        new_geom = WKTElement(
            "LINESTRING(" + ", ".join(f"{lng} {lat}" for lng, lat in coords_list) + ")",
            srid=4326,
        )

        route.geom = new_geom
        route.distance_m = float(variant["distance_m"])
        route.duration_s = float(variant["duration_s"])

        new_snapshot = {
            "geom": new_geom,
            "distance_m": route.distance_m,
            "duration_s": route.duration_s,
        }

        log_route_change(
            db=db,
            route_id=route.id,
            change_type="parcel_accepted",
            changed_by=changed_by,
            parcel_id=parcel.id,
            old_snapshot=old_snapshot,
            new_snapshot=new_snapshot,
            notes=f"Match #{match.id} accepted. Total parcels: {len(parcels_data)} (sequential)",
        )

        match.status = "accepted"
        parcel.status = "accepted"

        db.query(RouteParcelMatch).filter(
            RouteParcelMatch.parcel_id == parcel.id,
            RouteParcelMatch.id != match.id,
        ).update({"status": "rejected"}, synchronize_session=False)

        return {
            "route_id": int(route.id),
            "parcel_id": int(parcel.id),
            "new_distance_m": float(route.distance_m),
            "new_duration_s": float(route.duration_s),
            "total_parcels": len(parcels_data),
            "optimizer": "sequential",
        }