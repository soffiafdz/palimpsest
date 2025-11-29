#!/usr/bin/env python3
"""
Integration tests for wiki2sql import functions.

Tests the actual import functions in wiki2sql.py using PalimpsestDB
to improve coverage of the import logic.
"""
import pytest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from dev.database.manager import PalimpsestDB
from dev.database.models import Person, Entry, Event, RelationType
from dev.database.models_manuscript import (
    ManuscriptEntry,
    ManuscriptPerson,
    ManuscriptEvent,
    ManuscriptStatus,
)
from dev.pipeline.wiki2sql import (
    import_person,
    import_people,
    import_entry,
    import_entries,
    import_event,
    import_events,
    import_manuscript_entry,
    import_all_manuscript_entries,
    import_manuscript_character,
    import_all_manuscript_characters,
    import_manuscript_event,
    import_all_manuscript_events,
    import_all,
    ImportStats,
)


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = PalimpsestDB(
            db_path=db_path,
            alembic_dir=None,  # Skip migrations for tests
            enable_auto_backup=False,
        )

        # Initialize database schema
        from dev.database.models import Base
        from dev.database.models_manuscript import Base as MSBase
        Base.metadata.create_all(db.engine)
        MSBase.metadata.create_all(db.engine)

        yield db
        db.engine.dispose()


class TestImportPerson:
    """Test import_person function."""

    def test_import_person_skips_always(self, temp_db, tmp_path):
        """Test that person import always skips (no editable DB fields)."""
        # Create person in database
        with temp_db.session_scope() as session:
            person = Person(name="Alice", relation_type=RelationType.FRIEND)
            session.add(person)
            session.commit()

        # Create wiki file
        wiki_file = tmp_path / "alice.md"
        wiki_file.write_text("""# Palimpsest — Person

## Alice

### Category
Friend

### Notes
These notes are wiki-only and not stored in database.
""")

        # Import should skip (no database fields to update)
        result = import_person(wiki_file, temp_db)
        assert result == "skipped"

    def test_import_person_not_found(self, temp_db, tmp_path):
        """Test importing person that doesn't exist in database."""
        wiki_file = tmp_path / "nonexistent.md"
        wiki_file.write_text("""# Palimpsest — Person

## NonexistentPerson

### Category
Friend

### Notes
This person doesn't exist in database.
""")

        result = import_person(wiki_file, temp_db)
        assert result == "skipped"

    def test_import_person_invalid_file(self, temp_db, tmp_path):
        """Test importing invalid wiki file returns error."""
        wiki_file = tmp_path / "invalid.md"
        wiki_file.write_text("Invalid content")

        result = import_person(wiki_file, temp_db)
        # Should skip if parsing fails
        assert result in ["skipped", "error"]


class TestImportPeople:
    """Test import_people batch function."""

    def test_import_people_empty_dir(self, temp_db, tmp_path):
        """Test importing from nonexistent people directory."""
        stats = import_people(tmp_path, temp_db)
        assert stats.files_processed == 0
        assert stats.records_updated == 0

    def test_import_people_multiple_files(self, temp_db, tmp_path):
        """Test batch importing multiple people."""
        # Create people in database
        with temp_db.session_scope() as session:
            session.add(Person(name="Alice", relation_type=RelationType.FRIEND))
            session.add(Person(name="Bob", relation_type=RelationType.COLLEAGUE))
            session.commit()

        # Create wiki files
        people_dir = tmp_path / "people"
        people_dir.mkdir()

        (people_dir / "alice.md").write_text("""# Palimpsest — Person
## Alice
### Category
Friend
### Notes
Alice notes
""")

        (people_dir / "bob.md").write_text("""# Palimpsest — Person
## Bob
### Category
Colleague
### Notes
Bob notes
""")

        # Import all
        stats = import_people(tmp_path, temp_db)
        assert stats.files_processed == 2
        # Both skip because person has no editable DB fields
        assert stats.records_skipped == 2


class TestImportEntry:
    """Test import_entry function."""

    def test_import_entry_updates_notes(self, temp_db, tmp_path):
        """Test importing entry notes from wiki."""
        # Create entry in database
        source_file = tmp_path / "source.md"
        source_file.write_text("Journal content")

        with temp_db.session_scope() as session:
            entry = Entry(
                date=date(2024, 11, 1),
                file_path=str(source_file),
                word_count=100,
                reading_time=0.5,
                notes=None,
            )
            session.add(entry)
            session.commit()

        # Create wiki file with notes
        wiki_file = tmp_path / "2024-11-01.md"
        wiki_file.write_text("""# Palimpsest — Entry

## 2024-11-01

### Notes

This entry is important for the manuscript.
Captures a pivotal moment in the narrative.
""")

        # Import entry
        result = import_entry(wiki_file, temp_db)
        assert result == "updated"

        # Verify notes were updated
        with temp_db.session_scope() as session:
            entry = session.query(Entry).filter_by(date=date(2024, 11, 1)).first()
            assert entry.notes is not None
            assert "pivotal moment" in entry.notes

    def test_import_entry_no_changes_skips(self, temp_db, tmp_path):
        """Test that import skips when notes haven't changed."""
        source_file = tmp_path / "source.md"
        source_file.write_text("Content")

        with temp_db.session_scope() as session:
            entry = Entry(
                date=date(2024, 11, 1),
                file_path=str(source_file),
                word_count=100,
                reading_time=0.5,
                notes="Existing notes",
            )
            session.add(entry)
            session.commit()

        # Create wiki file with same notes
        wiki_file = tmp_path / "2024-11-01.md"
        wiki_file.write_text("""# Palimpsest — Entry

## 2024-11-01

### Notes

Existing notes
""")

        result = import_entry(wiki_file, temp_db)
        assert result == "skipped"

    def test_import_entry_not_found(self, temp_db, tmp_path):
        """Test importing entry that doesn't exist."""
        wiki_file = tmp_path / "2024-99-99.md"
        wiki_file.write_text("""# Palimpsest — Entry

## 2024-99-99

### Notes
Nonexistent entry
""")

        result = import_entry(wiki_file, temp_db)
        assert result == "skipped"


class TestImportEntries:
    """Test import_entries batch function."""

    def test_import_entries_empty_dir(self, temp_db, tmp_path):
        """Test importing from empty entries directory."""
        stats = import_entries(tmp_path, temp_db)
        assert stats.files_processed == 0

    def test_import_entries_multiple(self, temp_db, tmp_path):
        """Test batch importing multiple entries."""
        source1 = tmp_path / "source1.md"
        source1.write_text("Content 1")
        source2 = tmp_path / "source2.md"
        source2.write_text("Content 2")

        # Create entries in database
        with temp_db.session_scope() as session:
            session.add(Entry(
                date=date(2024, 11, 1),
                file_path=str(source1),
                word_count=100,
                reading_time=0.5,
                notes=None,
            ))
            session.add(Entry(
                date=date(2024, 11, 2),
                file_path=str(source2),
                word_count=100,
                reading_time=0.5,
                notes=None,
            ))
            session.commit()

        # Create wiki files
        entries_dir = tmp_path / "entries" / "2024"
        entries_dir.mkdir(parents=True)

        (entries_dir / "2024-11-01.md").write_text("""# Palimpsest — Entry
## 2024-11-01
### Notes
Entry 1 notes
""")

        (entries_dir / "2024-11-02.md").write_text("""# Palimpsest — Entry
## 2024-11-02
### Notes
Entry 2 notes
""")

        # Import all
        stats = import_entries(tmp_path, temp_db)
        assert stats.files_processed == 2
        assert stats.records_updated == 2


class TestImportEvent:
    """Test import_event function."""

    def test_import_event_updates_notes(self, temp_db, tmp_path):
        """Test importing event notes from wiki."""
        # Create event in database
        with temp_db.session_scope() as session:
            event = Event(event="Paris Trip", notes=None)
            session.add(event)
            session.commit()

        # Create wiki file
        wiki_file = tmp_path / "paris_trip.md"
        wiki_file.write_text("""# Palimpsest — Event

## Paris Trip

### Notes

The Paris trip was transformative.
Led to major personal insights.
""")

        result = import_event(wiki_file, temp_db)
        assert result == "updated"

        # Verify
        with temp_db.session_scope() as session:
            event = session.query(Event).filter_by(event="Paris Trip").first()
            assert "transformative" in event.notes

    def test_import_event_no_changes(self, temp_db, tmp_path):
        """Test event import skips when no changes."""
        with temp_db.session_scope() as session:
            event = Event(event="Paris Trip", notes="Existing notes")
            session.add(event)
            session.commit()

        wiki_file = tmp_path / "paris_trip.md"
        wiki_file.write_text("""# Palimpsest — Event
## Paris Trip
### Notes
Existing notes
""")

        result = import_event(wiki_file, temp_db)
        assert result == "skipped"


class TestImportEvents:
    """Test import_events batch function."""

    def test_import_events_empty_dir(self, temp_db, tmp_path):
        """Test importing from empty events directory."""
        stats = import_events(tmp_path, temp_db)
        assert stats.files_processed == 0

    def test_import_events_multiple(self, temp_db, tmp_path):
        """Test batch importing multiple events."""
        # Create events in database
        with temp_db.session_scope() as session:
            session.add(Event(event="Paris Trip", notes=None))
            session.add(Event(event="London Visit", notes=None))
            session.commit()

        # Create wiki files
        events_dir = tmp_path / "events"
        events_dir.mkdir()

        (events_dir / "paris_trip.md").write_text("""# Palimpsest — Event
## Paris Trip
### Notes
Paris notes
""")

        (events_dir / "london_visit.md").write_text("""# Palimpsest — Event
## London Visit
### Notes
London notes
""")

        stats = import_events(tmp_path, temp_db)
        assert stats.files_processed == 2
        assert stats.records_updated == 2


class TestImportManuscriptEntry:
    """Test import_manuscript_entry function."""

    def test_import_manuscript_entry_updates_notes(self, temp_db, tmp_path):
        """Test importing manuscript entry notes."""
        source = tmp_path / "source.md"
        source.write_text("Content")

        # Create entry with manuscript
        with temp_db.session_scope() as session:
            entry = Entry(
                date=date(2024, 11, 1),
                file_path=str(source),
                word_count=100,
                reading_time=0.5,
            )
            ms_entry = ManuscriptEntry(
                entry=entry,
                status=ManuscriptStatus.SOURCE,
                edited=True,
                notes=None,
                character_notes=None,
            )
            session.add_all([entry, ms_entry])
            session.commit()

        # Create manuscript wiki file
        wiki_file = tmp_path / "2024-11-01.md"
        wiki_file.write_text("""# Palimpsest — Manuscript Entry

## 2024-11-01

### Adaptation Notes

Transform into dialogue scene.
Focus on subtext.

### Character Notes

Alice as Alexandra - soften tone.
""")

        result = import_manuscript_entry(wiki_file, temp_db)
        assert result == "updated"

        # Verify both notes fields updated
        with temp_db.session_scope() as session:
            entry = session.query(Entry).filter_by(date=date(2024, 11, 1)).first()
            ms_entry = entry.manuscript
            assert "dialogue scene" in ms_entry.notes
            assert "Alexandra" in ms_entry.character_notes

    def test_import_manuscript_entry_no_manuscript(self, temp_db, tmp_path):
        """Test importing for entry without manuscript record."""
        source = tmp_path / "source.md"
        source.write_text("Content")

        # Create entry WITHOUT manuscript
        with temp_db.session_scope() as session:
            entry = Entry(
                date=date(2024, 11, 1),
                file_path=str(source),
                word_count=100,
                reading_time=0.5,
            )
            session.add(entry)
            session.commit()

        wiki_file = tmp_path / "2024-11-01.md"
        wiki_file.write_text("""# Palimpsest — Manuscript Entry
## 2024-11-01
### Adaptation Notes
Some notes
""")

        result = import_manuscript_entry(wiki_file, temp_db)
        assert result == "skipped"


class TestImportManuscriptCharacter:
    """Test import_manuscript_character function."""

    def test_import_manuscript_character_updates_fields(self, temp_db, tmp_path):
        """Test importing character description and arc."""
        # Create person and character mapping
        with temp_db.session_scope() as session:
            person = Person(name="Alice", full_name="Alice Johnson")
            ms_person = ManuscriptPerson(
                person=person,
                character="Alexandra",
                character_description=None,
                character_arc=None,
                voice_notes=None,
                appearance_notes=None,
            )
            session.add_all([person, ms_person])
            session.commit()

        # Create wiki file
        wiki_file = tmp_path / "alexandra.md"
        wiki_file.write_text("""# Palimpsest — Character

## Alexandra

**Real Person:** Alice

### Character Description

Protagonist. Introspective writer.

### Character Arc

Journey from isolation to connection.

### Voice Notes

First person perspective.

### Appearance Notes

Dark hair, intense gaze.
""")

        result = import_manuscript_character(wiki_file, temp_db)
        assert result == "updated"

        # Verify all fields updated
        with temp_db.session_scope() as session:
            ms_person = session.query(ManuscriptPerson).filter_by(character="Alexandra").first()
            assert "Protagonist" in ms_person.character_description
            assert "isolation" in ms_person.character_arc
            assert "First person" in ms_person.voice_notes
            assert "Dark hair" in ms_person.appearance_notes

    def test_import_manuscript_character_not_found(self, temp_db, tmp_path):
        """Test importing nonexistent character."""
        wiki_file = tmp_path / "nonexistent.md"
        wiki_file.write_text("""# Palimpsest — Character
## Nonexistent
### Character Description
Some description
""")

        result = import_manuscript_character(wiki_file, temp_db)
        assert result == "skipped"


class TestImportManuscriptEvent:
    """Test import_manuscript_event function."""

    def test_import_manuscript_event_updates_notes(self, temp_db, tmp_path):
        """Test importing manuscript event notes."""
        # Create event with manuscript
        with temp_db.session_scope() as session:
            event = Event(event="Paris Trip")
            ms_event = ManuscriptEvent(event=event, notes=None)
            session.add_all([event, ms_event])
            session.commit()

        wiki_file = tmp_path / "paris_trip.md"
        wiki_file.write_text("""# Palimpsest — Manuscript Event

## Paris Trip

### Manuscript Notes

Use as turning point in narrative arc.
""")

        result = import_manuscript_event(wiki_file, temp_db)
        assert result == "updated"

        # Verify
        with temp_db.session_scope() as session:
            event = session.query(Event).filter_by(event="Paris Trip").first()
            ms_event = event.manuscript
            assert "turning point" in ms_event.notes


class TestBatchManuscriptImports:
    """Test batch manuscript import functions."""

    def test_import_all_manuscript_entries(self, temp_db, tmp_path):
        """Test batch importing manuscript entries."""
        # Create entries with manuscripts
        with temp_db.session_scope() as session:
            for day in [1, 2]:
                # Create unique source file for each entry
                source = tmp_path / f"source{day}.md"
                source.write_text("Content")

                entry = Entry(
                    date=date(2024, 11, day),
                    file_path=str(source),
                    word_count=100,
                    reading_time=0.5,
                )
                ms_entry = ManuscriptEntry(
                    entry=entry,
                    status=ManuscriptStatus.SOURCE,
                    edited=True,
                )
                session.add_all([entry, ms_entry])
            session.commit()

        # Create wiki files
        ms_entries_dir = tmp_path / "manuscript" / "entries" / "2024"
        ms_entries_dir.mkdir(parents=True)

        (ms_entries_dir / "2024-11-01.md").write_text("""# Palimpsest — Manuscript Entry
## 2024-11-01
### Adaptation Notes
Notes 1
""")

        (ms_entries_dir / "2024-11-02.md").write_text("""# Palimpsest — Manuscript Entry
## 2024-11-02
### Adaptation Notes
Notes 2
""")

        stats = import_all_manuscript_entries(temp_db, tmp_path)
        assert stats.files_processed == 2
        assert stats.records_updated == 2

    def test_import_all_manuscript_characters(self, temp_db, tmp_path):
        """Test batch importing manuscript characters."""
        # Create characters
        with temp_db.session_scope() as session:
            for name, char in [("Alice", "Alexandra"), ("Bob", "Robert")]:
                person = Person(name=name)
                ms_person = ManuscriptPerson(person=person, character=char)
                session.add_all([person, ms_person])
            session.commit()

        # Create wiki files
        chars_dir = tmp_path / "manuscript" / "characters"
        chars_dir.mkdir(parents=True)

        (chars_dir / "alexandra.md").write_text("""# Palimpsest — Character
## Alexandra
### Character Description
Alexandra description
""")

        (chars_dir / "robert.md").write_text("""# Palimpsest — Character
## Robert
### Character Description
Robert description
""")

        stats = import_all_manuscript_characters(temp_db, tmp_path)
        assert stats.files_processed == 2
        assert stats.records_updated == 2

    def test_import_all_manuscript_events(self, temp_db, tmp_path):
        """Test batch importing manuscript events."""
        # Create events with manuscripts
        with temp_db.session_scope() as session:
            for event_name in ["Paris Trip", "London Visit"]:
                event = Event(event=event_name)
                ms_event = ManuscriptEvent(event=event)
                session.add_all([event, ms_event])
            session.commit()

        # Create wiki files
        events_dir = tmp_path / "manuscript" / "events"
        events_dir.mkdir(parents=True)

        (events_dir / "paris_trip.md").write_text("""# Palimpsest — Manuscript Event
## Paris Trip
### Manuscript Notes
Paris manuscript notes
""")

        (events_dir / "london_visit.md").write_text("""# Palimpsest — Manuscript Event
## London Visit
### Manuscript Notes
London manuscript notes
""")

        stats = import_all_manuscript_events(temp_db, tmp_path)
        assert stats.files_processed == 2
        assert stats.records_updated == 2


class TestImportAll:
    """Test import_all function."""

    def test_import_all_combines_stats(self, temp_db, tmp_path):
        """Test that import_all imports all entity types."""
        # Create minimal data for each type
        source = tmp_path / "source.md"
        source.write_text("Content")

        with temp_db.session_scope() as session:
            # Person
            person = Person(name="Alice", relation_type=RelationType.FRIEND)
            # Entry
            entry = Entry(
                date=date(2024, 11, 1),
                file_path=str(source),
                word_count=100,
                reading_time=0.5,
            )
            # Event
            event = Event(event="Paris Trip")
            session.add_all([person, entry, event])
            session.commit()

        # Create minimal wiki structure
        (tmp_path / "people").mkdir()
        (tmp_path / "people" / "alice.md").write_text("""# Palimpsest — Person
## Alice
### Category
Friend
""")

        entries_dir = tmp_path / "entries" / "2024"
        entries_dir.mkdir(parents=True)
        (entries_dir / "2024-11-01.md").write_text("""# Palimpsest — Entry
## 2024-11-01
### Notes
Entry notes
""")

        (tmp_path / "events").mkdir()
        (tmp_path / "events" / "paris_trip.md").write_text("""# Palimpsest — Event
## Paris Trip
### Notes
Event notes
""")

        # Import all
        stats = import_all(tmp_path, temp_db)

        # Should have processed files from all types
        assert stats.files_processed >= 3  # At least person, entry, event


class TestImportStats:
    """Test ImportStats dataclass."""

    def test_import_stats_initialization(self):
        """Test ImportStats initializes to zero."""
        stats = ImportStats()
        assert stats.files_processed == 0
        assert stats.records_updated == 0
        assert stats.records_skipped == 0
        assert stats.errors == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
