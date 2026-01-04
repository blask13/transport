# backend\app\routes_api.py
from __future__ import annotations

import os
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from .db import get_db
from .models import Route
from .schemas import RouteCreate, RouteOut
from .geo import point_wkt, linestring_wkt

# URL do OSRM (z docker-compose)
OSRM_URL = os.getenv("OSRM_URL", "http://osrm:5000")

router = APIRouter(prefix="/routes", tags=["routes"])


@router.post("", response_model=RouteOut)
async def create_route(payload: RouteCreate, db: Session = Depends(get_db)):
    """
    Tworzy trasę kuriera:
    - pyta OSRM o trasę po drogach
    - zapisuje LINESTRING do PostGIS
    """

    coords = f"{payload.start.lng},{payload.start.lat};{payload.end.lng},{payload.end.lat}"
    url = f"{OSRM_URL}/route/v1/driving/{coords}?overview=full&geometries=geojson"

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(120.0),
        limits=httpx.Limits(max_keepalive_connections=0),
    ) as client:
        r = await client.get(url)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="OSRM routing error")

    data = r.json()
    if not data.get("routes"):
        raise HTTPException(status_code=400, detail="No route found")

    route0 = data["routes"][0]
    geometry = route0["geometry"]          # GeoJSON LineString
    coords_list = geometry["coordinates"]  # [[lng, lat], ...]

    db_obj = Route(
        courier_id=payload.courier_id,
        title=payload.title,
        start_point=point_wkt(payload.start.lng, payload.start.lat),
        end_point=point_wkt(payload.end.lng, payload.end.lat),
        geom=linestring_wkt([(lng, lat) for lng, lat in coords_list]),
        distance_m=float(route0["distance"]),
        duration_s=float(route0["duration"]),
        is_active=True,
    )

    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)

    return RouteOut(
        id=int(db_obj.id),
        courier_id=int(db_obj.courier_id),
        distance_m=float(db_obj.distance_m),
        duration_s=float(db_obj.duration_s),
    )


@router.get("")
def list_routes(db: Session = Depends(get_db)):
    """
    Prosta lista tras – debug / test
    """
    rows = db.execute(
        select(
            Route.id,
            Route.courier_id,
            Route.distance_m,
            Route.duration_s,
        )
    ).all()

    return [
        {
            "id": r.id,
            "courier_id": r.courier_id,
            "distance_m": r.distance_m,
            "duration_s": r.duration_s,
        }
        for r in rows
    ]
from .matching import propose_matches_for_route


@router.post("/{route_id}/propose")
def propose_for_route(route_id: int, db: Session = Depends(get_db)):
    """
    DEBUG / MVP:
    Zwraca ID paczek w buforze trasy
    """
    proposals = propose_matches_for_route(route_id=route_id, db=db)
    return {
        "route_id": route_id,
        "proposals": proposals,
    }
