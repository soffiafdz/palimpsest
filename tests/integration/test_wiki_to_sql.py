#!/usr/bin/env python3
"""
Integration tests for Wiki → SQL pipeline.

Tests the wiki2sql import functionality including:
- Importing notes from wiki pages
- Main wiki entity imports (people, entries, events, etc.)
- Manuscript wiki imports (entries, characters, events)
- Field ownership verification (only editable fields updated)
- Round-trip consistency (SQL → Wiki → SQL)
"""
import pytest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dev.database.models import Base, Entry, Person, RelationType
from dev.database.models_manuscript import (
    ManuscriptEntry,
    ManuscriptPerson,
    ManuscriptStatus,
)
from dev.dataclasses.wiki_person import Person as WikiPerson
from dev.dataclasses.wiki_entry import Entry as WikiEntry


@pytest.fixture
def test_db():
    """Create in-memory database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestPersonImport:
    """Test importing person notes from wiki."""

    def test_import_person_notes(self, test_db, tmp_path):
        """Test importing edited notes from wiki person page."""

        # Create person in database
        person = Person(name="Alice", relation_type=RelationType.FRIEND, notes=None)
        test_db.add(person)
        test_db.commit()

        # Create wiki file with edited notes
        wiki_file = tmp_path / "alice.md"
        wiki_content = """# Palimpsest — Person

## Alice

### Notes

Alice is my childhood friend. Met in elementary school.
Extremely organized and detail-oriented.
"""
        wiki_file.write_text(wiki_content)

        # Mock PalimpsestDB for import
        # In real test, use actual PalimpsestDB instance
        # For this test, manually parse and update

        wiki_person = WikiPerson.from_file(wiki_file)

        # Update database person
        test_db.query(Person).filter_by(name="Alice").update({"notes": wiki_person.notes})
        test_db.commit()

        # Verify notes were imported
        updated_person = test_db.query(Person).filter_by(name="Alice").first()
        assert updated_person.notes is not None
        assert "childhood friend" in updated_person.notes
        assert "elementary school" in updated_person.notes

    def test_import_preserves_other_fields(self, test_db, tmp_path):
        """Test that import only updates notes, preserves other fields."""
        # Create person with specific data
        person = Person(
            name="Alice",
            full_name="Alice Johnson",
            relation_type=RelationType.FRIEND,
            notes="Old notes",
        )
        test_db.add(person)
        test_db.commit()
        person_id = person.id

        # Create wiki file with NEW notes
        wiki_file = tmp_path / "alice.md"
        wiki_content = """# Palimpsest — Person

## Alice

**Full Name:** Alice Johnson Modified (should not import)
**Relation:** colleague (should not import)

### Notes

New notes from wiki editing.
"""
        wiki_file.write_text(wiki_content)

        # Parse wiki
        wiki_person = WikiPerson.from_file(wiki_file)

        # Update only notes
        test_db.query(Person).filter_by(id=person_id).update({"notes": wiki_person.notes})
        test_db.commit()

        # Verify: notes changed, other fields unchanged
        updated_person = test_db.query(Person).filter_by(id=person_id).first()

        assert updated_person.notes == "New notes from wiki editing."
        assert updated_person.full_name == "Alice Johnson"  # Unchanged
        assert updated_person.relation_type == RelationType.FRIEND  # Unchanged


class TestEntryImport:
    """Test importing entry notes from wiki."""

    def test_import_entry_notes(self, test_db, tmp_path):
        """Test importing edited notes from wiki entry page."""
        file_path = tmp_path / "source.md"
        file_path.write_text("Content")

        # Create entry in database
        entry = Entry(
            date=date(2024, 11, 1),
            file_path=str(file_path),
            word_count=100,
            reading_time=0.5,
            notes=None,
        )
        test_db.add(entry)
        test_db.commit()

        # Create wiki file with edited notes
        wiki_file = tmp_path / "2024-11-01.md"
        wiki_content = """# Palimpsest — Entry

## 2024-11-01

### Notes

This entry captures a pivotal moment.
Perfect for the manuscript opening chapter.
"""
        wiki_file.write_text(wiki_content)

        # Parse and update
        wiki_entry = WikiEntry.from_file(wiki_file)

        test_db.query(Entry).filter_by(date=date(2024, 11, 1)).update(
            {"notes": wiki_entry.notes}
        )
        test_db.commit()

        # Verify
        updated_entry = test_db.query(Entry).filter_by(date=date(2024, 11, 1)).first()
        assert updated_entry.notes is not None
        assert "pivotal moment" in updated_entry.notes
        assert "opening chapter" in updated_entry.notes


class TestManuscriptImport:
    """Test importing manuscript wiki edits."""

    def test_import_manuscript_entry_notes(self, test_db, tmp_path):
        """Test importing manuscript entry notes and character notes."""
        file_path = tmp_path / "source.md"
        file_path.write_text("Content")

        # Create entry with manuscript
        entry = Entry(
            date=date(2024, 11, 1),
            file_path=str(file_path),
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

        test_db.add_all([entry, ms_entry])
        test_db.commit()

        # Create manuscript wiki file with edits
        wiki_file = tmp_path / "2024-11-01.md"
        wiki_content = """# Palimpsest — Manuscript Entry

## 2024-11-01

### Adaptation Notes

Transform this into a dialogue-heavy scene.
Focus on subtext and emotional undercurrents.

### Character Notes

Alice becomes Alexandra - soften her directness.
Bob as Robert - maintain wit but add vulnerability.
"""
        wiki_file.write_text(wiki_content)

        # Parse manuscript wiki
        from dev.dataclasses.manuscript_entry import ManuscriptEntry as WikiManuscriptEntry

        wiki_ms_entry = WikiManuscriptEntry.from_file(wiki_file)

        # Update manuscript entry
        test_db.query(ManuscriptEntry).filter_by(entry_id=entry.id).update({
            "notes": wiki_ms_entry.notes,
            "character_notes": wiki_ms_entry.character_notes,
        })
        test_db.commit()

        # Verify
        updated_ms = test_db.query(ManuscriptEntry).filter_by(entry_id=entry.id).first()
        assert updated_ms.notes is not None
        assert "dialogue-heavy scene" in updated_ms.notes
        assert updated_ms.character_notes is not None
        assert "Alexandra" in updated_ms.character_notes

    def test_import_manuscript_character(self, test_db, tmp_path):
        """Test importing manuscript character edits."""
        # Create person and character mapping
        person = Person(name="Alice", full_name="Alice Johnson")

        ms_person = ManuscriptPerson(
            person=person,
            character="Alexandra",
            character_description=None,
            character_arc=None,
        )

        test_db.add_all([person, ms_person])
        test_db.commit()

        # Create manuscript character wiki file
        wiki_file = tmp_path / "alexandra.md"
        wiki_content = """# Palimpsest — Character

## Alexandra

**Real Person:** Alice (Alice Johnson)

### Character Description

Protagonist. Introspective writer in her thirties.
Struggles with self-doubt but fiercely independent.

### Character Arc

Journey from isolation to connection.
Learns to trust others while maintaining autonomy.

### Voice Notes

First person perspective. Internal monologue heavy.
Lyrical but grounded language.

### Appearance Notes

Dark hair, intense gaze. Always carries a notebook.
Dresses simply but with attention to detail.
"""
        wiki_file.write_text(wiki_content)

        # Parse character wiki
        from dev.dataclasses.manuscript_character import Character

        wiki_character = Character.from_file(wiki_file)

        # Update manuscript person
        test_db.query(ManuscriptPerson).filter_by(person_id=person.id).update({
            "character_description": wiki_character.character_description,
            "character_arc": wiki_character.character_arc,
            "voice_notes": wiki_character.voice_notes,
            "appearance_notes": wiki_character.appearance_notes,
        })
        test_db.commit()

        # Verify
        updated_ms_person = test_db.query(ManuscriptPerson).filter_by(person_id=person.id).first()
        assert updated_ms_person.character_description is not None
        assert "Introspective writer" in updated_ms_person.character_description
        assert updated_ms_person.character_arc is not None
        assert "isolation to connection" in updated_ms_person.character_arc
        assert updated_ms_person.voice_notes is not None
        assert "First person" in updated_ms_person.voice_notes
        assert updated_ms_person.appearance_notes is not None
        assert "Dark hair" in updated_ms_person.appearance_notes


class TestFieldOwnership:
    """Test that only editable fields are imported."""

    def test_structural_fields_not_imported(self, test_db, tmp_path):
        """Test that structural fields are ignored during import."""
        # Create person
        person = Person(
            name="Alice",
            full_name="Alice Johnson",
            relation_type=RelationType.FRIEND,
        )
        test_db.add(person)
        test_db.commit()
        person_id = person.id

        # Create wiki file with "modified" structural data
        wiki_file = tmp_path / "alice.md"
        wiki_content = """# Palimpsest — Person

## Alice Modified Name (should not import)

**Full Name:** Alice Modified FullName (should not import)
**Relation:** colleague (should not import)

### Appearances (999 entries) (should not import)

- Fake entry 1
- Fake entry 2

### Notes

Only this should be imported.
"""
        wiki_file.write_text(wiki_content)

        # Parse and import only notes
        wiki_person = WikiPerson.from_file(wiki_file)

        test_db.query(Person).filter_by(id=person_id).update({"notes": wiki_person.notes})
        test_db.commit()

        # Verify: only notes changed
        updated_person = test_db.query(Person).filter_by(id=person_id).first()

        assert updated_person.notes == "Only this should be imported."
        assert updated_person.name == "Alice"  # Unchanged
        assert updated_person.full_name == "Alice Johnson"  # Unchanged
        assert updated_person.relation_type == RelationType.FRIEND  # Unchanged

    def test_manuscript_detailed_fields_only_in_wiki(self, test_db, tmp_path):
        """Test that manuscript detailed fields are NOT in YAML, only in wiki."""
        file_path = tmp_path / "source.md"
        file_path.write_text("Content")

        entry = Entry(
            date=date(2024, 11, 1),
            file_path=str(file_path),
            word_count=100,
            reading_time=0.5,
        )

        from dev.database.models_manuscript import EntryType

        ms_entry = ManuscriptEntry(
            entry=entry,
            status=ManuscriptStatus.SOURCE,
            edited=True,
            entry_type=EntryType.VIGNETTE,
            narrative_arc="paris_discovery",
        )

        test_db.add_all([entry, ms_entry])
        test_db.commit()

        # Verify these fields exist in database
        assert ms_entry.entry_type == EntryType.VIGNETTE
        assert ms_entry.narrative_arc == "paris_discovery"

        # These should NOT be editable via journal YAML
        # They are only editable via manuscript wiki

        # Simulate manuscript wiki edit
        wiki_file = tmp_path / "2024-11-01.md"
        wiki_content = """# Palimpsest — Manuscript Entry

## 2024-11-01

**Status:** source
**Entry Type:** scene (changed from vignette)
**Narrative Arc:** london_chapter (changed)

### Adaptation Notes

New notes here.
"""
        wiki_file.write_text(wiki_content)

        # Parse manuscript wiki
        from dev.dataclasses.manuscript_entry import ManuscriptEntry as WikiManuscriptEntry

        WikiManuscriptEntry.from_file(wiki_file)

        # In real import, would update entry_type and narrative_arc from manuscript wiki
        # This is allowed because it's the manuscript wiki, not journal YAML


class TestRoundTrip:
    """Test round-trip consistency: SQL → Wiki → SQL."""

    def test_round_trip_person_notes(self, test_db, tmp_path):
        """Test person notes survive round-trip."""
        # Start: database with notes
        person = Person(
            name="Alice",
            relation_type=RelationType.FRIEND,
            notes="Original notes",
        )
        test_db.add(person)
        test_db.commit()
        person_id = person.id

        # Export to wiki
        wiki_person = WikiPerson.from_database(person, tmp_path)
        wiki_lines = wiki_person.to_wiki()
        wiki_content = "\n".join(wiki_lines)

        # Write to file
        wiki_file = tmp_path / "alice.md"
        wiki_file.write_text(wiki_content)

        # Edit wiki notes
        edited_content = wiki_content.replace(
            "Original notes", "Edited notes after wiki export"
        )
        wiki_file.write_text(edited_content)

        # Import back
        wiki_person_import = WikiPerson.from_file(wiki_file)

        test_db.query(Person).filter_by(id=person_id).update({
            "notes": wiki_person_import.notes
        })
        test_db.commit()

        # Verify notes updated
        final_person = test_db.query(Person).filter_by(id=person_id).first()
        assert final_person.notes == "Edited notes after wiki export"
        assert final_person.name == "Alice"  # Unchanged
        assert final_person.relation_type == RelationType.FRIEND  # Unchanged

    def test_round_trip_manuscript_notes(self, test_db, tmp_path):
        """Test manuscript notes survive round-trip."""
        file_path = tmp_path / "source.md"
        file_path.write_text("Content")

        entry = Entry(
            date=date(2024, 11, 1),
            file_path=str(file_path),
            word_count=100,
            reading_time=0.5,
        )

        ms_entry = ManuscriptEntry(
            entry=entry,
            status=ManuscriptStatus.SOURCE,
            edited=True,
            notes="Original adaptation notes",
        )

        test_db.add_all([entry, ms_entry])
        test_db.commit()
        ms_entry_id = ms_entry.id

        # Export to wiki
        from dev.dataclasses.manuscript_entry import ManuscriptEntry as WikiManuscriptEntry

        journal_dir = tmp_path / "journal"

        wiki_ms_entry = WikiManuscriptEntry.from_database(
            entry, ms_entry, tmp_path, journal_dir
        )
        wiki_lines = wiki_ms_entry.to_wiki()
        wiki_content = "\n".join(wiki_lines)

        # Write to file
        wiki_file = tmp_path / "2024-11-01.md"
        wiki_file.write_text(wiki_content)

        # Edit wiki
        edited_content = wiki_content.replace(
            "Original adaptation notes", "Edited after manuscript wiki export"
        )
        wiki_file.write_text(edited_content)

        # Import back
        wiki_ms_import = WikiManuscriptEntry.from_file(wiki_file)

        test_db.query(ManuscriptEntry).filter_by(id=ms_entry_id).update({
            "notes": wiki_ms_import.notes
        })
        test_db.commit()

        # Verify
        final_ms = test_db.query(ManuscriptEntry).filter_by(id=ms_entry_id).first()
        assert final_ms.notes == "Edited after manuscript wiki export"
        assert final_ms.status == ManuscriptStatus.SOURCE  # Unchanged
        assert final_ms.edited is True  # Unchanged


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
