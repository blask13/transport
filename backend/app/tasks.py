# backend/app/tasks.py
"""
Background task do wygaszania starych propozycji.
W produkcji: użyj Celery/APScheduler.
W MVP: prosty endpoint który uruchamia cron lub admn ręcznie.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

from .models import RouteParcelMatch


def expire_old_proposals(
    db: Session,
    max_age_hours: int = 24,
) -> dict:
    """
    Wygasza propozycje starsze niż max_age_hours.
    
    Zwraca:
        {
            "expired_count": int,
            "cutoff_time": str
        }
    """
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    
    # Znajdź stare propozycje
    expired = db.execute(
        text("""
            UPDATE route_parcel_matches
            SET status = 'expired'
            WHERE status = 'proposed'
              AND created_at < :cutoff
            RETURNING id
        """),
        {"cutoff": cutoff}
    )
    
    count = len(expired.all())
    db.commit()
    
    return {
        "expired_count": count,
        "cutoff_time": cutoff.isoformat(),
    }


def cleanup_cancelled_parcel_matches(db: Session) -> dict:
    """
    Usuwa propozycje dla paczek które zostały anulowane.
    """
    result = db.execute(
        text("""
            UPDATE route_parcel_matches m
            SET status = 'rejected'
            FROM parcels p
            WHERE m.parcel_id = p.id
              AND p.status = 'cancelled'
              AND m.status = 'proposed'
            RETURNING m.id
        """)
    )
    
    count = len(result.all())
    db.commit()
    
    return {
        "cleaned_count": count
    }