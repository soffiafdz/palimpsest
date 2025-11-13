"""
wiki_location.py
----------------
Dataclass for geographic locations (venues) in vimwiki format.

Locations are specific venues/places mentioned in journal entries,
grouped under parent cities. Each location page shows visit timeline,
entries where mentioned, and people encountered there.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import List, Optional, Dict, Any

from dev.dataclasses.wiki_entity import WikiEntity
from dev.utils.wiki import relative_link


@dataclass
class Location(WikiEntity):
    """
    Represents a geographic location/venue for vimwiki export.

    Attributes:
        path: Path to wiki file (vimwiki/locations/{city}/{name}.md)
        name: Location name (venue)
        city: Parent city name
        city_country: City's country
        visits: List of visit records with dates and entries
        people: List of people encountered at this location
        notes: User-editable notes for manuscript use
    """

    path: Path
    name: str
    city: str
    city_country: Optional[str] = None
    visits: List[Dict[str, Any]] = field(default_factory=list)
    people: List[Dict[str, Any]] = field(default_factory=list)
    notes: Optional[str] = None

    @classmethod
    def from_database(
        cls,
        db_location: Any,
        wiki_dir: Path,
        journal_dir: Path,
    ) -> "Location":
        """
        Create Location from database model.

        Args:
            db_location: Database Location model with relationships loaded
            wiki_dir: Vimwiki root directory
            journal_dir: Journal entries directory

        Returns:
            Location instance
        """
        # Determine output path: vimwiki/locations/{city}/{name}.md
        city_slug = db_location.city.city.lower().replace(" ", "_")
        location_slug = db_location.name.lower().replace(" ", "_")
        path = wiki_dir / "locations" / city_slug / f"{location_slug}.md"

        # Build visit timeline
        visits = []

        # Add explicit dated visits (from MentionedDate)
        for mentioned_date in sorted(db_location.dates, key=lambda d: d.date):
            entry = None
            entry_link = None
            # Find the entry for this date
            for e in mentioned_date.entries:
                if db_location in e.locations:
                    entry = e
                    break

            if entry:
                entry_year = entry.date.year
                entry_path = wiki_dir / "entries" / str(entry_year) / f"{entry.date.isoformat()}.md"
                entry_link = relative_link(path, entry_path)

            visits.append({
                "date": mentioned_date.date,
                "context": mentioned_date.context or "",
                "entry_link": entry_link,
                "source": "mentioned_date",
            })

        # Add entry-based visits (from entries that mention this location)
        for entry in db_location.entries:
            # Check if this entry date is already in visits
            already_listed = any(v["date"] == entry.date for v in visits)
            if not already_listed:
                entry_year = entry.date.year
                entry_path = wiki_dir / "entries" / str(entry_year) / f"{entry.date.isoformat()}.md"
                entry_link = relative_link(path, entry_path)

                visits.append({
                    "date": entry.date,
                    "context": "",
                    "entry_link": entry_link,
                    "source": "entry",
                })

        # Sort all visits by date
        visits.sort(key=lambda v: v["date"])

        # Collect people encountered at this location
        people_dict = {}
        for entry in db_location.entries:
            for person in entry.people:
                if person.display_name not in people_dict:
                    person_filename = person.display_name.lower().replace(" ", "_") + ".md"
                    person_path = wiki_dir / "people" / person_filename
                    person_link = relative_link(path, person_path)

                    people_dict[person.display_name] = {
                        "name": person.display_name,
                        "link": person_link,
                        "count": 0,
                    }
                people_dict[person.display_name]["count"] += 1

        # Convert to sorted list
        people = sorted(people_dict.values(), key=lambda p: (-p["count"], p["name"]))

        return cls(
            path=path,
            name=db_location.name,
            city=db_location.city.city,
            city_country=db_location.city.country,
            visits=visits,
            people=people,
            notes=None,  # Will be preserved from existing file if present
        )

    def to_wiki(self) -> List[str]:
        """
        Convert location to vimwiki markdown.

        Returns:
            List of markdown lines
        """
        lines = [
            "# Palimpsest — Location",
            "",
            f"## {self.name}",
            "",
        ]

        # City and location info
        city_slug = self.city.lower().replace(" ", "_")
        city_path = Path("../../cities") / f"{city_slug}.md"
        city_display = f"{self.city}, {self.city_country}" if self.city_country else self.city

        lines.extend([
            "### Location Info",
            f"- **City:** [[{city_path}|{city_display}]]",
            f"- **Total Visits:** {len(self.visits)}",
            "",
        ])

        # Visit statistics
        if self.visits:
            first_visit = self.visits[0]["date"]
            last_visit = self.visits[-1]["date"]
            span_days = (last_visit - first_visit).days

            lines.extend([
                "### Visit History",
                f"- **First Visit:** {first_visit.isoformat()}",
                f"- **Last Visit:** {last_visit.isoformat()}",
                f"- **Span:** {span_days} days",
                "",
            ])

        # Visit timeline (grouped by year)
        if self.visits:
            lines.extend(["### Timeline", ""])

            # Group by year
            from itertools import groupby

            for year, year_visits in groupby(reversed(self.visits), key=lambda v: v["date"].year):
                year_visits_list = list(year_visits)
                lines.extend([f"#### {year}", ""])

                for visit in year_visits_list:
                    date_str = visit["date"].isoformat()
                    if visit["entry_link"]:
                        line = f"- **{date_str}** — [[{visit['entry_link']}|Entry]]"
                    else:
                        line = f"- **{date_str}**"

                    if visit["context"]:
                        line += f" — {visit['context']}"

                    lines.append(line)

                lines.append("")

        # People encountered
        if self.people:
            lines.extend(["### People Encountered", ""])
            for person in self.people:
                visit_str = f"{person['count']} visit" + ("s" if person["count"] != 1 else "")
                lines.append(f"- [[{person['link']}|{person['name']}]] ({visit_str})")
            lines.append("")

        # User notes (wiki-editable)
        lines.extend(["### Notes", ""])
        if self.notes:
            lines.append(self.notes)
        else:
            lines.append("[Add notes about this location for manuscript use]")
        lines.append("")

        return lines

    @classmethod
    def from_file(cls, file_path: Path) -> Optional["Location"]:
        """
        Parse Location from existing wiki file to extract editable fields.

        Only extracts:
        - notes: User notes about the location

        Other fields (visits, people) are read-only and come from database.

        Args:
            file_path: Path to existing wiki file

        Returns:
            Location instance (partial - only editable fields populated), or None if file doesn't exist
        """
        if not file_path.exists():
            return None

        try:
            from dev.utils.wiki_parser import parse_wiki_file, extract_notes

            sections = parse_wiki_file(file_path)

            # Extract location name from filename
            name = file_path.stem.replace("_", " ")

            # Extract city from parent directory
            city = file_path.parent.name.replace("_", " ")

            # Extract notes (editable field)
            notes = extract_notes(sections)

            return cls(
                path=file_path,
                name=name,
                city=city,
                city_country=None,  # Not parsed from wiki, comes from database
                visits=[],  # Not parsed from wiki, comes from database
                people=[],  # Not parsed from wiki, comes from database
                notes=notes,
            )
        except Exception as e:
            import sys
            sys.stderr.write(f"Error parsing {file_path}: {e}\n")
            return None

    # Computed properties
    @property
    def visit_count(self) -> int:
        """Total number of visits."""
        return len(self.visits)

    @property
    def first_visit(self) -> Optional[date]:
        """Date of first visit."""
        return self.visits[0]["date"] if self.visits else None

    @property
    def last_visit(self) -> Optional[date]:
        """Date of last visit."""
        return self.visits[-1]["date"] if self.visits else None

    @property
    def span_days(self) -> int:
        """Days between first and last visit."""
        if not self.visits or len(self.visits) < 2:
            return 0
        return (self.last_visit - self.first_visit).days
