"""Add notes field to chapters.

Chapter notes for author's internal annotations (planning, reminders, etc.).

Revision ID: 20260312_chapter_notes
Revises: 20260308_chapter_date
Create Date: 2026-03-12
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260312_chapter_notes"
down_revision = "20260308_chapter_date"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add notes column to chapters."""
    op.add_column("chapters", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove notes column from chapters."""
    op.drop_column("chapters", "notes")
