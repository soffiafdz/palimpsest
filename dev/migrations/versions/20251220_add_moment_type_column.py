"""add_moment_type_column

Revision ID: a1b2c3d4e5f6
Revises: 9e7f2a2a244e
Create Date: 2025-12-20 22:30:00.000000

Adds a 'type' column to the moments table to distinguish between
actual moments (events that happened) and references (contextual links
to dates where the action happens on the entry date, not the referenced date).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '9e7f2a2a244e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add 'type' column to moments table.

    The type column distinguishes between:
    - 'moment': An event that actually happened on the referenced date (default)
    - 'reference': A contextual link where action happens on entry date

    All existing moments are set to 'moment' type (the default).
    """
    # Add type column with default value 'moment'
    # SQLite doesn't support adding NOT NULL columns without defaults,
    # so we add with a default first
    op.add_column(
        'moments',
        sa.Column(
            'type',
            sa.Enum('moment', 'reference', name='momenttype'),
            nullable=False,
            server_default='moment'
        )
    )

    # Create index for efficient filtering by type
    op.create_index(
        'ix_moments_type',
        'moments',
        ['type'],
        unique=False
    )


def downgrade() -> None:
    """
    Remove 'type' column from moments table.

    Warning: This will lose the distinction between moments and references.
    All moments will be treated as actual moments after downgrade.
    """
    # Drop the index first
    op.drop_index('ix_moments_type', table_name='moments')

    # Remove the type column
    op.drop_column('moments', 'type')
