"""Add neighborhood column to locations table.

Adds an optional neighborhood/district field to Location entities,
allowing locations to be grouped by neighborhood within a city.

Revision ID: 20260222_neighborhood
Revises: 20260207_natural_keys
Create Date: 2026-02-22
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260222_neighborhood"
down_revision = "20260207_natural_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add neighborhood column to locations."""
    op.add_column(
        "locations",
        sa.Column("neighborhood", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    """Remove neighborhood column from locations."""
    op.drop_column("locations", "neighborhood")
