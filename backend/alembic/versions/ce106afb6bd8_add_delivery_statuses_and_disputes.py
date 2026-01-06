"""add delivery statuses and disputes

Revision ID: ce106afb6bd8
Revises: eaf94ce58605
Create Date: 2026-01-06 19:54:57.850797

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ce106afb6bd8'
down_revision: Union[str, Sequence[str], None] = 'eaf94ce58605'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rozszerz statusy paczek
    op.execute("""
        ALTER TABLE parcels 
        DROP CONSTRAINT IF EXISTS chk_parcels_status
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