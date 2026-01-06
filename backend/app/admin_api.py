# backend/app/admin_api.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from .models import Parcel 

from .db import get_db
from .tasks import expire_old_proposals, cleanup_cancelled_parcel_matches

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/expire-proposals")
def trigger_expire_proposals(
    max_age_hours: int = 24,
    db: Session = Depends(get_db)
):
    """
    Ręczne wyzwolenie expiry starych propozycji.
    W produkcji: to byłby cronjob.
    """
    result = expire_old_proposals(db, max_age_hours)
    return result


@router.post("/cleanup-cancelled")
def trigger_cleanup_cancelled(db: Session = Depends(get_db)):
    """
    Czyści propozycje dla anulowanych paczek.
    """
    result = cleanup_cancelled_parcel_matches(db)
    return result


@router.get("/stats")
def get_system_stats(db: Session = Depends(get_db)):
    """
    Statystyki systemowe - dla debugging/monitoring.
    """
    stats = {}
    
    # Trasy
    routes = db.execute(text("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN is_active THEN 1 ELSE 0 END) as active
        FROM routes
    """)).mappings().first()
    stats["routes"] = dict(routes)
    
    # Paczki
    parcels = db.execute(text("""
        SELECT 
            status,
            COUNT(*) as count
        FROM parcels
        GROUP BY status
    """)).mappings().all()
    stats["parcels"] = {row["status"]: row["count"] for row in parcels}
    
    # Propozycje
    matches = db.execute(text("""
        SELECT 
            status,
            COUNT(*) as count
        FROM route_parcel_matches
        GROUP BY status
    """)).mappings().all()
    stats["matches"] = {row["status"]: row["count"] for row in matches}
    
    return stats


@router.get("/health-detailed")
def health_detailed(db: Session = Depends(get_db)):
    """
    Szczegółowy healthcheck z sprawdzeniem DB i OSRM.
    """
    status = {
        "database": "unknown",
        "osrm": "unknown",
    }
    
    # Test DB
    try:
        db.execute(text("SELECT 1"))
        status["database"] = "ok"
    except Exception as e:
        status["database"] = f"error: {str(e)}"
    
    # Test OSRM
    import httpx
    import os
    try:
        osrm_url = os.getenv("OSRM_URL", "http://osrm:5000")
        r = httpx.get(f"{osrm_url}/route/v1/driving/21.0,52.0;21.1,52.1", timeout=5)
        if r.status_code == 200:
            status["osrm"] = "ok"
        else:
            status["osrm"] = f"status_code: {r.status_code}"
    except Exception as e:
        status["osrm"] = f"error: {str(e)}"
    
    overall = "ok" if all(v == "ok" for v in status.values()) else "degraded"
    
    return {
        "status": overall,
        "components": status
    }
# Fragment do dodania w backend/app/admin_api.py

@router.post("/cleanup-orphaned-parcels")
def cleanup_orphaned_parcels(db: Session = Depends(get_db)):
    """
    Przywraca do pending paczki które:
    - Mają status 'accepted'
    - Ale trasa jest nieaktywna (is_active=False) lub usunięta
    
    Przypadki użycia:
    - Po testach, gdy trasy były kasowane
    - Po bugach w systemie
    - Okresowe maintenance
    """
    
    # Znajdź paczki accepted, których trasy są nieaktywne
    orphaned_sql = text("""
        SELECT DISTINCT p.id, p.status, m.route_id, r.is_active
        FROM parcels p
        JOIN route_parcel_matches m ON m.parcel_id = p.id
        LEFT JOIN routes r ON r.id = m.route_id
        WHERE p.status = 'accepted'
          AND m.status = 'accepted'
          AND (r.is_active = FALSE OR r.id IS NULL)
    """)
    
    orphaned = db.execute(orphaned_sql).mappings().all()
    
    restored_count = 0
    details = []
    
    for row in orphaned:
        parcel = db.get(Parcel, row["id"])
        if parcel and parcel.status == "accepted":
            parcel.status = "pending"
            restored_count += 1
            details.append({
                "parcel_id": row["id"],
                "old_route_id": row["route_id"],
                "route_active": row["is_active"],
            })
    
    db.commit()
    
    return {
        "restored_count": restored_count,
        "details": details,
        "message": f"Przywrócono {restored_count} osieroconych paczek do pending"
    }

@router.post("/auto-resolve-disputes")
def trigger_auto_resolve_disputes(
    days: int = 7,
    db: Session = Depends(get_db)
):
    """
    Ręczne wyzwolenie auto-resolve dla starych sporów.
    W produkcji: cronjob.
    """
    from .tasks import auto_resolve_disputes
    result = auto_resolve_disputes(db, days)
    return result

@router.get("/orphaned-parcels")
def list_orphaned_parcels(db: Session = Depends(get_db)):
    """
    Lista paczek accepted bez aktywnej trasy (tylko podgląd, bez zmian).
    """
    
    orphaned_sql = text("""
        SELECT 
            p.id AS parcel_id,
            p.status AS parcel_status,
            m.route_id,
            r.is_active AS route_active,
            r.id IS NULL AS route_deleted
        FROM parcels p
        JOIN route_parcel_matches m ON m.parcel_id = p.id
        LEFT JOIN routes r ON r.id = m.route_id
        WHERE p.status = 'accepted'
          AND m.status = 'accepted'
          AND (r.is_active = FALSE OR r.id IS NULL)
    """)
    
    orphaned = db.execute(orphaned_sql).mappings().all()
    
    return {
        "count": len(orphaned),
        "parcels": [dict(row) for row in orphaned]
    }
