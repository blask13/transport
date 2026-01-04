# backend\app\osrm.py
import httpx
import os

OSRM_URL = os.getenv("OSRM_URL", "http://osrm:5000")


def osrm_route(
    coords: list[tuple[float, float]],
    *,
    with_geometry: bool = False,
) -> dict:
    """
    coords: [(lng, lat), ...]
    Zwraca:
      - zawsze: distance_m, duration_s
      - opcjonalnie: geometry (GeoJSON LineString)
    """
    coord_str = ";".join(f"{lng},{lat}" for lng, lat in coords)

    if with_geometry:
        url = f"{OSRM_URL}/route/v1/driving/{coord_str}?overview=full&geometries=geojson"
    else:
        url = f"{OSRM_URL}/route/v1/driving/{coord_str}?overview=false"

    r = httpx.get(url, timeout=60)
    r.raise_for_status()
    data = r.json()

    route = data["routes"][0]
    result = {
        "distance_m": route["distance"],
        "duration_s": route["duration"],
    }

    if with_geometry:
        result["geometry"] = route["geometry"]  # GeoJSON LineString

    return result