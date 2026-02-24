#!/usr/bin/env python3
"""
narrative.py
------------
Utility functions for narrative analysis processing.

Provides scene matching, event parsing, and section extraction utilities
for working with narrative analysis files (scenes, events, arcs).

Key Features:
    - Scene title normalization and fuzzy matching
    - Event file parsing and scene-to-event mapping
    - Numbered scene list parsing
    - Arc name formatting
    - Date range constants for core/flashback periods

Usage:
    from dev.utils.narrative import (
        normalize_scene_title,
        fuzzy_match_scene,
        build_scene_event_mapping,
        CORE_RANGE,
        FLASHBACK_RANGE,
    )

    # Build scene mapping for core story
    mapping = build_scene_event_mapping(events_dir, CORE_RANGE)

    # Match a scene title
    event_info = fuzzy_match_scene("The Morning After", mapping["2024-11"])
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ============================================================================
# Date Range Constants
# ============================================================================

CORE_RANGE: Dict[str, List[str]] = {
    "2024": ["11", "12"],
    "2025": ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"],
}
"""Date range for core story entries (November 2024 - December 2025)."""

FLASHBACK_RANGE: Dict[str, List[str]] = {
    "2015": ["08", "09", "10", "11", "12"],
    "2016": ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"],
    "2017": ["01", "02", "06"],
    "2018": ["12"],
    "2019": ["01", "02"],
    "2021": ["08", "09", "10", "11", "12"],
    "2022": ["01", "02", "03", "04", "06", "07", "11"],
    "2023": ["06"],
    "2024": ["01", "02", "03", "04", "05", "06", "07"],
}
"""Date range for flashback entries (2015 - October 2024)."""

CORE_MONTHS: List[str] = [
    "2024-11", "2024-12",
    "2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06",
    "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
]
"""Flat list of core story months in YYYY-MM format."""

FLASHBACK_MONTHS: List[str] = [
    "2015-08", "2015-09", "2015-10", "2015-11", "2015-12",
    "2016-01", "2016-02", "2016-03", "2016-04", "2016-05", "2016-06",
    "2016-07", "2016-08", "2016-09", "2016-10", "2016-11", "2016-12",
    "2017-01", "2017-02", "2017-06",
    "2018-12",
    "2019-01", "2019-02",
    "2021-08", "2021-09", "2021-10", "2021-11", "2021-12",
    "2022-01", "2022-02", "2022-03", "2022-04", "2022-06", "2022-07", "2022-11",
    "2023-06",
    "2024-01", "2024-02", "2024-03", "2024-04", "2024-05", "2024-06", "2024-07",
]
"""Flat list of flashback months in YYYY-MM format."""


# ============================================================================
# Scene Matching Functions
# ============================================================================

def normalize_scene_title(title: str) -> str:
    """
    Normalize a scene title for matching.

    Performs case normalization, removes common variations, and strips
    punctuation to enable fuzzy matching between analysis files and
    event manifests.

    Args:
        title: The scene title to normalize

    Returns:
        Normalized title string suitable for comparison

    Examples:
        >>> normalize_scene_title("**The Morning After**")
        'morning after'
        >>> normalize_scene_title("Clara's Return")
        'claras return'
    """
    # Remove bold markers, extra spaces, lowercase
    normalized = title.replace("**", "").strip().lower()
    # Remove leading "the"
    normalized = re.sub(r"^the\s+", "", normalized)
    # Collapse whitespace
    normalized = re.sub(r"\s+", " ", normalized)
    # Remove punctuation
    normalized = re.sub(r"[''\".,;:!?()]", "", normalized)
    return normalized


def fuzzy_match_scene(
    title: str, scene_map: Dict[str, Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Try to match a scene title with fuzzy matching.

    First tries exact match on normalized title, then attempts:
    - Substring matching (one contains the other)
    - Prefix matching (first few words match)

    Args:
        title: The scene title to match
        scene_map: Dict mapping normalized scene titles to event info

    Returns:
        Event info dict if match found, None otherwise.
        Event info contains: event_name, entries, arcs, original_title

    Examples:
        >>> scene_map = {"morning after": {"event_name": "Event 1: ..."}}
        >>> fuzzy_match_scene("The Morning After", scene_map)
        {"event_name": "Event 1: ...", ...}
    """
    normalized = normalize_scene_title(title)

    # Exact match
    if normalized in scene_map:
        return scene_map[normalized]

    # Try fuzzy matches
    for key, value in scene_map.items():
        # Check if one contains the other
        if normalized in key or key in normalized:
            return value

        # Check first few words match (for abbreviated titles)
        norm_words = normalized.split()[:3]
        key_words = key.split()[:3]
        if norm_words == key_words and len(norm_words) >= 2:
            return value

    return None


# ============================================================================
# Event File Parsing
# ============================================================================

def parse_events_file(file_path: Path) -> Dict[str, Dict[str, Any]]:
    """
    Parse an events file and extract scene-to-event mappings.

    Reads a monthly events manifest file and builds a dictionary mapping
    normalized scene titles to their event information.

    Args:
        file_path: Path to events file (e.g., events_2024-11.md)

    Returns:
        Dict mapping normalized scene titles to event info:
        {
            "scene title": {
                "event_name": "Event 1: The Title",
                "entries": ["2024-11-08", "2024-11-09"],
                "arcs": ["THE_BODY", "WRITING_AS_SURVIVAL"],
                "original_title": "Scene Title"
            }
        }
    """
    content = file_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    scene_to_event: Dict[str, Dict[str, Any]] = {}
    current_event: Optional[str] = None
    current_entries: List[str] = []
    current_arcs: List[str] = []
    in_scenes = False

    for line in lines:
        # Event header
        if line.startswith("## Event"):
            match = re.match(r"## (Event \d+: .+)", line)
            if match:
                current_event = match.group(1)
                current_entries = []
                current_arcs = []
                in_scenes = False

        # Entries line
        elif line.startswith("**Entries**:"):
            entries_text = line.replace("**Entries**:", "").strip()
            current_entries = [e.strip() for e in entries_text.split(",")]

        # Scenes section start
        elif line.startswith("**Scenes**:"):
            in_scenes = True

        # Thematic Arcs line (ends scenes section)
        elif line.startswith("**Thematic Arcs**:"):
            in_scenes = False
            arcs_text = line.replace("**Thematic Arcs**:", "").strip()
            current_arcs = [a.strip() for a in arcs_text.split(",")]

        # Scene line (within scenes section)
        elif in_scenes and line.startswith("- "):
            scene_line = line[2:].strip()
            # Scene format: "Title - Description" or just "Title"
            if " - " in scene_line:
                scene_title = scene_line.split(" - ")[0].strip()
            else:
                scene_title = scene_line

            normalized = normalize_scene_title(scene_title)
            scene_to_event[normalized] = {
                "event_name": current_event,
                "entries": current_entries.copy(),
                "arcs": current_arcs.copy(),
                "original_title": scene_title,
            }

        # Separator between events
        elif line.strip() == "---":
            in_scenes = False

    return scene_to_event


def parse_events_file_full(file_path: Path) -> List[Dict[str, Any]]:
    """
    Parse an events file and return list of complete event records.

    Unlike parse_events_file() which returns scene-indexed data, this
    returns event-indexed data suitable for validation views.

    Args:
        file_path: Path to events file (e.g., events_2024-11.md)

    Returns:
        List of event dicts, each containing:
        {
            "name": "Event 1: The Title",
            "entries": ["2024-11-08"],
            "scenes": ["Scene Title - Description"],
            "arcs": ["THE_BODY"]
        }
    """
    content = file_path.read_text(encoding="utf-8")
    events: List[Dict[str, Any]] = []

    current_event: Optional[str] = None
    current_entries: List[str] = []
    current_scenes: List[str] = []
    current_arcs: List[str] = []
    in_scenes = False

    for line in content.split("\n"):
        if line.startswith("## Event"):
            # Save previous event
            if current_event:
                events.append({
                    "name": current_event,
                    "entries": current_entries,
                    "scenes": current_scenes,
                    "arcs": current_arcs,
                })

            match = re.match(r"## (Event \d+: .+)", line)
            if match:
                current_event = match.group(1)
                current_entries = []
                current_scenes = []
                current_arcs = []
                in_scenes = False

        elif line.startswith("**Entries**:"):
            entries_text = line.replace("**Entries**:", "").strip()
            current_entries = [e.strip() for e in entries_text.split(",")]

        elif line.startswith("**Scenes**:"):
            in_scenes = True

        elif line.startswith("**Thematic Arcs**:"):
            in_scenes = False
            arcs_text = line.replace("**Thematic Arcs**:", "").strip()
            current_arcs = [a.strip() for a in arcs_text.split(",")]

        elif in_scenes and line.startswith("- "):
            current_scenes.append(line[2:].strip())

        elif line.strip() == "---":
            in_scenes = False

    # Don't forget last event
    if current_event:
        events.append({
            "name": current_event,
            "entries": current_entries,
            "scenes": current_scenes,
            "arcs": current_arcs,
        })

    return events


def build_scene_event_mapping(
    events_dir: Path, date_range: Dict[str, List[str]]
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    Build complete mapping of scenes to events for all months in range.

    Iterates through all months in the date range and builds a nested
    dictionary mapping each month's scenes to their event information.

    Args:
        events_dir: Path to _events directory containing monthly manifests
        date_range: Dict of {year: [months]} to process

    Returns:
        Nested dict: {year-month: {normalized_scene_title: event_info}}

    Examples:
        >>> mapping = build_scene_event_mapping(events_dir, CORE_RANGE)
        >>> mapping["2024-11"]["morning after"]["event_name"]
        "Event 1: The First Week"
    """
    mapping: Dict[str, Dict[str, Dict[str, Any]]] = {}

    for year, months in date_range.items():
        for month in months:
            events_file = events_dir / f"events_{year}-{month}.md"
            if events_file.exists():
                mapping[f"{year}-{month}"] = parse_events_file(events_file)
            else:
                mapping[f"{year}-{month}"] = {}

    return mapping


# ============================================================================
# Analysis File Parsing
# ============================================================================

def parse_scenes(scenes_text: str) -> List[Tuple[str, str]]:
    """
    Parse scenes section into list of (title, description) tuples.

    Handles both bold and non-bold scene title formats:
    - "1. **Scene Title** - Description"
    - "1. Scene Title - Description"

    Args:
        scenes_text: Raw text of the Scenes section from an analysis file

    Returns:
        List of (title, description) tuples

    Examples:
        >>> text = "1. **Morning Routine** - Starting the day"
        >>> parse_scenes(text)
        [("Morning Routine", "Starting the day")]
    """
    scenes: List[Tuple[str, str]] = []

    for line in scenes_text.split("\n"):
        # Match numbered scene: "1. **Title** - Description"
        match = re.match(r"\d+\.\s*\*\*(.+?)\*\*\s*[-–—]\s*(.+)", line)
        if match:
            scenes.append((match.group(1).strip(), match.group(2).strip()))
        else:
            # Try without bold: "1. Title - Description"
            match = re.match(r"\d+\.\s*(.+?)\s*[-–—]\s*(.+)", line)
            if match:
                scenes.append((match.group(1).strip(), match.group(2).strip()))

    return scenes


def extract_thematic_arcs(content: str) -> List[str]:
    """
    Extract thematic arcs from an analysis file.

    Finds the "## Thematic Arcs" section and parses the comma-separated
    list of arc names.

    Args:
        content: Full content of an analysis file

    Returns:
        List of arc names (e.g., ["THE_BODY", "WRITING_AS_SURVIVAL"])
    """
    from dev.utils.md import extract_section_text

    arcs_section = extract_section_text(content, "Thematic Arcs")
    if not arcs_section:
        return []
    return [a.strip() for a in arcs_section.split(",") if a.strip()]


# ============================================================================
# Formatting Functions
# ============================================================================

def format_arc(arc: str) -> str:
    """
    Format arc name from UPPERCASE_NAME to Title Case.

    Args:
        arc: Arc name in UPPERCASE_WITH_UNDERSCORES format

    Returns:
        Human-readable title case format

    Examples:
        >>> format_arc("THE_BODY")
        'The Body'
        >>> format_arc("WRITING_AS_SURVIVAL")
        'Writing As Survival'
    """
    return arc.replace("_", " ").title()
