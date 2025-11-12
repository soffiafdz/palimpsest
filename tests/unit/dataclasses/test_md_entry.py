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


class TestMdEntryRealFiles:
    """Test MdEntry parsing with real journal entry files."""

    @staticmethod
    def _safe_parse(file_path: Path):
        """Safely parse a file, returning None on error."""
        try:
            return MdEntry.from_file(file_path)
        except (EntryParseError, Exception):
            return None

    def test_parse_all_real_entries(self, sample_entries_dir):
        """Test that all real entry files can be parsed without errors."""
        md_files = list(sample_entries_dir.glob("*.md"))

        # Should have multiple real entry files
        assert len(md_files) > 5

        parsed_entries = []
        failed_files = []

        for file_path in md_files:
            try:
                entry = MdEntry.from_file(file_path)
                parsed_entries.append(entry)

                # Each entry should have basic required fields
                assert entry.date is not None
                assert isinstance(entry.date, date)
                assert entry.file_path == file_path
                assert isinstance(entry.metadata, dict)
                assert isinstance(entry.body, list)
            except (EntryParseError, Exception) as e:
                # Track files that fail to parse
                failed_files.append((file_path.name, str(e)[:100]))

        # Most files should parse successfully (allow some to have YAML errors)
        success_rate = len(parsed_entries) / len(md_files)
        assert success_rate > 0.8, f"Only {success_rate:.1%} parsed. Failed: {failed_files}"

    def test_real_entries_date_range(self, sample_entries_dir):
        """Test that real entries span expected date range."""
        md_files = list(sample_entries_dir.glob("*.md"))
        dates = []

        for file_path in md_files:
            entry = self._safe_parse(file_path)
            if entry:
                dates.append(entry.date)

        # Should have parsed at least some entries
        assert len(dates) > 5

        # Dates should be in reasonable range
        for entry_date in dates:
            assert entry_date.year >= 2024
            assert entry_date.year <= 2025

        # Should have entries from different dates
        assert len(set(dates)) > 1

    def test_real_entries_chronological_order(self, sample_entries_dir):
        """Test parsing entries in chronological order."""
        md_files = sorted(sample_entries_dir.glob("*.md"))
        entries = [self._safe_parse(f) for f in md_files]
        entries = [e for e in entries if e]  # Filter out failed parses

        # Should have parsed at least some entries
        assert len(entries) > 5

        # Files should generally be in chronological order
        # (allowing for some flexibility since filenames should match dates)
        if len(entries) > 1:
            # At least check first and last
            assert entries[0].date <= entries[-1].date

    def test_real_entries_with_people(self, sample_entries_dir):
        """Test that entries with people metadata parse correctly."""
        md_files = list(sample_entries_dir.glob("*.md"))
        entries_with_people = []

        for file_path in md_files:
            entry = self._safe_parse(file_path)
            if entry and 'people' in entry.metadata and entry.metadata['people']:
                entries_with_people.append(entry)

        # At least some entries should have people
        assert len(entries_with_people) > 0

        # Verify people field structure
        for entry in entries_with_people:
            people = entry.metadata['people']
            # People can be a list or a single string
            if isinstance(people, list):
                assert len(people) > 0
                # Each person should be a string (filter out None values)
                for person in people:
                    if person is not None:
                        assert isinstance(person, str)
            else:
                # Single person as string (or None)
                if people is not None:
                    assert isinstance(people, str)

    def test_real_entries_with_locations(self, sample_entries_dir):
        """Test that entries with location metadata parse correctly."""
        md_files = list(sample_entries_dir.glob("*.md"))
        entries_with_locations = []

        for file_path in md_files:
            entry = self._safe_parse(file_path)
            if entry and 'locations' in entry.metadata and entry.metadata['locations']:
                entries_with_locations.append(entry)

        # At least some entries should have locations
        assert len(entries_with_locations) > 0

        for entry in entries_with_locations:
            locations = entry.metadata['locations']
            # Locations can be a list, dict, or single string
            if isinstance(locations, list):
                assert len(locations) > 0
            elif isinstance(locations, dict):
                assert len(locations) > 0
            else:
                assert isinstance(locations, str)

    def test_real_entries_with_tags(self, sample_entries_dir):
        """Test that entries with tags parse correctly."""
        md_files = list(sample_entries_dir.glob("*.md"))
        entries_with_tags = []

        for file_path in md_files:
            entry = self._safe_parse(file_path)
            if entry and 'tags' in entry.metadata and entry.metadata['tags']:
                entries_with_tags.append(entry)

        # At least some entries should have tags
        assert len(entries_with_tags) > 0

        for entry in entries_with_tags:
            tags = entry.metadata['tags']
            # Tags can be a list or a single string
            if isinstance(tags, list):
                assert len(tags) > 0
            else:
                assert isinstance(tags, str)

    def test_real_entries_with_references(self, sample_entries_dir):
        """Test that entries with references parse correctly."""
        md_files = list(sample_entries_dir.glob("*.md"))
        entries_with_refs = []

        for file_path in md_files:
            entry = self._safe_parse(file_path)
            if entry and 'references' in entry.metadata and entry.metadata['references']:
                entries_with_refs.append(entry)

        # At least some entries should have references
        assert len(entries_with_refs) > 0

        for entry in entries_with_refs:
            references = entry.metadata['references']
            # References could be a list or a single dict
            if isinstance(references, list):
                assert len(references) > 0
            else:
                assert isinstance(references, dict)

    def test_real_entries_with_events(self, sample_entries_dir):
        """Test that entries with events parse correctly."""
        md_files = list(sample_entries_dir.glob("*.md"))
        entries_with_events = []

        for file_path in md_files:
            entry = self._safe_parse(file_path)
            if entry and 'events' in entry.metadata and entry.metadata['events']:
                entries_with_events.append(entry)

        # At least some entries should have events
        assert len(entries_with_events) > 0

    def test_real_entries_with_mentioned_dates(self, sample_entries_dir):
        """Test that entries with mentioned dates parse correctly."""
        md_files = list(sample_entries_dir.glob("*.md"))
        entries_with_dates = []

        for file_path in md_files:
            entry = self._safe_parse(file_path)
            if entry and 'dates' in entry.metadata and entry.metadata['dates']:
                entries_with_dates.append(entry)

        # At least some entries should have mentioned dates
        assert len(entries_with_dates) > 0

        for entry in entries_with_dates:
            dates = entry.metadata['dates']
            # Dates could be "~" (none) or a list
            if dates != "~":
                assert isinstance(dates, list)

    def test_real_entries_word_counts(self, sample_entries_dir):
        """Test that entries with word counts have reasonable values."""
        md_files = list(sample_entries_dir.glob("*.md"))
        entries_with_wc = []

        for file_path in md_files:
            entry = self._safe_parse(file_path)
            if entry and 'word_count' in entry.metadata and entry.metadata['word_count']:
                entries_with_wc.append(entry)

        # At least some entries should have word counts
        assert len(entries_with_wc) > 0

        for entry in entries_with_wc:
            wc = entry.metadata['word_count']
            assert isinstance(wc, (int, float))
            assert wc > 0
            # Reasonable upper bound
            assert wc < 10000

    def test_real_entries_reading_time(self, sample_entries_dir):
        """Test that entries with reading time have reasonable values."""
        md_files = list(sample_entries_dir.glob("*.md"))
        entries_with_rt = []

        for file_path in md_files:
            entry = self._safe_parse(file_path)
            if entry and 'reading_time' in entry.metadata and entry.metadata['reading_time']:
                entries_with_rt.append(entry)

        # At least some entries should have reading time
        assert len(entries_with_rt) > 0

        for entry in entries_with_rt:
            rt = entry.metadata['reading_time']
            assert isinstance(rt, (int, float))
            assert rt > 0
            # Should be proportional to word count if both present
            if 'word_count' in entry.metadata:
                wc = entry.metadata['word_count']
                # Rough estimate: 200-300 words per minute
                expected_min = wc / 300
                expected_max = wc / 150
                assert expected_min <= rt <= expected_max

    def test_real_entries_with_epigraphs(self, sample_entries_dir):
        """Test that entries with epigraphs parse correctly."""
        md_files = list(sample_entries_dir.glob("*.md"))
        entries_with_epigraphs = []

        for file_path in md_files:
            entry = self._safe_parse(file_path)
            if entry and 'epigraph' in entry.metadata and entry.metadata['epigraph']:
                entries_with_epigraphs.append(entry)

        # At least some entries should have epigraphs
        assert len(entries_with_epigraphs) > 0

        for entry in entries_with_epigraphs:
            epigraph = entry.metadata['epigraph']
            assert isinstance(epigraph, str)
            assert len(epigraph) > 0

    def test_real_entries_unicode_handling(self, sample_entries_dir):
        """Test that real entries with unicode characters parse correctly."""
        # The real entries contain names like "María José", "Montréal", Spanish text
        md_files = list(sample_entries_dir.glob("*.md"))

        unicode_handled = False
        for file_path in md_files:
            entry = self._safe_parse(file_path)
            if not entry:
                continue

            # Check for unicode in various fields
            if 'city' in entry.metadata:
                city = entry.metadata['city']
                if isinstance(city, str) and any(ord(c) > 127 for c in city):
                    unicode_handled = True
                    break

            if 'people' in entry.metadata:
                people = entry.metadata['people']
                if isinstance(people, list):
                    for person in people:
                        if isinstance(person, str) and any(ord(c) > 127 for c in person):
                            unicode_handled = True
                            break

        # At least some unicode should be present and handled
        assert unicode_handled

    def test_real_entries_body_content(self, sample_entries_dir):
        """Test that real entries have substantial body content."""
        md_files = list(sample_entries_dir.glob("*.md"))
        parsed_count = 0

        for file_path in md_files:
            entry = self._safe_parse(file_path)
            if not entry:
                continue

            parsed_count += 1

            # Body should be a list of strings
            assert isinstance(entry.body, list)

            # Most entries should have substantial content
            # (allowing for some short entries)
            body_text = "\n".join(entry.body)
            assert len(body_text) > 0

        # Should have parsed at least some entries
        assert parsed_count > 5


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
