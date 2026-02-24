#!/usr/bin/env python3
"""
person_manager.py
--------------------
Manages Person entities with soft delete support.

Person represents individuals mentioned in journal entries, scenes,
and threads. The manager handles alias-based lookup and provides
CRUD operations with soft delete support.

Key Features:
    - CRUD operations for persons
    - Soft delete support (preserves data with deleted_at flag)
    - Alias-based lookup (unique field on Person)
    - M2M relationships with entries, scenes, and threads
    - Relationship type categorization (family, friend, romantic, etc.)

Usage:
    person_mgr = PersonManager(session, logger)

    # Create person with alias
    person = person_mgr.create({
        "alias": "majo",
        "name": "Maria Jose",
        "lastname": "Castro",
        "relation_type": "friend"
    })

    # Get person by alias or name
    majo = person_mgr.get(alias="majo")
    maria = person_mgr.get(name="Maria Jose")

    # Soft delete
    person_mgr.delete(person, deleted_by="admin", reason="Duplicate")

    # Restore
    person_mgr.restore(person)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from typing import Any, Dict, List, Optional, Union

# --- Third-party imports ---
from sqlalchemy.orm import Session

# --- Local imports ---
from dev.core.exceptions import DatabaseError, ValidationError
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.core.validators import DataValidator
from dev.database.decorators import DatabaseOperation
from dev.database.models import Entry, Person, PersonAlias, RelationType, Scene, Thread

from .base_manager import BaseManager


class PersonManager(BaseManager):
    """
    Manages Person table operations with soft delete support.

    Provides CRUD operations for Person entities with alias-based
    lookup and relationship management.
    """

    def __init__(
        self,
        session: Session,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize the person manager.

        Args:
            session: SQLAlchemy session
            logger: Optional logger for operation tracking
        """
        super().__init__(session, logger)

    # =========================================================================
    # PERSON OPERATIONS
    # =========================================================================

    def exists(
        self,
        slug: Optional[str] = None,
        name: Optional[str] = None,
        include_deleted: bool = False,
    ) -> bool:
        """
        Check if a person exists.

        Args:
            slug: The person's slug (unique identifier)
            name: The person's name
            include_deleted: Whether to include soft-deleted persons

        Returns:
            True if person exists, False otherwise

        Notes:
            - Slug lookup is preferred (unique)
            - Name alone may match multiple people
        """
        with DatabaseOperation(self.logger, "person_exists"):
            if slug:
                return self._exists(
                    Person, "slug", slug, include_deleted=include_deleted
                )
            if name:
                return self._exists(
                    Person, "name", name, include_deleted=include_deleted
                )
            return False

    def get(
        self,
        slug: Optional[str] = None,
        name: Optional[str] = None,
        person_id: Optional[int] = None,
        include_deleted: bool = False,
    ) -> Optional[Person]:
        """
        Retrieve a person by slug, name, or ID.

        Args:
            slug: The person's slug (unique identifier)
            name: The person's name
            person_id: The person ID
            include_deleted: Whether to include soft-deleted persons

        Returns:
            Person object if found, None otherwise

        Notes:
            - Lookup priority: ID > slug > name
            - Slug is unique, so always returns single match
            - Name may match multiple people; returns first match
        """
        with DatabaseOperation(self.logger, "get_person"):
            # ID lookup
            if person_id is not None:
                return self._get_by_id(Person, person_id, include_deleted=include_deleted)

            # Slug lookup (unique)
            if slug is not None:
                normalized = DataValidator.normalize_string(slug)
                if not normalized:
                    return None
                return self._get_by_field(
                    Person, "slug", normalized, include_deleted=include_deleted
                )

            # Name lookup
            if name is not None:
                normalized = DataValidator.normalize_string(name)
                if not normalized:
                    return None

                query = self.session.query(Person).filter_by(name=normalized)
                if not include_deleted:
                    query = query.filter(Person.deleted_at.is_(None))

                return query.first()

            return None

    def get_all(self, include_deleted: bool = False) -> List[Person]:
        """
        Retrieve all persons.

        Args:
            include_deleted: Whether to include soft-deleted persons

        Returns:
            List of Person objects, ordered by name
        """
        with DatabaseOperation(self.logger, "get_all_persons"):
            return self._get_all(Person, order_by="name", include_deleted=include_deleted)

    def create(self, metadata: Dict[str, Any]) -> Person:
        """
        Create a new person.

        Args:
            metadata: Dictionary with required keys:
                - name: First/given name (required)
                - lastname OR disambiguator: At least one required for identification
                Optional keys:
                - relation_type: RelationType enum or string
                - entries: List of Entry objects or IDs
                - scenes: List of Scene objects or IDs
                - threads: List of Thread objects or IDs

        Returns:
            Created Person object

        Raises:
            ValidationError: If name is missing or neither lastname/disambiguator provided
            DatabaseError: If slug already exists
        """
        DataValidator.validate_required_fields(metadata, ["name"])
        with DatabaseOperation(self.logger, "create_person"):
            # Validate and normalize name
            p_name = DataValidator.normalize_string(metadata.get("name"))
            if not p_name:
                raise ValidationError(f"Invalid person name: {metadata.get('name')}")

            # Normalize optional fields
            p_lastname = DataValidator.normalize_string(metadata.get("lastname"))
            p_disambiguator = DataValidator.normalize_string(metadata.get("disambiguator"))

            # Validate: must have either lastname or disambiguator
            if not p_lastname and not p_disambiguator:
                raise ValidationError(
                    f"Person '{p_name}' must have either lastname or disambiguator"
                )

            # Generate slug
            slug = Person.generate_slug(p_name, p_lastname, p_disambiguator)

            # Check slug uniqueness
            existing = self.get(slug=slug, include_deleted=True)
            if existing:
                raise DatabaseError(f"Person already exists with slug '{slug}'")

            # Normalize relation_type
            relation_type = DataValidator.normalize_enum(
                metadata.get("relation_type"), RelationType, "relation_type"
            )

            # Create person
            person = Person(
                name=p_name,
                lastname=p_lastname,
                disambiguator=p_disambiguator,
                slug=slug,
                relation_type=relation_type,
            )
            self.session.add(person)
            self.session.flush()

            safe_logger(self.logger).log_debug(
                f"Created person: {p_name}",
                {
                    "person_id": person.id,
                    "slug": slug,
                    "lastname": p_lastname,
                    "disambiguator": p_disambiguator,
                },
            )

            # Update relationships
            self._update_person_relationships(person, metadata, incremental=False)

            return person

    def get_or_create(
        self,
        name: str,
        lastname: Optional[str] = None,
        disambiguator: Optional[str] = None,
        **extra_fields,
    ) -> Person:
        """
        Get existing person by slug or create new one if not found.

        Args:
            name: First/given name (required)
            lastname: Last/family name (optional, but one of lastname/disambiguator required)
            disambiguator: Context tag (optional, but one of lastname/disambiguator required)
            **extra_fields: Additional fields for creation (relation_type, etc.)

        Returns:
            Existing or newly created Person object

        Raises:
            ValidationError: If name is empty or neither lastname/disambiguator provided
        """
        with DatabaseOperation(self.logger, "get_or_create_person"):
            normalized_name = DataValidator.normalize_string(name)
            if not normalized_name:
                raise ValidationError("Person name cannot be empty")

            normalized_lastname = DataValidator.normalize_string(lastname)
            normalized_disambiguator = DataValidator.normalize_string(disambiguator)

            # Generate slug for lookup
            slug = Person.generate_slug(
                normalized_name, normalized_lastname, normalized_disambiguator
            )

            # Try to get by slug
            person = self.get(slug=slug)
            if person:
                return person

            # Person doesn't exist - create it
            metadata: Dict[str, Any] = {
                "name": normalized_name,
                "lastname": normalized_lastname,
                "disambiguator": normalized_disambiguator,
            }
            metadata.update(extra_fields)

            return self.create(metadata)

    def update(self, person: Person, metadata: Dict[str, Any]) -> Person:
        """
        Update an existing person.

        Args:
            person: Person object to update
            metadata: Dictionary with optional keys:
                - name: Updated primary name
                - alias: Updated alias
                - lastname: Updated last name
                - relation_type: Updated RelationType
                - entries: List of entries (incremental by default)
                - scenes: List of scenes (incremental by default)
                - threads: List of threads (incremental by default)
                - remove_entries, remove_scenes, remove_threads

        Returns:
            Updated Person object

        Raises:
            DatabaseError: If person not found or is deleted
            DatabaseError: If new alias conflicts with existing
        """
        with DatabaseOperation(self.logger, "update_person"):
            # Ensure exists and not deleted
            db_person = self.session.get(Person, person.id)
            if db_person is None:
                raise DatabaseError(f"Person with id={person.id} not found")
            if db_person.deleted_at:
                raise DatabaseError(f"Cannot update deleted person: {db_person.name}")

            # Attach to session
            person = self.session.merge(db_person)

            # Update name
            if "name" in metadata:
                new_name = DataValidator.normalize_string(metadata["name"])
                if new_name:
                    person.name = new_name

            # Update slug
            if "slug" in metadata:
                new_slug = DataValidator.normalize_string(metadata["slug"])
                if new_slug and new_slug != person.slug:
                    # Check uniqueness
                    existing = self.get(slug=new_slug, include_deleted=True)
                    if existing and existing.id != person.id:
                        raise DatabaseError(
                            f"Slug '{new_slug}' already used by another person"
                        )
                    person.slug = new_slug

            # Update lastname
            if "lastname" in metadata:
                person.lastname = DataValidator.normalize_string(metadata["lastname"])

            # Update relation_type
            if "relation_type" in metadata:
                relation_type = DataValidator.normalize_enum(
                    metadata["relation_type"], RelationType, "relation_type"
                )
                if relation_type:
                    person.relation_type = relation_type  # type: ignore[assignment]

            # Update relationships
            self._update_person_relationships(person, metadata, incremental=True)

            return person

    def delete(
        self,
        person: Union[Person, int],
        deleted_by: Optional[str] = None,
        reason: Optional[str] = None,
        hard_delete: bool = False,
    ) -> None:
        """
        Delete a person (soft delete by default).

        Args:
            person: Person object or ID to delete
            deleted_by: Identifier of who is deleting
            reason: Reason for deletion
            hard_delete: If True, permanently delete instead of soft delete

        Notes:
            - Soft delete preserves the person but hides from queries
            - Hard delete removes person (cascade handles relationships)
            - Relationships (entries, scenes) are preserved with soft delete
        """
        with DatabaseOperation(self.logger, "delete_person"):
            # Handle int ID lookup
            if isinstance(person, int):
                fetched = self.get(person_id=person, include_deleted=True)
                if not fetched:
                    raise DatabaseError(f"Person not found with id: {person}")
                person = fetched

            person_name = person.display_name

            if not hard_delete:
                # Soft delete
                safe_logger(self.logger).log_debug(
                    f"Soft deleting person: {person_name}",
                    {"id": person.id, "deleted_by": deleted_by, "reason": reason},
                )
                person.soft_delete(deleted_by=deleted_by, reason=reason)
            else:
                # Hard delete
                safe_logger(self.logger).log_debug(
                    f"Hard deleting person: {person_name}",
                    {"id": person.id},
                )
                self.session.delete(person)

            self.session.flush()

    def restore(self, person: Union[Person, int]) -> Person:
        """
        Restore a soft-deleted person.

        Args:
            person: Person object or ID to restore

        Returns:
            Restored Person object

        Raises:
            DatabaseError: If person not found or not deleted
        """
        with DatabaseOperation(self.logger, "restore_person"):
            # Handle int ID lookup
            if isinstance(person, int):
                fetched = self.get(person_id=person, include_deleted=True)
                if not fetched:
                    raise DatabaseError(f"Person not found with id: {person}")
                person = fetched

            # Validate deletion status
            if not person.deleted_at:
                raise DatabaseError(f"Person is not deleted: {person.display_name}")

            # Restore
            person.restore()
            self.session.flush()

            safe_logger(self.logger).log_debug(
                f"Restored person: {person.display_name}",
                {"id": person.id},
            )

            return person

    def add_aliases(self, person: Person, aliases: List[str]) -> None:
        """
        Add aliases to a person, skipping duplicates.

        Normalizes each alias and creates PersonAlias records for any
        that don't already exist on the person.

        Args:
            person: Person entity to add aliases to
            aliases: List of alias strings to add

        Notes:
            - Duplicate detection is case-insensitive
            - Whitespace is normalized before comparison
        """
        with DatabaseOperation(self.logger, "add_aliases"):
            existing = {a.alias.lower() for a in person.aliases}

            for alias in aliases:
                normalized = DataValidator.normalize_string(alias)
                if not normalized:
                    continue
                if normalized.lower() in existing:
                    continue

                person.aliases.append(PersonAlias(alias=normalized))
                existing.add(normalized.lower())

            self.session.flush()

    def _update_person_relationships(
        self,
        person: Person,
        metadata: Dict[str, Any],
        incremental: bool = True,
    ) -> None:
        """
        Update relationships for a person.

        Args:
            person: Person to update
            metadata: Metadata with relationship keys
            incremental: Add incrementally (True) or replace all (False)
        """
        relationship_configs = [
            ("entries", "entries", Entry),
            ("scenes", "scenes", Scene),
            ("threads", "threads", Thread),
        ]

        for meta_key, attr_name, model_class in relationship_configs:
            if meta_key not in metadata:
                continue

            items = metadata[meta_key]
            remove_items = metadata.get(f"remove_{meta_key}", [])
            collection = getattr(person, attr_name)

            if not incremental:
                # Replacement mode: clear and add all
                collection.clear()

            # Add items
            for item in items:
                resolved = self._resolve_object(item, model_class)
                if resolved and resolved not in collection:
                    collection.append(resolved)

            if incremental:
                # Remove specified items
                for item in remove_items:
                    resolved = self._resolve_object(item, model_class)
                    if resolved and resolved in collection:
                        collection.remove(resolved)

        self.session.flush()

    # =========================================================================
    # QUERY METHODS
    # =========================================================================

    def find_by_slug_or_name(
        self,
        identifier: str,
        include_deleted: bool = False,
    ) -> Optional[Person]:
        """
        Find a person by slug or name.

        Tries slug first, then name.

        Args:
            identifier: Slug or name to search for
            include_deleted: Whether to include soft-deleted persons

        Returns:
            Person object if found, None otherwise
        """
        with DatabaseOperation(self.logger, "find_person_by_slug_or_name"):
            normalized = DataValidator.normalize_string(identifier)
            if not normalized:
                return None

            # Try slug first
            person = self.get(slug=normalized, include_deleted=include_deleted)
            if person:
                return person

            # Try name
            return self.get(name=normalized, include_deleted=include_deleted)

    def get_by_relation_type(
        self,
        relation_type: Union[RelationType, str],
        include_deleted: bool = False,
    ) -> List[Person]:
        """
        Get all persons with a specific relation type.

        Args:
            relation_type: RelationType enum or string value
            include_deleted: Whether to include soft-deleted persons

        Returns:
            List of Person objects, ordered by name
        """
        with DatabaseOperation(self.logger, "get_persons_by_relation"):
            # Normalize type
            normalized_type = DataValidator.normalize_enum(
                relation_type if isinstance(relation_type, str) else relation_type.value,
                RelationType,
                "relation_type",
            )

            if normalized_type is None:
                return []

            query = self.session.query(Person).filter_by(relation_type=normalized_type)

            if not include_deleted:
                query = query.filter(Person.deleted_at.is_(None))

            return query.order_by(Person.name).all()

    def search(
        self,
        query_text: str,
        include_deleted: bool = False,
    ) -> List[Person]:
        """
        Search persons by name, lastname, or alias.

        Args:
            query_text: Text to search for (case-insensitive partial match)
            include_deleted: Whether to include soft-deleted persons

        Returns:
            List of matching Person objects
        """
        with DatabaseOperation(self.logger, "search_persons"):
            normalized = DataValidator.normalize_string(query_text)
            if not normalized:
                return []

            pattern = f"%{normalized}%"

            query = self.session.query(Person).filter(
                (Person.name.ilike(pattern)) |
                (Person.lastname.ilike(pattern)) |
                (Person.slug.ilike(pattern))
            )

            if not include_deleted:
                query = query.filter(Person.deleted_at.is_(None))

            return query.order_by(Person.name).all()
