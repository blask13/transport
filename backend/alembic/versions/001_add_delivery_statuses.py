"""add delivery statuses and disputes

Revises: a1b2c3d4e5f6
Revises: 
Create Date: 2026-01-07 14:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = 'a1b2c3d4e5f6' 
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Rozszerz statusy paczek
    op.execute("""
        ALTER TABLE parcels 
        DROP CONSTRAINT IF EXISTS chk_parcels_status
    """)
    
    op.execute("""
        ALTER TABLE parcels 
        DROP CONSTRAINT IF EXISTS parcels_status_check
    """)
    
    op.execute("""
        ALTER TABLE parcels 
        ADD CONSTRAINT chk_parcels_status 
        CHECK (status IN (
            'pending',
            'offered',
            'accepted',
            'delivered',
            'disputed',
            'completed',
            'rejected',
            'cancelled'
        ))
    """)
    
    # Tabela sporów
    op.execute("""
        CREATE TABLE IF NOT EXISTS disputes (
            id BIGSERIAL PRIMARY KEY,
            parcel_id BIGINT NOT NULL REFERENCES parcels(id) ON DELETE CASCADE,
            reported_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
            courier_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
            reason TEXT NOT NULL,
            courier_response TEXT,
            resolution TEXT,
            status TEXT NOT NULL DEFAULT 'open' 
                CHECK (status IN ('open','resolved','escalated')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            resolved_at TIMESTAMPTZ
        )
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_disputes_parcel 
        ON disputes(parcel_id)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_disputes_status 
        ON disputes(status) WHERE status = 'open'
    """)

def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS disputes")
    
    op.execute("""
        ALTER TABLE parcels 
        DROP CONSTRAINT IF EXISTS chk_parcels_status
    """)
    
    op.execute("""
        ALTER TABLE parcels 
        ADD CONSTRAINT chk_parcels_status 
        CHECK (status IN (
            'pending','offered','accepted','rejected','cancelled'
        ))
    """)
