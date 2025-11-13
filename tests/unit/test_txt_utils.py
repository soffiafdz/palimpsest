"""
test_txt_utils.py
-----------------
Unit tests for txt utility functions.

Tests utilities for parsing, formatting, and processing text documents
from 750words exports.

Target Coverage: 95%+
"""
import pytest
from dev.utils.txt import ordinal, format_body, reflow_paragraph, compute_metrics


class TestOrdinal:
    """Test ordinal() function for converting numbers to ordinal strings."""

    def test_ordinal_1st(self):
        """Test 1st."""
        assert ordinal(1) == "1st"

    def test_ordinal_2nd(self):
        """Test 2nd."""
        assert ordinal(2) == "2nd"

    def test_ordinal_3rd(self):
        """Test 3rd."""
        assert ordinal(3) == "3rd"

    def test_ordinal_4th(self):
        """Test 4th."""
        assert ordinal(4) == "4th"

    def test_ordinal_11th(self):
        """Test 11th (special case)."""
        assert ordinal(11) == "11th"

    def test_ordinal_12th(self):
        """Test 12th (special case)."""
        assert ordinal(12) == "12th"

    def test_ordinal_13th(self):
        """Test 13th (special case)."""
        assert ordinal(13) == "13th"

    def test_ordinal_21st(self):
        """Test 21st."""
        assert ordinal(21) == "21st"

    def test_ordinal_22nd(self):
        """Test 22nd."""
        assert ordinal(22) == "22nd"

    def test_ordinal_23rd(self):
        """Test 23rd."""
        assert ordinal(23) == "23rd"

    def test_ordinal_24th(self):
        """Test 24th."""
        assert ordinal(24) == "24th"

    def test_ordinal_31st(self):
        """Test 31st (max day of month)."""
        assert ordinal(31) == "31st"

    def test_ordinal_100th(self):
        """Test 100th."""
        assert ordinal(100) == "100th"

    def test_ordinal_101st(self):
        """Test 101st."""
        assert ordinal(101) == "101st"

    def test_ordinal_111th(self):
        """Test 111th (special case with 11)."""
        assert ordinal(111) == "111th"

    def test_ordinal_112th(self):
        """Test 112th (special case with 12)."""
        assert ordinal(112) == "112th"

    def test_ordinal_113th(self):
        """Test 113th (special case with 13)."""
        assert ordinal(113) == "113th"


class TestFormatBody:
    """Test format_body() function for processing text lines."""

    def test_single_line(self):
        """Test formatting single line."""
        lines = ["Hello world"]
        result = format_body(lines)
        assert result == [("Hello world", False)]

    def test_multiple_lines(self):
        """Test formatting multiple lines."""
        lines = ["Line 1", "Line 2", "Line 3"]
        result = format_body(lines)
        assert result == [
            ("Line 1", False),
            ("Line 2", False),
            ("Line 3", False),
        ]

    def test_soft_break_with_backslash(self):
        """Test detecting soft break (line ending with backslash)."""
        lines = ["Line with soft break\\"]
        result = format_body(lines)
        assert result == [("Line with soft break\\", True)]

    def test_strips_newlines(self):
        """Test stripping newline characters."""
        lines = ["Line 1\n", "Line 2\n"]
        result = format_body(lines)
        assert result == [("Line 1", False), ("Line 2", False)]

    def test_strips_whitespace(self):
        """Test stripping leading/trailing whitespace."""
        lines = ["  Line with spaces  ", "\tLine with tabs\t"]
        result = format_body(lines)
        assert result == [
            ("Line with spaces", False),
            ("Line with tabs", False),
        ]

    def test_blank_line_preserved(self):
        """Test blank lines are preserved."""
        lines = ["Line 1", "", "Line 2"]
        result = format_body(lines)
        assert result == [
            ("Line 1", False),
            ("", False),
            ("Line 2", False),
        ]

    def test_consecutive_blank_lines_collapsed(self):
        """Test consecutive blank lines are collapsed to one."""
        lines = ["Line 1", "", "", "", "Line 2"]
        result = format_body(lines)
        assert result == [
            ("Line 1", False),
            ("", False),
            ("Line 2", False),
        ]

    def test_whitespace_only_lines_treated_as_blank(self):
        """Test lines with only whitespace are treated as blank."""
        lines = ["Line 1", "   ", "\t", "Line 2"]
        result = format_body(lines)
        assert result == [
            ("Line 1", False),
            ("", False),
            ("Line 2", False),
        ]

    def test_soft_break_preserved_after_stripping(self):
        """Test soft break backslash is preserved."""
        lines = ["Line with trailing spaces and break  \\  "]
        result = format_body(lines)
        # The backslash should be kept, but trailing spaces after it are stripped
        assert len(result) == 1
        assert result[0][1] is True  # is_soft_break=True
        assert result[0][0].endswith("\\")

    def test_empty_input(self):
        """Test empty input list."""
        lines = []
        result = format_body(lines)
        assert result == []

    def test_mixed_blank_and_content(self):
        """Test mix of blank lines and content."""
        lines = ["", "Content", "", "", "More content", ""]
        result = format_body(lines)
        # Last blank line is preserved, consecutive middle blanks collapsed
        assert len(result) == 5
        assert result[0] == ("", False)
        assert result[1] == ("Content", False)
        assert result[2] == ("", False)
        assert result[3] == ("More content", False)
        assert result[4] == ("", False)


class TestReflowParagraph:
    """Test reflow_paragraph() function for text wrapping."""

    def test_short_line_unchanged(self):
        """Test short line doesn't need wrapping."""
        paragraph = ["Short line"]
        result = reflow_paragraph(paragraph, width=80)
        assert result == ["Short line"]

    def test_long_line_wrapped(self):
        """Test long line is wrapped to specified width."""
        paragraph = ["This is a very long line that definitely needs to be wrapped"]
        result = reflow_paragraph(paragraph, width=20)
        assert len(result) > 1
        for line in result:
            assert len(line) <= 20

    def test_multiple_lines_joined_and_wrapped(self):
        """Test multiple lines are joined and wrapped."""
        paragraph = ["First part", "Second part", "Third part"]
        result = reflow_paragraph(paragraph, width=20)
        # Should join with spaces and wrap
        full_text = " ".join(result)
        assert "First part" in full_text
        assert "Second part" in full_text
        assert "Third part" in full_text

    def test_width_respected(self):
        """Test all output lines respect width limit."""
        paragraph = ["A" * 100]  # 100 characters
        result = reflow_paragraph(paragraph, width=30)
        for line in result:
            assert len(line) <= 30

    def test_default_width_80(self):
        """Test default width is 80 characters."""
        long_line = "word " * 50  # ~250 characters
        paragraph = [long_line]
        result = reflow_paragraph(paragraph)
        for line in result:
            assert len(line) <= 80

    def test_empty_paragraph(self):
        """Test empty paragraph returns empty list."""
        result = reflow_paragraph([])
        assert result == []

    def test_preserves_word_boundaries(self):
        """Test wrapping preserves word boundaries."""
        paragraph = ["one two three four five six seven eight"]
        result = reflow_paragraph(paragraph, width=15)
        # No word should be split
        for line in result:
            assert not line.startswith(" ")
            assert not line.endswith(" ") or line == ""

    def test_single_long_word(self):
        """Test single word longer than width."""
        # TextWrapper with break_long_words=True (default) will break long words
        paragraph = ["supercalifragilisticexpialidocious"]
        result = reflow_paragraph(paragraph, width=10)
        # Word will be broken into chunks
        assert len(result) > 1
        # Rejoin should give original word
        assert "".join(result) == "supercalifragilisticexpialidocious"


class TestComputeMetrics:
    """Test compute_metrics() function for word count and reading time."""

    def test_single_line(self):
        """Test computing metrics for single line."""
        lines = ["Hello world"]
        wc, rt = compute_metrics(lines)
        assert wc == 2
        assert rt == pytest.approx(2 / 260, abs=0.001)

    def test_multiple_lines(self):
        """Test computing metrics for multiple lines."""
        lines = ["Hello world", "This is a test"]
        wc, rt = compute_metrics(lines)
        assert wc == 6
        assert rt == pytest.approx(6 / 260, abs=0.001)

    def test_excludes_punctuation(self):
        """Test word count excludes punctuation."""
        lines = ["Hello, world! How are you?"]
        wc, rt = compute_metrics(lines)
        # Should count words, not punctuation
        assert wc == 5  # Hello world How are you

    def test_reading_time_calculation(self):
        """Test reading time uses 260 WPM."""
        # 260 words should be ~1 minute
        words = " ".join(["word"] * 260)
        lines = [words]
        wc, rt = compute_metrics(lines)
        assert wc == 260
        assert rt == pytest.approx(1.0, abs=0.01)

    def test_empty_lines(self):
        """Test computing metrics for empty input."""
        lines = []
        wc, rt = compute_metrics(lines)
        assert wc == 0
        assert rt == 0.0

    def test_whitespace_only(self):
        """Test lines with only whitespace."""
        lines = ["   ", "\t\t", "  \n  "]
        wc, rt = compute_metrics(lines)
        assert wc == 0
        assert rt == 0.0

    def test_strips_whitespace_before_counting(self):
        """Test whitespace is stripped before counting."""
        lines = ["  Hello  ", "  world  "]
        wc, rt = compute_metrics(lines)
        assert wc == 2

    def test_realistic_paragraph(self):
        """Test with realistic paragraph."""
        lines = [
            "This is a test paragraph with multiple sentences.",
            "It contains various words and punctuation marks.",
            "The word count should be accurate.",
        ]
        wc, rt = compute_metrics(lines)
        assert wc > 0
        assert wc < 50  # Reasonable range
        assert rt > 0
        assert rt < 1.0  # Should be less than a minute

    def test_numbers_counted_as_words(self):
        """Test numbers are counted as words."""
        lines = ["I have 3 apples and 5 oranges"]
        wc, rt = compute_metrics(lines)
        # lexicon_count counts numbers as words
        assert wc == 7  # I have 3 apples and 5 oranges

    def test_hyphenated_words(self):
        """Test hyphenated words counting."""
        lines = ["This is a well-known fact"]
        wc, rt = compute_metrics(lines)
        # Depends on lexicon_count behavior, but should count reasonably
        assert wc >= 4
        assert wc <= 5
