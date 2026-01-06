# backend/app/waypoint_optimizer.py - SEQUENTIAL INSERTION
"""
Sequential insertion optimizer dla multi-parcel routing.

Strategia:
- NIE przelicza kolejności już zaakceptowanych paczek
- Nową paczkę wstawia w najlepsze miejsce w istniejącej sekwencji
- Zachowuje logiczny flow trasy (bez cofania się)
"""
from __future__ import annotations
from typing import List, Tuple
from .osrm import osrm_route


def optimize_waypoints(
    start: Tuple[float, float],
    end: Tuple[float, float],
    parcels: List[dict],  # [{"id": 1, "pickup": (lng, lat), "drop": (lng, lat)}]
) -> List[Tuple[float, float]]:
    """
    Sequential insertion: każda paczka wstawiana w najlepsze miejsce.
    
    NIE zmienia kolejności już istniejących paczek - tylko dodaje nową
    w optymalnym miejscu.
    
    Args:
        start: (lng, lat) początek trasy
        end: (lng, lat) koniec trasy
        parcels: Lista paczek [już zaakceptowane + nowa paczka]
        
    Returns:
        Lista waypoints w kolejności: [start, wp1, wp2, ..., end]
    """
    
    if not parcels:
        return [start, end]
    
    # Strategia: buduj sekwencję waypoints liniowo
    # Dla każdej paczki: pickup, potem drop (w najlepszym miejscu)
    
    waypoints = [start]
    
    for parcel in parcels:
        pickup = parcel["pickup"]
        drop = parcel["drop"]
        
        # Wstaw pickup w najlepsze miejsce
        best_pickup_pos = _find_best_insertion_position(waypoints, end, pickup)
        waypoints.insert(best_pickup_pos, pickup)
        
        # Wstaw drop w najlepsze miejsce (ale PO pickup!)
        best_drop_pos = _find_best_insertion_position(
            waypoints, 
            end, 
            drop, 
            min_position=best_pickup_pos + 1  # drop musi być po pickup
        )
        waypoints.insert(best_drop_pos, drop)
    
    waypoints.append(end)
    return waypoints


def _find_best_insertion_position(
    current_waypoints: List[Tuple[float, float]],
    end: Tuple[float, float],
    new_point: Tuple[float, float],
    min_position: int = 1,  # Nie wstawiaj przed start
) -> int:
    """
    Znajduje najlepszą pozycję do wstawienia punktu.
    
    Sprawdza każdą pozycję i wybiera tę która minimalizuje całkowity dystans.
    """
    
    if len(current_waypoints) < min_position:
        return len(current_waypoints)
    
    best_position = min_position
    best_distance = float('inf')
    
    # Spróbuj wstawić w każdej możliwej pozycji
    for pos in range(min_position, len(current_waypoints) + 1):
        test_waypoints = current_waypoints[:pos] + [new_point] + current_waypoints[pos:]
        test_waypoints_with_end = test_waypoints + [end]
        
        try:
            result = osrm_route(test_waypoints_with_end)
            distance = result["distance_m"]
            
            if distance < best_distance:
                best_distance = distance
                best_position = pos
        except:
            continue
    
    return best_position


def optimize_waypoints_simple(
    start: Tuple[float, float],
    end: Tuple[float, float],
    parcels: List[dict],
) -> List[Tuple[float, float]]:
    """
    Najprostsza strategia: FIFO (First In First Out).
    
    Każda paczka: pickup → drop, w kolejności dodawania.
    Zero optymalizacji, ale zawsze logiczna trasa.
    """
    
    waypoints = [start]
    
    for parcel in parcels:
        waypoints.append(parcel["pickup"])
        waypoints.append(parcel["drop"])
    
    waypoints.append(end)
    return waypoints


def optimize_waypoints_greedy_forward(
    start: Tuple[float, float],
    end: Tuple[float, float],
    parcels: List[dict],
) -> List[Tuple[float, float]]:
    """
    Greedy forward: zawsze wybieraj najbliższy dostępny punkt.
    
    Constraint: pickup przed drop tej samej paczki.
    NIE cofa się - zawsze idzie "do przodu".
    """
    
    waypoints = [start]
    current = start
    
    picked_up = set()
    delivered = set()
    
    remaining_parcels = {i: p for i, p in enumerate(parcels)}
    
    while remaining_parcels or (picked_up - delivered):
        
        candidates = []
        
        # Dostępne pickupy
        for p_id, parcel in remaining_parcels.items():
            pickup = parcel["pickup"]
            dist = _haversine_distance(current, pickup)
            candidates.append(("pickup", p_id, pickup, dist))
        
        # Dostępne dropy (tylko jeśli mamy pickup)
        for p_id in picked_up - delivered:
            if p_id in [pid for pid, _ in remaining_parcels.items()]:
                continue  # Skip if still in remaining
            parcel = parcels[p_id]
            drop = parcel["drop"]
            dist = _haversine_distance(current, drop)
            candidates.append(("drop", p_id, drop, dist))
        
        if not candidates:
            break
        
        # Wybierz najbliższy
        candidates.sort(key=lambda x: x[3])
        action, p_id, point, _ = candidates[0]
        
        waypoints.append(point)
        current = point
        
        if action == "pickup":
            picked_up.add(p_id)
            del remaining_parcels[p_id]
        else:  # drop
            delivered.add(p_id)
    
    waypoints.append(end)
    return waypoints


def _haversine_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Oblicza dystans haversine między dwoma punktami (w metrach)."""
    from math import radians, sin, cos, sqrt, atan2
    
    lon1, lat1 = p1
    lon2, lat2 = p2
    
    R = 6371000  # promień Ziemi w metrach
    
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c