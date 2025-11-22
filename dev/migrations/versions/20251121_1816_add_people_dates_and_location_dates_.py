"""add_people_dates_and_location_dates_associations

Revision ID: 24e94820d476
Revises: c777bc065343
Create Date: 2025-11-21 18:16:24.715476

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '24e94820d476'
down_revision: Union[str, Sequence[str], None] = 'c777bc065343'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add association tables for Person-Date and Location-Date relationships.

    These tables enable tracking which dates are mentioned in relation to
    specific people or locations.
    """
    # Create people_dates association table
    op.create_table(
        'people_dates',
        sa.Column('person_id', sa.Integer(), nullable=False),
        sa.Column('date_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['date_id'], ['dates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['person_id'], ['people.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('person_id', 'date_id')
    )

    # Create location_dates association table
    op.create_table(
        'location_dates',
        sa.Column('location_id', sa.Integer(), nullable=False),
        sa.Column('date_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['date_id'], ['dates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('location_id', 'date_id')
    )


def downgrade() -> None:
    """Remove Person-Date and Location-Date association tables."""
    op.drop_table('location_dates')
    op.drop_table('people_dates')
