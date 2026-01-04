from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import text

from .models import Route


def propose_matches_for_route(
    route_id: int,
    db: Session,
    buffer_m: float = 2000.0,  # 2 km – MVP
):
    """
    KROK 1 (ETAP 2):
    - wybór paczek w buforze trasy (PostGIS)
    - brak automatycznych decyzji
    - zwraca LISTĘ kandydatów (parcel_id)
    """

    # --- 1) Sprawdź trasę ---
    route = db.get(Route, route_id)
    if not route or not route.is_active:
        return []

    # --- 2) Zapytanie PostGIS ---
    # Uwaga:
    # - geometrie są w SRID 4326 (stopnie)
    # - bufor liczymy w metrach -> rzut do geography
    sql = text(
        """
        SELECT p.id AS parcel_id
        FROM parcels p
        WHERE
            p.status = 'pending'
            AND ST_DWithin(
                p.pickup_point::geography,
                :route_geom::geography,
                :buffer_m
            )
            AND ST_DWithin(
                p.drop_point::geography,
                :route_geom::geography,
                :buffer_m
            )
        """
    )

    rows = db.execute(
        sql,
        {
            "route_geom": route.geom,
            "buffer_m": buffer_m,
        },
    ).all()

    # --- 3) Zwróć TYLKO identyfikatory kandydatów ---
    return [r.parcel_id for r in rows]
