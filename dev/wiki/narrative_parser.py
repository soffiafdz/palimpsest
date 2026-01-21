#!/usr/bin/env python3
"""
narrative_parser.py
-------------------
Parse narrative analysis manifests for wiki generation.

Reads scene/event/arc data from markdown manifests in the narrative_analysis
directory. This data is used by the wiki generator to create arc-based
navigation pages, event pages with scenes, and cross-reference views.

The manifests are the source of truth for:
- Scenes (granular narrative moments)
- Events (chapter-like groupings)
- Arcs (overarching storylines)

Key Features:
    - Parse event manifests from _events/*.md
    - Parse arc manifest from _arcs/arcs_manifest.md
    - Build cross-reference indices (entry→scenes, event→entries, arc→events)
    - Provide structured data for wiki templates

Usage:
    from dev.wiki.narrative_parser import NarrativeParser

    parser = NarrativeParser(analysis_dir)
    arcs = parser.get_arcs()
    events = parser.get_events()
    scenes_for_entry = parser.get_scenes_for_entry("2024-11-08")
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

# --- Local imports ---
from dev.core.paths import JOURNAL_DIR

ANALYSIS_DIR = JOURNAL_DIR / "narrative_analysis"


@dataclass
class Scene:
    """A granular narrative moment within an entry."""

    title: str
    description: str
    entry_date: date
    event_name: Optional[str] = None

    @property
    def slug(self) -> str:
        """URL-safe slug for the scene."""
        return re.sub(r"[^a-z0-9]+", "-", self.title.lower()).strip("-")


@dataclass
class NarrativeEvent:
    """
    A chapter-like grouping of related scenes.

    Note: Named NarrativeEvent to distinguish from database Event model.
    """

    name: str
    batch_label: str
    entries: List[str]  # Entry dates as strings
    scenes: List[Scene] = field(default_factory=list)
    arc_name: Optional[str] = None

    @property
    def slug(self) -> str:
        """URL-safe slug for the event."""
        return re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")

    @property
    def entry_dates(self) -> List[date]:
        """Parse entry strings to date objects."""
        dates = []
        for entry in self.entries:
            try:
                dates.append(date.fromisoformat(entry.strip()))
            except ValueError:
                continue
        return sorted(dates)

    @property
    def date_range(self) -> Optional[str]:
        """Format date range for display."""
        dates = self.entry_dates
        if not dates:
            return None
        if len(dates) == 1:
            return dates[0].isoformat()
        return f"{dates[0].isoformat()} to {dates[-1].isoformat()}"


@dataclass
class NarrativeArc:
    """An overarching storyline spanning multiple events."""

    name: str
    theme: str
    timespan: str
    events: List[str]  # Event names
    summary: str = ""

    @property
    def slug(self) -> str:
        """URL-safe slug for the arc."""
        return re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")


class NarrativeParser:
    """
    Parse narrative analysis manifests for wiki generation.

    Reads event and arc manifests from the narrative_analysis directory
    and provides structured data for wiki templates.

    Attributes:
        analysis_dir: Path to narrative_analysis directory
        _events: Cached parsed events
        _arcs: Cached parsed arcs
        _scenes_by_entry: Index of scenes by entry date
        _events_by_entry: Index of events by entry date
    """

    def __init__(self, analysis_dir: Optional[Path] = None):
        """
        Initialize the narrative parser.

        Args:
            analysis_dir: Path to narrative_analysis directory.
                         Defaults to JOURNAL_DIR/narrative_analysis.
        """
        self.analysis_dir = analysis_dir or ANALYSIS_DIR
        self._events: Optional[List[NarrativeEvent]] = None
        self._arcs: Optional[List[NarrativeArc]] = None
        self._scenes_by_entry: Optional[Dict[str, List[Scene]]] = None
        self._events_by_entry: Optional[Dict[str, List[NarrativeEvent]]] = None

    @property
    def events_dir(self) -> Path:
        """Path to _events directory."""
        return self.analysis_dir / "_events"

    @property
    def arcs_dir(self) -> Path:
        """Path to _arcs directory."""
        return self.analysis_dir / "_arcs"

    def parse_event_file(self, filepath: Path) -> List[NarrativeEvent]:
        """
        Parse a single event manifest file.

        Args:
            filepath: Path to event manifest file

        Returns:
            List of NarrativeEvent objects
        """
        content = filepath.read_text()
        events = []

        # Extract batch label from filename
        stem = filepath.stem.replace("events_", "")
        parts = stem.split("_")
        if len(parts) == 3:  # e.g., nov_dec_2024
            batch_label = f"{parts[0].title()}-{parts[1].title()} {parts[2]}"
        elif len(parts) == 2:  # e.g., mar_2025
            batch_label = f"{parts[0].title()} {parts[1]}"
        else:
            batch_label = stem

        # Parse events using regex
        event_pattern = re.compile(
            r"## Event \d+: (.+?)\n"
            r"\*\*Entries\*\*: ([^\n]+)\n"
            r"\*\*Scenes\*\*:\n((?:- .+\n)*)",
            re.MULTILINE
        )

        for match in event_pattern.finditer(content):
            event_name = match.group(1).strip()
            entries_str = match.group(2).strip()
            scenes_block = match.group(3)

            # Parse entries
            entries = [e.strip() for e in entries_str.split(",")]

            # Parse scenes
            scenes = []
            for line in scenes_block.strip().split("\n"):
                if line.startswith("- "):
                    # Format: "- Scene Title - Description"
                    scene_text = line[2:].strip()
                    if " - " in scene_text:
                        scene_title, scene_desc = scene_text.split(" - ", 1)
                    else:
                        scene_title = scene_text
                        scene_desc = ""

                    # Try to extract entry date from scene title or use first entry
                    entry_date_str = entries[0] if entries else None
                    try:
                        entry_date = date.fromisoformat(entry_date_str) if entry_date_str else None
                    except ValueError:
                        entry_date = None

                    if entry_date:
                        scenes.append(Scene(
                            title=scene_title.strip(),
                            description=scene_desc.strip(),
                            entry_date=entry_date,
                            event_name=event_name,
                        ))

            events.append(NarrativeEvent(
                name=event_name,
                batch_label=batch_label,
                entries=entries,
                scenes=scenes,
            ))

        return events

    def get_events(self, force_reload: bool = False) -> List[NarrativeEvent]:
        """
        Get all events from event manifest files.

        Args:
            force_reload: Force re-parsing of manifest files

        Returns:
            List of all NarrativeEvent objects
        """
        if self._events is not None and not force_reload:
            return self._events

        self._events = []

        if not self.events_dir.exists():
            return self._events

        # Process files in chronological order
        batch_order = [
            "events_nov_dec_2024.md",
            "events_jan_feb_2025.md",
            "events_mar_2025.md",
            "events_apr_2025.md",
            "events_may_2025.md",
            "events_jun_jul_2025.md",
            "events_aug_dec_2025.md",
        ]

        for filename in batch_order:
            filepath = self.events_dir / filename
            if filepath.exists():
                self._events.extend(self.parse_event_file(filepath))

        return self._events

    def parse_arcs_file(self) -> List[NarrativeArc]:
        """
        Parse the arcs manifest file.

        Returns:
            List of NarrativeArc objects
        """
        arcs_file = self.arcs_dir / "arcs_manifest.md"
        if not arcs_file.exists():
            return []

        content = arcs_file.read_text()
        arcs = []

        # Split content by arc headers
        arc_sections = re.split(r"\n---\n+", content)

        for section in arc_sections:
            # Check if this section contains an arc
            header_match = re.search(r"## Arc \d+: (.+)", section)
            if not header_match:
                continue

            arc_name = header_match.group(1).strip()

            # Extract theme
            theme_match = re.search(r"\*\*Theme\*\*: ([^\n]+)", section)
            theme = theme_match.group(1).strip() if theme_match else ""

            # Extract timespan
            timespan_match = re.search(r"\*\*Timespan\*\*: ([^\n]+)", section)
            timespan = timespan_match.group(1).strip() if timespan_match else ""

            # Extract events block
            events_match = re.search(
                r"\*\*Events\*\*:\n((?:\d+\. .+\n)+)",
                section
            )
            event_names = []
            if events_match:
                events_block = events_match.group(1)
                for line in events_block.strip().split("\n"):
                    # Format: "1. Event Name (Batch)" or "1. Event Name (Batch) - note"
                    event_match = re.match(r"\d+\.\s+(.+?)\s*\(", line)
                    if event_match:
                        event_names.append(event_match.group(1).strip())

            # Extract summary
            summary_match = re.search(
                r"\*\*Arc Summary\*\*: (.+?)(?=\n\n|\Z)",
                section,
                re.DOTALL
            )
            summary = summary_match.group(1).strip() if summary_match else ""

            arcs.append(NarrativeArc(
                name=arc_name,
                theme=theme,
                timespan=timespan,
                events=event_names,
                summary=summary,
            ))

        return arcs

    def get_arcs(self, force_reload: bool = False) -> List[NarrativeArc]:
        """
        Get all arcs from the arcs manifest.

        Args:
            force_reload: Force re-parsing of manifest file

        Returns:
            List of all NarrativeArc objects
        """
        if self._arcs is not None and not force_reload:
            return self._arcs

        self._arcs = self.parse_arcs_file()

        # Link events to arcs
        events = self.get_events()
        event_lookup = {e.name: e for e in events}

        for arc in self._arcs:
            for event_name in arc.events:
                if event_name in event_lookup:
                    event_lookup[event_name].arc_name = arc.name

        return self._arcs

    def build_entry_index(self) -> None:
        """Build index of scenes and events by entry date."""
        self._scenes_by_entry = {}
        self._events_by_entry = {}

        events = self.get_events()

        for event in events:
            for entry_str in event.entries:
                entry_str = entry_str.strip()
                if entry_str not in self._events_by_entry:
                    self._events_by_entry[entry_str] = []
                self._events_by_entry[entry_str].append(event)

            for scene in event.scenes:
                entry_key = scene.entry_date.isoformat()
                if entry_key not in self._scenes_by_entry:
                    self._scenes_by_entry[entry_key] = []
                self._scenes_by_entry[entry_key].append(scene)

    def get_scenes_for_entry(self, entry_date: str) -> List[Scene]:
        """
        Get all scenes for a specific entry date.

        Args:
            entry_date: Entry date as ISO string (YYYY-MM-DD)

        Returns:
            List of Scene objects for this entry
        """
        if self._scenes_by_entry is None:
            self.build_entry_index()
        return self._scenes_by_entry.get(entry_date, [])

    def get_events_for_entry(self, entry_date: str) -> List[NarrativeEvent]:
        """
        Get all events that include a specific entry date.

        Args:
            entry_date: Entry date as ISO string (YYYY-MM-DD)

        Returns:
            List of NarrativeEvent objects that include this entry
        """
        if self._events_by_entry is None:
            self.build_entry_index()
        return self._events_by_entry.get(entry_date, [])

    def get_arc_for_event(self, event_name: str) -> Optional[NarrativeArc]:
        """
        Get the arc that contains a specific event.

        Args:
            event_name: Name of the event

        Returns:
            NarrativeArc that contains this event, or None
        """
        arcs = self.get_arcs()
        for arc in arcs:
            if event_name in arc.events:
                return arc
        return None

    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about the narrative structure.

        Returns:
            Dictionary with counts of arcs, events, scenes
        """
        arcs = self.get_arcs()
        events = self.get_events()
        scenes = sum(len(e.scenes) for e in events)
        entries = set()
        for event in events:
            entries.update(event.entries)

        return {
            "arcs": len(arcs),
            "events": len(events),
            "scenes": scenes,
            "entries": len(entries),
        }
