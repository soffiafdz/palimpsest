"""rename_aliases_to_person_aliases

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-01-31 15:45:00.000000

Renames the 'aliases' table to 'person_aliases' to match the model definition.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6g7h8i9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6g7h8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Rename aliases table to person_aliases.
    """
    op.rename_table('aliases', 'person_aliases')
    # Also recreate the index with proper name
    op.create_index('ix_person_aliases_alias', 'person_aliases', ['alias'])


def downgrade() -> None:
    """
    Rename person_aliases back to aliases.
    """
    op.drop_index('ix_person_aliases_alias', table_name='person_aliases')
    op.rename_table('person_aliases', 'aliases')
