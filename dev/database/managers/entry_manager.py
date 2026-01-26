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

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Sequence

from sqlalchemy.orm import Session
from sqlalchemy import insert

from dev.core.exceptions import ValidationError
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.core.validators import DataValidator
from dev.utils import fs
from dev.database.models import (
    Arc,
    City,
    Entry,
    Event,
    NarratedDate,
    Person,
    Scene,
    Tag,
    Theme,
    Thread,
)
from dev.database.decorators import DatabaseOperation
# TODO: TombstoneManager needs rebuild for new model structure
# from dev.database.tombstone_manager import TombstoneManager
from .base_manager import BaseManager
# TODO: EntryRelationshipHelper needs rebuild for new model structure
# from .entry_helpers import EntryRelationshipHelper


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
        # TODO: Re-enable when tombstone system is rebuilt
        # self.tombstones = TombstoneManager(session, logger)
        # self.helpers = EntryRelationshipHelper(session, logger)

        # Cache manager instances to avoid repeated instantiation
        from dev.database.managers import PersonManager, LocationManager, EventManager
        self._person_mgr = PersonManager(session, logger)
        self._location_mgr = LocationManager(session, logger)
        self._event_mgr = EventManager(session, logger)

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
                if file_path_obj.exists():
                    file_hash = fs.get_file_hash(file_path)
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
                            file_hash = fs.get_file_hash(value)
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
                        file_hash = fs.get_file_hash(file_path)

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

        # Handle dicts for Person model (from MdEntry people parsing)
        if isinstance(item, dict) and model_class == Person:
            name = DataValidator.normalize_string(item.get("name"))
            full_name = DataValidator.normalize_string(item.get("full_name"))

            if name or full_name:
                return self._person_mgr.get_or_create(name or full_name, full_name)
            return None

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

        Creates tombstones for removed associations to enable proper multi-machine
        synchronization.

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
            sync_source (str): Source of sync ('yaml', 'wiki', 'manual') for tombstones
            removed_by (str): Who/what is making changes ('yaml2sql', 'wiki2sql', etc.)

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
                ("events", "events", Event, "entry_events"),
            ]

            for rel_name, meta_key, model_class, table_name in many_to_many_configs:
                if meta_key in metadata:
                    items = metadata[meta_key]
                    remove_items = metadata.get(f"remove_{meta_key}", [])

                    # Get the collection
                    collection = getattr(entry, rel_name)

                    # Replacement mode: clear and add all
                    if not incremental:
                        # TODO: Create tombstones for all removed items (tombstones disabled)
                        # for existing_item in list(collection):
                        #     self.tombstones.create(
                        #         table_name=table_name,
                        #         left_id=entry.id,
                        #         right_id=existing_item.id,
                        #         removed_by=removed_by,
                        #         sync_source=sync_source,
                        #         reason="replacement_mode",
                        #     )

                        collection.clear()

                        for item in items:
                            resolved_item = self._resolve_or_create(item, model_class)
                            if resolved_item and resolved_item not in collection:
                                # TODO: Remove tombstone if re-adding (tombstones disabled)
                                # self.tombstones.remove_tombstone(
                                #     table_name, entry.id, resolved_item.id
                                # )
                                collection.append(resolved_item)
                    else:
                        # Incremental mode: add new items
                        for item in items:
                            resolved_item = self._resolve_or_create(item, model_class)
                            if resolved_item and resolved_item not in collection:
                                # TODO: Remove tombstone if re-adding (tombstones disabled)
                                # self.tombstones.remove_tombstone(
                                #     table_name, entry.id, resolved_item.id
                                # )
                                collection.append(resolved_item)

                        # Remove specified items
                        for item in remove_items:
                            resolved_item = self._resolve_or_create(item, model_class)
                            if resolved_item and resolved_item in collection:
                                # TODO: Create tombstone before removing (tombstones disabled)
                                # self.tombstones.create(
                                #     table_name=table_name,
                                #     left_id=entry.id,
                                #     right_id=resolved_item.id,
                                #     removed_by=removed_by,
                                #     sync_source=sync_source,
                                #     reason="removed_from_source",
                                # )
                                collection.remove(resolved_item)

                    self.session.flush()

            # --- Aliases ---
            # TODO: Alias model removed in new schema - person.alias is now a field
            # if "alias" in metadata:
            #     self._process_aliases(entry, metadata["alias"])

            # --- Locations ---
            if "locations" in metadata:
                self._process_locations(entry, metadata["locations"], incremental)

            # --- Narrated Dates ---
            # TODO: Rebuild for new NarratedDate model (replaces Moment)
            # if "narrated_dates" in metadata:
            #     self._process_narrated_dates(entry, metadata["narrated_dates"])

            # --- References ---
            # References need special handling because they involve ReferenceSource creation
            if "references" in metadata:
                self._process_references(entry, metadata["references"])

            # --- Poems ---
            if "poems" in metadata:
                self._process_poems(entry, metadata["poems"])

            # --- Related entries ---
            # Handle related entries (uni-directional relationships)
            if "related_entries" in metadata:
                self._process_related_entries(entry, metadata["related_entries"])

            # --- Tags ---
            # They're strings, not objects
            if "tags" in metadata:
                self._process_tags(entry, metadata["tags"], incremental)

            # --- Manuscript ---
            # TODO: Manuscript processing now handled via Chapter model

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
    # DEPRECATED: Alias processing removed - person.alias is now a field on Person
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # DEPRECATED: Moment processing removed - replaced by NarratedDate/Scene/Thread
    # TODO: Rebuild for new schema when needed
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

    def _process_related_entries(self, entry: Entry, related_dates: List[str]) -> None:
        """Process related entry connections (uni-directional)."""
        for date_str in related_dates:
            try:
                related_date = date.fromisoformat(date_str)
                related_entry = (
                    self.session.query(Entry).filter_by(date=related_date).first()
                )
                if related_entry and related_entry.id != entry.id:
                    entry.related_entries.append(related_entry)
            except ValueError:
                # Invalid date format, skip
                continue

    def _process_locations(
        self,
        entry: Entry,
        locations_data: List[Dict[str, Any]],
        incremental: bool = True,
    ) -> None:
        """
        Process locations with city context for entry.

        Delegates to LocationManager for location resolution.

        Args:
            entry: Entry to update
            locations_data: List of location dicts with "name" and "city" keys
            incremental: Whether to add (True) or replace (False) locations
        """
        # Use helper for location processing
        self.helpers.update_entry_locations(entry, locations_data, incremental)

    def _process_references(
        self,
        entry: Entry,
        references_data: List[Dict[str, Any]],
    ) -> None:
        """
        Process references with source creation.

        Delegates to ReferenceManager via helper.

        Args:
            entry: Entry to attach references to
            references_data: List of reference dicts
        """
        # Use helper for reference processing
        self.helpers.process_references(entry, references_data)

    def _process_poems(
        self,
        entry: Entry,
        poems_data: List[Dict[str, Any]],
    ) -> None:
        """
        Process poem versions with parent poem creation.

        Delegates to PoemManager via helper.

        Args:
            entry: Entry to attach poems to
            poems_data: List of poem version dicts
        """
        # Use helper for poem processing
        self.helpers.process_poems(entry, poems_data)

    # -------------------------------------------------------------------------
    # DEPRECATED: Manuscript processing removed - use Chapter model directly
    # -------------------------------------------------------------------------
