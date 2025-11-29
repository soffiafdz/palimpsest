"""
wiki_city.py
------------
Dataclass for cities (geographic regions) in vimwiki format.

Cities are parent entities for locations, representing geographic
regions where journal entries take place. Each city page shows
entries, locations, people, and visit frequency over time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import List, Optional, Dict, Any

from dev.dataclasses.wiki_entity import WikiEntity
from dev.utils.md import relative_link


@dataclass
class City(WikiEntity):
    """
    Represents a city for vimwiki export.

    Attributes:
        path: Path to wiki file (vimwiki/cities/{name}.md)
        name: City name
        state_province: State or province (optional)
        country: Country (optional)
        entries: List of entry records
        locations: List of child locations
        people: List of people met in this city
        visit_frequency: Monthly visit frequency data
        notes: User-editable notes for manuscript use
    """

    path: Path
    name: str
    state_province: Optional[str] = None
    country: Optional[str] = None
    entries: List[Dict[str, Any]] = field(default_factory=list)
    locations: List[Dict[str, Any]] = field(default_factory=list)
    people: List[Dict[str, Any]] = field(default_factory=list)
    visit_frequency: Dict[str, int] = field(default_factory=dict)
    notes: Optional[str] = None

    @classmethod
    def from_database(
        cls,
        db_city: Any,
        wiki_dir: Path,
        journal_dir: Path,
    ) -> "City":
        """
        Create City from database model.

        Args:
            db_city: Database City model with relationships loaded
            wiki_dir: Vimwiki root directory
            journal_dir: Journal entries directory

        Returns:
            City instance
        """
        # Determine output path: vimwiki/cities/{name}.md
        city_slug = db_city.city.lower().replace(" ", "_")
        path = wiki_dir / "cities" / f"{city_slug}.md"

        # Build entries list
        entries = []
        for entry in sorted(db_city.entries, key=lambda e: e.date, reverse=True):
            entry_year = entry.date.year
            entry_path = wiki_dir / "entries" / str(entry_year) / f"{entry.date.isoformat()}.md"
            entry_link = relative_link(path, entry_path)

            entries.append({
                "date": entry.date,
                "link": entry_link,
                "word_count": entry.word_count,
            })

        # Build locations list
        locations = []
        for location in sorted(db_city.locations, key=lambda loc: loc.name):
            location_slug = location.name.lower().replace(" ", "_")
            location_path = wiki_dir / "locations" / city_slug / f"{location_slug}.md"
            location_link = relative_link(path, location_path)

            # Count visits (from location's entries)
            visit_count = len(location.entries)

            locations.append({
                "name": location.name,
                "link": location_link,
                "visit_count": visit_count,
            })

        # Collect people met in this city
        people_dict = {}
        for entry in db_city.entries:
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

        # Calculate visit frequency by year-month
        visit_frequency = {}
        for entry in db_city.entries:
            year_month = entry.date.strftime("%Y-%m")
            visit_frequency[year_month] = visit_frequency.get(year_month, 0) + 1

        return cls(
            path=path,
            name=db_city.city,
            state_province=db_city.state_province,
            country=db_city.country,
            entries=entries,
            locations=locations,
            people=people,
            visit_frequency=visit_frequency,
            notes=None,  # Will be preserved from existing file if present
        )

    def to_wiki(self) -> List[str]:
        """
        Convert city to vimwiki markdown using template.

        Returns:
            List of markdown lines
        """
        from dev.utils.templates import render_template

        # Generate location info section
        location_info_lines = []
        if self.state_province:
            location_info_lines.append(f"- **State/Province:** {self.state_province}")
        if self.country:
            location_info_lines.append(f"- **Country:** {self.country}")
        location_info_lines.append(f"- **Total Entries:** {len(self.entries)}")
        location_info_lines.append(f"- **Tracked Locations:** {len(self.locations)}")
        location_info = "\n".join(location_info_lines)

        # Generate statistics section
        statistics = ""
        if self.entries:
            first_entry = self.entries[-1]["date"]  # entries are reverse sorted
            last_entry = self.entries[0]["date"]
            span_days = (last_entry - first_entry).days

            statistics_lines = [
                f"- **First Entry:** {first_entry.isoformat()}",
                f"- **Last Entry:** {last_entry.isoformat()}",
                f"- **Span:** {span_days} days",
            ]

            # Add visit frequency visualization
            if self.visit_frequency:
                statistics_lines.append("")
                statistics_lines.append("**Visit Frequency by Year:**")
                statistics_lines.append("")

                # Group by year
                freq_by_year = {}
                for year_month, count in self.visit_frequency.items():
                    year = year_month[:4]
                    if year not in freq_by_year:
                        freq_by_year[year] = {}
                    month = year_month[5:7]
                    freq_by_year[year][month] = count

                # Output by year (most recent first)
                for year in sorted(freq_by_year.keys(), reverse=True):
                    months = freq_by_year[year]
                    total = sum(months.values())
                    statistics_lines.append(f"**{year}** ({total} entries):")
                    statistics_lines.append("")

                    # Month bars (simple visualization)
                    for month_num in ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"]:
                        if month_num in months:
                            count = months[month_num]
                            month_name = date(int(year), int(month_num), 1).strftime("%b")
                            bar = "█" * min(count, 20)  # Max 20 blocks
                            statistics_lines.append(f"- {month_name}: {bar} ({count})")

                    statistics_lines.append("")

            statistics = "\n".join(statistics_lines)

        # Generate locations section
        locations_content = ""
        if self.locations:
            locations_lines = []
            # Sort by visit count (descending)
            sorted_locations = sorted(self.locations, key=lambda loc: (-loc["visit_count"], loc["name"]))
            for loc in sorted_locations:
                visit_str = f"{loc['visit_count']} visit" + ("s" if loc["visit_count"] != 1 else "")
                locations_lines.append(f"- [[{loc['link']}|{loc['name']}]] ({visit_str})")
            locations_content = "\n".join(locations_lines)

        # Generate people encountered section
        people_encountered = ""
        if self.people:
            people_lines = []
            for person in self.people[:20]:  # Top 20
                entry_str = f"{person['count']} entr" + ("ies" if person["count"] != 1 else "y")
                people_lines.append(f"- [[{person['link']}|{person['name']}]] ({entry_str})")
            if len(self.people) > 20:
                people_lines.append(f"- ... and {len(self.people) - 20} more")
            people_encountered = "\n".join(people_lines)

        # Prepare template variables
        variables = {
            "name": self.name,
            "location_info": location_info,
            "statistics": statistics,
            "locations": locations_content,
            "people_encountered": people_encountered,
            "notes": self.notes or "[Add notes about this city for manuscript use]",
        }

        return render_template("city", variables)

    @classmethod
    def from_file(cls, file_path: Path) -> Optional["City"]:  # type: ignore[override]
        """
        Parse City from existing wiki file to extract editable fields.

        Only extracts:
        - notes: User notes about the city

        Other fields (country, entries, locations, visit_freq) are read-only and come from database.

        Args:
            file_path: Path to existing wiki file

        Returns:
            City instance (partial - only editable fields populated), or None if file doesn't exist
        """
        if not file_path.exists():
            return None

        try:
            from dev.utils.wiki import parse_wiki_file, extract_notes

            sections = parse_wiki_file(file_path)

            # Extract city name from filename
            name = file_path.stem.replace("_", " ")

            # Extract notes (editable field)
            notes = extract_notes(sections)

            return cls(
                path=file_path,
                name=name,
                country=None,  # Not parsed from wiki, comes from database
                entries=[],  # Not parsed from wiki, comes from database
                locations=[],  # Not parsed from wiki, comes from database
                visit_frequency={},  # Not parsed from wiki, comes from database
                notes=notes,
            )
        except Exception as e:
            import sys
            sys.stderr.write(f"Error parsing {file_path}: {e}\n")
            return None

    # Computed properties
    @property
    def entry_count(self) -> int:
        """Total number of entries."""
        return len(self.entries)

    @property
    def location_count(self) -> int:
        """Total number of tracked locations."""
        return len(self.locations)

    @property
    def first_entry_date(self) -> Optional[date]:
        """Date of first entry."""
        return self.entries[-1]["date"] if self.entries else None

    @property
    def last_entry_date(self) -> Optional[date]:
        """Date of last entry."""
        return self.entries[0]["date"] if self.entries else None
