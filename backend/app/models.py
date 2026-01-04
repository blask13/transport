# backend\app\models.py
from __future__ import annotations
from sqlalchemy.orm import DeclarativeBase

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Text,
)
from sqlalchemy.sql import func
from geoalchemy2 import Geometry

class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)
    handle = Column(Text, unique=True, nullable=False)
    role = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("role IN ('courier','sender','admin')", name="chk_users_role"),
    )


class Route(Base):
    __tablename__ = "routes"

    id = Column(BigInteger, primary_key=True)
    courier_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(Text)
    start_point = Column(Geometry("POINT", srid=4326), nullable=False)
    end_point = Column(Geometry("POINT", srid=4326), nullable=False)
    geom = Column(Geometry("LINESTRING", srid=4326), nullable=False)
    distance_m = Column(Float, nullable=False)
    duration_s = Column(Float, nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Parcel(Base):
    __tablename__ = "parcels"

    id = Column(BigInteger, primary_key=True)
    sender_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))

    title = Column(Text, nullable=True)

    pickup_point = Column(Geometry("POINT", srid=4326), nullable=False)
    drop_point = Column(Geometry("POINT", srid=4326), nullable=False)

    pickup_after = Column(DateTime(timezone=True), nullable=True)
    pickup_before = Column(DateTime(timezone=True), nullable=True)
    dropoff_after = Column(DateTime(timezone=True), nullable=True)
    dropoff_before = Column(DateTime(timezone=True), nullable=True)

    weight_kg = Column(Float, nullable=True)
    size_class = Column(Text, nullable=True)

    status = Column(Text, nullable=False, server_default="pending")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','offered','accepted','rejected','cancelled')",
            name="chk_parcels_status",
        ),
    )
class RouteParcelMatch(Base):
    __tablename__ = "route_parcel_matches"

    id = Column(BigInteger, primary_key=True)

    route_id = Column(
        BigInteger,
        ForeignKey("routes.id", ondelete="CASCADE"),
        nullable=False,
    )
    parcel_id = Column(
        BigInteger,
        ForeignKey("parcels.id", ondelete="CASCADE"),
        nullable=False,
    )

    status = Column(
        Text,
        nullable=False,
        server_default="proposed",
    )

    # Δ względem trasy bazowej
    delta_distance_m = Column(Float, nullable=False)
    delta_duration_s = Column(Float, nullable=False)

    # opcjonalnie: snapshoty
    base_distance_m = Column(Float, nullable=True)
    base_duration_s = Column(Float, nullable=True)
    new_distance_m = Column(Float, nullable=True)
    new_duration_s = Column(Float, nullable=True)

    algorithm_version = Column(Text, nullable=False, server_default="mvp-0.1")

    debug = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed','accepted','rejected','expired')",
            name="chk_route_parcel_match_status",
        ),
    )
