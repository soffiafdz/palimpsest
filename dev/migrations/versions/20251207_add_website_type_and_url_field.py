"""add_website_reference_type_and_url_field

Revision ID: b8e4f0c2a3d5
Revises: e8f92a3c4d51
Create Date: 2025-12-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8e4f0c2a3d5'
down_revision: Union[str, Sequence[str], None] = 'e8f92a3c4d51'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add 'website' type to ReferenceType enum and add url field to reference_sources table.

    Changes:
    1. Adds 'website' as a valid reference type
    2. Adds url column to reference_sources table (VARCHAR(500), nullable)
    """
    # Add url column to reference_sources table
    op.add_column(
        'reference_sources',
        sa.Column('url', sa.String(length=500), nullable=True)
    )

    # Note: For SQLite, we cannot easily modify an enum constraint.
    # The 'website' value will be added to the ReferenceType enum in the Python code.
    # SQLite's CHECK constraint based on the enum will automatically accept it
    # once the Python enum is updated (which has already been done).

    # For PostgreSQL, you would need:
    # op.execute("ALTER TYPE referencetype ADD VALUE 'website'")
    # But since this project uses SQLite, the enum is enforced at the application layer.


def downgrade() -> None:
    """
    Remove 'website' type and url field.

    Warning: This will remove URL data for all reference sources.
    """
    # Remove url column
    op.drop_column('reference_sources', 'url')

    # Note: For SQLite, we cannot remove enum values easily.
    # Any existing 'website' type references will cause constraint violations
    # if the Python enum is reverted.
    # Consider updating existing 'website' references to 'other' type before downgrade.
