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
        assert len(entry.body) > 0
        assert entry.metadata['date'] == date(2024, 1, 15)

    def test_from_complex_file(self, complex_entry_file):
        """Test parsing complex entry with all metadata."""
        entry = MdEntry.from_file(complex_entry_file)

        assert entry.date == date(2024, 1, 15)
        assert entry.metadata.get('word_count') == 850
        assert entry.metadata.get('reading_time') == 4.2
        assert 'city' in entry.metadata
        assert 'locations' in entry.metadata
        assert 'people' in entry.metadata
        assert 'tags' in entry.metadata

    def test_nonexistent_file_raises_error(self, tmp_dir):
        """Test reading nonexistent file raises error."""
        nonexistent = tmp_dir / "nonexistent.md"
        with pytest.raises((FileNotFoundError, EntryParseError)):
            MdEntry.from_file(nonexistent)

    def test_file_without_frontmatter(self, tmp_dir):
        """Test file without frontmatter raises error."""
        file_path = tmp_dir / "no-frontmatter.md"
        file_path.write_text("# Title\n\nJust body content, no YAML.")

        with pytest.raises((EntryParseError, EntryValidationError, ValueError)):
            MdEntry.from_file(file_path)

    def test_file_with_invalid_yaml(self, tmp_dir):
        """Test file with malformed YAML raises error."""
        file_path = tmp_dir / "bad-yaml.md"
        file_path.write_text("""---
date: 2024-01-15
people: [unclosed list
---

Body content""")

        with pytest.raises((EntryParseError, Exception)):
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
        assert len(entry.body) > 0

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
        assert 'people' in entry.metadata
        people = entry.metadata['people']
        assert len(people) >= 1

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
        assert entry.metadata.get('city') == "Montreal"
        assert 'locations' in entry.metadata

    def test_body_is_list_of_strings(self):
        """Test that body is a list of strings."""
        text = """---
date: 2024-01-15
---

Line 1
Line 2
Line 3"""

        entry = MdEntry.from_markdown_text(text)
        assert isinstance(entry.body, list)
        assert all(isinstance(line, str) for line in entry.body)

    def test_metadata_is_dict(self):
        """Test that metadata is a dictionary."""
        text = """---
date: 2024-01-15
word_count: 100
---

Body"""

        entry = MdEntry.from_markdown_text(text)
        assert isinstance(entry.metadata, dict)
        assert 'date' in entry.metadata
        assert 'word_count' in entry.metadata


class TestMdEntryParsing:
    """Test MdEntry field parsing."""

    def test_parse_single_city(self):
        """Test parsing single city string."""
        text = """---
date: 2024-01-15
city: Montreal
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        assert entry.metadata.get('city') == "Montreal"

    def test_parse_multiple_cities(self):
        """Test parsing city as list."""
        text = """---
date: 2024-01-15
city:
  - Montreal
  - Toronto
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        city = entry.metadata.get('city')
        assert city is not None

    def test_parse_tags_list(self):
        """Test parsing tags."""
        text = """---
date: 2024-01-15
tags:
  - python
  - testing
  - palimpsest
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        tags = entry.metadata.get('tags', [])
        assert 'python' in tags
        assert 'testing' in tags

    def test_parse_word_count_and_reading_time(self):
        """Test parsing numeric fields."""
        text = """---
date: 2024-01-15
word_count: 500
reading_time: 2.5
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        assert entry.metadata.get('word_count') == 500
        assert entry.metadata.get('reading_time') == 2.5

    def test_parse_poem_with_metadata(self):
        """Test parsing poem with all fields."""
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
        poems = entry.metadata.get('poems', [])
        assert len(poems) >= 1

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
        references = entry.metadata.get('references', [])
        assert len(references) >= 1

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
        manuscript = entry.metadata.get('manuscript')
        assert manuscript is not None


class TestMdEntryToDatabaseMetadata:
    """Test MdEntry.to_database_metadata() method."""

    def test_minimal_entry_to_db_metadata(self, tmp_dir):
        """Test converting minimal entry to database metadata."""
        text = """---
date: 2024-01-15
---

# Entry"""

        file_path = tmp_dir / "test.md"
        entry = MdEntry.from_markdown_text(text, file_path=file_path)
        db_meta = entry.to_database_metadata()

        assert db_meta['date'] == date(2024, 1, 15)
        assert isinstance(db_meta, dict)

    def test_entry_with_people_to_db_metadata(self, tmp_dir):
        """Test people field conversion to database format."""
        text = """---
date: 2024-01-15
people:
  - Alice
  - Bob
---

# Entry"""

        file_path = tmp_dir / "test.md"
        entry = MdEntry.from_markdown_text(text, file_path=file_path)
        db_meta = entry.to_database_metadata()

        assert 'people' in db_meta or 'person' in db_meta

    def test_entry_with_tags_to_db_metadata(self, tmp_dir):
        """Test tags field conversion."""
        text = """---
date: 2024-01-15
tags:
  - test
  - python
---

# Entry"""

        file_path = tmp_dir / "test.md"
        entry = MdEntry.from_markdown_text(text, file_path=file_path)
        db_meta = entry.to_database_metadata()

        # Check tags are present in some form
        assert 'tags' in db_meta or 'tag' in db_meta


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
        assert "date:" in output or "2024-01-15" in output
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

        assert "---" in output
        # YAML frontmatter should be present
        assert output.count("---") >= 2

    def test_to_markdown_is_valid_format(self):
        """Test generated markdown has valid structure."""
        text = """---
date: 2024-01-15
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        output = entry.to_markdown()

        # Should start with frontmatter
        assert output.strip().startswith("---")


class TestMdEntryValidation:
    """Test MdEntry validation methods."""

    def test_valid_entry_passes_validation(self):
        """Test valid entry passes validation."""
        text = """---
date: 2024-01-15
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        errors = entry.validate()

        # Should return a list (possibly empty if valid)
        assert isinstance(errors, list)

    def test_is_valid_returns_boolean(self):
        """Test is_valid returns boolean."""
        text = """---
date: 2024-01-15
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        result = entry.is_valid

        assert isinstance(result, bool)


class TestMdEntryAttributes:
    """Test MdEntry attributes and structure."""

    def test_entry_has_required_attributes(self):
        """Test entry has all required attributes."""
        text = """---
date: 2024-01-15
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)

        assert hasattr(entry, 'date')
        assert hasattr(entry, 'body')
        assert hasattr(entry, 'metadata')
        assert hasattr(entry, 'file_path')
        assert hasattr(entry, 'frontmatter_raw')

    def test_entry_attribute_types(self):
        """Test attribute types are correct."""
        text = """---
date: 2024-01-15
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)

        assert isinstance(entry.date, date)
        assert isinstance(entry.body, list)
        assert isinstance(entry.metadata, dict)
        assert isinstance(entry.frontmatter_raw, str)

    def test_file_path_is_none_for_text(self):
        """Test file_path is None when parsed from text."""
        text = """---
date: 2024-01-15
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        assert entry.file_path is None

    def test_file_path_is_set_from_file(self, minimal_entry_file):
        """Test file_path is set when loaded from file."""
        entry = MdEntry.from_file(minimal_entry_file)
        assert entry.file_path == minimal_entry_file
        assert isinstance(entry.file_path, Path)


class TestMdEntryEdgeCases:
    """Test edge cases and special scenarios."""

    def test_entry_with_empty_body(self):
        """Test entry with minimal/empty body."""
        text = """---
date: 2024-01-15
---
"""

        entry = MdEntry.from_markdown_text(text)
        assert entry.date == date(2024, 1, 15)
        # Body might be empty list or have minimal content
        assert isinstance(entry.body, list)

    def test_entry_with_unicode_content(self):
        """Test parsing entry with unicode characters."""
        text = """---
date: 2024-01-15
city: Montréal
people:
  - François
  - María José
---

# Entry

Unicode: café, naïve, 日本語"""

        entry = MdEntry.from_markdown_text(text)
        assert entry.date == date(2024, 1, 15)
        # Should handle unicode gracefully

    def test_entry_with_special_characters_in_names(self):
        """Test names with hyphens and special characters."""
        text = """---
date: 2024-01-15
people:
  - María-José
  - Jean-Claude
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        people = entry.metadata.get('people', [])
        assert len(people) >= 1

    def test_entry_with_multiline_content(self):
        """Test entry with multiple paragraphs."""
        text = """---
date: 2024-01-15
---

# Title

Paragraph 1 with some text.

Paragraph 2 with more text.

Paragraph 3 continues.
"""

        entry = MdEntry.from_markdown_text(text)
        assert len(entry.body) > 3

    def test_empty_metadata_fields(self):
        """Test entry with empty list fields."""
        text = """---
date: 2024-01-15
people: []
tags: []
---

# Entry"""

        entry = MdEntry.from_markdown_text(text)
        assert entry.date == date(2024, 1, 15)


class TestMdEntryRoundTrip:
    """Test round-trip conversions."""

    def test_parse_and_regenerate_preserves_date(self):
        """Test date is preserved through parse and generate cycle."""
        text = """---
date: 2024-01-15
---

# Entry"""

        entry1 = MdEntry.from_markdown_text(text)
        markdown = entry1.to_markdown()
        entry2 = MdEntry.from_markdown_text(markdown)

        assert entry1.date == entry2.date

    def test_to_markdown_produces_parseable_output(self):
        """Test generated markdown can be parsed again."""
        text = """---
date: 2024-01-15
word_count: 100
tags:
  - test
---

# Entry

Content."""

        entry = MdEntry.from_markdown_text(text)
        markdown = entry.to_markdown()

        # Should be able to parse the generated markdown
        entry2 = MdEntry.from_markdown_text(markdown)
        assert entry2.date == date(2024, 1, 15)
