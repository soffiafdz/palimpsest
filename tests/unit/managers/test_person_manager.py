"""
test_person_manager.py
----------------------
Unit tests for PersonManager.add_aliases() method.

Tests alias creation, duplicate detection, and whitespace normalization.
"""
# --- Annotations ---
from __future__ import annotations

# --- Local imports ---
from dev.database.models import Person


class TestPersonManagerAddAliases:
    """Test PersonManager.add_aliases() method."""

    def _create_person(self, db_session, name="Alice", lastname="Smith"):
        """Helper to create a person for testing."""
        person = Person(
            name=name,
            lastname=lastname,
            slug=Person.generate_slug(name, lastname, None),
        )
        db_session.add(person)
        db_session.flush()
        return person

    def test_add_aliases_creates_records(self, person_manager, db_session):
        """Test that add_aliases creates PersonAlias records."""
        person = self._create_person(db_session)

        person_manager.add_aliases(person, ["Ali", "Ally"])
        db_session.commit()
        db_session.refresh(person)

        alias_values = {a.alias for a in person.aliases}
        assert alias_values == {"Ali", "Ally"}

    def test_add_aliases_skips_duplicates(self, person_manager, db_session):
        """Test that add_aliases does not create duplicate aliases."""
        person = self._create_person(db_session)

        # Add initial alias
        person_manager.add_aliases(person, ["Ali"])
        db_session.flush()

        # Try to add same alias again (case-insensitive)
        person_manager.add_aliases(person, ["ali", "ALI", "Ali"])
        db_session.commit()
        db_session.refresh(person)

        assert len(person.aliases) == 1
        assert person.aliases[0].alias == "Ali"

    def test_add_aliases_normalizes_whitespace(self, person_manager, db_session):
        """Test that add_aliases normalizes whitespace in alias strings."""
        person = self._create_person(db_session)

        person_manager.add_aliases(person, ["  Ali  ", " Ally  "])
        db_session.commit()
        db_session.refresh(person)

        alias_values = {a.alias for a in person.aliases}
        assert alias_values == {"Ali", "Ally"}

    def test_add_aliases_skips_empty_strings(self, person_manager, db_session):
        """Test that add_aliases skips empty or whitespace-only strings."""
        person = self._create_person(db_session)

        person_manager.add_aliases(person, ["", "  ", "Valid"])
        db_session.commit()
        db_session.refresh(person)

        assert len(person.aliases) == 1
        assert person.aliases[0].alias == "Valid"

    def test_add_aliases_empty_list(self, person_manager, db_session):
        """Test that add_aliases with empty list is a no-op."""
        person = self._create_person(db_session)

        person_manager.add_aliases(person, [])
        db_session.commit()
        db_session.refresh(person)

        assert len(person.aliases) == 0
