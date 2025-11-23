"""add_tombstone_and_sync_tracking

Revision ID: e8f92a3c4d51
Revises: 24e94820d476
Create Date: 2025-11-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8f92a3c4d51'
down_revision: Union[str, Sequence[str], None] = '24e94820d476'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add tombstone and synchronization tracking infrastructure.

    Phase 1 of Strategy 3 (Tombstone Pattern) implementation for multi-machine
    synchronization. This migration adds:

    1. Soft delete support for Entry model
    2. AssociationTombstone table for tracking deleted associations
    3. SyncState table for conflict detection
    4. EntitySnapshot table for baseline tracking and recovery

    This enables reliable deletion propagation across machines and conflict
    detection for concurrent edits.
    """

    # ===== 1. Add soft delete fields to entries table =====
    with op.batch_alter_table('entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('deleted_by', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('deletion_reason', sa.Text(), nullable=True))

        # Add index on deleted_at for filtering queries
        batch_op.create_index('idx_entries_deleted_at', ['deleted_at'], unique=False)

    # ===== 2. Create association_tombstones table =====
    op.create_table(
        'association_tombstones',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('table_name', sa.String(length=100), nullable=False),
        sa.Column('left_id', sa.Integer(), nullable=False),
        sa.Column('right_id', sa.Integer(), nullable=False),
        sa.Column('removed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('removed_by', sa.String(length=255), nullable=True),
        sa.Column('removal_reason', sa.Text(), nullable=True),
        sa.Column('sync_source', sa.String(length=50), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('table_name', 'left_id', 'right_id', name='uq_tombstone_association')
    )

    # Indexes for association_tombstones
    with op.batch_alter_table('association_tombstones', schema=None) as batch_op:
        batch_op.create_index('idx_tombstone_table', ['table_name'], unique=False)
        batch_op.create_index('idx_tombstone_left_id', ['left_id'], unique=False)
        batch_op.create_index('idx_tombstone_right_id', ['right_id'], unique=False)
        batch_op.create_index('idx_tombstone_removed_at', ['removed_at'], unique=False)
        batch_op.create_index('idx_tombstone_expires', ['expires_at'], unique=False)

    # ===== 3. Create sync_states table =====
    op.create_table(
        'sync_states',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('entity_type', sa.String(length=100), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sync_source', sa.String(length=50), nullable=False),
        sa.Column('sync_hash', sa.String(length=64), nullable=True),
        sa.Column('modified_since_sync', sa.Boolean(), nullable=False),
        sa.Column('conflict_detected', sa.Boolean(), nullable=False),
        sa.Column('conflict_resolved', sa.Boolean(), nullable=False),
        sa.Column('machine_id', sa.String(length=255), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entity_type', 'entity_id', name='uq_sync_state_entity')
    )

    # Indexes for sync_states
    with op.batch_alter_table('sync_states', schema=None) as batch_op:
        batch_op.create_index('idx_sync_state_entity_type', ['entity_type'], unique=False)
        batch_op.create_index('idx_sync_state_entity_id', ['entity_id'], unique=False)
        batch_op.create_index('idx_sync_state_conflicts', ['conflict_detected'], unique=False)

    # ===== 4. Create entity_snapshots table =====
    op.create_table(
        'entity_snapshots',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('entity_type', sa.String(length=100), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('snapshot_data', sa.String(), nullable=False),  # JSON as String
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=False),
        sa.Column('snapshot_type', sa.String(length=50), nullable=False),
        sa.Column('retain_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('parent_snapshot_id', sa.Integer(), nullable=True),

        sa.ForeignKeyConstraint(['parent_snapshot_id'], ['entity_snapshots.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for entity_snapshots
    with op.batch_alter_table('entity_snapshots', schema=None) as batch_op:
        batch_op.create_index('idx_snapshot_entity_type', ['entity_type'], unique=False)
        batch_op.create_index('idx_snapshot_entity_id', ['entity_id'], unique=False)
        batch_op.create_index('idx_snapshot_created_at', ['created_at'], unique=False)
        batch_op.create_index('idx_snapshot_type', ['snapshot_type'], unique=False)
        batch_op.create_index('idx_snapshot_retention', ['retain_until'], unique=False)


def downgrade() -> None:
    """
    Remove tombstone and synchronization tracking infrastructure.

    WARNING: This will remove all tombstone and sync state data.
    Downgrading will:
    - Remove all tombstone records (deletion history lost)
    - Remove all sync state (conflict detection disabled)
    - Remove all entity snapshots (recovery data lost)
    - Remove soft delete fields from entries (deletion timestamps lost)

    Only downgrade if you are certain you want to remove this infrastructure.
    """

    # Drop tables in reverse order
    op.drop_table('entity_snapshots')
    op.drop_table('sync_states')
    op.drop_table('association_tombstones')

    # Remove soft delete fields from entries
    with op.batch_alter_table('entries', schema=None) as batch_op:
        batch_op.drop_index('idx_entries_deleted_at')
        batch_op.drop_column('deletion_reason')
        batch_op.drop_column('deleted_by')
        batch_op.drop_column('deleted_at')
