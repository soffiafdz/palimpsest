#!/usr/bin/env python3
"""
event_manager.py
--------------------
Manages Event entities and their relationships with entries and people.

Events represent narrative events or periods that span multiple journal entries.
They support soft delete functionality and have many-to-many relationships
with both entries and people.

Key Features:
    - CRUD operations for events
    - Soft delete support (deleted events are hidden but preserved)
    - Link/unlink events to/from entries and people
    - Query by various criteria (date range, participants)
    - Chronological ordering of event entries
    - Manuscript event relationship handling

Usage:
    event_mgr = EventManager(session, logger)

    # Create event
    event = event_mgr.create({
        "event": "paris_trip",
        "title": "Paris Trip 2023",
        "description": "Two week trip to Paris"
    })

    # Update event
    event_mgr.update(event, {
        "description": "Updated description",
        "entries": [entry1, entry2],
        "people": [person1]
    })

    # Link to entry
    event_mgr.link_to_entry(event, entry)

    # Soft delete
    event_mgr.delete(event, deleted_by="admin", reason="Duplicate")

    # Restore
    event_mgr.restore(event)
"""
from typing import Dict, List, Optional, Any
from datetime import date

from dev.core.validators import DataValidator
from dev.core.exceptions import ValidationError, DatabaseError
from dev.database.decorators import (
    handle_db_errors,
    log_database_operation,
    validate_metadata,
)
from dev.database.models import Event, Entry, Person
from .base_manager import BaseManager


class EventManager(BaseManager):
    """
    Manages Event table operations and relationships.

    Events are narrative events or periods that can span multiple entries
    and involve multiple people. They support soft delete.
    """

    # -------------------------------------------------------------------------
    # Core CRUD Operations
    # -------------------------------------------------------------------------

    @handle_db_errors
    @log_database_operation("event_exists")
    def exists(self, event_name: str, include_deleted: bool = False) -> bool:
        """
        Check if an event exists without raising exceptions.

        Args:
            event_name: The event identifier to check
            include_deleted: Whether to include soft-deleted events

        Returns:
            True if event exists, False otherwise
        """
        normalized = DataValidator.normalize_string(event_name)
        if not normalized:
            return False

        query = self.session.query(Event).filter_by(event=normalized)

        if not include_deleted:
            query = query.filter(Event.deleted_at.is_(None))

        return query.first() is not None

    @handle_db_errors
    @log_database_operation("get_event")
    def get(
        self, event_name: Optional[str] = None, event_id: Optional[int] = None, include_deleted: bool = False
    ) -> Optional[Event]:
        """
        Retrieve an event by name or ID.

        Args:
            event_name: The event identifier
            event_id: The event ID
            include_deleted: Whether to include soft-deleted events

        Returns:
            Event object if found, None otherwise

        Notes:
            - If both name and ID provided, ID takes precedence
            - By default, soft-deleted events are excluded
        """
        if event_id is not None:
            event = self.session.get(Event, event_id)
            if event and (include_deleted or not event.deleted_at):
                return event
            return None

        if event_name is not None:
            normalized = DataValidator.normalize_string(event_name)
            if not normalized:
                return None

            query = self.session.query(Event).filter_by(event=normalized)

            if not include_deleted:
                query = query.filter(Event.deleted_at.is_(None))

            return query.first()

        return None

    @handle_db_errors
    @log_database_operation("get_all_events")
    def get_all(self, include_deleted: bool = False) -> List[Event]:
        """
        Retrieve all events.

        Args:
            include_deleted: Whether to include soft-deleted events

        Returns:
            List of all Event objects, ordered by event name
        """
        query = self.session.query(Event)

        if not include_deleted:
            query = query.filter(Event.deleted_at.is_(None))

        return query.order_by(Event.event).all()

    @handle_db_errors
    @log_database_operation("create_event")
    @validate_metadata(["event"])
    def create(self, metadata: Dict[str, Any]) -> Event:
        """
        Create a new event with optional relationships.

        Args:
            metadata: Dictionary with required key:
                - event: Short identifier (required, unique)
                Optional keys:
                - title: Full title
                - description: Detailed description
                - entries: List of Entry objects or IDs
                - people: List of Person objects or IDs

        Returns:
            Created Event object

        Raises:
            ValidationError: If event name is missing or invalid
            DatabaseError: If event already exists
        """
        event_name = DataValidator.normalize_string(metadata.get("event"))
        if not event_name:
            raise ValidationError(f"Invalid event name: {metadata.get('event')}")

        # Check for existing (including deleted)
        existing = self.get(event_name=event_name, include_deleted=True)
        if existing:
            if existing.deleted_at:
                raise DatabaseError(
                    f"Event '{event_name}' exists but is deleted. "
                    f"Restore it instead of creating new."
                )
            else:
                raise DatabaseError(f"Event already exists: {event_name}")

        # Create event
        event = Event(
            event=event_name,
            title=DataValidator.normalize_string(metadata.get("title")),
            description=DataValidator.normalize_string(metadata.get("description")),
        )
        self.session.add(event)
        self.session.flush()

        if self.logger:
            self.logger.log_debug(f"Created event: {event_name}", {"event_id": event.id})

        # Update relationships
        self._update_relationships(event, metadata, incremental=False)

        return event

    @handle_db_errors
    @log_database_operation("get_or_create_event")
    def get_or_create(self, event_name: str) -> Event:
        """
        Get existing event or create new one if not found.

        This is a convenience method for use when processing YAML metadata that
        contains event names as strings. It creates events with minimal metadata.

        Args:
            event_name: Event identifier to search for or create

        Returns:
            Existing or newly created Event object

        Raises:
            ValidationError: If event_name is empty or invalid
        """
        normalized_name = DataValidator.normalize_string(event_name)
        if not normalized_name:
            raise ValidationError("Event name cannot be empty")
        event_name = normalized_name

        # Try to get existing event
        event = self.get(event_name=event_name)
        if event:
            return event

        # Event doesn't exist - create it
        return self.create({"event": event_name})

    @handle_db_errors
    @log_database_operation("update_event")
    def update(self, event: Event, metadata: Dict[str, Any]) -> Event:
        """
        Update an existing event.

        Args:
            event: Event object to update
            metadata: Dictionary with optional keys:
                - event: Short identifier
                - title: Full title
                - description: Detailed description
                - entries: List of Entry objects or IDs (incremental by default)
                - people: List of Person objects or IDs (incremental by default)
                - remove_entries: List of entries to remove
                - remove_people: List of people to remove

        Returns:
            Updated Event object

        Raises:
            DatabaseError: If event not found or is deleted
        """
        # Ensure event exists and is not deleted
        db_event = self.session.get(Event, event.id)
        if db_event is None:
            raise DatabaseError(f"Event with id={event.id} does not exist")
        if db_event.deleted_at:
            raise DatabaseError(f"Cannot update deleted event: {db_event.event}")

        # Attach to session
        event = self.session.merge(db_event)

        # Update scalar fields
        field_updates = {
            "event": DataValidator.normalize_string,
            "title": DataValidator.normalize_string,
            "description": DataValidator.normalize_string,
        }

        for field, normalizer in field_updates.items():
            if field in metadata:
                value = normalizer(metadata[field])
                if value is not None or field in ["title", "description"]:
                    setattr(event, field, value)

        # Update relationships
        self._update_relationships(event, metadata, incremental=True)

        return event

    @handle_db_errors
    @log_database_operation("delete_event")
    def delete(
        self,
        event: Event,
        deleted_by: Optional[str] = None,
        reason: Optional[str] = None,
        hard_delete: bool = False,
    ) -> None:
        """
        Delete an event (soft delete by default).

        Args:
            event: Event object or ID to delete
            deleted_by: Identifier of who is deleting
            reason: Reason for deletion
            hard_delete: If True, permanently delete instead of soft delete

        Notes:
            - Soft delete preserves the event but hides it from queries
            - Hard delete removes the event and all relationships
            - Manuscript events are cascade deleted
        """
        if isinstance(event, int):
            event = self.get(event_id=event, include_deleted=True)
            if not event:
                raise DatabaseError(f"Event not found with id: {event}")

        if hard_delete:
            if self.logger:
                self.logger.log_debug(
                    f"Hard deleting event: {event.event}",
                    {"event_id": event.id, "entry_count": len(event.entries)},
                )
            self.session.delete(event)
        else:
            if self.logger:
                self.logger.log_debug(
                    f"Soft deleting event: {event.event}",
                    {
                        "event_id": event.id,
                        "deleted_by": deleted_by,
                        "reason": reason,
                    },
                )
            from datetime import datetime, timezone

            event.deleted_at = datetime.now(timezone.utc)
            event.deleted_by = deleted_by
            event.deletion_reason = reason

        self.session.flush()

    @handle_db_errors
    @log_database_operation("restore_event")
    def restore(self, event: Event) -> Event:
        """
        Restore a soft-deleted event.

        Args:
            event: Event object or ID to restore

        Returns:
            Restored Event object

        Raises:
            DatabaseError: If event not found or not deleted
        """
        if isinstance(event, int):
            event = self.get(event_id=event, include_deleted=True)
            if not event:
                raise DatabaseError(f"Event not found with id: {event}")

        if not event.deleted_at:
            raise DatabaseError(f"Event is not deleted: {event.event}")

        event.deleted_at = None
        event.deleted_by = None
        event.deletion_reason = None

        self.session.flush()

        if self.logger:
            self.logger.log_debug(
                f"Restored event: {event.event}", {"event_id": event.id}
            )

        return event

    # -------------------------------------------------------------------------
    # Relationship Management
    # -------------------------------------------------------------------------

    def _update_relationships(
        self,
        event: Event,
        metadata: Dict[str, Any],
        incremental: bool = True,
    ) -> None:
        """
        Update relationships for an event.

        Args:
            event: Event object to update
            metadata: Metadata with relationship keys:
                - entries: List of Entry objects or IDs
                - people: List of Person objects or IDs
                - remove_entries: List to remove (incremental mode only)
                - remove_people: List to remove (incremental mode only)
            incremental: Whether to add incrementally or replace all
        """
        # Many-to-many relationships
        many_to_many_configs = [
            ("entries", "entries", Entry),
            ("people", "people", Person),
        ]

        for rel_name, meta_key, model_class in many_to_many_configs:
            if meta_key in metadata:
                items = metadata[meta_key]
                remove_items = metadata.get(f"remove_{meta_key}", [])

                # Get the collection
                collection = getattr(event, rel_name)

                # Replacement mode: clear and add all
                if not incremental:
                    collection.clear()
                    for item in items:
                        resolved_item = self._resolve_object(item, model_class)
                        if resolved_item and resolved_item not in collection:
                            collection.append(resolved_item)
                else:
                    # Incremental mode: add new items
                    for item in items:
                        resolved_item = self._resolve_object(item, model_class)
                        if resolved_item and resolved_item not in collection:
                            collection.append(resolved_item)

                    # Remove specified items
                    for item in remove_items:
                        resolved_item = self._resolve_object(item, model_class)
                        if resolved_item and resolved_item in collection:
                            collection.remove(resolved_item)

                self.session.flush()

    @handle_db_errors
    @log_database_operation("link_event_to_entry")
    def link_to_entry(self, event: Event, entry: Entry) -> None:
        """
        Link an event to an entry.

        Args:
            event: Event object
            entry: Entry object to link

        Raises:
            ValueError: If either object is not persisted
        """
        if event.id is None:
            raise ValueError("Event must be persisted before linking")
        if entry.id is None:
            raise ValueError("Entry must be persisted before linking")

        if entry not in event.entries:
            event.entries.append(entry)
            self.session.flush()

            if self.logger:
                self.logger.log_debug(
                    f"Linked event to entry",
                    {"event": event.event, "entry_date": entry.date},
                )

    @handle_db_errors
    @log_database_operation("unlink_event_from_entry")
    def unlink_from_entry(self, event: Event, entry: Entry) -> bool:
        """
        Unlink an event from an entry.

        Args:
            event: Event object
            entry: Entry object to unlink

        Returns:
            True if unlinked, False if wasn't linked

        Raises:
            ValueError: If either object is not persisted
        """
        if event.id is None:
            raise ValueError("Event must be persisted before unlinking")
        if entry.id is None:
            raise ValueError("Entry must be persisted before unlinking")

        if entry in event.entries:
            event.entries.remove(entry)
            self.session.flush()

            if self.logger:
                self.logger.log_debug(
                    f"Unlinked event from entry",
                    {"event": event.event, "entry_date": entry.date},
                )
            return True

        return False

    @handle_db_errors
    @log_database_operation("link_event_to_person")
    def link_to_person(self, event: Event, person: Person) -> None:
        """
        Link an event to a person.

        Args:
            event: Event object
            person: Person object to link

        Raises:
            ValueError: If either object is not persisted
        """
        if event.id is None:
            raise ValueError("Event must be persisted before linking")
        if person.id is None:
            raise ValueError("Person must be persisted before linking")

        if person not in event.people:
            event.people.append(person)
            self.session.flush()

            if self.logger:
                self.logger.log_debug(
                    f"Linked event to person",
                    {"event": event.event, "person": person.name},
                )

    @handle_db_errors
    @log_database_operation("unlink_event_from_person")
    def unlink_from_person(self, event: Event, person: Person) -> bool:
        """
        Unlink an event from a person.

        Args:
            event: Event object
            person: Person object to unlink

        Returns:
            True if unlinked, False if wasn't linked

        Raises:
            ValueError: If either object is not persisted
        """
        if event.id is None:
            raise ValueError("Event must be persisted before unlinking")
        if person.id is None:
            raise ValueError("Person must be persisted before unlinking")

        if person in event.people:
            event.people.remove(person)
            self.session.flush()

            if self.logger:
                self.logger.log_debug(
                    f"Unlinked event from person",
                    {"event": event.event, "person": person.name},
                )
            return True

        return False

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    @handle_db_errors
    @log_database_operation("get_events_by_date_range")
    def get_by_date_range(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_deleted: bool = False,
    ) -> List[Event]:
        """
        Get events that have entries within a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            include_deleted: Whether to include soft-deleted events

        Returns:
            List of Event objects with entries in the date range

        Notes:
            - Events are filtered based on their entry dates
            - Results are sorted by event name
        """
        query = self.session.query(Event).join(Event.entries)

        if start_date:
            query = query.filter(Entry.date >= start_date)
        if end_date:
            query = query.filter(Entry.date <= end_date)
        if not include_deleted:
            query = query.filter(Event.deleted_at.is_(None))

        return query.order_by(Event.event).distinct().all()

    @handle_db_errors
    @log_database_operation("get_events_for_person")
    def get_for_person(
        self, person: Person, include_deleted: bool = False
    ) -> List[Event]:
        """
        Get all events associated with a person.

        Args:
            person: Person object
            include_deleted: Whether to include soft-deleted events

        Returns:
            List of Event objects linked to the person
        """
        query = self.session.query(Event).join(Event.people).filter(Person.id == person.id)

        if not include_deleted:
            query = query.filter(Event.deleted_at.is_(None))

        return query.order_by(Event.event).all()

    @handle_db_errors
    @log_database_operation("get_events_for_entry")
    def get_for_entry(
        self, entry: Entry, include_deleted: bool = False
    ) -> List[Event]:
        """
        Get all events associated with an entry.

        Args:
            entry: Entry object
            include_deleted: Whether to include soft-deleted events

        Returns:
            List of Event objects linked to the entry
        """
        if include_deleted:
            return entry.events
        else:
            return [e for e in entry.events if not e.deleted_at]
