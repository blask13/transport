"""add route history tracking

Revision ID: a1b2c3d4e5f6
Revises: 14d2dbf52b48
Create Date: 2026-01-06 12:00:00.000000

Historia zmian tras - do ETAPU 5.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '14d2dbf52b48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Dodaje tabelę route_history do śledzenia zmian."""
    
    # Tabela historii zmian tras
    op.execute("""
        CREATE TABLE IF NOT EXISTS route_history (
            id BIGSERIAL PRIMARY KEY,
            route_id BIGINT NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
            changed_by TEXT NOT NULL,
            change_type TEXT NOT NULL CHECK (change_type IN ('created','parcel_accepted','cancelled')),
            parcel_id BIGINT REFERENCES parcels(id) ON DELETE SET NULL,
            
            -- snapshot przed zmianą
            old_geom geometry(LineString, 4326),
            old_distance_m DOUBLE PRECISION,
            old_duration_s DOUBLE PRECISION,
            
            -- snapshot po zmianie
            new_geom geometry(LineString, 4326),
            new_distance_m DOUBLE PRECISION,
            new_duration_s DOUBLE PRECISION,
            
            -- delta (dla parcel_accepted)
            delta_distance_m DOUBLE PRECISION,
            delta_duration_s DOUBLE PRECISION,
            
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    
    # Indeks dla szybkiego lookup po route_id
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_route_history_route_id 
        ON route_history(route_id)
    """)
    
    # Indeks dla zapytań po czasie
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_route_history_created_at 
        ON route_history(created_at DESC)
    """)


def downgrade() -> None:
    """Usuwa tabelę route_history."""
    op.execute("DROP TABLE IF EXISTS route_history")