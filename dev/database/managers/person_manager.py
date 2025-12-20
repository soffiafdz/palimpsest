#!/usr/bin/env python3
"""
person_manager.py
--------------------
Manages Person and Alias entities with name disambiguation and soft delete support.

Person represents individuals mentioned in journal entries. The manager handles complex
name disambiguation logic (name_fellow) when multiple people share the same name,
requiring full_name for differentiation.

Key Features:
    - CRUD operations for persons and aliases
    - Name disambiguation with name_fellow flag
    - Soft delete support (preserves data with deleted_at flag)
    - One-to-many relationship (Person → Aliases)
    - M2M relationships with entries, events, and mentioned dates
    - Relationship type categorization (family, friend, romantic, etc.)
    - Alias resolution and management

Usage:
    person_mgr = PersonManager(session, logger)

    # Create person (simple)
    person = person_mgr.create({
        "name": "Alice",
        "relation_type": "friend"
    })

    # Create person with name disambiguation
    person2 = person_mgr.create({
        "name": "Alice",  # Same name!
        "full_name": "Alice Johnson",  # Required due to conflict
        "relation_type": "colleague"
    })  # Both Alices now have name_fellow=True

    # Get person (handles disambiguation)
    alice = person_mgr.get(person_name="Alice")  # Raises error if multiple
    alice_j = person_mgr.get(person_full_name="Alice Johnson")  # Unique lookup

    # Soft delete
    person_mgr.delete(person, deleted_by="admin", reason="Duplicate")

    # Restore
    person_mgr.restore(person)

    # Add aliases
    person_mgr.add_alias(person, "Ali")
    person_mgr.add_aliases(person, ["Allie", "A."])
"""
from typing import Dict, List, Optional, Any, Union, cast
from datetime import datetime, timezone

from dev.core.validators import DataValidator
from dev.core.exceptions import ValidationError, DatabaseError
from dev.database.decorators import (
    handle_db_errors,
    log_database_operation,
    validate_metadata,
)
from dev.database.models import Person, Alias, Entry, Event, Moment, RelationType
from .base_manager import BaseManager


class PersonManager(BaseManager):
    """
    Manages Person and Alias table operations with name disambiguation.

    This manager handles the complex name_fellow logic where multiple people
    can share the same name, requiring full_name for disambiguation.
    """

    # =========================================================================
    # PERSON OPERATIONS
    # =========================================================================

    @handle_db_errors
    @log_database_operation("person_exists")
    def exists(
        self,
        person_name: Optional[str] = None,
        person_full_name: Optional[str] = None,
        include_deleted: bool = False,
    ) -> bool:
        """
        Check if a person exists.

        Args:
            person_name: The person's primary name
            person_full_name: The person's full name (unique)
            include_deleted: Whether to include soft-deleted persons

        Returns:
            True if person exists, False otherwise

        Notes:
            - If both provided, full_name takes precedence
            - Name alone may match multiple people (name_fellows)
        """
        if person_full_name:
            return self._exists(
                Person, "full_name", person_full_name, include_deleted=include_deleted
            )
        if person_name:
            return self._exists(
                Person, "name", person_name, include_deleted=include_deleted
            )
        return False

    @handle_db_errors
    @log_database_operation("get_person")
    def get(
        self,
        person_name: Optional[str] = None,
        person_full_name: Optional[str] = None,
        person_id: Optional[int] = None,
        include_deleted: bool = False,
    ) -> Optional[Person]:
        """
        Retrieve a person by name, full_name, or ID.

        Args:
            person_name: The person's primary name
            person_full_name: The person's full name (unique)
            person_id: The person ID
            include_deleted: Whether to include soft-deleted persons

        Returns:
            Person object if found, None otherwise

        Raises:
            ValidationError: If person_name matches multiple people (name_fellows)

        Notes:
            - Lookup priority: ID > full_name > name
            - If name matches multiple people, raises error requiring full_name
            - By default, soft-deleted persons are excluded
        """
        # ID lookup
        if person_id is not None:
            return self._get_by_id(Person, person_id, include_deleted=include_deleted)

        # Full name lookup (unique)
        if person_full_name is not None:
            return self._get_by_field(
                Person, "full_name", person_full_name, include_deleted=include_deleted
            )

        # Name lookup (may be ambiguous - requires special handling)
        if person_name is not None:
            normalized = DataValidator.normalize_string(person_name)
            if not normalized:
                return None

            query = self.session.query(Person).filter_by(name=normalized)
            if not include_deleted:
                query = query.filter(Person.deleted_at.is_(None))

            count = query.count()
            if count == 0:
                return None
            elif count == 1:
                return query.first()
            else:
                # Multiple people with same name - require full_name
                raise ValidationError(
                    f"Multiple people exist with name '{normalized}'. "
                    f"Use person_full_name for disambiguation."
                )

        return None

    @handle_db_errors
    @log_database_operation("get_all_persons")
    def get_all(self, include_deleted: bool = False) -> List[Person]:
        """
        Retrieve all persons.

        Args:
            include_deleted: Whether to include soft-deleted persons

        Returns:
            List of Person objects, ordered by name
        """
        return self._get_all(Person, order_by="name", include_deleted=include_deleted)

    @handle_db_errors
    @log_database_operation("create_person")
    @validate_metadata(["name"])
    def create(self, metadata: Dict[str, Any]) -> Person:
        """
        Create a new person with name disambiguation.

        Args:
            metadata: Dictionary with required key:
                - name: Primary name (required)
                Optional keys:
                - full_name: Full legal name (required if name_fellows exist)
                - relation_type: RelationType enum or string
                - aliases: List of alias strings
                - events: List of Event objects or IDs
                - entries: List of Entry objects or IDs
                - dates: List of Moment objects or IDs

        Returns:
            Created Person object

        Raises:
            ValidationError: If name is invalid
            ValidationError: If name_fellows exist but full_name not provided
            ValidationError: If full_name already exists

        Notes:
            - Automatically sets name_fellow=True for all people with same name
            - If creating second person with existing name, full_name is required
        """
        # Validate and normalize name
        p_name = DataValidator.normalize_string(metadata.get("name"))
        if not p_name:
            raise ValidationError(f"Invalid person name: {metadata.get('name')}")

        # Normalize full_name
        p_fname = DataValidator.normalize_string(metadata.get("full_name"))

        # Check for name conflicts (name_fellows)
        name_fellows = (
            self.session.query(Person)
            .filter_by(name=p_name)
            .filter(Person.deleted_at.is_(None))
            .all()
        )

        if name_fellows:
            # Name conflict exists - require full_name
            if not p_fname:
                raise ValidationError(
                    f"Person(s) already exist with name '{p_name}'. "
                    f"Provide full_name for disambiguation."
                )

            # Check full_name uniqueness
            for fellow in name_fellows:
                if fellow.full_name == p_fname:
                    raise ValidationError(
                        f"Person already exists with full_name '{p_fname}'"
                    )

            # Merge all name_fellows into session for update
            name_fellows = [self.session.merge(f) for f in name_fellows]

        # Normalize relation_type
        relation_type = DataValidator.normalize_enum(
            metadata.get("relation_type"), RelationType, "relation_type"
        )

        # Create person
        person = Person(
            name=p_name,
            full_name=p_fname,
            relation_type=relation_type,
        )
        self.session.add(person)
        self.session.flush()

        if self.logger:
            self.logger.log_debug(
                f"Created person: {p_name}",
                {
                    "person_id": person.id,
                    "full_name": p_fname,
                    "has_name_fellows": len(name_fellows) > 0,
                },
            )

        # Set name_fellow flag for all people with same name
        if name_fellows:
            name_fellows.append(person)  # Include newly created person
            for fellow in name_fellows:
                fellow.name_fellow = True

            if self.logger:
                self.logger.log_debug(
                    f"Set name_fellow=True for {len(name_fellows)} people named '{p_name}'"
                )

        # Update relationships
        self._update_relationships(person, metadata, incremental=False)

        return person

    @handle_db_errors
    @log_database_operation("get_or_create_person")
    def get_or_create(self, person_name: str, full_name: Optional[str] = None) -> Person:
        """
        Get existing person or create new one if not found.

        This is a convenience method for use when processing YAML metadata that
        contains person names as strings. It handles name disambiguation and
        creates persons with minimal metadata.

        Args:
            person_name: Primary name to search for or create
            full_name: Optional full name (required if name_fellows exist)

        Returns:
            Existing or newly created Person object

        Raises:
            ValidationError: If name is ambiguous and full_name not provided
        """
        normalized_name = DataValidator.normalize_string(person_name)
        if not normalized_name:
            raise ValidationError("Person name cannot be empty")

        # Try to get existing person
        try:
            person = self.get(person_name=normalized_name)
            if person:
                return person
        except ValidationError:
            # Multiple people with same name - need full_name
            if full_name:
                person = self.get(person_full_name=full_name)
                if person:
                    return person
            else:
                raise  # Re-raise ValidationError about ambiguity

        # Person doesn't exist - create it
        metadata: Dict[str, Any] = {"name": normalized_name}
        if full_name:
            metadata["full_name"] = full_name

        return self.create(metadata)

    @handle_db_errors
    @log_database_operation("update_person")
    def update(self, person: Person, metadata: Dict[str, Any]) -> Person:
        """
        Update an existing person.

        Args:
            person: Person object to update
            metadata: Dictionary with optional keys:
                - name: Updated primary name (triggers name_fellow check)
                - full_name: Updated full name
                - relation_type: Updated RelationType
                - aliases: List of aliases (incremental by default)
                - events: List of events (incremental by default)
                - entries: List of entries (incremental by default)
                - dates: List of mentioned dates (incremental by default)
                - remove_aliases, remove_events, remove_entries, remove_dates

        Returns:
            Updated Person object

        Raises:
            DatabaseError: If person not found or is deleted
            ValidationError: If name changed and name_fellows exist but no full_name
        """
        # Ensure exists and not deleted
        db_person = self.session.get(Person, person.id)
        if db_person is None:
            raise DatabaseError(f"Person with id={person.id} not found")
        if db_person.deleted_at:
            raise DatabaseError(f"Cannot update deleted person: {db_person.name}")

        # Attach to session
        person = self.session.merge(db_person)

        # Update name (with name_fellow check)
        if "name" in metadata:
            new_name = DataValidator.normalize_string(metadata["name"])
            if new_name and new_name != person.name:
                # Check if new name creates name_fellows situation
                name_fellows = (
                    self.session.query(Person)
                    .filter_by(name=new_name)
                    .filter(Person.deleted_at.is_(None))
                    .filter(Person.id != person.id)  # Exclude self
                    .all()
                )

                if name_fellows and not person.full_name:
                    raise ValidationError(
                        f"Changing name to '{new_name}' creates name conflict. "
                        f"Provide full_name for disambiguation."
                    )

                person.name = new_name

                # Set name_fellow flags if needed
                if name_fellows:
                    name_fellows.append(person)
                    for fellow in name_fellows:
                        fellow.name_fellow = True

        # Update full_name
        if "full_name" in metadata:
            person.full_name = DataValidator.normalize_string(metadata["full_name"])

        # Update relation_type
        if "relation_type" in metadata:
            relation_type = DataValidator.normalize_enum(
                metadata["relation_type"], RelationType, "relation_type"
            )
            if relation_type:
                person.relation_type = relation_type  # type: ignore[misc]

        # Update relationships
        self._update_relationships(person, metadata, incremental=True)

        return person

    @handle_db_errors
    @log_database_operation("delete_person")
    def delete(
        self,
        person: Person,
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
            - Hard delete removes person and all aliases (cascade)
            - Relationships (entries, events) are preserved with soft delete
        """
        if isinstance(person, int):
            person = self.get(person_id=person, include_deleted=True)
            if not person:
                raise DatabaseError(f"Person not found with id: {person}")

        if hard_delete:
            if self.logger:
                self.logger.log_debug(
                    f"Hard deleting person: {person.display_name}",
                    {
                        "person_id": person.id,
                        "alias_count": len(person.aliases),
                        "entry_count": person.entry_count,
                    },
                )
            self.session.delete(person)
        else:
            if self.logger:
                self.logger.log_debug(
                    f"Soft deleting person: {person.display_name}",
                    {
                        "person_id": person.id,
                        "deleted_by": deleted_by,
                        "reason": reason,
                    },
                )
            person.deleted_at = datetime.now(timezone.utc)
            person.deleted_by = deleted_by
            person.deletion_reason = reason

        self.session.flush()

    @handle_db_errors
    @log_database_operation("restore_person")
    def restore(self, person: Person) -> Person:
        """
        Restore a soft-deleted person.

        Args:
            person: Person object or ID to restore

        Returns:
            Restored Person object

        Raises:
            DatabaseError: If person not found or not deleted
        """
        if isinstance(person, int):
            person = self.get(person_id=person, include_deleted=True)
            if not person:
                raise DatabaseError(f"Person not found with id: {person}")

        if not person.deleted_at:
            raise DatabaseError(f"Person is not deleted: {person.display_name}")

        person.deleted_at = None
        person.deleted_by = None
        person.deletion_reason = None

        self.session.flush()

        if self.logger:
            self.logger.log_debug(
                f"Restored person: {person.display_name}", {"person_id": person.id}
            )

        return person

    def _update_relationships(
        self,
        person: Person,
        metadata: Dict[str, Any],
        incremental: bool = True,
    ) -> None:
        """Update relationships for a person."""
        # Handle aliases specially (one-to-many with string input)
        if "aliases" in metadata:
            self._update_person_aliases(person, metadata, incremental)

        # Many-to-many relationships using base class helper
        super()._update_relationships(
            person,
            metadata,
            [
                ("events", "events", Event),
                ("entries", "entries", Entry),
                ("dates", "dates", Moment),
            ],
            incremental,
        )

    def _update_person_aliases(
        self,
        person: Person,
        metadata: Dict[str, Any],
        incremental: bool,
    ) -> None:
        """
        Update aliases for a person.

        Handles conversion of string aliases to Alias objects.

        Args:
            person: Person to update aliases for
            metadata: Metadata containing 'aliases' key
            incremental: If False, clears existing aliases first
        """
        alias_strs = metadata.get("aliases", [])
        if not alias_strs:
            return

        # Incremental mode: only add new aliases
        if incremental:
            existing_aliases = {a.alias for a in person.aliases}
            for alias_str in alias_strs:
                normalized = DataValidator.normalize_string(alias_str)
                if normalized and normalized not in existing_aliases:
                    alias_obj = Alias(alias=normalized, person=person)
                    self.session.add(alias_obj)
                    person.aliases.append(alias_obj)
        else:
            # Replacement mode: clear all and add new
            # Clear existing aliases (cascade will handle DB deletion)
            person.aliases.clear()
            self.session.flush()

            for alias_str in alias_strs:
                normalized = DataValidator.normalize_string(alias_str)
                if normalized:
                    alias_obj = Alias(alias=normalized, person=person)
                    self.session.add(alias_obj)
                    person.aliases.append(alias_obj)

        self.session.flush()

    # =========================================================================
    # ALIAS OPERATIONS
    # =========================================================================

    @handle_db_errors
    @log_database_operation("get_alias")
    def get_alias(self, alias_id: int) -> Optional[Alias]:
        """
        Retrieve an alias by ID.

        Args:
            alias_id: The alias ID

        Returns:
            Alias object if found, None otherwise
        """
        return self.session.get(Alias, alias_id)

    @handle_db_errors
    @log_database_operation("add_alias")
    def add_alias(self, person: Person, alias_name: str) -> Alias:
        """
        Add a single alias to a person.

        Args:
            person: Person object
            alias_name: Alias string to add

        Returns:
            Created Alias object

        Raises:
            ValueError: If person is not persisted
            ValidationError: If alias_name is empty
        """
        if person.id is None:
            raise ValueError("Person must be persisted before adding aliases")

        normalized = DataValidator.normalize_string(alias_name)
        if not normalized:
            raise ValidationError("Alias cannot be empty")

        # Check if alias already exists for this person
        for existing in person.aliases:
            if existing.alias == normalized:
                if self.logger:
                    self.logger.log_debug(
                        f"Alias '{normalized}' already exists for {person.display_name}"
                    )
                return existing

        # Create new alias
        alias_obj = Alias(alias=normalized, person=person)
        self.session.add(alias_obj)
        self.session.flush()

        if self.logger:
            self.logger.log_debug(
                f"Added alias '{normalized}' to {person.display_name}",
                {"alias_id": alias_obj.id, "person_id": person.id},
            )

        return alias_obj

    @handle_db_errors
    @log_database_operation("add_aliases")
    def add_aliases(self, person: Person, alias_names: List[str]) -> List[Alias]:
        """
        Add multiple aliases to a person.

        Args:
            person: Person object
            alias_names: List of alias strings

        Returns:
            List of Alias objects (created or existing)
        """
        aliases = []
        for alias_name in alias_names:
            try:
                alias = self.add_alias(person, alias_name)
                aliases.append(alias)
            except ValidationError:
                # Skip empty/invalid aliases
                continue

        return aliases

    @handle_db_errors
    @log_database_operation("remove_alias")
    def remove_alias(self, person: Person, alias_name: str) -> bool:
        """
        Remove an alias from a person.

        Args:
            person: Person object
            alias_name: Alias string to remove

        Returns:
            True if alias was removed, False if not found
        """
        normalized = DataValidator.normalize_string(alias_name)
        if not normalized:
            return False

        for alias_obj in person.aliases:
            if alias_obj.alias == normalized:
                self.session.delete(alias_obj)
                self.session.flush()

                if self.logger:
                    self.logger.log_debug(
                        f"Removed alias '{normalized}' from {person.display_name}",
                        {"person_id": person.id},
                    )
                return True

        return False

    # =========================================================================
    # QUERY METHODS
    # =========================================================================

    @handle_db_errors
    @log_database_operation("get_aliases_for_person")
    def get_aliases_for_person(self, person: Person) -> List[Alias]:
        """
        Get all aliases for a person.

        Args:
            person: Person object

        Returns:
            List of Alias objects, ordered by alias string
        """
        return sorted(person.aliases, key=lambda a: a.alias)

    @handle_db_errors
    @log_database_operation("find_person_by_alias")
    def find_person_by_alias(
        self, alias_name: str, include_deleted: bool = False
    ) -> Optional[Person]:
        """
        Find a person by one of their aliases.

        Args:
            alias_name: Alias to search for
            include_deleted: Whether to include soft-deleted persons

        Returns:
            Person object if found, None otherwise
        """
        normalized = DataValidator.normalize_string(alias_name)
        if not normalized:
            return None

        alias_obj = (
            self.session.query(Alias).filter_by(alias=normalized).first()
        )

        if not alias_obj:
            return None

        person = alias_obj.person

        if not include_deleted and person.deleted_at:
            return None

        return person

    @handle_db_errors
    @log_database_operation("get_persons_by_relation")
    def get_by_relation_type(
        self, relation_type: Union[RelationType, str], include_deleted: bool = False
    ) -> List[Person]:
        """
        Get all persons with a specific relation type.

        Args:
            relation_type: RelationType enum or string value
            include_deleted: Whether to include soft-deleted persons

        Returns:
            List of Person objects, ordered by name
        """
        # Normalize type
        normalized_type: Optional[RelationType] = None
        if isinstance(relation_type, str):
            enum_result = DataValidator.normalize_enum(
                relation_type, RelationType, "relation_type"
            )
            if enum_result is not None:
                normalized_type = cast(RelationType, enum_result)
        else:
            normalized_type = relation_type

        if normalized_type is None:
            return []

        query = self.session.query(Person).filter_by(relation_type=normalized_type)

        if not include_deleted:
            query = query.filter(Person.deleted_at.is_(None))

        return query.order_by(Person.name).all()

    @handle_db_errors
    @log_database_operation("get_name_fellows")
    def get_name_fellows(self, person_name: str) -> List[Person]:
        """
        Get all persons with a specific name (name_fellows).

        Args:
            person_name: Name to search for

        Returns:
            List of Person objects sharing this name (excluding deleted)
        """
        normalized = DataValidator.normalize_string(person_name)
        if not normalized:
            return []

        return (
            self.session.query(Person)
            .filter_by(name=normalized)
            .filter(Person.deleted_at.is_(None))
            .order_by(Person.full_name)
            .all()
        )
