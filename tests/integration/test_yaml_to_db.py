#!/usr/bin/env python3
"""
Integration tests for YAML → Database pipeline.

These tests verify the full pipeline from YAML frontmatter with string
relationship names to properly created and linked database entities.
"""
import pytest
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dev.database.models import Base, Entry, Person, Event, City, Location
from dev.database.managers import EntryManager


@pytest.fixture
def test_db():
    """Create in-memory database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def entry_manager(test_db):
    """Create EntryManager with test database."""
    return EntryManager(test_db, logger=None)


class TestYAMLStringResolution:
    """Test that string names from YAML are properly resolved to entities."""

    def test_entry_with_string_people(self, entry_manager, test_db, tmp_path):
        """Test creating entry with people as strings (YAML format)."""
        # Create entry with people as strings (like from YAML)
        file_path = tmp_path / "2024-01-15.md"
        file_path.write_text("# Test entry")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "people": ["Alice", "Bob", "Dr-Martinez"]  # Strings, not IDs!
        })

        test_db.commit()
        test_db.refresh(entry)

        # Verify people were auto-created
        assert len(entry.people) == 3
        people_names = {p.name for p in entry.people}
        assert people_names == {"Alice", "Bob", "Dr-Martinez"}

        # Verify people exist in database
        alice = test_db.query(Person).filter_by(name="Alice").first()
        assert alice is not None
        assert alice.id is not None

        bob = test_db.query(Person).filter_by(name="Bob").first()
        assert bob is not None

        dr_martinez = test_db.query(Person).filter_by(name="Dr-Martinez").first()
        assert dr_martinez is not None

    def test_entry_with_string_events(self, entry_manager, test_db, tmp_path):
        """Test creating entry with events as strings."""
        file_path = tmp_path / "2024-01-15.md"
        file_path.write_text("# Test entry")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "events": ["therapy-session", "family-dinner", "madrid-trip-2024"]
        })

        test_db.commit()
        test_db.refresh(entry)

        # Verify events were auto-created
        assert len(entry.events) == 3
        event_names = {e.event for e in entry.events}
        assert event_names == {"therapy-session", "family-dinner", "madrid-trip-2024"}

        # Verify events exist in database
        therapy = test_db.query(Event).filter_by(event="therapy-session").first()
        assert therapy is not None
        assert therapy.id is not None

    def test_entry_with_string_cities(self, entry_manager, test_db, tmp_path):
        """Test creating entry with cities as strings."""
        file_path = tmp_path / "2024-01-15.md"
        file_path.write_text("# Test entry")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "cities": ["Montreal", "Madrid", "San-Diego"]
        })

        test_db.commit()
        test_db.refresh(entry)

        # Verify cities were auto-created
        assert len(entry.cities) == 3
        city_names = {c.city for c in entry.cities}
        assert city_names == {"Montreal", "Madrid", "San-Diego"}

        # Verify cities exist in database
        montreal = test_db.query(City).filter_by(city="Montreal").first()
        assert montreal is not None
        assert montreal.id is not None

    def test_entry_with_mixed_types(self, entry_manager, test_db, tmp_path):
        """Test creating entry with mix of strings, IDs, and objects."""
        file_path = tmp_path / "2024-01-15.md"
        file_path.write_text("# Test entry")

        # Create a person ahead of time
        from dev.database.managers import PersonManager
        person_mgr = PersonManager(test_db, None)
        existing_person = person_mgr.create({"name": "Charlie"})
        test_db.commit()

        # Create entry with mix: string + ID + object
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "people": [
                "Alice",              # String - will be created
                existing_person.id,   # ID - will be looked up
                existing_person       # Object - used directly
            ]
        })

        test_db.commit()
        test_db.refresh(entry)

        # Verify we have 2 people (Alice + Charlie)
        # Charlie shouldn't be duplicated even though passed twice
        assert len(entry.people) == 2
        people_names = {p.name for p in entry.people}
        assert people_names == {"Alice", "Charlie"}

    def test_entry_with_complex_yaml_scenario(self, entry_manager, test_db, tmp_path):
        """Test complex scenario matching example_yaml.md format."""
        file_path = tmp_path / "2024-03-15.md"
        file_path.write_text("# Complex entry")

        entry = entry_manager.create({
            "date": "2024-03-15",
            "file_path": str(file_path),
            "word_count": 2847,
            "reading_time": 11.2,
            "people": ["Mom", "Alice", "Dr-Martinez", "María-José"],
            "events": ["therapy-breakthrough", "alice-wedding-planning"],
            "cities": ["Madrid", "Barcelona", "San-Diego"],
            "tags": ["family", "therapy", "breakthrough", "grief", "travel"],
            "notes": "Breakthrough session with Dr. Martinez."
        })

        test_db.commit()
        test_db.refresh(entry)

        # Verify all relationships were created
        assert len(entry.people) == 4
        assert len(entry.events) == 2
        assert len(entry.cities) == 3
        assert len(entry.tags) == 5

        # Verify data quality
        assert entry.word_count == 2847
        assert entry.reading_time == 11.2
        assert entry.notes == "Breakthrough session with Dr. Martinez."

        # Verify people were normalized correctly
        people_names = {p.name for p in entry.people}
        assert "Dr-Martinez" in people_names
        assert "María-José" in people_names

        # Verify events were normalized
        event_names = {e.event for e in entry.events}
        assert "therapy-breakthrough" in event_names
        assert "alice-wedding-planning" in event_names

    def test_update_entry_with_string_additions(self, entry_manager, test_db, tmp_path):
        """Test updating entry by adding string relationships incrementally."""
        file_path = tmp_path / "2024-01-15.md"
        file_path.write_text("# Test entry")

        # Create entry with initial people
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "people": ["Alice"]
        })
        test_db.commit()

        # Update with additional people (incremental)
        entry_manager.update_relationships(
            entry,
            {"people": ["Bob", "Charlie"]},
            incremental=True
        )
        test_db.commit()
        test_db.refresh(entry)

        # Should have all three people
        assert len(entry.people) == 3
        people_names = {p.name for p in entry.people}
        assert people_names == {"Alice", "Bob", "Charlie"}

    def test_duplicate_strings_handled_correctly(self, entry_manager, test_db, tmp_path):
        """Test that duplicate string names don't create duplicate entities."""
        file_path1 = tmp_path / "2024-01-15.md"
        file_path1.write_text("# Entry 1")
        file_path2 = tmp_path / "2024-01-16.md"
        file_path2.write_text("# Entry 2")

        # Create first entry with Alice
        entry1 = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path1),
            "people": ["Alice"]
        })
        test_db.commit()

        # Create second entry also mentioning Alice
        entry2 = entry_manager.create({
            "date": "2024-01-16",
            "file_path": str(file_path2),
            "people": ["Alice", "Bob"]
        })
        test_db.commit()

        # Should only have 2 total people in database (Alice + Bob)
        total_people = test_db.query(Person).count()
        assert total_people == 2

        # Both entries should reference the same Alice
        alice_1 = next(p for p in entry1.people if p.name == "Alice")
        alice_2 = next(p for p in entry2.people if p.name == "Alice")
        assert alice_1.id == alice_2.id

    def test_error_on_empty_string(self, entry_manager, test_db, tmp_path):
        """Test that empty strings raise validation errors."""
        file_path = tmp_path / "2024-01-15.md"
        file_path.write_text("# Test entry")

        with pytest.raises(Exception):  # Will be ValidationError
            entry_manager.create({
                "date": "2024-01-15",
                "file_path": str(file_path),
                "people": [""]  # Empty string should fail
            })
