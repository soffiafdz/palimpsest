#!/usr/bin/env python3
"""
Integration tests for SQL → Wiki pipeline.

Tests the sql2wiki export functionality including:
- Entity export (people, entries, events, etc.)
- Wiki page generation
- Relationship rendering
- Navigation links
- Manuscript subwiki export
- Index and special pages
"""
import pytest
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dev.database.models import Base, Entry, Person, Event, City, Location, Tag, RelationType
from dev.database.models_manuscript import (
    ManuscriptEntry,
    ManuscriptPerson,
    ManuscriptStatus,
    EntryType,
)
from dev.dataclasses.wiki_person import Person as WikiPerson
from dev.dataclasses.wiki_entry import Entry as WikiEntry
from dev.dataclasses.manuscript_entry import ManuscriptEntry as WikiManuscriptEntry


@pytest.fixture
def test_db():
    """Create in-memory database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestPersonExport:
    """Test exporting people from database to wiki."""

    def test_export_minimal_person(self, test_db, tmp_path):
        """Test exporting person with minimal data."""
        person = Person(name="Alice", relation_type=RelationType.FRIEND)
        test_db.add(person)
        test_db.commit()

        # Export to wiki
        wiki_person = WikiPerson.from_database(person, tmp_path)
        wiki_lines = wiki_person.to_wiki()
        wiki_content = "\n".join(wiki_lines)

        # Verify content
        assert "# Palimpsest — Person" in wiki_content
        assert "Alice" in wiki_content
        assert "friend" in wiki_content.lower()

    def test_export_person_with_full_name(self, test_db, tmp_path):
        """Test exporting person with full name."""
        person = Person(
            name="Alice",
            full_name="Alice Johnson",
            relation_type=RelationType.FRIEND,
        )
        test_db.add(person)
        test_db.commit()

        wiki_person = WikiPerson.from_database(person, tmp_path)
        wiki_lines = wiki_person.to_wiki()
        wiki_content = "\n".join(wiki_lines)

        assert "Alice Johnson" in wiki_content

    def test_export_person_with_entries(self, test_db, tmp_path):
        """Test exporting person with entry appearances."""
        file_path1 = tmp_path / "source1.md"
        file_path1.write_text("Content")

        file_path2 = tmp_path / "source2.md"
        file_path2.write_text("Content")

        person = Person(name="Alice", relation_type=RelationType.FRIEND)
        entry1 = Entry(
            date=date(2024, 11, 1),
            file_path=str(file_path1),
            word_count=100,
            reading_time=0.5,
        )
        entry2 = Entry(
            date=date(2024, 11, 5),
            file_path=str(file_path2),
            word_count=200,
            reading_time=1.0,
        )

        person.entries.extend([entry1, entry2])

        test_db.add_all([person, entry1, entry2])
        test_db.commit()

        wiki_person = WikiPerson.from_database(person, tmp_path)
        wiki_lines = wiki_person.to_wiki()
        wiki_content = "\n".join(wiki_lines)

        # Verify appearances section
        assert "Appearances" in wiki_content
        assert "2024-11-01" in wiki_content
        assert "2024-11-05" in wiki_content


class TestEntryExport:
    """Test exporting entries from database to wiki."""

    def test_export_minimal_entry(self, test_db, tmp_path):
        """Test exporting entry with minimal data."""
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

        journal_dir = tmp_path / "journal"

        wiki_entry = WikiEntry.from_database(entry, tmp_path, journal_dir)
        wiki_lines = wiki_entry.to_wiki()
        wiki_content = "\n".join(wiki_lines)

        assert "# Palimpsest — Entry" in wiki_content
        assert "2024-11-01" in wiki_content
        assert "100 words" in wiki_content

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

        alice = Person(name="Alice", relation_type=RelationType.FRIEND)
        bob = Person(name="Bob", relation_type=RelationType.COLLEAGUE)

        entry.people.extend([alice, bob])

        test_db.add_all([entry, alice, bob])
        test_db.commit()

        journal_dir = tmp_path / "journal"

        wiki_entry = WikiEntry.from_database(entry, tmp_path, journal_dir)
        wiki_lines = wiki_entry.to_wiki()
        wiki_content = "\n".join(wiki_lines)

        # Verify people section with counts
        assert "**People (2)**" in wiki_content
        assert "Alice" in wiki_content
        assert "Bob" in wiki_content
        assert "friend" in wiki_content.lower()
        assert "colleague" in wiki_content.lower()

    def test_export_entry_with_navigation(self, test_db, tmp_path):
        """Test exporting entry with prev/next navigation."""
        file_path1 = tmp_path / "source1.md"
        file_path1.write_text("Content")

        file_path2 = tmp_path / "source2.md"
        file_path2.write_text("Content")

        file_path3 = tmp_path / "source3.md"
        file_path3.write_text("Content")

        entry1 = Entry(
            date=date(2024, 11, 1),
            file_path=str(file_path1),
            word_count=100,
            reading_time=0.5,
        )
        entry2 = Entry(
            date=date(2024, 11, 5),
            file_path=str(file_path2),
            word_count=100,
            reading_time=0.5,
        )
        entry3 = Entry(
            date=date(2024, 11, 10),
            file_path=str(file_path3),
            word_count=100,
            reading_time=0.5,
        )

        test_db.add_all([entry1, entry2, entry3])
        test_db.commit()

        journal_dir = tmp_path / "journal"

        # Export middle entry with navigation
        wiki_entry = WikiEntry.from_database(
            entry2, tmp_path, journal_dir, prev_entry=entry1, next_entry=entry3
        )
        wiki_lines = wiki_entry.to_wiki()
        wiki_content = "\n".join(wiki_lines)

        assert "**Navigation**" in wiki_content
        assert "Previous" in wiki_content
        assert "Next" in wiki_content
        assert "2024-11-01" in wiki_content
        assert "2024-11-10" in wiki_content


class TestManuscriptExport:
    """Test exporting manuscript subwiki."""

    def test_export_manuscript_entry(self, test_db, tmp_path):
        """Test exporting manuscript entry."""
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
            entry_type=EntryType.VIGNETTE,
            character_notes="Alice becomes Alexandra",
            narrative_arc="paris_discovery",
            notes="Key transformative scene",
        )

        test_db.add_all([entry, ms_entry])
        test_db.commit()

        journal_dir = tmp_path / "journal"

        # Export manuscript entry
        wiki_ms_entry = WikiManuscriptEntry.from_database(
            entry, ms_entry, tmp_path, journal_dir
        )
        wiki_lines = wiki_ms_entry.to_wiki()
        wiki_content = "\n".join(wiki_lines)

        assert "# Palimpsest — Manuscript Entry" in wiki_content
        assert "2024-11-01" in wiki_content
        assert "source" in wiki_content.lower()
        assert "vignette" in wiki_content.lower()
        assert "paris_discovery" in wiki_content
        assert "Alice becomes Alexandra" in wiki_content

    def test_manuscript_entry_with_characters(self, test_db, tmp_path):
        """Test manuscript entry with character mappings."""
        file_path = tmp_path / "source.md"
        file_path.write_text("Content")

        entry = Entry(
            date=date(2024, 11, 1),
            file_path=str(file_path),
            word_count=100,
            reading_time=0.5,
        )

        # Add real person
        alice = Person(name="Alice", full_name="Alice Johnson")
        entry.people.append(alice)

        # Add manuscript entry
        ms_entry = ManuscriptEntry(
            entry=entry,
            status=ManuscriptStatus.SOURCE,
            edited=True,
        )

        # Add character mapping
        ms_person = ManuscriptPerson(
            person=alice,
            character="Alexandra",
            character_description="Protagonist, introspective writer",
        )

        test_db.add_all([entry, alice, ms_entry, ms_person])
        test_db.commit()

        journal_dir = tmp_path / "journal"

        # Export manuscript entry
        wiki_ms_entry = WikiManuscriptEntry.from_database(
            entry, ms_entry, tmp_path, journal_dir
        )
        wiki_lines = wiki_ms_entry.to_wiki()
        wiki_content = "\n".join(wiki_lines)

        # Verify character mapping appears
        assert "Alexandra" in wiki_content
        assert "Alice" in wiki_content


class TestWikiFormatting:
    """Test wiki formatting and structure."""

    def test_breadcrumbs(self, test_db, tmp_path):
        """Test breadcrumb generation."""
        person = Person(name="Alice", relation_type=RelationType.FRIEND)
        test_db.add(person)
        test_db.commit()

        wiki_person = WikiPerson.from_database(person, tmp_path)
        wiki_lines = wiki_person.to_wiki()
        wiki_content = "\n".join(wiki_lines)

        # Verify breadcrumbs present
        assert "Home" in wiki_content
        assert "People" in wiki_content

    def test_entity_counts_in_headers(self, test_db, tmp_path):
        """Test that section headers include entity counts."""
        file_path = tmp_path / "source.md"
        file_path.write_text("Content")

        entry = Entry(
            date=date(2024, 11, 1),
            file_path=str(file_path),
            word_count=100,
            reading_time=0.5,
        )

        # Add 3 people
        alice = Person(name="Alice")
        bob = Person(name="Bob")
        charlie = Person(name="Charlie")
        entry.people.extend([alice, bob, charlie])

        # Add 2 tags
        tag1 = Tag(tag="reflection")
        tag2 = Tag(tag="milestone")
        entry.tags.extend([tag1, tag2])

        test_db.add_all([entry, alice, bob, charlie, tag1, tag2])
        test_db.commit()

        journal_dir = tmp_path / "journal"

        wiki_entry = WikiEntry.from_database(entry, tmp_path, journal_dir)
        wiki_lines = wiki_entry.to_wiki()
        wiki_content = "\n".join(wiki_lines)

        # Verify counts in headers
        assert "**People (3)**" in wiki_content
        assert "**Tags (2)**" in wiki_content

    def test_table_formatted_metadata(self, test_db, tmp_path):
        """Test that metadata is formatted as table."""
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

        journal_dir = tmp_path / "journal"

        wiki_entry = WikiEntry.from_database(entry, tmp_path, journal_dir)
        wiki_lines = wiki_entry.to_wiki()
        wiki_content = "\n".join(wiki_lines)

        # Verify table format
        assert "| Property | Value |" in wiki_content
        assert "| --- | --- |" in wiki_content
        assert "| **Date** |" in wiki_content
        assert "| **Word Count** |" in wiki_content

    def test_horizontal_rule_separator(self, test_db, tmp_path):
        """Test horizontal rule after title."""
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

        journal_dir = tmp_path / "journal"

        wiki_entry = WikiEntry.from_database(entry, tmp_path, journal_dir)
        wiki_lines = wiki_entry.to_wiki()

        # Find the title line and check next non-empty line
        for i, line in enumerate(wiki_lines):
            if line.startswith("## 2024-11-01"):
                # Next non-empty line should be ---
                for j in range(i + 1, len(wiki_lines)):
                    if wiki_lines[j].strip():
                        assert wiki_lines[j] == "---"
                        break
                break


class TestEditableFields:
    """Test that only editable fields are marked for wiki editing."""

    def test_notes_section_present(self, test_db, tmp_path):
        """Test that notes section is present in wiki export."""
        person = Person(name="Alice", relation_type=RelationType.FRIEND)
        test_db.add(person)
        test_db.commit()

        wiki_person = WikiPerson.from_database(person, tmp_path)
        wiki_lines = wiki_person.to_wiki()
        wiki_content = "\n".join(wiki_lines)

        assert "### Notes" in wiki_content

    def test_placeholder_for_empty_notes(self, test_db, tmp_path):
        """Test placeholder text for empty notes."""
        person = Person(name="Alice", relation_type=RelationType.FRIEND, notes=None)
        test_db.add(person)
        test_db.commit()

        wiki_person = WikiPerson.from_database(person, tmp_path)
        wiki_lines = wiki_person.to_wiki()
        wiki_content = "\n".join(wiki_lines)

        assert "[Add your notes" in wiki_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
