"""Add theme_instances table and drop entry_themes.

Converts themes from simple M2M (entry_themes) to instance-based
pattern (theme_instances) with per-entry descriptions, following
the motif/motif_instances pattern.

Revision ID: 20260223_theme_instances
Revises: 20260222_neighborhood
Create Date: 2026-02-23
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260223_theme_instances"
down_revision = "20260222_neighborhood"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create theme_instances table and drop entry_themes."""
    op.create_table(
        "theme_instances",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("theme_id", sa.Integer(), nullable=False),
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["theme_id"], ["themes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["entry_id"], ["entries.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("description != ''", name="ck_theme_instance_non_empty_desc"),
        sa.UniqueConstraint("theme_id", "entry_id", name="uq_theme_instance_theme_entry"),
    )

    op.drop_table("entry_themes")


def downgrade() -> None:
    """Recreate entry_themes and drop theme_instances."""
    op.create_table(
        "entry_themes",
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("theme_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["entry_id"], ["entries.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["theme_id"], ["themes.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("entry_id", "theme_id"),
    )

    op.drop_table("theme_instances")
