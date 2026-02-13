#!/usr/bin/env python3
"""
test_filters.py
---------------
Tests for wiki template filters.

Covers all pure filter functions: wikilinks, date formatting,
list formatting, timeline tables, source paths, and flexible dates.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date

# --- Third-party imports ---
import pytest

# --- Local imports ---
from dev.wiki.filters import (
    wikilink,
    date_long,
    date_range,
    mid_dot_join,
    adaptive_list,
    timeline_table,
    source_path,
    flexible_date_display,
    thread_date_range,
    chunked_list,
)


# ==================== wikilink ====================

class TestWikilink:
    """Tests for wikilink filter."""

    def test_simple_wikilink(self) -> None:
        """Generate basic wikilink without display text."""
        assert wikilink("Clara Dupont") == "[[Clara Dupont]]"

    def test_wikilink_with_display(self) -> None:
        """Generate wikilink with alternate display text."""
        assert wikilink("Clara Dupont", "Clara") == "[[Clara Dupont|Clara]]"

    def test_wikilink_display_same_as_name(self) -> None:
        """Display text identical to name produces simple wikilink."""
        assert wikilink("Clara", "Clara") == "[[Clara]]"

    def test_wikilink_display_none(self) -> None:
        """Explicit None display produces simple wikilink."""
        assert wikilink("Clara", None) == "[[Clara]]"

    def test_wikilink_empty_string(self) -> None:
        """Empty name still produces wikilink structure."""
        assert wikilink("") == "[[]]"

    def test_wikilink_with_date(self) -> None:
        """Date strings work as wikilink targets."""
        assert wikilink("2024-11-08") == "[[2024-11-08]]"


# ==================== date_long ====================

class TestDateLong:
    """Tests for date_long filter."""

    def test_weekday_format(self) -> None:
        """Produces full day-of-week, month, day, year."""
        d = date(2024, 11, 8)
        result = date_long(d)
        assert result == "Friday, November 8, 2024"

    def test_single_digit_day(self) -> None:
        """Day is not zero-padded."""
        d = date(2024, 1, 5)
        result = date_long(d)
        assert "January 5" in result
        assert "January 05" not in result

    def test_new_years(self) -> None:
        """January 1 renders correctly."""
        d = date(2025, 1, 1)
        result = date_long(d)
        assert result == "Wednesday, January 1, 2025"


# ==================== date_range ====================

class TestDateRange:
    """Tests for date_range filter."""

    def test_different_months(self) -> None:
        """Range spanning months shows both endpoints."""
        start = date(2024, 11, 1)
        end = date(2025, 1, 15)
        assert date_range(start, end) == "Nov 2024 – Jan 2025"

    def test_same_month(self) -> None:
        """Range within same month shows single month."""
        start = date(2024, 11, 1)
        end = date(2024, 11, 30)
        assert date_range(start, end) == "Nov 2024"

    def test_same_day(self) -> None:
        """Same start and end date produces single month."""
        d = date(2024, 11, 8)
        assert date_range(d, d) == "Nov 2024"

    def test_different_years(self) -> None:
        """Range spanning years shows both."""
        start = date(2023, 3, 1)
        end = date(2025, 6, 15)
        assert date_range(start, end) == "Mar 2023 – Jun 2025"


# ==================== mid_dot_join ====================

class TestMidDotJoin:
    """Tests for mid_dot_join filter."""

    def test_multiple_items(self) -> None:
        """Joins items with middle dot."""
        assert mid_dot_join(["A", "B", "C"]) == "A · B · C"

    def test_single_item(self) -> None:
        """Single item returns itself."""
        assert mid_dot_join(["A"]) == "A"

    def test_empty_list(self) -> None:
        """Empty list returns empty string."""
        assert mid_dot_join([]) == ""

    def test_two_items(self) -> None:
        """Two items joined correctly."""
        assert mid_dot_join(["X", "Y"]) == "X · Y"


# ==================== adaptive_list ====================

class TestAdaptiveList:
    """Tests for adaptive_list filter."""

    def test_short_list_inline(self) -> None:
        """Lists at or below threshold render inline."""
        result = adaptive_list(["A", "B", "C"], threshold=4)
        assert result == "A · B · C"

    def test_at_threshold_inline(self) -> None:
        """Exactly at threshold renders inline."""
        result = adaptive_list(["A", "B", "C", "D"], threshold=4)
        assert result == "A · B · C · D"

    def test_above_threshold_bulleted(self) -> None:
        """Lists above threshold render as bulleted markdown."""
        result = adaptive_list(["A", "B", "C", "D", "E"], threshold=4)
        assert result == "- A\n- B\n- C\n- D\n- E"

    def test_empty_list(self) -> None:
        """Empty list returns empty string."""
        assert adaptive_list([]) == ""

    def test_single_item(self) -> None:
        """Single item renders inline."""
        assert adaptive_list(["A"]) == "A"

    def test_default_threshold(self) -> None:
        """Default threshold is 4."""
        result = adaptive_list(["A", "B", "C", "D", "E"])
        assert result.startswith("- ")


# ==================== timeline_table ====================

class TestTimelineTable:
    """Tests for timeline_table filter."""

    def test_basic_table(self) -> None:
        """Generates markdown table with year rows and month columns."""
        counts = {"2024-01": 3, "2024-06": 1, "2024-11": 20}
        result = timeline_table(counts)
        assert "| Year |" in result
        assert "| 2024 |" in result
        assert "**20**" in result  # Peak month bolded
        assert "24" in result  # Total: 3+1+20=24

    def test_multiple_years(self) -> None:
        """Table spans multiple years."""
        counts = {"2023-10": 3, "2024-11": 5}
        result = timeline_table(counts)
        assert "2023" in result
        assert "2024" in result

    def test_empty_counts(self) -> None:
        """Empty dict returns empty string."""
        assert timeline_table({}) == ""

    def test_zero_months_show_dash(self) -> None:
        """Months with no entries show dash."""
        counts = {"2024-06": 1}
        result = timeline_table(counts)
        assert "—" in result

    def test_single_entry_not_bolded(self) -> None:
        """Single-entry peak is not bolded (max_count must be > 1)."""
        counts = {"2024-06": 1}
        result = timeline_table(counts)
        assert "**1**" not in result

    def test_header_has_month_abbreviations(self) -> None:
        """Header row contains month abbreviations."""
        counts = {"2024-01": 1}
        result = timeline_table(counts)
        assert "Jan" in result
        assert "Dec" in result


# ==================== source_path ====================

class TestSourcePath:
    """Tests for source_path filter."""

    def test_journal_md_path(self) -> None:
        """Generates relative path to journal markdown."""
        result = source_path("journal_md", "2024-11-08")
        assert result == "../../../journal/content/md/2024/2024-11-08.md"

    def test_metadata_yaml_path(self) -> None:
        """Generates relative path to metadata YAML."""
        result = source_path("metadata_yaml", "2024-11-08")
        assert result == "../../../metadata/journal/2024/2024-11-08.yaml"

    def test_unknown_type(self) -> None:
        """Unknown entity type returns empty string."""
        assert source_path("unknown", "anything") == ""


# ==================== flexible_date_display ====================

class TestFlexibleDateDisplay:
    """Tests for flexible_date_display filter."""

    def test_full_date(self) -> None:
        """YYYY-MM-DD format displays as 'Mon D, YYYY'."""
        result = flexible_date_display("2024-11-08")
        assert result == "Nov 8, 2024"

    def test_month_year(self) -> None:
        """YYYY-MM format displays as 'Mon YYYY'."""
        result = flexible_date_display("2024-11")
        assert result == "Nov 2024"

    def test_year_only(self) -> None:
        """YYYY format displays as year."""
        result = flexible_date_display("2024")
        assert result == "2024"

    def test_approximate_date(self) -> None:
        """Approximate prefix preserved in output."""
        result = flexible_date_display("~2024-11")
        assert result == "~Nov 2024"

    def test_approximate_full_date(self) -> None:
        """Approximate full date."""
        result = flexible_date_display("~2024-11-08")
        assert result == "~Nov 8, 2024"


# ==================== thread_date_range ====================

class TestThreadDateRange:
    """Tests for thread_date_range filter."""

    def test_full_to_month(self) -> None:
        """Full date to month-only format."""
        result = thread_date_range("2024-11-08", "2024-12")
        assert result == "Nov 8, 2024 → Dec 2024"

    def test_full_to_year(self) -> None:
        """Full date to year-only format."""
        result = thread_date_range("2024-11-08", "2015")
        assert result == "Nov 8, 2024 → 2015"

    def test_month_to_month(self) -> None:
        """Month to month format."""
        result = thread_date_range("2024-11", "2025-03")
        assert result == "Nov 2024 → Mar 2025"


# ==================== chunked_list ====================

class TestChunkedList:
    """Tests for chunked_list filter."""

    def test_exact_chunks(self) -> None:
        """List evenly divisible by chunk size."""
        result = chunked_list(["A", "B", "C", "D", "E", "F"], 3)
        assert result == [["A", "B", "C"], ["D", "E", "F"]]

    def test_remainder_chunk(self) -> None:
        """Last chunk can be smaller than chunk_size."""
        result = chunked_list(["A", "B", "C", "D", "E"], 3)
        assert result == [["A", "B", "C"], ["D", "E"]]

    def test_empty_list(self) -> None:
        """Empty list returns empty list."""
        assert chunked_list([]) == []

    def test_single_item(self) -> None:
        """Single item in one chunk."""
        assert chunked_list(["A"]) == [["A"]]

    def test_default_chunk_size(self) -> None:
        """Default chunk size is 3."""
        result = chunked_list(["A", "B", "C", "D"])
        assert result == [["A", "B", "C"], ["D"]]
