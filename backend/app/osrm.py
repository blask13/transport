# backend/app/osrm.py - IMPROVED VERSION
from __future__ import annotations

import httpx
import os
from typing import Literal

OSRM_URL = os.getenv("OSRM_URL", "http://osrm:5000")


class OSRMError(Exception):
    """Bazowy wyjątek dla błędów OSRM."""
    pass


class OSRMTimeoutError(OSRMError):
    """OSRM nie odpowiedział w czasie."""
    pass


class OSRMNoRouteError(OSRMError):
    """OSRM nie znalazł trasy między punktami."""
    pass


class OSRMServiceError(OSRMError):
    """OSRM zwrócił błąd serwisowy."""
    pass


def osrm_route(
    coords: list[tuple[float, float]],
    *,
    with_geometry: bool = False,
    timeout: int = 60,
) -> dict:
    """
    Pobiera trasę z OSRM.
    
    Args:
        coords: Lista (lng, lat) punktów
        with_geometry: Czy zwrócić pełną geometrię GeoJSON
        timeout: Timeout w sekundach
        
    Returns:
        {
            "distance_m": float,
            "duration_s": float,
            "geometry": dict | None  # jeśli with_geometry=True
        }
        
    Raises:
        OSRMTimeoutError: Gdy OSRM nie odpowiada
        OSRMNoRouteError: Gdy nie ma trasy między punktami
        OSRMServiceError: Inne błędy OSRM
    """
    if len(coords) < 2:
        raise ValueError("Potrzebne minimum 2 punkty")
    
    # Walidacja współrzędnych
    for lng, lat in coords:
        if not (-180 <= lng <= 180):
            raise ValueError(f"Nieprawidłowa longitude: {lng}")
        if not (-90 <= lat <= 90):
            raise ValueError(f"Nieprawidłowa latitude: {lat}")
    
    coord_str = ";".join(f"{lng},{lat}" for lng, lat in coords)
    
    if with_geometry:
        url = f"{OSRM_URL}/route/v1/driving/{coord_str}?overview=full&geometries=geojson"
    else:
        url = f"{OSRM_URL}/route/v1/driving/{coord_str}?overview=false"
    
    try:
        r = httpx.get(url, timeout=timeout)
        r.raise_for_status()
    except httpx.TimeoutException:
        raise OSRMTimeoutError(
            f"OSRM nie odpowiedział w ciągu {timeout}s. "
            "Trasa może być zbyt długa lub serwis niedostępny."
        )
    except httpx.HTTPStatusError as e:
        raise OSRMServiceError(
            f"OSRM zwrócił błąd {e.response.status_code}: {e.response.text}"
        )
    except httpx.RequestError as e:
        raise OSRMServiceError(
            f"Nie można połączyć się z OSRM: {str(e)}"
        )
    
    data = r.json()
    
    # OSRM może zwrócić 200 ale z kodem błędu w JSON
    if data.get("code") != "Ok":
        if data.get("code") == "NoRoute":
            raise OSRMNoRouteError(
                "Nie można znaleźć trasy między podanymi punktami. "
                "Sprawdź czy punkty są na drogach."
            )
        raise OSRMServiceError(
            f"OSRM zwrócił błąd: {data.get('code')} - {data.get('message', 'brak opisu')}"
        )
    
    if not data.get("routes"):
        raise OSRMNoRouteError("OSRM nie zwrócił żadnej trasy")
    
    route = data["routes"][0]
    
    result = {
        "distance_m": float(route["distance"]),
        "duration_s": float(route["duration"]),
    }
    
    if with_geometry:
        result["geometry"] = route["geometry"]
    
    return result


def validate_coords(coords: list[tuple[float, float]]) -> tuple[bool, str | None]:
    """
    Waliduje współrzędne bez odpytywania OSRM.
    
    Returns:
        (is_valid, error_message)
    """
    if len(coords) < 2:
        return False, "Potrzebne minimum 2 punkty"
    
    for i, (lng, lat) in enumerate(coords):
        if not (-180 <= lng <= 180):
            return False, f"Punkt {i+1}: nieprawidłowa longitude {lng}"
        if not (-90 <= lat <= 90):
            return False, f"Punkt {i+1}: nieprawidłowa latitude {lat}"
    
    return True, None