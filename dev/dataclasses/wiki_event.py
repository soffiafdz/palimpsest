"""
wiki_event.py
-------------
Dataclass for events (narrative arcs) in vimwiki format.

Events track significant occurrences or periods spanning multiple
journal entries. Each event page shows a timeline of entries,
people involved, duration, and manuscript adaptation status.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import List, Optional, Dict, Any

from dev.dataclasses.wiki_entity import WikiEntity
from dev.utils.md import relative_link
from dev.utils.wiki import entity_path


@dataclass
class Event(WikiEntity):
    """
    Represents an event for vimwiki export.

    Attributes:
        path: Path to wiki file (vimwiki/events/{event}.md)
        event: Short identifier
        title: Full title (optional)
        description: Detailed description
        entries: List of entry records (chronological)
        people: List of people involved
        start_date: First entry date
        end_date: Last entry date
        duration_days: Event duration
        manuscript_status: Manuscript metadata
        manuscript_narrative_arc: Narrative arc name
        manuscript_themes: List of themes
        notes: User-editable notes for manuscript use
    """

    path: Path
    event: str
    title: Optional[str] = None
    description: Optional[str] = None
    entries: List[Dict[str, Any]] = field(default_factory=list)
    people: List[Dict[str, Any]] = field(default_factory=list)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    duration_days: int = 0
    manuscript_status: Optional[str] = None
    manuscript_narrative_arc: Optional[str] = None
    manuscript_themes: List[Dict[str, Any]] = field(default_factory=list)
    notes: Optional[str] = None

    @classmethod
    def from_database(
        cls,
        db_event: Any,
        wiki_dir: Path,
        journal_dir: Path,
    ) -> "Event":
        """
        Create Event from database model.

        Args:
            db_event: Database Event model with relationships loaded
            wiki_dir: Vimwiki root directory
            journal_dir: Journal entries directory

        Returns:
            Event instance
        """
        # Determine output path: vimwiki/events/{event}.md
        path = entity_path(wiki_dir, "events", db_event.event)

        # Build entries list (chronological)
        entries = []
        sorted_entries = sorted(db_event.entries, key=lambda e: e.date)
        for entry in sorted_entries:
            entry_year = entry.date.year
            entry_path = wiki_dir / "entries" / str(entry_year) / f"{entry.date.isoformat()}.md"
            entry_link = relative_link(path, entry_path)

            entries.append({
                "date": entry.date,
                "link": entry_link,
                "word_count": entry.word_count,
            })

        # Build people list
        people_dict = {}
        for person in db_event.people:
            person_path = entity_path(wiki_dir, "people", person.display_name)
            person_link = relative_link(path, person_path)

            # Count how many entries this person appears in
            person_entry_count = sum(1 for e in db_event.entries if person in e.people)

            people_dict[person.display_name] = {
                "name": person.display_name,
                "link": person_link,
                "entry_count": person_entry_count,
            }

        # Convert to sorted list (by entry count, then name)
        people = sorted(people_dict.values(), key=lambda p: (-p["entry_count"], p["name"]))

        # Calculate timeline metadata
        start_date = None
        end_date = None
        duration_days = 0
        if entries:
            start_date = entries[0]["date"]
            end_date = entries[-1]["date"]
            duration_days = (end_date - start_date).days + 1

        # Manuscript metadata
        manuscript_status = None
        manuscript_narrative_arc = None
        manuscript_themes = []
        if hasattr(db_event, "manuscript") and db_event.manuscript:
            ms = db_event.manuscript
            manuscript_status = ms.status.value if hasattr(ms, "status") and ms.status else None
            manuscript_narrative_arc = ms.narrative_arc

            # Get themes
            if hasattr(ms, "themes"):
                for theme in sorted(ms.themes, key=lambda t: t.theme):
                    theme_path = entity_path(wiki_dir, "themes", theme.theme)
                    theme_link = relative_link(path, theme_path)

                    manuscript_themes.append({
                        "name": theme.theme,
                        "link": theme_link,
                    })

        return cls(
            path=path,
            event=db_event.event,
            title=db_event.title,
            description=db_event.description,
            entries=entries,
            people=people,
            start_date=start_date,
            end_date=end_date,
            duration_days=duration_days,
            manuscript_status=manuscript_status,
            manuscript_narrative_arc=manuscript_narrative_arc,
            manuscript_themes=manuscript_themes,
            notes=db_event.notes,  # Export Event.notes from database
        )

    def to_wiki(self) -> List[str]:
        """
        Convert event to vimwiki markdown using template.

        Returns:
            List of markdown lines
        """
        from dev.utils.templates import render_template

        # Display name (title or event ID)
        display_name = self.title or self.event

        # Generate event info section
        event_info_lines = [f"- **Event ID:** {self.event}"]
        if self.title:
            event_info_lines.append(f"- **Title:** {self.title}")
        event_info_lines.append(f"- **Total Entries:** {len(self.entries)}")
        if self.start_date and self.end_date:
            event_info_lines.append(f"- **Date Range:** {self.start_date.isoformat()} to {self.end_date.isoformat()}")
            event_info_lines.append(f"- **Duration:** {self.duration_days} days")

        # Add manuscript metadata to event info
        if self.manuscript_status:
            event_info_lines.append(f"- **Manuscript Status:** {self.manuscript_status}")
        if self.manuscript_narrative_arc:
            event_info_lines.append(f"- **Narrative Arc:** {self.manuscript_narrative_arc}")
        if self.manuscript_themes:
            event_info_lines.append("- **Themes:**")
            for theme in self.manuscript_themes:
                event_info_lines.append(f"  - [[{theme['link']}|{theme['name']}]]")

        event_info = "\n".join(event_info_lines)

        # Generate description
        description = self.description if self.description else ""

        # Generate entries timeline (grouped by year)
        entries_content = ""
        if self.entries:
            entries_lines = []

            # Group by year
            entries_by_year = {}
            for entry in self.entries:
                year = entry["date"].year
                if year not in entries_by_year:
                    entries_by_year[year] = []
                entries_by_year[year].append(entry)

            # Output by year (most recent first)
            for year in sorted(entries_by_year.keys(), reverse=True):
                year_entries = entries_by_year[year]
                entries_lines.append(f"#### {year} ({len(year_entries)} entries)")
                entries_lines.append("")

                for entry in reversed(year_entries):  # Most recent first within year
                    word_str = f"{entry['word_count']} words" if entry['word_count'] else "no content"
                    entries_lines.append(f"- [[{entry['link']}|{entry['date'].isoformat()}]] — {word_str}")

                entries_lines.append("")

            entries_content = "\n".join(entries_lines)

        # Generate people involved section
        people_involved = ""
        if self.people:
            people_lines = []
            for person in self.people[:20]:  # Top 20
                entry_str = f"{person['entry_count']} entr" + ("ies" if person["entry_count"] != 1 else "y")
                people_lines.append(f"- [[{person['link']}|{person['name']}]] ({entry_str})")
            if len(self.people) > 20:
                people_lines.append(f"- ... and {len(self.people) - 20} more")
            people_involved = "\n".join(people_lines)

        # Locations section (placeholder for future implementation)
        locations = ""

        # Prepare template variables
        variables = {
            "display_name": display_name,
            "event_info": event_info,
            "description": description,
            "entries": entries_content,
            "people_involved": people_involved,
            "locations": locations,
            "notes": self.notes or "[Add notes about this event for manuscript use]",
        }

        return render_template("event", variables)

    @classmethod
    def from_file(cls, file_path: Path) -> Optional["Event"]:  # type: ignore[override]
        """
        Parse Event from existing wiki file to extract editable fields.

        Only extracts:
        - notes: User notes about the event

        Other fields (entries, people, themes, dates) are read-only and come from database.

        Args:
            file_path: Path to existing wiki file

        Returns:
            Event instance (partial - only editable fields populated), or None if file doesn't exist
        """
        if not file_path.exists():
            return None

        try:
            from dev.utils.wiki import parse_wiki_file, extract_notes

            sections = parse_wiki_file(file_path)

            # Extract event name from filename
            event_name = file_path.stem.replace("_", " ")

            # Extract notes (editable field)
            notes = extract_notes(sections)

            return cls(
                path=file_path,
                event=event_name,
                title=None,  # Not parsed from wiki, comes from database
                entries=[],  # Not parsed from wiki, comes from database
                people=[],  # Not parsed from wiki, comes from database
                manuscript_themes=[],  # Not parsed from wiki, comes from database
                start_date=None,  # Not parsed from wiki, comes from database
                end_date=None,  # Not parsed from wiki, comes from database
                manuscript_status=None,  # Not parsed from wiki, comes from database
                notes=notes,
            )
        except Exception as e:
            import sys
            sys.stderr.write(f"Error parsing {file_path}: {e}\n")
            return None

    # Computed properties
    @property
    def display_name(self) -> str:
        """Display name (title or event ID)."""
        return self.title or self.event

    @property
    def entry_count(self) -> int:
        """Total number of entries."""
        return len(self.entries)

    @property
    def people_count(self) -> int:
        """Total number of people involved."""
        return len(self.people)

    @property
    def has_manuscript_metadata(self) -> bool:
        """Check if event has manuscript metadata."""
        return bool(
            self.manuscript_status
            or self.manuscript_narrative_arc
            or self.manuscript_themes
        )
