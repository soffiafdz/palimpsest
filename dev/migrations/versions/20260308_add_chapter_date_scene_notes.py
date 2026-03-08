"""Add date field to chapters.

Chapter date is an optional temporal anchor for when the chapter is set.

Revision ID: 20260308_chapter_date
Revises: 20260308_scene_characters
Create Date: 2026-03-08
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260308_chapter_date"
down_revision = "20260308_scene_characters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add date column to chapters."""
    op.add_column("chapters", sa.Column("date", sa.Date(), nullable=True))


def downgrade() -> None:
    """Remove date column from chapters."""
    op.drop_column("chapters", "date")
