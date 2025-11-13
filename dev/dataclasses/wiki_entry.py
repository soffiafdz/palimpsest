"""
wiki_entry.py
-------------
Dataclass for journal entries in vimwiki format.

Entry is the CORE entity connecting all metadata. Each entry page
shows:
- Entry metadata (date, word count, reading time, epigraph)
- All related entities (people, locations, cities, events, themes, tags)
- Poems written and references cited
- Manuscript metadata
- Related entries (prev/next/explicit)
- User-editable notes

This is the foundation for navigating the autofiction source material.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import List, Optional, Dict, Any

from dev.dataclasses.wiki_entity import WikiEntity
from dev.utils.wiki import relative_link


@dataclass
class Entry(WikiEntity):
    """
    Represents a journal entry for vimwiki export.

    The core entity of the metadata wiki - each journal entry with
    all its relationships, metadata, and cross-references.

    Attributes:
        path: Path to wiki file (vimwiki/entries/YYYY/YYYY-MM-DD.md)
        date: Entry date (ISO format)
        source_path: Path to original markdown file
        word_count: Number of words
        reading_time: Estimated reading time in minutes
        epigraph: Opening quote
        epigraph_attribution: Quote attribution
        age_display: Human-readable age

        # Relationships
        people: List of people mentioned with their roles
        locations: List of locations visited
        cities: List of cities
        events: List of events this entry belongs to
        themes: List of themes present
        tags: List of keyword tags
        poems: List of poems written in this entry
        references: List of references cited
        mentioned_dates: List of dates referenced
        related_entries: List of explicitly related entries
        prev_entry: Previous entry (chronological)
        next_entry: Next entry (chronological)

        # Manuscript
        manuscript_status: Manuscript metadata if entry is being adapted
        manuscript_type: Type (vignette, scene, etc)
        manuscript_characters: Character mappings
        manuscript_narrative_arc: Narrative arc name

        # Editable
        notes: User-editable notes for manuscript use
    """

    path: Path
    date: date
    source_path: Path
    word_count: int = 0
    reading_time: float = 0.0
    epigraph: Optional[str] = None
    epigraph_attribution: Optional[str] = None
    age_display: str = ""

    # Relationships
    people: List[Dict[str, Any]] = field(default_factory=list)
    locations: List[Dict[str, Any]] = field(default_factory=list)
    cities: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    themes: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    poems: List[Dict[str, Any]] = field(default_factory=list)
    references: List[Dict[str, Any]] = field(default_factory=list)
    mentioned_dates: List[Dict[str, Any]] = field(default_factory=list)
    related_entries: List[Dict[str, Any]] = field(default_factory=list)
    prev_entry: Optional[Dict[str, Any]] = None
    next_entry: Optional[Dict[str, Any]] = None

    # Manuscript
    manuscript_status: Optional[str] = None
    manuscript_type: Optional[str] = None
    manuscript_characters: Optional[str] = None
    manuscript_narrative_arc: Optional[str] = None

    # Editable
    notes: Optional[str] = None

    @classmethod
    def from_database(
        cls,
        db_entry: Any,
        wiki_dir: Path,
        journal_dir: Path,
        prev_entry: Optional[Any] = None,
        next_entry: Optional[Any] = None,
    ) -> "Entry":
        """
        Create Entry from database model.

        Args:
            db_entry: Database Entry model with relationships loaded
            wiki_dir: Vimwiki root directory
            journal_dir: Journal entries directory
            prev_entry: Previous entry (chronological) for navigation
            next_entry: Next entry (chronological) for navigation

        Returns:
            Entry instance
        """
        # Determine output path: vimwiki/entries/YYYY/YYYY-MM-DD.md
        year = db_entry.date.year
        entry_filename = f"{db_entry.date.isoformat()}.md"
        path = wiki_dir / "entries" / str(year) / entry_filename

        # Source path
        source_path = Path(db_entry.file_path)

        # People mentioned
        people = []
        for person in sorted(db_entry.people, key=lambda p: p.display_name):
            person_filename = person.display_name.lower().replace(" ", "_") + ".md"
            person_path = wiki_dir / "people" / person_filename
            link = relative_link(path, person_path)

            people.append({
                "name": person.display_name,
                "link": link,
                "relation": person.relation_type.value if person.relation_type else "Unknown",
            })

        # Locations visited
        locations = []
        for location in sorted(db_entry.locations, key=lambda l: l.name):
            city_slug = location.city.city.lower().replace(" ", "_")
            location_slug = location.name.lower().replace(" ", "_")
            location_path = wiki_dir / "locations" / city_slug / f"{location_slug}.md"
            link = relative_link(path, location_path)

            locations.append({
                "name": location.name,
                "city": location.city.city,
                "link": link,
            })

        # Cities
        cities = []
        for city in sorted(db_entry.cities, key=lambda c: c.city):
            city_slug = city.city.lower().replace(" ", "_")
            city_path = wiki_dir / "cities" / f"{city_slug}.md"
            link = relative_link(path, city_path)

            cities.append({
                "name": city.city,
                "country": city.country,
                "link": link,
            })

        # Events
        events = []
        for event in sorted(db_entry.events, key=lambda e: e.display_name):
            event_slug = event.event.lower().replace(" ", "_")
            event_path = wiki_dir / "events" / f"{event_slug}.md"
            link = relative_link(path, event_path)

            events.append({
                "name": event.display_name,
                "link": link,
            })

        # Themes (manuscript)
        themes = []
        if hasattr(db_entry, "manuscript") and db_entry.manuscript:
            for theme in sorted(db_entry.manuscript.themes, key=lambda t: t.theme):
                theme_slug = theme.theme.lower().replace(" ", "_")
                theme_path = wiki_dir / "themes" / f"{theme_slug}.md"
                link = relative_link(path, theme_path)

                themes.append({
                    "name": theme.theme,
                    "link": link,
                })

        # Tags
        tags = sorted([tag.tag for tag in db_entry.tags])

        # Poems
        poems = []
        for poem_version in db_entry.poems:
            if poem_version.poem:
                poem_slug = poem_version.poem.title.lower().replace(" ", "_")
                poem_path = wiki_dir / "poems" / f"{poem_slug}.md"
                link = relative_link(path, poem_path)

                poems.append({
                    "title": poem_version.poem.title,
                    "link": link,
                    "revision_date": poem_version.revision_date,
                })

        # References
        references = []
        for ref in db_entry.references:
            if ref.source:
                source_slug = ref.source.title.lower().replace(" ", "_")
                source_path = wiki_dir / "references" / f"{source_slug}.md"
                link = relative_link(path, source_path)

                references.append({
                    "source": ref.source.title,
                    "content": ref.content,
                    "link": link,
                })

        # Mentioned dates
        mentioned_dates = []
        for md in sorted(db_entry.dates, key=lambda d: d.date):
            mentioned_dates.append({
                "date": md.date,
                "context": md.context or "",
            })

        # Related entries
        related = []
        for rel_entry in db_entry.related_entries:
            rel_year = rel_entry.date.year
            rel_filename = f"{rel_entry.date.isoformat()}.md"
            rel_path = wiki_dir / "entries" / str(rel_year) / rel_filename
            link = relative_link(path, rel_path)

            related.append({
                "date": rel_entry.date,
                "link": link,
            })

        # Previous/next entries
        prev_dict = None
        if prev_entry:
            prev_year = prev_entry.date.year
            prev_filename = f"{prev_entry.date.isoformat()}.md"
            prev_path = wiki_dir / "entries" / str(prev_year) / prev_filename
            prev_link = relative_link(path, prev_path)
            prev_dict = {"date": prev_entry.date, "link": prev_link}

        next_dict = None
        if next_entry:
            next_year = next_entry.date.year
            next_filename = f"{next_entry.date.isoformat()}.md"
            next_path = wiki_dir / "entries" / str(next_year) / next_filename
            next_link = relative_link(path, next_path)
            next_dict = {"date": next_entry.date, "link": next_link}

        # Manuscript metadata
        manuscript_status = None
        manuscript_type = None
        manuscript_characters = None
        manuscript_narrative_arc = None
        if hasattr(db_entry, "manuscript") and db_entry.manuscript:
            ms = db_entry.manuscript
            manuscript_status = ms.status.value if hasattr(ms, "status") and ms.status else None
            manuscript_type = ms.entry_type.value if hasattr(ms, "entry_type") and ms.entry_type else None
            manuscript_characters = ms.character_notes
            manuscript_narrative_arc = ms.narrative_arc

        return cls(
            path=path,
            date=db_entry.date,
            source_path=source_path,
            word_count=db_entry.word_count,
            reading_time=db_entry.reading_time,
            epigraph=db_entry.epigraph,
            epigraph_attribution=db_entry.epigraph_attribution,
            age_display=db_entry.age_display,
            people=people,
            locations=locations,
            cities=cities,
            events=events,
            themes=themes,
            tags=tags,
            poems=poems,
            references=references,
            mentioned_dates=mentioned_dates,
            related_entries=related,
            prev_entry=prev_dict,
            next_entry=next_dict,
            manuscript_status=manuscript_status,
            manuscript_type=manuscript_type,
            manuscript_characters=manuscript_characters,
            manuscript_narrative_arc=manuscript_narrative_arc,
            notes=None,  # Will be preserved from existing file if present
        )

    def to_wiki(self) -> List[str]:
        """
        Convert entry to vimwiki markdown.

        Returns:
            List of markdown lines
        """
        lines = [
            "# Palimpsest — Entry",
            "",
            f"## {self.date.isoformat()}",
            "",
        ]

        # Basic metadata
        lines.extend([
            "### Metadata",
            f"- **Date:** {self.date.isoformat()}",
            f"- **Word Count:** {self.word_count} words",
            f"- **Reading Time:** {self.reading_time:.1f} minutes",
            f"- **Age:** {self.age_display}",
            "",
        ])

        # Epigraph if present
        if self.epigraph:
            lines.extend(["### Epigraph", ""])
            lines.append(f"> {self.epigraph}")
            if self.epigraph_attribution:
                lines.append(f"> — {self.epigraph_attribution}")
            lines.append("")

        # Source link
        source_link = relative_link(self.path, self.source_path)
        lines.extend([
            "### Source",
            f"[[{source_link}|Read Full Entry]]",
            "",
        ])

        # People
        if self.people:
            lines.extend(["### People", ""])
            for person in self.people:
                lines.append(f"- [[{person['link']}|{person['name']}]] ({person['relation']})")
            lines.append("")

        # Locations
        if self.locations:
            lines.extend(["### Locations", ""])
            for location in self.locations:
                lines.append(f"- [[{location['link']}|{location['name']}]] ({location['city']})")
            lines.append("")

        # Cities
        if self.cities:
            lines.extend(["### Cities", ""])
            for city in self.cities:
                city_display = f"{city['name']}, {city['country']}" if city['country'] else city['name']
                lines.append(f"- [[{city['link']}|{city_display}]]")
            lines.append("")

        # Events
        if self.events:
            lines.extend(["### Events", ""])
            for event in self.events:
                lines.append(f"- [[{event['link']}|{event['name']}]]")
            lines.append("")

        # Themes
        if self.themes:
            lines.extend(["### Themes", ""])
            for theme in self.themes:
                lines.append(f"- [[{theme['link']}|{theme['name']}]]")
            lines.append("")

        # Tags
        if self.tags:
            lines.extend(["### Tags", ""])
            tag_str = " ".join([f"#{tag}" for tag in self.tags])
            lines.append(tag_str)
            lines.append("")

        # Poems
        if self.poems:
            lines.extend(["### Poems Written", ""])
            for poem in self.poems:
                poem_str = f"- [[{poem['link']}|{poem['title']}]]"
                if poem['revision_date']:
                    poem_str += f" ({poem['revision_date']})"
                lines.append(poem_str)
            lines.append("")

        # References
        if self.references:
            lines.extend(["### References Cited", ""])
            for ref in self.references:
                lines.append(f"- [[{ref['link']}|{ref['source']}]]")
                if ref['content']:
                    lines.append(f"  > {ref['content'][:100]}...")
            lines.append("")

        # Mentioned dates
        if self.mentioned_dates:
            lines.extend(["### Mentioned Dates", ""])
            for md in self.mentioned_dates:
                date_str = f"- {md['date'].isoformat()}"
                if md['context']:
                    date_str += f" — {md['context']}"
                lines.append(date_str)
            lines.append("")

        # Manuscript metadata
        if self.manuscript_status or self.manuscript_type:
            lines.extend(["### Manuscript", ""])
            if self.manuscript_status:
                lines.append(f"- **Status:** {self.manuscript_status}")
            if self.manuscript_type:
                lines.append(f"- **Type:** {self.manuscript_type}")
            if self.manuscript_narrative_arc:
                lines.append(f"- **Narrative Arc:** {self.manuscript_narrative_arc}")
            if self.manuscript_characters:
                lines.append(f"- **Character Notes:** {self.manuscript_characters}")
            lines.append("")

        # Navigation
        lines.extend(["### Navigation", ""])
        if self.prev_entry:
            lines.append(f"- **Previous:** [[{self.prev_entry['link']}|{self.prev_entry['date']}]]")
        if self.next_entry:
            lines.append(f"- **Next:** [[{self.next_entry['link']}|{self.next_entry['date']}]]")

        # Related entries
        if self.related_entries:
            lines.extend(["", "**Related Entries:**"])
            for rel in self.related_entries:
                lines.append(f"- [[{rel['link']}|{rel['date']}]]")

        lines.append("")

        # User notes (wiki-editable)
        lines.extend(["### Notes", ""])
        if self.notes:
            lines.append(self.notes)
        else:
            lines.append("[Add your notes about this entry for manuscript use]")
        lines.append("")

        return lines

    @classmethod
    def from_file(cls, file_path: Path) -> "Entry":
        """
        Parse Entry from existing wiki file.

        Extracts the wiki-editable fields (notes) while preserving
        database-computed fields.

        Args:
            file_path: Path to existing wiki file

        Returns:
            Entry instance (partial - only editable fields populated)
        """
        # TODO: Implement in Phase 3 (wiki2sql)
        raise NotImplementedError("from_file() will be implemented in Phase 3")

    # Computed properties
    @property
    def has_manuscript_metadata(self) -> bool:
        """Check if entry has manuscript metadata."""
        return bool(
            self.manuscript_status
            or self.manuscript_type
            or self.manuscript_narrative_arc
            or self.manuscript_characters
        )

    @property
    def entity_count(self) -> int:
        """Total count of related entities."""
        return (
            len(self.people)
            + len(self.locations)
            + len(self.cities)
            + len(self.events)
            + len(self.themes)
            + len(self.tags)
            + len(self.poems)
            + len(self.references)
        )

    @property
    def date_iso(self) -> str:
        """ISO format date string."""
        return self.date.isoformat()
