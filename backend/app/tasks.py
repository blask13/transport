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

def auto_resolve_disputes(db: Session, days: int = 7) -> dict:
    """
    Automatycznie rozwiązuje spory starsze niż {days} dni.
    Status: disputed → completed
    """
    from datetime import datetime, timedelta
    from .models import Dispute, Parcel
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Znajdź stare spory
    old_disputes = db.execute(
        select(Dispute)
        .where(Dispute.status == "open")
        .where(Dispute.created_at < cutoff)
    ).scalars().all()
    
    resolved_count = 0
    for dispute in old_disputes:
        parcel = db.get(Parcel, dispute.parcel_id)
        if parcel and parcel.status == "disputed":
            # Auto-resolve jako completed
            parcel.status = "completed"
            dispute.status = "resolved"
            dispute.resolved_at = datetime.utcnow()
            dispute.resolution = f"Auto-resolved after {days} days (no response from courier)"
            resolved_count += 1
    
    db.commit()
    
    return {
        "resolved_count": resolved_count,
        "cutoff_date": cutoff.isoformat()
    }