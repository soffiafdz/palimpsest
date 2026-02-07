#!/usr/bin/env python3
"""
character_manager.py
--------------------
Manages Character and PersonCharacterMap entities.

Characters are fictional personas in the manuscript that may be based on
real people from the journal. The PersonCharacterMap tracks the relationship
between people and characters with contribution type metadata.

Key Features:
    - CRUD for Character with role and narrator flag
    - PersonCharacterMap management (link/unlink person to character)
    - Query characters by chapter or by person
    - Contribution type tracking (primary, composite, inspiration)

Usage:
    mgr = CharacterManager(session, logger)

    # Create character
    char = mgr.create({"name": "Sofia", "role": "protagonist", "is_narrator": True})

    # Link person to character
    mgr.link_person(char, person_id=1, contribution="primary")

    # Query
    chars = mgr.get_by_chapter(chapter_id=3)
    chars = mgr.get_by_person(person_id=1)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from typing import Any, Dict, List, Optional

# --- Third party imports ---
from sqlalchemy.orm import Session

# --- Local imports ---
from dev.core.exceptions import DatabaseError, ValidationError
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.core.validators import DataValidator
from dev.database.decorators import DatabaseOperation
from dev.database.models import (
    Chapter,
    Character,
    Person,
    PersonCharacterMap,
)
from dev.database.models.enums import ContributionType

from .entity_manager import EntityManager, EntityManagerConfig


# Configuration for Character entity
CHARACTER_CONFIG = EntityManagerConfig(
    model_class=Character,
    name_field="name",
    display_name="character",
    supports_soft_delete=False,
    order_by="name",
    scalar_fields=[
        ("name", DataValidator.normalize_string),
        ("description", lambda x: x, True),
        ("role", lambda x: x, True),
    ],
    relationships=[],
)


class CharacterManager(EntityManager):
    """
    Manages Character entities and their person mappings.

    Inherits EntityManager for Character CRUD and adds operations for
    PersonCharacterMap and character queries.
    """

    def __init__(
        self,
        session: Session,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize the character manager.

        Args:
            session: SQLAlchemy session
            logger: Optional logger for operation tracking
        """
        super().__init__(session, logger, CHARACTER_CONFIG)

    # =========================================================================
    # Character Hooks
    # =========================================================================

    def _validate_create(self, metadata: Dict[str, Any]) -> None:
        """
        Validate character creation metadata.

        Args:
            metadata: Must include 'name'

        Raises:
            ValidationError: If name is missing
        """
        DataValidator.validate_required_fields(metadata, ["name"])

    def _create_entity(self, metadata: Dict[str, Any], name: str) -> Character:
        """
        Create a Character with role and narrator flag.

        Args:
            metadata: Character creation data
            name: Normalized name

        Returns:
            New Character instance
        """
        return Character(
            name=name,
            description=metadata.get("description"),
            role=metadata.get("role"),
            is_narrator=metadata.get("is_narrator", False),
        )

    # =========================================================================
    # PersonCharacterMap Operations
    # =========================================================================

    def link_person(
        self,
        character: Character,
        person_id: int,
        contribution: str = "primary",
        notes: Optional[str] = None,
    ) -> PersonCharacterMap:
        """
        Link a person to a character with contribution type.

        Args:
            character: Target character
            person_id: Person to link
            contribution: Contribution type (primary, composite, inspiration)
            notes: Optional notes about the mapping

        Returns:
            Created PersonCharacterMap

        Raises:
            DatabaseError: If person not found or already linked
        """
        with DatabaseOperation(self.logger, "link_person_character"):
            person = self._get_by_id(Person, person_id)
            if not person:
                raise DatabaseError(f"Person with id={person_id} not found")

            # Check for existing mapping
            existing = (
                self.session.query(PersonCharacterMap)
                .filter_by(person_id=person_id, character_id=character.id)
                .first()
            )
            if existing:
                raise DatabaseError(
                    f"Person {person_id} already linked to character {character.id}"
                )

            contribution_type = self._resolve_contribution(contribution)

            mapping = PersonCharacterMap(
                person_id=person_id,
                character_id=character.id,
                contribution=contribution_type,
                notes=notes,
            )
            self.session.add(mapping)
            self.session.flush()

            safe_logger(self.logger).log_debug(
                f"Linked person {person_id} to character {character.name}",
                {"contribution": contribution_type.value},
            )
            return mapping

    def unlink_person(self, character: Character, person_id: int) -> None:
        """
        Unlink a person from a character.

        Args:
            character: Target character
            person_id: Person to unlink
        """
        with DatabaseOperation(self.logger, "unlink_person_character"):
            mapping = (
                self.session.query(PersonCharacterMap)
                .filter_by(person_id=person_id, character_id=character.id)
                .first()
            )
            if mapping:
                self.session.delete(mapping)
                self.session.flush()

    def update_person_mapping(
        self,
        character: Character,
        person_id: int,
        contribution: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> PersonCharacterMap:
        """
        Update an existing person-character mapping.

        Args:
            character: Target character
            person_id: Person in the mapping
            contribution: New contribution type
            notes: New notes

        Returns:
            Updated PersonCharacterMap

        Raises:
            DatabaseError: If mapping not found
        """
        with DatabaseOperation(self.logger, "update_person_character_mapping"):
            mapping = (
                self.session.query(PersonCharacterMap)
                .filter_by(person_id=person_id, character_id=character.id)
                .first()
            )
            if not mapping:
                raise DatabaseError(
                    f"No mapping between person {person_id} and "
                    f"character {character.id}"
                )

            if contribution is not None:
                mapping.contribution = self._resolve_contribution(contribution)
            if notes is not None:
                mapping.notes = notes

            self.session.flush()
            return mapping

    # =========================================================================
    # Query Operations
    # =========================================================================

    def get_by_chapter(self, chapter_id: int) -> List[Character]:
        """
        Get all characters in a chapter.

        Args:
            chapter_id: Chapter ID

        Returns:
            List of Character instances
        """
        with DatabaseOperation(self.logger, "get_characters_by_chapter"):
            chapter = self._get_by_id(Chapter, chapter_id)
            if not chapter:
                return []
            return list(chapter.characters)

    def get_by_person(self, person_id: int) -> List[Character]:
        """
        Get all characters based on a person.

        Args:
            person_id: Person ID

        Returns:
            List of Character instances linked to this person
        """
        with DatabaseOperation(self.logger, "get_characters_by_person"):
            mappings = (
                self.session.query(PersonCharacterMap)
                .filter_by(person_id=person_id)
                .all()
            )
            return [m.character for m in mappings]

    def get_person_mappings(self, character: Character) -> List[PersonCharacterMap]:
        """
        Get all person mappings for a character.

        Args:
            character: Target character

        Returns:
            List of PersonCharacterMap instances
        """
        with DatabaseOperation(self.logger, "get_person_mappings"):
            return (
                self.session.query(PersonCharacterMap)
                .filter_by(character_id=character.id)
                .all()
            )

    # =========================================================================
    # Helpers
    # =========================================================================

    @staticmethod
    def _resolve_contribution(value: str) -> ContributionType:
        """
        Resolve a contribution type string to enum.

        Args:
            value: Contribution type string

        Returns:
            ContributionType enum value

        Raises:
            ValidationError: If value is invalid
        """
        if isinstance(value, ContributionType):
            return value
        try:
            return ContributionType(value)
        except (ValueError, KeyError):
            try:
                return ContributionType[value.upper()]
            except (KeyError, AttributeError):
                raise ValidationError(
                    f"Invalid contribution type: {value}. "
                    f"Valid: {[e.value for e in ContributionType]}"
                )
