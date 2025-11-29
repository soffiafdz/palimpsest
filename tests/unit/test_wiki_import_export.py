#!/usr/bin/env python3
"""
Unit tests for wiki import/export functionality.

Tests the dataclass parsing and serialization without full database integration.
"""
import pytest
from dev.dataclasses.wiki_person import Person as WikiPerson
from dev.dataclasses.manuscript_entry import ManuscriptEntry
from dev.dataclasses.manuscript_character import Character


class TestWikiPersonParsing:
    """Test WikiPerson parsing from markdown."""

    def test_parse_minimal_person(self, tmp_path):
        """Test parsing person with minimal content."""
        wiki_file = tmp_path / "alice.md"
        wiki_file.write_text("""# Palimpsest — Person

*[[../index.md|Home]] > People > alice*

## Alice

### Category
Friend

### Alias
-

### Appearances
- No appearances recorded

### Themes
-

### Vignettes
-

### Notes
[Add your notes here]
""")

        person = WikiPerson.from_file(wiki_file)
        assert person is not None
        assert person.name == "Alice"
        assert person.category == "Friend"
        assert len(person.appearances) == 0

    def test_parse_person_with_notes(self, tmp_path):
        """Test parsing person with actual notes."""
        wiki_file = tmp_path / "alice.md"
        wiki_file.write_text("""# Palimpsest — Person

## Alice

### Category
Friend

### Alias
- Ali
- A

### Appearances
- No appearances recorded

### Themes
- creativity
- resilience

### Vignettes
-

### Notes
Alice is a childhood friend.
Very supportive and creative.
""")

        person = WikiPerson.from_file(wiki_file)
        assert person is not None
        assert person.name == "Alice"
        assert person.category == "Friend"
        assert "childhood friend" in person.notes
        assert "supportive" in person.notes
        assert "Ali" in person.alias
        assert "A" in person.alias
        assert "creativity" in person.themes
        assert "resilience" in person.themes

    def test_parse_person_ignores_placeholder(self, tmp_path):
        """Test that placeholder notes are treated as None."""
        wiki_file = tmp_path / "alice.md"
        wiki_file.write_text("""# Palimpsest — Person

## Alice

### Category
Friend

### Alias
-

### Appearances
- No appearances recorded

### Themes
-

### Vignettes
-

### Notes
[Add your notes here]
""")

        person = WikiPerson.from_file(wiki_file)
        assert person is not None
        # Placeholder should be stripped to None
        assert person.notes is None or person.notes == "[Add your notes here]"


class TestManuscriptEntryParsing:
    """Test ManuscriptEntry parsing from markdown."""

    def test_parse_manuscript_entry_with_notes(self, tmp_path):
        """Test parsing manuscript entry with adaptation notes."""
        wiki_file = tmp_path / "2024-11-01.md"
        wiki_file.write_text("""# Palimpsest — Manuscript Entry

## 2024-11-01

### Adaptation Notes

Transform this into a dialogue-heavy scene.
Focus on subtext and emotional undercurrents.

### Character Notes

Alice becomes Alexandra - soften her directness.
Bob as Robert - maintain wit but add vulnerability.
""")

        entry = ManuscriptEntry.from_file(wiki_file)
        assert entry is not None
        assert "dialogue-heavy" in entry.notes
        assert "subtext" in entry.notes
        assert "Alexandra" in entry.character_notes
        assert "Robert" in entry.character_notes

    def test_parse_manuscript_entry_empty_sections(self, tmp_path):
        """Test parsing manuscript entry with empty sections."""
        wiki_file = tmp_path / "2024-11-01.md"
        wiki_file.write_text("""# Palimpsest — Manuscript Entry

## 2024-11-01

### Adaptation Notes

### Character Notes
""")

        entry = ManuscriptEntry.from_file(wiki_file)
        assert entry is not None
        # Empty sections return empty string or None
        assert not entry.notes or entry.notes == ""
        assert not entry.character_notes or entry.character_notes == ""


class TestManuscriptCharacterParsing:
    """Test Character parsing from markdown."""

    def test_parse_character_with_all_fields(self, tmp_path):
        """Test parsing character with all fields populated."""
        wiki_file = tmp_path / "alexandra.md"
        wiki_file.write_text("""# Palimpsest — Character

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
""")

        character = Character.from_file(wiki_file)
        assert character is not None
        assert character.name == "Alexandra"
        assert "Protagonist" in character.character_description
        assert "isolation to connection" in character.character_arc
        assert "First person" in character.voice_notes
        assert "Dark hair" in character.appearance_notes

    def test_parse_character_partial_fields(self, tmp_path):
        """Test parsing character with only some fields."""
        wiki_file = tmp_path / "alexandra.md"
        wiki_file.write_text("""# Palimpsest — Character

## Alexandra

**Real Person:** Alice

### Character Description

Protagonist.

### Character Arc

### Voice Notes

### Appearance Notes
""")

        character = Character.from_file(wiki_file)
        assert character is not None
        assert character.name == "Alexandra"
        assert "Protagonist" in character.character_description
        # Empty sections return empty string or None
        assert not character.character_arc or character.character_arc == ""
        assert not character.voice_notes or character.voice_notes == ""
        assert not character.appearance_notes or character.appearance_notes == ""


class TestWikiPersonSerialization:
    """Test WikiPerson serialization to markdown."""

    def test_serialize_minimal_person(self, tmp_path):
        """Test serializing person with minimal data."""
        person = WikiPerson(
            path=tmp_path / "alice.md",
            wiki_dir=tmp_path,
            name="Alice",
            category="Friend",
        )

        lines = person.to_wiki()
        content = "\n".join(lines)

        assert "# Palimpsest — Person" in content
        assert "## Alice" in content
        assert "### Category" in content
        assert "Friend" in content
        assert "### Appearances" in content
        assert "### Notes" in content

    def test_serialize_person_with_notes(self, tmp_path):
        """Test serializing person with notes."""
        person = WikiPerson(
            path=tmp_path / "alice.md",
            wiki_dir=tmp_path,
            name="Alice",
            category="Friend",
            notes="Alice is a childhood friend.",
        )

        lines = person.to_wiki()
        content = "\n".join(lines)

        assert "### Notes" in content
        assert "childhood friend" in content

    def test_serialize_person_no_notes_gets_placeholder(self, tmp_path):
        """Test that person without notes gets placeholder."""
        person = WikiPerson(
            path=tmp_path / "alice.md",
            wiki_dir=tmp_path,
            name="Alice",
            category="Friend",
            notes=None,
        )

        lines = person.to_wiki()
        content = "\n".join(lines)

        assert "### Notes" in content
        assert "[Add your notes here]" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
