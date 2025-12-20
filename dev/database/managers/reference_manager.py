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
    source = ref_mgr.create({
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
# --- Annotations ---
from typing import Any, Dict, List, Optional, Union, cast

# --- Standard library imports ---

# --- Third party imports ---
from sqlalchemy.orm import Session

# --- Local imports ---
from dev.core.exceptions import DatabaseError, ValidationError
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.core.validators import DataValidator
from dev.database.decorators import DatabaseOperation
from dev.database.models import (
    Entry,
    Reference,
    ReferenceMode,
    ReferenceSource,
    ReferenceType,
)

from .entity_manager import EntityManager, EntityManagerConfig

# Configuration for ReferenceSource entity
SOURCE_CONFIG = EntityManagerConfig(
    model_class=ReferenceSource,
    name_field="title",
    display_name="reference source",
    supports_soft_delete=False,
    order_by="title",
    scalar_fields=[
        ("title", DataValidator.normalize_string),
        ("author", DataValidator.normalize_string, True),
    ],
    relationships=[],
)


class ReferenceManager(EntityManager):
    """
    Manages Reference and ReferenceSource table operations.

    Inherits EntityManager for ReferenceSource CRUD and adds
    Reference-specific operations for the child entity.
    """

    def __init__(
        self,
        session: Session,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize the reference manager.

        Args:
            session: SQLAlchemy session
            logger: Optional logger for operation tracking
        """
        super().__init__(session, logger, SOURCE_CONFIG)

    # =========================================================================
    # REFERENCE SOURCE OPERATIONS (via EntityManager)
    # =========================================================================

    # Inherited from EntityManager:
    # - exists(name, entity_id, include_deleted) -> bool
    # - get(name, entity_id, include_deleted) -> Optional[ReferenceSource]
    # - get_all(include_deleted) -> List[ReferenceSource]
    # - get_or_create(name, extra_metadata) -> ReferenceSource
    # - create(metadata) -> ReferenceSource
    # - update(entity, metadata) -> ReferenceSource
    # - delete(entity) -> None

    def _validate_create(self, metadata: Dict[str, Any]) -> None:
        """Validate ReferenceSource creation metadata."""
        # Type is required for sources
        ref_type = DataValidator.normalize_enum(
            metadata.get("type"), ReferenceType, "type"
        )
        if ref_type is None:
            raise ValidationError(f"Invalid reference type: {metadata.get('type')}")

    def _create_entity(self, metadata: Dict[str, Any], name: str) -> ReferenceSource:
        """Create ReferenceSource with type validation."""
        ref_type = DataValidator.normalize_enum(
            metadata.get("type"), ReferenceType, "type"
        )
        author = DataValidator.normalize_string(metadata.get("author"))

        # Warn if author missing for types that require it
        if cast(ReferenceType, ref_type).requires_author and not author:
            safe_logger(self.logger).log_warning(
                f"Source type '{ref_type.value}' typically requires an author",
                {"title": name},
            )

        return ReferenceSource(type=ref_type, title=name, author=author)

    # Convenience aliases for backward compatibility
    def source_exists(self, title: str) -> bool:
        """Check if a reference source exists."""
        return self.exists(name=title)

    def get_source(
        self, title: Optional[str] = None, source_id: Optional[int] = None
    ) -> Optional[ReferenceSource]:
        """Retrieve a reference source by title or ID."""
        return self.get(name=title, entity_id=source_id)

    def get_all_sources(
        self, source_type: Optional[ReferenceType] = None
    ) -> List[ReferenceSource]:
        """Retrieve all reference sources, optionally filtered by type."""
        if source_type is not None:
            return self._get_all(ReferenceSource, order_by="title", type=source_type)
        return self.get_all()

    def create_source(self, metadata: Dict[str, Any]) -> ReferenceSource:
        """Create a new reference source."""
        # Ensure type is provided
        if "type" not in metadata:
            raise ValidationError("Reference source requires 'type'")
        return self.create(metadata)

    def update_source(
        self, source: ReferenceSource, metadata: Dict[str, Any]
    ) -> ReferenceSource:
        """Update an existing reference source."""
        # Handle type update specially (enum)
        if "type" in metadata:
            ref_type = DataValidator.normalize_enum(
                metadata["type"], ReferenceType, "type"
            )
            if ref_type:
                source.type = ref_type  # type: ignore[misc]
        return self.update(source, metadata)

    def delete_source(self, source: ReferenceSource) -> None:
        """Delete a reference source."""
        self.delete(source)

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
        with DatabaseOperation(self.logger, "get_or_create_source"):
            return self.get_or_create(
                title,
                extra_metadata={"type": source_type, "author": author},
            )

    # =========================================================================
    # REFERENCE OPERATIONS (Child entity)
    # =========================================================================

    def get_reference(self, reference_id: int) -> Optional[Reference]:
        """
        Retrieve a reference by ID.

        Args:
            reference_id: The reference ID

        Returns:
            Reference object if found, None otherwise
        """
        with DatabaseOperation(self.logger, "get_reference"):
            return self._get_by_id(Reference, reference_id)

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
        with DatabaseOperation(self.logger, "get_all_references"):
            if mode is not None:
                return self._get_all(Reference, mode=mode)
            return self._get_all(Reference)

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
        with DatabaseOperation(self.logger, "create_reference"):
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
                        safe_logger(self.logger).log_warning(
                            f"Source not found with id: {source_spec}",
                            {"reference_content": content or description},
                        )
                elif isinstance(source_spec, dict):
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

            safe_logger(self.logger).log_debug(
                f"Created reference for entry {entry.date}",
                {
                    "reference_id": reference.id,
                    "mode": mode.value,
                    "has_source": source is not None,
                },
            )

            return reference

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
        """
        with DatabaseOperation(self.logger, "update_reference"):
            db_ref = self.session.get(Reference, reference.id)
            if db_ref is None:
                raise DatabaseError(f"Reference with id={reference.id} not found")

            reference = self.session.merge(db_ref)

            # Update scalar fields
            self._update_scalar_fields(
                reference,
                metadata,
                [
                    ("content", DataValidator.normalize_string, True),
                    ("description", DataValidator.normalize_string, True),
                    ("speaker", DataValidator.normalize_string, True),
                ],
            )

            # Validate content or description requirement
            if not reference.content and not reference.description:
                raise ValidationError(
                    "Reference must have either 'content' or 'description'"
                )

            # Update mode
            if "mode" in metadata:
                mode = DataValidator.normalize_enum(metadata["mode"], ReferenceMode, "mode")
                if mode:
                    reference.mode = mode  # type: ignore[misc]

            # Update entry
            if "entry" in metadata:
                entry = self._resolve_parent(
                    metadata["entry"],
                    Entry,
                    lambda **kw: self.session.get(Entry, kw.get("id")),
                    None,
                    "id",
                )
                if entry:
                    reference.entry = entry

            # Update source (allows None to clear)
            if "source" in metadata:
                if metadata["source"] is None:
                    reference.source = None
                else:
                    source = self._resolve_parent(
                        metadata["source"],
                        ReferenceSource,
                        lambda **kw: self.get_source(source_id=kw.get("id")),
                        None,
                        "id",
                    )
                    if source:
                        reference.source = source

            self.session.flush()
            return reference

    def delete_reference(self, reference: Reference) -> None:
        """
        Delete a reference.

        Args:
            reference: Reference object or ID to delete
        """
        with DatabaseOperation(self.logger, "delete_reference"):
            if isinstance(reference, int):
                fetched_ref = self.session.get(Reference, reference)
                if not fetched_ref:
                    raise DatabaseError(f"Reference not found with id: {reference}")
                reference = fetched_ref

            safe_logger(self.logger).log_debug(
                "Deleting reference",
                {"reference_id": reference.id, "entry_id": reference.entry_id},
            )

            self.session.delete(reference)
            self.session.flush()

    # =========================================================================
    # QUERY METHODS
    # =========================================================================

    def get_references_for_entry(self, entry: Entry) -> List[Reference]:
        """Get all references for an entry."""
        with DatabaseOperation(self.logger, "get_references_for_entry"):
            return entry.references

    def get_references_for_source(self, source: ReferenceSource) -> List[Reference]:
        """Get all references from a specific source."""
        with DatabaseOperation(self.logger, "get_references_for_source"):
            return source.references

    def get_sources_by_type(
        self, source_type: Union[ReferenceType, str]
    ) -> List[ReferenceSource]:
        """Get all sources of a specific type."""
        with DatabaseOperation(self.logger, "get_sources_by_type"):
            normalized_type: Union[ReferenceType, str, None] = source_type
            if isinstance(source_type, str):
                normalized_type = cast(
                    Optional[ReferenceType],
                    DataValidator.normalize_enum(source_type, ReferenceType, "source_type"),
                )

            if normalized_type is None:
                return []

            return self._get_all(
                ReferenceSource, order_by="title", type=normalized_type
            )
