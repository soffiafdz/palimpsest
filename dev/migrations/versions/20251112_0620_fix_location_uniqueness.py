"""Fix Location uniqueness constraint to be per-city

Revision ID: 20251112_0620_fix_location_uniqueness
Revises: 20251013_1722_add_alias_entry_tracking
Create Date: 2025-11-12 06:20:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7f3e9c1b2d4'  # Auto-generated hash
down_revision: Union[str, Sequence[str], None] = 'd0e202db42d1'  # Previous migration
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Fix Location uniqueness constraint.

    Change from globally unique name to composite unique (name, city_id).
    This allows the same location name in different cities (e.g., "Central Park" in NYC and SF).
    """
    # Drop the old unique index on name (serves as both index and uniqueness constraint in SQLite)
    with op.batch_alter_table('locations', schema=None) as batch_op:
        batch_op.drop_index('ix_locations_name')  # Drop unique index

        # Recreate the index without unique constraint
        batch_op.create_index('ix_locations_name', ['name'], unique=False)

        # Add composite unique constraint on (name, city_id)
        batch_op.create_unique_constraint('uq_location_name_city', ['name', 'city_id'])


def downgrade() -> None:
    """
    Revert to globally unique location names.

    WARNING: This may fail if there are duplicate location names across cities.
    """
    with op.batch_alter_table('locations', schema=None) as batch_op:
        # Drop composite unique constraint
        batch_op.drop_constraint('uq_location_name_city', type_='unique')

        # Drop the non-unique index
        batch_op.drop_index('ix_locations_name')

        # Recreate as unique index
        batch_op.create_index('ix_locations_name', ['name'], unique=True)

        # Add back the unique constraint
        batch_op.create_unique_constraint('uq_locations_name', ['name'])
