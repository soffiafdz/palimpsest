#!/usr/bin/env python3
"""
simple_manager.py
-----------------
Config-driven manager for simple entities: Tag, Theme, Arc, Event.

This module provides a generic manager for simple lookup entities
that share common patterns: get_or_create, link to entries, etc.

Each entity type is defined by a SimpleManagerConfig that specifies:
- The model class and primary lookup field
- Input normalization
- Soft delete support
- Relationship configuration

Usage:
    # Get pre-configured managers
    tag_mgr = SimpleManager.for_tags(session, logger)
    theme_mgr = SimpleManager.for_themes(session, logger)
    arc_mgr = SimpleManager.for_arcs(session, logger)
    event_mgr = SimpleManager.for_events(session, logger)

    # Common operations
    tag = tag_mgr.get_or_create("python")
    theme = theme_mgr.get_or_create("identity")
    arc = arc_mgr.get_or_create("The Long Wanting")
    event = event_mgr.get_or_create("Birthday Party")

    # Relationships
    tag_mgr.link_to_entry(tag, entry)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Type, Union

from sqlalchemy.orm import Session

from dev.core.exceptions import DatabaseError, ValidationError
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.core.validators import DataValidator
from dev.database.decorators import DatabaseOperation
from dev.database.models import Arc, Entry, Event, Scene, Tag, Theme
from .base_manager import BaseManager


@dataclass
class RelationshipConfig:
    """Configuration for a many-to-many relationship."""

    attr_name: str  # Attribute name on model (e.g., 'entries')
    model_class: Type  # Related model class (e.g., Entry)


@dataclass
class SimpleManagerConfig:
    """
    Configuration for a simple entity manager.

    Attributes:
        model_class: SQLAlchemy model class
        name_field: Primary lookup field name (e.g., 'name')
        display_name: Human-readable name for error messages
        normalizer: Function to normalize input values
        supports_soft_delete: Whether entity supports soft delete
        extra_fields: Additional fields for create/update
        relationships: List of relationship configurations
    """

    model_class: Type
    name_field: str
    display_name: str
    normalizer: Callable[[Any], Any]
    supports_soft_delete: bool = False
    extra_fields: List[str] = field(default_factory=list)
    relationships: List[RelationshipConfig] = field(default_factory=list)


def _normalize_string(value: Any) -> Optional[str]:
    """Normalize a string value."""
    return DataValidator.normalize_string(value)


# Pre-defined configurations for each entity type
TAG_CONFIG = SimpleManagerConfig(
    model_class=Tag,
    name_field="name",
    display_name="tag",
    normalizer=_normalize_string,
    supports_soft_delete=False,
    extra_fields=[],
    relationships=[RelationshipConfig("entries", Entry)],
)

THEME_CONFIG = SimpleManagerConfig(
    model_class=Theme,
    name_field="name",
    display_name="theme",
    normalizer=_normalize_string,
    supports_soft_delete=False,
    extra_fields=[],
    relationships=[RelationshipConfig("entries", Entry)],
)

ARC_CONFIG = SimpleManagerConfig(
    model_class=Arc,
    name_field="name",
    display_name="arc",
    normalizer=_normalize_string,
    supports_soft_delete=False,
    extra_fields=["description"],
    relationships=[RelationshipConfig("entries", Entry)],
)

EVENT_CONFIG = SimpleManagerConfig(
    model_class=Event,
    name_field="name",
    display_name="event",
    normalizer=_normalize_string,
    supports_soft_delete=False,
    extra_fields=[],
    relationships=[
        RelationshipConfig("entries", Entry),
        RelationshipConfig("scenes", Scene),
    ],
)


class SimpleManager(BaseManager):
    """
    Generic manager for simple entities (Tag, Theme, Arc).

    Uses configuration to provide consistent CRUD operations and relationship
    management across different entity types.
    """

    def __init__(
        self,
        session: Session,
        logger: Optional[PalimpsestLogger],
        config: SimpleManagerConfig,
    ):
        """
        Initialize the simple manager.

        Args:
            session: SQLAlchemy session
            logger: Optional logger for operation tracking
            config: Entity-specific configuration
        """
        super().__init__(session, logger)
        self.config = config

    # -------------------------------------------------------------------------
    # Factory Methods
    # -------------------------------------------------------------------------

    @classmethod
    def for_tags(
        cls, session: Session, logger: Optional[PalimpsestLogger] = None
    ) -> "SimpleManager":
        """Create a manager for Tag entities."""
        return cls(session, logger, TAG_CONFIG)

    @classmethod
    def for_themes(
        cls, session: Session, logger: Optional[PalimpsestLogger] = None
    ) -> "SimpleManager":
        """Create a manager for Theme entities."""
        return cls(session, logger, THEME_CONFIG)

    @classmethod
    def for_arcs(
        cls, session: Session, logger: Optional[PalimpsestLogger] = None
    ) -> "SimpleManager":
        """Create a manager for Arc entities."""
        return cls(session, logger, ARC_CONFIG)

    @classmethod
    def for_events(
        cls, session: Session, logger: Optional[PalimpsestLogger] = None
    ) -> "SimpleManager":
        """Create a manager for Event entities."""
        return cls(session, logger, EVENT_CONFIG)

    # -------------------------------------------------------------------------
    # Core CRUD Operations
    # -------------------------------------------------------------------------

    def exists(self, value: Any, include_deleted: bool = False) -> bool:
        """
        Check if an entity exists.

        Args:
            value: The lookup value (e.g., tag name)
            include_deleted: Include soft-deleted entities (if supported)

        Returns:
            True if entity exists, False otherwise
        """
        with DatabaseOperation(self.logger, "exists"):
            try:
                normalized = self.config.normalizer(value)
            except (ValidationError, TypeError):
                return False

            if normalized is None:
                return False

            query = self.session.query(self.config.model_class).filter_by(
                **{self.config.name_field: normalized}
            )

            if self.config.supports_soft_delete and not include_deleted:
                query = query.filter(self.config.model_class.deleted_at.is_(None))

            return query.first() is not None

    def get(
        self,
        value: Optional[Any] = None,
        entity_id: Optional[int] = None,
        include_deleted: bool = False,
    ) -> Optional[Any]:
        """
        Retrieve an entity by value or ID.

        Args:
            value: The lookup value (e.g., tag name)
            entity_id: The entity ID
            include_deleted: Include soft-deleted entities (if supported)

        Returns:
            Entity object if found, None otherwise

        Notes:
            If both value and ID provided, ID takes precedence.
        """
        with DatabaseOperation(self.logger, "get"):
            if entity_id is not None:
                entity = self.session.get(self.config.model_class, entity_id)
                if entity:
                    if self.config.supports_soft_delete:
                        if include_deleted or not entity.deleted_at:
                            return entity
                        return None
                    return entity
                return None

            if value is not None:
                try:
                    normalized = self.config.normalizer(value)
                except (ValidationError, TypeError):
                    return None

                if normalized is None:
                    return None

                query = self.session.query(self.config.model_class).filter_by(
                    **{self.config.name_field: normalized}
                )

                if self.config.supports_soft_delete and not include_deleted:
                    query = query.filter(self.config.model_class.deleted_at.is_(None))

                return query.first()

            return None

    def get_by_id(self, entity_id: int) -> Optional[Any]:
        """Retrieve an entity by ID."""
        with DatabaseOperation(self.logger, "get_by_id"):
            return self.session.get(self.config.model_class, entity_id)

    def get_all(
        self,
        include_deleted: bool = False,
        order_by: Optional[str] = None,
    ) -> List[Any]:
        """
        Retrieve all entities.

        Args:
            include_deleted: Include soft-deleted entities (if supported)
            order_by: Field to order by (defaults to name_field)

        Returns:
            List of entity objects
        """
        with DatabaseOperation(self.logger, "get_all"):
            query = self.session.query(self.config.model_class)

            if self.config.supports_soft_delete and not include_deleted:
                query = query.filter(self.config.model_class.deleted_at.is_(None))

            # Determine ordering
            if order_by == "usage_count":
                # Special case: order by computed property (done in Python)
                entities = query.all()
                return sorted(
                    entities,
                    key=lambda e: len(e.entries) if hasattr(e, "entries") else 0,
                    reverse=True,
                )

            # Default ordering by name_field
            order_field = order_by or self.config.name_field
            if hasattr(self.config.model_class, order_field):
                attr = getattr(self.config.model_class, order_field)
                # Only use for ordering if it's a column, not a property
                if hasattr(attr, '__clause_element__') or hasattr(attr, 'property'):
                    query = query.order_by(attr)

            return query.all()

    def create(self, metadata: Dict[str, Any]) -> Any:
        """
        Create a new entity.

        Args:
            metadata: Dictionary with:
                - [name_field]: Required lookup value
                - [extra_fields]: Optional additional fields
                - [relationships]: Optional relationship lists

        Returns:
            Created entity object

        Raises:
            ValidationError: If required field is missing or invalid
            DatabaseError: If entity already exists
        """
        with DatabaseOperation(self.logger, "create"):
            # Validate and normalize the primary field
            raw_value = metadata.get(self.config.name_field)
            if raw_value is None:
                raise ValidationError(
                    f"{self.config.display_name.capitalize()} "
                    f"{self.config.name_field} is required"
                )

            try:
                normalized = self.config.normalizer(raw_value)
            except ValidationError:
                raise
            except Exception as e:
                raise ValidationError(
                    f"Invalid {self.config.name_field}: {raw_value}"
                ) from e

            if normalized is None:
                raise ValidationError(
                    f"{self.config.display_name.capitalize()} cannot be empty"
                )

            # Check for existing (including deleted if soft delete supported)
            existing = self.get(value=normalized, include_deleted=True)
            if existing:
                if self.config.supports_soft_delete and existing.deleted_at:
                    raise DatabaseError(
                        f"{self.config.display_name.capitalize()} '{normalized}' exists "
                        f"but is deleted. Restore it instead of creating new."
                    )
                raise DatabaseError(
                    f"{self.config.display_name.capitalize()} already exists: {normalized}"
                )

            # Build entity fields
            fields = {self.config.name_field: normalized}
            for extra_field in self.config.extra_fields:
                if extra_field in metadata:
                    value = metadata[extra_field]
                    if isinstance(value, str):
                        value = DataValidator.normalize_string(value)
                    fields[extra_field] = value

            # Create entity
            entity = self.config.model_class(**fields)
            self.session.add(entity)
            self.session.flush()

            safe_logger(self.logger).log_debug(
                f"Created {self.config.display_name}: {normalized}",
                {"id": entity.id},
            )

            # Update relationships
            self._update_entity_relationships(entity, metadata, incremental=False)

            return entity

    def get_or_create(self, value: Any, **extra_fields) -> Any:
        """
        Get an existing entity or create it if it doesn't exist.

        Args:
            value: The lookup value
            **extra_fields: Additional fields for creation

        Returns:
            Entity object (existing or newly created)

        Raises:
            ValidationError: If value is invalid
        """
        with DatabaseOperation(self.logger, "get_or_create"):
            try:
                normalized = self.config.normalizer(value)
            except ValidationError:
                raise
            except Exception as e:
                raise ValidationError(f"Invalid {self.config.name_field}: {value}") from e

            if normalized is None:
                raise ValidationError(
                    f"{self.config.display_name.capitalize()} cannot be empty"
                )

            # Try to get existing
            entity = self.get(value=normalized)
            if entity:
                return entity

            # Create new
            metadata = {self.config.name_field: normalized, **extra_fields}
            return self.create(metadata)

    def update(self, entity: Any, metadata: Dict[str, Any]) -> Any:
        """
        Update an existing entity.

        Args:
            entity: Entity object to update
            metadata: Dictionary with fields to update

        Returns:
            Updated entity object

        Raises:
            DatabaseError: If entity not found or is deleted
        """
        with DatabaseOperation(self.logger, "update"):
            # Ensure entity exists
            db_entity = self.session.get(self.config.model_class, entity.id)
            if db_entity is None:
                raise DatabaseError(
                    f"{self.config.display_name.capitalize()} with id={entity.id} not found"
                )

            if self.config.supports_soft_delete and db_entity.deleted_at:
                raise DatabaseError(
                    f"Cannot update deleted {self.config.display_name}: "
                    f"{getattr(db_entity, self.config.name_field)}"
                )

            # Attach to session
            entity = self.session.merge(db_entity)

            # Update name field if provided
            name_field = self.config.name_field
            if name_field in metadata:
                value = metadata[name_field]
                if isinstance(value, str):
                    value = DataValidator.normalize_string(value)
                if value is not None:
                    setattr(entity, name_field, value)

            # Update extra fields
            for field_name in self.config.extra_fields:
                if field_name in metadata:
                    value = metadata[field_name]
                    if isinstance(value, str):
                        value = DataValidator.normalize_string(value)
                    setattr(entity, field_name, value)

            # Update relationships
            self._update_entity_relationships(entity, metadata, incremental=True)

            return entity

    def delete(
        self,
        entity: Union[Any, int],
        deleted_by: Optional[str] = None,
        reason: Optional[str] = None,
        hard_delete: bool = False,
    ) -> None:
        """
        Delete an entity.

        Args:
            entity: Entity object or ID to delete
            deleted_by: Who is deleting (for soft delete audit)
            reason: Why deleted (for soft delete audit)
            hard_delete: Force hard delete even if soft delete supported

        Notes:
            - Entities without soft delete support always hard delete
            - Cascade deletes remove all relationships
        """
        with DatabaseOperation(self.logger, "delete"):
            # Resolve entity ID to object if needed
            resolved_entity: Any
            if isinstance(entity, int):
                found = self.get(entity_id=entity, include_deleted=True)
                if not found:
                    raise DatabaseError(
                        f"{self.config.display_name.capitalize()} not found with id: {entity}"
                    )
                resolved_entity = found
            else:
                resolved_entity = entity

            entity_name = getattr(resolved_entity, self.config.name_field)

            if self.config.supports_soft_delete and not hard_delete:
                # Soft delete
                safe_logger(self.logger).log_debug(
                    f"Soft deleting {self.config.display_name}: {entity_name}",
                    {"id": resolved_entity.id, "deleted_by": deleted_by, "reason": reason},
                )
                resolved_entity.deleted_at = datetime.now(timezone.utc)
                resolved_entity.deleted_by = deleted_by
                resolved_entity.deletion_reason = reason
            else:
                # Hard delete
                safe_logger(self.logger).log_debug(
                    f"Hard deleting {self.config.display_name}: {entity_name}",
                    {"id": resolved_entity.id},
                )
                self.session.delete(resolved_entity)

            self.session.flush()

    def restore(self, entity: Union[Any, int]) -> Any:
        """
        Restore a soft-deleted entity.

        Args:
            entity: Entity object or ID to restore

        Returns:
            Restored entity object

        Raises:
            DatabaseError: If entity not found, not deleted, or doesn't support soft delete
        """
        with DatabaseOperation(self.logger, "restore"):
            if not self.config.supports_soft_delete:
                raise DatabaseError(
                    f"{self.config.display_name.capitalize()} does not support soft delete"
                )

            # Resolve entity ID to object if needed
            resolved_entity: Any
            if isinstance(entity, int):
                found = self.get(entity_id=entity, include_deleted=True)
                if not found:
                    raise DatabaseError(
                        f"{self.config.display_name.capitalize()} not found with id: {entity}"
                    )
                resolved_entity = found
            else:
                resolved_entity = entity

            if not resolved_entity.deleted_at:
                entity_name = getattr(resolved_entity, self.config.name_field)
                raise DatabaseError(
                    f"{self.config.display_name.capitalize()} is not deleted: {entity_name}"
                )

            resolved_entity.deleted_at = None
            resolved_entity.deleted_by = None
            resolved_entity.deletion_reason = None

            self.session.flush()

            entity_name = getattr(resolved_entity, self.config.name_field)
            safe_logger(self.logger).log_debug(
                f"Restored {self.config.display_name}: {entity_name}",
                {"id": resolved_entity.id},
            )

            return resolved_entity

    # -------------------------------------------------------------------------
    # Relationship Management
    # -------------------------------------------------------------------------

    def _update_entity_relationships(
        self,
        entity: Any,
        metadata: Dict[str, Any],
        incremental: bool = True,
    ) -> None:
        """
        Update relationships for an entity.

        Args:
            entity: Entity to update
            metadata: Metadata with relationship keys
            incremental: Add incrementally (True) or replace all (False)
        """
        for rel_config in self.config.relationships:
            attr_name = rel_config.attr_name
            if attr_name not in metadata:
                continue

            items = metadata[attr_name]
            remove_items = metadata.get(f"remove_{attr_name}", [])
            collection = getattr(entity, attr_name)

            if not incremental:
                # Replacement mode: clear and add all
                collection.clear()

            # Add items
            for item in items:
                resolved = self._resolve_object(item, rel_config.model_class)
                if resolved and resolved not in collection:
                    collection.append(resolved)

            if incremental:
                # Remove specified items
                for item in remove_items:
                    resolved = self._resolve_object(item, rel_config.model_class)
                    if resolved and resolved in collection:
                        collection.remove(resolved)

            self.session.flush()

    def link_to_entry(
        self, entity_or_entry: Any, entry_or_name: Any = None
    ) -> Optional[Any]:
        """
        Link an entity to an entry.

        For Tag entities (backward compatibility):
            link_to_entry(entry, "tag_name") -> Tag
            Gets or creates the tag, then links to entry.

        For other entities:
            link_to_entry(entity, entry) -> None
        """
        with DatabaseOperation(self.logger, "link_to_entry"):
            # Tag-specific: link_to_entry(entry, tag_name)
            if self.config.model_class == Tag and isinstance(entry_or_name, str):
                entry = entity_or_entry
                tag_name = entry_or_name

                if entry.id is None:
                    raise ValueError("Entry must be persisted before linking tags")

                tag = self.get_or_create(tag_name)
                if tag not in entry.tags:
                    entry.tags.append(tag)
                    self.session.flush()

                    safe_logger(self.logger).log_debug(
                        "Linked tag to entry",
                        {"tag": tag.name, "entry_date": entry.date},
                    )
                return tag

            # Generic: link_to_entry(entity, entry)
            entity = entity_or_entry
            entry = entry_or_name
            self._link(entity, entry, "entries")
            return None

    def unlink_from_entry(
        self, entity_or_entry: Any, entry_or_name: Any = None
    ) -> bool:
        """
        Unlink an entity from an entry.

        For Tag entities (backward compatibility):
            unlink_from_entry(entry, "tag_name") -> bool

        For other entities:
            unlink_from_entry(entity, entry) -> bool
        """
        with DatabaseOperation(self.logger, "unlink_from_entry"):
            # Tag-specific: unlink_from_entry(entry, tag_name)
            if self.config.model_class == Tag and isinstance(entry_or_name, str):
                entry = entity_or_entry
                tag_name = entry_or_name

                if entry.id is None:
                    raise ValueError("Entry must be persisted before unlinking tags")

                tag = self.get(value=tag_name)
                if not tag or tag not in entry.tags:
                    return False

                entry.tags.remove(tag)
                self.session.flush()

                safe_logger(self.logger).log_debug(
                    "Unlinked tag from entry",
                    {"tag": tag.name, "entry_date": entry.date},
                )
                return True

            # Generic: unlink_from_entry(entity, entry)
            entity = entity_or_entry
            entry = entry_or_name
            return self._unlink(entity, entry, "entries")

    def update_entry_tags(
        self,
        entry: Entry,
        tags: List[str],
        incremental: bool = True,
    ) -> None:
        """
        Update all tags for an entry (Tag-specific method).

        Args:
            entry: Entry object whose tags are to be updated
            tags: List of tag names (strings)
            incremental: Add incrementally (True) or replace all (False)

        Raises:
            ValueError: If not a Tag manager or entry is not persisted
        """
        with DatabaseOperation(self.logger, "update_entry_tags"):
            if self.config.model_class != Tag:
                raise ValueError("update_entry_tags only available for Tag manager")

            if entry.id is None:
                raise ValueError("Entry must be persisted before updating tags")

            # Normalize incoming tags
            norm_tags = set()
            for t in tags:
                if t:
                    normalized = DataValidator.normalize_string(t)
                    if normalized:
                        norm_tags.add(normalized)

            # Replacement mode: clear all existing
            if not incremental:
                entry.tags.clear()
                self.session.flush()

            # Get existing tags
            existing_tags = {tag.name for tag in entry.tags}

            # Add new tags
            new_tags = norm_tags - existing_tags
            for tag_name in new_tags:
                tag_obj = self.get_or_create(tag_name)
                entry.tags.append(tag_obj)

            if new_tags:
                self.session.flush()

                safe_logger(self.logger).log_debug(
                    "Updated entry tags",
                    {
                        "entry_date": entry.date,
                        "added_count": len(new_tags),
                        "total_count": len(entry.tags),
                        "incremental": incremental,
                    },
                )

    def _link(self, entity: Any, related: Any, attr_name: str) -> None:
        """Generic link helper."""
        if entity.id is None:
            raise ValueError(
                f"{self.config.display_name.capitalize()} must be persisted before linking"
            )
        if related.id is None:
            # Use the class name for a more specific error message
            related_name = type(related).__name__
            raise ValueError(f"{related_name} must be persisted before linking")

        # Verify this relationship exists for this entity type
        if not any(r.attr_name == attr_name for r in self.config.relationships):
            raise ValueError(
                f"{self.config.display_name.capitalize()} does not have "
                f"'{attr_name}' relationship"
            )

        collection = getattr(entity, attr_name)
        if related not in collection:
            collection.append(related)
            self.session.flush()

            entity_name = getattr(entity, self.config.name_field)
            safe_logger(self.logger).log_debug(
                f"Linked {self.config.display_name} to {attr_name}",
                {self.config.name_field: entity_name},
            )

    def _unlink(self, entity: Any, related: Any, attr_name: str) -> bool:
        """Generic unlink helper."""
        if entity.id is None:
            raise ValueError(
                f"{self.config.display_name.capitalize()} must be persisted before unlinking"
            )
        if related.id is None:
            # Use the class name for a more specific error message
            related_name = type(related).__name__
            raise ValueError(f"{related_name} must be persisted before unlinking")

        # Verify this relationship exists
        if not any(r.attr_name == attr_name for r in self.config.relationships):
            raise ValueError(
                f"{self.config.display_name.capitalize()} does not have "
                f"'{attr_name}' relationship"
            )

        collection = getattr(entity, attr_name)
        if related in collection:
            collection.remove(related)
            self.session.flush()

            entity_name = getattr(entity, self.config.name_field)
            safe_logger(self.logger).log_debug(
                f"Unlinked {self.config.display_name} from {attr_name}",
                {self.config.name_field: entity_name},
            )
            return True

        return False

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    def get_by_usage(
        self, min_count: int = 1, max_count: Optional[int] = None
    ) -> List[Any]:
        """
        Get entities filtered by usage count (entry relationships).

        Args:
            min_count: Minimum number of linked entries
            max_count: Maximum number of linked entries (optional)

        Returns:
            List of entities sorted by usage count (descending)
        """
        with DatabaseOperation(self.logger, "get_by_usage"):
            all_entities = self.get_all()

            # Filter by entry count
            filtered = []
            for entity in all_entities:
                count = len(entity.entries) if hasattr(entity, "entries") else 0
                if count >= min_count and (max_count is None or count <= max_count):
                    filtered.append(entity)

            # Sort by usage count descending
            return sorted(
                filtered,
                key=lambda e: len(e.entries) if hasattr(e, "entries") else 0,
                reverse=True,
            )

    def get_unused(self) -> List[Any]:
        """Get entities not linked to any entries."""
        with DatabaseOperation(self.logger, "get_unused"):
            return self.get_by_usage(min_count=0, max_count=0)


# Convenience factory functions
TagManager = SimpleManager.for_tags
ThemeManager = SimpleManager.for_themes
ArcManager = SimpleManager.for_arcs
EventManager = SimpleManager.for_events
