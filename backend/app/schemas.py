# backend\app\schemas.py
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, List

class LngLat(BaseModel):
    lng: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)


class RouteCreate(BaseModel):
    courier_id: int
    title: str | None = None
    start: LngLat
    end: LngLat


class RouteOut(BaseModel):
    id: int
    courier_id: int
    distance_m: float
    duration_s: float


class ParcelCreate(BaseModel):
    sender_id: int | None = None
    pickup: LngLat
    drop: LngLat


class ParcelOut(BaseModel):
    id: int
    status: str


# =========================
# READ MODELS (pod frontend)
# =========================

GeoJSON = Dict[str, Any]


class RouteReadOut(BaseModel):
    id: int
    courier_id: int
    title: str | None
    start_point: GeoJSON
    end_point: GeoJSON
    geom: GeoJSON
    distance_m: float
    duration_s: float


class ParcelReadOut(BaseModel):
    id: int
    status: str
    pickup_point: GeoJSON
    drop_point: GeoJSON


class MatchReadOut(BaseModel):
    id: int
    route_id: int
    parcel_id: int
    status: str
    delta_distance_m: float
    delta_duration_s: float
    pickup_to_route_m: float
    drop_to_route_m: float
    pickup_point: GeoJSON
    drop_point: GeoJSON

class RouteMatchesReadOut(BaseModel):
    route_id: int
    items: List[MatchReadOut]
