"""
Synchronization Models
-----------------------

Models for tracking database synchronization and deletions across machines.

Models:
    - AssociationTombstone: Records of deleted many-to-many associations
    - SyncState: Synchronization state for conflict detection
    - EntitySnapshot: Point-in-time snapshots of entities

These models enable multi-machine synchronization and conflict resolution.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AssociationTombstone(Base):
    """
    Tombstone records for deleted many-to-many associations.

    Tracks when a relationship was removed (e.g., person removed from entry)
    to distinguish removal from "never existed" and enable sync propagation
    across multiple machines.

    This is critical for multi-machine synchronization: when a person is removed
    from an entry on Machine A, the tombstone ensures Machine B also removes the
    person instead of re-adding them during sync.

    Attributes:
        id: Primary key
        table_name: Association table name ('entry_people', 'entry_tags', etc.)
        left_id: Left side ID (usually entry_id)
        right_id: Right side ID (person_id, tag_id, etc.)
        removed_at: Timestamp when association was removed
        removed_by: Who/what removed it ('yaml2sql', 'wiki2sql', 'user@hostname')
        removal_reason: Optional reason ('corrected_tag', 'wrong_person', etc.)
        sync_source: Source of removal ('yaml', 'wiki', 'manual')
        expires_at: Tombstone expiry (NULL = permanent, else auto-cleanup date)

    Examples:
        # Person removed from entry
        AssociationTombstone(
            table_name='entry_people',
            left_id=123,  # entry.id
            right_id=45,  # person.id
            removed_by='yaml2sql',
            sync_source='yaml',
            removal_reason='corrected_name'
        )

        # Tag removed from entry (90-day TTL)
        AssociationTombstone(
            table_name='entry_tags',
            left_id=123,
            right_id=7,
            removed_by='user@laptop',
            sync_source='manual',
            expires_at=datetime.now() + timedelta(days=90)
        )
    """

    __tablename__ = "association_tombstones"
    __table_args__ = (
        # Prevent duplicate tombstones for same association
        UniqueConstraint("table_name", "left_id", "right_id", name="uq_tombstone_association"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    left_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    right_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    removed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    removed_by: Mapped[Optional[str]] = mapped_column(String(255))
    removal_reason: Mapped[Optional[str]] = mapped_column(Text)
    sync_source: Mapped[str] = mapped_column(String(50), nullable=False)

    # TTL for tombstone cleanup (NULL = permanent)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<Tombstone {self.table_name}("
            f"left={self.left_id}, right={self.right_id}) "
            f"removed={self.removed_at}>"
        )


class SyncState(Base):
    """
    Track synchronization state for entities.

    Enables conflict detection by comparing last sync timestamp with entity
    modification timestamp. If an entity was modified after its last sync,
    a conflict may exist (concurrent edits on different machines).

    Attributes:
        id: Primary key
        entity_type: Type of entity ('Entry', 'Person', 'Event', etc.)
        entity_id: ID of the entity
        last_synced_at: When entity was last synced from source
        sync_source: Source of sync ('yaml', 'wiki')
        sync_hash: Hash of source content at sync time
        modified_since_sync: Flag indicating entity changed after sync
        conflict_detected: Flag indicating conflict was detected
        conflict_resolved: Flag indicating conflict was resolved
        machine_id: Identifier of machine that performed sync (hostname or UUID)

    Examples:
        # Entry synced from YAML
        SyncState(
            entity_type='Entry',
            entity_id=123,
            last_synced_at=datetime.now(),
            sync_source='yaml',
            sync_hash='abc123...',
            machine_id='laptop'
        )

        # Conflict detected
        state.conflict_detected = True  # Hash changed between syncs
        state.conflict_resolved = False
    """

    __tablename__ = "sync_states"
    __table_args__ = (
        # One sync state per entity
        UniqueConstraint("entity_type", "entity_id", name="uq_sync_state_entity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    sync_source: Mapped[str] = mapped_column(String(50), nullable=False)
    sync_hash: Mapped[Optional[str]] = mapped_column(String(64))

    modified_since_sync: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    conflict_detected: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    conflict_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    machine_id: Mapped[Optional[str]] = mapped_column(String(255))

    def __repr__(self) -> str:
        return (
            f"<SyncState {self.entity_type}({self.entity_id}) "
            f"synced={self.last_synced_at} source={self.sync_source}>"
        )


class EntitySnapshot(Base):
    """
    Snapshot of entity state at a point in time.

    Provides baseline tracking for three-way merge, audit trail,
    and restoration functionality. Snapshots store the complete
    entity state as JSON for later comparison or recovery.

    Attributes:
        id: Primary key
        entity_type: Type of entity ('Entry', 'Person', etc.)
        entity_id: ID of the entity
        snapshot_data: Complete entity state as JSON
        created_at: When snapshot was created
        created_by: Who/what created snapshot ('yaml2sql', 'user@hostname')
        snapshot_type: Type of snapshot ('sync', 'backup', 'manual', 'pre_delete')
        retain_until: Retention expiry (NULL = permanent)
        parent_snapshot_id: Parent snapshot for diff chains (optional)

    Examples:
        # Automatic snapshot before deletion
        EntitySnapshot(
            entity_type='Entry',
            entity_id=123,
            snapshot_data={'date': '2024-11-01', 'people': ['Alice', 'Bob'], ...},
            created_by='entry_manager',
            snapshot_type='pre_delete',
            retain_until=None  # Keep forever
        )

        # Periodic backup snapshot (30-day retention)
        EntitySnapshot(
            entity_type='Entry',
            entity_id=123,
            snapshot_data={...},
            created_by='backup_job',
            snapshot_type='backup',
            retain_until=datetime.now() + timedelta(days=30)
        )
    """

    __tablename__ = "entity_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Store complete entity state as JSON
    snapshot_data: Mapped[Dict[str, Any]] = mapped_column(
        String,  # SQLAlchemy 2.0 JSON will be serialized as String
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    snapshot_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Retention policy
    retain_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # Diff chain (optional)
    parent_snapshot_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("entity_snapshots.id"), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<Snapshot {self.entity_type}({self.entity_id}) "
            f"type={self.snapshot_type} created={self.created_at}>"
        )
