#!/usr/bin/env python3
"""
manuscript_event.py
-------------------
Dataclass for manuscript event wiki pages.

Represents events adapted for the manuscript narrative, with arc placement and adaptation notes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from dev.dataclasses.wiki_entity import WikiEntity
from dev.utils.md import relative_link


@dataclass
class ManuscriptEvent(WikiEntity):
    """
    Represents an event adapted for the manuscript.

    Links journal events to manuscript narrative, with arc placement
    and adaptation notes.

    Attributes:
        path: Path to manuscript event wiki file (wiki/manuscript/events/event.md)
        wiki_dir: Wiki root directory for breadcrumb generation
        name: Event name
        source_event_path: Link to event in main wiki

        # Manuscript metadata
        arc: Name of story arc this event belongs to
        notes: Adaptation notes for this event

        # Event details
        start_date: Event start date
        end_date: Event end date
        entry_count: Number of entries in this event

        # Relationships
        entries: List of manuscript entries in this event
        people: List of people/characters involved
    """

    path: Path
    wiki_dir: Path
    name: str
    source_event_path: Path

    # Manuscript metadata
    arc: Optional[str] = None
    notes: Optional[str] = None

    # Event details
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    entry_count: int = 0

    # Relationships
    entries: List[Dict[str, Any]] = field(default_factory=list)
    people: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_database(
        cls,
        db_event: Any,
        manuscript_event: Any,
        wiki_dir: Path,
        journal_dir: Path,
    ) -> "ManuscriptEvent":
        """
        Create ManuscriptEvent from database models.

        Args:
            db_event: Event database model
            manuscript_event: ManuscriptEvent database model
            wiki_dir: Wiki root directory
            journal_dir: Journal directory (unused but kept for consistency)

        Returns:
            ManuscriptEvent instance
        """
        # Path setup
        event_slug = db_event.event.lower().replace(" ", "_")
        path = wiki_dir / "manuscript" / "events" / f"{event_slug}.md"

        # Source event path
        source_event_path = wiki_dir / "events" / f"{event_slug}.md"

        # Arc
        arc = manuscript_event.arc.arc if manuscript_event.arc else None

        # Entries in this event (only manuscript entries)
        entries = []
        for entry in db_event.entries:
            # Check if entry has manuscript record
            if hasattr(entry, "manuscript") and entry.manuscript:
                entry_year = entry.date.year
                entry_path = wiki_dir / "manuscript" / "entries" / str(entry_year) / f"{entry.date.isoformat()}.md"
                entries.append({
                    "date": entry.date.isoformat(),
                    "link": relative_link(path, entry_path),
                })

        # Sort by date
        entries.sort(key=lambda x: x["date"])

        # People involved (with character mappings if available)
        people = []
        for person in db_event.people:
            person_info = {
                "real_name": person.display_name,
                "link": relative_link(
                    path,
                    wiki_dir / "people" / f"{person.name.lower().replace(' ', '_')}.md"
                ),
            }

            # Add character name if person has manuscript mapping
            if hasattr(person, "manuscript") and person.manuscript:
                person_info["character_name"] = person.manuscript.character
                person_info["character_link"] = relative_link(
                    path,
                    wiki_dir / "manuscript" / "characters" / f"{person.manuscript.character.lower().replace(' ', '_')}.md"
                )

            people.append(person_info)

        return cls(
            path=path,
            wiki_dir=wiki_dir,
            name=db_event.event,
            source_event_path=source_event_path,
            arc=arc,
            notes=manuscript_event.notes,
            start_date=db_event.start_date,
            end_date=db_event.end_date,
            entry_count=len(entries),
            entries=entries,
            people=people,
        )

    def to_wiki(self) -> List[str]:
        """
        Convert manuscript event to vimwiki markdown.

        Returns:
            List of markdown lines
        """
        lines = [
            "# Palimpsest — Manuscript Event",
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

        # Source link
        source_link = relative_link(self.path, self.source_event_path)
        lines.extend([
            "### Source",
            f"**Original Event**: [[{source_link}|View in Main Wiki]]",
            "",
        ])

        # Event details
        lines.extend(["### Event Details"])
        if self.start_date:
            lines.append(f"- **Start**: {self.start_date.isoformat()}")
        if self.end_date:
            lines.append(f"- **End**: {self.end_date.isoformat()}")
        lines.append(f"- **Entries**: {self.entry_count}")
        lines.append("")

        # Arc
        if self.arc:
            arc_link = f"../../arcs/{self.arc.lower().replace(' ', '_')}.md"
            lines.extend([
                "### Story Arc",
                f"[[{arc_link}|{self.arc}]]",
                "",
            ])

        # Characters
        if self.people:
            lines.extend(["### Characters"])
            for person in self.people:
                if "character_name" in person:
                    lines.append(
                        f"- [[{person['character_link']}|{person['character_name']}]] "
                        f"(based on [[{person['link']}|{person['real_name']}]])"
                    )
                else:
                    lines.append(f"- [[{person['link']}|{person['real_name']}]] (no character mapping)")
            lines.append("")

        # Entries
        if self.entries:
            lines.extend(["### Entries"])
            for entry in self.entries:
                lines.append(f"- [[{entry['link']}|{entry['date']}]]")
            lines.append("")

        # Adaptation notes
        if self.notes:
            lines.extend([
                "### Adaptation Notes",
                self.notes,
                "",
            ])

        return lines

    @classmethod
    def from_file(cls, path: Path) -> Optional["ManuscriptEvent"]:
        """
        Parse manuscript event wiki file to extract editable fields.

        Args:
            path: Path to manuscript event wiki file

        Returns:
            ManuscriptEvent with editable fields populated
        """
        if not path.exists():
            return None

        try:
            from dev.utils.wiki import parse_wiki_file

            sections = parse_wiki_file(path)

            # Extract event name from filename
            name = path.stem.replace("_", " ").title()

            # Extract editable fields
            notes = None
            if "adaptation notes" in sections:
                notes = "\n".join(sections["adaptation notes"]).strip()

            return cls(
                path=path,
                wiki_dir=Path("."),  # Placeholder
                name=name,
                source_event_path=Path("."),  # Placeholder
                notes=notes,
            )

        except Exception as e:
            import sys
            sys.stderr.write(f"Error parsing {path}: {e}\n")
            return None
