"""rename_mentioneddate_to_moment

Revision ID: 9e7f2a2a244e
Revises: b8e4f0c2a3d5
Create Date: 2025-12-20 01:01:29.954469

This migration renames MentionedDate to Moment:
- Renames 'dates' table to 'moments'
- Renames association tables and their foreign key columns
- Creates new 'moment_events' M2M table

Data is preserved through table renames and column migrations.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e7f2a2a244e'
down_revision: Union[str, Sequence[str], None] = 'b8e4f0c2a3d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema: Rename MentionedDate to Moment.

    Steps:
    1. Rename main 'dates' table to 'moments'
    2. Rename and restructure association tables
    3. Create new 'moment_events' table
    """
    # Step 1: Rename main table
    op.rename_table('dates', 'moments')

    # Rename index (SQLite requires drop/create for index rename)
    op.drop_index('ix_dates_date', table_name='moments')
    op.create_index('ix_moments_date', 'moments', ['date'], unique=False)

    # Step 2: Rename association tables and restructure columns
    # For SQLite, we need to recreate tables to rename columns
    # Using batch_alter_table for SQLite compatibility

    # 2a. entry_dates -> entry_moments (rename date_id -> moment_id)
    with op.batch_alter_table('entry_dates', recreate='always') as batch_op:
        batch_op.alter_column('date_id', new_column_name='moment_id')
    op.rename_table('entry_dates', 'entry_moments')

    # 2b. people_dates -> moment_people (rename date_id -> moment_id)
    with op.batch_alter_table('people_dates', recreate='always') as batch_op:
        batch_op.alter_column('date_id', new_column_name='moment_id')
    op.rename_table('people_dates', 'moment_people')

    # 2c. location_dates -> moment_locations (rename date_id -> moment_id)
    with op.batch_alter_table('location_dates', recreate='always') as batch_op:
        batch_op.alter_column('date_id', new_column_name='moment_id')
    op.rename_table('location_dates', 'moment_locations')

    # Step 3: Create new moment_events table
    op.create_table('moment_events',
        sa.Column('moment_id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['moment_id'], ['moments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('moment_id', 'event_id')
    )


def downgrade() -> None:
    """
    Downgrade schema: Revert Moment back to MentionedDate.
    """
    # Step 1: Drop moment_events table (new table, no data to preserve from upgrade)
    op.drop_table('moment_events')

    # Step 2: Revert association table names and column names
    # 2a. moment_locations -> location_dates
    op.rename_table('moment_locations', 'location_dates')
    with op.batch_alter_table('location_dates', recreate='always') as batch_op:
        batch_op.alter_column('moment_id', new_column_name='date_id')

    # 2b. moment_people -> people_dates
    op.rename_table('moment_people', 'people_dates')
    with op.batch_alter_table('people_dates', recreate='always') as batch_op:
        batch_op.alter_column('moment_id', new_column_name='date_id')

    # 2c. entry_moments -> entry_dates
    op.rename_table('entry_moments', 'entry_dates')
    with op.batch_alter_table('entry_dates', recreate='always') as batch_op:
        batch_op.alter_column('moment_id', new_column_name='date_id')

    # Step 3: Rename main table back
    op.drop_index('ix_moments_date', table_name='moments')
    op.create_index('ix_dates_date', 'moments', ['date'], unique=False)
    op.rename_table('moments', 'dates')
