#!/usr/bin/env python3
"""
base_manager.py
--------------------
Base manager providing common CRUD operations and utilities.
All entity managers should inherit from this class.

Key Features:
    - Abstract base class with common CRUD scaffolding
    - Retry logic for database lock handling
    - Generic get-or-create utilities
    - Object resolution helpers
    - Consistent error handling via DatabaseOperation context manager
    - Consistent logging via DatabaseOperation context manager
    - Support for both soft and hard delete where applicable
    - Transaction management helpers

Usage:
    Subclass BaseManager for each entity type and override/implement:
    - exists(): Check if entity exists without exceptions
    - get(): Retrieve single entity with entity-specific logic
    - create(): Create new entity with validation and relationships
    - update(): Update entity with validation and relationships
    - delete(): Delete entity (soft or hard)
    - restore(): Restore soft-deleted entity (if applicable)

Example:
    class PersonManager(BaseManager):
        def __init__(self, session: Session, logger: Optional[PalimpsestLogger] = None):
            super().__init__(session, logger)

        def create(self, metadata: Dict[str, Any]) -> Person:
            DataValidator.validate_required_fields(metadata, ["name"])
            with DatabaseOperation(self.logger, "create_person"):
                # Entity-specific creation logic
                ...
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import time
from abc import ABC
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union, Protocol

# --- Third party imports ---
from sqlalchemy.orm import Session, Mapped
from sqlalchemy.exc import IntegrityError, OperationalError

# --- Local imports ---
from dev.core.exceptions import DatabaseError
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.core.validators import DataValidator


class HasId(Protocol):
    """Protocol for objects that have an id attribute."""

    id: Mapped[int]


T = TypeVar("T", bound=HasId)


class BaseManager(ABC):
    """
    Abstract base manager providing common CRUD operations and utilities.

    All entity managers should inherit from this class to ensure consistent
    patterns across the database layer.

    Attributes:
        session: SQLAlchemy session for database operations
        logger: Optional logger for operation tracking
    """

    def __init__(self, session: Session, logger: Optional[PalimpsestLogger] = None):
        """
        Initialize the base manager.

        Args:
            session: SQLAlchemy session
            logger: Optional logger for operation tracking
        """
        self.session = session
        self.logger = logger

    # -------------------------------------------------------------------------
    # Core Helper Methods
    # -------------------------------------------------------------------------

    def _execute_with_retry(
        self,
        operation: Callable,
        max_retries: int = 3,
        retry_delay: float = 0.1,
    ) -> Any:
        """
        Execute database operation with retry on lock.

        Args:
            operation: Callable that performs the operation
            max_retries: Maximum number of retry attempts
            retry_delay: Base delay between retries (exponential backoff)

        Returns:
            Result of the operation

        Raises:
            OperationalError: If all retries exhausted
            DatabaseError: If retry loop completes without success
        """
        for attempt in range(max_retries):
            try:
                return operation()
            except OperationalError as e:
                error_msg = str(e).lower()

                if (
                    "locked" in error_msg or "busy" in error_msg
                ) and attempt < max_retries - 1:
                    wait_time = retry_delay * (2**attempt)  # Exponential backoff

                    safe_logger(self.logger).log_debug(
                        f"Database locked, retrying in {wait_time}s",
                        {"attempt": attempt + 1, "max_retries": max_retries},
                    )

                    time.sleep(wait_time)
                    continue

                # Re-raise the exception if not a lock error or retries exhausted
                raise

        # This should never be reached due to the raise in the except block
        raise DatabaseError("Retry loop completed without success")

    def _get_or_create(
        self,
        model_class: Type[T],
        lookup_fields: Dict[str, Any],
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> T:
        """
        Get an existing item from a lookup table or create it if it doesn't exist.

        Handles race conditions where another process might create the object
        between our check and creation attempt.

        Args:
            model_class: ORM model class to query or create
            lookup_fields: Dictionary of field_name: value to filter/create
            extra_fields: Additional fields for new object creation only

        Returns:
            ORM instance of the model class

        Raises:
            DatabaseError: If creation fails after handling race condition

        Notes:
            - For string-based columns, value should be a str
            - For dates or other types, pass the appropriate Python types
            - The new object is added to the session and flushed immediately
        """
        # Try to get existing first
        obj = self.session.query(model_class).filter_by(**lookup_fields).first()
        if obj:
            return obj

        # Create new object
        fields = lookup_fields.copy()
        if extra_fields:
            fields.update(extra_fields)

        try:
            obj = model_class(**fields)
            self.session.add(obj)
            self.session.flush()
            return obj
        except IntegrityError:
            # Handle race condition - another process might have created it
            self.session.rollback()
            obj = self.session.query(model_class).filter_by(**lookup_fields).first()
            if obj:
                return obj
            # If still not found, something else went wrong
            raise DatabaseError(
                f"Failed to create {model_class.__name__} even after handling race condition"
            )

    def _resolve_object(
        self, item: Union[T, int], model_class: Type[T]
    ) -> T:
        """
        Resolve an item to an ORM object.

        Handles both ORM instances and integer IDs, ensuring the object
        is persisted and retrieving it from the database if needed.

        Args:
            item: Object instance or ID
            model_class: Target model class

        Returns:
            Resolved ORM object

        Raises:
            ValueError: If object not found or not persisted
            TypeError: If item type is invalid
        """
        if isinstance(item, model_class):
            if item.id is None:
                raise ValueError(f"{model_class.__name__} instance must be persisted")
            return item
        elif isinstance(item, int):
            obj = self.session.get(model_class, item)
            if obj is None:
                raise ValueError(f"No {model_class.__name__} found with id: {item}")
            return obj
        else:
            raise TypeError(
                f"Expected {model_class.__name__} instance or int, got {type(item)}"
            )

    # -------------------------------------------------------------------------
    # Generic CRUD Helpers
    # -------------------------------------------------------------------------

    def _exists(
        self,
        model_class: Type[T],
        field_name: str,
        value: Any,
        normalize: bool = True,
        include_deleted: bool = False,
    ) -> bool:
        """
        Generic existence check for any entity.

        Args:
            model_class: ORM model class to query
            field_name: Field name to filter by
            value: Value to check for
            normalize: Whether to normalize string values
            include_deleted: Include soft-deleted entities

        Returns:
            True if entity exists, False otherwise
        """
        if value is None:
            return False

        # Normalize string values
        if normalize and isinstance(value, str):
            value = DataValidator.normalize_string(value)
            if not value:
                return False

        query = self.session.query(model_class).filter_by(**{field_name: value})

        # Handle soft delete if model supports it
        if not include_deleted and hasattr(model_class, "deleted_at"):
            query = query.filter(model_class.deleted_at.is_(None))

        return query.first() is not None

    def _get_by_id(
        self,
        model_class: Type[T],
        entity_id: int,
        include_deleted: bool = False,
    ) -> Optional[T]:
        """
        Get entity by ID with optional soft-delete filtering.

        Args:
            model_class: ORM model class
            entity_id: The entity ID
            include_deleted: Include soft-deleted entities

        Returns:
            Entity if found, None otherwise
        """
        entity = self.session.get(model_class, entity_id)
        if entity is None:
            return None

        if not include_deleted and hasattr(entity, "deleted_at"):
            if entity.deleted_at is not None:
                return None

        return entity

    def _get_by_field(
        self,
        model_class: Type[T],
        field_name: str,
        value: Any,
        normalize: bool = True,
        include_deleted: bool = False,
    ) -> Optional[T]:
        """
        Get entity by a specific field value.

        Args:
            model_class: ORM model class
            field_name: Field name to filter by
            value: Value to look up
            normalize: Whether to normalize string values
            include_deleted: Include soft-deleted entities

        Returns:
            Entity if found, None otherwise
        """
        if value is None:
            return None

        # Normalize string values
        if normalize and isinstance(value, str):
            value = DataValidator.normalize_string(value)
            if not value:
                return None

        query = self.session.query(model_class).filter_by(**{field_name: value})

        # Handle soft delete if model supports it
        if not include_deleted and hasattr(model_class, "deleted_at"):
            query = query.filter(model_class.deleted_at.is_(None))

        return query.first()

    def _get_all(
        self,
        model_class: Type[T],
        order_by: Optional[str] = None,
        include_deleted: bool = False,
        **filters: Any,
    ) -> List[T]:
        """
        Get all entities of a type with optional filtering and ordering.

        Args:
            model_class: ORM model class
            order_by: Field name to order by (optional)
            include_deleted: Include soft-deleted entities
            **filters: Additional filter conditions

        Returns:
            List of entities
        """
        query = self.session.query(model_class)

        # Apply filters
        if filters:
            query = query.filter_by(**filters)

        # Handle soft delete if model supports it
        if not include_deleted and hasattr(model_class, "deleted_at"):
            query = query.filter(model_class.deleted_at.is_(None))

        # Apply ordering
        if order_by and hasattr(model_class, order_by):
            attr = getattr(model_class, order_by)
            # Check if it's a column attribute (not a Python property)
            if hasattr(attr, "__clause_element__") or hasattr(attr, "property"):
                query = query.order_by(attr)

        return query.all()

    def _count(
        self,
        model_class: Type[T],
        include_deleted: bool = False,
        **filters: Any,
    ) -> int:
        """
        Count entities with optional filtering.

        Args:
            model_class: ORM model class
            include_deleted: Include soft-deleted entities
            **filters: Additional filter conditions

        Returns:
            Count of matching entities
        """
        query = self.session.query(model_class)

        if filters:
            query = query.filter_by(**filters)

        if not include_deleted and hasattr(model_class, "deleted_at"):
            query = query.filter(model_class.deleted_at.is_(None))

        return query.count()

    # -------------------------------------------------------------------------
    # Generic Relationship Helpers
    # -------------------------------------------------------------------------

    def _update_collection(
        self,
        entity: Any,
        attr_name: str,
        items: List[Any],
        model_class: Type[T],
        remove_items: Optional[List[Any]] = None,
        incremental: bool = True,
    ) -> None:
        """
        Update a many-to-many relationship collection.

        Args:
            entity: Entity whose collection to update
            attr_name: Name of the relationship attribute (e.g., 'entries', 'tags')
            items: Items to add (can be objects or IDs)
            model_class: Model class for resolving IDs
            remove_items: Items to remove in incremental mode
            incremental: If True, add/remove items; if False, replace entire collection

        Example:
            self._update_collection(
                person, "events", metadata.get("events", []),
                Event, metadata.get("remove_events", [])
            )
        """
        collection = getattr(entity, attr_name)

        if not incremental:
            # Replacement mode: clear and add all
            collection.clear()

        # Add items
        for item in items:
            try:
                resolved = self._resolve_object(item, model_class)
                if resolved and resolved not in collection:
                    collection.append(resolved)
            except (ValueError, TypeError):
                safe_logger(self.logger).log_warning(
                    f"Could not resolve {model_class.__name__} for {attr_name}",
                    {"item": item},
                )

        # Remove items (only in incremental mode)
        if incremental and remove_items:
            for item in remove_items:
                try:
                    resolved = self._resolve_object(item, model_class)
                    if resolved and resolved in collection:
                        collection.remove(resolved)
                except (ValueError, TypeError):
                    pass  # Silently skip items that can't be resolved

        self.session.flush()

    def _update_relationships(
        self,
        entity: Any,
        metadata: Dict[str, Any],
        relationship_configs: List[tuple],
        incremental: bool = True,
    ) -> None:
        """
        Update multiple many-to-many relationships from metadata.

        Args:
            entity: Entity to update
            metadata: Dictionary containing relationship data
            relationship_configs: List of (attr_name, meta_key, model_class) tuples
            incremental: If True, add/remove items; if False, replace

        Example:
            self._update_relationships(person, metadata, [
                ("events", "events", Event),
                ("entries", "entries", Entry),
                ("dates", "dates", Moment),
            ])
        """
        for attr_name, meta_key, model_class in relationship_configs:
            if meta_key not in metadata:
                continue

            items = metadata[meta_key]
            remove_items = metadata.get(f"remove_{meta_key}", [])

            self._update_collection(
                entity, attr_name, items, model_class, remove_items, incremental
            )

    # -------------------------------------------------------------------------
    # Scalar Field Update Helpers
    # -------------------------------------------------------------------------

    def _update_scalar_fields(
        self,
        entity: Any,
        metadata: Dict[str, Any],
        field_configs: List[tuple],
    ) -> None:
        """
        Update multiple scalar fields from metadata using normalizers.

        Args:
            entity: Entity to update
            metadata: Dictionary containing field values
            field_configs: List of tuples:
                - (field_name, normalizer) for required fields
                - (field_name, normalizer, allow_none) for optional fields

        Example:
            self._update_scalar_fields(city, metadata, [
                ("city", DataValidator.normalize_string),
                ("state_province", DataValidator.normalize_string, True),
                ("country", DataValidator.normalize_string, True),
            ])
        """
        for config in field_configs:
            field_name = config[0]
            normalizer = config[1]
            allow_none = config[2] if len(config) > 2 else False

            if field_name not in metadata:
                continue

            value = normalizer(metadata[field_name])
            if value is not None or allow_none:
                setattr(entity, field_name, value)

    def _resolve_parent(
        self,
        parent_spec: Any,
        parent_model: Type[T],
        get_method: Callable,
        get_or_create_method: Optional[Callable] = None,
        id_param: str = "id",
    ) -> Optional[T]:
        """
        Resolve a parent entity from various input types.

        Args:
            parent_spec: Parent object, ID, or name string
            parent_model: Parent model class
            get_method: Method to get parent by name/id (e.g., self.get_city)
            get_or_create_method: Optional method for string-based creation
            id_param: Parameter name for ID lookup (default: "id")

        Returns:
            Resolved parent entity or None

        Example:
            city = self._resolve_parent(
                metadata.get("city"),
                City,
                lambda **kw: self.get_city(city_id=kw.get("id"), city_name=kw.get("name")),
                self.get_or_create_city
            )
        """
        if parent_spec is None:
            return None

        if isinstance(parent_spec, parent_model):
            return parent_spec
        elif isinstance(parent_spec, int):
            return get_method(**{id_param: parent_spec})
        elif isinstance(parent_spec, str) and get_or_create_method:
            return get_or_create_method(parent_spec)
        elif isinstance(parent_spec, str):
            return get_method(name=parent_spec)

        return None

    # -------------------------------------------------------------------------
    # Abstract CRUD Methods (to be implemented by subclasses)
    # -------------------------------------------------------------------------
    #
    # Subclasses should implement these methods with entity-specific logic:
    #
    # def exists(self, **kwargs) -> bool:
    #     """Check if entity exists without raising exceptions."""
    #     pass
    #
    # def get(self, **kwargs) -> Optional[T]:
    #     """Retrieve single entity."""
    #     pass
    #
    # def get_all(self, **kwargs) -> List[T]:
    #     """Retrieve multiple entities."""
    #     pass
    #
    # def create(self, metadata: Dict[str, Any]) -> T:
    #     """Create new entity."""
    #     pass
    #
    # def update(self, entity: T, metadata: Dict[str, Any]) -> T:
    #     """Update existing entity."""
    #     pass
    #
    # def delete(self, entity: T) -> None:
    #     """Delete entity (soft or hard)."""
    #     pass
    #
    # def restore(self, entity: T) -> T:
    #     """Restore soft-deleted entity (if applicable)."""
    #     pass
    # -------------------------------------------------------------------------
