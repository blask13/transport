# backend/app/history.py
"""
Moduł do śledzenia historii zmian tras.
"""
from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Text,
)
from sqlalchemy.sql import func
from geoalchemy2 import Geometry

from .models import Base


class RouteHistory(Base):
    """Historia zmian trasy."""
    
    __tablename__ = "route_history"

    id = Column(BigInteger, primary_key=True)
    route_id = Column(
        BigInteger, 
        ForeignKey("routes.id", ondelete="CASCADE"), 
        nullable=False
    )
    
    changed_by = Column(Text, nullable=False)  # user handle lub "system"
    change_type = Column(Text, nullable=False)
    parcel_id = Column(
        BigInteger, 
        ForeignKey("parcels.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Snapshot PRZED zmianą
    old_geom = Column(Geometry("LINESTRING", srid=4326), nullable=True)
    old_distance_m = Column(Float, nullable=True)
    old_duration_s = Column(Float, nullable=True)
    
    # Snapshot PO zmianie
    new_geom = Column(Geometry("LINESTRING", srid=4326), nullable=True)
    new_distance_m = Column(Float, nullable=True)
    new_duration_s = Column(Float, nullable=True)
    
    # Delta (dla parcel_accepted)
    delta_distance_m = Column(Float, nullable=True)
    delta_duration_s = Column(Float, nullable=True)
    
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "change_type IN ('created','parcel_accepted','cancelled')",
            name="chk_route_history_change_type",
        ),
    )


def log_route_change(
    db,
    route_id: int,
    change_type: str,
    changed_by: str = "system",
    parcel_id: int | None = None,
    old_snapshot: dict | None = None,
    new_snapshot: dict | None = None,
    notes: str | None = None,
):
    """
    Helper do logowania zmian trasy.
    
    Args:
        db: Session
        route_id: ID trasy
        change_type: 'created' | 'parcel_accepted' | 'cancelled'
        changed_by: kto wykonał zmianę (user handle)
        parcel_id: ID paczki (dla parcel_accepted)
        old_snapshot: {geom, distance_m, duration_s}
        new_snapshot: {geom, distance_m, duration_s}
        notes: dodatkowe notatki
    """
    entry = RouteHistory(
        route_id=route_id,
        changed_by=changed_by,
        change_type=change_type,
        parcel_id=parcel_id,
        notes=notes,
    )
    
    if old_snapshot:
        entry.old_geom = old_snapshot.get("geom")
        entry.old_distance_m = old_snapshot.get("distance_m")
        entry.old_duration_s = old_snapshot.get("duration_s")
    
    if new_snapshot:
        entry.new_geom = new_snapshot.get("geom")
        entry.new_distance_m = new_snapshot.get("distance_m")
        entry.new_duration_s = new_snapshot.get("duration_s")
    
    # Oblicz deltę
    if old_snapshot and new_snapshot:
        entry.delta_distance_m = (
            new_snapshot.get("distance_m", 0) - old_snapshot.get("distance_m", 0)
        )
        entry.delta_duration_s = (
            new_snapshot.get("duration_s", 0) - old_snapshot.get("duration_s", 0)
        )
    
    db.add(entry)
    db.flush()
    
    return entry