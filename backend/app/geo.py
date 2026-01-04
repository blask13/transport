from __future__ import annotations

from typing import Iterable, Tuple
from geoalchemy2.elements import WKTElement


def point_wkt(lng: float, lat: float) -> WKTElement:
    return WKTElement(f"POINT({lng} {lat})", srid=4326)


def linestring_wkt(coords: Iterable[Tuple[float, float]]) -> WKTElement:
    pts = ", ".join(f"{lng} {lat}" for lng, lat in coords)
    return WKTElement(f"LINESTRING({pts})", srid=4326)
