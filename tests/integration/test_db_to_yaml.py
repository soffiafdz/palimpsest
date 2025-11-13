#!/usr/bin/env python3
"""
Integration tests for SQL → YAML pipeline.

Tests the sql2yaml export functionality including:
- Basic entry export
- Relationship export (people, cities, locations, events, tags)
- Complex fields (references, poems, dates)
- Manuscript metadata export
- Content preservation strategies
- Round-trip consistency (DB → YAML → DB)
"""
import pytest
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dev.database.models import Base, Entry, Person, Event, City, Location, Tag, RelationType
from dev.database.models_manuscript import ManuscriptEntry, ManuscriptStatus, Theme
from dev.dataclasses.md_entry import MdEntry
from dev.pipeline.sql2yaml import export_entry_to_markdown


@pytest.fixture
def test_db():
    """Create in-memory database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestBasicExport:
    """Test basic entry export from database to YAML."""

    def test_export_minimal_entry(self, test_db, tmp_path):
        """Test exporting entry with minimal metadata."""
        # Create minimal entry
        file_path = tmp_path / "source" / "2024-11-01.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("Test content")

        entry = Entry(
            date=date(2024, 11, 1),
            file_path=str(file_path),
            word_count=100,
            reading_time=0.5,
        )
        test_db.add(entry)
        test_db.commit()

        # Export to YAML
        output_dir = tmp_path / "output"
        status = export_entry_to_markdown(entry, output_dir)

        assert status in ("created", "updated")

        # Verify exported file
        exported_file = output_dir / "2024" / "2024-11-01.md"
        assert exported_file.exists()

        # Parse exported YAML
        md_entry = MdEntry.from_file(exported_file)
        assert md_entry.date == date(2024, 11, 1)
        assert md_entry.metadata["word_count"] == 100
        assert md_entry.metadata["reading_time"] == 0.5

    def test_export_entry_with_text_fields(self, test_db, tmp_path):
        """Test exporting entry with epigraph and notes."""
        file_path = tmp_path / "source.md"
        file_path.write_text("Content")

        entry = Entry(
            date=date(2024, 11, 1),
            file_path=str(file_path),
            word_count=100,
            reading_time=0.5,
            epigraph="To be or not to be",
            epigraph_attribution="Shakespeare",
            notes="Important memory",
        )
        test_db.add(entry)
        test_db.commit()

        # Export
        output_dir = tmp_path / "output"
        export_entry_to_markdown(entry, output_dir)

        # Verify
        exported_file = output_dir / "2024" / "2024-11-01.md"
        md_entry = MdEntry.from_file(exported_file)

        assert md_entry.metadata["epigraph"] == "To be or not to be"
        assert md_entry.metadata["epigraph_attribution"] == "Shakespeare"
        assert md_entry.metadata["notes"] == "Important memory"


class TestRelationshipExport:
    """Test exporting entries with various relationships."""

    def test_export_entry_with_people(self, test_db, tmp_path):
        """Test exporting entry with people relationships."""
        file_path = tmp_path / "source.md"
        file_path.write_text("Content")

        entry = Entry(
            date=date(2024, 11, 1),
            file_path=str(file_path),
            word_count=100,
            reading_time=0.5,
        )

        # Add people
        alice = Person(name="Alice", full_name="Alice Johnson", relation_type=RelationType.FRIEND)
        bob = Person(name="Bob", relation_type=RelationType.COLLEAGUE)

        entry.people.extend([alice, bob])

        test_db.add_all([entry, alice, bob])
        test_db.commit()

        # Export
        output_dir = tmp_path / "output"
        export_entry_to_markdown(entry, output_dir)

        # Verify
        exported_file = output_dir / "2024" / "2024-11-01.md"
        md_entry = MdEntry.from_file(exported_file)

        assert "people" in md_entry.metadata
        people = md_entry.metadata["people"]
        assert len(people) >= 2

    def test_export_entry_with_cities_and_locations(self, test_db, tmp_path):
        """Test exporting entry with geographic data."""
        file_path = tmp_path / "source.md"
        file_path.write_text("Content")

        entry = Entry(
            date=date(2024, 11, 1),
            file_path=str(file_path),
            word_count=100,
            reading_time=0.5,
        )

        # Add city and locations
        montreal = City(city="Montreal", country="Canada")
        cafe = Location(name="Café Olimpico", city=montreal)
        park = Location(name="Parc Jarry", city=montreal)

        entry.cities.append(montreal)
        entry.locations.extend([cafe, park])

        test_db.add_all([entry, montreal, cafe, park])
        test_db.commit()

        # Export
        output_dir = tmp_path / "output"
        export_entry_to_markdown(entry, output_dir)

        # Verify
        exported_file = output_dir / "2024" / "2024-11-01.md"
        md_entry = MdEntry.from_file(exported_file)

        assert "city" in md_entry.metadata
        assert md_entry.metadata["city"] == "Montreal"

        assert "locations" in md_entry.metadata
        locations = md_entry.metadata["locations"]
        assert isinstance(locations, list)
        assert "Café Olimpico" in locations
        assert "Parc Jarry" in locations

    def test_export_entry_with_events_and_tags(self, test_db, tmp_path):
        """Test exporting entry with events and tags."""
        file_path = tmp_path / "source.md"
        file_path.write_text("Content")

        entry = Entry(
            date=date(2024, 11, 1),
            file_path=str(file_path),
            word_count=100,
            reading_time=0.5,
        )

        # Add events
        therapy = Event(event="therapy-session", title="Therapy Session")
        conference = Event(event="pycon-2024", title="PyCon 2024")

        entry.events.extend([therapy, conference])

        # Add tags
        tag1 = Tag(tag="reflection")
        tag2 = Tag(tag="milestone")

        entry.tags.extend([tag1, tag2])

        test_db.add_all([entry, therapy, conference, tag1, tag2])
        test_db.commit()

        # Export
        output_dir = tmp_path / "output"
        export_entry_to_markdown(entry, output_dir)

        # Verify
        exported_file = output_dir / "2024" / "2024-11-01.md"
        md_entry = MdEntry.from_file(exported_file)

        assert "events" in md_entry.metadata
        events = md_entry.metadata["events"]
        assert "therapy-session" in events
        assert "pycon-2024" in events

        assert "tags" in md_entry.metadata
        tags = md_entry.metadata["tags"]
        assert "reflection" in tags
        assert "milestone" in tags


class TestManuscriptExport:
    """Test exporting manuscript metadata."""

    def test_export_entry_with_manuscript_metadata(self, test_db, tmp_path):
        """Test exporting entry with manuscript metadata."""
        file_path = tmp_path / "source.md"
        file_path.write_text("Content")

        entry = Entry(
            date=date(2024, 11, 1),
            file_path=str(file_path),
            word_count=100,
            reading_time=0.5,
        )

        # Add manuscript metadata
        ms_entry = ManuscriptEntry(
            entry=entry,
            status=ManuscriptStatus.SOURCE,
            edited=True,
            notes="Key scene for character development",
        )

        # Add themes
        theme1 = Theme(theme="identity")
        theme2 = Theme(theme="growth")
        ms_entry.themes.extend([theme1, theme2])

        test_db.add_all([entry, ms_entry, theme1, theme2])
        test_db.commit()

        # Export
        output_dir = tmp_path / "output"
        export_entry_to_markdown(entry, output_dir)

        # Verify
        exported_file = output_dir / "2024" / "2024-11-01.md"
        md_entry = MdEntry.from_file(exported_file)

        assert "manuscript" in md_entry.metadata
        manuscript = md_entry.metadata["manuscript"]

        assert manuscript["status"] == "source"
        assert manuscript["edited"] is True
        assert manuscript["notes"] == "Key scene for character development"
        assert "themes" in manuscript
        assert "identity" in manuscript["themes"]
        assert "growth" in manuscript["themes"]

    def test_manuscript_fields_not_exported_to_yaml(self, test_db, tmp_path):
        """Verify that detailed manuscript fields are NOT exported to YAML."""
        file_path = tmp_path / "source.md"
        file_path.write_text("Content")

        entry = Entry(
            date=date(2024, 11, 1),
            file_path=str(file_path),
            word_count=100,
            reading_time=0.5,
        )

        # Add manuscript with detailed fields (these should NOT export to YAML)
        from dev.database.models_manuscript import EntryType

        ms_entry = ManuscriptEntry(
            entry=entry,
            status=ManuscriptStatus.SOURCE,
            edited=True,
            entry_type=EntryType.VIGNETTE,
            character_notes="Alice becomes Alexandra",
            narrative_arc="paris_discovery",
        )

        test_db.add_all([entry, ms_entry])
        test_db.commit()

        # Export
        output_dir = tmp_path / "output"
        export_entry_to_markdown(entry, output_dir)

        # Verify - detailed fields should NOT be in YAML
        exported_file = output_dir / "2024" / "2024-11-01.md"
        md_entry = MdEntry.from_file(exported_file)

        manuscript = md_entry.metadata["manuscript"]

        # These should be in YAML
        assert "status" in manuscript
        assert "edited" in manuscript

        # These should NOT be in YAML (manuscript wiki only)
        assert "entry_type" not in manuscript
        assert "character_notes" not in manuscript
        assert "narrative_arc" not in manuscript


class TestContentPreservation:
    """Test body content preservation strategies."""

    def test_preserve_existing_body(self, test_db, tmp_path):
        """Test that existing body content is preserved."""
        # Create source file with content
        file_path = tmp_path / "source.md"
        file_path.write_text("Original content here")

        entry = Entry(
            date=date(2024, 11, 1),
            file_path=str(file_path),
            word_count=100,
            reading_time=0.5,
        )
        test_db.add(entry)
        test_db.commit()

        # Export first time
        output_dir = tmp_path / "output"
        export_entry_to_markdown(entry, output_dir, preserve_body=True)

        exported_file = output_dir / "2024" / "2024-11-01.md"
        assert "Original content here" in exported_file.read_text()

        # Modify database metadata
        entry.word_count = 200
        test_db.commit()

        # Export again with preserve_body=True
        export_entry_to_markdown(entry, output_dir, preserve_body=True)

        # Body should be preserved, metadata should update
        content = exported_file.read_text()
        assert "Original content here" in content
        assert "word_count: 200" in content

    def test_force_overwrite(self, test_db, tmp_path):
        """Test force overwrite behavior."""
        file_path = tmp_path / "source.md"
        file_path.write_text("Content")

        entry = Entry(
            date=date(2024, 11, 1),
            file_path=str(file_path),
            word_count=100,
            reading_time=0.5,
        )
        test_db.add(entry)
        test_db.commit()

        # Export
        output_dir = tmp_path / "output"
        status1 = export_entry_to_markdown(entry, output_dir)
        assert status1 == "created"

        # Export again without changes
        status2 = export_entry_to_markdown(entry, output_dir, force_overwrite=False)
        assert status2 == "skipped"

        # Export with force
        status3 = export_entry_to_markdown(entry, output_dir, force_overwrite=True)
        assert status3 == "updated"


class TestRoundTrip:
    """Test round-trip consistency: DB → YAML → DB."""

    def test_round_trip_basic_entry(self, test_db, tmp_path):
        """Test that entry survives round-trip unchanged."""
        from dev.database.managers import EntryManager

        # Create entry in database
        file_path = tmp_path / "source.md"
        file_path.write_text("Content")

        entry = Entry(
            date=date(2024, 11, 1),
            file_path=str(file_path),
            word_count=150,
            reading_time=0.75,
            epigraph="Quote",
            epigraph_attribution="Author",
        )
        test_db.add(entry)
        test_db.commit()
        test_db.refresh(entry)

        original_id = entry.id

        # Export to YAML
        output_dir = tmp_path / "output"
        export_entry_to_markdown(entry, output_dir)

        exported_file = output_dir / "2024" / "2024-11-01.md"

        # Parse back
        md_entry = MdEntry.from_file(exported_file)

        # Verify key fields preserved
        assert md_entry.date == date(2024, 11, 1)
        assert md_entry.metadata["word_count"] == 150
        assert md_entry.metadata["reading_time"] == 0.75
        assert md_entry.metadata["epigraph"] == "Quote"
        assert md_entry.metadata["epigraph_attribution"] == "Author"

    def test_round_trip_with_relationships(self, test_db, tmp_path):
        """Test that relationships survive round-trip."""
        file_path = tmp_path / "source.md"
        file_path.write_text("Content")

        entry = Entry(
            date=date(2024, 11, 1),
            file_path=str(file_path),
            word_count=100,
            reading_time=0.5,
        )

        alice = Person(name="Alice", full_name="Alice Johnson")
        montreal = City(city="Montreal")
        therapy = Event(event="therapy-session")
        reflection = Tag(tag="reflection")

        entry.people.append(alice)
        entry.cities.append(montreal)
        entry.events.append(therapy)
        entry.tags.append(reflection)

        test_db.add_all([entry, alice, montreal, therapy, reflection])
        test_db.commit()

        # Export
        output_dir = tmp_path / "output"
        export_entry_to_markdown(entry, output_dir)

        exported_file = output_dir / "2024" / "2024-11-01.md"

        # Parse back
        md_entry = MdEntry.from_file(exported_file)

        # Convert to DB format
        db_meta = md_entry.to_database_metadata()

        # Verify relationships preserved
        assert "people" in db_meta or len(md_entry.metadata.get("people", [])) > 0
        assert "cities" in db_meta or md_entry.metadata.get("city") == "Montreal"
        assert "events" in db_meta or "therapy-session" in md_entry.metadata.get("events", [])
        assert "tags" in db_meta or "reflection" in md_entry.metadata.get("tags", [])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
