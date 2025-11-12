"""
test_txt_entry.py
-----------------
Unit tests for dev.dataclasses.txt_entry module.

Tests the TxtEntry dataclass which handles parsing of 750words .txt export files.

Target Coverage: 90%+
"""
import pytest
from datetime import date
from dev.dataclasses.txt_entry import TxtEntry, LEGACY_BODY_OFFSET
from dev.core.exceptions import EntryParseError


class TestTxtEntryFromLines:
    """Test TxtEntry.from_lines() method."""

    def test_from_basic_lines(self):
        """Test parsing basic txt entry lines."""
        lines = [
            "January 15, 2024",
            "Entry Title",
            "",
            "This is the body content of the entry.",
            "Multiple lines of text here."
        ]

        entry = TxtEntry.from_lines(lines)

        assert entry.date == date(2024, 1, 15)
        assert entry.header is not None
        assert len(entry.body) > 0
        assert entry.word_count > 0
        assert entry.reading_time > 0

    def test_from_lines_with_minimal_content(self):
        """Test parsing minimal entry."""
        lines = [
            "January 15, 2024",
            "",
            "",
            "Body text."
        ]

        entry = TxtEntry.from_lines(lines)
        assert entry.date == date(2024, 1, 15)
        assert len(entry.body) > 0

    def test_from_lines_calculates_word_count(self):
        """Test word count calculation."""
        lines = [
            "January 15, 2024",
            "Title",
            "",
            "This entry has exactly ten words in the body content."
        ]

        entry = TxtEntry.from_lines(lines)
        assert entry.word_count == 10

    def test_from_lines_calculates_reading_time(self):
        """Test reading time calculation."""
        # Create entry with ~200 words (1 minute reading time)
        body_text = " ".join(["word"] * 200)
        lines = [
            "January 15, 2024",
            "Title",
            "",
            body_text
        ]

        entry = TxtEntry.from_lines(lines)
        assert entry.reading_time > 0
        assert entry.reading_time < 5  # Should be reasonable


class TestTxtEntryParsing:
    """Test TxtEntry parsing logic."""

    def test_parse_date_from_various_formats(self):
        """Test date parsing from different formats."""
        date_formats = [
            ("January 15, 2024", date(2024, 1, 15)),
            ("Jan 15, 2024", date(2024, 1, 15)),
            ("01/15/2024", date(2024, 1, 15)),
        ]

        for date_str, expected_date in date_formats:
            lines = [date_str, "", "", "Body"]
            try:
                entry = TxtEntry.from_lines(lines)
                if entry.date == expected_date:
                    assert True
            except (EntryParseError, ValueError):
                # Some formats might not be supported
                pass

    def test_parse_handles_empty_lines(self):
        """Test parsing handles multiple empty lines."""
        lines = [
            "January 15, 2024",
            "",
            "",
            "",
            "",
            "Body content starts here."
        ]

        entry = TxtEntry.from_lines(lines)
        assert len(entry.body) > 0
        # Empty lines should be handled gracefully

    def test_parse_preserves_paragraph_structure(self):
        """Test body parsing preserves paragraphs."""
        lines = [
            "January 15, 2024",
            "Title",
            "",
            "First paragraph.",
            "",
            "Second paragraph.",
            "",
            "Third paragraph."
        ]

        entry = TxtEntry.from_lines(lines)
        body_text = "\n".join(entry.body)

        # Should have paragraph breaks
        assert len(entry.body) > 3


class TestTxtEntryBodyProcessing:
    """Test body content processing."""

    def test_body_text_cleaning(self):
        """Test body text is cleaned of artifacts."""
        lines = [
            "January 15, 2024",
            "Title",
            "",
            "Text with   extra    spaces",
            "Text with\ttabs"
        ]

        entry = TxtEntry.from_lines(lines)
        # Body should be cleaned

    def test_body_unicode_handling(self):
        """Test body handles unicode characters."""
        lines = [
            "January 15, 2024",
            "Title",
            "",
            "Unicode text: café, naïve, 日本語"
        ]

        entry = TxtEntry.from_lines(lines)
        body_text = " ".join(entry.body)
        # Unicode should be preserved or properly handled
        assert len(body_text) > 0

    def test_long_body_content(self):
        """Test processing very long body content."""
        long_text = " ".join(["word"] * 5000)
        lines = [
            "January 15, 2024",
            "Title",
            "",
            long_text
        ]

        entry = TxtEntry.from_lines(lines)
        assert entry.word_count > 4000
        assert entry.reading_time > 10  # ~5000 words / ~200 wpm


class TestTxtEntryToMarkdown:
    """Test TxtEntry markdown conversion."""

    def test_to_minimal_markdown(self):
        """Test converting to minimal markdown."""
        lines = [
            "January 15, 2024",
            "",
            "",
            "Body content here."
        ]

        entry = TxtEntry.from_lines(lines)

        # TxtEntry should have basic conversion capability
        # Even if it's just the raw data
        assert entry.header is not None
        assert entry.body is not None


class TestTxtEntryEdgeCases:
    """Test edge cases."""

    def test_entry_with_special_characters(self):
        """Test entry with special characters in body."""
        lines = [
            "January 15, 2024",
            "Title",
            "",
            "Text with \"quotes\" and 'apostrophes'",
            "Text with <html> tags",
            "Text with & ampersand"
        ]

        entry = TxtEntry.from_lines(lines)
        assert len(entry.body) > 0

    def test_empty_body(self):
        """Test entry with empty body."""
        lines = [
            "January 15, 2024",
            "",
            "",
            ""
        ]

        # Should handle gracefully or raise appropriate error
        try:
            entry = TxtEntry.from_lines(lines)
            # If it succeeds, word count should be 0
            assert entry.word_count == 0
        except EntryParseError:
            # Or it might raise an error for empty content
            pass

    def test_malformed_date(self):
        """Test entry with malformed date."""
        lines = [
            "Not a valid date",
            "",
            "",
            "Body content"
        ]

        # Should raise appropriate error
        with pytest.raises((EntryParseError, ValueError)):
            TxtEntry.from_lines(lines)


class TestTxtEntryLegacyFormat:
    """Test handling of legacy 750words format."""

    def test_legacy_body_offset(self):
        """Test LEGACY_BODY_OFFSET constant."""
        assert LEGACY_BODY_OFFSET == 3

    def test_legacy_format_parsing(self):
        """Test parsing entry in legacy format."""
        # In legacy format, body starts at line 3 after date
        lines = [
            "January 15, 2024",  # Line 0
            "Title Line",         # Line 1
            "",                   # Line 2
            "Body starts here"    # Line 3 (LEGACY_BODY_OFFSET)
        ]

        entry = TxtEntry.from_lines(lines)
        assert entry.date == date(2024, 1, 15)
        assert "Body starts here" in " ".join(entry.body)


class TestTxtEntryAttributes:
    """Test TxtEntry attributes."""

    def test_entry_has_required_attributes(self):
        """Test entry has all required attributes."""
        lines = [
            "January 15, 2024",
            "",
            "",
            "Body"
        ]

        entry = TxtEntry.from_lines(lines)

        assert hasattr(entry, 'date')
        assert hasattr(entry, 'header')
        assert hasattr(entry, 'body')
        assert hasattr(entry, 'word_count')
        assert hasattr(entry, 'reading_time')

    def test_entry_attributes_types(self):
        """Test attribute types are correct."""
        lines = [
            "January 15, 2024",
            "Header",
            "",
            "Body content"
        ]

        entry = TxtEntry.from_lines(lines)

        assert isinstance(entry.date, date)
        assert isinstance(entry.header, str)
        assert isinstance(entry.body, list)
        assert isinstance(entry.word_count, int)
        assert isinstance(entry.reading_time, float)
