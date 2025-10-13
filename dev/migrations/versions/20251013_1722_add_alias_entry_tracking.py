"""add alias entry tracking

Revision ID: d0e202db42d1
Revises:
Create Date: 2025-10-13 17:22:59.286885

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d0e202db42d1"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "entry_aliases",
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("alias_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["alias_id"], ["aliases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entry_id"], ["entries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("entry_id", "alias_id"),
    )

    # Create indexes for better query performance
    op.create_index("ix_alias_entries_alias_id", "entry_aliases", ["alias_id"])
    op.create_index("ix_alias_entries_entry_id", "entry_aliases", ["entry_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_alias_entries_entry_id", table_name="entry_aliases")
    op.drop_index("ix_alias_entries_alias_id", table_name="entry_aliases")
    op.drop_table("entry_aliases")
