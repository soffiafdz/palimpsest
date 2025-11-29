#!/usr/bin/env python3
"""
manuscript_arc.py
-----------------
Dataclass for manuscript story arc wiki pages.

Represents narrative arcs that group related events and entries in the manuscript.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from dev.dataclasses.wiki_entity import WikiEntity
from dev.utils.md import relative_link


@dataclass
class Arc(WikiEntity):
    """
    Represents a story arc in the manuscript.

    A narrative arc groups related events and entries, providing
    structure to the manuscript narrative.

    Attributes:
        path: Path to arc wiki file (wiki/manuscript/arcs/arc.md)
        wiki_dir: Wiki root directory for breadcrumb generation
        name: Arc name/identifier
        description: Description of the arc's narrative purpose

        # Relationships
        events: List of manuscript events in this arc
        entries: List of manuscript entries in this arc
        characters: List of characters prominent in this arc
        themes: List of themes explored in this arc

        # Timeline
        date_range_start: First entry date in arc
        date_range_end: Last entry date in arc

        # Statistics
        total_entries: Number of entries in arc
        total_events: Number of events in arc
        completion_percentage: Estimated completion (0-100)

        # Notes
        notes: Editorial notes about this arc
    """

    path: Path
    wiki_dir: Path
    name: str
    description: Optional[str] = None

    # Relationships
    events: List[Dict[str, Any]] = field(default_factory=list)
    entries: List[Dict[str, Any]] = field(default_factory=list)
    characters: List[Dict[str, Any]] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)

    # Timeline
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None

    # Statistics
    total_entries: int = 0
    total_events: int = 0
    completion_percentage: int = 0

    # Notes
    notes: Optional[str] = None

    @classmethod
    def from_database(
        cls,
        db_arc: Any,
        wiki_dir: Path,
        journal_dir: Path,
    ) -> "Arc":
        """
        Create Arc from database model.

        Args:
            db_arc: Arc database model
            wiki_dir: Wiki root directory
            journal_dir: Journal directory (unused but kept for consistency)

        Returns:
            Arc instance
        """
        # Path setup
        arc_slug = db_arc.arc.lower().replace(" ", "_")
        path = wiki_dir / "manuscript" / "arcs" / f"{arc_slug}.md"

        # Events in this arc
        events = []
        for ms_event in db_arc.events:
            event_slug = ms_event.event.event.lower().replace(" ", "_")
            event_path = wiki_dir / "manuscript" / "events" / f"{event_slug}.md"
            events.append({
                "name": ms_event.event.event,
                "link": relative_link(path, event_path),
                "date_range": f"{ms_event.event.start_date} to {ms_event.event.end_date}",
            })

        # Entries in this arc (need to query separately)
        # This will be populated by the export function
        entries = []

        # Characters (extracted from entries)
        characters = []

        # Themes (extracted from entries)
        themes = []

        # Timeline
        date_range_start = None
        date_range_end = None
        if db_arc.events:
            dates = [event.event.start_date for event in db_arc.events if event.event.start_date]
            if dates:
                date_range_start = min(dates)
                date_range_end = max(event.event.end_date for event in db_arc.events if event.event.end_date)

        return cls(
            path=path,
            wiki_dir=wiki_dir,
            name=db_arc.arc,
            description=None,  # Not in database yet
            events=events,
            entries=entries,
            characters=characters,
            themes=themes,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            total_entries=len(entries),
            total_events=len(events),
            completion_percentage=0,  # Will be calculated
            notes=None,  # Not in database yet
        )

    def to_wiki(self) -> List[str]:
        """
        Convert arc to vimwiki markdown.

        Returns:
            List of markdown lines
        """
        lines = [
            "# Palimpsest — Story Arc",
            "",
        ]

        # Add breadcrumbs
        breadcrumbs = self.generate_breadcrumbs(self.wiki_dir)
        if breadcrumbs:
            lines.extend([
                f"*{breadcrumbs}*",
                "",
            ])

        lines.extend([
            f"## {self.name}",
            "",
        ])

        # Description
        if self.description:
            lines.extend([
                "### Description",
                self.description,
                "",
            ])

        # Timeline
        if self.date_range_start or self.date_range_end:
            lines.extend(["### Timeline"])
            if self.date_range_start:
                lines.append(f"- **Start**: {self.date_range_start.isoformat()}")
            if self.date_range_end:
                lines.append(f"- **End**: {self.date_range_end.isoformat()}")
            lines.append("")

        # Events in arc
        if self.events:
            lines.extend(["### Events in Arc"])
            for event in self.events:
                lines.append(f"- [[{event['link']}|{event['name']}]] ({event['date_range']})")
            lines.append("")

        # Entries in arc
        if self.entries:
            lines.extend(["### Entries in Arc"])
            for entry in self.entries:
                note = f" — {entry['note']}" if entry.get("note") else ""
                lines.append(f"- [[{entry['link']}|{entry['date']}]]{note}")
            lines.append("")

        # Characters
        if self.characters:
            lines.extend(["### Characters"])
            for char in self.characters:
                lines.append(f"- [[{char['link']}|{char['name']}]] — {char.get('role', '')}")
            lines.append("")

        # Themes
        if self.themes:
            lines.extend(["### Themes"])
            for theme in self.themes:
                theme_link = f"../../manuscript/themes/{theme.lower().replace(' ', '_')}.md"
                lines.append(f"- [[{theme_link}|{theme}]]")
            lines.append("")

        # Arc notes
        if self.notes:
            lines.extend([
                "### Arc Notes",
                self.notes,
                "",
            ])

        # Status
        lines.extend([
            "### Status",
            f"- **Entries**: {self.total_entries}" + (" planned" if self.total_entries > 0 else ""),
            f"- **Completion**: {self.completion_percentage}%",
        ])

        return lines

    @classmethod
    def from_file(cls, path: Path) -> Optional["Arc"]:
        """
        Parse arc wiki file to extract editable fields.

        Args:
            path: Path to arc wiki file

        Returns:
            Arc with editable fields populated
        """
        if not path.exists():
            return None

        try:
            from dev.utils.wiki import parse_wiki_file

            sections = parse_wiki_file(path)

            # Extract arc name from filename
            name = path.stem.replace("_", " ").title()

            # Extract editable fields
            description = sections.get("Description", "").strip() or None

            notes = sections.get("Arc Notes", "").strip() or None

            return cls(
                path=path,
                wiki_dir=Path("."),  # Placeholder
                name=name,
                description=description,
                notes=notes,
            )

        except Exception as e:
            import sys
            sys.stderr.write(f"Error parsing {path}: {e}\n")
            return None
