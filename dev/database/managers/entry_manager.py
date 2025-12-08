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
from dev.core.logging_manager import PalimpsestLogger
from dev.core.validators import DataValidator
from dev.utils import fs
from dev.database.models import (
    Entry,
    MentionedDate,
    City,
    Person,
    Alias,
    Event,
    Tag,
)
from dev.database.decorators import (
    handle_db_errors,
    log_database_operation,
)
from dev.database.tombstone_manager import TombstoneManager
from .base_manager import BaseManager
from .entry_helpers import EntryRelationshipHelper


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
        self.tombstones = TombstoneManager(session, logger)
        self.helpers = EntryRelationshipHelper(session, logger)

        # Cache manager instances to avoid repeated instantiation
        from dev.database.managers import PersonManager, LocationManager, EventManager
        self._person_mgr = PersonManager(session, logger)
        self._location_mgr = LocationManager(session, logger)
        self._event_mgr = EventManager(session, logger)

    # -------------------------------------------------------------------------
    # Core CRUD Operations
    # -------------------------------------------------------------------------

    @handle_db_errors
    @log_database_operation("entry_exists")
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

    @handle_db_errors
    @log_database_operation("get_entry")
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

    @handle_db_errors
    @log_database_operation("create_entry")
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
                    - dates (List[MentionedDate|int])
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
                if self.logger:
                    self.logger.log_warning(
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
                epigraph=DataValidator.normalize_string(metadata.get("epigraph")),
                epigraph_attribution=DataValidator.normalize_string(
                    metadata.get("epigraph_attribution")
                ),
                notes=DataValidator.normalize_string(metadata.get("notes")),
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

    @handle_db_errors
    @log_database_operation("update_entry")
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
                "epigraph": DataValidator.normalize_string,
                "epigraph_attribution": DataValidator.normalize_string,
                "notes": DataValidator.normalize_string,
            }

            for field, normalizer in field_updates.items():
                if field not in metadata:
                    continue

                value = normalizer(metadata[field])
                if value is not None or field in [
                    "epigraph",
                    "epigraph_attribution",
                    "notes",
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

    @handle_db_errors
    @log_database_operation("delete_entry")
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

        def _do_delete():
            if hard_delete:
                # Permanent deletion - cannot be recovered
                self.session.delete(entry)
                if self.logger:
                    self.logger.log_warning(
                        f"HARD DELETE: Entry {entry.date}",
                        {"reason": reason, "deleted_by": deleted_by},
                    )
            else:
                # Soft delete - mark as deleted
                entry.soft_delete(deleted_by=deleted_by, reason=reason)
                if self.logger:
                    self.logger.log_info(
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
            if self.logger:
                self.logger.log_info(f"Restored entry {entry.date}")
            self.session.flush()

        self._execute_with_retry(_do_restore)

    @handle_db_errors
    @log_database_operation("bulk_create_entries")
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

                mappings.append(
                    {
                        "date": parsed_date,
                        "file_path": file_path,
                        "file_hash": file_hash,
                        "word_count": DataValidator.normalize_int(
                            metadata.get("word_count")
                        ),
                        "reading_time": DataValidator.normalize_float(
                            metadata.get("reading_time")
                        ),
                        "epigraph": DataValidator.normalize_string(
                            metadata.get("epigraph")
                        ),
                        "epigraph_attribution": DataValidator.normalize_string(
                            metadata.get("epigraph_attribution")
                        ),
                        "notes": DataValidator.normalize_string(metadata.get("notes")),
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

            if self.logger:
                self.logger.log_operation(
                    "bulk_create_batch",
                    {"batch_number": i // batch_size + 1, "count": len(batch)},
                )

        return created_ids

    @handle_db_errors
    @log_database_operation("get_entry_for_display")
    def get_for_display(self, entry_date: Union[str, date]) -> Optional[Entry]:
        """
        Get single entry optimized for display operations.

        Loads basic metadata without heavy relationships like references/poems.

        Args:
            entry_date: Date to query

        Returns:
            Entry with display relationships preloaded
        """
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
                    - dates (List[MentionedDate|int|str|Dict]) - Mentioned dates with optional context
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
                    - remove_dates (List[MentionedDate|int])
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
                        # Create tombstones for all removed items
                        for existing_item in list(collection):
                            self.tombstones.create(
                                table_name=table_name,
                                left_id=entry.id,
                                right_id=existing_item.id,
                                removed_by=removed_by,
                                sync_source=sync_source,
                                reason="replacement_mode",
                            )

                        collection.clear()

                        for item in items:
                            resolved_item = self._resolve_or_create(item, model_class)
                            if resolved_item and resolved_item not in collection:
                                # Remove tombstone if re-adding
                                self.tombstones.remove_tombstone(
                                    table_name, entry.id, resolved_item.id
                                )
                                collection.append(resolved_item)
                    else:
                        # Incremental mode: add new items
                        for item in items:
                            resolved_item = self._resolve_or_create(item, model_class)
                            if resolved_item and resolved_item not in collection:
                                # Remove tombstone if re-adding previously removed item
                                self.tombstones.remove_tombstone(
                                    table_name, entry.id, resolved_item.id
                                )
                                collection.append(resolved_item)

                        # Remove specified items
                        for item in remove_items:
                            resolved_item = self._resolve_or_create(item, model_class)
                            if resolved_item and resolved_item in collection:
                                # Create tombstone before removing
                                self.tombstones.create(
                                    table_name=table_name,
                                    left_id=entry.id,
                                    right_id=resolved_item.id,
                                    removed_by=removed_by,
                                    sync_source=sync_source,
                                    reason="removed_from_source",
                                )
                                collection.remove(resolved_item)

                    self.session.flush()

            # --- Aliases ---
            if "alias" in metadata:
                self._process_aliases(entry, metadata["alias"])

            # --- Locations ---
            if "locations" in metadata:
                self._process_locations(entry, metadata["locations"], incremental)

            # --- Dates ---
            if "dates" in metadata:
                if not incremental:
                    entry.dates.clear()
                    self.session.flush()
                self._process_mentioned_dates(entry, metadata["dates"])

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
            if "manuscript" in metadata:
                self._process_manuscript(entry, metadata["manuscript"])

            self.session.flush()

        except Exception as e:
            # Log error with context
            if self.logger:
                self.logger.log_error(
                    e,
                    {
                        "operation": "update_entry_relationships",
                        "entry_id": entry.id,
                        "entry_date": str(entry.date),
                    },
                )
            # Re-raise for higher-level handling
            raise

    def _process_aliases(
        self,
        entry: Entry,
        alias_data: Sequence[str | Sequence[str] | Dict[str, Any]],
    ):
        """
        Process aliases with optional person context and link to entry.

        Args:
            entry: Entry to link aliases to
            alias_data: List of alias specifications:
                - str: single alias
                - List[str]: multiple aliases for same person
                - Dict: {"alias": str|List[str], "name": str, "full_name": str}

        Raises:
            ValueError: If entry not persisted or invalid alias data
        """
        if entry.id is None:
            raise ValueError("Entry must be persisted before linking aliases")

        alias_orms = []

        for alias_obj in alias_data:
            person: Optional[Person] = None
            aliases: List[str] = []
            name: Optional[str] = None
            full_name: Optional[str] = None

            # Parse input format
            if isinstance(alias_obj, dict):
                # Dict format: {"alias": [...], "name": "...", "full_name": "..."}
                alias_raw = alias_obj.get("alias", [])
                if isinstance(alias_raw, str):
                    alias_raw = [alias_raw]

                aliases_raw = [
                    DataValidator.normalize_string(a) for a in alias_raw if a
                ]
                aliases = [a for a in aliases_raw if a]

                name = DataValidator.normalize_string(alias_obj.get("name"))
                full_name = DataValidator.normalize_string(alias_obj.get("full_name"))

            elif isinstance(alias_obj, list):
                # List format: ["alias1", "alias2"]
                aliases_raw = [DataValidator.normalize_string(a) for a in alias_obj]
                aliases = [a for a in aliases_raw if a]

            elif isinstance(alias_obj, str):
                # String format: "alias"
                normalized = DataValidator.normalize_string(alias_obj)
                if normalized:
                    aliases = [normalized]

            else:
                if self.logger:
                    self.logger.log_warning(
                        f"Invalid alias format: {type(alias_obj).__name__}",
                        {"entry_id": entry.id, "alias_data": str(alias_obj)[:100]},
                    )
                continue

            if not aliases:
                if self.logger:
                    self.logger.log_warning(
                        "Empty alias list after normalization",
                        {"entry_id": entry.id, "raw_data": str(alias_obj)[:100]},
                    )
                continue

            # Try to resolve person from existing aliases
            unresolved_aliases = aliases.copy()
            alias_fellows = []
            for alias in aliases:
                existing_aliases = (
                    self.session.query(Alias).filter_by(alias=alias).all()
                )

                if len(existing_aliases) == 1:
                    # Unique alias found - use it
                    alias_orms.append(existing_aliases[0])
                    person = existing_aliases[0].person
                    unresolved_aliases.remove(alias)

                elif len(existing_aliases) > 1:
                    # Ambiguous - multiple people have this alias
                    alias_fellows.append(alias)
                    unresolved_aliases.remove(alias)

            if unresolved_aliases or alias_fellows:
                if not person:
                    if name or full_name:
                        try:
                            # Use helper to get or create person
                            person = self.helpers.get_person(name, full_name)
                        except ValidationError as e:
                            if self.logger:
                                self.logger.log_warning(
                                    f"Could not resolve person for aliases: {e}",
                                    {
                                        "entry_id": entry.id,
                                        "entry_date": str(entry.date),
                                        "alias": [
                                            *unresolved_aliases,
                                            *alias_fellows,
                                        ],
                                        "name": name,
                                        "full_name": full_name,
                                    },
                                )
                            continue

                        if person is None:
                            if self.logger:
                                person_id = full_name if full_name else name
                                self.logger.log_warning(
                                    f"Person '{person_id}' not found for alias",
                                    {
                                        "entry_id": entry.id,
                                        "entry_date": str(entry.date),
                                        "alias": [
                                            *unresolved_aliases,
                                            *alias_fellows,
                                        ],
                                        "name": name,
                                        "full_name": full_name,
                                    },
                                )
                            continue
                    else:
                        # No person context provided
                        if self.logger:
                            self.logger.log_warning(
                                "Cannot resolve alias without person context",
                                {
                                    "entry_id": entry.id,
                                    "entry_date": str(entry.date),
                                    "alias": [*unresolved_aliases, *alias_fellows],
                                    "hint": "Provide 'name' or 'full_name' in alias dict",
                                },
                            )
                        continue

                if alias_fellows:
                    # Resolve ambiguous alias
                    resolved_fellows = []
                    for alias in alias_fellows:
                        existing_aliases = (
                            self.session.query(Alias)
                            .filter_by(alias=alias, person_id=person.id)
                            .all()
                        )

                        if len(existing_aliases) == 1:
                            # Unique alias found - use it
                            alias_orms.append(existing_aliases[0])
                            resolved_fellows.append(alias)

                    alias_fellows = [
                        a for a in alias_fellows if a not in resolved_fellows
                    ]
                    # This shouldn't happen due to Tables limitation, leave here anyway
                    if alias_fellows:
                        if self.logger:
                            self.logger.log_warning(
                                f"Ambiguous alias(es) '{alias_fellows}' match multiple people",
                                {
                                    "entry_id": entry.id,
                                    "entry_date": str(entry.date),
                                    "alias": alias_fellows,
                                },
                            )

                # Create new alias records for this person
                for alias in unresolved_aliases:
                    try:
                        alias_orm = self._get_or_create(
                            Alias,
                            lookup_fields={"alias": alias, "person_id": person.id},
                        )
                        alias_orms.append(alias_orm)

                        if self.logger:
                            self.logger.log_debug(
                                f"Created alias '{alias}' for {person.display_name}",
                                {
                                    "entry_id": entry.id,
                                    "person_id": person.id,
                                    "alias": alias,
                                },
                            )
                    except Exception as e:
                        if self.logger:
                            self.logger.log_error(
                                e,
                                {
                                    "operation": "create_alias",
                                    "entry_id": entry.id,
                                    "person_id": person.id,
                                    "alias": alias,
                                },
                            )
                        # Continue processing other aliases
                        continue

        # Link all collected aliases to entry
        if alias_orms:
            try:
                # Incremental mode: add new aliases
                for alias_orm in alias_orms:
                    resolved_alias = self._resolve_object(alias_orm, Alias)
                    if resolved_alias and resolved_alias not in entry.aliases_used:
                        entry.aliases_used.append(resolved_alias)
                self.session.flush()

                if self.logger:
                    self.logger.log_debug(
                        f"Linked {len(alias_orms)} aliases to entry",
                        {
                            "entry_id": entry.id,
                            "entry_date": str(entry.date),
                            "alias_count": len(alias_orms),
                        },
                    )
            except Exception as e:
                if self.logger:
                    self.logger.log_error(
                        e,
                        {
                            "operation": "link_aliases_to_entry",
                            "entry_id": entry.id,
                            "entry_date": str(entry.date),
                            "alias_count": len(alias_orms),
                        },
                    )
                raise
        elif self.logger:
            # No aliases were successfully processed
            self.logger.log_debug(
                "No alias linked to entry",
                {
                    "entry_id": entry.id,
                    "entry_date": str(entry.date),
                    "input_count": len(alias_data),
                },
            )

    def _process_mentioned_dates(
        self,
        entry: Entry,
        dates_data: List[Union[str, Dict[str, Any]]],
    ) -> None:
        """
        Process mentioned dates with optional context, locations, and people.

        Each date can have:
        - date: ISO format date string (required)
        - context: Optional text context
        - locations: List of location names (creates relationships)
        - people: List of person specs (creates relationships)

        Args:
            entry: Entry to attach dates to
            dates_data: List of date specifications
        """
        existing_date_ids = {d.id for d in entry.dates}

        for date_item in dates_data:
            mentioned_date = None

            if isinstance(date_item, str):
                # Simple date string
                date_obj = date.fromisoformat(date_item)
                mentioned_date = self._get_or_create(MentionedDate, {"date": date_obj})

            elif isinstance(date_item, dict) and "date" in date_item:
                # Date with context
                date_obj = date.fromisoformat(date_item["date"])
                context = date_item.get("context")

                mentioned_date = self._get_or_create(
                    MentionedDate, {"date": date_obj, "context": context}
                )

                if "locations" in date_item and date_item["locations"]:
                    self._update_mentioned_date_locations(
                        mentioned_date, date_item["locations"]
                    )

                if "people" in date_item and date_item["people"]:
                    self._update_mentioned_date_people(
                        mentioned_date, date_item["people"]
                    )
            else:
                continue

            if mentioned_date and mentioned_date.id not in existing_date_ids:
                entry.dates.append(mentioned_date)

    def _update_mentioned_date_locations(
        self,
        mentioned_date: MentionedDate,
        locations_data: List[str],
    ) -> None:
        """
        Update locations associated with a mentioned date.

        Auto-creates locations that don't exist yet, similar to how
        entry locations are handled.

        Args:
            mentioned_date: MentionedDate to update
            locations_data: List of location names
        """
        if mentioned_date.id is None:
            raise ValueError("MentionedDate must be persisted before linking locations")

        # Get existing location IDs to avoid duplicates
        existing_location_ids = {loc.id for loc in mentioned_date.locations}

        for loc_name in locations_data:
            # Normalize location name
            norm_name = DataValidator.normalize_string(loc_name)
            if not norm_name:
                continue

            # Handle possessive locations: check if this is a person's place
            # If location ends with "'s", check if base name is a known person
            # "#Alda's" → check if "Alda" is a person → "Alda's house"
            # "#McDonald's" → "McDonald" not a person → "McDonald's" (keep as-is)
            if norm_name.endswith("'s"):
                base_name = norm_name[:-2]  # Remove "'s"

                # Check if base_name matches a person in the database
                person = self._person_mgr.get(base_name)

                if person is not None:
                    # It's a person's place! Convert to "Name's house"
                    norm_name = f"{base_name}'s house"
                # else: keep as-is (it's a business/location name with apostrophe)

            # Get or create location (auto-create like we do for entries)
            # If no city is specified, use "Unknown" as default
            location = self._location_mgr.get_or_create_location(
                norm_name, city_name="Unknown"
            )

            # Link if not already linked
            if location.id not in existing_location_ids:
                mentioned_date.locations.append(location)

        if locations_data:
            self.session.flush()

    def _update_mentioned_date_people(
        self,
        mentioned_date: MentionedDate,
        people_data: List[Union[str, Dict[str, Any]]],
    ) -> None:
        """
        Update people associated with a mentioned date.

        Auto-creates people that don't exist yet, similar to how
        entry people are handled.

        Supports both simple names and full person specifications:
        - String: "John" (auto-creates if needed)
        - Dict: {"name": "John"} or {"full_name": "John Smith"}

        Args:
            mentioned_date: MentionedDate to update
            people_data: List of person specifications
        """
        if mentioned_date.id is None:
            raise ValueError("MentionedDate must be persisted before linking people")

        # Get existing person IDs to avoid duplicates
        existing_person_ids = {p.id for p in mentioned_date.people}

        for person_spec in people_data:
            person = None

            if isinstance(person_spec, str):
                # Simple name - use get_or_create
                norm_name = DataValidator.normalize_string(person_spec)
                if not norm_name:
                    continue

                person = self._person_mgr.get_or_create(norm_name)

            elif isinstance(person_spec, dict):
                # Dict with name or full_name - use get_or_create
                name = DataValidator.normalize_string(person_spec.get("name"))
                full_name = DataValidator.normalize_string(person_spec.get("full_name"))

                if name or full_name:
                    person = self._person_mgr.get_or_create(name or full_name, full_name)

            if person and person.id not in existing_person_ids:
                mentioned_date.people.append(person)

        if people_data:
            self.session.flush()

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

        existing_tags = {tag.tag for tag in entry.tags}

        # Add new tags
        for tag_name in norm_tags - existing_tags:
            tag_obj = self._get_or_create(Tag, {"tag": tag_name})
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

    def _process_manuscript(
        self,
        entry: Entry,
        manuscript_data: Dict[str, Any],
    ) -> None:
        """
        Create or update manuscript entry.

        Delegates to ManuscriptManager via helper.

        Args:
            entry: Entry to attach manuscript to
            manuscript_data: Manuscript metadata dict
        """
        # Use helper for manuscript processing
        self.helpers.create_or_update_manuscript_entry(entry, manuscript_data)
