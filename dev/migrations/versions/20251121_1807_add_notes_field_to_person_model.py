"""add_notes_field_to_person_model

Revision ID: c777bc065343
Revises: d27932f4e887
Create Date: 2025-11-21 18:07:40.185485

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c777bc065343'
down_revision: Union[str, Sequence[str], None] = 'd27932f4e887'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add notes column to Person model for wiki curation."""
    # Add notes column to people table
    op.add_column('people', sa.Column('notes', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove notes column from Person model."""
    # Drop notes column from people table
    op.drop_column('people', 'notes')
