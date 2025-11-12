"""
test_md_entry.py
----------------
Unit tests for dev.dataclasses.md_entry module.

Tests the MdEntry dataclass which serves as the bridge between
Markdown files and database models.

Target Coverage: 90%+
"""
import pytest
from datetime import date
from pathlib import Path
from dev.dataclasses.md_entry import MdEntry
from dev.core.exceptions import EntryParseError, EntryValidationError


class TestMdEntryFromFile:
    """Test MdEntry.from_file() method."""

    def test_from_minimal_file(self, minimal_entry_file):
        """Test parsing minimal entry file."""
        entry = MdEntry.from_file(minimal_entry_file)

        assert entry.date == date(2024, 1, 15)
        assert entry.file_path == minimal_entry_file
        assert entry.word_count > 0
        assert len(entry.body_lines) > 0

    def test_from_complex_file(self, complex_entry_file):
        """Test parsing complex entry with all metadata."""
        entry = MdEntry.from_file(complex_entry_file)

        assert entry.date == date(2024, 1, 15)
        assert entry.word_count == 850
        assert entry.reading_time == 4.2
        assert entry.city is not None
        assert entry.locations is not None
        assert entry.people is not None
        assert entry.tags is not None

    def test_nonexistent_file_raises_error(self, tmp_dir):
        """Test reading nonexistent file raises error."""
        nonexistent = tmp_dir / "nonexistent.md"
        with pytest.raises((FileNotFoundError, EntryParseError)):
            MdEntry.from_file(nonexistent)

    def test_file_without_frontmatter(self, tmp_dir):
        """Test file without frontmatter raises error."""
        file_path = tmp_dir / "no-frontmatter.md"
        file_path.write_text("# Title\n\nJust body content, no YAML.")

        with pytest.raises(EntryParseError):
            MdEntry.from_file(file_path)

    def test_file_with_invalid_yaml(self, tmp_dir):
        """Test file with malformed YAML raises error."""
        file_path = tmp_dir / "bad-yaml.md"
        file_path.write_text("""---
date: 2024-01-15
people: [unclosed list
---

Body content""")

        with pytest.raises(EntryParseError):
            MdEntry.from_file(file_path)


class TestMdEntryFromMarkdownText:
    """Test MdEntry.from_markdown_text() method."""

    def test_from_minimal_text(self):
        """Test parsing minimal markdown text."""
        text = """---
date: 2024-01-15
---

# Entry Title

Body content here."""

        entry = MdEntry.from_markdown_text(text)
        assert entry.date == date(2024, 1, 15)
        assert len(entry.body_lines) > 0

    def test_from_text_with_people(self):
        """Test parsing entry with people metadata."""
        text = """---
date: 2024-01-15
people:
  - Alice
  - Bob (Robert Smith)
---

# Entry

Met with Alice and Bob."""

        entry = MdEntry.from_markdown_text(text)
        assert entry.people is not None
        assert len(entry.people) == 2

    def test_from_text_with_locations(self):
        """Test parsing entry with location metadata."""
        text = """---
date: 2024-01-15
city: Montreal
locations:
  - Cafe X
  - Library
---

# Entry

Visited locations."""

        entry = MdEntry.from_markdown_text(text)
        assert entry.city == "Montreal"
        assert entry.locations is not None
        assert len(entry.locations) >= 2


class TestMdEntryParsing:
    """Test MdEntry field parsing methods."""

    def test_parse_city_single_string(self):
        """Test parsing single city string."""
        text = """---
date: 2024-01-15
city: Montreal
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        assert entry.city == "Montreal"

    def test_parse_city_list(self):
        """Test parsing city as list."""
        text = """---
date: 2024-01-15
city:
  - Montreal
  - Toronto
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        assert entry.city is not None

    def test_parse_person_with_full_name(self):
        """Test parsing person with full name in parentheses."""
        text = """---
date: 2024-01-15
people:
  - Bob (Robert Smith)
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        assert entry.people is not None
        assert len(entry.people) == 1

    def test_parse_person_with_at_symbol(self):
        """Test parsing person with @ prefix."""
        text = """---
date: 2024-01-15
people:
  - "@Alice"
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        assert entry.people is not None
        # @ symbol should be stripped

    def test_parse_hyphenated_names(self):
        """Test parsing hyphenated names."""
        text = """---
date: 2024-01-15
people:
  - María-José
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        assert entry.people is not None

    def test_parse_date_with_context(self):
        """Test parsing mentioned date with context."""
        text = """---
date: 2024-01-15
dates:
  - 2024-06-01 (thesis exam)
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        assert entry.dates is not None
        assert len(entry.dates) >= 1

    def test_parse_poem_with_revision_date(self):
        """Test parsing poem with revision_date."""
        text = """---
date: 2024-01-15
poems:
  - title: Test Poem
    content: |
      Line 1
      Line 2
    revision_date: 2024-01-15
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        assert entry.poems is not None
        assert len(entry.poems) == 1

    def test_parse_poem_without_revision_date(self):
        """Test poem without revision_date defaults to entry date."""
        text = """---
date: 2024-01-15
poems:
  - title: Test Poem
    content: Test content
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        assert entry.poems is not None
        # Should not raise error

    def test_parse_reference_with_source(self):
        """Test parsing reference with source metadata."""
        text = """---
date: 2024-01-15
references:
  - content: "Quote text"
    speaker: Author
    source:
      title: Book Title
      type: book
      author: Author Name
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        assert entry.references is not None
        assert len(entry.references) == 1

    def test_parse_manuscript_metadata(self):
        """Test parsing manuscript metadata."""
        text = """---
date: 2024-01-15
manuscript:
  status: draft
  edited: false
  themes:
    - identity
    - memory
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        assert entry.manuscript is not None


class TestMdEntryToDatabaseMetadata:
    """Test MdEntry.to_database_metadata() method."""

    def test_minimal_entry_to_db_metadata(self):
        """Test converting minimal entry to database metadata."""
        text = """---
date: 2024-01-15
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        metadata = entry.to_database_metadata()

        assert metadata["date"] == date(2024, 1, 15)
        assert "word_count" in metadata
        assert "reading_time" in metadata

    def test_entry_with_people_to_db_metadata(self):
        """Test people field conversion to database format."""
        text = """---
date: 2024-01-15
people:
  - Alice
  - Bob (Robert Smith)
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        metadata = entry.to_database_metadata()

        assert "people" in metadata
        assert len(metadata["people"]) == 2

    def test_entry_with_locations_to_db_metadata(self):
        """Test locations field conversion."""
        text = """---
date: 2024-01-15
city: Montreal
locations:
  - Cafe X
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        metadata = entry.to_database_metadata()

        assert "cities" in metadata
        assert "locations" in metadata

    def test_entry_with_all_fields_to_db_metadata(self, complex_entry_content):
        """Test comprehensive entry conversion."""
        entry = MdEntry.from_markdown_text(complex_entry_content)
        metadata = entry.to_database_metadata()

        # Verify all major fields present
        assert "date" in metadata
        assert "people" in metadata
        assert "locations" in metadata
        assert "tags" in metadata
        assert "events" in metadata
        assert "dates" in metadata
        assert "references" in metadata
        assert "poems" in metadata


class TestMdEntryToMarkdown:
    """Test MdEntry.to_markdown() method."""

    def test_minimal_entry_to_markdown(self):
        """Test generating markdown for minimal entry."""
        text = """---
date: 2024-01-15
---

# Entry

Body content."""

        entry = MdEntry.from_markdown_text(text)
        output = entry.to_markdown()

        assert "---" in output
        assert "date: 2024-01-15" in output
        assert "Body content" in output

    def test_entry_with_metadata_to_markdown(self):
        """Test markdown generation preserves metadata."""
        text = """---
date: 2024-01-15
people:
  - Alice
tags:
  - test
---

# Entry

Body."""

        entry = MdEntry.from_markdown_text(text)
        output = entry.to_markdown()

        assert "people:" in output
        assert "Alice" in output
        assert "tags:" in output
        assert "test" in output

    def test_to_markdown_yaml_formatting(self):
        """Test YAML frontmatter is properly formatted."""
        text = """---
date: 2024-01-15
city: Montreal
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        output = entry.to_markdown()

        # Should have valid YAML structure
        assert output.startswith("---\n")
        assert "---\n\n" in output or "---\r\n\r\n" in output


class TestMdEntryValidation:
    """Test MdEntry validation methods."""

    def test_valid_entry_passes_validation(self):
        """Test valid entry passes validation."""
        text = """---
date: 2024-01-15
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        assert entry.is_valid()

        errors = entry.validate()
        assert len(errors) == 0

    def test_entry_without_date_fails_validation(self):
        """Test entry without required date field."""
        entry = MdEntry(
            date=None,  # type: ignore
            body_lines=["test"]
        )

        assert not entry.is_valid()


class TestMdEntryEdgeCases:
    """Test edge cases and special scenarios."""

    def test_entry_with_empty_fields(self):
        """Test entry with empty optional fields."""
        text = """---
date: 2024-01-15
people: []
tags: []
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        assert entry.date == date(2024, 1, 15)

    def test_entry_with_unicode_content(self, entry_with_special_chars):
        """Test parsing entry with unicode characters."""
        entry = MdEntry.from_markdown_text(entry_with_special_chars)

        assert entry.date == date(2024, 1, 15)
        # Should handle unicode in city, locations, people

    def test_entry_with_very_long_content(self, tmp_dir):
        """Test entry with very long body content."""
        long_content = "Word " * 10000  # 10,000 words
        text = f"""---
date: 2024-01-15
---

# Entry

{long_content}"""

        entry = MdEntry.from_markdown_text(text)
        assert entry.word_count > 5000

    def test_entry_with_special_characters_in_names(self):
        """Test names with accents and special characters."""
        text = """---
date: 2024-01-15
people:
  - François
  - María José García
  - 李明
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        assert entry.people is not None
        assert len(entry.people) >= 3

    def test_location_with_parenthetical_expansion(self):
        """Test location with name expansion."""
        text = """---
date: 2024-01-15
locations:
  - Mtl (Montreal)
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        assert entry.locations is not None


class TestMdEntryRoundTrip:
    """Test round-trip conversions."""

    def test_markdown_to_markdown_preserves_structure(self):
        """Test parsing and regenerating markdown preserves structure."""
        original = """---
date: 2024-01-15
word_count: 100
reading_time: 0.5
people:
  - Alice
tags:
  - test
---

# Entry Title

Body content here."""

        entry = MdEntry.from_markdown_text(original)
        regenerated = entry.to_markdown()

        # Parse again to verify it's valid
        entry2 = MdEntry.from_markdown_text(regenerated)

        assert entry.date == entry2.date
        assert entry.word_count == entry2.word_count

    def test_to_db_and_back_preserves_data(self):
        """Test conversion to database format preserves key data."""
        text = """---
date: 2024-01-15
people:
  - Alice
  - Bob
tags:
  - test
city: Montreal
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        db_metadata = entry.to_database_metadata()

        # Verify critical data preserved
        assert db_metadata["date"] == entry.date
        assert len(db_metadata.get("people", [])) == 2
        assert len(db_metadata.get("tags", [])) == 1
        assert "Montreal" in db_metadata.get("cities", [])
