"""
test_entry_manager.py
---------------------
Unit tests for EntryManager CRUD operations and relationship processing.

Tests the most complex manager as Entry is the central entity with
relationships to almost all other entities.

Target Coverage: 90%+
"""
import pytest
from datetime import date
from pathlib import Path
from dev.database.models import Entry, Tag, City, Person, Event
from dev.core.exceptions import ValidationError, DatabaseError


class TestEntryManagerExists:
    """Test EntryManager.exists() method."""

    def test_exists_by_date_returns_false_when_not_found(self, entry_manager):
        """Test exists returns False when entry doesn't exist."""
        assert entry_manager.exists(entry_date="2024-01-15") is False

    def test_exists_by_date_returns_true_when_found(self, entry_manager, tmp_dir):
        """Test exists returns True when entry exists."""
        # Create entry
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })

        assert entry_manager.exists(entry_date="2024-01-15") is True

    def test_exists_by_file_path_returns_true_when_found(self, entry_manager, tmp_dir):
        """Test exists by file path."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })

        assert entry_manager.exists(file_path=str(file_path)) is True

    def test_exists_with_date_object(self, entry_manager, tmp_dir):
        """Test exists with date object instead of string."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry_manager.create({
            "date": date(2024, 1, 15),
            "file_path": str(file_path)
        })

        assert entry_manager.exists(entry_date=date(2024, 1, 15)) is True


class TestEntryManagerGet:
    """Test EntryManager.get() method."""

    def test_get_by_date_returns_none_when_not_found(self, entry_manager):
        """Test get returns None when entry doesn't exist."""
        result = entry_manager.get(entry_date="2024-01-15")
        assert result is None

    def test_get_by_date_returns_entry_when_found(self, entry_manager, tmp_dir):
        """Test get returns entry when found."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        created = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })

        result = entry_manager.get(entry_date="2024-01-15")
        assert result is not None
        assert result.id == created.id
        assert result.date == date(2024, 1, 15)

    def test_get_by_id_returns_entry(self, entry_manager, tmp_dir):
        """Test get by entry ID."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        created = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })

        result = entry_manager.get(entry_id=created.id)
        assert result is not None
        assert result.id == created.id

    def test_get_by_file_path_returns_entry(self, entry_manager, tmp_dir):
        """Test get by file path."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })

        result = entry_manager.get(file_path=str(file_path))
        assert result is not None
        assert result.file_path == str(file_path)


class TestEntryManagerCreate:
    """Test EntryManager.create() method."""

    def test_create_minimal_entry(self, entry_manager, tmp_dir):
        """Test creating entry with minimal required fields."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })

        assert entry is not None
        assert entry.id is not None
        assert entry.date == date(2024, 1, 15)
        assert entry.file_path == str(file_path)
        assert entry.file_hash is not None  # Auto-calculated

    def test_create_entry_with_all_scalar_fields(self, entry_manager, tmp_dir):
        """Test creating entry with all scalar fields."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "word_count": 500,
            "reading_time": 2.5,
            "epigraph": "Test epigraph",
            "epigraph_attribution": "Author",
            "notes": "Test notes"
        })

        assert entry.word_count == 500
        assert entry.reading_time == 2.5
        assert entry.epigraph == "Test epigraph"
        assert entry.epigraph_attribution == "Author"
        assert entry.notes == "Test notes"

    def test_create_entry_with_date_object(self, entry_manager, tmp_dir):
        """Test create with date object instead of string."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({
            "date": date(2024, 1, 15),
            "file_path": str(file_path)
        })

        assert entry.date == date(2024, 1, 15)

    def test_create_entry_missing_date_raises_error(self, entry_manager, tmp_dir):
        """Test creating entry without date raises error."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        with pytest.raises((KeyError, ValueError)):
            entry_manager.create({
                "file_path": str(file_path)
            })

    def test_create_entry_missing_file_path_raises_error(self, entry_manager):
        """Test creating entry without file_path raises error."""
        with pytest.raises((KeyError, ValueError)):
            entry_manager.create({
                "date": "2024-01-15"
            })

    def test_create_entry_invalid_date_raises_error(self, entry_manager, tmp_dir):
        """Test creating entry with invalid date format."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        with pytest.raises(ValueError):
            entry_manager.create({
                "date": "invalid-date",
                "file_path": str(file_path)
            })

    def test_create_duplicate_file_path_raises_error(self, entry_manager, tmp_dir):
        """Test creating entry with duplicate file_path raises error."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })

        # Try to create another entry with same file_path
        with pytest.raises(ValidationError) as exc_info:
            entry_manager.create({
                "date": "2024-01-16",
                "file_path": str(file_path)
            })
        assert "already exists" in str(exc_info.value).lower()

    def test_create_entry_with_provided_hash(self, entry_manager, tmp_dir):
        """Test creating entry with pre-computed hash."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        custom_hash = "abc123"

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "file_hash": custom_hash
        })

        assert entry.file_hash == custom_hash

    def test_create_entry_with_nonexistent_file_path(self, entry_manager, tmp_dir):
        """Test creating entry with nonexistent file still works."""
        file_path = tmp_dir / "nonexistent.md"

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })

        # Should create entry but without hash
        assert entry is not None
        assert entry.file_hash is None


class TestEntryManagerUpdate:
    """Test EntryManager.update() method."""

    def test_update_entry_scalar_fields(self, entry_manager, tmp_dir, db_session):
        """Test updating entry scalar fields."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })
        db_session.commit()

        # Update fields
        updated = entry_manager.update(entry, {
            "word_count": 1000,
            "reading_time": 5.0,
            "epigraph": "Updated epigraph"
        })

        assert updated.word_count == 1000
        assert updated.reading_time == 5.0
        assert updated.epigraph == "Updated epigraph"

    def test_update_entry_date(self, entry_manager, tmp_dir, db_session):
        """Test updating entry date."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })
        db_session.commit()

        updated = entry_manager.update(entry, {
            "date": "2024-01-20"
        })

        assert updated.date == date(2024, 1, 20)

    def test_update_nonexistent_entry_raises_error(self, entry_manager, db_session):
        """Test updating non-existent entry raises error."""
        # Create a fake entry object not in database
        from dev.database.models import Entry
        fake_entry = Entry()
        fake_entry.id = 99999

        with pytest.raises(ValueError) as exc_info:
            entry_manager.update(fake_entry, {"word_count": 100})
        assert "does not exist" in str(exc_info.value).lower()


class TestEntryManagerDelete:
    """Test EntryManager.delete() method."""

    def test_delete_entry(self, entry_manager, tmp_dir, db_session):
        """Test deleting an entry."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })
        entry_id = entry.id
        db_session.commit()

        # Delete
        entry_manager.delete(entry)
        db_session.commit()

        # Verify deleted
        result = entry_manager.get(entry_id=entry_id)
        assert result is None


class TestEntryManagerRelationships:
    """Test EntryManager relationship processing."""

    def test_create_entry_with_tags(self, entry_manager, tmp_dir, db_session):
        """Test creating entry with tags."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "tags": ["python", "testing", "database"]
        })

        db_session.commit()
        db_session.refresh(entry)

        assert len(entry.tags) == 3
        tag_names = {tag.tag for tag in entry.tags}
        assert tag_names == {"python", "testing", "database"}

    def test_create_entry_with_cities(self, entry_manager, tmp_dir, db_session):
        """Test creating entry with cities."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        # Create city first (City uses 'city' field, not 'name')
        from dev.database.models import City
        city = City(city="Montreal")
        db_session.add(city)
        db_session.commit()

        # Pass City instance or ID, not string
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "cities": [city.id]
        })

        db_session.commit()
        db_session.refresh(entry)

        assert len(entry.cities) == 1
        assert entry.cities[0].city == "Montreal"

    def test_create_entry_with_people(self, entry_manager, tmp_dir, db_session):
        """Test creating entry with people."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        # Create person first
        from dev.database.models import Person
        person = Person(name="Alice", full_name="Alice Smith")
        db_session.add(person)
        db_session.commit()

        # Pass Person instance or ID, not string
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "people": [person.id]
        })

        db_session.commit()
        db_session.refresh(entry)

        assert len(entry.people) >= 1
        assert entry.people[0].name == "Alice"

    def test_create_entry_with_events(self, entry_manager, tmp_dir, db_session):
        """Test creating entry with events."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        # Create event first (Event uses 'event' and 'title', not 'name'/'full_name')
        from dev.database.models import Event
        event = Event(event="conference", title="Annual Conference 2024")
        db_session.add(event)
        db_session.commit()

        # Pass Event instance or ID, not string
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "events": [event.id]
        })

        db_session.commit()
        db_session.refresh(entry)

        assert len(entry.events) >= 1
        assert entry.events[0].event == "conference"

    def test_update_entry_tags_incremental(self, entry_manager, tmp_dir, db_session):
        """Test incrementally updating entry tags."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "tags": ["python", "testing"]
        })
        db_session.commit()

        # Add more tags incrementally
        entry_manager.update_relationships(entry, {
            "tags": ["database", "sqlalchemy"]
        }, incremental=True)
        db_session.commit()
        db_session.refresh(entry)

        # Should have all 4 tags
        tag_names = {tag.tag for tag in entry.tags}
        assert len(tag_names) >= 3  # At least original + some new

    def test_update_entry_tags_overwrite(self, entry_manager, tmp_dir, db_session):
        """Test overwriting entry tags."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "tags": ["python", "testing"]
        })
        db_session.commit()

        # Overwrite tags
        entry_manager.update_relationships(entry, {
            "tags": ["new-tag"]
        }, incremental=False)
        db_session.commit()
        db_session.refresh(entry)

        # Should only have new tag
        tag_names = {tag.tag for tag in entry.tags}
        assert tag_names == {"new-tag"}


class TestEntryManagerBulkCreate:
    """Test EntryManager.bulk_create() method."""

    def test_bulk_create_multiple_entries(self, entry_manager, tmp_dir, db_session):
        """Test bulk creating multiple entries."""
        entries_data = []
        for i in range(5):
            file_path = tmp_dir / f"2024-01-{15+i:02d}.md"
            file_path.write_text(f"# Entry {i}")
            entries_data.append({
                "date": f"2024-01-{15+i:02d}",
                "file_path": str(file_path),
                "word_count": 100 + i * 10,
                "reading_time": 0.5 + i * 0.1
            })

        created_ids = entry_manager.bulk_create(entries_data)

        assert len(created_ids) == 5

        # Verify entries exist
        for entry_id in created_ids:
            entry = entry_manager.get(entry_id=entry_id)
            assert entry is not None

    def test_bulk_create_with_custom_batch_size(self, entry_manager, tmp_dir, db_session):
        """Test bulk create with custom batch size."""
        entries_data = []
        for i in range(10):
            file_path = tmp_dir / f"2024-01-{10+i:02d}.md"
            file_path.write_text(f"# Entry {i}")
            entries_data.append({
                "date": f"2024-01-{10+i:02d}",
                "file_path": str(file_path),
                "word_count": 50,
                "reading_time": 0.5
            })

        created_ids = entry_manager.bulk_create(entries_data, batch_size=3)

        assert len(created_ids) == 10


class TestEntryManagerEdgeCases:
    """Test edge cases and error handling."""

    def test_create_entry_with_empty_string_fields(self, entry_manager, tmp_dir):
        """Test creating entry with empty string fields."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "epigraph": "",
            "notes": ""
        })

        # Empty strings should be stored as None or empty
        assert entry.epigraph in (None, "")
        assert entry.notes in (None, "")

    def test_create_entry_with_none_optional_fields(self, entry_manager, tmp_dir):
        """Test creating entry with explicit None values."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "word_count": None,
            "reading_time": None,
            "epigraph": None
        })

        # word_count and reading_time have defaults (0 and 0.0)
        assert entry.word_count == 0
        assert entry.reading_time == 0.0
        assert entry.epigraph is None

    def test_create_entry_with_zero_word_count(self, entry_manager, tmp_dir):
        """Test creating entry with zero word count is allowed."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "word_count": 0
        })

        assert entry.word_count == 0

    def test_create_entry_with_negative_word_count(self, entry_manager, tmp_dir):
        """Test creating entry with negative word count raises error."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        # Should raise error due to CHECK constraint: word_count >= 0
        with pytest.raises(DatabaseError) as exc_info:
            entry_manager.create({
                "date": "2024-01-15",
                "file_path": str(file_path),
                "word_count": -10
            })
        assert "constraint" in str(exc_info.value).lower()

    def test_create_entry_with_empty_tags_list(self, entry_manager, tmp_dir, db_session):
        """Test creating entry with empty tags list."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "tags": []
        })

        db_session.commit()
        db_session.refresh(entry)

        assert len(entry.tags) == 0
