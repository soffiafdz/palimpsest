#!/usr/bin/env python3
"""
date_manager.py
--------------------
Manages MentionedDate entities and their relationships with entries, locations, and people.

MentionedDates represent specific dates referenced within journal entries that are
distinct from the entry's own date. They track temporal references and enable
cross-referencing of events across the journal timeline.

Key Features:
    - CRUD operations for mentioned dates
    - Many-to-many relationships with entries, locations, and people
    - Context tracking for why dates are mentioned
    - Temporal analysis and querying
    - Get-or-create semantics with optional context

Usage:
    date_mgr = DateManager(session, logger)

    # Create or get a mentioned date
    mentioned_date = date_mgr.get_or_create(date(2023, 6, 15), context="Birthday")

    # Link to entry
    date_mgr.link_to_entry(mentioned_date, entry)

    # Link to location and people
    date_mgr.link_to_location(mentioned_date, location)
    date_mgr.link_to_person(mentioned_date, person)

    # Query dates by range
    dates = date_mgr.get_by_range(start_date, end_date)
"""
from typing import Dict, List, Optional, Any, Union
from datetime import date

from sqlalchemy import and_

from dev.core.validators import DataValidator
from dev.core.exceptions import ValidationError, DatabaseError
from dev.database.decorators import (
    handle_db_errors,
    log_database_operation,
)
from dev.database.models import MentionedDate, Entry, Location, Person
from dev.database.relationship_manager import RelationshipManager
from .base_manager import BaseManager


class DateManager(BaseManager):
    """
    Manages MentionedDate table operations and relationships.

    Mentioned dates are temporal references within journal entries that
    can be linked to specific locations and people for context.
    """

    # -------------------------------------------------------------------------
    # Core CRUD Operations
    # -------------------------------------------------------------------------

    @handle_db_errors
    @log_database_operation("mentioned_date_exists")
    def exists(self, target_date: date) -> bool:
        """
        Check if a mentioned date exists.

        Args:
            target_date: The date to check

        Returns:
            True if date exists, False otherwise
        """
        return (
            self.session.query(MentionedDate).filter_by(date=target_date).first()
            is not None
        )

    @handle_db_errors
    @log_database_operation("get_mentioned_date")
    def get(
        self, target_date: date = None, date_id: int = None
    ) -> Optional[MentionedDate]:
        """
        Retrieve a mentioned date by date value or ID.

        Args:
            target_date: The date value
            date_id: The mentioned date ID

        Returns:
            MentionedDate object if found, None otherwise

        Notes:
            - If both provided, ID takes precedence
            - Multiple MentionedDate records can exist for same date with different contexts
            - Returns first match when searching by date
        """
        if date_id is not None:
            return self.session.get(MentionedDate, date_id)

        if target_date is not None:
            return self.session.query(MentionedDate).filter_by(date=target_date).first()

        return None

    @handle_db_errors
    @log_database_operation("get_all_mentioned_dates")
    def get_all(self, order_by_date: bool = True) -> List[MentionedDate]:
        """
        Retrieve all mentioned dates.

        Args:
            order_by_date: Whether to order by date (default True)

        Returns:
            List of all MentionedDate objects
        """
        query = self.session.query(MentionedDate)

        if order_by_date:
            query = query.order_by(MentionedDate.date)

        return query.all()

    @handle_db_errors
    @log_database_operation("create_mentioned_date")
    def create(self, metadata: Dict[str, Any]) -> MentionedDate:
        """
        Create a new mentioned date.

        Args:
            metadata: Dictionary with required key:
                - date: date object or ISO string (required)
                Optional keys:
                - context: Text explaining why date is mentioned
                - entries: List of Entry objects or IDs
                - locations: List of Location objects or IDs
                - people: List of Person objects or IDs

        Returns:
            Created MentionedDate object

        Raises:
            ValidationError: If date is missing or invalid
            DatabaseError: If date already exists (use get_or_create instead)
        """
        # Parse date
        date_value = metadata.get("date")
        if isinstance(date_value, str):
            try:
                date_value = date.fromisoformat(date_value)
            except ValueError as e:
                raise ValidationError(f"Invalid date format: {date_value}") from e
        elif not isinstance(date_value, date):
            raise ValidationError(f"Invalid date type: {type(date_value)}")

        # Check for existing
        existing = self.get(target_date=date_value)
        if existing:
            raise DatabaseError(
                f"Mentioned date already exists for {date_value.isoformat()}. "
                f"Use get_or_create instead."
            )

        # Create
        mentioned_date = MentionedDate(
            date=date_value,
            context=DataValidator.normalize_string(metadata.get("context")),
        )
        self.session.add(mentioned_date)
        self.session.flush()

        if self.logger:
            self.logger.log_debug(
                f"Created mentioned date: {date_value.isoformat()}",
                {"date_id": mentioned_date.id},
            )

        # Update relationships
        self._update_relationships(mentioned_date, metadata, incremental=False)

        return mentioned_date

    @handle_db_errors
    @log_database_operation("update_mentioned_date")
    def update(
        self, mentioned_date: MentionedDate, metadata: Dict[str, Any]
    ) -> MentionedDate:
        """
        Update an existing mentioned date.

        Args:
            mentioned_date: MentionedDate object to update
            metadata: Dictionary with optional keys:
                - context: Updated context text
                - entries: List of entries (incremental by default)
                - locations: List of locations (incremental by default)
                - people: List of people (incremental by default)
                - remove_entries: Entries to unlink
                - remove_locations: Locations to unlink
                - remove_people: People to unlink

        Returns:
            Updated MentionedDate object

        Notes:
            - The date value itself cannot be changed
            - Use incremental updates for relationships by default
        """
        # Ensure exists
        db_date = self.session.get(MentionedDate, mentioned_date.id)
        if db_date is None:
            raise DatabaseError(f"MentionedDate with id={mentioned_date.id} not found")

        # Attach to session
        mentioned_date = self.session.merge(db_date)

        # Update context if provided
        if "context" in metadata:
            mentioned_date.context = DataValidator.normalize_string(
                metadata["context"]
            )

        # Update relationships
        self._update_relationships(mentioned_date, metadata, incremental=True)

        return mentioned_date

    @handle_db_errors
    @log_database_operation("delete_mentioned_date")
    def delete(self, mentioned_date: MentionedDate) -> None:
        """
        Delete a mentioned date.

        Args:
            mentioned_date: MentionedDate object or ID to delete

        Notes:
            - This is a hard delete (no soft delete for dates)
            - All relationships are cascade deleted
        """
        if isinstance(mentioned_date, int):
            mentioned_date = self.session.get(MentionedDate, mentioned_date)
            if not mentioned_date:
                raise DatabaseError(f"MentionedDate not found with id: {mentioned_date}")

        if self.logger:
            self.logger.log_debug(
                f"Deleting mentioned date: {mentioned_date.date.isoformat()}",
                {
                    "date_id": mentioned_date.id,
                    "entry_count": mentioned_date.entry_count,
                },
            )

        self.session.delete(mentioned_date)
        self.session.flush()

    @handle_db_errors
    @log_database_operation("get_or_create_mentioned_date")
    def get_or_create(
        self,
        target_date: Union[date, str],
        context: Optional[str] = None,
    ) -> MentionedDate:
        """
        Get an existing mentioned date or create it if it doesn't exist.

        Args:
            target_date: Date object or ISO string
            context: Optional context text

        Returns:
            MentionedDate object (existing or newly created)

        Notes:
            - This is the recommended way to work with mentioned dates
            - Matches on date value only, context is additive
        """
        # Parse date if string
        if isinstance(target_date, str):
            try:
                target_date = date.fromisoformat(target_date)
            except ValueError as e:
                raise ValidationError(f"Invalid date format: {target_date}") from e

        # Try to get existing
        existing = self.get(target_date=target_date)
        if existing:
            return existing

        # Create new
        return self.create({"date": target_date, "context": context})

    # -------------------------------------------------------------------------
    # Relationship Management
    # -------------------------------------------------------------------------

    def _update_relationships(
        self,
        mentioned_date: MentionedDate,
        metadata: Dict[str, Any],
        incremental: bool = True,
    ) -> None:
        """
        Update relationships for a mentioned date.

        Args:
            mentioned_date: MentionedDate to update
            metadata: Metadata with relationship keys:
                - entries: List of Entry objects or IDs
                - locations: List of Location objects or IDs
                - people: List of Person objects or IDs
                - remove_entries: Entries to unlink
                - remove_locations: Locations to unlink
                - remove_people: People to unlink
            incremental: Whether to add incrementally or replace all
        """
        # Many-to-many relationships
        many_to_many_configs = [
            ("entries", "entries", Entry),
            ("locations", "locations", Location),
            ("people", "people", Person),
        ]

        for rel_name, meta_key, model_class in many_to_many_configs:
            if meta_key in metadata:
                RelationshipManager.update_many_to_many(
                    session=self.session,
                    parent_obj=mentioned_date,
                    relationship_name=rel_name,
                    items=metadata[meta_key],
                    model_class=model_class,
                    incremental=incremental,
                    remove_items=metadata.get(f"remove_{meta_key}", []),
                )

    @handle_db_errors
    @log_database_operation("link_mentioned_date_to_entry")
    def link_to_entry(
        self, mentioned_date: MentionedDate, entry: Entry
    ) -> None:
        """
        Link a mentioned date to an entry.

        Args:
            mentioned_date: MentionedDate object
            entry: Entry object to link

        Raises:
            ValueError: If either object is not persisted
        """
        if mentioned_date.id is None:
            raise ValueError("MentionedDate must be persisted before linking")
        if entry.id is None:
            raise ValueError("Entry must be persisted before linking")

        if entry not in mentioned_date.entries:
            mentioned_date.entries.append(entry)
            self.session.flush()

            if self.logger:
                self.logger.log_debug(
                    f"Linked mentioned date to entry",
                    {
                        "mentioned_date": mentioned_date.date.isoformat(),
                        "entry_date": entry.date,
                    },
                )

    @handle_db_errors
    @log_database_operation("link_mentioned_date_to_location")
    def link_to_location(
        self, mentioned_date: MentionedDate, location: Location
    ) -> None:
        """
        Link a mentioned date to a location.

        Args:
            mentioned_date: MentionedDate object
            location: Location object to link
        """
        if mentioned_date.id is None:
            raise ValueError("MentionedDate must be persisted before linking")
        if location.id is None:
            raise ValueError("Location must be persisted before linking")

        if location not in mentioned_date.locations:
            mentioned_date.locations.append(location)
            self.session.flush()

            if self.logger:
                self.logger.log_debug(
                    f"Linked mentioned date to location",
                    {
                        "mentioned_date": mentioned_date.date.isoformat(),
                        "location": location.name,
                    },
                )

    @handle_db_errors
    @log_database_operation("link_mentioned_date_to_person")
    def link_to_person(
        self, mentioned_date: MentionedDate, person: Person
    ) -> None:
        """
        Link a mentioned date to a person.

        Args:
            mentioned_date: MentionedDate object
            person: Person object to link
        """
        if mentioned_date.id is None:
            raise ValueError("MentionedDate must be persisted before linking")
        if person.id is None:
            raise ValueError("Person must be persisted before linking")

        if person not in mentioned_date.people:
            mentioned_date.people.append(person)
            self.session.flush()

            if self.logger:
                self.logger.log_debug(
                    f"Linked mentioned date to person",
                    {
                        "mentioned_date": mentioned_date.date.isoformat(),
                        "person": person.name,
                    },
                )

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    @handle_db_errors
    @log_database_operation("get_mentioned_dates_by_range")
    def get_by_range(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[MentionedDate]:
        """
        Get mentioned dates within a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of MentionedDate objects in the range, ordered by date
        """
        query = self.session.query(MentionedDate)

        conditions = []
        if start_date:
            conditions.append(MentionedDate.date >= start_date)
        if end_date:
            conditions.append(MentionedDate.date <= end_date)

        if conditions:
            query = query.filter(and_(*conditions))

        return query.order_by(MentionedDate.date).all()

    @handle_db_errors
    @log_database_operation("get_mentioned_dates_for_entry")
    def get_for_entry(self, entry: Entry) -> List[MentionedDate]:
        """
        Get all mentioned dates for an entry.

        Args:
            entry: Entry object

        Returns:
            List of MentionedDate objects, ordered by date
        """
        return sorted(entry.dates, key=lambda d: d.date)

    @handle_db_errors
    @log_database_operation("get_mentioned_dates_for_location")
    def get_for_location(self, location: Location) -> List[MentionedDate]:
        """
        Get all mentioned dates for a location.

        Args:
            location: Location object

        Returns:
            List of MentionedDate objects, ordered by date
        """
        return sorted(location.dates, key=lambda d: d.date)

    @handle_db_errors
    @log_database_operation("get_mentioned_dates_for_person")
    def get_for_person(self, person: Person) -> List[MentionedDate]:
        """
        Get all mentioned dates for a person.

        Args:
            person: Person object

        Returns:
            List of MentionedDate objects, ordered by date
        """
        return sorted(person.dates, key=lambda d: d.date)
