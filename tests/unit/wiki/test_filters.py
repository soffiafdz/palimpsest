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
from typing import Dict, Optional

# --- Third-party imports ---
import pytest
from jinja2 import Environment

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

def _make_env(targets: Optional[Dict[str, str]] = None) -> Environment:
    """Create a Jinja2 Environment with optional wikilink targets."""
    env = Environment()
    if targets is not None:
        env.globals["_wikilink_targets"] = targets
    return env


class TestWikilink:
    """Tests for wikilink filter."""

    def test_simple_wikilink_no_targets(self) -> None:
        """Name not in lookup falls back to WikiLink1 fallback."""
        env = _make_env()
        assert wikilink(env, "Marguerite Duras") == "[Marguerite Duras][]"

    def test_wikilink_resolved_via_lookup(self) -> None:
        """Name found in lookup produces WikiLink1 with absolute path."""
        targets = {"Marguerite Duras": "/journal/people/marguerite_duras"}
        env = _make_env(targets)
        result = wikilink(env, "Marguerite Duras")
        assert result == "[Marguerite Duras][/journal/people/marguerite_duras]"

    def test_wikilink_with_display_and_lookup(self) -> None:
        """Resolved target uses custom display text."""
        targets = {"Marguerite Duras": "/journal/people/marguerite_duras"}
        env = _make_env(targets)
        result = wikilink(env, "Marguerite Duras", "Marguerite")
        assert result == "[Marguerite][/journal/people/marguerite_duras]"

    def test_wikilink_display_fallback_no_match(self) -> None:
        """Unresolved name with display text still falls back."""
        env = _make_env({})
        result = wikilink(env, "Unknown Person")
        assert result == "[Unknown Person][]"

    def test_wikilink_empty_string(self) -> None:
        """Empty name still produces WikiLink1 structure."""
        env = _make_env()
        assert wikilink(env, "") == "[][]"

    def test_wikilink_with_date_resolved(self) -> None:
        """Date strings resolved via lookup produce WikiLink1."""
        targets = {"2024-11-08": "/journal/entries/2024/2024-11-08"}
        env = _make_env(targets)
        result = wikilink(env, "2024-11-08")
        assert result == "[2024-11-08][/journal/entries/2024/2024-11-08]"

    def test_wikilink_with_date_unresolved(self) -> None:
        """Date strings not in lookup fall back to WikiLink1 fallback."""
        env = _make_env()
        assert wikilink(env, "2024-11-08") == "[2024-11-08][]"

    def test_wikilink_none_targets_dict(self) -> None:
        """Environment without _wikilink_targets key falls back."""
        env = Environment()
        assert wikilink(env, "Some Name") == "[Some Name][]"

    def test_wikilink_via_template(self) -> None:
        """Wikilink filter works correctly when called from a template."""
        env = Environment()
        env.filters["wikilink"] = wikilink
        targets = {"René Descartes": "/journal/people/rene_descartes"}
        env.globals["_wikilink_targets"] = targets
        tmpl = env.from_string('{{ name | wikilink }}')
        result = tmpl.render(name="René Descartes")
        assert result == "[René Descartes][/journal/people/rene_descartes]"

    def test_wikilink_via_template_fallback(self) -> None:
        """Unresolved name in template falls back to WikiLink1."""
        env = Environment()
        env.filters["wikilink"] = wikilink
        env.globals["_wikilink_targets"] = {}
        tmpl = env.from_string('{{ name | wikilink }}')
        result = tmpl.render(name="Unknown")
        assert result == "[Unknown][]"


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
        assert " 20 " in result  # Peak month present (no bold)
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

    P = "{{PROJECT_ROOT}}"

    def test_journal_md_path(self) -> None:
        """Generates file: path with PROJECT_ROOT placeholder."""
        result = source_path("journal_md", "2024-11-08")
        assert result == f"file:{self.P}/data/journal/content/md/2024/2024-11-08.md"

    def test_metadata_yaml_path(self) -> None:
        """Generates file: path with PROJECT_ROOT placeholder."""
        result = source_path("metadata_yaml", "2024-11-08")
        assert result == f"file:{self.P}/data/metadata/journal/2024/2024-11-08.yaml"

    def test_unknown_type(self) -> None:
        """Unknown entity type returns empty string."""
        assert source_path("unknown", "anything") == ""

    def test_person_yaml_path(self) -> None:
        """Generates file: path with PROJECT_ROOT placeholder."""
        result = source_path("person_yaml", "clara_dupont")
        assert result == f"file:{self.P}/data/metadata/people/clara_dupont.yaml"

    def test_location_yaml_path(self) -> None:
        """Generates file: path with PROJECT_ROOT placeholder."""
        result = source_path("location_yaml", "montreal/cafe-olimpico")
        assert result == f"file:{self.P}/data/metadata/locations/montreal/cafe-olimpico.yaml"

    def test_city_yaml_path(self) -> None:
        """Generates file: path with PROJECT_ROOT placeholder."""
        result = source_path("city_yaml", "")
        assert result == f"file:{self.P}/data/metadata/cities.yaml"

    def test_arc_yaml_path(self) -> None:
        """Generates file: path with PROJECT_ROOT placeholder."""
        result = source_path("arc_yaml", "")
        assert result == f"file:{self.P}/data/metadata/arcs.yaml"

    def test_chapter_yaml_path(self) -> None:
        """Generates file: path with PROJECT_ROOT placeholder."""
        result = source_path("chapter_yaml", "the-beginning")
        assert result == f"file:{self.P}/data/metadata/manuscript/chapters/the-beginning.yaml"

    def test_character_yaml_path(self) -> None:
        """Generates file: path with PROJECT_ROOT placeholder."""
        result = source_path("character_yaml", "protagonist")
        assert result == f"file:{self.P}/data/metadata/manuscript/characters/protagonist.yaml"

    def test_scene_yaml_path(self) -> None:
        """Generates file: path with PROJECT_ROOT placeholder."""
        result = source_path("scene_yaml", "opening-scene")
        assert result == f"file:{self.P}/data/metadata/manuscript/scenes/opening-scene.yaml"

    def test_neighborhoods_yaml_path(self) -> None:
        """Generates file: path with PROJECT_ROOT placeholder."""
        result = source_path("neighborhoods_yaml", "")
        assert result == f"file:{self.P}/data/metadata/neighborhoods.yaml"

    def test_relation_types_yaml_path(self) -> None:
        """Generates file: path with PROJECT_ROOT placeholder."""
        result = source_path("relation_types_yaml", "")
        assert result == f"file:{self.P}/data/metadata/relation_types.yaml"


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
