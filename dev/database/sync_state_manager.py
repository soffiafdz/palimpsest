#!/usr/bin/env python3
"""
sync_state_manager.py
--------------------
Manager for synchronization state tracking and conflict detection.

Tracks when entities were last synced from source files and detects conflicts
when the same entity is modified on multiple machines.

Usage:
    from dev.database.sync_state_manager import SyncStateManager

    mgr = SyncStateManager(session, logger)

    # Update sync state after syncing from YAML
    mgr.update_or_create(
        entity_type='Entry',
        entity_id=entry.id,
        last_synced_at=datetime.utcnow(),
        sync_source='yaml',
        sync_hash=compute_hash(yaml_content),
        machine_id='laptop'
    )

    # Check for conflicts before syncing
    conflict = mgr.check_conflict('Entry', entry.id, new_hash)
    if conflict:
        # Handle conflict
        pass

    # List all unresolved conflicts
    conflicts = mgr.list_conflicts()
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session

from dev.database.models import SyncState
from dev.core.logging_manager import PalimpsestLogger, safe_logger


class SyncStateManager:
    """
    Manage synchronization state for conflict detection.

    Tracks last sync timestamp and hash for each entity to detect when
    concurrent modifications have occurred on different machines.

    Attributes:
        session: SQLAlchemy session
        logger: Optional logger for debugging/info messages
    """

    def __init__(self, session: Session, logger: Optional[PalimpsestLogger] = None):
        """
        Initialize sync state manager.

        Args:
            session: SQLAlchemy session for database operations
            logger: Optional logger for recording operations
        """
        self.session = session
        self.logger = logger

    def update_or_create(
        self,
        entity_type: str,
        entity_id: int,
        last_synced_at: datetime,
        sync_source: str,
        sync_hash: Optional[str] = None,
        machine_id: Optional[str] = None,
    ) -> SyncState:
        """
        Update or create sync state for entity.

        If sync state exists, updates it. If not, creates new sync state.
        Resets conflict flags when updating.

        Args:
            entity_type: Type of entity ('Entry', 'Person', 'Event', etc.)
            entity_id: ID of the entity
            last_synced_at: When entity was synced
            sync_source: Source of sync ('yaml', 'wiki')
            sync_hash: Optional hash of source content (for conflict detection)
            machine_id: Optional machine identifier (hostname or UUID)

        Returns:
            Updated or created SyncState

        Examples:
            >>> # After syncing entry from YAML
            >>> state = mgr.update_or_create(
            ...     entity_type='Entry',
            ...     entity_id=123,
            ...     last_synced_at=datetime.now(timezone.utc),
            ...     sync_source='yaml',
            ...     sync_hash='abc123def456',
            ...     machine_id='laptop'
            ... )
        """
        sync_state = self.session.query(SyncState).filter_by(
            entity_type=entity_type,
            entity_id=entity_id,
        ).first()

        if sync_state:
            # Update existing
            sync_state.last_synced_at = last_synced_at
            sync_state.sync_source = sync_source
            sync_state.sync_hash = sync_hash
            sync_state.machine_id = machine_id
            sync_state.modified_since_sync = False  # Reset flag
            # Note: Don't reset conflict_detected - that's explicit

            safe_logger(self.logger).log_debug(
                f"Updated sync state: {entity_type} {entity_id}",
                {
                    "source": sync_source,
                    "hash": sync_hash[:8] if sync_hash else None,
                    "machine": machine_id
                }
            )
        else:
            # Create new
            sync_state = SyncState(
                entity_type=entity_type,
                entity_id=entity_id,
                last_synced_at=last_synced_at,
                sync_source=sync_source,
                sync_hash=sync_hash,
                machine_id=machine_id,
                modified_since_sync=False,
                conflict_detected=False,
                conflict_resolved=False,
            )
            self.session.add(sync_state)

            safe_logger(self.logger).log_debug(
                f"Created sync state: {entity_type} {entity_id}",
                {
                    "source": sync_source,
                    "hash": sync_hash[:8] if sync_hash else None,
                    "machine": machine_id
                }
            )

        self.session.flush()
        return sync_state

    def get(
        self,
        entity_type: str,
        entity_id: int,
    ) -> Optional[SyncState]:
        """
        Get sync state for entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of entity

        Returns:
            SyncState if exists, None otherwise

        Examples:
            >>> state = mgr.get('Entry', 123)
            >>> if state:
            ...     print(f"Last synced: {state.last_synced_at}")
            ...     print(f"Source: {state.sync_source}")
        """
        return self.session.query(SyncState).filter_by(
            entity_type=entity_type,
            entity_id=entity_id,
        ).first()

    def check_conflict(
        self,
        entity_type: str,
        entity_id: int,
        new_hash: str,
    ) -> bool:
        """
        Check if entity has conflict.

        Compares new hash with stored hash. If they differ, entity was
        modified since last sync (potential concurrent edit on another machine).

        Args:
            entity_type: Type of entity
            entity_id: ID of entity
            new_hash: Hash of current source content

        Returns:
            True if conflict detected (hash mismatch), False otherwise

        Examples:
            >>> # Before syncing, check for conflict
            >>> new_hash = compute_hash(yaml_content)
            >>> if mgr.check_conflict('Entry', 123, new_hash):
            ...     print("Warning: Entry was modified on another machine")
            ...     # Handle conflict
        """
        sync_state = self.get(entity_type, entity_id)

        if not sync_state:
            # No previous sync - no conflict possible
            return False

        if not sync_state.sync_hash:
            # No hash stored - can't detect conflict
            return False

        if sync_state.sync_hash != new_hash:
            # Hash changed - conflict detected
            sync_state.conflict_detected = True
            self.session.flush()

            safe_logger(self.logger).log_warning(
                f"Conflict detected: {entity_type} {entity_id}",
                {
                    "last_sync": sync_state.last_synced_at.isoformat(),
                    "machine": sync_state.machine_id,
                    "old_hash": sync_state.sync_hash[:8],
                    "new_hash": new_hash[:8],
                }
            )

            return True

        return False

    def mark_conflict_resolved(
        self,
        entity_type: str,
        entity_id: int,
    ) -> bool:
        """
        Mark conflict as resolved.

        Should be called after user manually resolves a conflict.

        Args:
            entity_type: Type of entity
            entity_id: ID of entity

        Returns:
            True if conflict was marked resolved, False if no sync state

        Examples:
            >>> # After user resolves conflict
            >>> mgr.mark_conflict_resolved('Entry', 123)
        """
        sync_state = self.get(entity_type, entity_id)

        if sync_state:
            sync_state.conflict_resolved = True
            self.session.flush()

            safe_logger(self.logger).log_info(
                f"Marked conflict as resolved: {entity_type} {entity_id}"
            )

            return True

        return False

    def reset_conflict(
        self,
        entity_type: str,
        entity_id: int,
    ) -> bool:
        """
        Reset conflict flags (for testing or manual intervention).

        Args:
            entity_type: Type of entity
            entity_id: ID of entity

        Returns:
            True if flags were reset, False if no sync state

        Examples:
            >>> # Reset conflict state
            >>> mgr.reset_conflict('Entry', 123)
        """
        sync_state = self.get(entity_type, entity_id)

        if sync_state:
            sync_state.conflict_detected = False
            sync_state.conflict_resolved = False
            self.session.flush()

            safe_logger(self.logger).log_debug(
                f"Reset conflict flags: {entity_type} {entity_id}"
            )

            return True

        return False

    def list_conflicts(
        self,
        resolved: bool = False,
    ) -> List[SyncState]:
        """
        List entities with conflicts.

        Args:
            resolved: If False (default), only unresolved conflicts.
                     If True, only resolved conflicts.

        Returns:
            List of SyncState objects with conflicts

        Examples:
            >>> # Get all unresolved conflicts
            >>> conflicts = mgr.list_conflicts()
            >>> for state in conflicts:
            ...     print(f"{state.entity_type} {state.entity_id}")
            ...     print(f"  Last synced: {state.last_synced_at}")
            ...     print(f"  Machine: {state.machine_id}")

            >>> # Get resolved conflicts
            >>> resolved = mgr.list_conflicts(resolved=True)
        """
        query = self.session.query(SyncState).filter(
            SyncState.conflict_detected == True  # noqa: E712
        )

        if resolved:
            query = query.filter(SyncState.conflict_resolved == True)  # noqa: E712
        else:
            query = query.filter(SyncState.conflict_resolved == False)  # noqa: E712

        return query.order_by(SyncState.last_synced_at.desc()).all()

    def delete(
        self,
        entity_type: str,
        entity_id: int,
    ) -> bool:
        """
        Delete sync state for entity.

        Should be called when entity is permanently deleted.

        Args:
            entity_type: Type of entity
            entity_id: ID of entity

        Returns:
            True if sync state was deleted, False if didn't exist

        Examples:
            >>> # After permanently deleting entry
            >>> mgr.delete('Entry', 123)
        """
        sync_state = self.get(entity_type, entity_id)

        if sync_state:
            self.session.delete(sync_state)
            self.session.flush()

            safe_logger(self.logger).log_debug(
                f"Deleted sync state: {entity_type} {entity_id}"
            )

            return True

        return False

    def get_statistics(self) -> dict:
        """
        Get sync state statistics.

        Returns:
            Dictionary with counts and statistics

        Examples:
            >>> stats = mgr.get_statistics()
            >>> print(f"Total entities tracked: {stats['total']}")
            >>> print(f"Conflicts (unresolved): {stats['conflicts_unresolved']}")
            >>> print(f"Conflicts (resolved): {stats['conflicts_resolved']}")
            >>> print(f"By entity type: {stats['by_entity_type']}")
        """
        from sqlalchemy import func

        # Total count
        total = self.session.query(SyncState).count()

        # Conflicts
        conflicts_unresolved = self.session.query(SyncState).filter(
            SyncState.conflict_detected == True,  # noqa: E712
            SyncState.conflict_resolved == False,  # noqa: E712
        ).count()

        conflicts_resolved = self.session.query(SyncState).filter(
            SyncState.conflict_detected == True,  # noqa: E712
            SyncState.conflict_resolved == True,  # noqa: E712
        ).count()

        # By entity type
        by_entity_type = {
            entity_type: count
            for entity_type, count in self.session.query(
                SyncState.entity_type,
                func.count(SyncState.id)
            ).group_by(SyncState.entity_type).all()
        }

        # By sync source
        by_source = {
            sync_source: count
            for sync_source, count in self.session.query(
                SyncState.sync_source,
                func.count(SyncState.id)
            ).group_by(SyncState.sync_source).all()
        }

        # By machine
        by_machine = {
            machine_id: count
            for machine_id, count in self.session.query(
                SyncState.machine_id,
                func.count(SyncState.id)
            ).group_by(SyncState.machine_id).all()
        }

        return {
            'total': total,
            'conflicts_unresolved': conflicts_unresolved,
            'conflicts_resolved': conflicts_resolved,
            'by_entity_type': by_entity_type,
            'by_source': by_source,
            'by_machine': by_machine,
        }
