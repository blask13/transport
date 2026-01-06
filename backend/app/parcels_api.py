# backend/app/parcels_api.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy import func
from .models import RouteParcelMatch

from .db import get_db
from .models import Parcel
from .schemas import ParcelCreate, ParcelOut, ParcelReadOut
import json
router = APIRouter(prefix="/parcels", tags=["parcels"])

def _geojson(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)

@router.post("/{parcel_id}/confirm-delivery")
def confirm_delivery(parcel_id: int, db: Session = Depends(get_db)):
    """
    Nadawca potwierdza odbiór paczki.
    Status: delivered → completed
    """
    parcel = db.get(Parcel, parcel_id)
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    
    if parcel.status != "delivered":
        raise HTTPException(
            status_code=400,
            detail=f"Can only confirm delivered parcels. Current: {parcel.status}"
        )
    
    parcel.status = "completed"
    db.commit()
    
    return {
        "status": "completed",
        "parcel_id": parcel_id,
        "message": "Delivery confirmed"
    }


@router.post("/{parcel_id}/dispute-delivery")
def dispute_delivery(
    parcel_id: int,
    reason: str,
    db: Session = Depends(get_db)
):
    """
    Nadawca zgłasza problem z dostawą.
    Status: delivered → disputed
    """
    parcel = db.get(Parcel, parcel_id)
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    
    if parcel.status != "delivered":
        raise HTTPException(
            status_code=400,
            detail=f"Can only dispute delivered parcels. Current: {parcel.status}"
        )
    
    # Zmień status
    parcel.status = "disputed"
    
    # Znajdź kuriera
    match = db.execute(
        select(RouteParcelMatch)
        .where(RouteParcelMatch.parcel_id == parcel_id)
        .where(RouteParcelMatch.status == "accepted")
    ).scalar_one_or_none()
    
    courier_id = None
    if match:
        route = db.get(Route, match.route_id)
        if route:
            courier_id = route.courier_id
    
    # Utwórz spór
    from .models import Dispute
    dispute = Dispute(
        parcel_id=parcel_id,
        reported_by=parcel.sender_id,
        courier_id=courier_id,
        reason=reason,
        status="open"
    )
    
    db.add(dispute)
    db.commit()
    db.refresh(dispute)
    
    return {
        "status": "disputed",
        "parcel_id": parcel_id,
        "dispute_id": dispute.id,
        "message": "Dispute created"
    }

@router.post("", response_model=ParcelOut)
def create_parcel(payload: ParcelCreate, db: Session = Depends(get_db)):
    parcel = Parcel(
        sender_id=payload.sender_id,
        pickup_point=func.ST_SetSRID(
            func.ST_MakePoint(payload.pickup.lng, payload.pickup.lat), 4326
        ),
        drop_point=func.ST_SetSRID(
            func.ST_MakePoint(payload.drop.lng, payload.drop.lat), 4326
        ),
        status="pending",
    )

    db.add(parcel)
    db.commit()
    db.refresh(parcel)

    return ParcelOut(id=parcel.id, status=parcel.status)

@router.get("", response_model=list[ParcelReadOut])
def list_my_parcels(sender_id: int, db: Session = Depends(get_db)):
    rows = db.execute(
        select(
            Parcel.id,
            Parcel.status,
            func.ST_AsGeoJSON(Parcel.pickup_point).label("pickup_point"),
            func.ST_AsGeoJSON(Parcel.drop_point).label("drop_point"),
        ).where(Parcel.sender_id == sender_id)
    ).mappings().all()
    return [
        ParcelReadOut(
            id=r["id"],
            status=r["status"],
            pickup_point=_geojson(r["pickup_point"]),
            drop_point=_geojson(r["drop_point"]),
        )
        for r in rows
    ]

@router.get("/{parcel_id}", response_model=ParcelReadOut)
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

@router.delete("/{parcel_id}")
def cancel_parcel(parcel_id: int, db: Session = Depends(get_db)):
    """
    Anuluje paczkę (zmienia status na 'cancelled').
    """
    parcel = db.get(Parcel, parcel_id)
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    if parcel.status == "accepted":
        raise HTTPException(status_code=400, detail="Parcel already accepted")

    parcel.status = "cancelled"

    # ❗ unieważnij wszystkie propozycje tej paczki
    db.query(RouteParcelMatch).filter(
        RouteParcelMatch.parcel_id == parcel.id,
        RouteParcelMatch.status.in_(["proposed"]),
    ).update(
        {"status": "rejected"},
        synchronize_session=False,
    )
    
    db.commit()

    return {"status": "cancelled"}


@router.delete("/{parcel_id}/permanent")
def delete_parcel_permanently(parcel_id: int, db: Session = Depends(get_db)):
    """
    Fizyczne usunięcie paczki z bazy danych.
    
    TYLKO dla paczek ze statusem 'cancelled'.
    Usuwa paczkę i wszystkie powiązane propozycje (cascade).
    """
    parcel = db.get(Parcel, parcel_id)
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    
    if parcel.status != "cancelled":
        raise HTTPException(
            status_code=400, 
            detail=f"Can only delete cancelled parcels. Current status: {parcel.status}"
        )
    
    # Kasowanie (propozycje usuną się przez ON DELETE CASCADE)
    db.delete(parcel)
    db.commit()
    
    return {
        "status": "deleted",
        "parcel_id": parcel_id,
        "message": "Parcel permanently deleted from database"
    }