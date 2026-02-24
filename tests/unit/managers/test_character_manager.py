#!/usr/bin/env python3
"""
test_character_manager.py
-------------------------
Tests for CharacterManager — character CRUD, person-character mappings, and queries.

Usage:
    python -m pytest tests/unit/managers/test_character_manager.py -v
"""
# --- Annotations ---
from __future__ import annotations

# --- Third-party imports ---
import pytest

# --- Local imports ---
from dev.database.managers.character_manager import CharacterManager
from dev.database.models import (
    Character,
    Chapter,
    Person,
    PersonCharacterMap,
)
from dev.database.models.enums import ContributionType


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def character_manager(db_session):
    """Create CharacterManager instance for testing."""
    return CharacterManager(db_session)


@pytest.fixture
def sample_character(character_manager):
    """Create a sample character."""
    return character_manager.create(
        {"name": "Sofia", "role": "protagonist", "is_narrator": True}
    )


@pytest.fixture
def sample_person(db_session):
    """Create a sample person."""
    person = Person(
        name="Maria",
        lastname="Garcia",
        slug=Person.generate_slug("Maria", "Garcia"),
    )
    db_session.add(person)
    db_session.flush()
    return person


@pytest.fixture
def second_person(db_session):
    """Create a second person for multi-mapping tests."""
    person = Person(
        name="Ana",
        lastname="Lopez",
        slug=Person.generate_slug("Ana", "Lopez"),
    )
    db_session.add(person)
    db_session.flush()
    return person


@pytest.fixture
def sample_chapter(db_session):
    """Create a sample chapter for query tests."""
    chapter = Chapter(title="The Gray Fence")
    db_session.add(chapter)
    db_session.flush()
    return chapter


# =========================================================================
# Test Classes
# =========================================================================


class TestCharacterCreate:
    """Test character creation."""

    def test_create_basic(self, character_manager):
        """Create character with just name."""
        char = character_manager.create({"name": "Clara"})
        assert char.name == "Clara"
        assert char.is_narrator is False

    def test_create_with_role(self, character_manager):
        """Create character with role."""
        char = character_manager.create({"name": "Majo", "role": "friend"})
        assert char.role == "friend"

    def test_create_narrator(self, character_manager):
        """Create character as narrator."""
        char = character_manager.create(
            {"name": "Sofia", "is_narrator": True}
        )
        assert char.is_narrator is True

    def test_create_with_description(self, character_manager):
        """Create character with description."""
        char = character_manager.create(
            {"name": "Bea", "description": "A fleeting presence"}
        )
        assert char.description == "A fleeting presence"

    def test_create_duplicate_raises(self, character_manager):
        """Creating duplicate character raises error."""
        character_manager.create({"name": "Unique"})
        with pytest.raises(Exception):
            character_manager.create({"name": "Unique"})

    def test_create_missing_name_raises(self, character_manager):
        """Creating character without name raises ValidationError."""
        with pytest.raises(Exception):
            character_manager.create({})


class TestCharacterUpdate:
    """Test character field updates."""

    def test_update_role(self, character_manager, sample_character):
        """Update character role."""
        updated = character_manager.update(
            sample_character, {"role": "antagonist"}
        )
        assert updated.role == "antagonist"

    def test_update_description(self, character_manager, sample_character):
        """Update character description."""
        updated = character_manager.update(
            sample_character, {"description": "A complex narrator"}
        )
        assert updated.description == "A complex narrator"

    def test_update_name(self, character_manager, sample_character):
        """Update character name."""
        updated = character_manager.update(
            sample_character, {"name": "Sofía"}
        )
        assert updated.name == "Sofía"


class TestPersonCharacterMap:
    """Test person-character mapping operations."""

    def test_link_person(self, character_manager, sample_character, sample_person):
        """Link person to character."""
        mapping = character_manager.link_person(
            sample_character, sample_person.id, contribution="primary"
        )
        assert mapping.person_id == sample_person.id
        assert mapping.character_id == sample_character.id
        assert mapping.contribution == ContributionType.PRIMARY

    def test_link_person_with_notes(
        self, character_manager, sample_character, sample_person
    ):
        """Link person with notes."""
        mapping = character_manager.link_person(
            sample_character,
            sample_person.id,
            contribution="inspiration",
            notes="Loosely based on",
        )
        assert mapping.notes == "Loosely based on"
        assert mapping.contribution == ContributionType.INSPIRATION

    def test_unlink_person(self, character_manager, sample_character, sample_person):
        """Unlink person from character."""
        character_manager.link_person(
            sample_character, sample_person.id
        )
        character_manager.unlink_person(sample_character, sample_person.id)
        mappings = character_manager.get_person_mappings(sample_character)
        assert len(mappings) == 0

    def test_duplicate_link_raises(
        self, character_manager, sample_character, sample_person
    ):
        """Linking same person twice raises error."""
        character_manager.link_person(
            sample_character, sample_person.id
        )
        with pytest.raises(Exception):
            character_manager.link_person(
                sample_character, sample_person.id
            )

    def test_link_nonexistent_person_raises(
        self, character_manager, sample_character
    ):
        """Linking nonexistent person raises error."""
        with pytest.raises(Exception):
            character_manager.link_person(
                sample_character, 9999
            )

    def test_update_mapping_contribution(
        self, character_manager, sample_character, sample_person
    ):
        """Update mapping contribution type."""
        character_manager.link_person(
            sample_character, sample_person.id, contribution="primary"
        )
        updated = character_manager.update_person_mapping(
            sample_character, sample_person.id, contribution="composite"
        )
        assert updated.contribution == ContributionType.COMPOSITE

    def test_update_mapping_notes(
        self, character_manager, sample_character, sample_person
    ):
        """Update mapping notes."""
        character_manager.link_person(
            sample_character, sample_person.id
        )
        updated = character_manager.update_person_mapping(
            sample_character, sample_person.id, notes="Updated notes"
        )
        assert updated.notes == "Updated notes"

    def test_update_nonexistent_mapping_raises(
        self, character_manager, sample_character, sample_person
    ):
        """Updating nonexistent mapping raises error."""
        with pytest.raises(Exception):
            character_manager.update_person_mapping(
                sample_character, sample_person.id, contribution="primary"
            )

    def test_multiple_persons_per_character(
        self, character_manager, sample_character, sample_person, second_person
    ):
        """Multiple persons can be linked to one character."""
        character_manager.link_person(
            sample_character, sample_person.id, contribution="primary"
        )
        character_manager.link_person(
            sample_character, second_person.id, contribution="inspiration"
        )
        mappings = character_manager.get_person_mappings(sample_character)
        assert len(mappings) == 2


class TestCharacterQuery:
    """Test character query operations."""

    def test_get_by_chapter(
        self, character_manager, sample_character, sample_chapter
    ):
        """Get characters by chapter."""
        sample_chapter.characters.append(sample_character)
        results = character_manager.get_by_chapter(sample_chapter.id)
        assert len(results) == 1
        assert results[0].name == "Sofia"

    def test_get_by_chapter_empty(self, character_manager, sample_chapter):
        """Get characters for chapter with none returns empty list."""
        results = character_manager.get_by_chapter(sample_chapter.id)
        assert results == []

    def test_get_by_chapter_nonexistent(self, character_manager):
        """Get characters for nonexistent chapter returns empty list."""
        results = character_manager.get_by_chapter(9999)
        assert results == []

    def test_get_by_person(
        self, character_manager, sample_character, sample_person
    ):
        """Get characters by person."""
        character_manager.link_person(
            sample_character, sample_person.id
        )
        results = character_manager.get_by_person(sample_person.id)
        assert len(results) == 1
        assert results[0].name == "Sofia"

    def test_get_by_person_empty(self, character_manager, sample_person):
        """Get characters for person with no mappings."""
        results = character_manager.get_by_person(sample_person.id)
        assert results == []

    def test_get_person_mappings(
        self, character_manager, sample_character, sample_person
    ):
        """Get person mappings for a character."""
        character_manager.link_person(
            sample_character, sample_person.id, contribution="primary"
        )
        mappings = character_manager.get_person_mappings(sample_character)
        assert len(mappings) == 1
        assert mappings[0].contribution == ContributionType.PRIMARY
