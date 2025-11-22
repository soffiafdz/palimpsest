#!/usr/bin/env python3
"""
Integration tests for date context parsing with nested people/locations.

These tests verify that people and locations referenced in date contexts
are properly created and linked in the database.

Note: These tests assume that the YAML parsing layer has already cleaned
@ and # symbols from the context strings and extracted the entities.
"""
import pytest
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dev.database.models import Base, Entry, Person, Location, MentionedDate
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


class TestDateContextWithNestedEntities:
    """Test dates with nested people/locations from context parsing."""

    def test_date_with_person(self, entry_manager, test_db, tmp_path):
        """Test date with person in context (already extracted by YAML parser)."""
        file_path = tmp_path / "2024-01-15.md"
        file_path.write_text("# Test entry")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "dates": [
                {
                    "date": "2024-01-10",
                    "context": "Met with Alice",  # Cleaned context (@ removed)
                    "people": ["Alice"]  # Extracted from @Alice
                }
            ]
        })

        test_db.commit()
        test_db.refresh(entry)

        # Find the mentioned date with context
        mentioned_dates = [d for d in entry.dates if d.context]
        assert len(mentioned_dates) == 1
        mentioned_date = mentioned_dates[0]

        assert mentioned_date.date == date(2024, 1, 10)
        assert mentioned_date.context == "Met with Alice"

        # Verify person was auto-created and linked
        assert len(mentioned_date.people) == 1
        assert mentioned_date.people[0].name == "Alice"

    def test_date_with_multiple_people(self, entry_manager, test_db, tmp_path):
        """Test date with multiple people."""
        file_path = tmp_path / "2024-01-15.md"
        file_path.write_text("# Test entry")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "dates": [
                {
                    "date": "2024-01-10",
                    "context": "Dinner with Alice and Bob",
                    "people": ["Alice", "Bob"]
                }
            ]
        })

        test_db.commit()
        test_db.refresh(entry)

        mentioned_date = next(d for d in entry.dates if d.context)
        assert len(mentioned_date.people) == 2

        people_names = {p.name for p in mentioned_date.people}
        assert people_names == {"Alice", "Bob"}

    def test_date_with_location(self, entry_manager, test_db, tmp_path):
        """Test date with location in context."""
        file_path = tmp_path / "2024-01-15.md"
        file_path.write_text("# Test entry")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "dates": [
                {
                    "date": "2024-01-10",
                    "context": "Meeting at Office",
                    "locations": ["Office"]
                }
            ]
        })

        test_db.commit()
        test_db.refresh(entry)

        mentioned_date = next(d for d in entry.dates if d.context)
        assert len(mentioned_date.locations) == 1
        assert mentioned_date.locations[0].name == "Office"

    def test_date_with_multiple_locations(self, entry_manager, test_db, tmp_path):
        """Test date with multiple locations."""
        file_path = tmp_path / "2024-01-15.md"
        file_path.write_text("# Test entry")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "dates": [
                {
                    "date": "2024-01-10",
                    "context": "Walked from Park to Cafe",
                    "locations": ["Park", "Cafe"]
                }
            ]
        })

        test_db.commit()
        test_db.refresh(entry)

        mentioned_date = next(d for d in entry.dates if d.context)
        assert len(mentioned_date.locations) == 2

        location_names = {loc.name for loc in mentioned_date.locations}
        assert location_names == {"Park", "Cafe"}

    def test_date_with_people_and_locations(self, entry_manager, test_db, tmp_path):
        """Test date with both people and locations."""
        file_path = tmp_path / "2024-01-15.md"
        file_path.write_text("# Test entry")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "dates": [
                {
                    "date": "2024-01-10",
                    "context": "Met Alice and Bob at Cafe Central",
                    "people": ["Alice", "Bob"],
                    "locations": ["Cafe Central"]
                }
            ]
        })

        test_db.commit()
        test_db.refresh(entry)

        mentioned_date = next(d for d in entry.dates if d.context)

        # Verify both people and locations were linked
        assert len(mentioned_date.people) == 2
        assert len(mentioned_date.locations) == 1

        people_names = {p.name for p in mentioned_date.people}
        assert people_names == {"Alice", "Bob"}
        assert mentioned_date.locations[0].name == "Cafe Central"

    def test_multiple_dates_with_nested_entities(self, entry_manager, test_db, tmp_path):
        """Test entry with multiple dates, each having nested entities."""
        file_path = tmp_path / "2024-01-15.md"
        file_path.write_text("# Test entry")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "dates": [
                {
                    "date": "2024-01-10",
                    "context": "Therapy with Dr Martinez at Office",
                    "people": ["Dr Martinez"],
                    "locations": ["Office"]
                },
                {
                    "date": "2024-01-12",
                    "context": "Dinner with Alice at Restaurant",
                    "people": ["Alice"],
                    "locations": ["Restaurant"]
                }
            ]
        })

        test_db.commit()
        test_db.refresh(entry)

        # Verify each mentioned date has correct relationships
        mentioned_dates = [d for d in entry.dates if d.context]
        assert len(mentioned_dates) == 2

        date_jan10 = next(d for d in mentioned_dates if d.date == date(2024, 1, 10))
        assert len(date_jan10.people) == 1
        assert date_jan10.people[0].name == "Dr Martinez"
        assert len(date_jan10.locations) == 1
        assert date_jan10.locations[0].name == "Office"

        date_jan12 = next(d for d in mentioned_dates if d.date == date(2024, 1, 12))
        assert len(date_jan12.people) == 1
        assert date_jan12.people[0].name == "Alice"
        assert len(date_jan12.locations) == 1
        assert date_jan12.locations[0].name == "Restaurant"

    def test_entities_are_not_duplicated(self, entry_manager, test_db, tmp_path):
        """Test that same entities across multiple dates aren't duplicated."""
        file_path = tmp_path / "2024-01-15.md"
        file_path.write_text("# Test entry")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "dates": [
                {
                    "date": "2024-01-10",
                    "context": "Meeting with Alice",
                    "people": ["Alice"]
                },
                {
                    "date": "2024-01-12",
                    "context": "Lunch with Alice",
                    "people": ["Alice"]
                }
            ]
        })

        test_db.commit()
        test_db.refresh(entry)

        # Should only have one Alice in database
        total_alices = test_db.query(Person).filter_by(name="Alice").count()
        assert total_alices == 1

        # Both dates should reference the same Alice
        mentioned_dates = [d for d in entry.dates if d.context]
        alice_1 = mentioned_dates[0].people[0]
        alice_2 = mentioned_dates[1].people[0]
        assert alice_1.id == alice_2.id

    def test_location_deduplication(self, entry_manager, test_db, tmp_path):
        """Test that same location across multiple dates isn't duplicated."""
        file_path = tmp_path / "2024-01-15.md"
        file_path.write_text("# Test entry")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "dates": [
                {
                    "date": "2024-01-10",
                    "context": "Morning at Office",
                    "locations": ["Office"]
                },
                {
                    "date": "2024-01-12",
                    "context": "Meeting at Office",
                    "locations": ["Office"]
                }
            ]
        })

        test_db.commit()
        test_db.refresh(entry)

        # Should only have one Office in database
        total_offices = test_db.query(Location).filter_by(name="Office").count()
        assert total_offices == 1

        # Both dates should reference the same Office
        mentioned_dates = [d for d in entry.dates if d.context]
        office_1 = mentioned_dates[0].locations[0]
        office_2 = mentioned_dates[1].locations[0]
        assert office_1.id == office_2.id

    def test_date_context_only_no_nested_entities(self, entry_manager, test_db, tmp_path):
        """Test date with just context, no people or locations."""
        file_path = tmp_path / "2024-01-15.md"
        file_path.write_text("# Test entry")

        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "dates": [
                {
                    "date": "2024-01-10",
                    "context": "Important milestone"
                }
            ]
        })

        test_db.commit()
        test_db.refresh(entry)

        mentioned_date = next(d for d in entry.dates if d.context)
        assert mentioned_date.context == "Important milestone"
        assert len(mentioned_date.people) == 0
        assert len(mentioned_date.locations) == 0
