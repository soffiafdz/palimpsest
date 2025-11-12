#!/usr/bin/env python3
"""
manuscript_manager.py
--------------------
Manages manuscript-related entities for journal-to-manuscript adaptation tracking.

Handles ManuscriptEntry, ManuscriptPerson, ManuscriptEvent, Arc, and Theme entities.
These entities track which journal content is selected for manuscript inclusion and
how it's adapted (status, character mappings, story arcs, thematic elements).

Key Features:
    - ManuscriptEntry: 1-1 with Entry, tracks inclusion status and editing state
    - ManuscriptPerson: 1-1 with Person, maps real people to fictional characters
    - ManuscriptEvent: 1-1 with Event, tracks events in story arcs
    - Arc: Story arc grouping for manuscript events
    - Theme: Thematic elements across manuscript entries
    - Soft delete support for Person, Event, Arc, Theme
    - Status tracking with ManuscriptStatus enum

Usage:
    ms_mgr = ManuscriptManager(session, logger)

    # Mark entry for manuscript
    ms_entry = ms_mgr.create_or_update_entry(entry, {
        "status": "source",
        "edited": True,
        "themes": ["identity", "loss"]
    })

    # Map person to character
    ms_person = ms_mgr.create_or_update_person(person, {
        "character": "Alexandra"
    })

    # Add event to arc
    ms_event = ms_mgr.create_or_update_event(event, {
        "arc": "paris_trip",
        "notes": "Climactic scene"
    })

    # Get ready entries
    ready = ms_mgr.get_ready_entries()  # edited=True, status.is_content=True
"""
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone

from dev.core.validators import DataValidator
from dev.core.exceptions import ValidationError, DatabaseError
from dev.database.decorators import (
    handle_db_errors,
    log_database_operation,
)
from dev.database.models import Entry, Person, Event
from dev.database.models_manuscript import (
    ManuscriptEntry,
    ManuscriptPerson,
    ManuscriptEvent,
    Arc,
    Theme,
    ManuscriptStatus,
)
from dev.database.relationship_manager import RelationshipManager
from .base_manager import BaseManager


class ManuscriptManager(BaseManager):
    """
    Manages all manuscript-related entities.

    Handles the complete manuscript tracking system including entry selection,
    character mapping, story arcs, and thematic analysis.
    """

    # =========================================================================
    # MANUSCRIPT ENTRY OPERATIONS
    # =========================================================================

    @handle_db_errors
    @log_database_operation("create_or_update_manuscript_entry")
    def create_or_update_entry(
        self, entry: Entry, manuscript_data: Dict[str, Any]
    ) -> Optional[ManuscriptEntry]:
        """
        Create or update manuscript metadata for an entry.

        Args:
            entry: Entry object to attach manuscript data to
            manuscript_data: Dictionary with optional keys:
                - status: ManuscriptStatus enum or string
                - edited: Boolean editing state
                - notes: Text notes
                - themes: List of theme names

        Returns:
            ManuscriptEntry object, or None if deleted

        Notes:
            - Status accepts both enum and string (flexible matching)
            - Themes are replaced (not incremental)
        """
        if entry.id is None:
            raise ValueError("Entry must be persisted before manuscript operations")

        # Normalize status (flexible matching)
        status = None
        if "status" in manuscript_data:
            status_val = manuscript_data["status"]
            if isinstance(status_val, ManuscriptStatus):
                status = status_val
            elif isinstance(status_val, str):
                # Try enum name first, then value
                status_val_upper = status_val.upper()
                try:
                    status = ManuscriptStatus[status_val_upper]
                except KeyError:
                    # Try by value (case-insensitive)
                    status_val_lower = status_val.lower()
                    for ms in ManuscriptStatus:
                        if ms.value == status_val_lower:
                            status = ms
                            break

        # Prepare child data
        child_data = {}
        if status:
            child_data["status"] = status
        if "edited" in manuscript_data:
            child_data["edited"] = DataValidator.normalize_bool(
                manuscript_data["edited"]
            )
        if "notes" in manuscript_data:
            child_data["notes"] = DataValidator.normalize_string(
                manuscript_data["notes"]
            )

        # Create or update ManuscriptEntry (entity-specific logic)
        # Query database directly to avoid lazy loading issues
        ms_entry = self.session.query(ManuscriptEntry).filter_by(entry_id=entry.id).first()

        if ms_entry:
            # Existing manuscript entry
            if manuscript_data.get("delete", False):
                self.session.delete(ms_entry)
                self.session.flush()
                return None
            # Update existing
            if child_data:
                for key, value in child_data.items():
                    setattr(ms_entry, key, value)
                self.session.flush()
        else:
            # Create new manuscript entry
            if not manuscript_data.get("delete", False):
                child_data["entry_id"] = entry.id
                ms_entry = ManuscriptEntry(**child_data)
                self.session.add(ms_entry)
                self.session.flush()

        if ms_entry and "themes" in manuscript_data:
            self._update_themes(ms_entry, manuscript_data["themes"])

        return ms_entry

    @handle_db_errors
    @log_database_operation("delete_manuscript_entry")
    def delete_entry(self, entry: Entry) -> None:
        """
        Delete manuscript metadata for an entry.

        Args:
            entry: Entry whose manuscript data to delete
        """
        if entry.manuscript:
            self.session.delete(entry.manuscript)
            self.session.flush()

    def _update_themes(
        self, manuscript_entry: ManuscriptEntry, themes_list: List[str]
    ) -> None:
        """
        Update themes for a manuscript entry (replacement mode).

        Args:
            manuscript_entry: ManuscriptEntry to update
            themes_list: List of theme names
        """
        # Normalize theme names
        normalized_themes = [
            DataValidator.normalize_string(t) for t in themes_list
        ]
        normalized_themes = [t for t in normalized_themes if t]  # Filter empty

        # Get or create Theme objects
        theme_objs = []
        for theme_name in normalized_themes:
            theme = self._get_or_create(Theme, {"theme": theme_name})
            theme_objs.append(theme)

        # Replace all themes (entity-specific logic)
        # Clear existing themes
        manuscript_entry.themes.clear()
        # Add new themes
        for theme in theme_objs:
            if theme not in manuscript_entry.themes:
                manuscript_entry.themes.append(theme)
        self.session.flush()

    # =========================================================================
    # MANUSCRIPT PERSON OPERATIONS
    # =========================================================================

    @handle_db_errors
    @log_database_operation("create_or_update_manuscript_person")
    def create_or_update_person(
        self, person: Person, manuscript_data: Dict[str, Any]
    ) -> Optional[ManuscriptPerson]:
        """
        Create or update manuscript metadata for a person (character mapping).

        Args:
            person: Person object to map to character
            manuscript_data: Dictionary with optional keys:
                - character: Character name (required for creation)

        Returns:
            ManuscriptPerson object, or None if deleted

        Raises:
            ValidationError: If character is missing or empty
        """
        if person.id is None:
            raise ValueError("Person must be persisted before manuscript operations")

        # Validate character field
        character = DataValidator.normalize_string(manuscript_data.get("character"))
        if not character:
            raise ValidationError("Character name is required for manuscript person")

        # Prepare child data
        child_data = {"character": character}

        # Create or update ManuscriptPerson (entity-specific logic)
        # Query database directly to avoid lazy loading issues
        ms_person = self.session.query(ManuscriptPerson).filter_by(person_id=person.id).first()

        if ms_person:
            # Existing manuscript person
            if manuscript_data.get("delete", False):
                self.session.delete(ms_person)
                self.session.flush()
                return None
            # Update existing
            if child_data:
                for key, value in child_data.items():
                    setattr(ms_person, key, value)
                self.session.flush()
        else:
            # Create new manuscript person
            if not manuscript_data.get("delete", False):
                child_data["person_id"] = person.id
                ms_person = ManuscriptPerson(**child_data)
                self.session.add(ms_person)
                self.session.flush()

        return ms_person

    @handle_db_errors
    @log_database_operation("delete_manuscript_person")
    def delete_person(
        self,
        person: Person,
        deleted_by: Optional[str] = None,
        reason: Optional[str] = None,
        hard_delete: bool = False,
    ) -> None:
        """
        Delete manuscript metadata for a person (soft delete by default).

        Args:
            person: Person whose manuscript data to delete
            deleted_by: Who deleted it
            reason: Deletion reason
            hard_delete: If True, permanently delete
        """
        # Query database directly to avoid lazy loading issues
        ms_person = self.session.query(ManuscriptPerson).filter_by(person_id=person.id).first()
        if not ms_person:
            return

        if hard_delete:
            self.session.delete(ms_person)
        else:
            ms_person.deleted_at = datetime.now(timezone.utc)
            ms_person.deleted_by = deleted_by
            ms_person.deletion_reason = reason

        self.session.flush()

    @handle_db_errors
    @log_database_operation("restore_manuscript_person")
    def restore_person(self, person: Person) -> ManuscriptPerson:
        """
        Restore soft-deleted manuscript person.

        Args:
            person: Person whose manuscript data to restore

        Returns:
            Restored ManuscriptPerson

        Raises:
            DatabaseError: If not deleted or doesn't exist
        """
        # Query database directly to avoid lazy loading issues
        ms_person = self.session.query(ManuscriptPerson).filter_by(person_id=person.id).first()
        if not ms_person:
            raise DatabaseError(f"No manuscript data for person: {person.display_name}")

        if not ms_person.deleted_at:
            raise DatabaseError(
                f"Manuscript person not deleted: {person.display_name}"
            )

        ms_person.deleted_at = None
        ms_person.deleted_by = None
        ms_person.deletion_reason = None

        self.session.flush()

        return ms_person

    # =========================================================================
    # MANUSCRIPT EVENT OPERATIONS
    # =========================================================================

    @handle_db_errors
    @log_database_operation("create_or_update_manuscript_event")
    def create_or_update_event(
        self, event: Event, manuscript_data: Dict[str, Any]
    ) -> Optional[ManuscriptEvent]:
        """
        Create or update manuscript metadata for an event.

        Args:
            event: Event object
            manuscript_data: Dictionary with optional keys:
                - notes: Text notes
                - arc: Arc name (auto-creates arc)

        Returns:
            ManuscriptEvent object, or None if deleted
        """
        if event.id is None:
            raise ValueError("Event must be persisted before manuscript operations")

        # Prepare child data
        child_data = {}
        if "notes" in manuscript_data:
            child_data["notes"] = DataValidator.normalize_string(
                manuscript_data["notes"]
            )

        # Create or update ManuscriptEvent (entity-specific logic)
        # Query database directly to avoid lazy loading issues
        ms_event = self.session.query(ManuscriptEvent).filter_by(event_id=event.id).first()

        if ms_event:
            # Existing manuscript event
            if manuscript_data.get("delete", False):
                self.session.delete(ms_event)
                self.session.flush()
                return None
            # Update existing
            if child_data:
                for key, value in child_data.items():
                    setattr(ms_event, key, value)
                self.session.flush()
        else:
            # Create new manuscript event
            if not manuscript_data.get("delete", False):
                child_data["event_id"] = event.id
                ms_event = ManuscriptEvent(**child_data)
                self.session.add(ms_event)
                self.session.flush()

        # Handle arc assignment
        if ms_event and "arc" in manuscript_data:
            arc_name = DataValidator.normalize_string(manuscript_data["arc"])
            if arc_name:
                arc = self._get_or_create(Arc, {"arc": arc_name})
                ms_event.arc = arc
                self.session.flush()

        return ms_event

    @handle_db_errors
    @log_database_operation("delete_manuscript_event")
    def delete_event(
        self,
        event: Event,
        deleted_by: Optional[str] = None,
        reason: Optional[str] = None,
        hard_delete: bool = False,
    ) -> None:
        """
        Delete manuscript metadata for an event (soft delete by default).

        Args:
            event: Event whose manuscript data to delete
            deleted_by: Who deleted it
            reason: Deletion reason
            hard_delete: If True, permanently delete
        """
        # Query database directly to avoid lazy loading issues
        ms_event = self.session.query(ManuscriptEvent).filter_by(event_id=event.id).first()
        if not ms_event:
            return

        if hard_delete:
            self.session.delete(ms_event)
        else:
            ms_event.deleted_at = datetime.now(timezone.utc)
            ms_event.deleted_by = deleted_by
            ms_event.deletion_reason = reason

        self.session.flush()

    @handle_db_errors
    @log_database_operation("restore_manuscript_event")
    def restore_event(self, event: Event) -> ManuscriptEvent:
        """
        Restore soft-deleted manuscript event.

        Args:
            event: Event whose manuscript data to restore

        Returns:
            Restored ManuscriptEvent

        Raises:
            DatabaseError: If not deleted or doesn't exist
        """
        # Query database directly to avoid lazy loading issues
        ms_event = self.session.query(ManuscriptEvent).filter_by(event_id=event.id).first()
        if not ms_event:
            raise DatabaseError(f"No manuscript data for event: {event.display_name}")

        if not ms_event.deleted_at:
            raise DatabaseError(f"Manuscript event not deleted: {event.display_name}")

        ms_event.deleted_at = None
        ms_event.deleted_by = None
        ms_event.deletion_reason = None

        self.session.flush()

        return ms_event

    # =========================================================================
    # ARC OPERATIONS
    # =========================================================================

    @handle_db_errors
    @log_database_operation("get_arc")
    def get_arc(self, arc_name: str, include_deleted: bool = False) -> Optional[Arc]:
        """Get arc by name."""
        normalized = DataValidator.normalize_string(arc_name)
        if not normalized:
            return None

        query = self.session.query(Arc).filter_by(arc=normalized)

        if not include_deleted:
            query = query.filter(Arc.deleted_at.is_(None))

        return query.first()

    @handle_db_errors
    @log_database_operation("get_or_create_arc")
    def get_or_create_arc(self, arc_name: str) -> Arc:
        """Get existing arc or create it."""
        normalized = DataValidator.normalize_string(arc_name)
        if not normalized:
            raise ValidationError("Arc name cannot be empty")

        return self._get_or_create(Arc, {"arc": normalized})

    @handle_db_errors
    @log_database_operation("get_all_arcs")
    def get_all_arcs(self, include_deleted: bool = False) -> List[Arc]:
        """Get all arcs."""
        query = self.session.query(Arc)

        if not include_deleted:
            query = query.filter(Arc.deleted_at.is_(None))

        return query.order_by(Arc.arc).all()

    # =========================================================================
    # THEME OPERATIONS
    # =========================================================================

    @handle_db_errors
    @log_database_operation("get_theme")
    def get_theme(
        self, theme_name: str, include_deleted: bool = False
    ) -> Optional[Theme]:
        """Get theme by name."""
        normalized = DataValidator.normalize_string(theme_name)
        if not normalized:
            return None

        query = self.session.query(Theme).filter_by(theme=normalized)

        if not include_deleted:
            query = query.filter(Theme.deleted_at.is_(None))

        return query.first()

    @handle_db_errors
    @log_database_operation("get_or_create_theme")
    def get_or_create_theme(self, theme_name: str) -> Theme:
        """Get existing theme or create it."""
        normalized = DataValidator.normalize_string(theme_name)
        if not normalized:
            raise ValidationError("Theme name cannot be empty")

        return self._get_or_create(Theme, {"theme": normalized})

    @handle_db_errors
    @log_database_operation("get_all_themes")
    def get_all_themes(self, include_deleted: bool = False) -> List[Theme]:
        """Get all themes."""
        query = self.session.query(Theme)

        if not include_deleted:
            query = query.filter(Theme.deleted_at.is_(None))

        return query.order_by(Theme.theme).all()

    # =========================================================================
    # QUERY METHODS
    # =========================================================================

    @handle_db_errors
    @log_database_operation("get_ready_entries")
    def get_ready_entries(self) -> List[ManuscriptEntry]:
        """
        Get entries ready for manuscript (edited=True AND status.is_content=True).

        Returns:
            List of ManuscriptEntry objects ready for publication
        """
        all_entries = self.session.query(ManuscriptEntry).all()

        ready = [
            me
            for me in all_entries
            if me.edited and me.status and me.status.is_content
        ]

        # Sort by entry date
        return sorted(ready, key=lambda me: me.entry.date)

    @handle_db_errors
    @log_database_operation("get_entries_by_status")
    def get_entries_by_status(
        self, status: Union[ManuscriptStatus, str]
    ) -> List[ManuscriptEntry]:
        """Get all manuscript entries with specific status."""
        if isinstance(status, str):
            try:
                status = ManuscriptStatus[status.upper()]
            except KeyError:
                status_lower = status.lower()
                for ms in ManuscriptStatus:
                    if ms.value == status_lower:
                        status = ms
                        break

        if not isinstance(status, ManuscriptStatus):
            return []

        return (
            self.session.query(ManuscriptEntry)
            .filter_by(status=status)
            .order_by(ManuscriptEntry.entry_id)
            .all()
        )

    @handle_db_errors
    @log_database_operation("get_events_by_arc")
    def get_events_by_arc(
        self, arc: Arc, include_deleted: bool = False
    ) -> List[ManuscriptEvent]:
        """Get all manuscript events in an arc."""
        query = self.session.query(ManuscriptEvent).filter_by(arc_id=arc.id)

        if not include_deleted:
            query = query.filter(ManuscriptEvent.deleted_at.is_(None))

        return query.all()

    @handle_db_errors
    @log_database_operation("get_entries_by_theme")
    def get_entries_by_theme(
        self, theme: Theme, include_deleted: bool = False
    ) -> List[ManuscriptEntry]:
        """Get all manuscript entries with a specific theme."""
        if include_deleted:
            return theme.entries
        else:
            # Filter out entries from soft-deleted themes
            return [
                e for e in theme.entries if not hasattr(theme, 'deleted_at') or not theme.deleted_at
            ]
