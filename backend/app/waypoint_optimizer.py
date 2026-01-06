# backend/app/waypoint_optimizer.py
"""
Optymalizacja kolejności waypoints dla multi-parcel routing.

Problem: Mając N paczek, znaleźć optymalną kolejność odbioru/dostawy
minimalizującą całkowity dystans, z constraintem że pickup musi być przed drop.

Algorytm: Greedy nearest neighbor z constraintami.
"""
from __future__ import annotations
from typing import List, Tuple
from .osrm import osrm_route
import itertools


def optimize_waypoints(
    start: Tuple[float, float],
    end: Tuple[float, float],
    parcels: List[dict],  # [{"id": 1, "pickup": (lng, lat), "drop": (lng, lat)}]
    max_permutations: int = 5040,  # 7! = dla max 7 paczek brute force
) -> List[Tuple[float, float]]:
    """
    Optymalizuje kolejność waypoints dla multi-parcel routing.
    
    Args:
        start: (lng, lat) początek trasy
        end: (lng, lat) koniec trasy
        parcels: Lista paczek z pickup/drop
        max_permutations: Maksymalna liczba permutacji do sprawdzenia
        
    Returns:
        Lista waypoints w optymalnej kolejności: [start, p1, p2, ..., end]
        
    Strategy:
        - Dla małej liczby paczek (≤3): brute force wszystkie permutacje
        - Dla średniej (4-6): greedy nearest neighbor
        - Dla dużej (7+): greedy z ograniczonymi permutacjami
    """
    
    if not parcels:
        return [start, end]
    
    n_parcels = len(parcels)
    
    # Strategia zależnie od liczby paczek
    if n_parcels <= 3:
        # Brute force - sprawdź wszystkie permutacje
        return _optimize_brute_force(start, end, parcels)
    else:
        # Greedy nearest neighbor
        return _optimize_greedy(start, end, parcels)


def _optimize_brute_force(
    start: Tuple[float, float],
    end: Tuple[float, float],
    parcels: List[dict],
) -> List[Tuple[float, float]]:
    """
    Brute force: sprawdza wszystkie permutacje paczek.
    Dla każdej permutacji generuje wszystkie możliwe wstawienia drop'ów.
    """
    
    best_distance = float('inf')
    best_waypoints = None
    
    # Permutacje kolejności paczek
    for parcel_order in itertools.permutations(parcels):
        # Dla każdej permutacji, spróbuj różne pozycje drop'ów
        # (ale zawsze drop po pickup tej samej paczki)
        waypoints_candidates = _generate_drop_positions(parcel_order)
        
        for waypoints in waypoints_candidates:
            full_waypoints = [start] + waypoints + [end]
            
            # Sprawdź dystans przez OSRM
            try:
                result = osrm_route(full_waypoints)
                if result["distance_m"] < best_distance:
                    best_distance = result["distance_m"]
                    best_waypoints = full_waypoints
            except:
                continue
    
    return best_waypoints if best_waypoints else [start, end]


def _generate_drop_positions(parcel_order: Tuple[dict]) -> List[List[Tuple[float, float]]]:
    """
    Dla danej kolejności paczek, generuje możliwe pozycje drop'ów.
    
    Przykład: paczki A, B
    - [pickup_A, drop_A, pickup_B, drop_B]
    - [pickup_A, pickup_B, drop_A, drop_B]
    - [pickup_A, pickup_B, drop_B, drop_A]
    """
    
    n = len(parcel_order)
    
    # Dla 1-2 paczek: wszystkie kombinacje
    if n <= 2:
        return _generate_all_drop_positions(parcel_order)
    
    # Dla 3+ paczek: tylko sensowne strategie
    return _generate_heuristic_drop_positions(parcel_order)


def _generate_all_drop_positions(parcel_order: Tuple[dict]) -> List[List[Tuple[float, float]]]:
    """Generuje WSZYSTKIE możliwe pozycje drop'ów (dla małej liczby paczek)."""
    
    results = []
    
    def backtrack(waypoints, remaining_pickups, remaining_drops):
        if not remaining_pickups and not remaining_drops:
            results.append(waypoints[:])
            return
        
        # Dodaj pickup (jeśli są)
        for i, (p_id, pickup) in enumerate(remaining_pickups):
            new_waypoints = waypoints + [pickup]
            new_pickups = remaining_pickups[:i] + remaining_pickups[i+1:]
            new_drops = remaining_drops + [(p_id, parcel_order[p_id]["drop"])]
            backtrack(new_waypoints, new_pickups, new_drops)
        
        # Dodaj drop (jeśli są i pickup już był)
        for i, (p_id, drop) in enumerate(remaining_drops):
            new_waypoints = waypoints + [drop]
            new_drops = remaining_drops[:i] + remaining_drops[i+1:]
            backtrack(new_waypoints, remaining_pickups, new_drops)
    
    initial_pickups = [(i, p["pickup"]) for i, p in enumerate(parcel_order)]
    backtrack([], initial_pickups, [])
    
    return results


def _generate_heuristic_drop_positions(parcel_order: Tuple[dict]) -> List[List[Tuple[float, float]]]:
    """
    Dla 3+ paczek: generuje tylko heurystyczne strategie.
    
    Strategie:
    1. FIFO: pickup_1, drop_1, pickup_2, drop_2, ...
    2. Batch pickups: pickup_all, then drop_all
    3. Mixed: pickup pół, drop pół, pickup reszta, drop reszta
    """
    
    strategies = []
    
    # Strategia 1: FIFO (First In First Out)
    fifo = []
    for p in parcel_order:
        fifo.append(p["pickup"])
        fifo.append(p["drop"])
    strategies.append(fifo)
    
    # Strategia 2: Batch (wszystkie pickupy, potem wszystkie dropy)
    batch = [p["pickup"] for p in parcel_order] + [p["drop"] for p in parcel_order]
    strategies.append(batch)
    
    # Strategia 3: Batch reversed (wszystkie pickupy, dropy w odwrotnej kolejności)
    batch_rev = [p["pickup"] for p in parcel_order] + [p["drop"] for p in reversed(parcel_order)]
    strategies.append(batch_rev)
    
    return strategies


def _optimize_greedy(
    start: Tuple[float, float],
    end: Tuple[float, float],
    parcels: List[dict],
) -> List[Tuple[float, float]]:
    """
    Greedy nearest neighbor z constraintami.
    
    Algorytm:
    1. Zacznij od start
    2. W każdym kroku wybierz najbliższy dostępny punkt (pickup lub drop)
    3. Constraint: nie możesz wziąć drop jeśli nie masz pickup
    4. Kontynuuj aż wszystkie punkty odwiedzone
    5. Dodaj end
    """
    
    waypoints = [start]
    current = start
    
    picked_up = set()  # IDs paczek które już mamy
    delivered = set()  # IDs paczek które już dostarczyliśmy
    
    available_pickups = {i: p["pickup"] for i, p in enumerate(parcels)}
    available_drops = {i: p["drop"] for i, p in enumerate(parcels)}
    
    while available_pickups or (picked_up - delivered):
        
        candidates = []
        
        # Dostępne pickupy
        for p_id, pickup in available_pickups.items():
            dist = _haversine_distance(current, pickup)
            candidates.append(("pickup", p_id, pickup, dist))
        
        # Dostępne dropy (tylko jeśli mamy pickup)
        for p_id in picked_up - delivered:
            drop = available_drops[p_id]
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
            del available_pickups[p_id]
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