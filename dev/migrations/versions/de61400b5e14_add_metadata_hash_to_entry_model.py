"""Add metadata_hash to Entry model

Revision ID: de61400b5e14
Revises: d4e5f6g7h8i9
Create Date: 2026-02-01 09:05:43.276852

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'de61400b5e14'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6g7h8i9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add metadata_hash column to entries table."""
    op.add_column('entries', sa.Column('metadata_hash', sa.String(length=64), nullable=True))


def downgrade() -> None:
    """Remove metadata_hash column from entries table."""
    op.drop_column('entries', 'metadata_hash')
