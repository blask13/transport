"""add parcel optional fields

Revision ID: 14d2dbf52b48
Revises: 4e3473d74d99
Create Date: 2026-01-04 15:01:36.338420
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "14d2dbf52b48"
down_revision: Union[str, Sequence[str], None] = "4e3473d74d99"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE parcels ADD COLUMN IF NOT EXISTS title TEXT")
    op.execute("ALTER TABLE parcels ADD COLUMN IF NOT EXISTS pickup_after TIMESTAMPTZ")
    op.execute("ALTER TABLE parcels ADD COLUMN IF NOT EXISTS pickup_before TIMESTAMPTZ")
    op.execute("ALTER TABLE parcels ADD COLUMN IF NOT EXISTS dropoff_after TIMESTAMPTZ")
    op.execute("ALTER TABLE parcels ADD COLUMN IF NOT EXISTS dropoff_before TIMESTAMPTZ")
    op.execute("ALTER TABLE parcels ADD COLUMN IF NOT EXISTS weight_kg DOUBLE PRECISION")
    op.execute("ALTER TABLE parcels ADD COLUMN IF NOT EXISTS size_class TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE parcels DROP COLUMN IF EXISTS size_class")
    op.execute("ALTER TABLE parcels DROP COLUMN IF EXISTS weight_kg")
    op.execute("ALTER TABLE parcels DROP COLUMN IF EXISTS dropoff_before")
    op.execute("ALTER TABLE parcels DROP COLUMN IF EXISTS dropoff_after")
    op.execute("ALTER TABLE parcels DROP COLUMN IF EXISTS pickup_before")
    op.execute("ALTER TABLE parcels DROP COLUMN IF EXISTS pickup_after")
    op.execute("ALTER TABLE parcels DROP COLUMN IF EXISTS title")

