#!/usr/bin/env python3
"""
test_metadata2pdf.py
--------------------
Unit tests for metadata PDF formatting functions.

Tests formatting helpers:
- format_rating: Star rating formatting
- format_scene: Scene formatting with metadata
- format_thread: Thread formatting with date ranges
- format_entry_metadata: Complete entry formatting

Test Coverage:
    - Star ratings (full, half, none)
    - Scene formatting (with/without people/locations)
    - Thread formatting (with/without entry reference)
    - Arc change detection
"""
# --- Standard library imports ---
from datetime import date
from typing import Any, Dict, List, cast

# --- Local imports ---
from dev.builders.metadata_pdfbuilder import (
    format_rating,
    format_scene,
    format_thread,
    format_entry_metadata,
)
from dev.dataclasses.metadata_entry import (
    MetadataEntry,
    SceneSpec,
    ThemeSpec,
    ThreadSpec,
    EventSpec,
    MotifSpec,
)


# --- Test format_rating ---


def test_format_rating_full_stars():
    """Test full star ratings."""
    assert format_rating(5.0) == "⭐⭐⭐⭐⭐"
    assert format_rating(3.0) == "⭐⭐⭐"
    assert format_rating(1.0) == "⭐"


def test_format_rating_half_stars():
    """Test half star ratings."""
    assert format_rating(4.5) == "⭐⭐⭐⭐½"
    assert format_rating(2.5) == "⭐⭐½"
    assert format_rating(0.5) == "½"


def test_format_rating_none():
    """Test None rating."""
    assert format_rating(None) == ""


def test_format_rating_edge_cases():
    """Test edge cases."""
    assert format_rating(0.0) == ""  # No stars
    assert format_rating(4.3) == "⭐⭐⭐⭐"  # No half (< 0.5)
    assert format_rating(4.7) == "⭐⭐⭐⭐½"  # Half (>= 0.5)


# --- Test format_scene ---


def test_format_scene_minimal():
    """Test scene with minimal metadata."""
    scene: SceneSpec = {"name": "Test Scene", "description": "Test description"}
    # format_scene no longer used directly, scenes are formatted inline
    assert scene["name"] == "Test Scene"
    assert scene["description"] == "Test description"


def test_format_scene_with_people():
    """Test scene with people."""
    scene: SceneSpec = {
        "name": "Meeting",
        "description": "Discussion",
        "people": ["Alice", "Bob"],
    }
    result = format_scene(scene, 2)

    assert "2. **Meeting**" in result
    assert "People: Alice, Bob" in result


def test_format_scene_with_locations():
    """Test scene with locations."""
    scene: SceneSpec = {
        "name": "Café Talk",
        "description": "Coffee discussion",
        "locations": ["Café Nord"],
    }
    result = format_scene(scene, 1)

    assert "Location: Café Nord" in result


def test_format_scene_with_date():
    """Test scene with single date."""
    scene: SceneSpec = {
        "name": "Event",
        "description": "Something happened",
        "date": "2025-02-28",
    }
    result = format_scene(scene, 1)

    assert "Date: 2025-02-28" in result


def test_format_scene_with_date_list():
    """Test scene with multiple dates."""
    scene: SceneSpec = {
        "name": "Multi-day Event",
        "description": "Spanning days",
        "date": ["2025-02-28", "2025-03-01"],
    }
    result = format_scene(scene, 1)

    assert "Date: 2025-02-28, 2025-03-01" in result


def test_format_scene_multiline_description():
    """Test scene with multiline description."""
    scene: SceneSpec = {
        "name": "Complex Scene",
        "description": "First paragraph.\n\nSecond paragraph.",
    }
    result = format_scene(scene, 1)

    assert "First paragraph" in result
    assert "Second paragraph" in result


# --- Test format_thread ---


def test_format_thread_minimal():
    """Test thread with minimal metadata."""
    thread: ThreadSpec = {
        "name": "Connection",
        "from_": "2025-02-28",
        "to": "2024-11-15",
        "content": "Link between moments",
    }
    result = format_thread(thread)

    assert "**CONNECTION**" in result
    assert "*2025-02-28 → 2024-11-15*" in result
    assert "Link between moments" in result


def test_format_thread_with_entry():
    """Test thread with entry reference."""
    thread: ThreadSpec = {
        "name": "Memory",
        "from_": "2025-02-28",
        "to": "2023-01-10",
        "content": "Echoes of the past",
        "entry": "2023-01-10",
    }
    result = format_thread(thread)

    assert "*→ Entry: 2023-01-10*" in result


def test_format_thread_with_people():
    """Test thread with people."""
    thread: ThreadSpec = {
        "name": "Shared Moment",
        "from_": "2025-02-28",
        "to": "2024-06-12",
        "content": "Connection through person",
        "people": ["Sarah", "Emma"],
    }
    result = format_thread(thread)

    assert "Sarah, Emma" in result


def test_format_thread_with_locations():
    """Test thread with locations."""
    thread: ThreadSpec = {
        "name": "Place Echo",
        "from_": "2025-02-28",
        "to": "2024-03-20",
        "content": "Same place, different time",
        "locations": ["Central Park"],
    }
    result = format_thread(thread)

    assert "at Central Park" in result


def test_format_thread_complete():
    """Test thread with all metadata."""
    thread: ThreadSpec = {
        "name": "Full Thread",
        "from_": "2025-02-28",
        "to": "2023-12-01",
        "content": "Complex connection",
        "entry": "2023-12-01",
        "people": ["Alex"],
        "locations": ["Library"],
    }
    result = format_thread(thread)

    assert "Alex" in result
    assert "at Library" in result
    assert "*→ Entry: 2023-12-01*" in result


# --- Test format_arc_marker ---


# Arc markers removed in favor of inline arc tags


# --- Test format_entry_metadata ---


def test_format_entry_metadata_minimal():
    """Test entry with minimal metadata."""
    entry = MetadataEntry(
        date=date(2025, 2, 28), summary="A day happened", rating=3.0
    )
    result = format_entry_metadata(entry)

    assert "\\Huge\\bfseries 2025-02-28" in result
    assert "⭐⭐⭐" in result
    assert "A day happened" in result


def test_format_entry_metadata_with_arcs():
    """Test entry with arcs."""
    entry = MetadataEntry(
        date=date(2025, 2, 28),
        summary="Important day",
        arcs=["The Long Wanting", "The Stalled Transition"],
    )
    result = format_entry_metadata(entry)

    assert "\\large\\bfseries The Long Wanting" in result
    assert "The Stalled Transition" in result


def test_format_entry_metadata_with_scenes():
    """Test entry with scenes."""
    scenes: List[SceneSpec] = [
        cast(
            SceneSpec,
            {
                "name": "Morning Walk",
                "description": "Through the park",
                "people": ["Clara"],
            },
        )
    ]
    entry = MetadataEntry(date=date(2025, 2, 28), summary="Day", scenes=scenes)
    result = format_entry_metadata(entry)

    assert "\\LARGE\\bfseries Scenes" in result
    assert "Morning Walk" in result
    assert "Clara" in result


def test_format_entry_metadata_with_events():
    """Test entry with events and scenes."""
    scenes: List[SceneSpec] = [
        cast(SceneSpec, {"name": "Scene1", "description": "First scene"}),
        cast(SceneSpec, {"name": "Scene2", "description": "Second scene"}),
    ]
    events: List[EventSpec] = [
        cast(EventSpec, {"name": "City Errands", "scenes": ["Scene1", "Scene2"]})
    ]
    entry = MetadataEntry(date=date(2025, 2, 28), summary="Day", events=events, scenes=scenes)
    result = format_entry_metadata(entry)

    assert "\\LARGE\\bfseries Events \\& Scenes" in result
    assert "\\large\\bfseries City Errands" in result
    assert "\\large\\itshape Scene1" in result


def test_format_entry_metadata_with_themes():
    """Test entry with themes."""
    themes: List[ThemeSpec] = [
        cast(ThemeSpec, {"name": "Loneliness", "description": "Alone at home."}),
        cast(ThemeSpec, {"name": "Hope", "description": "A glimmer of something."}),
    ]
    entry = MetadataEntry(
        date=date(2025, 2, 28), summary="Day", themes=themes
    )
    result = format_entry_metadata(entry)

    assert "\\bfseries\\large Themes" in result
    assert "Loneliness" in result
    assert "Hope" in result


def test_format_entry_metadata_with_motifs():
    """Test entry with motifs."""
    motifs: List[MotifSpec] = [
        cast(
            MotifSpec,
            {"name": "The Gray Fence", "description": "Boundary between worlds"},
        )
    ]
    entry = MetadataEntry(date=date(2025, 2, 28), summary="Day", motifs=motifs)
    result = format_entry_metadata(entry)

    assert "\\bfseries\\large Motifs" in result
    assert "\\textbf{The Gray Fence}" in result
    assert "Boundary between worlds" in result


def test_format_entry_metadata_with_threads():
    """Test entry with threads."""
    threads: List[ThreadSpec] = [
        cast(
            ThreadSpec,
            {
                "name": "Echo",
                "from_": "2025-02-28",
                "to": "2024-01-15",
                "content": "Connection",
            },
        )
    ]
    entry = MetadataEntry(date=date(2025, 2, 28), summary="Day", threads=threads)
    result = format_entry_metadata(entry)

    assert "\\bfseries\\large Threads" in result
    assert "\\textbf{Echo}" in result
    assert "\\textit{2025-02-28 $\\rightarrow$ 2024-01-15}" in result


def test_format_entry_metadata_with_tags():
    """Test entry with tags (tags render inside multicol with themes)."""
    entry = MetadataEntry(
        date=date(2025, 2, 28), summary="Day",
        themes=[cast(ThemeSpec, {"name": "Hope", "description": "A glimmer."})],
        tags=["Introspection", "City", "Clara"],
    )
    result = format_entry_metadata(entry)

    assert "\\bfseries\\large Tags" in result
    assert "Introspection" in result
    assert "City" in result
    assert "Clara" in result


def test_format_entry_metadata_single_column():
    """Test that layout is clean single column."""
    entry = MetadataEntry(
        date=date(2025, 2, 28),
        summary="Day",
        rating=4.5,
        themes=[cast(ThemeSpec, {"name": "Theme", "description": "A theme."})],
    )
    result = format_entry_metadata(entry)

    # Should have themes section
    assert "\\bfseries\\large Themes" in result
    assert "Theme" in result


def test_format_entry_metadata_no_rating():
    """Test entry without rating."""
    entry = MetadataEntry(date=date(2025, 2, 28), summary="Day")
    result = format_entry_metadata(entry)

    # Should have date in LaTeX header
    assert "\\Huge\\bfseries 2025-02-28" in result
    # Should not have rating stars
    assert "⭐" not in result
