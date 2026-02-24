#!/usr/bin/env python3
"""
entity_manager.py
-----------------
Config-driven manager for complex entities: Person, Location, Reference, Poem.

This module provides a base EntityManager class that consolidates common CRUD
patterns from the individual entity managers. Each entity type is configured
via an EntityManagerConfig that specifies:
- The model class and primary lookup field
- Soft delete support
- Scalar field normalizers
- Relationship configurations

Entity-specific logic is handled through method overrides in subclasses.

Usage:
    # Subclass for entity-specific behavior
    class PersonManager(EntityManager):
        def __init__(self, session, logger):
            super().__init__(session, logger, PERSON_CONFIG)

        def _validate_create(self, metadata):
            # Person-specific validation (name_fellow logic)
            ...
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, TypeVar

# --- Third party imports ---
from sqlalchemy.orm import Session

# --- Local imports ---
from dev.core.exceptions import DatabaseError, ValidationError
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.core.validators import DataValidator
from dev.database.decorators import DatabaseOperation
from .base_manager import BaseManager

T = TypeVar("T")


@dataclass
class EntityManagerConfig:
    """
    Configuration for an entity manager.

    Attributes:
        model_class: SQLAlchemy model class
        name_field: Primary lookup field name (e.g., 'name', 'title')
        display_name: Human-readable name for error messages
        supports_soft_delete: Whether entity supports soft delete
        order_by: Field name for default ordering
        scalar_fields: List of (field_name, normalizer, allow_none) tuples
        relationships: List of (attr_name, meta_key, model_class) tuples
    """

    model_class: Type
    name_field: str
    display_name: str
    supports_soft_delete: bool = False
    order_by: Optional[str] = None
    scalar_fields: List[tuple] = field(default_factory=list)
    relationships: List[tuple] = field(default_factory=list)


class EntityManager(BaseManager):
    """
    Config-driven manager for complex entities.

    Provides template methods for CRUD operations that subclasses can
    customize through hook methods. This reduces boilerplate while
    allowing entity-specific logic.

    Subclasses should override:
        - _validate_create(): Add entity-specific validation
        - _create_entity(): Customize entity creation
        - _post_create(): Add post-creation logic
        - _validate_update(): Add entity-specific validation
        - _post_update(): Add post-update logic
        - _pre_delete(): Add pre-deletion logic
    """

    config: EntityManagerConfig

    def __init__(
        self,
        session: Session,
        logger: Optional[PalimpsestLogger],
        config: EntityManagerConfig,
    ):
        """
        Initialize the entity manager.

        Args:
            session: SQLAlchemy session
            logger: Optional logger for operation tracking
            config: Entity configuration
        """
        super().__init__(session, logger)
        self.config = config

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def exists(
        self,
        name: Optional[str] = None,
        entity_id: Optional[int] = None,
        include_deleted: bool = False,
    ) -> bool:
        """
        Check if an entity exists.

        Args:
            name: Entity name to check
            entity_id: Entity ID to check
            include_deleted: Include soft-deleted entities

        Returns:
            True if entity exists, False otherwise
        """
        with DatabaseOperation(self.logger, f"check_{self.config.display_name}_exists"):
            if entity_id is not None:
                entity = self._get_by_id(
                    self.config.model_class, entity_id, include_deleted=include_deleted
                )
                return entity is not None
            if name is not None:
                return self._exists(
                    self.config.model_class,
                    self.config.name_field,
                    name,
                    include_deleted=include_deleted,
                )
            return False

    def get(
        self,
        name: Optional[str] = None,
        entity_id: Optional[int] = None,
        include_deleted: bool = False,
    ) -> Optional[T]:
        """
        Retrieve an entity by name or ID.

        Args:
            name: Entity name
            entity_id: Entity ID
            include_deleted: Include soft-deleted entities

        Returns:
            Entity if found, None otherwise
        """
        with DatabaseOperation(self.logger, f"get_{self.config.display_name}"):
            if entity_id is not None:
                return self._get_by_id(
                    self.config.model_class, entity_id, include_deleted=include_deleted
                )
            if name is not None:
                return self._get_by_field(
                    self.config.model_class,
                    self.config.name_field,
                    name,
                    include_deleted=include_deleted,
                )
            return None

    def get_all(self, include_deleted: bool = False) -> List[T]:
        """
        Retrieve all entities.

        Args:
            include_deleted: Include soft-deleted entities

        Returns:
            List of all entities
        """
        with DatabaseOperation(self.logger, f"get_all_{self.config.display_name}s"):
            return self._get_all(
                self.config.model_class,
                order_by=self.config.order_by,
                include_deleted=include_deleted,
            )

    def get_or_create(
        self,
        name: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> T:
        """
        Get an existing entity or create a new one.

        Args:
            name: Entity name to find or create
            extra_metadata: Additional fields for creation

        Returns:
            Existing or newly created entity
        """
        with DatabaseOperation(self.logger, f"get_or_create_{self.config.display_name}"):
            # Try to get existing
            existing = self.get(name=name)
            if existing:
                return existing

            # Create new
            metadata = {self.config.name_field: name}
            if extra_metadata:
                metadata.update(extra_metadata)
            return self.create(metadata)

    def create(self, metadata: Dict[str, Any]) -> T:
        """
        Create a new entity.

        Args:
            metadata: Dictionary with entity fields

        Returns:
            Created entity

        Raises:
            ValidationError: If validation fails
            DatabaseError: If entity already exists
        """
        with DatabaseOperation(self.logger, f"create_{self.config.display_name}"):
            # Validate
            self._validate_create(metadata)

            # Normalize name field
            name = DataValidator.normalize_string(metadata.get(self.config.name_field))
            if not name:
                raise ValidationError(
                    f"Invalid {self.config.display_name} name: "
                    f"{metadata.get(self.config.name_field)}"
                )

            # Check for existing
            existing = self.get(name=name)
            if existing:
                raise DatabaseError(f"{self.config.display_name} already exists: {name}")

            # Create entity
            entity = self._create_entity(metadata, name)
            self.session.add(entity)
            self.session.flush()

            safe_logger(self.logger).log_debug(
                f"Created {self.config.display_name}: {name}",
                {f"{self.config.display_name}_id": entity.id},  # type: ignore[attr-defined]
            )

            # Post-creation (relationships, etc.)
            self._post_create(entity, metadata)

            return entity

    def update(self, entity: T, metadata: Dict[str, Any]) -> T:
        """
        Update an existing entity.

        Args:
            entity: Entity to update
            metadata: Dictionary with fields to update

        Returns:
            Updated entity
        """
        with DatabaseOperation(self.logger, f"update_{self.config.display_name}"):
            # Validate
            self._validate_update(entity, metadata)

            # Get fresh from session
            db_entity = self.session.get(self.config.model_class, entity.id)  # type: ignore[attr-defined]
            if db_entity is None:
                raise DatabaseError(
                    f"{self.config.display_name} with id={entity.id} does not exist"  # type: ignore[attr-defined]
                )
            entity = self.session.merge(db_entity)

            # Update scalar fields
            if self.config.scalar_fields:
                self._update_scalar_fields(entity, metadata, self.config.scalar_fields)

            # Update relationships
            if self.config.relationships:
                self._update_relationships(
                    entity, metadata, self.config.relationships, incremental=True
                )

            # Post-update hook
            self._post_update(entity, metadata)

            self.session.flush()
            return entity

    def delete(
        self,
        entity: T,
        deleted_by: Optional[str] = None,
        reason: Optional[str] = None,
        hard: bool = False,
    ) -> None:
        """
        Delete an entity.

        Args:
            entity: Entity to delete
            deleted_by: Who is deleting (for soft delete)
            reason: Why it's being deleted (for soft delete)
            hard: If True, permanently delete even if soft delete is supported
        """
        with DatabaseOperation(self.logger, f"delete_{self.config.display_name}"):
            if not isinstance(entity, self.config.model_class):
                raise TypeError(
                    f"Expected {self.config.model_class.__name__}, "
                    f"got {type(entity).__name__}"
                )

            # Pre-delete hook
            self._pre_delete(entity)

            # Soft delete if supported and not forced hard
            if self.config.supports_soft_delete and not hard:
                entity.deleted_at = datetime.now(timezone.utc)  # type: ignore[attr-defined]
                entity.deleted_by = deleted_by  # type: ignore[attr-defined]
                entity.deletion_reason = reason  # type: ignore[attr-defined]
                safe_logger(self.logger).log_debug(
                    f"Soft deleted {self.config.display_name}",
                    {
                        f"{self.config.display_name}_id": entity.id,  # type: ignore[attr-defined]
                        "deleted_by": deleted_by,
                    },
                )
            else:
                # Hard delete
                self.session.delete(entity)
                safe_logger(self.logger).log_debug(
                    f"Deleted {self.config.display_name}",
                    {f"{self.config.display_name}_id": entity.id},  # type: ignore[attr-defined]
                )

            self.session.flush()

    def restore(self, entity: T) -> T:
        """
        Restore a soft-deleted entity.

        Args:
            entity: Entity to restore

        Returns:
            Restored entity

        Raises:
            DatabaseError: If entity doesn't support soft delete
        """
        with DatabaseOperation(self.logger, f"restore_{self.config.display_name}"):
            if not self.config.supports_soft_delete:
                raise DatabaseError(
                    f"{self.config.display_name} does not support soft delete"
                )

            if not isinstance(entity, self.config.model_class):
                raise TypeError(
                    f"Expected {self.config.model_class.__name__}, "
                    f"got {type(entity).__name__}"
                )

            entity.deleted_at = None  # type: ignore[attr-defined]
            entity.deleted_by = None  # type: ignore[attr-defined]
            entity.deletion_reason = None  # type: ignore[attr-defined]
            self.session.flush()

            safe_logger(self.logger).log_debug(
                f"Restored {self.config.display_name}",
                {f"{self.config.display_name}_id": entity.id},  # type: ignore[attr-defined]
            )

            return entity

    # =========================================================================
    # Hook Methods (Override in Subclasses)
    # =========================================================================

    def _validate_create(self, metadata: Dict[str, Any]) -> None:
        """
        Validate metadata before entity creation.

        Override for entity-specific validation.

        Args:
            metadata: Creation metadata

        Raises:
            ValidationError: If validation fails
        """
        pass

    def _create_entity(self, metadata: Dict[str, Any], name: str) -> T:
        """
        Create the entity instance.

        Override for entity-specific creation logic.

        Args:
            metadata: Creation metadata
            name: Normalized entity name

        Returns:
            Created entity (not yet persisted)
        """
        # Build entity with normalized scalar fields
        fields = {self.config.name_field: name}

        for config in self.config.scalar_fields:
            field_name = config[0]
            normalizer = config[1]
            if field_name in metadata and field_name != self.config.name_field:
                fields[field_name] = normalizer(metadata[field_name])

        return self.config.model_class(**fields)

    def _post_create(self, entity: T, metadata: Dict[str, Any]) -> None:
        """
        Post-creation hook for relationships and additional setup.

        Override for entity-specific post-creation logic.

        Args:
            entity: Created entity
            metadata: Creation metadata
        """
        # Default: update relationships
        if self.config.relationships:
            self._update_relationships(
                entity, metadata, self.config.relationships, incremental=False
            )

    def _validate_update(self, entity: T, metadata: Dict[str, Any]) -> None:
        """
        Validate metadata before entity update.

        Override for entity-specific validation.

        Args:
            entity: Entity being updated
            metadata: Update metadata

        Raises:
            ValidationError: If validation fails
        """
        pass

    def _post_update(self, entity: T, metadata: Dict[str, Any]) -> None:
        """
        Post-update hook for additional logic.

        Override for entity-specific post-update logic.

        Args:
            entity: Updated entity
            metadata: Update metadata
        """
        pass

    def _pre_delete(self, entity: T) -> None:
        """
        Pre-deletion hook for cleanup.

        Override for entity-specific pre-deletion logic.

        Args:
            entity: Entity being deleted
        """
        pass
