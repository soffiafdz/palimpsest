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
    - Consistent error handling with decorators
    - Consistent logging with decorators
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

        @handle_db_errors
        @log_database_operation("create_person")
        @validate_metadata(["name"])
        def create(self, metadata: Dict[str, Any]) -> Person:
            # Entity-specific creation logic
            ...
"""
from __future__ import annotations

import time
from abc import ABC
from typing import Any, Callable, Dict, Optional, Type, TypeVar, Union, Protocol

from sqlalchemy.orm import Session, Mapped
from sqlalchemy.exc import IntegrityError, OperationalError

from dev.core.exceptions import DatabaseError
from dev.core.logging_manager import PalimpsestLogger


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

                    if self.logger:
                        self.logger.log_debug(
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
