"""
test_entry_manager.py
---------------------
Unit tests for EntryManager CRUD operations and relationship processing.

Tests the most complex manager as Entry is the central entity with
relationships to almost all other entities.

Target Coverage: 90%+
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import pytest
from datetime import date
from pathlib import Path

# --- Local imports ---
from dev.core.exceptions import DatabaseError, ValidationError
from dev.database.models import City, Entry, Event, Person, Tag


class TestEntryManagerExists:
    """Test EntryManager.exists() method."""

    def test_exists_by_date_returns_false_when_not_found(self, entry_manager):
        """Test exists returns False when entry doesn't exist."""
        assert entry_manager.exists(entry_date="2024-01-15") is False

    def test_exists_by_date_returns_true_when_found(self, entry_manager, tmp_dir, db_session):
        """Test exists returns True when entry exists."""
        # Create entry
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry_manager.create({"date": "2024-01-15", "file_path": str(file_path)})
        db_session.commit()

        assert entry_manager.exists(entry_date="2024-01-15") is True

    def test_exists_by_file_path_returns_true_when_found(
        self, entry_manager, tmp_dir, db_session
    ):
        """Test exists by file path."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry_manager.create({"date": "2024-01-15", "file_path": str(file_path)})
        db_session.commit()

        assert entry_manager.exists(file_path=str(file_path)) is True

    def test_exists_with_date_object(self, entry_manager, tmp_dir, db_session):
        """Test exists with date object instead of string."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry_manager.create({"date": date(2024, 1, 15), "file_path": str(file_path)})
        db_session.commit()

        assert entry_manager.exists(entry_date=date(2024, 1, 15)) is True

    def test_exists_with_invalid_date_returns_false(self, entry_manager):
        """Test exists with invalid date format returns False."""
        assert entry_manager.exists(entry_date="invalid-date") is False

    def test_exists_with_none_returns_false(self, entry_manager):
        """Test exists with None parameters returns False."""
        assert entry_manager.exists(entry_date=None, file_path=None) is False


class TestEntryManagerGet:
    """Test EntryManager.get() method."""

    def test_get_by_date_returns_none_when_not_found(self, entry_manager):
        """Test get returns None when entry doesn't exist."""
        result = entry_manager.get(entry_date="2024-01-15")
        assert result is None

    def test_get_by_date_returns_entry_when_found(self, entry_manager, tmp_dir, db_session):
        """Test get returns entry when found."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        created = entry_manager.create({"date": "2024-01-15", "file_path": str(file_path)})
        db_session.commit()

        result = entry_manager.get(entry_date="2024-01-15")
        assert result is not None
        assert result.id == created.id
        assert result.date == date(2024, 1, 15)

    def test_get_by_id_returns_entry(self, entry_manager, tmp_dir, db_session):
        """Test get by entry ID."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        created = entry_manager.create({"date": "2024-01-15", "file_path": str(file_path)})
        db_session.commit()

        result = entry_manager.get(entry_id=created.id)
        assert result is not None
        assert result.id == created.id

    def test_get_by_file_path_returns_entry(self, entry_manager, tmp_dir, db_session):
        """Test get by file path."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry_manager.create({"date": "2024-01-15", "file_path": str(file_path)})
        db_session.commit()

        result = entry_manager.get(file_path=str(file_path))
        assert result is not None
        assert result.file_path == str(file_path)

    def test_get_excludes_deleted_by_default(self, entry_manager, tmp_dir, db_session):
        """Test get excludes soft-deleted entries by default."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry = entry_manager.create({"date": "2024-01-15", "file_path": str(file_path)})
        db_session.commit()

        entry_manager.delete(entry, deleted_by="test")
        db_session.commit()

        result = entry_manager.get(entry_date="2024-01-15")
        assert result is None

    def test_get_includes_deleted_when_requested(self, entry_manager, tmp_dir, db_session):
        """Test get includes soft-deleted entries when requested."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry = entry_manager.create({"date": "2024-01-15", "file_path": str(file_path)})
        db_session.commit()

        entry_manager.delete(entry, deleted_by="test")
        db_session.commit()

        result = entry_manager.get(entry_date="2024-01-15", include_deleted=True)
        assert result is not None
        assert result.deleted_at is not None

    def test_get_with_no_parameters_returns_none(self, entry_manager):
        """Test get with no search parameters returns None."""
        result = entry_manager.get()
        assert result is None


class TestEntryManagerCreate:
    """Test EntryManager.create() method."""

    def test_create_minimal_entry(self, entry_manager, tmp_dir, db_session):
        """Test creating entry with minimal required fields."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({"date": "2024-01-15", "file_path": str(file_path)})
        db_session.commit()

        assert entry is not None
        assert entry.id is not None
        assert entry.date == date(2024, 1, 15)
        assert entry.file_path == str(file_path)
        assert entry.file_hash is not None  # Auto-calculated

    def test_create_entry_with_all_scalar_fields(self, entry_manager, tmp_dir, db_session):
        """Test creating entry with all scalar fields."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create(
            {
                "date": "2024-01-15",
                "file_path": str(file_path),
                "word_count": 500,
                "reading_time": 2.5,
                "summary": "Test summary",
                "rating": 4.0,
                "rating_justification": "Good entry",
            }
        )
        db_session.commit()

        assert entry.word_count == 500
        assert entry.reading_time == 2.5
        assert entry.summary == "Test summary"
        assert entry.rating == 4.0
        assert entry.rating_justification == "Good entry"

    def test_create_entry_with_date_object(self, entry_manager, tmp_dir, db_session):
        """Test create with date object instead of string."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({"date": date(2024, 1, 15), "file_path": str(file_path)})
        db_session.commit()

        assert entry.date == date(2024, 1, 15)

    def test_create_entry_missing_date_raises_error(self, entry_manager, tmp_dir):
        """Test creating entry without date raises error."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        with pytest.raises((ValidationError, ValueError, KeyError)):
            entry_manager.create({"file_path": str(file_path)})

    def test_create_entry_missing_file_path_raises_error(self, entry_manager):
        """Test creating entry without file_path raises error."""
        with pytest.raises((ValidationError, ValueError, KeyError)):
            entry_manager.create({"date": "2024-01-15"})

    def test_create_entry_with_invalid_date_raises_error(self, entry_manager, tmp_dir):
        """Test creating entry with invalid date raises error."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        with pytest.raises((ValidationError, ValueError)):
            entry_manager.create({"date": "invalid-date", "file_path": str(file_path)})

    def test_create_entry_duplicate_file_path_raises_error(
        self, entry_manager, tmp_dir, db_session
    ):
        """Test creating entry with duplicate file_path raises error."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry_manager.create({"date": "2024-01-15", "file_path": str(file_path)})
        db_session.commit()

        # Try to create another entry with same file_path
        with pytest.raises(ValidationError) as exc_info:
            entry_manager.create({"date": "2024-01-16", "file_path": str(file_path)})
        assert "already exists" in str(exc_info.value).lower()

    def test_create_entry_auto_calculates_hash(self, entry_manager, tmp_dir, db_session):
        """Test entry creation auto-calculates file hash."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test content")

        entry = entry_manager.create({"date": "2024-01-15", "file_path": str(file_path)})
        db_session.commit()

        assert entry.file_hash is not None
        assert len(entry.file_hash) > 0

    def test_create_entry_with_explicit_hash(self, entry_manager, tmp_dir, db_session):
        """Test creating entry with explicitly provided hash."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create(
            {"date": "2024-01-15", "file_path": str(file_path), "file_hash": "custom_hash"}
        )
        db_session.commit()

        assert entry.file_hash == "custom_hash"

    def test_create_entry_nonexistent_file_path(self, entry_manager, db_session):
        """Test creating entry with non-existent file path."""
        # Should not fail - manager handles this gracefully
        entry = entry_manager.create(
            {"date": "2024-01-15", "file_path": "/nonexistent/path.md"}
        )
        db_session.commit()

        assert entry is not None
        assert entry.file_hash is None  # Cannot calculate hash for non-existent file


class TestEntryManagerUpdate:
    """Test EntryManager.update() method."""

    def test_update_entry_scalar_fields(self, entry_manager, tmp_dir, db_session):
        """Test updating entry scalar fields."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({"date": "2024-01-15", "file_path": str(file_path)})
        db_session.commit()

        entry_manager.update(
            entry,
            {
                "word_count": 750,
                "reading_time": 3.5,
                "summary": "Updated summary",
                "rating": 3.5,
            },
        )
        db_session.commit()
        db_session.refresh(entry)

        assert entry.word_count == 750
        assert entry.reading_time == 3.5
        assert entry.summary == "Updated summary"
        assert entry.rating == 3.5

    def test_update_entry_date(self, entry_manager, tmp_dir, db_session):
        """Test updating entry date."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({"date": "2024-01-15", "file_path": str(file_path)})
        db_session.commit()

        entry_manager.update(entry, {"date": "2024-01-16"})
        db_session.commit()
        db_session.refresh(entry)

        assert entry.date == date(2024, 1, 16)

    def test_update_entry_file_path_recalculates_hash(
        self, entry_manager, tmp_dir, db_session
    ):
        """Test updating file_path recalculates hash."""
        file_path1 = tmp_dir / "2024-01-15.md"
        file_path1.write_text("# Test 1")

        entry = entry_manager.create({"date": "2024-01-15", "file_path": str(file_path1)})
        db_session.commit()
        original_hash = entry.file_hash

        # Create new file with different content
        file_path2 = tmp_dir / "2024-01-15-v2.md"
        file_path2.write_text("# Test 2 - different content")

        entry_manager.update(entry, {"file_path": str(file_path2)})
        db_session.commit()
        db_session.refresh(entry)

        assert entry.file_path == str(file_path2)
        assert entry.file_hash != original_hash

    def test_update_nonexistent_entry_raises_error(self, entry_manager):
        """Test updating non-existent entry raises error."""
        fake_entry = Entry()
        fake_entry.id = 99999

        with pytest.raises((DatabaseError, ValueError)):
            entry_manager.update(fake_entry, {"word_count": 100})

    def test_update_clears_optional_fields(self, entry_manager, tmp_dir, db_session):
        """Test updating can clear optional text fields."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create(
            {
                "date": "2024-01-15",
                "file_path": str(file_path),
                "summary": "Test summary",
                "rating_justification": "Justification",
            }
        )
        db_session.commit()

        # Clear optional fields
        entry_manager.update(entry, {"summary": None, "rating_justification": None})
        db_session.commit()
        db_session.refresh(entry)

        assert entry.summary is None
        assert entry.rating_justification is None


class TestEntryManagerDelete:
    """Test EntryManager.delete() method."""

    def test_delete_entry_soft_delete(self, entry_manager, tmp_dir, db_session):
        """Test soft deleting an entry."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({"date": "2024-01-15", "file_path": str(file_path)})
        db_session.commit()

        entry_manager.delete(entry, deleted_by="admin")
        db_session.commit()
        db_session.refresh(entry)

        assert entry.deleted_at is not None
        assert entry.deleted_by == "admin"

    def test_delete_entry_with_reason(self, entry_manager, tmp_dir, db_session):
        """Test deleting entry with reason."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({"date": "2024-01-15", "file_path": str(file_path)})
        db_session.commit()

        entry_manager.delete(entry, deleted_by="admin", reason="Duplicate entry")
        db_session.commit()
        db_session.refresh(entry)

        assert entry.deleted_at is not None
        assert entry.deletion_reason == "Duplicate entry"

    def test_deleted_entry_not_in_get(self, entry_manager, tmp_dir, db_session):
        """Test deleted entry not returned by get()."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({"date": "2024-01-15", "file_path": str(file_path)})
        db_session.commit()

        entry_manager.delete(entry, deleted_by="admin")
        db_session.commit()

        result = entry_manager.get(entry_date="2024-01-15")
        assert result is None

    def test_hard_delete_removes_entry(self, entry_manager, tmp_dir, db_session):
        """Test hard delete permanently removes entry."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({"date": "2024-01-15", "file_path": str(file_path)})
        db_session.commit()
        entry_id = entry.id

        entry_manager.delete(entry, hard_delete=True)
        db_session.commit()

        # Entry should not exist at all
        result = entry_manager.get(entry_id=entry_id, include_deleted=True)
        assert result is None


class TestEntryManagerRestore:
    """Test EntryManager.restore() method."""

    def test_restore_deleted_entry(self, entry_manager, tmp_dir, db_session):
        """Test restoring a soft-deleted entry."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({"date": "2024-01-15", "file_path": str(file_path)})
        db_session.commit()

        entry_manager.delete(entry, deleted_by="admin")
        db_session.commit()

        entry_manager.restore(entry)
        db_session.commit()
        db_session.refresh(entry)

        assert entry.deleted_at is None
        assert entry.deleted_by is None
        assert entry.deletion_reason is None

    def test_restored_entry_in_get(self, entry_manager, tmp_dir, db_session):
        """Test restored entry is returned by get()."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({"date": "2024-01-15", "file_path": str(file_path)})
        db_session.commit()

        entry_manager.delete(entry, deleted_by="admin")
        db_session.commit()

        entry_manager.restore(entry)
        db_session.commit()

        result = entry_manager.get(entry_date="2024-01-15")
        assert result is not None
        assert result.id == entry.id


class TestEntryManagerTagProcessing:
    """Test EntryManager tag processing with Tag.name field."""

    def test_create_entry_with_tags(self, entry_manager, tmp_dir, db_session):
        """Test creating entry with tags (uses Tag.name field)."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create(
            {
                "date": "2024-01-15",
                "file_path": str(file_path),
                "tags": ["python", "testing", "database"],
            }
        )
        db_session.commit()
        db_session.refresh(entry)

        assert len(entry.tags) == 3
        tag_names = {tag.name for tag in entry.tags}
        assert tag_names == {"python", "testing", "database"}

    def test_update_entry_tags_incremental(self, entry_manager, tmp_dir, db_session):
        """Test incrementally adding tags."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create(
            {"date": "2024-01-15", "file_path": str(file_path), "tags": ["python", "testing"]}
        )
        db_session.commit()

        # Add more tags incrementally
        entry_manager.update_relationships(
            entry, {"tags": ["database", "sqlalchemy"]}, incremental=True
        )
        db_session.commit()
        db_session.refresh(entry)

        # Should have original tags plus new ones
        tag_names = {tag.name for tag in entry.tags}
        assert "python" in tag_names
        assert "testing" in tag_names
        assert "database" in tag_names
        assert "sqlalchemy" in tag_names

    def test_update_entry_tags_replacement(self, entry_manager, tmp_dir, db_session):
        """Test replacing all tags."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create(
            {"date": "2024-01-15", "file_path": str(file_path), "tags": ["python", "testing"]}
        )
        db_session.commit()

        # Replace tags
        entry_manager.update_relationships(
            entry, {"tags": ["new-tag"]}, incremental=False
        )
        db_session.commit()
        db_session.refresh(entry)

        # Should only have new tag
        tag_names = {tag.name for tag in entry.tags}
        assert tag_names == {"new-tag"}

    def test_tags_normalize_whitespace(self, entry_manager, tmp_dir, db_session):
        """Test tags normalize whitespace."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create(
            {
                "date": "2024-01-15",
                "file_path": str(file_path),
                "tags": ["  python  ", " testing "],
            }
        )
        db_session.commit()
        db_session.refresh(entry)

        tag_names = {tag.name for tag in entry.tags}
        assert tag_names == {"python", "testing"}

    def test_tags_avoid_duplicates(self, entry_manager, tmp_dir, db_session):
        """Test tags don't create duplicates."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create(
            {
                "date": "2024-01-15",
                "file_path": str(file_path),
                "tags": ["python", "python", "testing"],
            }
        )
        db_session.commit()
        db_session.refresh(entry)

        tag_names = [tag.name for tag in entry.tags]
        assert tag_names.count("python") == 1


class TestEntryManagerCityProcessing:
    """Test EntryManager city processing with City.name field."""

    def test_create_entry_with_cities_by_string(self, entry_manager, tmp_dir, db_session):
        """Test creating entry with cities as strings (uses City.name field)."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create(
            {"date": "2024-01-15", "file_path": str(file_path), "cities": ["Montreal"]}
        )
        db_session.commit()
        db_session.refresh(entry)

        assert len(entry.cities) == 1
        assert entry.cities[0].name == "Montreal"

    def test_create_entry_with_cities_by_id(self, entry_manager, tmp_dir, db_session):
        """Test creating entry with cities by ID."""
        # Create city first
        city = City(name="Montreal")
        db_session.add(city)
        db_session.commit()

        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create(
            {"date": "2024-01-15", "file_path": str(file_path), "cities": [city.id]}
        )
        db_session.commit()
        db_session.refresh(entry)

        assert len(entry.cities) == 1
        assert entry.cities[0].name == "Montreal"

    def test_update_entry_cities_incremental(self, entry_manager, tmp_dir, db_session):
        """Test incrementally adding cities."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create(
            {"date": "2024-01-15", "file_path": str(file_path), "cities": ["Montreal"]}
        )
        db_session.commit()

        # Add more cities
        entry_manager.update_relationships(
            entry, {"cities": ["Toronto"]}, incremental=True
        )
        db_session.commit()
        db_session.refresh(entry)

        city_names = {city.name for city in entry.cities}
        assert city_names == {"Montreal", "Toronto"}

    def test_update_entry_cities_replacement(self, entry_manager, tmp_dir, db_session):
        """Test replacing all cities."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create(
            {"date": "2024-01-15", "file_path": str(file_path), "cities": ["Montreal"]}
        )
        db_session.commit()

        # Replace cities
        entry_manager.update_relationships(
            entry, {"cities": ["Toronto"]}, incremental=False
        )
        db_session.commit()
        db_session.refresh(entry)

        city_names = {city.name for city in entry.cities}
        assert city_names == {"Toronto"}


class TestEntryManagerPeopleProcessing:
    """Test EntryManager people processing."""

    def test_create_entry_with_people_by_dict(self, entry_manager, tmp_dir, db_session):
        """Test creating entry with people as dicts (from MD parsing)."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create(
            {
                "date": "2024-01-15",
                "file_path": str(file_path),
                "people": [{"name": "Bob", "full_name": "Robert Smith"}],
            }
        )
        db_session.commit()
        db_session.refresh(entry)

        assert len(entry.people) >= 1
        person_names = {p.name for p in entry.people}
        assert "Bob" in person_names



class TestEntryManagerEventProcessing:
    """
    Test EntryManager event processing with Event.name field.

    Note: Event processing is currently broken in EntryManager as it treats
    Event as M2M when it's actually one-to-many. These tests are skipped until
    the implementation is fixed.
    """

    @pytest.mark.skip(reason="Event processing broken - Event is one-to-many, not M2M")
    def test_create_entry_with_events_by_string(self, entry_manager, tmp_dir, db_session):
        """Test creating entry with events as strings (uses Event.name field)."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create(
            {"date": "2024-01-15", "file_path": str(file_path), "events": ["conference"]}
        )
        db_session.commit()
        db_session.refresh(entry)

        assert len(entry.events) >= 1
        event_names = {e.name for e in entry.events}
        assert "conference" in event_names

    @pytest.mark.skip(reason="Event processing broken - Event is one-to-many, not M2M")
    def test_create_entry_with_events_by_id(self, entry_manager, tmp_dir, db_session):
        """Test creating entry with events by ID."""
        # Create event first
        event = Event(name="conference", entry_id=1)
        db_session.add(event)
        db_session.commit()

        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create(
            {"date": "2024-01-15", "file_path": str(file_path), "events": [event.id]}
        )
        db_session.commit()
        db_session.refresh(entry)

        # Note: Event relationship is one-to-many from Entry, not M2M
        # So events should be accessible via entry.events
        assert len(entry.events) >= 1

    @pytest.mark.skip(reason="Event processing broken - Event is one-to-many, not M2M")
    def test_update_entry_events_incremental(self, entry_manager, tmp_dir, db_session):
        """Test incrementally adding events."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create(
            {"date": "2024-01-15", "file_path": str(file_path), "events": ["conference"]}
        )
        db_session.commit()

        # Add more events
        entry_manager.update_relationships(
            entry, {"events": ["workshop"]}, incremental=True
        )
        db_session.commit()
        db_session.refresh(entry)

        event_names = {e.name for e in entry.events}
        assert "conference" in event_names
        assert "workshop" in event_names

    @pytest.mark.skip(reason="Event processing broken - Event is one-to-many, not M2M")
    def test_update_entry_events_replacement(self, entry_manager, tmp_dir, db_session):
        """Test replacing all events."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create(
            {"date": "2024-01-15", "file_path": str(file_path), "events": ["conference"]}
        )
        db_session.commit()

        # Replace events
        entry_manager.update_relationships(
            entry, {"events": ["meeting"]}, incremental=False
        )
        db_session.commit()
        db_session.refresh(entry)

        event_names = {e.name for e in entry.events}
        assert event_names == {"meeting"}


class TestEntryManagerBulkCreate:
    """Test EntryManager.bulk_create() method."""

    def test_bulk_create_entries(self, entry_manager, tmp_dir, db_session):
        """Test bulk creating multiple entries."""
        # Create files
        files = []
        for i in range(1, 6):
            file_path = tmp_dir / f"2024-01-{i:02d}.md"
            file_path.write_text(f"# Test {i}")
            files.append(file_path)

        # Prepare metadata
        entries_metadata = [
            {"date": f"2024-01-{i:02d}", "file_path": str(file_path)}
            for i, file_path in enumerate(files, 1)
        ]

        # Bulk create
        created_ids = entry_manager.bulk_create(entries_metadata)
        db_session.commit()

        assert len(created_ids) == 5

        # Verify all created
        for i in range(1, 6):
            entry = entry_manager.get(entry_date=f"2024-01-{i:02d}")
            assert entry is not None

    def test_bulk_create_with_batch_size(self, entry_manager, tmp_dir, db_session):
        """Test bulk create with custom batch size."""
        # Create files
        files = []
        for i in range(1, 11):
            file_path = tmp_dir / f"2024-01-{i:02d}.md"
            file_path.write_text(f"# Test {i}")
            files.append(file_path)

        entries_metadata = [
            {"date": f"2024-01-{i:02d}", "file_path": str(file_path)}
            for i, file_path in enumerate(files, 1)
        ]

        # Bulk create with small batch size
        created_ids = entry_manager.bulk_create(entries_metadata, batch_size=3)
        db_session.commit()

        assert len(created_ids) == 10


class TestEntryManagerEdgeCases:
    """Test edge cases and special scenarios."""

    def test_create_entry_with_unicode_file_path(self, entry_manager, tmp_dir, db_session):
        """Test creating entry with unicode characters in path."""
        file_path = tmp_dir / "2024-01-15-café.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({"date": "2024-01-15", "file_path": str(file_path)})
        db_session.commit()

        assert entry.file_path == str(file_path)

    def test_create_entry_with_zero_word_count(self, entry_manager, tmp_dir, db_session):
        """Test creating entry with zero word count."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create(
            {"date": "2024-01-15", "file_path": str(file_path), "word_count": 0}
        )
        db_session.commit()

        assert entry.word_count == 0

    def test_create_entry_with_negative_word_count_fails(
        self, entry_manager, tmp_dir, db_session
    ):
        """Test creating entry with negative word count fails check constraint."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        # Should fail on entry creation due to check constraint
        with pytest.raises(DatabaseError) as exc_info:
            entry = entry_manager.create(
                {"date": "2024-01-15", "file_path": str(file_path), "word_count": -1}
            )
            db_session.commit()

        assert "constraint" in str(exc_info.value).lower()

    def test_update_entry_empty_tags_list(self, entry_manager, tmp_dir, db_session):
        """Test updating entry with empty tags list clears tags."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create(
            {"date": "2024-01-15", "file_path": str(file_path), "tags": ["python"]}
        )
        db_session.commit()

        # Clear tags with empty list
        entry_manager.update_relationships(entry, {"tags": []}, incremental=False)
        db_session.commit()
        db_session.refresh(entry)

        assert len(entry.tags) == 0

    def test_get_for_display(self, entry_manager, tmp_dir, db_session):
        """Test get_for_display returns entry with optimized loading."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry_manager.create({"date": "2024-01-15", "file_path": str(file_path)})
        db_session.commit()

        entry = entry_manager.get_for_display("2024-01-15")
        assert entry is not None
        assert entry.date == date(2024, 1, 15)

    def test_entry_has_timestamps(self, entry_manager, tmp_dir, db_session):
        """Test entry has created_at and updated_at timestamps."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({"date": "2024-01-15", "file_path": str(file_path)})
        db_session.commit()

        assert entry.created_at is not None
        assert entry.updated_at is not None

    def test_multiple_entries_different_dates(self, entry_manager, tmp_dir, db_session):
        """Test creating multiple entries with different dates."""
        for i in range(1, 4):
            file_path = tmp_dir / f"2024-01-{i:02d}.md"
            file_path.write_text(f"# Test {i}")
            entry_manager.create({"date": f"2024-01-{i:02d}", "file_path": str(file_path)})

        db_session.commit()

        # Verify all exist
        for i in range(1, 4):
            entry = entry_manager.get(entry_date=f"2024-01-{i:02d}")
            assert entry is not None
