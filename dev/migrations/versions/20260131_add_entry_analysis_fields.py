"""add_entry_analysis_fields

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-01-31 15:30:00.000000

Adds analysis fields to the entries table for Phase 14b-2:
- summary: Narrative summary from analysis YAML
- rating: Quality rating 1-5 (float for half-points)
- rating_justification: Explanation for the rating
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add analysis fields to entries table.

    These fields store narrative analysis data imported from metadata YAML files:
    - summary: Narrative summary of the entry
    - rating: Quality rating 1-5 (float allows half-points like 4.5)
    - rating_justification: Explanation for the rating
    """
    with op.batch_alter_table('entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('summary', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('rating', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('rating_justification', sa.Text(), nullable=True))
        batch_op.create_check_constraint(
            'ck_entry_rating_range',
            'rating IS NULL OR (rating >= 1 AND rating <= 5)'
        )


def downgrade() -> None:
    """
    Remove analysis fields from entries table.
    """
    with op.batch_alter_table('entries', schema=None) as batch_op:
        batch_op.drop_constraint('ck_entry_rating_range', type_='check')
        batch_op.drop_column('rating_justification')
        batch_op.drop_column('rating')
        batch_op.drop_column('summary')
