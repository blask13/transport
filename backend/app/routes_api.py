# backend\app\routes_api.py
from __future__ import annotations

import os
import httpx
import json
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy import func
from .history import RouteHistory
from sqlalchemy import desc

from .db import get_db
from .models import Route, Parcel, RouteParcelMatch
from .schemas import (
    RouteCreate,
    RouteOut,
    RouteReadOut,
    ParcelReadOut,
    RouteMatchesReadOut,
    MatchReadOut,
)

from .geo import point_wkt, linestring_wkt
from .matching import accept_match, propose_matches_for_route

# URL do OSRM (z docker-compose)
OSRM_URL = os.getenv("OSRM_URL", "http://osrm:5000")

router = APIRouter(prefix="/routes", tags=["routes"])

def _geojson(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)

@router.post("", response_model=RouteOut)
async def create_route(payload: RouteCreate, db: Session = Depends(get_db)):
    """
    Tworzy trasę kuriera:
    - pyta OSRM o trasę po drogach
    - zapisuje LINESTRING do PostGIS
    """

    if len(payload.points) < 2:
        raise HTTPException(status_code=400, detail="At least 2 points required")

    coords = ";".join(
        f"{p.lng},{p.lat}" for p in payload.points
    )
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
        start_point=point_wkt(payload.points[0].lng, payload.points[0].lat),
        end_point=point_wkt(payload.points[-1].lng, payload.points[-1].lat),
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
def list_routes(
    courier_id: Optional[int] = None,
    active_only: int = 1,
    db: Session = Depends(get_db),
):
    """
    Prosta lista tras – debug / test
    """
    q = select(
        Route.id,
        Route.courier_id,
        Route.distance_m,
        Route.duration_s,
        Route.is_active,
    )
    if courier_id is not None:
        q = q.where(Route.courier_id == courier_id)
    if active_only:
        q = q.where(Route.is_active.is_(True))

    rows = db.execute(q).all()

    return [
        {
            "id": r.id,
            "courier_id": r.courier_id,
            "distance_m": r.distance_m,
            "duration_s": r.duration_s,
            "is_active": r.is_active,
        }
        for r in rows
    ]

# =====================
# READ: pojedyncza trasa
# =====================

@router.get("/{route_id}", response_model=RouteReadOut)
def get_route(route_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        select(
            Route.id,
            Route.courier_id,
            Route.title,
            func.ST_AsGeoJSON(Route.start_point).label("start_point"),
            func.ST_AsGeoJSON(Route.end_point).label("end_point"),
            func.ST_AsGeoJSON(Route.geom).label("geom"),
            Route.distance_m,
            Route.duration_s,
        ).where(Route.id == route_id)
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Route not found")

    return RouteReadOut(
        id=row["id"],
        courier_id=row["courier_id"],
        title=row["title"],
        start_point=_geojson(row["start_point"]),
        end_point=_geojson(row["end_point"]),
        geom=_geojson(row["geom"]),
        distance_m=float(row["distance_m"]),
        duration_s=float(row["duration_s"]),
    )


# =====================
# READ: propozycje trasy
# =====================

@router.get("/{route_id}/matches", response_model=RouteMatchesReadOut)
def get_route_matches(
    route_id: int,
    status: str = "proposed",
    db: Session = Depends(get_db),
):
    exists = db.execute(
        select(Route.id).where(Route.id == route_id)
    ).scalar_one_or_none()
    if not exists:
        raise HTTPException(status_code=404, detail="Route not found")

    rows = db.execute(
        select(
            RouteParcelMatch.id,
            RouteParcelMatch.route_id,
            RouteParcelMatch.parcel_id,
            RouteParcelMatch.status,
            RouteParcelMatch.delta_distance_m,
            RouteParcelMatch.delta_duration_s,
            RouteParcelMatch.pickup_to_route_m,
            RouteParcelMatch.drop_to_route_m,
            func.ST_AsGeoJSON(Parcel.pickup_point).label("pickup_point"),
            func.ST_AsGeoJSON(Parcel.drop_point).label("drop_point"),            
        )
        .join(Parcel, Parcel.id == RouteParcelMatch.parcel_id)        
        .where(RouteParcelMatch.route_id == route_id)
        .where(RouteParcelMatch.status == status)        
        .order_by(
            RouteParcelMatch.delta_distance_m.asc(),
            RouteParcelMatch.delta_duration_s.asc(),
        )
    ).mappings().all()

    return RouteMatchesReadOut(
        route_id=route_id,
        items=[
            MatchReadOut(
                id=r["id"],
                route_id=r["route_id"],
                parcel_id=r["parcel_id"],
                status=r["status"],
                delta_distance_m=float(r["delta_distance_m"]),
                delta_duration_s=float(r["delta_duration_s"]),
                pickup_to_route_m=float(r["pickup_to_route_m"]),
                drop_to_route_m=float(r["drop_to_route_m"]),
                pickup_point=_geojson(r["pickup_point"]),
                drop_point=_geojson(r["drop_point"]),                
            )
            for r in rows
        ],
    )


# =====================
# READ: paczka
# =====================

@router.get("/parcels/{parcel_id}", response_model=ParcelReadOut)
def get_parcel(parcel_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        select(
            Parcel.id,
            Parcel.status,
            func.ST_AsGeoJSON(Parcel.pickup_point).label("pickup_point"),
            func.ST_AsGeoJSON(Parcel.drop_point).label("drop_point"),
        ).where(Parcel.id == parcel_id)
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Parcel not found")

    return ParcelReadOut(
        id=row["id"],
        status=row["status"],
        pickup_point=_geojson(row["pickup_point"]),
        drop_point=_geojson(row["drop_point"]),
    )

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

@router.post("/matches/{match_id}/accept")
def accept_route_match(match_id: int, db: Session = Depends(get_db)):
    """
    ETAP 4:
    Kurier akceptuje propozycję wpięcia paczki do trasy
    """
    try:
        return accept_match(match_id=match_id, db=db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))



# Fragment do zastąpienia w backend/app/routes_api.py

@router.delete("/{route_id}")
def cancel_route(route_id: int, db: Session = Depends(get_db)):
    """
    Anuluje trasę i przywraca paczki do stanu 'pending'.
    
    LOGIKA:
    1. Trasa is_active = False
    2. Propozycje (proposed) → expired
    3. Paczki (accepted na tej trasie) → pending (żeby inni mogli je wziąć)
    4. Paczki (accepted, ale nie dostarczonych) → pending
    """
    route = db.get(Route, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    
    # 1. Anuluj trasę
    route.is_active = False

    # 2. Odrzuć wiszące propozycje tej trasy
    db.query(RouteParcelMatch).filter(
        RouteParcelMatch.route_id == route.id,
        RouteParcelMatch.status == "proposed",
    ).update(
        {"status": "expired"},
        synchronize_session=False,
    )

    # 3. NOWE: Przywróć paczki do pending
    # Znajdź wszystkie zaakceptowane paczki tej trasy
    accepted_matches = db.query(RouteParcelMatch).filter(
        RouteParcelMatch.route_id == route.id,
        RouteParcelMatch.status == "accepted",
    ).all()
    
    for match in accepted_matches:
        parcel = db.get(Parcel, match.parcel_id)
        if parcel and parcel.status == "accepted":
            # Przywróć paczkę do pending
            parcel.status = "pending"
            
            # Oznacz match jako expired
            match.status = "expired"
    
    db.commit()
    
    return {
        "status": "cancelled",
        "parcels_restored": len(accepted_matches),
        "message": f"Trasa anulowana. {len(accepted_matches)} paczek przywróconych do pending."
    }

@router.get("/{route_id}/history")
def get_route_history(
    route_id: int,
    db: Session = Depends(get_db)
):
    """
    Historia zmian trasy - timeline.
    """
    # Sprawdź czy trasa istnieje
    exists = db.execute(
        select(Route.id).where(Route.id == route_id)
    ).scalar_one_or_none()
    
    if not exists:
        raise HTTPException(status_code=404, detail="Route not found")
    
    # Pobierz historię
    rows = db.execute(
        select(
            RouteHistory.id,
            RouteHistory.change_type,
            RouteHistory.changed_by,
            RouteHistory.parcel_id,
            RouteHistory.old_distance_m,
            RouteHistory.old_duration_s,
            RouteHistory.new_distance_m,
            RouteHistory.new_duration_s,
            RouteHistory.delta_distance_m,
            RouteHistory.delta_duration_s,
            RouteHistory.notes,
            RouteHistory.created_at,
        )
        .where(RouteHistory.route_id == route_id)
        .order_by(desc(RouteHistory.created_at))
    ).mappings().all()
    
    return {
        "route_id": route_id,
        "history": [
            {
                "id": r["id"],
                "change_type": r["change_type"],
                "changed_by": r["changed_by"],
                "parcel_id": r["parcel_id"],
                "old_distance_m": r["old_distance_m"],
                "old_duration_s": r["old_duration_s"],
                "new_distance_m": r["new_distance_m"],
                "new_duration_s": r["new_duration_s"],
                "delta_distance_m": r["delta_distance_m"],
                "delta_duration_s": r["delta_duration_s"],
                "notes": r["notes"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    }