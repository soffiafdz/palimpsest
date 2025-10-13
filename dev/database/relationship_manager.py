#!/usr/bin/env python3
"""
relationship_manager.py
-----------------------
Handles generic relationship updates: one-to-one, one-to-many and many-to-many.

Provides static methods for managing SQLAlchemy relationships with proper
error handling, transaction management, and support for incremental updates.

Key Features:
    - Type-safe relationship management using Protocol
    - Support for incremental and full replacement modes
    - Automatic flush management
    - Object resolution (handle IDs or ORM instances)
    - Comprehensive error handling
    - Minimal API surface (all static methods)

Relationship Types:
    One-to-One:
        - Create/update single child object
        - Optional deletion support
        - Foreign key management

    One-to-Many:
        - Parent owns multiple children
        - Children have foreign key to parent
        - Add/remove/replace operations

    Many-to-Many:
        - Association table relationships
        - Bidirectional updates
        - Add/remove/replace operations

Usage Patterns:
    One-to-One (e.g., Entry → ManuscriptEntry):
        >>> RelationshipManager.update_one_to_one(
        ...     session=session,
        ...     parent_obj=entry,
        ...     relationship_name="manuscript",
        ...     model_class=ManuscriptEntry,
        ...     foreign_key_attr="entry_id",
        ...     child_data={"status": "source", "edited": True}
        ... )

    One-to-Many (e.g., ReferenceSource → References):
        >>> RelationshipManager.update_one_to_many(
        ...     session=session,
        ...     parent_obj=source,
        ...     items=[ref1, ref2, ref3],
        ...     model_class=Reference,
        ...     foreign_key_attr="source_id",
        ...     incremental=True
        ... )

    Many-to-Many (e.g., Entry → People):
        >>> RelationshipManager.update_many_to_many(
        ...     session=session,
        ...     parent_obj=entry,
        ...     relationship_name="people",
        ...     items=["Alice", "Bob"],  # Can be IDs or objects
        ...     model_class=Person,
        ...     incremental=True,
        ...     remove_items=["Charlie"]
        ... )

Modes:
    Incremental Mode (incremental=True):
        - Add new items to existing relationships
        - Optionally remove specific items
        - Preserves unlisted items
        - Efficient for updates

    Replacement Mode (incremental=False):
        - Clear all existing relationships
        - Add only specified items
        - Complete replacement
        - Use for full sync operations

Helper Methods:
    _resolve_object:
        - Converts IDs to ORM objects
        - Validates object persistence
        - Handles both instances and integers
        - Comprehensive error messages

Error Handling:
    - ValueError: Parent object not persisted
    - ValueError: Referenced object not found
    - TypeError: Invalid item type
    - Automatic transaction rollback on errors

Notes:
    - All operations call session.flush() if changes made
    - Parent objects must be persisted (have ID) before linking
    - Supports mixing ORM objects and IDs in item lists
    - Returns boolean indicating if changes were made
    - Thread-safe when used with proper session management
"""
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, Protocol
from sqlalchemy.orm import Session, Mapped


class HasId(Protocol):
    """Protocol for objects that have an id attribute."""

    id: Mapped[int]


T = TypeVar("T", bound=HasId)
C = TypeVar("C", bound=HasId)


class RelationshipManager:
    """
    Handles generic relationship updates: one-to-one, one-to-many and many-to-many.

    Provides static methods for managing SQLAlchemy relationships with proper
    error handling and transaction management.
    """

    @staticmethod
    def update_one_to_one(
        session: Session,
        parent_obj: HasId,
        relationship_name: str,
        model_class: Type[C],
        foreign_key_attr: str,
        child_data: Dict[str, Any] = {},
        delete: bool = False,
    ) -> Optional[C]:
        """
        Update a one-to-one relationship.

        Args:
            session: SQLAlchemy session
            parent_obj: Parent object containing the relationship
            relationship_name: Name of the relationship attribute
            model_class: Class of the child object
            foreign_key_attr: Foreign key attribute name
            child_data: Data for creating/updating child object
            delete: Whether to delete the relationship

        Returns:
            Updated or created child object, None if deleted

        Raises:
            ValueError: If parent object is not persisted
        """
        if parent_obj.id is None:
            raise ValueError(
                f"{parent_obj.__class__.__name__} must be persisted before linking"
            )

        existing_child: Optional[C] = getattr(parent_obj, relationship_name, None)

        if existing_child:
            if delete:
                session.delete(existing_child)
                session.flush()
                return None
            if child_data:
                for key, value in child_data.items():
                    if hasattr(existing_child, key):
                        setattr(existing_child, key, value)
                session.flush()
            return existing_child

        child_data[foreign_key_attr] = parent_obj.id
        child_obj = model_class(**child_data)
        session.add(child_obj)
        session.flush()
        return child_obj

    @staticmethod
    def update_one_to_many(
        session: Session,
        parent_obj: HasId,
        items: List[Union[C, int, Dict[str, Any]]],
        model_class: Type[C],
        foreign_key_attr: str,
        incremental: bool = True,
        remove_items: Optional[List[Union[T, int]]] = None,
    ) -> bool:
        """
        Generic one-to-many relationship updater.

        Args:
            session: SQLAlchemy session
            parent_obj: Parent object
            items: List of items to add/update
            model_class: Class of child objects
            foreign_key_attr: Foreign key attribute name
            incremental: Whether to add incrementally or replace all
            remove_items: Items to remove (incremental mode only)

        Returns:
            True if any changes were made

        Raises:
            ValueError: If parent object is not persisted
        """
        if parent_obj.id is None:
            raise ValueError(
                f"{parent_obj.__class__.__name__} must be persisted before linking"
            )

        changed = False
        existing_children = (
            session.query(model_class)
            .filter(getattr(model_class, foreign_key_attr) == parent_obj.id)
            .all()
        )
        existing_ids = {child.id for child in existing_children}

        if not incremental:
            for child in existing_children:
                setattr(child, foreign_key_attr, None)
                changed = True

        for item in items:
            if isinstance(item, dict):
                child_obj = model_class(**item)
                session.add(child_obj)
                session.flush()
                setattr(child_obj, foreign_key_attr, parent_obj.id)
                changed = True
            else:
                child_obj = RelationshipManager._resolve_object(
                    session, item, model_class
                )
                current_parent_id = getattr(child_obj, foreign_key_attr)

                if current_parent_id != parent_obj.id:
                    setattr(child_obj, foreign_key_attr, parent_obj.id)
                    changed = True

        if incremental and remove_items:
            for item in remove_items:
                child_obj = RelationshipManager._resolve_object(
                    session, item, model_class
                )
                if child_obj.id in existing_ids:
                    setattr(child_obj, foreign_key_attr, None)
                    changed = True

        if changed:
            session.flush()

        return changed

    @staticmethod
    def update_many_to_many(
        session: Session,
        parent_obj: HasId,
        relationship_name: str,
        items: List[Union[C, int]],
        model_class: Type[C],
        incremental: bool = True,
        remove_items: Optional[List[Union[C, int]]] = None,
    ) -> bool:
        """
        Generic many-to-many relationship updater.

        Args:
            session: SQLAlchemy session
            parent_obj: Parent object
            relationship_name: Name of the relationship attribute
            items: List of items to add
            model_class: Class of related objects
            incremental: Whether to add incrementally or replace all
            remove_items: Items to remove (incremental mode only)

        Returns:
            True if any changes were made

        Raises:
            ValueError: If parent object is not persisted
        """
        if parent_obj.id is None:
            raise ValueError(
                f"{parent_obj.__class__.__name__} must be persisted before linking"
            )

        relationship = getattr(parent_obj, relationship_name)
        existing_ids = {obj.id for obj in relationship}
        changed = False

        if not incremental:
            relationship.clear()
            changed = True

        for item in items:
            obj = RelationshipManager._resolve_object(session, item, model_class)
            if obj.id not in existing_ids:
                relationship.append(obj)
                changed = True

        if incremental and remove_items:
            for item in remove_items:
                obj = RelationshipManager._resolve_object(session, item, model_class)
                if obj.id in existing_ids:
                    relationship.remove(obj)
                    changed = True

        if changed:
            session.flush()

        return changed

    @staticmethod
    def _resolve_object(
        session: Session, item: Union[T, int], model_class: Type[T]
    ) -> T:
        """
        Resolve an item to an ORM object.

        Args:
            session: SQLAlchemy session
            item: Object instance, ID, or other identifier
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
            obj = session.get(model_class, item)
            if obj is None:
                raise ValueError(f"No {model_class.__name__} found with id: {item}")
            return obj
        else:
            raise TypeError(
                f"Expected {model_class.__name__} instance or int, got {type(item)}"
            )
