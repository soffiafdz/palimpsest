#!/usr/bin/env python3
"""
tombstone_manager.py
-------------------
Manager for association tombstones - tracks deleted many-to-many relationships.

Tombstones enable reliable deletion propagation across multiple machines by
recording when an association was removed (e.g., person removed from entry).
This prevents re-adding deleted associations during synchronization.

Usage:
    from dev.database.tombstone_manager import TombstoneManager

    mgr = TombstoneManager(session, logger)

    # Create tombstone when removing association
    mgr.create(
        table_name='entry_people',
        left_id=entry.id,
        right_id=person.id,
        removed_by='yaml2sql',
        sync_source='yaml'
    )

    # Check if association was previously removed
    if mgr.exists('entry_people', entry.id, person.id):
        # Skip re-adding
        pass

    # Remove tombstone when association re-added
    mgr.remove_tombstone('entry_people', entry.id, person.id)

    # Cleanup expired tombstones
    count = mgr.cleanup_expired()
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, List
from sqlalchemy.orm import Session

from dev.database.models import AssociationTombstone
from dev.core.logging_manager import PalimpsestLogger


class TombstoneManager:
    """
    Manage association tombstones for deleted many-to-many relationships.

    Provides CRUD operations for tombstones and utilities for cleanup
    and querying. Tombstones are idempotent - creating duplicate tombstones
    returns the existing record.

    Attributes:
        session: SQLAlchemy session
        logger: Optional logger for debugging/info messages
    """

    def __init__(self, session: Session, logger: Optional[PalimpsestLogger] = None):
        """
        Initialize tombstone manager.

        Args:
            session: SQLAlchemy session for database operations
            logger: Optional logger for recording operations
        """
        self.session = session
        self.logger = logger

    def create(
        self,
        table_name: str,
        left_id: int,
        right_id: int,
        removed_by: str,
        sync_source: str,
        reason: Optional[str] = None,
        ttl_days: Optional[int] = 90,
    ) -> AssociationTombstone:
        """
        Create association tombstone.

        Idempotent - if tombstone already exists for this association,
        returns the existing tombstone instead of creating a duplicate.

        Args:
            table_name: Association table name ('entry_people', 'entry_tags', etc.)
            left_id: Left side ID (usually entry_id)
            right_id: Right side ID (person_id, tag_id, etc.)
            removed_by: Who/what removed it ('yaml2sql', 'wiki2sql', 'user@hostname')
            sync_source: Source of removal ('yaml', 'wiki', 'manual')
            reason: Optional reason for removal ('corrected_tag', 'wrong_person', etc.)
            ttl_days: Days until tombstone expires (None = permanent, default 90)

        Returns:
            Created or existing tombstone

        Examples:
            >>> # Person removed from entry
            >>> tombstone = mgr.create(
            ...     table_name='entry_people',
            ...     left_id=123,
            ...     right_id=45,
            ...     removed_by='yaml2sql',
            ...     sync_source='yaml',
            ...     reason='corrected_person_name'
            ... )

            >>> # Tag removed with custom TTL
            >>> tombstone = mgr.create(
            ...     table_name='entry_tags',
            ...     left_id=123,
            ...     right_id=7,
            ...     removed_by='user@laptop',
            ...     sync_source='manual',
            ...     ttl_days=30
            ... )
        """
        # Check for existing tombstone (idempotency)
        existing = self.session.query(AssociationTombstone).filter_by(
            table_name=table_name,
            left_id=left_id,
            right_id=right_id,
        ).first()

        if existing:
            # Already exists - return existing (idempotent)
            if self.logger:
                self.logger.log_debug(
                    f"Tombstone already exists: {table_name}({left_id}, {right_id})",
                    {"existing_id": existing.id}
                )
            return existing

        # Create new tombstone
        tombstone = AssociationTombstone(
            table_name=table_name,
            left_id=left_id,
            right_id=right_id,
            removed_by=removed_by,
            removal_reason=reason,
            sync_source=sync_source,
            removed_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=ttl_days) if ttl_days else None,
        )

        self.session.add(tombstone)
        self.session.flush()  # Get ID without committing

        if self.logger:
            self.logger.log_debug(
                f"Created tombstone: {table_name}({left_id}, {right_id})",
                {
                    "id": tombstone.id,
                    "removed_by": removed_by,
                    "source": sync_source,
                    "ttl_days": ttl_days
                }
            )

        return tombstone

    def exists(
        self,
        table_name: str,
        left_id: int,
        right_id: int,
    ) -> bool:
        """
        Check if tombstone exists for association.

        Args:
            table_name: Association table name
            left_id: Left side ID
            right_id: Right side ID

        Returns:
            True if tombstone exists, False otherwise

        Examples:
            >>> if mgr.exists('entry_people', entry.id, person.id):
            ...     print("This person was previously removed")
        """
        count = self.session.query(AssociationTombstone).filter_by(
            table_name=table_name,
            left_id=left_id,
            right_id=right_id,
        ).count()

        return count > 0

    def get(
        self,
        table_name: str,
        left_id: int,
        right_id: int,
    ) -> Optional[AssociationTombstone]:
        """
        Get tombstone for specific association.

        Args:
            table_name: Association table name
            left_id: Left side ID
            right_id: Right side ID

        Returns:
            Tombstone if exists, None otherwise

        Examples:
            >>> tombstone = mgr.get('entry_people', 123, 45)
            >>> if tombstone:
            ...     print(f"Removed at: {tombstone.removed_at}")
            ...     print(f"Removed by: {tombstone.removed_by}")
        """
        return self.session.query(AssociationTombstone).filter_by(
            table_name=table_name,
            left_id=left_id,
            right_id=right_id,
        ).first()

    def get_tombstones_for_entity(
        self,
        table_name: str,
        left_id: int,
    ) -> List[AssociationTombstone]:
        """
        Get all tombstones for an entity.

        Useful for viewing all associations that were removed from an entry.

        Args:
            table_name: Association table name
            left_id: Left side ID (usually entry_id)

        Returns:
            List of tombstones for this entity

        Examples:
            >>> # Get all people removed from entry 123
            >>> tombstones = mgr.get_tombstones_for_entity('entry_people', 123)
            >>> for t in tombstones:
            ...     print(f"Person ID {t.right_id} removed at {t.removed_at}")
        """
        return self.session.query(AssociationTombstone).filter_by(
            table_name=table_name,
            left_id=left_id,
        ).all()

    def remove_tombstone(
        self,
        table_name: str,
        left_id: int,
        right_id: int,
    ) -> bool:
        """
        Remove tombstone (when association re-added).

        When an association is re-added after being removed, the tombstone
        should be deleted to allow the association to exist again.

        Args:
            table_name: Association table name
            left_id: Left side ID
            right_id: Right side ID

        Returns:
            True if tombstone was removed, False if didn't exist

        Examples:
            >>> # Person re-added to entry - remove tombstone
            >>> removed = mgr.remove_tombstone('entry_people', 123, 45)
            >>> if removed:
            ...     print("Tombstone removed - association can be re-added")
        """
        tombstone = self.session.query(AssociationTombstone).filter_by(
            table_name=table_name,
            left_id=left_id,
            right_id=right_id,
        ).first()

        if tombstone:
            self.session.delete(tombstone)
            self.session.flush()

            if self.logger:
                self.logger.log_debug(
                    f"Removed tombstone: {table_name}({left_id}, {right_id})",
                    {"id": tombstone.id}
                )
            return True

        return False

    def cleanup_expired(self, dry_run: bool = False) -> int:
        """
        Remove expired tombstones.

        Tombstones with a non-NULL expires_at timestamp that is in the past
        are permanently deleted. This prevents the tombstone table from
        growing indefinitely.

        Args:
            dry_run: If True, only count expired tombstones without deleting

        Returns:
            Number of tombstones cleaned up (or would be cleaned up if dry_run)

        Examples:
            >>> # Preview how many would be deleted
            >>> count = mgr.cleanup_expired(dry_run=True)
            >>> print(f"Would delete {count} expired tombstones")

            >>> # Actually delete
            >>> count = mgr.cleanup_expired()
            >>> print(f"Deleted {count} expired tombstones")
        """
        query = self.session.query(AssociationTombstone).filter(
            AssociationTombstone.expires_at.isnot(None),
            AssociationTombstone.expires_at < datetime.now(timezone.utc),
        )

        if dry_run:
            count = query.count()
            if self.logger:
                self.logger.log_info(f"Would clean up {count} expired tombstones (dry run)")
            return count

        # Get IDs before deleting for logging
        tombstones = query.all()
        count = len(tombstones)

        if count > 0:
            # Delete expired tombstones
            query.delete(synchronize_session=False)
            self.session.flush()

            if self.logger:
                self.logger.log_info(
                    f"Cleaned up {count} expired tombstones",
                    {"count": count}
                )

        return count

    def list_all(
        self,
        table_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[AssociationTombstone]:
        """
        List tombstones with optional filtering.

        Args:
            table_name: Optional filter by table name
            limit: Maximum number to return (default 100)

        Returns:
            List of tombstones ordered by removal time (newest first)

        Examples:
            >>> # List all recent tombstones
            >>> tombstones = mgr.list_all(limit=50)

            >>> # List only entry_people tombstones
            >>> tombstones = mgr.list_all(table_name='entry_people')
        """
        query = self.session.query(AssociationTombstone)

        if table_name:
            query = query.filter_by(table_name=table_name)

        query = query.order_by(AssociationTombstone.removed_at.desc())
        query = query.limit(limit)

        return query.all()

    def get_statistics(self) -> dict:
        """
        Get tombstone statistics.

        Returns:
            Dictionary with counts by table name, source, and totals

        Examples:
            >>> stats = mgr.get_statistics()
            >>> print(f"Total tombstones: {stats['total']}")
            >>> print(f"By table: {stats['by_table']}")
            >>> print(f"By source: {stats['by_source']}")
        """
        from sqlalchemy import func

        # Total count
        total = self.session.query(AssociationTombstone).count()

        # Count by table
        by_table = dict(
            self.session.query(
                AssociationTombstone.table_name,
                func.count(AssociationTombstone.id)
            ).group_by(AssociationTombstone.table_name).all()
        )

        # Count by sync source
        by_source = dict(
            self.session.query(
                AssociationTombstone.sync_source,
                func.count(AssociationTombstone.id)
            ).group_by(AssociationTombstone.sync_source).all()
        )

        # Expired count
        expired_count = self.session.query(AssociationTombstone).filter(
            AssociationTombstone.expires_at.isnot(None),
            AssociationTombstone.expires_at < datetime.now(timezone.utc),
        ).count()

        return {
            'total': total,
            'by_table': by_table,
            'by_source': by_source,
            'expired': expired_count,
        }
