from __future__ import annotations

from pydantic import BaseModel, Field


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
