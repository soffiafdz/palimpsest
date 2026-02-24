#!/usr/bin/env python3
"""
entry_manager.py
--------------------
Manager for Entry CRUD operations and relationship processing.

This is the most complex manager as Entry is the central entity with
relationships to almost all other entities.

Key Features:
    - Entry creation with full relationship processing
    - Bulk entry creation with batch processing
    - Complex relationship updates (incremental and full overwrite)
    - Mentioned dates, aliases, tags, locations, references, poems processing
    - Manuscript metadata integration
    - File hash management

Usage:
    entry_mgr = EntryManager(session, logger)
    entry = entry_mgr.create({"date": "2024-01-15", "file_path": "/path.md"})
"""
from __future__ import annotations

import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.orm import Session
from sqlalchemy import insert

from dev.core.exceptions import ValidationError
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.core.paths import JOURNAL_DIR
from dev.core.validators import DataValidator
from dev.utils import fs
from dev.database.models import (
    Arc,
    City,
    Entry,
    Event,
    Location,
    Motif,
    MotifInstance,
    NarratedDate,
    Person,
    Reference,
    ReferenceMode,
    ReferenceSource,
    ReferenceType,
    Scene,
    SceneDate,
    Tag,
    Theme,
    ThemeInstance,
    Thread,
)
from dev.database.decorators import DatabaseOperation
from .base_manager import BaseManager


class EntryManager(BaseManager):
    """
    Manager for Entry CRUD operations and complex relationship processing.

    The Entry is the central entity in the database, representing a journal entry
    with relationships to dates, people, locations, events, tags, references, poems,
    and manuscript metadata.

    This manager handles:
    - Entry creation and updates
    - Complex relationship processing
    - Bulk operations
    - File hash management
    - Full relationship graph updates
    """

    def __init__(self, session: Session, logger: Optional[PalimpsestLogger] = None):
        """
        Initialize EntryManager.

        Args:
            session: SQLAlchemy session
            logger: Optional logger for operation tracking
        """
        super().__init__(session, logger)

        # Cache manager instances to avoid repeated instantiation
        from dev.database.managers import PersonManager, LocationManager, EventManager
        from dev.database.managers.poem_manager import PoemManager
        self._person_mgr = PersonManager(session, logger)
        self._location_mgr = LocationManager(session, logger)
        self._event_mgr = EventManager(session, logger)
        self._poem_mgr = PoemManager(session, logger)

    # -------------------------------------------------------------------------
    # Core CRUD Operations
    # -------------------------------------------------------------------------

    def exists(
        self,
        entry_date: Optional[Union[str, date]] = None,
        file_path: Optional[str] = None,
    ) -> bool:
        """
        Check if an entry exists by date or file path.

        Args:
            entry_date: Entry date to check
            file_path: File path to check

        Returns:
            True if entry exists, False otherwise
        """
        with DatabaseOperation(self.logger, "entry_exists"):
            if entry_date is not None:
                if isinstance(entry_date, str):
                    normalized_date = DataValidator.normalize_date(entry_date)
                    if normalized_date is None:
                        return False
                    entry_date = normalized_date
                return (
                    self.session.query(Entry).filter_by(date=entry_date).first() is not None
                )

            if file_path is not None:
                file_path = DataValidator.normalize_string(file_path)
                return (
                    self.session.query(Entry).filter_by(file_path=file_path).first()
                    is not None
                )

            return False

    def get(
        self,
        entry_date: Optional[Union[str, date]] = None,
        entry_id: Optional[int] = None,
        file_path: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Optional[Entry]:
        """
        Retrieve an entry by date, ID, or file path.

        Args:
            entry_date: Entry date
            entry_id: Entry ID
            file_path: File path
            include_deleted: If True, include soft-deleted entries (default False)

        Returns:
            Entry if found, None otherwise

        Examples:
            >>> # Get entry (excludes deleted)
            >>> entry = entry_mgr.get(entry_date=date(2024, 11, 1))

            >>> # Get entry including deleted
            >>> entry = entry_mgr.get(entry_date=date(2024, 11, 1), include_deleted=True)
        """
        with DatabaseOperation(self.logger, "get_entry"):
            if entry_id is not None:
                entry = self.session.get(Entry, entry_id)
                if entry and not include_deleted and entry.is_deleted:
                    return None
                return entry

            query = self.session.query(Entry)

            if entry_date is not None:
                if isinstance(entry_date, str):
                    entry_date = DataValidator.normalize_date(entry_date)
                query = query.filter_by(date=entry_date)

            elif file_path is not None:
                file_path = DataValidator.normalize_string(file_path)
                query = query.filter_by(file_path=file_path)

            else:
                return None

            # Filter out soft-deleted entries unless explicitly requested
            if not include_deleted:
                query = query.filter(Entry.deleted_at.is_(None))

            return query.first()

    def create(
        self,
        metadata: Dict[str, Any],
        sync_source: str = "manual",
        removed_by: str = "system",
    ) -> Entry:
        """
        Create a new Entry in the database with its associated relationships.

        This function does NOT handle file I/O or Markdown parsing. It assumes
        that `metadata` is already normalized (all dates as `datetime.date`,
        people, tags, events, etc. as strings or dicts).

        Args:
            metadata (Dict[str, Any]): Normalized metadata for the entry.
                Required keys:
                    - date (str | datetime.date)
                    - file_path (str)
                Optional keys:
                    - file_hash (str)
                    - word_count (int|str)
                    - reading_time (float|str)
                    - epigraph (str)
                    - epigraph_attribution (str)
                    - notes (str)
                Relationship keys (optional):
                    - dates (List[Moment|int])
                    - cities (List[City|int])
                    - locations (List[Location|int])
                    - people (List[Person|int])
                    - references (List[Reference|int])
                    - events (List[Event|int])
                    - poems (List[Poem|int])
                    - tags (List[str])
                    - alias (List[str|Dict])
                    - related_entries (List[str])
                    - manuscript (Dict)
        Returns:
            Entry: The newly created Entry ORM object.
        """
        with DatabaseOperation(self.logger, "create_entry"):
            # --- Required fields ---
            parsed_date = DataValidator.normalize_date(metadata["date"])
            if not parsed_date:
                raise ValueError(f"Invalid date format: {metadata['date']}")

            file_path = DataValidator.normalize_string(metadata["file_path"])
            if not file_path:
                raise ValueError(f"Invalid file_path: {metadata['file_path']}")

            # --- file_path uniqueness check ---
            existing = self.session.query(Entry).filter_by(file_path=file_path).first()
            if existing:
                raise ValidationError(f"Entry already exists for file_path: {file_path}")

            # --- If hash doesn't exist, create it ---
            file_hash = DataValidator.normalize_string((metadata.get("file_hash")))
            if not file_hash and file_path:
                file_path_obj = Path(file_path)
                if not file_path_obj.is_absolute():
                    file_path_obj = JOURNAL_DIR / file_path_obj
                if file_path_obj.exists():
                    file_hash = fs.get_file_hash(file_path_obj)
                else:
                    safe_logger(self.logger).log_warning(
                        f"File path does not exist, cannot calculate hash: {file_path}"
                    )

            # --- Create Entry ---
            def _do_create():
                entry = Entry(
                    date=parsed_date,
                    file_path=file_path,
                    file_hash=file_hash,
                    word_count=DataValidator.normalize_int(metadata.get("word_count")),
                    reading_time=DataValidator.normalize_float(
                        metadata.get("reading_time")
                    ),
                    summary=DataValidator.normalize_string(metadata.get("summary")),
                    rating=DataValidator.normalize_float(metadata.get("rating")),
                    rating_justification=DataValidator.normalize_string(
                        metadata.get("rating_justification")
                    ),
                    metadata_hash=DataValidator.normalize_string(
                        metadata.get("metadata_hash")
                    ),
                )
                self.session.add(entry)
                self.session.flush()
                return entry

            entry = self._execute_with_retry(_do_create)

            # --- Relationships ---
            self.update_relationships(
                entry,
                metadata,
                incremental=True,
                sync_source=sync_source,
                removed_by=removed_by,
            )
            return entry

    def update(
        self,
        entry: Entry,
        metadata: Dict[str, Any],
        sync_source: str = "manual",
        removed_by: str = "system",
    ) -> Entry:
        """
        Update an existing Entry in the database and refresh its relationships.

        Does NOT perform file parsing. Accepts pre-normalized metadata.
        Clears previous relationships before adding new ones.

        Args:
            entry (Entry): Existing Entry ORM object to update.
            metadata (Dict[str, Any]): Normalized metadata as in `create`.
                Keys may include:
                    - Core fields:
                      date, file_path,
                      word_count, reading_time, epigraph, epigraph_attribution, notes
                    - Relationship keys:
                      dates, cities, locations, people, references, events, poems, tags

        Returns:
            Entry: The updated Entry ORM object (still attached to session).

        Notes: version_hash is automatically updated if content changes
        """
        with DatabaseOperation(self.logger, "update_entry"):
            # --- Ensure existance ---
            db_entry = self.session.get(Entry, entry.id)
            if db_entry is None:
                raise ValueError(f"Entry with id={entry.id} does not exist")

            # --- Attach to session ---
            entry = self.session.merge(db_entry)

            # --- Update scalar fields ---
            def _do_update():
                field_updates = {
                    "date": DataValidator.normalize_date,
                    "file_path": DataValidator.normalize_string,
                    "file_hash": DataValidator.normalize_string,
                    "metadata_hash": DataValidator.normalize_string,
                    "word_count": DataValidator.normalize_int,
                    "reading_time": DataValidator.normalize_float,
                    "summary": DataValidator.normalize_string,
                    "rating": DataValidator.normalize_float,
                    "rating_justification": DataValidator.normalize_string,
                }

                for field, normalizer in field_updates.items():
                    if field not in metadata:
                        continue

                    value = normalizer(metadata[field])
                    if value is not None or field in [
                        "summary",
                        "rating_justification",
                    ]:
                        if field == "file_path" and value is not None:
                            resolved = Path(value)
                            if not resolved.is_absolute():
                                resolved = JOURNAL_DIR / resolved
                            file_hash = fs.get_file_hash(resolved)
                            setattr(entry, "file_hash", file_hash)
                        setattr(entry, field, value)

                self.session.flush()
                return entry

            entry = self._execute_with_retry(_do_update)

            # --- Update relationships ---
            self.update_relationships(
                entry,
                metadata,
                incremental=False,  # Update mode uses replacement
                sync_source=sync_source,
                removed_by=removed_by,
            )
            return entry

    def delete(
        self,
        entry: Entry,
        deleted_by: str = "system",
        reason: Optional[str] = None,
        hard_delete: bool = False,
    ) -> None:
        """
        Delete an entry (soft delete by default).

        Soft delete marks the entry as deleted without removing it from the
        database, enabling recovery and proper multi-machine synchronization.

        Args:
            entry: Entry to delete
            deleted_by: Who/what is deleting (user, system, sync process)
            reason: Optional reason for deletion
            hard_delete: If True, permanently delete (use with caution!)

        Examples:
            >>> # Soft delete (default)
            >>> entry_mgr.delete(entry, deleted_by='yaml2sql', reason='removed_from_source')

            >>> # Hard delete (permanent)
            >>> entry_mgr.delete(entry, hard_delete=True, reason='duplicate')
        """
        with DatabaseOperation(self.logger, "delete_entry"):
            def _do_delete():
                if hard_delete:
                    # Permanent deletion - cannot be recovered
                    self.session.delete(entry)
                    safe_logger(self.logger).log_warning(
                        f"HARD DELETE: Entry {entry.date}",
                        {"reason": reason, "deleted_by": deleted_by},
                    )
                else:
                    # Soft delete - mark as deleted
                    entry.soft_delete(deleted_by=deleted_by, reason=reason)
                    safe_logger(self.logger).log_info(
                        f"Soft deleted entry {entry.date}",
                        {"deleted_by": deleted_by, "reason": reason},
                    )

                self.session.flush()

            self._execute_with_retry(_do_delete)

    def restore(self, entry: Entry) -> None:
        """
        Restore a soft-deleted entry.

        Args:
            entry: Entry to restore

        Examples:
            >>> # Restore deleted entry
            >>> entry_mgr.restore(entry)
        """

        def _do_restore():
            entry.restore()
            safe_logger(self.logger).log_info(f"Restored entry {entry.date}")
            self.session.flush()

        self._execute_with_retry(_do_restore)

    def bulk_create(
        self,
        entries_metadata: List[Dict[str, Any]],
        batch_size: int = 100,
    ) -> List[int]:
        """
        Create multiple entries efficiently using bulk operations.

        Args:
            entries_metadata: List of metadata dictionaries for entries
            batch_size: Number of entries to insert per batch

        Returns:
            List of created entry IDs
        """
        with DatabaseOperation(self.logger, "bulk_create_entries"):
            created_ids = []

            # Process in batches
            for i in range(0, len(entries_metadata), batch_size):
                batch = entries_metadata[i : i + batch_size]

                # Prepare mappings for bulk insert
                mappings = []
                for metadata in batch:
                    parsed_date = DataValidator.normalize_date(metadata["date"])
                    file_path = DataValidator.normalize_string(metadata["file_path"])
                    file_hash = DataValidator.normalize_string(metadata.get("file_hash"))

                    if file_path and not file_hash:
                        resolved = Path(file_path)
                        if not resolved.is_absolute():
                            resolved = JOURNAL_DIR / resolved
                        file_hash = fs.get_file_hash(resolved)

                    # Use default values for NOT NULL fields with defaults
                    word_count = DataValidator.normalize_int(metadata.get("word_count"))
                    reading_time = DataValidator.normalize_float(metadata.get("reading_time"))

                    mappings.append(
                        {
                            "date": parsed_date,
                            "file_path": file_path,
                            "file_hash": file_hash,
                            "word_count": word_count if word_count is not None else 0,
                            "reading_time": reading_time if reading_time is not None else 0.0,
                            "summary": DataValidator.normalize_string(
                                metadata.get("summary")
                            ),
                            "rating": DataValidator.normalize_float(metadata.get("rating")),
                            "rating_justification": DataValidator.normalize_string(
                                metadata.get("rating_justification")
                            ),
                            "created_at": datetime.now(timezone.utc),
                            "updated_at": datetime.now(timezone.utc),
                        }
                    )

                def _do_bulk_insert():
                    # Use Core insert for bulk operations
                    stmt = insert(Entry).values(mappings)
                    self.session.execute(stmt)
                    self.session.flush()

                self._execute_with_retry(_do_bulk_insert)

                # Get IDs of created entries
                dates = [m["date"] for m in mappings]
                created_entries = (
                    self.session.query(Entry).filter(Entry.date.in_(dates)).all()
                )
                created_ids.extend([e.id for e in created_entries])

                safe_logger(self.logger).log_operation(
                    "bulk_create_batch",
                    {"batch_number": i // batch_size + 1, "count": len(batch)},
                )

            return created_ids

    def get_for_display(self, entry_date: Union[str, date]) -> Optional[Entry]:
        """
        Get single entry optimized for display operations.

        Loads basic metadata without heavy relationships like references/poems.

        Args:
            entry_date: Date to query

        Returns:
            Entry with display relationships preloaded
        """
        with DatabaseOperation(self.logger, "get_entry_for_display"):
            if isinstance(entry_date, str):
                entry_date = date.fromisoformat(entry_date)

            entry = self.session.query(Entry).filter_by(date=entry_date).first()

            if entry:
                # Import here to avoid circular dependency
                from dev.database.query_optimizer import QueryOptimizer

                # Use optimized display query
                return QueryOptimizer.for_display(self.session, entry.id)

            return None

    # -------------------------------------------------------------------------
    # Relationship Processing Methods
    # -------------------------------------------------------------------------

    def _resolve_or_create(
        self, item: Union[Any, int, str], model_class: type
    ) -> Optional[Any]:
        """
        Resolve an item to an ORM object, creating it if it's a string.

        This extends the base _resolve_object() to handle string inputs from
        YAML parsing by delegating to get_or_create methods.

        Args:
            item: Object instance, ID, or string name
            model_class: Target model class

        Returns:
            Resolved ORM object, or None if item is None

        Raises:
            ValueError: If object not found
            TypeError: If item type is unsupported
        """
        if item is None:
            return None

        # Handle strings by delegating to appropriate get_or_create
        if isinstance(item, str):
            if model_class == Person:
                return self._person_mgr.get_or_create(item)
            elif model_class == Event:
                return self._event_mgr.get_or_create(item)
            elif model_class == City:
                return self._location_mgr.get_or_create_city(item)
            else:
                raise TypeError(
                    f"String resolution not supported for {model_class.__name__}"
                )

        # Handle dicts for Person model
        if isinstance(item, dict) and model_class == Person:
            name = DataValidator.normalize_string(item.get("name"))
            lastname = DataValidator.normalize_string(item.get("lastname"))
            disambiguator = DataValidator.normalize_string(item.get("disambiguator"))

            # Backward compat: fall back to full_name as lastname
            if not lastname and not disambiguator:
                lastname = DataValidator.normalize_string(item.get("full_name"))

            if not name:
                safe_logger(self.logger).log_warning(
                    f"Person dict missing 'name': {item}"
                )
                return None

            if not lastname and not disambiguator:
                safe_logger(self.logger).log_warning(
                    f"Person '{name}' missing both lastname and disambiguator"
                )
                return None

            person = self._person_mgr.get_or_create(name, lastname, disambiguator)

            # Handle alias field
            alias_val = item.get("alias")
            if alias_val:
                aliases = alias_val if isinstance(alias_val, list) else [alias_val]
                self._person_mgr.add_aliases(person, aliases)

            return person

        # Handle ORM instances and IDs using base method (after string check to narrow type)
        if isinstance(item, (model_class, int)):
            return self._resolve_object(item, model_class)  # type: ignore[arg-type]

        # Unknown type
        raise TypeError(
            f"Expected {model_class.__name__} instance, int, or str, got {type(item)}"
        )

    def update_relationships(
        self,
        entry: Entry,
        metadata: Dict[str, Any],
        incremental: bool = True,
        sync_source: str = "manual",
        removed_by: str = "system",
    ) -> None:
        """
        Update relationships for an Entry object in the database.

        Supports both incremental updates (default) and full overwrite.
        This function handles relationships only. No I/O or Markdown parsing.
        Prevents duplicates and ensures lookup tables are updated.


        Args:
            entry (Entry): Entry ORM object to update relationships for.
            metadata (Dict[str, Any]): Normalized metadata containing:
                Expected keys (optional):
                    - dates (List[Moment|int|str|Dict]) - Mentioned dates with optional context
                    - cities (List[City|int|str]) - Cities where entry took place
                    - locations (List[Dict]) - Locations with city context: {"name": str, "city": str}
                    - people (List[Person|int|str]) - People mentioned
                    - events (List[Event|int|str]) - Events entry belongs to
                    - tags (List[str]) - Keyword tags
                    - alias (List[str|Dict]) - Aliases used in this entry
                    - related_entries (List[str]) - Date strings of related entries
                    - references (List[Dict]) - External references with sources
                    - poems (List[Dict]) - Poem versions
                    - manuscript (Dict) - Manuscript metadata
                Removal keys (optional):
                    - remove_dates (List[Moment|int])
                    - remove_cities (List[City|int])
                    - remove_people (List[Person|int])
                    - remove_events (List[Event|int])
                    - remove_locations (List[Location|int])
            incremental (bool): If True, add/remove specified items.
                                If False, replace all relationships.
            sync_source (str): Source of sync (unused, kept for compatibility)
            removed_by (str): Who/what is making changes (unused, kept for compatibility)

        Behavior:
            - Incremental mode:
                adds new relationships and/or removes explicitly listed items.
            - Overwrite mode:
                clears all existing relationships before adding new ones.
            - Calls session.flush() only if any changes were made

        Special Handling:
            - dates: Supports both simple date strings and dicts with context
            - locations: Requires city context in dict format
            - references: Creates ReferenceSource records as needed
            - poems: Creates Poem parent records as needed
            - tags: Simple string list (not ORM objects)
            - related_entries: Uni-directional relationships by date string
        """
        try:
            # --- Many to many ---
            many_to_many_configs = [
                ("cities", "cities", City, "entry_cities"),
                ("people", "people", Person, "entry_people"),
            ]

            for rel_name, meta_key, model_class, table_name in many_to_many_configs:
                if meta_key in metadata:
                    items = metadata[meta_key]
                    remove_items = metadata.get(f"remove_{meta_key}", [])

                    # Get the collection
                    collection = getattr(entry, rel_name)

                    # Replacement mode: clear and add all
                    if not incremental:
                        collection.clear()

                        for item in items:
                            resolved_item = self._resolve_or_create(item, model_class)
                            if resolved_item and resolved_item not in collection:
                                collection.append(resolved_item)
                    else:
                        # Incremental mode: add new items
                        for item in items:
                            resolved_item = self._resolve_or_create(item, model_class)
                            if resolved_item and resolved_item not in collection:
                                collection.append(resolved_item)

                        # Remove specified items
                        for item in remove_items:
                            resolved_item = self._resolve_or_create(item, model_class)
                            if resolved_item and resolved_item in collection:
                                collection.remove(resolved_item)

                    self.session.flush()

            # --- Locations (M2M with city context) ---
            if "locations" in metadata:
                self._process_locations(entry, metadata["locations"], incremental)

            # --- Narrated Dates (O2M) ---
            if "narrated_dates" in metadata:
                self._process_narrated_dates(
                    entry, metadata["narrated_dates"], incremental
                )

            # --- Scenes (O2M) ---
            if "scenes" in metadata:
                self._process_scenes(
                    entry, metadata["scenes"], incremental
                )

            # --- Events (M2M with scene linking) ---
            if "events" in metadata:
                self._process_events(entry, metadata["events"], incremental)

            # --- Tags ---
            if "tags" in metadata:
                self._process_tags(entry, metadata["tags"], incremental)

            # --- Arcs (M2M) ---
            if "arcs" in metadata:
                self._process_arcs(entry, metadata["arcs"], incremental)

            # --- Themes (M2M) ---
            if "themes" in metadata:
                self._process_themes(entry, metadata["themes"], incremental)

            # --- Threads (O2M) ---
            if "threads" in metadata:
                self._process_threads(entry, metadata["threads"], incremental)

            # --- Motifs (O2M) ---
            if "motifs" in metadata:
                self._process_motifs(entry, metadata["motifs"], incremental)

            # --- References (O2M) ---
            if "references" in metadata:
                self._process_references(entry, metadata["references"], incremental)

            # --- Poems (O2M) ---
            if "poems" in metadata:
                self._process_poems(entry, metadata["poems"], incremental)

            self.session.flush()

        except Exception as e:
            # Log error with context
            safe_logger(self.logger).log_error(
                e,
                {
                    "operation": "update_entry_relationships",
                    "entry_id": entry.id,
                    "entry_date": str(entry.date),
                },
            )
            # Re-raise for higher-level handling
            raise

    # -------------------------------------------------------------------------
    # Name Normalization and Lookup Helpers
    # -------------------------------------------------------------------------

    def _normalize_name(self, name: str) -> str:
        """
        Normalize a name for accent/diacritic-insensitive comparison.

        Handles accent differences (Sofía vs Sofia), hyphen/space
        differences (María-José vs María José), and case folding.

        Args:
            name: Name string to normalize

        Returns:
            Lowercase name with accents stripped and hyphens as spaces
        """
        text = name.lower().strip()
        text = text.replace("-", " ")
        normalized = unicodedata.normalize("NFD", text)
        without_accents = "".join(
            c for c in normalized if unicodedata.category(c)[0] != "M"
        )
        return without_accents

    def _find_person_in_entry(self, name: str, entry: Entry) -> Optional[Person]:
        """
        Find a person in the entry's already-resolved people list.

        Scene/thread people are subsets of entry-level people. This looks
        up a person by name (with accent normalization) from the entry's
        people list, including alias matching.

        Args:
            name: Person name to find
            entry: Entry with already-resolved people

        Returns:
            Person entity if found, None otherwise
        """
        name_normalized = self._normalize_name(name)
        for person in entry.people:
            if self._normalize_name(person.name) == name_normalized:
                return person
            for alias in person.aliases:
                if self._normalize_name(alias.alias) == name_normalized:
                    return person
        return None

    def _find_location_in_entry(
        self, name: str, entry: Entry
    ) -> Optional[Location]:
        """
        Find a location in the entry's already-resolved locations list.

        Scene/thread locations are subsets of entry-level locations. This
        looks up a location by name (with accent normalization) from the
        entry's locations list.

        Args:
            name: Location name to find
            entry: Entry with already-resolved locations

        Returns:
            Location entity if found, None otherwise
        """
        name_normalized = self._normalize_name(name)
        for location in entry.locations:
            if self._normalize_name(location.name) == name_normalized:
                return location
        return None

    def _add_scene_date(self, scene: Scene, date_value: Any) -> None:
        """
        Add a date to a scene as a SceneDate record.

        Stores dates as strings to support flexible formats:
        YYYY-MM-DD, YYYY-MM, YYYY, ~YYYY, ~YYYY-MM, ~YYYY-MM-DD.

        Args:
            scene: Scene entity to add the date to
            date_value: Date value (date object or string)
        """
        if isinstance(date_value, date):
            date_str = date_value.isoformat()
        elif isinstance(date_value, str):
            date_str = date_value.strip()
        else:
            return
        sd = SceneDate(date=date_str, scene_id=scene.id)
        self.session.add(sd)

    def _get_or_create_event(self, name: str) -> Event:
        """
        Get an existing event by name or create a new one.

        Events are unique by name and shared across entries via M2M.

        Args:
            name: Event name

        Returns:
            Event entity (existing or newly created)
        """
        event = self.session.query(Event).filter_by(name=name).first()
        if not event:
            event = Event(name=name)
            self.session.add(event)
            self.session.flush()
        return event

    def _get_or_create_reference_source(
        self, source_data: Dict[str, Any]
    ) -> ReferenceSource:
        """
        Get an existing reference source by title or create a new one.

        Args:
            source_data: Dict with title, author (optional), type (optional),
                        url (optional)

        Returns:
            ReferenceSource entity (existing or newly created)
        """
        title = source_data.get("title", "")
        source = (
            self.session.query(ReferenceSource).filter_by(title=title).first()
        )
        if not source:
            type_str = source_data.get("type", "book")
            try:
                ref_type = ReferenceType(type_str)
            except ValueError:
                ref_type = ReferenceType.BOOK

            source = ReferenceSource(
                title=title,
                author=source_data.get("author"),
                type=ref_type,
                url=source_data.get("url"),
            )
            self.session.add(source)
            self.session.flush()
        else:
            # Update mutable fields if they changed
            new_author = source_data.get("author")
            if new_author and new_author != source.author:
                source.author = new_author
            new_url = source_data.get("url")
            if new_url and new_url != source.url:
                source.url = new_url
            new_type = source_data.get("type")
            if new_type:
                try:
                    ref_type = ReferenceType(new_type)
                    if ref_type != source.type:
                        source.type = ref_type
                except ValueError:
                    pass
            self.session.flush()
        return source

    # -------------------------------------------------------------------------
    # Relationship Processor Methods
    # -------------------------------------------------------------------------

    def _process_tags(
        self,
        entry: Entry,
        tags: List[str],
        incremental: bool = True,
    ) -> None:
        """
        Update Tags for an Entry from metadata.

        Args:
            entry (Entry): Entry object whose tags are to be updated.
            tags (List[str]): List of tags (strings).
            incremental (bool): Whether incremental/overwrite mode.

        Behavior:
            - Incremental mode:
                adds new relationships and/or removes explicitly listed items.
            - Overwrite mode:
                clears all existing relationships before adding new ones.
            - Calls session.flush() only if any changes were made

        Returns:
            None
        """
        # --- Failsafe ---
        if entry.id is None:
            raise ValueError("Entry must be persisted before linking tags")

        # --- Normalize incoming tags --
        norm_tags = {DataValidator.normalize_string(t) for t in tags}

        if not incremental:
            entry.tags.clear()
            self.session.flush()

        existing_tags = {tag.name for tag in entry.tags}

        # Add new tags
        for tag_name in norm_tags - existing_tags:
            tag_obj = self._get_or_create(Tag, {"name": tag_name})
            entry.tags.append(tag_obj)

        if norm_tags - existing_tags:
            self.session.flush()

    def _process_locations(
        self,
        entry: Entry,
        locations_data: Any,
        incremental: bool = True,
    ) -> None:
        """
        Process locations with city context for an entry.

        Input format is a dict of {city_name: [location_names]}, matching
        the MD frontmatter structure.

        Args:
            entry: Entry to link locations to
            locations_data: Dict mapping city names to lists of location names
            incremental: If True, add locations; if False, clear and replace

        Notes:
            - Cities are automatically added to entry.cities
            - Uses LocationManager for get-or-create operations
        """
        if not incremental:
            entry.locations.clear()
            self.session.flush()

        if not isinstance(locations_data, dict):
            return

        for city_name, loc_names in locations_data.items():
            city = self._location_mgr.get_or_create_city(str(city_name))
            if city not in entry.cities:
                entry.cities.append(city)

            if isinstance(loc_names, list):
                for loc_name in loc_names:
                    location = self._location_mgr.get_or_create_location(
                        str(loc_name), str(city_name)
                    )
                    if location not in entry.locations:
                        entry.locations.append(location)

        self.session.flush()

    def _process_narrated_dates(
        self,
        entry: Entry,
        narrated_dates: List[Any],
        incremental: bool = True,
    ) -> None:
        """
        Create NarratedDate records for an entry.

        Args:
            entry: Entry to create NarratedDates for
            narrated_dates: List of date objects or ISO date strings
            incremental: If True, add dates; if False, clear and replace
        """
        if not incremental:
            entry.narrated_dates.clear()
            self.session.flush()

        for date_val in narrated_dates or []:
            if isinstance(date_val, date):
                nd = NarratedDate(date=date_val, entry_id=entry.id)
                self.session.add(nd)
            elif isinstance(date_val, str):
                try:
                    parsed = date.fromisoformat(date_val)
                    nd = NarratedDate(date=parsed, entry_id=entry.id)
                    self.session.add(nd)
                except ValueError:
                    pass

        self.session.flush()

    def _process_scenes(
        self,
        entry: Entry,
        scenes_data: List[Dict[str, Any]],
        incremental: bool = True,
    ) -> None:
        """
        Create scenes for an entry with dates, people, and locations.

        Scene people and locations are resolved from the entry's
        already-linked people and locations (subset matching).

        Args:
            entry: Entry to create scenes for
            scenes_data: List of scene dicts with name, description, date,
                        people, locations
            incremental: If True, add scenes; if False, clear and replace

        Notes:
            - Stores a _scene_map attribute on entry for event linking
            - People/locations are matched by normalized name against
              entry-level collections
        """
        if not incremental:
            entry.scenes.clear()
            self.session.flush()

        scene_map: Dict[str, Scene] = {}

        for scene_data in scenes_data or []:
            scene = Scene(
                name=scene_data.get("name", "Unnamed Scene"),
                description=scene_data.get("description", ""),
                entry_id=entry.id,
            )
            self.session.add(scene)
            self.session.flush()

            scene_map[scene.name] = scene

            # Create scene dates
            scene_date = scene_data.get("date")
            if scene_date:
                if isinstance(scene_date, list):
                    for d in scene_date:
                        self._add_scene_date(scene, d)
                else:
                    self._add_scene_date(scene, scene_date)

            # Link people from entry (subset matching)
            for person_name in scene_data.get("people", []) or []:
                person = self._find_person_in_entry(str(person_name), entry)
                if person and person not in scene.people:
                    scene.people.append(person)

            # Link locations from entry (subset matching)
            for loc_name in scene_data.get("locations", []) or []:
                location = self._find_location_in_entry(str(loc_name), entry)
                if location and location not in scene.locations:
                    scene.locations.append(location)

        # Store scene map on entry for event processing
        entry._scene_map = scene_map  # type: ignore[attr-defined]
        self.session.flush()

    def _process_events(
        self,
        entry: Entry,
        events_data: List[Any],
        incremental: bool = True,
    ) -> None:
        """
        Process events for an entry with scene linking.

        Events are M2M with both Entry and Scene. Each event dict can
        specify which scenes belong to it. Accepts both string event
        names and dicts with name + scenes.

        Args:
            entry: Entry to link events to
            events_data: List of event names (str) or dicts with
                        name and scenes keys
            incremental: If True, add events; if False, clear and replace
        """
        if not incremental:
            entry.events.clear()
            self.session.flush()

        # Build scene map from _scene_map or existing scenes
        scene_map: Dict[str, Scene] = getattr(entry, "_scene_map", {})
        if not scene_map:
            scene_map = {scene.name: scene for scene in entry.scenes}

        for event_data in events_data or []:
            if isinstance(event_data, str):
                event_name = event_data
                event_scenes: List[str] = []
            elif isinstance(event_data, dict):
                event_name = event_data.get("name", "Unnamed Event")
                event_scenes = event_data.get("scenes", []) or []
            else:
                continue

            event = self._get_or_create_event(event_name)

            if event not in entry.events:
                entry.events.append(event)

            # Link scenes by name
            for scene_name in event_scenes:
                scene = scene_map.get(scene_name)
                if scene and scene not in event.scenes:
                    event.scenes.append(scene)

        self.session.flush()

    def _process_arcs(
        self,
        entry: Entry,
        arcs_data: List[str],
        incremental: bool = True,
    ) -> None:
        """
        Link arcs to an entry (M2M).

        Args:
            entry: Entry to link arcs to
            arcs_data: List of arc name strings
            incremental: If True, add arcs; if False, clear and replace
        """
        if not incremental:
            entry.arcs.clear()

        for arc_name in arcs_data or []:
            arc = self._get_or_create(Arc, {"name": arc_name})
            if arc not in entry.arcs:
                entry.arcs.append(arc)

        self.session.flush()

    def _process_themes(
        self,
        entry: Entry,
        themes_data: List[Dict[str, Any]],
        incremental: bool = True,
    ) -> None:
        """
        Create theme instances for an entry.

        Each theme instance links a free-form theme to an entry with
        an entry-specific description, following the motif instance pattern.

        Args:
            entry: Entry to create theme instances for
            themes_data: List of dicts with name and description
            incremental: If True, add instances; if False, clear and replace

        Notes:
            - Both name and description are required; items missing either
              are silently skipped
        """
        if not incremental:
            entry.theme_instances.clear()
            self.session.flush()

        for theme_data in themes_data or []:
            theme_name = theme_data.get("name")
            description = theme_data.get("description", "")

            if not theme_name or not description:
                continue

            theme = self._get_or_create(Theme, {"name": theme_name})

            instance = ThemeInstance(
                theme_id=theme.id,
                entry_id=entry.id,
                description=description,
            )
            self.session.add(instance)

        self.session.flush()

    def _process_threads(
        self,
        entry: Entry,
        threads_data: List[Dict[str, Any]],
        incremental: bool = True,
    ) -> None:
        """
        Create threads for an entry.

        Threads are temporal echoes connecting a proximate moment to a
        distant moment. Dates are stored as strings to support flexible
        formats (YYYY, YYYY-MM, YYYY-MM-DD, ~YYYY, etc.).

        Args:
            entry: Entry to create threads for
            threads_data: List of thread dicts with name, from, to, entry,
                         content, people, locations
            incremental: If True, add threads; if False, clear and replace

        Notes:
            - People/locations are matched against entry-level collections
            - referenced_entry_date is parsed to a date object when possible
        """
        if not incremental:
            entry.threads.clear()
            self.session.flush()

        for thread_data in threads_data or []:
            # Parse from_date
            from_date_val = thread_data.get("from")
            if isinstance(from_date_val, date):
                from_date_str = from_date_val.isoformat()
            elif isinstance(from_date_val, str):
                from_date_str = from_date_val
            else:
                continue

            # Parse to_date
            to_date_val = thread_data.get("to", "")
            if isinstance(to_date_val, date):
                to_date_str = to_date_val.isoformat()
            else:
                to_date_str = str(to_date_val)

            # Parse referenced entry date
            ref_entry_val = thread_data.get("entry")
            ref_entry_date = None
            if isinstance(ref_entry_val, date):
                ref_entry_date = ref_entry_val
            elif isinstance(ref_entry_val, str):
                try:
                    ref_entry_date = date.fromisoformat(ref_entry_val)
                except ValueError:
                    pass

            thread = Thread(
                name=thread_data.get("name", "Unnamed Thread"),
                from_date=from_date_str,
                to_date=to_date_str,
                referenced_entry_date=ref_entry_date,
                content=thread_data.get("content", ""),
                entry_id=entry.id,
            )
            self.session.add(thread)
            self.session.flush()

            # Link people from entry (subset matching)
            for person_name in thread_data.get("people", []) or []:
                person = self._find_person_in_entry(str(person_name), entry)
                if person and person not in thread.people:
                    thread.people.append(person)

            # Link locations from entry (subset matching)
            for loc_name in thread_data.get("locations", []) or []:
                location = self._find_location_in_entry(str(loc_name), entry)
                if location and location not in thread.locations:
                    thread.locations.append(location)

        self.session.flush()

    def _process_motifs(
        self,
        entry: Entry,
        motifs_data: List[Dict[str, Any]],
        incremental: bool = True,
    ) -> None:
        """
        Create motif instances for an entry.

        Each motif instance links a controlled-vocabulary motif to an
        entry with an entry-specific description.

        Args:
            entry: Entry to create motif instances for
            motifs_data: List of dicts with name and description
            incremental: If True, add instances; if False, clear and replace

        Notes:
            - Both name and description are required; items missing either
              are silently skipped
        """
        if not incremental:
            entry.motif_instances.clear()
            self.session.flush()

        for motif_data in motifs_data or []:
            motif_name = motif_data.get("name")
            description = motif_data.get("description", "")

            if not motif_name or not description:
                continue

            motif = self._get_or_create(Motif, {"name": motif_name})

            instance = MotifInstance(
                motif_id=motif.id,
                entry_id=entry.id,
                description=description,
            )
            self.session.add(instance)

        self.session.flush()

    def _process_references(
        self,
        entry: Entry,
        refs_data: List[Dict[str, Any]],
        incremental: bool = True,
    ) -> None:
        """
        Create references for an entry with source resolution.

        Each reference links an entry to a ReferenceSource with content
        and/or description and a reference mode.

        Args:
            entry: Entry to create references for
            refs_data: List of dicts with source (dict or str), content,
                      description, mode
            incremental: If True, add references; if False, clear and replace

        Notes:
            - Source can be a string (treated as title) or a dict with
              title, author, type, url
            - Mode defaults to "direct" if not specified or invalid
        """
        if not incremental:
            entry.references.clear()
            self.session.flush()

        for ref_data in refs_data or []:
            source_data = ref_data.get("source", {})
            if isinstance(source_data, str):
                source_data = {"title": source_data}

            title = source_data.get("title")
            if not title:
                continue

            source = self._get_or_create_reference_source(source_data)

            mode_str = ref_data.get("mode", "direct")
            try:
                mode = ReferenceMode(mode_str)
            except ValueError:
                mode = ReferenceMode.DIRECT

            reference = Reference(
                entry_id=entry.id,
                source_id=source.id,
                content=ref_data.get("content"),
                description=ref_data.get("description"),
                mode=mode,
            )
            self.session.add(reference)

        self.session.flush()

    def _process_poems(
        self,
        entry: Entry,
        poems_data: List[Dict[str, Any]],
        incremental: bool = True,
    ) -> None:
        """
        Create poem versions for an entry.

        Delegates to PoemManager.create_version() which handles parent
        Poem get-or-create and content deduplication.

        Args:
            entry: Entry to create poem versions for
            poems_data: List of dicts with title and content
            incremental: If True, add versions; if False, clear and replace

        Notes:
            - Both title and content are required; items missing either
              are silently skipped
            - Duplicate content for the same poem is deduplicated by
              PoemManager
        """
        if not incremental:
            entry.poems.clear()
            self.session.flush()

        for poem_data in poems_data or []:
            title = poem_data.get("title")
            content = poem_data.get("content")

            if not title or not content:
                continue

            self._poem_mgr.create_version({
                "title": title,
                "content": content,
                "entry": entry,
            })

        self.session.flush()
