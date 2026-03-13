"""Add order field to manuscript scenes.

Per-chapter scene ordering, mirroring the per-part chapter numbering pattern.

Revision ID: 20260312_scene_order
Revises: 20260312_chapter_notes
Create Date: 2026-03-12
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260312_scene_order"
down_revision = "20260312_chapter_notes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add order column to manuscript_scenes."""
    op.add_column("manuscript_scenes", sa.Column("order", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove order column from manuscript_scenes."""
    op.drop_column("manuscript_scenes", "order")
