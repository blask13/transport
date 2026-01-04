import httpx
import os

OSRM_URL = os.getenv("OSRM_URL", "http://osrm:5000")


def osrm_route(coords: list[tuple[float, float]]) -> dict:
    """
    coords: [(lng, lat), ...]
    Zwraca: {distance_m, duration_s}
    """
    coord_str = ";".join(f"{lng},{lat}" for lng, lat in coords)
    url = f"{OSRM_URL}/route/v1/driving/{coord_str}?overview=false"

    r = httpx.get(url, timeout=60)
    r.raise_for_status()
    data = r.json()

    route = data["routes"][0]
    return {
        "distance_m": route["distance"],
        "duration_s": route["duration"],
    }
