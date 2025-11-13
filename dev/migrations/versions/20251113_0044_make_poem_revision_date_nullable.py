"""make_poem_revision_date_nullable

Revision ID: f060de8a49a9
Revises: b9e4f2d3c5a6
Create Date: 2025-11-13 00:44:50.051153

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f060de8a49a9'
down_revision: Union[str, Sequence[str], None] = 'b9e4f2d3c5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make poem_versions.revision_date nullable.

    This allows poems to be created without an explicit revision date,
    which will default to the entry date when parsed from YAML.
    """
    # SQLite requires batch mode for column alterations
    with op.batch_alter_table('poem_versions', schema=None) as batch_op:
        batch_op.alter_column('revision_date',
                              existing_type=sa.Date(),
                              nullable=True)


def downgrade() -> None:
    """Revert poem_versions.revision_date to NOT NULL.

    Note: This will fail if any NULL revision_dates exist in the database.
    """
    with op.batch_alter_table('poem_versions', schema=None) as batch_op:
        batch_op.alter_column('revision_date',
                              existing_type=sa.Date(),
                              nullable=False)
