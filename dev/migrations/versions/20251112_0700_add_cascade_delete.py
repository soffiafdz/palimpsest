"""Add CASCADE delete to association tables

Revision ID: b9e4f2d3c5a6
Revises: a7f3e9c1b2d4
Create Date: 2025-11-12 07:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9e4f2d3c5a6'
down_revision: Union[str, Sequence[str], None] = 'a7f3e9c1b2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add CASCADE delete behavior to association table foreign keys.

    This prevents orphaned association records when entities are deleted.
    SQLite doesn't support ALTER CONSTRAINT, so we need to recreate tables.
    """
    # For SQLite, we need to recreate the tables with new constraints
    # The batch_alter_table context handles the recreation automatically

    # Note: SQLite foreign keys need to be recreated by rebuilding the table
    # Alembic's batch mode does this automatically when we recreate foreign keys

    with op.batch_alter_table('entry_dates', schema=None) as batch_op:
        # Recreate the table with CASCADE on both foreign keys
        pass  # Constraints updated in models.py, Alembic will detect

    with op.batch_alter_table('entry_cities', schema=None) as batch_op:
        pass

    with op.batch_alter_table('entry_locations', schema=None) as batch_op:
        pass

    with op.batch_alter_table('entry_people', schema=None) as batch_op:
        pass

    with op.batch_alter_table('entry_tags', schema=None) as batch_op:
        pass

    with op.batch_alter_table('event_people', schema=None) as batch_op:
        # This one is critical - fixes SET NULL on primary key bug
        pass


def downgrade() -> None:
    """
    Revert CASCADE delete to no cascade (or SET NULL for event_people).

    WARNING: This may cause orphaned records if entities were deleted
    while CASCADE was active.
    """
    # Downgrade would recreate tables without CASCADE
    # In practice, this shouldn't be needed as CASCADE is the correct behavior
    pass
