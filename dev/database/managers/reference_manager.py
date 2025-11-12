#!/usr/bin/env python3
"""
reference_manager.py
--------------------
Manages Reference and ReferenceSource entities with their parent-child relationship.

References are citations or quotes from external sources mentioned in journal entries.
ReferenceSources are centralized source records (books, articles, films, etc.) that
can be referenced multiple times across entries.

Key Features:
    - CRUD operations for references and reference sources
    - Parent-child relationship (ReferenceSource → References)
    - Support for multiple source types and reference modes
    - Validation of content/description requirements
    - Optional source linking for references

Usage:
    ref_mgr = ReferenceManager(session, logger)

    # Create a reference source
    source = ref_mgr.create_source({
        "type": "book",
        "title": "The Great Gatsby",
        "author": "F. Scott Fitzgerald"
    })

    # Create a reference (with source)
    reference = ref_mgr.create_reference({
        "content": "So we beat on, boats against the current...",
        "mode": "direct",
        "entry": entry,
        "source": source
    })

    # Create a standalone reference (no source)
    ref2 = ref_mgr.create_reference({
        "description": "Quote about hope",
        "mode": "indirect",
        "entry": entry
    })
"""
from typing import Dict, List, Optional, Any, Union

from dev.core.validators import DataValidator
from dev.core.exceptions import ValidationError, DatabaseError
from dev.database.decorators import (
    handle_db_errors,
    log_database_operation,
    validate_metadata,
)
from dev.database.models import (
    Reference,
    ReferenceSource,
    ReferenceMode,
    ReferenceType,
    Entry,
)
from .base_manager import BaseManager


class ReferenceManager(BaseManager):
    """
    Manages Reference and ReferenceSource table operations.

    This manager handles both entities since they have a tight parent-child
    relationship: References can optionally link to ReferenceSources.
    """

    # =========================================================================
    # REFERENCE SOURCE OPERATIONS (Parent)
    # =========================================================================

    @handle_db_errors
    @log_database_operation("source_exists")
    def source_exists(self, title: str) -> bool:
        """
        Check if a reference source exists.

        Args:
            title: The source title to check

        Returns:
            True if source exists, False otherwise
        """
        normalized = DataValidator.normalize_string(title)
        if not normalized:
            return False

        return (
            self.session.query(ReferenceSource).filter_by(title=normalized).first()
            is not None
        )

    @handle_db_errors
    @log_database_operation("get_source")
    def get_source(
        self, title: str = None, source_id: int = None
    ) -> Optional[ReferenceSource]:
        """
        Retrieve a reference source by title or ID.

        Args:
            title: The source title
            source_id: The source ID

        Returns:
            ReferenceSource object if found, None otherwise
        """
        if source_id is not None:
            return self.session.get(ReferenceSource, source_id)

        if title is not None:
            normalized = DataValidator.normalize_string(title)
            if not normalized:
                return None
            return (
                self.session.query(ReferenceSource).filter_by(title=normalized).first()
            )

        return None

    @handle_db_errors
    @log_database_operation("get_all_sources")
    def get_all_sources(
        self, source_type: Optional[ReferenceType] = None
    ) -> List[ReferenceSource]:
        """
        Retrieve all reference sources, optionally filtered by type.

        Args:
            source_type: Optional filter by ReferenceType

        Returns:
            List of ReferenceSource objects, ordered by title
        """
        query = self.session.query(ReferenceSource)

        if source_type is not None:
            query = query.filter_by(type=source_type)

        return query.order_by(ReferenceSource.title).all()

    @handle_db_errors
    @log_database_operation("create_source")
    @validate_metadata(["type", "title"])
    def create_source(self, metadata: Dict[str, Any]) -> ReferenceSource:
        """
        Create a new reference source.

        Args:
            metadata: Dictionary with required keys:
                - type: ReferenceType enum or string value (required)
                - title: Source title (required, unique)
                Optional keys:
                - author: Author or creator name

        Returns:
            Created ReferenceSource object

        Raises:
            ValidationError: If type/title missing or invalid
            DatabaseError: If source with title already exists
        """
        # Normalize and validate type
        ref_type = DataValidator.normalize_enum(
            metadata.get("type"), ReferenceType, "type"
        )
        if ref_type is None:
            raise ValidationError(f"Invalid reference type: {metadata.get('type')}")

        # Normalize title
        title = DataValidator.normalize_string(metadata.get("title"))
        if not title:
            raise ValidationError(f"Invalid title: {metadata.get('title')}")

        # Check for existing
        existing = self.get_source(title=title)
        if existing:
            raise DatabaseError(f"Reference source already exists: {title}")

        # Normalize author
        author = DataValidator.normalize_string(metadata.get("author"))

        # Validate author requirement for certain types
        if ref_type.requires_author and not author:
            if self.logger:
                self.logger.log_warning(
                    f"Source type '{ref_type.value}' typically requires an author",
                    {"title": title},
                )

        # Create source
        source = ReferenceSource(type=ref_type, title=title, author=author)
        self.session.add(source)
        self.session.flush()

        if self.logger:
            self.logger.log_debug(
                f"Created reference source: {title}",
                {"source_id": source.id, "type": ref_type.value},
            )

        return source

    @handle_db_errors
    @log_database_operation("update_source")
    def update_source(
        self, source: ReferenceSource, metadata: Dict[str, Any]
    ) -> ReferenceSource:
        """
        Update an existing reference source.

        Args:
            source: ReferenceSource object to update
            metadata: Dictionary with optional keys:
                - type: ReferenceType enum or string
                - title: Source title
                - author: Author or creator name

        Returns:
            Updated ReferenceSource object
        """
        # Ensure exists
        db_source = self.session.get(ReferenceSource, source.id)
        if db_source is None:
            raise DatabaseError(f"ReferenceSource with id={source.id} not found")

        # Attach to session
        source = self.session.merge(db_source)

        # Update type
        if "type" in metadata:
            ref_type = DataValidator.normalize_enum(
                metadata["type"], ReferenceType, "type"
            )
            if ref_type:
                source.type = ref_type

        # Update title
        if "title" in metadata:
            title = DataValidator.normalize_string(metadata["title"])
            if title:
                source.title = title

        # Update author
        if "author" in metadata:
            source.author = DataValidator.normalize_string(metadata["author"])

        self.session.flush()

        return source

    @handle_db_errors
    @log_database_operation("delete_source")
    def delete_source(self, source: ReferenceSource) -> None:
        """
        Delete a reference source.

        Args:
            source: ReferenceSource object or ID to delete

        Notes:
            - This is a hard delete
            - All associated References are cascade deleted
            - Use with caution if references exist
        """
        if isinstance(source, int):
            source = self.session.get(ReferenceSource, source)
            if not source:
                raise DatabaseError(f"ReferenceSource not found with id: {source}")

        if self.logger:
            self.logger.log_debug(
                f"Deleting reference source: {source.title}",
                {
                    "source_id": source.id,
                    "reference_count": source.reference_count,
                },
            )

        self.session.delete(source)
        self.session.flush()

    @handle_db_errors
    @log_database_operation("get_or_create_source")
    def get_or_create_source(
        self,
        title: str,
        source_type: Union[ReferenceType, str],
        author: Optional[str] = None,
    ) -> ReferenceSource:
        """
        Get an existing reference source or create it if needed.

        Args:
            title: The source title
            source_type: ReferenceType enum or string value
            author: Optional author/creator name

        Returns:
            ReferenceSource object (existing or newly created)
        """
        normalized_title = DataValidator.normalize_string(title)
        if not normalized_title:
            raise ValidationError("Source title cannot be empty")

        # Try to get existing
        existing = self.get_source(title=normalized_title)
        if existing:
            return existing

        # Create new
        return self.create_source({
            "title": normalized_title,
            "type": source_type,
            "author": author,
        })

    # =========================================================================
    # REFERENCE OPERATIONS (Child)
    # =========================================================================

    @handle_db_errors
    @log_database_operation("get_reference")
    def get_reference(self, reference_id: int) -> Optional[Reference]:
        """
        Retrieve a reference by ID.

        Args:
            reference_id: The reference ID

        Returns:
            Reference object if found, None otherwise
        """
        return self.session.get(Reference, reference_id)

    @handle_db_errors
    @log_database_operation("get_all_references")
    def get_all_references(
        self, mode: Optional[ReferenceMode] = None
    ) -> List[Reference]:
        """
        Retrieve all references, optionally filtered by mode.

        Args:
            mode: Optional filter by ReferenceMode

        Returns:
            List of Reference objects
        """
        query = self.session.query(Reference)

        if mode is not None:
            query = query.filter_by(mode=mode)

        return query.all()

    @handle_db_errors
    @log_database_operation("create_reference")
    def create_reference(self, metadata: Dict[str, Any]) -> Reference:
        """
        Create a new reference for an entry.

        Args:
            metadata: Dictionary with keys:
                Required (at least one):
                - content: The quoted/referenced content
                - description: Brief description of reference
                Required:
                - entry: Entry object or entry ID
                Optional:
                - mode: ReferenceMode enum or string (default: "direct")
                - speaker: Who said/wrote this
                - source: ReferenceSource object or source ID

        Returns:
            Created Reference object

        Raises:
            ValidationError: If content AND description both missing,
                           or if entry is missing/invalid
        """
        # Validate content or description requirement
        content = DataValidator.normalize_string(metadata.get("content"))
        description = DataValidator.normalize_string(metadata.get("description"))

        if not content and not description:
            raise ValidationError(
                "Reference must have either 'content' or 'description'"
            )

        # Resolve entry
        entry_spec = metadata.get("entry")
        if entry_spec is None:
            raise ValidationError("Reference must be linked to an entry")

        if isinstance(entry_spec, Entry):
            entry = entry_spec
        elif isinstance(entry_spec, int):
            entry = self.session.get(Entry, entry_spec)
            if not entry:
                raise ValidationError(f"Entry not found with id: {entry_spec}")
        else:
            raise ValidationError(f"Invalid entry specification: {entry_spec}")

        # Normalize mode
        mode = DataValidator.normalize_enum(
            metadata.get("mode", "direct"), ReferenceMode, "mode"
        )
        if mode is None:
            mode = ReferenceMode.DIRECT

        # Resolve source (optional)
        source = None
        source_spec = metadata.get("source")
        if source_spec is not None:
            if isinstance(source_spec, ReferenceSource):
                source = source_spec
            elif isinstance(source_spec, int):
                source = self.get_source(source_id=source_spec)
                if not source:
                    if self.logger:
                        self.logger.log_warning(
                            f"Source not found with id: {source_spec}",
                            {"reference_content": content or description},
                        )
            elif isinstance(source_spec, dict):
                # Create source from dict
                source = self.create_source(source_spec)

        # Create reference
        reference = Reference(
            content=content,
            description=description,
            speaker=DataValidator.normalize_string(metadata.get("speaker")),
            mode=mode,
            entry=entry,
            source=source,
        )
        self.session.add(reference)
        self.session.flush()

        if self.logger:
            self.logger.log_debug(
                f"Created reference for entry {entry.date}",
                {
                    "reference_id": reference.id,
                    "mode": mode.value,
                    "has_source": source is not None,
                },
            )

        return reference

    @handle_db_errors
    @log_database_operation("update_reference")
    def update_reference(
        self, reference: Reference, metadata: Dict[str, Any]
    ) -> Reference:
        """
        Update an existing reference.

        Args:
            reference: Reference object to update
            metadata: Dictionary with optional keys:
                - content: Updated content
                - description: Updated description
                - speaker: Updated speaker
                - mode: Updated ReferenceMode
                - entry: Updated Entry object or ID
                - source: Updated ReferenceSource object or ID

        Returns:
            Updated Reference object

        Notes:
            - Must maintain content OR description requirement
        """
        # Ensure exists
        db_ref = self.session.get(Reference, reference.id)
        if db_ref is None:
            raise DatabaseError(f"Reference with id={reference.id} not found")

        # Attach to session
        reference = self.session.merge(db_ref)

        # Update content/description (validate at least one remains)
        if "content" in metadata:
            reference.content = DataValidator.normalize_string(metadata["content"])
        if "description" in metadata:
            reference.description = DataValidator.normalize_string(
                metadata["description"]
            )

        # Validate content or description requirement
        if not reference.content and not reference.description:
            raise ValidationError(
                "Reference must have either 'content' or 'description'"
            )

        # Update speaker
        if "speaker" in metadata:
            reference.speaker = DataValidator.normalize_string(metadata["speaker"])

        # Update mode
        if "mode" in metadata:
            mode = DataValidator.normalize_enum(metadata["mode"], ReferenceMode, "mode")
            if mode:
                reference.mode = mode

        # Update entry
        if "entry" in metadata:
            entry_spec = metadata["entry"]
            if isinstance(entry_spec, Entry):
                reference.entry = entry_spec
            elif isinstance(entry_spec, int):
                entry = self.session.get(Entry, entry_spec)
                if entry:
                    reference.entry = entry

        # Update source
        if "source" in metadata:
            source_spec = metadata["source"]
            if source_spec is None:
                reference.source = None
            elif isinstance(source_spec, ReferenceSource):
                reference.source = source_spec
            elif isinstance(source_spec, int):
                source = self.get_source(source_id=source_spec)
                if source:
                    reference.source = source

        self.session.flush()

        return reference

    @handle_db_errors
    @log_database_operation("delete_reference")
    def delete_reference(self, reference: Reference) -> None:
        """
        Delete a reference.

        Args:
            reference: Reference object or ID to delete

        Notes:
            - This is a hard delete
            - Does not affect the ReferenceSource
        """
        if isinstance(reference, int):
            reference = self.session.get(Reference, reference)
            if not reference:
                raise DatabaseError(f"Reference not found with id: {reference}")

        if self.logger:
            self.logger.log_debug(
                f"Deleting reference",
                {"reference_id": reference.id, "entry_id": reference.entry_id},
            )

        self.session.delete(reference)
        self.session.flush()

    # =========================================================================
    # QUERY METHODS
    # =========================================================================

    @handle_db_errors
    @log_database_operation("get_references_for_entry")
    def get_references_for_entry(self, entry: Entry) -> List[Reference]:
        """
        Get all references for an entry.

        Args:
            entry: Entry object

        Returns:
            List of Reference objects
        """
        return entry.references

    @handle_db_errors
    @log_database_operation("get_references_for_source")
    def get_references_for_source(
        self, source: ReferenceSource
    ) -> List[Reference]:
        """
        Get all references from a specific source.

        Args:
            source: ReferenceSource object

        Returns:
            List of Reference objects
        """
        return source.references

    @handle_db_errors
    @log_database_operation("get_sources_by_type")
    def get_sources_by_type(
        self, source_type: Union[ReferenceType, str]
    ) -> List[ReferenceSource]:
        """
        Get all sources of a specific type.

        Args:
            source_type: ReferenceType enum or string value

        Returns:
            List of ReferenceSource objects, ordered by title
        """
        # Normalize type
        if isinstance(source_type, str):
            source_type = DataValidator.normalize_enum(
                source_type, ReferenceType, "source_type"
            )

        if source_type is None:
            return []

        return self.get_all_sources(source_type=source_type)
