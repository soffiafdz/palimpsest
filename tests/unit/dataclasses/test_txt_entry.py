"""
test_txt_entry.py
-----------------
Unit tests for TxtEntry dataclass.

Tests parsing of 750words .txt export files into structured entry objects.

Target Coverage: 90%+
"""
import pytest
from datetime import date
from pathlib import Path
from dev.dataclasses.txt_entry import TxtEntry
from dev.core.exceptions import EntryParseError


class TestTxtEntryFromLines:
    """Test TxtEntry.from_lines() constructor."""

    def test_from_minimal_lines(self):
        """Test creating TxtEntry from minimal valid lines."""
        lines = [
            "Date: 2024-01-15",
            "",
            "This is the body content."
        ]
        entry = TxtEntry.from_lines(lines)

        assert entry.date == date(2024, 1, 15)
        assert entry.header == "Monday, January 15th, 2024"
        assert len(entry.body) > 0
        assert entry.word_count > 0

    def test_from_lines_with_title(self):
        """Test creating entry with custom title."""
        lines = [
            "Date: 2024-01-15",
            "Title: My Custom Title",
            "",
            "Body content here."
        ]
        entry = TxtEntry.from_lines(lines)

        assert entry.date == date(2024, 1, 15)
        assert entry.header == "My Custom Title"

    def test_from_lines_with_delimited_format(self):
        """Test parsing === delimited format."""
        lines = [
            "=== DATE: 2024-01-15 ===",
            "=== TITLE: Test Title ===",
            "",
            "Body content."
        ]
        entry = TxtEntry.from_lines(lines)

        assert entry.date == date(2024, 1, 15)
        assert entry.header == "Test Title"

    def test_from_lines_computes_word_count(self):
        """Test word count is computed."""
        lines = [
            "Date: 2024-01-15",
            "",
            "Hello world this is a test"
        ]
        entry = TxtEntry.from_lines(lines)

        assert entry.word_count == 6

    def test_from_lines_computes_reading_time(self):
        """Test reading time is computed."""
        lines = [
            "Date: 2024-01-15",
            "",
            "word " * 260  # 260 words = ~1 minute
        ]
        entry = TxtEntry.from_lines(lines)

        assert entry.reading_time > 0.9
        assert entry.reading_time < 1.1

    def test_from_lines_missing_date_raises_error(self):
        """Test parsing without date raises error."""
        lines = [
            "Title: No Date Entry",
            "",
            "Body content."
        ]

        with pytest.raises(EntryParseError) as exc_info:
            TxtEntry.from_lines(lines)
        assert "date" in str(exc_info.value).lower()

    def test_from_lines_formats_body(self):
        """Test body is formatted (whitespace stripped, etc.)."""
        lines = [
            "Date: 2024-01-15",
            "",
            "  Line with spaces  ",
            "",
            "  Another line  "
        ]
        entry = TxtEntry.from_lines(lines)

        # Body should be cleaned
        assert all(not line.startswith("  ") for line in entry.body if line)


class TestTxtEntryFromFile:
    """Test TxtEntry.from_file() constructor."""

    def test_from_file_single_entry(self, tmp_dir):
        """Test parsing file with single entry."""
        file_path = tmp_dir / "single.txt"
        content = """Date: 2024-01-15

This is a single entry file.
"""
        file_path.write_text(content)

        entries = TxtEntry.from_file(file_path)

        assert len(entries) == 1
        assert entries[0].date == date(2024, 1, 15)

    def test_from_file_multiple_entries(self, tmp_dir):
        """Test parsing file with multiple entries separated by markers."""
        file_path = tmp_dir / "multiple.txt"
        content = """Date: 2024-01-15

First entry content.

------ ENTRY ------

Date: 2024-01-16

Second entry content.

------ ENTRY ------

Date: 2024-01-17

Third entry content.
"""
        file_path.write_text(content)

        entries = TxtEntry.from_file(file_path)

        assert len(entries) == 3
        assert entries[0].date == date(2024, 1, 15)
        assert entries[1].date == date(2024, 1, 16)
        assert entries[2].date == date(2024, 1, 17)

    def test_from_file_with_alternate_marker(self, tmp_dir):
        """Test parsing with alternate entry marker format."""
        file_path = tmp_dir / "alternate.txt"
        content = """Date: 2024-01-15

First entry.

===== ENTRY =====

Date: 2024-01-16

Second entry.
"""
        file_path.write_text(content)

        entries = TxtEntry.from_file(file_path)

        assert len(entries) == 2

    def test_from_file_nonexistent_raises_error(self, tmp_dir):
        """Test reading nonexistent file raises error."""
        file_path = tmp_dir / "nonexistent.txt"

        with pytest.raises((OSError, FileNotFoundError)):
            TxtEntry.from_file(file_path)

    def test_from_file_fixes_encoding(self, tmp_dir):
        """Test file reading fixes text encoding issues."""
        file_path = tmp_dir / "encoded.txt"
        # ftfy will fix encoding issues
        content = """Date: 2024-01-15

Entry with potential encoding issues.
"""
        file_path.write_text(content, encoding='utf-8')

        entries = TxtEntry.from_file(file_path)

        assert len(entries) == 1


class TestTxtEntryToMarkdown:
    """Test TxtEntry.to_markdown() serialization."""

    def test_to_markdown_includes_frontmatter(self):
        """Test markdown output includes YAML frontmatter."""
        lines = [
            "Date: 2024-01-15",
            "",
            "Body content."
        ]
        entry = TxtEntry.from_lines(lines)

        markdown = entry.to_markdown()

        assert markdown.startswith("---")
        assert "date: 2024-01-15" in markdown
        assert "word_count:" in markdown
        assert "reading_time:" in markdown

    def test_to_markdown_includes_header(self):
        """Test markdown includes formatted header."""
        lines = [
            "Date: 2024-01-15",
            "Title: Test Entry",
            "",
            "Body."
        ]
        entry = TxtEntry.from_lines(lines)

        markdown = entry.to_markdown()

        assert "# Test Entry" in markdown

    def test_to_markdown_includes_body(self):
        """Test markdown includes body content."""
        lines = [
            "Date: 2024-01-15",
            "",
            "This is the body."
        ]
        entry = TxtEntry.from_lines(lines)

        markdown = entry.to_markdown()

        assert "This is the body" in markdown

    def test_to_markdown_formats_reading_time(self):
        """Test reading time is formatted to 1 decimal place."""
        lines = [
            "Date: 2024-01-15",
            "",
            "Short body."
        ]
        entry = TxtEntry.from_lines(lines)

        markdown = entry.to_markdown()

        # Should have format like "reading_time: 0.0"
        assert "reading_time:" in markdown
        # Check it's formatted with 1 decimal
        import re
        match = re.search(r'reading_time: (\d+\.\d)', markdown)
        assert match is not None


class TestTxtEntrySplitEntries:
    """Test TxtEntry._split_entries() helper."""

    def test_split_single_entry(self):
        """Test splitting lines with no markers returns single entry."""
        lines = ["Line 1", "Line 2", "Line 3"]
        markers = ["------ ENTRY ------"]

        entries = TxtEntry._split_entries(lines, markers)

        assert len(entries) == 1
        assert entries[0] == lines

    def test_split_multiple_entries(self):
        """Test splitting on entry markers."""
        lines = [
            "Entry 1 line 1",
            "Entry 1 line 2",
            "------ ENTRY ------",
            "Entry 2 line 1",
            "Entry 2 line 2",
        ]
        markers = ["------ ENTRY ------"]

        entries = TxtEntry._split_entries(lines, markers)

        assert len(entries) == 2
        assert entries[0] == ["Entry 1 line 1", "Entry 1 line 2"]
        assert entries[1] == ["Entry 2 line 1", "Entry 2 line 2"]

    def test_split_with_multiple_markers(self):
        """Test splitting with multiple marker types."""
        lines = [
            "Entry 1",
            "------ ENTRY ------",
            "Entry 2",
            "===== ENTRY =====",
            "Entry 3",
        ]
        markers = ["------ ENTRY ------", "===== ENTRY ====="]

        entries = TxtEntry._split_entries(lines, markers)

        assert len(entries) == 3

    def test_split_ignores_marker_lines(self):
        """Test marker lines are not included in entries."""
        lines = [
            "Content",
            "------ ENTRY ------",
            "More content",
        ]
        markers = ["------ ENTRY ------"]

        entries = TxtEntry._split_entries(lines, markers)

        assert "------ ENTRY ------" not in entries[0]
        assert "------ ENTRY ------" not in entries[1]

    def test_split_empty_lines_returns_empty(self):
        """Test splitting empty input returns empty list."""
        entries = TxtEntry._split_entries([], ["------ ENTRY ------"])

        assert entries == []

    def test_split_marker_at_start(self):
        """Test marker at start creates first entry after it."""
        lines = [
            "------ ENTRY ------",
            "Entry 1",
        ]
        markers = ["------ ENTRY ------"]

        entries = TxtEntry._split_entries(lines, markers)

        assert len(entries) == 1
        assert entries[0] == ["Entry 1"]


class TestTxtEntryParseEntry:
    """Test TxtEntry._parse_entry() helper."""

    def test_parse_simple_format(self):
        """Test parsing simple Date:/Title: format."""
        lines = [
            "Date: 2024-01-15",
            "Title: Test Title",
            "",
            "Body line 1",
            "Body line 2",
        ]

        date_obj, header, body = TxtEntry._parse_entry(lines)

        assert date_obj == date(2024, 1, 15)
        assert header == "Test Title"
        assert "Body line 1" in body

    def test_parse_delimited_format(self):
        """Test parsing === delimited format."""
        lines = [
            "=== DATE: 2024-01-15 ===",
            "=== TITLE: Delimited Title ===",
            "",
            "Body content",
        ]

        date_obj, header, body = TxtEntry._parse_entry(lines)

        assert date_obj == date(2024, 1, 15)
        assert header == "Delimited Title"

    def test_parse_without_title_generates_header(self):
        """Test entry without title generates formatted date header."""
        lines = [
            "Date: 2024-01-15",
            "",
            "Body",
        ]

        date_obj, header, body = TxtEntry._parse_entry(lines)

        assert date_obj == date(2024, 1, 15)
        assert "January" in header
        assert "15th" in header
        assert "2024" in header

    def test_parse_with_body_marker(self):
        """Test parsing with explicit === BODY === marker."""
        lines = [
            "Date: 2024-01-15",
            "Title: Test",
            "=== BODY ===",
            "Body starts here",
        ]

        date_obj, header, body = TxtEntry._parse_entry(lines)

        assert body[0] == "Body starts here"

    def test_parse_missing_date_raises_error(self):
        """Test parsing without date raises EntryParseError."""
        lines = [
            "Title: No Date",
            "",
            "Body",
        ]

        with pytest.raises(EntryParseError) as exc_info:
            TxtEntry._parse_entry(lines)
        assert "date" in str(exc_info.value).lower()


class TestTxtEntryAttributes:
    """Test TxtEntry attribute types and values."""

    def test_entry_has_date_attribute(self):
        """Test entry has date attribute."""
        lines = ["Date: 2024-01-15", "", "Body"]
        entry = TxtEntry.from_lines(lines)

        assert hasattr(entry, 'date')
        assert isinstance(entry.date, date)

    def test_entry_has_header_attribute(self):
        """Test entry has header attribute."""
        lines = ["Date: 2024-01-15", "", "Body"]
        entry = TxtEntry.from_lines(lines)

        assert hasattr(entry, 'header')
        assert isinstance(entry.header, str)

    def test_entry_has_body_attribute(self):
        """Test entry has body attribute as list."""
        lines = ["Date: 2024-01-15", "", "Body"]
        entry = TxtEntry.from_lines(lines)

        assert hasattr(entry, 'body')
        assert isinstance(entry.body, list)

    def test_entry_has_word_count(self):
        """Test entry has word_count attribute."""
        lines = ["Date: 2024-01-15", "", "Body"]
        entry = TxtEntry.from_lines(lines)

        assert hasattr(entry, 'word_count')
        assert isinstance(entry.word_count, int)
        assert entry.word_count >= 0

    def test_entry_has_reading_time(self):
        """Test entry has reading_time attribute."""
        lines = ["Date: 2024-01-15", "", "Body"]
        entry = TxtEntry.from_lines(lines)

        assert hasattr(entry, 'reading_time')
        assert isinstance(entry.reading_time, float)
        assert entry.reading_time >= 0.0


class TestTxtEntryEdgeCases:
    """Test edge cases and special scenarios."""

    def test_entry_with_empty_body(self):
        """Test entry with no body content."""
        lines = [
            "Date: 2024-01-15",
            "",
        ]
        entry = TxtEntry.from_lines(lines)

        assert entry.date == date(2024, 1, 15)
        assert entry.word_count == 0

    def test_entry_with_unicode_content(self):
        """Test entry with unicode characters."""
        lines = [
            "Date: 2024-01-15",
            "",
            "Café français with émojis 🎉"
        ]
        entry = TxtEntry.from_lines(lines)

        assert "Café" in " ".join(entry.body)

    def test_entry_with_very_long_body(self):
        """Test entry with long body text."""
        lines = ["Date: 2024-01-15", ""] + ["word"] * 1000
        entry = TxtEntry.from_lines(lines)

        assert entry.word_count == 1000
        assert entry.reading_time > 3.0  # Should be ~4 minutes

    def test_multiple_entries_same_date(self, tmp_dir):
        """Test parsing multiple entries with same date."""
        file_path = tmp_dir / "same_date.txt"
        content = """Date: 2024-01-15

First entry.

------ ENTRY ------

Date: 2024-01-15

Second entry same date.
"""
        file_path.write_text(content)

        entries = TxtEntry.from_file(file_path)

        assert len(entries) == 2
        assert entries[0].date == entries[1].date

    def test_entry_with_soft_breaks(self):
        """Test entry with soft break markers (backslash)."""
        lines = [
            "Date: 2024-01-15",
            "",
            "Line with soft break\\",
            "Continues here"
        ]
        entry = TxtEntry.from_lines(lines)

        # Soft breaks should be preserved
        assert len(entry.body) > 0

    def test_to_markdown_roundtrip_preserves_date(self):
        """Test converting to markdown preserves date."""
        lines = ["Date: 2024-01-15", "", "Body content"]
        entry = TxtEntry.from_lines(lines)

        markdown = entry.to_markdown()

        assert "2024-01-15" in markdown
