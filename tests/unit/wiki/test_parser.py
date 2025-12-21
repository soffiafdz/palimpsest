"""
test_parser.py
--------------
Unit tests for dev.wiki.parser module.

Tests wiki file parsing functions that extract editable fields (notes, vignettes)
from wiki markdown files for database import.

Target Coverage: 95%+
"""
import pytest
from datetime import date
from pathlib import Path
import tempfile

from dev.wiki.parser import (
    parse_wiki_notes,
    parse_person_file,
    parse_entry_file,
    parse_event_file,
    parse_tag_file,
    parse_theme_file,
    parse_manuscript_entry_file,
    parse_manuscript_character_file,
    parse_manuscript_event_file,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test wiki files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def create_wiki_file(path: Path, content: str) -> Path:
    """Helper to create a wiki file with given content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# =============================================================================
# Test parse_wiki_notes
# =============================================================================


class TestParseWikiNotes:
    """Test parse_wiki_notes function."""

    def test_extracts_notes_section(self, temp_dir):
        """Test extracting notes from wiki file."""
        wiki_file = create_wiki_file(
            temp_dir / "test.md",
            "# Title\n\n### Notes\nThis is the notes content.\n"
        )
        result = parse_wiki_notes(wiki_file)
        assert result == "This is the notes content."

    def test_returns_none_for_missing_file(self, temp_dir):
        """Test returns None for non-existent file."""
        result = parse_wiki_notes(temp_dir / "missing.md")
        assert result is None

    def test_returns_none_for_no_notes_section(self, temp_dir):
        """Test returns None when no Notes section exists."""
        wiki_file = create_wiki_file(
            temp_dir / "test.md",
            "# Title\n\n### Other Section\nContent here.\n"
        )
        result = parse_wiki_notes(wiki_file)
        assert result is None

    def test_returns_none_for_placeholder_notes(self, temp_dir):
        """Test returns None for placeholder text in notes."""
        wiki_file = create_wiki_file(
            temp_dir / "test.md",
            "# Title\n\n### Notes\n[Add notes...]\n"
        )
        result = parse_wiki_notes(wiki_file)
        assert result is None

    def test_multiline_notes(self, temp_dir):
        """Test extracting multiline notes content."""
        wiki_file = create_wiki_file(
            temp_dir / "test.md",
            "# Title\n\n### Notes\nLine 1\nLine 2\nLine 3\n"
        )
        result = parse_wiki_notes(wiki_file)
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result


# =============================================================================
# Test parse_person_file
# =============================================================================


class TestParsePersonFile:
    """Test parse_person_file function."""

    def test_parses_person_with_notes(self, temp_dir):
        """Test parsing person file with notes."""
        wiki_file = create_wiki_file(
            temp_dir / "john_doe.md",
            "# John Doe\n\n### Notes\nPerson notes here.\n"
        )
        result = parse_person_file(wiki_file)
        assert result["name"] == "john doe"
        assert result["notes"] == "Person notes here."
        assert result["vignettes"] is None

    def test_parses_person_with_vignettes(self, temp_dir):
        """Test parsing person file with vignettes."""
        wiki_file = create_wiki_file(
            temp_dir / "jane_smith.md",
            "# Jane Smith\n\n### Vignettes\nA story about Jane.\n"
        )
        result = parse_person_file(wiki_file)
        assert result["name"] == "jane smith"
        assert result["vignettes"] == "A story about Jane."

    def test_parses_person_with_both(self, temp_dir):
        """Test parsing person file with notes and vignettes."""
        wiki_file = create_wiki_file(
            temp_dir / "bob_wilson.md",
            "# Bob Wilson\n\n### Notes\nBob's notes.\n\n### Vignettes\nBob's story.\n"
        )
        result = parse_person_file(wiki_file)
        assert result["notes"] == "Bob's notes."
        assert result["vignettes"] == "Bob's story."

    def test_returns_none_for_missing_file(self, temp_dir):
        """Test returns None for non-existent file."""
        result = parse_person_file(temp_dir / "missing.md")
        assert result is None

    def test_name_from_filename_underscores(self, temp_dir):
        """Test name extraction with underscores converted to spaces."""
        wiki_file = create_wiki_file(
            temp_dir / "mary_jane_watson.md",
            "# Mary Jane Watson\n\n### Notes\nNotes.\n"
        )
        result = parse_person_file(wiki_file)
        assert result["name"] == "mary jane watson"

    def test_empty_vignettes_becomes_none(self, temp_dir):
        """Test empty vignettes section becomes None."""
        wiki_file = create_wiki_file(
            temp_dir / "test.md",
            "# Test\n\n### Vignettes\n   \n"
        )
        result = parse_person_file(wiki_file)
        assert result["vignettes"] is None


# =============================================================================
# Test parse_entry_file
# =============================================================================


class TestParseEntryFile:
    """Test parse_entry_file function."""

    def test_parses_entry_with_notes(self, temp_dir):
        """Test parsing entry file with notes."""
        wiki_file = create_wiki_file(
            temp_dir / "2024-01-15.md",
            "# January 15, 2024\n\n### Notes\nEntry notes here.\n"
        )
        result = parse_entry_file(wiki_file)
        assert result["date"] == date(2024, 1, 15)
        assert result["notes"] == "Entry notes here."

    def test_returns_none_for_missing_file(self, temp_dir):
        """Test returns None for non-existent file."""
        result = parse_entry_file(temp_dir / "2024-01-15.md")
        assert result is None

    def test_returns_none_for_invalid_date_filename(self, temp_dir):
        """Test returns None for invalid date in filename."""
        wiki_file = create_wiki_file(
            temp_dir / "not-a-date.md",
            "# Entry\n\n### Notes\nNotes.\n"
        )
        result = parse_entry_file(wiki_file)
        assert result is None

    def test_returns_none_for_invalid_date_format(self, temp_dir):
        """Test returns None for invalid date format."""
        wiki_file = create_wiki_file(
            temp_dir / "01-15-2024.md",  # Wrong format
            "# Entry\n"
        )
        result = parse_entry_file(wiki_file)
        assert result is None

    def test_empty_notes(self, temp_dir):
        """Test entry with no notes section."""
        wiki_file = create_wiki_file(
            temp_dir / "2024-06-01.md",
            "# June 1, 2024\n\n### Other\nContent.\n"
        )
        result = parse_entry_file(wiki_file)
        assert result["date"] == date(2024, 6, 1)
        assert result["notes"] is None


# =============================================================================
# Test parse_event_file
# =============================================================================


class TestParseEventFile:
    """Test parse_event_file function."""

    def test_parses_event_with_notes(self, temp_dir):
        """Test parsing event file with notes."""
        wiki_file = create_wiki_file(
            temp_dir / "birthday_party.md",
            "# Birthday Party\n\n### Notes\nEvent notes here.\n"
        )
        result = parse_event_file(wiki_file)
        assert result["event"] == "birthday party"
        assert result["notes"] == "Event notes here."

    def test_returns_none_for_missing_file(self, temp_dir):
        """Test returns None for non-existent file."""
        result = parse_event_file(temp_dir / "missing.md")
        assert result is None

    def test_event_name_from_filename(self, temp_dir):
        """Test event name extraction from filename."""
        wiki_file = create_wiki_file(
            temp_dir / "christmas_dinner_2024.md",
            "# Event\n"
        )
        result = parse_event_file(wiki_file)
        assert result["event"] == "christmas dinner 2024"

    def test_empty_notes(self, temp_dir):
        """Test event with no notes."""
        wiki_file = create_wiki_file(
            temp_dir / "event.md",
            "# Event\n"
        )
        result = parse_event_file(wiki_file)
        assert result["notes"] is None


# =============================================================================
# Test parse_tag_file
# =============================================================================


class TestParseTagFile:
    """Test parse_tag_file function."""

    def test_parses_tag_with_notes(self, temp_dir):
        """Test parsing tag file with notes."""
        wiki_file = create_wiki_file(
            temp_dir / "work_life.md",
            "# Work Life\n\n### Notes\nTag description here.\n"
        )
        result = parse_tag_file(wiki_file)
        assert result["tag"] == "work life"
        assert result["notes"] == "Tag description here."

    def test_returns_none_for_missing_file(self, temp_dir):
        """Test returns None for non-existent file."""
        result = parse_tag_file(temp_dir / "missing.md")
        assert result is None

    def test_tag_name_from_filename(self, temp_dir):
        """Test tag name extraction from filename."""
        wiki_file = create_wiki_file(
            temp_dir / "creative_writing.md",
            "# Tag\n"
        )
        result = parse_tag_file(wiki_file)
        assert result["tag"] == "creative writing"


# =============================================================================
# Test parse_theme_file
# =============================================================================


class TestParseThemeFile:
    """Test parse_theme_file function."""

    def test_parses_theme_with_notes(self, temp_dir):
        """Test parsing theme file with notes."""
        wiki_file = create_wiki_file(
            temp_dir / "self_discovery.md",
            "# Self Discovery\n\n### Notes\nTheme notes.\n"
        )
        result = parse_theme_file(wiki_file)
        assert result["theme"] == "Self Discovery"
        assert result["notes"] == "Theme notes."

    def test_parses_theme_with_description(self, temp_dir):
        """Test parsing theme file with description."""
        wiki_file = create_wiki_file(
            temp_dir / "healing.md",
            "# Healing\n\n### Description\nA theme about healing.\n"
        )
        result = parse_theme_file(wiki_file)
        assert result["description"] == "A theme about healing."

    def test_returns_none_for_missing_file(self, temp_dir):
        """Test returns None for non-existent file."""
        result = parse_theme_file(temp_dir / "missing.md")
        assert result is None

    def test_theme_name_hyphen_to_slash(self, temp_dir):
        """Test theme name with hyphen converted to slash and title case."""
        wiki_file = create_wiki_file(
            temp_dir / "life-death.md",
            "# Life/Death\n"
        )
        result = parse_theme_file(wiki_file)
        assert result["theme"] == "Life/Death"

    def test_empty_description_becomes_none(self, temp_dir):
        """Test empty description becomes None."""
        wiki_file = create_wiki_file(
            temp_dir / "test.md",
            "# Test\n\n### Description\n   \n"
        )
        result = parse_theme_file(wiki_file)
        assert result["description"] is None


# =============================================================================
# Test parse_manuscript_entry_file
# =============================================================================


class TestParseManuscriptEntryFile:
    """Test parse_manuscript_entry_file function."""

    def test_parses_manuscript_entry(self, temp_dir):
        """Test parsing manuscript entry file."""
        wiki_file = create_wiki_file(
            temp_dir / "2024-01-15.md",
            "# January 15, 2024\n\n"
            "### Adaptation Notes\nHow to adapt this entry.\n\n"
            "### Character Notes\nCharacter insights here.\n"
        )
        result = parse_manuscript_entry_file(wiki_file)
        assert result["date"] == date(2024, 1, 15)
        assert result["notes"] == "How to adapt this entry."
        assert result["character_notes"] == "Character insights here."

    def test_returns_none_for_missing_file(self, temp_dir):
        """Test returns None for non-existent file."""
        result = parse_manuscript_entry_file(temp_dir / "2024-01-15.md")
        assert result is None

    def test_returns_none_for_invalid_date(self, temp_dir):
        """Test returns None for invalid date in filename."""
        wiki_file = create_wiki_file(
            temp_dir / "not-a-date.md",
            "# Entry\n"
        )
        result = parse_manuscript_entry_file(wiki_file)
        assert result is None

    def test_empty_sections_become_none(self, temp_dir):
        """Test empty sections become None."""
        wiki_file = create_wiki_file(
            temp_dir / "2024-06-01.md",
            "# Entry\n\n### Adaptation Notes\n   \n"
        )
        result = parse_manuscript_entry_file(wiki_file)
        assert result["notes"] is None
        assert result["character_notes"] is None


# =============================================================================
# Test parse_manuscript_character_file
# =============================================================================


class TestParseManuscriptCharacterFile:
    """Test parse_manuscript_character_file function."""

    def test_parses_character_file(self, temp_dir):
        """Test parsing manuscript character file."""
        wiki_file = create_wiki_file(
            temp_dir / "john_doe.md",
            "# John Doe\n\n"
            "### Character Description\nA protagonist.\n\n"
            "### Character Arc\nFrom doubt to confidence.\n\n"
            "### Voice Notes\nSpoken with hesitation.\n\n"
            "### Appearance Notes\nTall with dark hair.\n"
        )
        result = parse_manuscript_character_file(wiki_file)
        assert result["name"] == "John Doe"
        assert result["character_description"] == "A protagonist."
        assert result["character_arc"] == "From doubt to confidence."
        assert result["voice_notes"] == "Spoken with hesitation."
        assert result["appearance_notes"] == "Tall with dark hair."

    def test_returns_none_for_missing_file(self, temp_dir):
        """Test returns None for non-existent file."""
        result = parse_manuscript_character_file(temp_dir / "missing.md")
        assert result is None

    def test_name_from_filename_title_case(self, temp_dir):
        """Test character name in title case from filename."""
        wiki_file = create_wiki_file(
            temp_dir / "jane_smith.md",
            "# Jane\n"
        )
        result = parse_manuscript_character_file(wiki_file)
        assert result["name"] == "Jane Smith"

    def test_empty_sections_become_none(self, temp_dir):
        """Test empty sections become None."""
        wiki_file = create_wiki_file(
            temp_dir / "test.md",
            "# Test\n\n### Character Description\n  \n"
        )
        result = parse_manuscript_character_file(wiki_file)
        assert result["character_description"] is None
        assert result["character_arc"] is None
        assert result["voice_notes"] is None
        assert result["appearance_notes"] is None


# =============================================================================
# Test parse_manuscript_event_file
# =============================================================================


class TestParseManuscriptEventFile:
    """Test parse_manuscript_event_file function."""

    def test_parses_event_with_adaptation_notes(self, temp_dir):
        """Test parsing event file with Adaptation Notes section."""
        wiki_file = create_wiki_file(
            temp_dir / "wedding_day.md",
            "# Wedding Day\n\n### Adaptation Notes\nHow to adapt this event.\n"
        )
        result = parse_manuscript_event_file(wiki_file)
        assert result["name"] == "Wedding Day"
        assert result["notes"] == "How to adapt this event."

    def test_parses_event_with_manuscript_notes(self, temp_dir):
        """Test parsing event file with Manuscript Notes section (fallback)."""
        wiki_file = create_wiki_file(
            temp_dir / "graduation.md",
            "# Graduation\n\n### Manuscript Notes\nFallback notes section.\n"
        )
        result = parse_manuscript_event_file(wiki_file)
        assert result["notes"] == "Fallback notes section."

    def test_returns_none_for_missing_file(self, temp_dir):
        """Test returns None for non-existent file."""
        result = parse_manuscript_event_file(temp_dir / "missing.md")
        assert result is None

    def test_name_from_filename_title_case(self, temp_dir):
        """Test event name in title case from filename."""
        wiki_file = create_wiki_file(
            temp_dir / "birthday_celebration.md",
            "# Event\n"
        )
        result = parse_manuscript_event_file(wiki_file)
        assert result["name"] == "Birthday Celebration"

    def test_empty_notes_becomes_none(self, temp_dir):
        """Test empty notes becomes None."""
        wiki_file = create_wiki_file(
            temp_dir / "test.md",
            "# Test\n\n### Adaptation Notes\n  \n"
        )
        result = parse_manuscript_event_file(wiki_file)
        assert result["notes"] is None

    def test_adaptation_notes_takes_priority(self, temp_dir):
        """Test Adaptation Notes takes priority over Manuscript Notes."""
        wiki_file = create_wiki_file(
            temp_dir / "test.md",
            "# Test\n\n"
            "### Adaptation Notes\nPrimary notes.\n\n"
            "### Manuscript Notes\nSecondary notes.\n"
        )
        result = parse_manuscript_event_file(wiki_file)
        assert result["notes"] == "Primary notes."
