#!/usr/bin/env python3
"""
entry_helpers.py
--------------------
Helper class for EntryManager relationship processing.

This module contains the EntryRelationshipHelper class which handles the complex
relationship processing logic for Entry objects.

Key Features:
    - Caches manager instances to avoid repeated instantiation
    - Processes person relationships
    - Handles location associations
    - Manages reference creation and linking
    - Processes poem version creation
    - Manages manuscript entry associations

Usage:
    from .entry_helpers import EntryRelationshipHelper

    helper = EntryRelationshipHelper(session, logger)
    helper.process_references(entry, references_data)
    helper.process_poems(entry, poems_data)
    helper.update_entry_locations(entry, locations_data)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from dev.core.logging_manager import PalimpsestLogger
from dev.core.validators import DataValidator
from dev.database.models import Entry, Person, Location


class EntryRelationshipHelper:
    """
    Helper class for processing Entry relationships.

    This class caches manager instances and provides methods for processing
    various types of relationships associated with Entry objects.

    Attributes:
        session: SQLAlchemy session for database operations
        logger: Optional logger for operation tracking
        person_manager: Cached PersonManager instance
        location_manager: Cached LocationManager instance
        reference_manager: Cached ReferenceManager instance
        poem_manager: Cached PoemManager instance
    """

    def __init__(self, session: Session, logger: Optional[PalimpsestLogger] = None):
        """
        Initialize the helper with cached manager instances.

        Args:
            session: SQLAlchemy session for database operations
            logger: Optional logger for operation tracking
        """
        self.session = session
        self.logger = logger

        # Import managers here to avoid circular dependencies
        from .person_manager import PersonManager
        from .location_manager import LocationManager
        from .reference_manager import ReferenceManager
        from .poem_manager import PoemManager

        # Cache manager instances to avoid repeated instantiation
        self.person_manager = PersonManager(session, logger)
        self.location_manager = LocationManager(session, logger)
        self.reference_manager = ReferenceManager(session, logger)
        self.poem_manager = PoemManager(session, logger)

    def get_person(
        self,
        person_name: Optional[str] = None,
        person_full_name: Optional[str] = None,
    ) -> Optional[Person]:
        """
        Get a person by name or full name.

        Args:
            person_name: The person's name (alias)
            person_full_name: The person's full name

        Returns:
            Person object if found, None otherwise
        """
        return self.person_manager.get(
            person_name=person_name,
            person_full_name=person_full_name
        )

    def update_entry_locations(
        self,
        entry: Entry,
        locations_data: List[Any],
        incremental: bool = True,
    ) -> None:
        """
        Update locations associated with an entry.

        Processes location data and associates locations with the entry.
        Supports different input formats: dictionaries with name/city,
        location names as strings, or Location objects.

        Args:
            entry: The Entry object to update
            locations_data: List of location specifications (dicts, strings, or Location objects)
            incremental: If False, clears existing locations before adding new ones

        Raises:
            ValueError: If entry is not persisted
        """
        if entry.id is None:
            raise ValueError("Entry must be persisted before linking locations")

        if not incremental:
            entry.locations.clear()
            self.session.flush()

        existing_location_ids = {loc.id for loc in entry.locations}

        for loc_spec in locations_data:
            # Handle different input formats
            if isinstance(loc_spec, dict):
                location_name = DataValidator.normalize_string(loc_spec.get("name"))
                city_name = DataValidator.normalize_string(loc_spec.get("city"))

                if not location_name or not city_name:
                    continue

                # Get or create location via manager
                city = self.location_manager.get_or_create_city(city_name)
                location = self.location_manager.get_or_create_location(location_name, city)

            elif isinstance(loc_spec, str):
                # Just a location name - need city context
                location_name = DataValidator.normalize_string(loc_spec)
                if not location_name:
                    continue
                # Try to find existing location by name only
                # Type narrowing: LocationManager.get returns Optional[Location]
                location_result = self.location_manager.get_location(location_name=location_name)  # type: ignore[attr-defined]
                if not location_result:
                    continue
                location = location_result
            elif isinstance(loc_spec, Location):
                location = loc_spec
            else:
                continue

            if location and location.id not in existing_location_ids:
                entry.locations.append(location)

        self.session.flush()

    def process_references(
        self,
        entry: Entry,
        references_data: List[Dict[str, Any]],
    ) -> None:
        """
        Process and create references associated with an entry.

        Creates Reference objects from metadata and associates them with the entry.
        Also handles reference source creation/lookup if provided.

        Args:
            entry: The Entry object to add references to
            references_data: List of reference metadata dictionaries

        Raises:
            ValueError: If entry is not persisted
        """
        if entry.id is None:
            raise ValueError("Entry must be persisted before adding references")

        for ref_data in references_data:
            content = DataValidator.normalize_string(ref_data.get("content"))
            description = DataValidator.normalize_string(ref_data.get("description"))

            if not content and not description:
                continue

            # Process source if provided
            source = None
            if "source" in ref_data and ref_data["source"]:
                source_data = ref_data["source"]
                if isinstance(source_data, dict):
                    title = DataValidator.normalize_string(source_data.get("title"))
                    if title:
                        # Get or create source via manager
                        source = self.reference_manager.get_or_create_source(
                            title=title,
                            source_type=source_data.get("type"),
                            author=source_data.get("author"),
                        )

            # Create reference via manager
            ref_metadata = {
                "content": content,
                "description": description,
                "mode": ref_data.get("mode", "direct"),
                "speaker": ref_data.get("speaker"),
                "entry": entry,
                "source": source,
            }
            self.reference_manager.create_reference(ref_metadata)

    def process_poems(
        self,
        entry: Entry,
        poems_data: List[Dict[str, Any]],
    ) -> None:
        """
        Process and create poem versions associated with an entry.

        Creates PoemVersion objects from metadata and associates them with the entry.
        Uses the entry date as the default revision date if not specified.

        Args:
            entry: The Entry object to add poems to
            poems_data: List of poem metadata dictionaries

        Raises:
            ValueError: If entry is not persisted
        """
        if entry.id is None:
            raise ValueError("Entry must be persisted before adding poems")

        for poem_data in poems_data:
            title = DataValidator.normalize_string(poem_data.get("title"))
            content = DataValidator.normalize_string(poem_data.get("content"))

            if not title or not content:
                continue

            # Parse revision date (default to entry date)
            revision_date = DataValidator.normalize_date(
                poem_data.get("revision_date") or entry.date
            )

            # Create poem version via manager
            self.poem_manager.create_version({
                "title": title,
                "content": content,
                "revision_date": revision_date,
                "notes": poem_data.get("notes"),
                "entry": entry,
            })

    # -------------------------------------------------------------------------
    # DEPRECATED: Manuscript entry creation removed - use Chapter model directly
    # -------------------------------------------------------------------------
