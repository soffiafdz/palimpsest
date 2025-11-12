"""
test_person_manager.py
----------------------
Unit tests for PersonManager CRUD operations and name disambiguation.

Tests person management including the complex name_fellow logic for handling
multiple people with the same name.

Target Coverage: 90%+
"""
import pytest
from datetime import datetime
from dev.database.models import Person, Alias, RelationType
from dev.core.exceptions import ValidationError, DatabaseError


class TestPersonManagerExists:
    """Test PersonManager.exists() method."""

    def test_exists_returns_false_when_not_found(self, person_manager):
        """Test exists returns False for non-existent person."""
        assert person_manager.exists(person_name="NonExistent") is False

    def test_exists_by_name_returns_true(self, person_manager, db_session):
        """Test exists returns True when person exists by name."""
        person_manager.create({"name": "Alice"})
        db_session.commit()

        assert person_manager.exists(person_name="Alice") is True

    def test_exists_by_full_name_returns_true(self, person_manager, db_session):
        """Test exists by full_name."""
        person_manager.create({"name": "Bob", "full_name": "Robert Smith"})
        db_session.commit()

        assert person_manager.exists(person_full_name="Robert Smith") is True

    def test_exists_excludes_deleted_by_default(self, person_manager, db_session):
        """Test exists excludes soft-deleted persons by default."""
        person = person_manager.create({"name": "Charlie"})
        db_session.commit()
        person_manager.delete(person, deleted_by="test")
        db_session.commit()

        assert person_manager.exists(person_name="Charlie") is False

    def test_exists_includes_deleted_when_requested(self, person_manager, db_session):
        """Test exists includes soft-deleted persons when requested."""
        person = person_manager.create({"name": "Dave"})
        db_session.commit()
        person_manager.delete(person, deleted_by="test")
        db_session.commit()

        assert person_manager.exists(person_name="Dave", include_deleted=True) is True


class TestPersonManagerGet:
    """Test PersonManager.get() method."""

    def test_get_returns_none_when_not_found(self, person_manager):
        """Test get returns None for non-existent person."""
        result = person_manager.get(person_name="NonExistent")
        assert result is None

    def test_get_by_name(self, person_manager, db_session):
        """Test get person by name."""
        created = person_manager.create({"name": "Alice"})
        db_session.commit()

        result = person_manager.get(person_name="Alice")
        assert result is not None
        assert result.id == created.id
        assert result.name == "Alice"

    def test_get_by_full_name(self, person_manager, db_session):
        """Test get person by full_name."""
        person_manager.create({"name": "Bob", "full_name": "Robert Smith"})
        db_session.commit()

        result = person_manager.get(person_full_name="Robert Smith")
        assert result is not None
        assert result.full_name == "Robert Smith"

    def test_get_by_id(self, person_manager, db_session):
        """Test get person by ID."""
        created = person_manager.create({"name": "Charlie"})
        db_session.commit()

        result = person_manager.get(person_id=created.id)
        assert result is not None
        assert result.id == created.id

    def test_get_excludes_deleted_by_default(self, person_manager, db_session):
        """Test get excludes soft-deleted persons by default."""
        person = person_manager.create({"name": "Dave"})
        db_session.commit()
        person_manager.delete(person, deleted_by="test")
        db_session.commit()

        result = person_manager.get(person_name="Dave")
        assert result is None

    def test_get_includes_deleted_when_requested(self, person_manager, db_session):
        """Test get includes soft-deleted persons when requested."""
        person = person_manager.create({"name": "Eve"})
        db_session.commit()
        person_manager.delete(person, deleted_by="test")
        db_session.commit()

        result = person_manager.get(person_name="Eve", include_deleted=True)
        assert result is not None

    def test_get_raises_error_when_name_ambiguous(self, person_manager, db_session):
        """Test get raises error when multiple people have same name."""
        # Create two people with same name
        person_manager.create({"name": "Alice", "full_name": "Alice Johnson"})
        person_manager.create({"name": "Alice", "full_name": "Alice Smith"})
        db_session.commit()

        with pytest.raises(ValidationError) as exc_info:
            person_manager.get(person_name="Alice")
        assert "multiple" in str(exc_info.value).lower()


class TestPersonManagerGetAll:
    """Test PersonManager.get_all() method."""

    def test_get_all_empty(self, person_manager):
        """Test get_all returns empty list when no persons."""
        result = person_manager.get_all()
        assert result == []

    def test_get_all_returns_all_persons(self, person_manager, db_session):
        """Test get_all returns all active persons."""
        person_manager.create({"name": "Alice"})
        person_manager.create({"name": "Bob"})
        person_manager.create({"name": "Charlie"})
        db_session.commit()

        result = person_manager.get_all()
        assert len(result) == 3
        names = {p.name for p in result}
        assert names == {"Alice", "Bob", "Charlie"}

    def test_get_all_excludes_deleted_by_default(self, person_manager, db_session):
        """Test get_all excludes soft-deleted persons."""
        person_manager.create({"name": "Alice"})
        person = person_manager.create({"name": "Bob"})
        db_session.commit()
        person_manager.delete(person, deleted_by="test")
        db_session.commit()

        result = person_manager.get_all()
        assert len(result) == 1
        assert result[0].name == "Alice"


class TestPersonManagerCreate:
    """Test PersonManager.create() method."""

    def test_create_minimal_person(self, person_manager, db_session):
        """Test creating person with minimal fields."""
        person = person_manager.create({"name": "Alice"})

        assert person is not None
        assert person.id is not None
        assert person.name == "Alice"
        assert person.full_name is None
        assert person.name_fellow is False

    def test_create_person_with_full_name(self, person_manager, db_session):
        """Test creating person with full_name."""
        person = person_manager.create({
            "name": "Bob",
            "full_name": "Robert Smith"
        })

        assert person.name == "Bob"
        assert person.full_name == "Robert Smith"

    def test_create_person_with_relation_type(self, person_manager, db_session):
        """Test creating person with relation_type."""
        person = person_manager.create({
            "name": "Charlie",
            "relation_type": "friend"
        })

        assert person.relation_type == RelationType.FRIEND

    def test_create_person_missing_name_raises_error(self, person_manager):
        """Test creating person without name raises error."""
        with pytest.raises(ValidationError):
            person_manager.create({})

    def test_create_duplicate_name_requires_full_name(self, person_manager, db_session):
        """Test creating second person with same name requires full_name."""
        person_manager.create({"name": "Alice", "full_name": "Alice Johnson"})
        db_session.commit()

        # Try to create another Alice without full_name
        with pytest.raises(ValidationError) as exc_info:
            person_manager.create({"name": "Alice"})
        assert "full_name" in str(exc_info.value).lower()

    def test_create_name_fellows_sets_flag(self, person_manager, db_session):
        """Test creating name_fellows sets flag on both persons."""
        alice1 = person_manager.create({"name": "Alice", "full_name": "Alice Johnson"})
        db_session.commit()

        alice2 = person_manager.create({"name": "Alice", "full_name": "Alice Smith"})
        db_session.commit()

        # Refresh from DB
        db_session.refresh(alice1)
        db_session.refresh(alice2)

        assert alice1.name_fellow is True
        assert alice2.name_fellow is True

    def test_create_duplicate_full_name_raises_error(self, person_manager, db_session):
        """Test creating person with duplicate full_name raises error."""
        person_manager.create({"name": "Alice", "full_name": "Alice Johnson"})
        db_session.commit()

        with pytest.raises(ValidationError) as exc_info:
            person_manager.create({"name": "Alice", "full_name": "Alice Johnson"})
        assert "already exists" in str(exc_info.value).lower()

    def test_create_person_with_empty_name_raises_error(self, person_manager):
        """Test creating person with empty name raises error."""
        with pytest.raises(ValidationError):
            person_manager.create({"name": ""})


class TestPersonManagerUpdate:
    """Test PersonManager.update() method."""

    def test_update_person_name(self, person_manager, db_session):
        """Test updating person name."""
        person = person_manager.create({"name": "Alice"})
        db_session.commit()

        person_manager.update(person, {"name": "Alicia"})
        db_session.commit()
        db_session.refresh(person)

        assert person.name == "Alicia"

    def test_update_person_full_name(self, person_manager, db_session):
        """Test updating person full_name."""
        person = person_manager.create({"name": "Bob"})
        db_session.commit()

        person_manager.update(person, {"full_name": "Robert Smith"})
        db_session.commit()
        db_session.refresh(person)

        assert person.full_name == "Robert Smith"

    def test_update_person_relation_type(self, person_manager, db_session):
        """Test updating person relation_type."""
        person = person_manager.create({"name": "Charlie"})
        db_session.commit()

        person_manager.update(person, {"relation_type": "family"})
        db_session.commit()
        db_session.refresh(person)

        assert person.relation_type == RelationType.FAMILY

    def test_update_nonexistent_person_raises_error(self, person_manager):
        """Test updating non-existent person raises error."""
        fake_person = Person()
        fake_person.id = 99999

        with pytest.raises(DatabaseError):
            person_manager.update(fake_person, {"name": "Test"})

    def test_update_deleted_person_raises_error(self, person_manager, db_session):
        """Test updating deleted person raises error."""
        person = person_manager.create({"name": "Dave"})
        db_session.commit()
        person_manager.delete(person, deleted_by="test")
        db_session.commit()

        with pytest.raises(DatabaseError) as exc_info:
            person_manager.update(person, {"name": "David"})
        assert "deleted" in str(exc_info.value).lower()

    def test_update_name_to_existing_requires_full_name(self, person_manager, db_session):
        """Test changing name to existing name requires full_name."""
        person_manager.create({"name": "Alice", "full_name": "Alice Johnson"})
        person = person_manager.create({"name": "Bob"})
        db_session.commit()

        # Try to change Bob's name to Alice without full_name
        with pytest.raises(ValidationError) as exc_info:
            person_manager.update(person, {"name": "Alice"})
        assert "full_name" in str(exc_info.value).lower()


class TestPersonManagerDelete:
    """Test PersonManager.delete() method."""

    def test_delete_person_soft_delete(self, person_manager, db_session):
        """Test soft deleting a person."""
        person = person_manager.create({"name": "Alice"})
        db_session.commit()

        person_manager.delete(person, deleted_by="admin")
        db_session.commit()
        db_session.refresh(person)

        assert person.deleted_at is not None
        assert person.deleted_by == "admin"

    def test_delete_person_with_reason(self, person_manager, db_session):
        """Test deleting person with reason."""
        person = person_manager.create({"name": "Bob"})
        db_session.commit()

        person_manager.delete(person, deleted_by="admin", reason="Duplicate entry")
        db_session.commit()
        db_session.refresh(person)

        assert person.deleted_at is not None
        assert person.deletion_reason == "Duplicate entry"

    def test_deleted_person_not_in_get(self, person_manager, db_session):
        """Test deleted person not returned by get()."""
        person = person_manager.create({"name": "Charlie"})
        db_session.commit()
        person_manager.delete(person, deleted_by="admin")
        db_session.commit()

        result = person_manager.get(person_name="Charlie")
        assert result is None


class TestPersonManagerRestore:
    """Test PersonManager.restore() method."""

    def test_restore_deleted_person(self, person_manager, db_session):
        """Test restoring a soft-deleted person."""
        person = person_manager.create({"name": "Alice"})
        db_session.commit()
        person_manager.delete(person, deleted_by="admin")
        db_session.commit()

        person_manager.restore(person)
        db_session.commit()
        db_session.refresh(person)

        assert person.deleted_at is None
        assert person.deleted_by is None
        assert person.deletion_reason is None

    def test_restored_person_in_get(self, person_manager, db_session):
        """Test restored person is returned by get()."""
        person = person_manager.create({"name": "Bob"})
        db_session.commit()
        person_manager.delete(person, deleted_by="admin")
        db_session.commit()
        person_manager.restore(person)
        db_session.commit()

        result = person_manager.get(person_name="Bob")
        assert result is not None
        assert result.id == person.id


class TestPersonManagerAliases:
    """Test PersonManager alias methods."""

    def test_add_single_alias(self, person_manager, db_session):
        """Test adding a single alias to person."""
        person = person_manager.create({"name": "Alice"})
        db_session.commit()

        person_manager.add_alias(person, "Ali")
        db_session.commit()
        db_session.refresh(person)

        assert len(person.aliases) >= 1
        alias_names = {a.alias for a in person.aliases}
        assert "Ali" in alias_names

    def test_add_multiple_aliases(self, person_manager, db_session):
        """Test adding multiple aliases at once."""
        person = person_manager.create({"name": "Bob"})
        db_session.commit()

        person_manager.add_aliases(person, ["Bobby", "Rob", "Bert"])
        db_session.commit()
        db_session.refresh(person)

        assert len(person.aliases) >= 3
        alias_names = {a.alias for a in person.aliases}
        assert "Bobby" in alias_names
        assert "Rob" in alias_names
        assert "Bert" in alias_names

    def test_add_duplicate_alias_does_not_error(self, person_manager, db_session):
        """Test adding duplicate alias is handled gracefully."""
        person = person_manager.create({"name": "Charlie"})
        db_session.commit()

        person_manager.add_alias(person, "Chuck")
        db_session.commit()

        # Try to add same alias again
        person_manager.add_alias(person, "Chuck")
        db_session.commit()

        # Should only have one "Chuck"
        alias_names = [a.alias for a in person.aliases]
        assert alias_names.count("Chuck") == 1


class TestPersonManagerEdgeCases:
    """Test edge cases and special scenarios."""

    def test_create_person_with_whitespace_name_normalized(self, person_manager, db_session):
        """Test person name with whitespace is normalized."""
        person = person_manager.create({"name": "  Alice  "})

        assert person.name == "Alice"

    def test_get_person_case_sensitive(self, person_manager, db_session):
        """Test person lookup is case-sensitive."""
        person_manager.create({"name": "Alice"})
        db_session.commit()

        # Should not find "alice"
        result = person_manager.get(person_name="alice")
        assert result is None

    def test_create_person_with_unicode_name(self, person_manager, db_session):
        """Test creating person with unicode characters."""
        person = person_manager.create({"name": "François"})

        assert person.name == "François"

    def test_create_person_with_hyphenated_name(self, person_manager, db_session):
        """Test creating person with hyphenated name."""
        person = person_manager.create({"name": "Jean-Pierre"})

        assert person.name == "Jean-Pierre"

    def test_get_all_ordered_by_name(self, person_manager, db_session):
        """Test get_all returns persons ordered by name."""
        person_manager.create({"name": "Charlie"})
        person_manager.create({"name": "Alice"})
        person_manager.create({"name": "Bob"})
        db_session.commit()

        result = person_manager.get_all()
        names = [p.name for p in result]

        assert names == ["Alice", "Bob", "Charlie"]
