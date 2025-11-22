#!/usr/bin/env python3
"""
manuscript_entry.py
-------------------
Dataclass for manuscript entry wiki pages.

Represents journal entries adapted for the manuscript, with manuscript-specific
metadata like entry type, character notes, and narrative arc placement.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from dev.dataclasses.wiki_entity import WikiEntity
from dev.utils.wiki import relative_link


@dataclass
class ManuscriptEntry(WikiEntity):
    """
    Represents a manuscript entry for the manuscript subwiki.

    A journal entry that has been designated for manuscript inclusion,
    with metadata about how it's being adapted (type, character notes,
    narrative arc).

    Attributes:
        path: Path to manuscript wiki file (wiki/manuscript/entries/YYYY/YYYY-MM-DD.md)
        wiki_dir: Wiki root directory for breadcrumb generation
        date: Entry date
        source_entry_path: Path to original entry in main wiki
        source_md_path: Path to source markdown in journal

        # Manuscript metadata
        status: Manuscript status (source, quote, fragments, etc.)
        edited: Whether entry has been edited for manuscript
        entry_type: Narrative form (vignette, scene, summary, etc.)
        narrative_arc: Name of narrative arc this entry belongs to

        # Content
        notes: Adaptation notes
        character_notes: Notes about character development

        # Relationships
        characters: List of characters (with real person mapping)
        themes: List of manuscript themes
        prev_entry: Previous manuscript entry (chronological)
        next_entry: Next manuscript entry (chronological)

        # Source metadata
        word_count: Word count from source entry
        reading_time: Reading time from source entry
        age_display: Human-readable age
    """

    path: Path
    wiki_dir: Path
    date: date
    source_entry_path: Path  # Link to main wiki entry
    source_md_path: Path     # Link to journal markdown

    # Manuscript metadata
    status: str = "unspecified"
    edited: bool = False
    entry_type: Optional[str] = None
    narrative_arc: Optional[str] = None

    # Content
    notes: Optional[str] = None
    character_notes: Optional[str] = None

    # Relationships
    characters: List[Dict[str, Any]] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)
    prev_entry: Optional[Dict[str, Any]] = None
    next_entry: Optional[Dict[str, Any]] = None

    # Source metadata
    word_count: int = 0
    reading_time: float = 0.0
    age_display: str = ""

    @classmethod
    def from_database(
        cls,
        db_entry: Any,
        manuscript_entry: Any,
        wiki_dir: Path,
        journal_dir: Path,
        prev_entry: Optional[Any] = None,
        next_entry: Optional[Any] = None,
    ) -> "ManuscriptEntry":
        """
        Create ManuscriptEntry from database models.

        Args:
            db_entry: Entry database model
            manuscript_entry: ManuscriptEntry database model
            wiki_dir: Wiki root directory
            journal_dir: Journal directory
            prev_entry: Previous manuscript entry (for navigation)
            next_entry: Next manuscript entry (for navigation)

        Returns:
            ManuscriptEntry instance
        """
        # Path setup
        year = db_entry.date.year
        filename = f"{db_entry.date.isoformat()}.md"
        path = wiki_dir / "manuscript" / "entries" / str(year) / filename

        # Source paths
        main_wiki_year = db_entry.date.year
        main_wiki_filename = f"{db_entry.date.isoformat()}.md"
        source_entry_path = wiki_dir / "entries" / str(main_wiki_year) / main_wiki_filename

        # Journal source path
        source_md_path = journal_dir / "content" / "md" / str(year) / f"{db_entry.date.isoformat()}.md"

        # Characters (from entry.people with manuscript person mapping)
        characters = []
        for person in db_entry.people:
            character_info = {
                "real_name": person.display_name,
                "link": relative_link(
                    path,
                    wiki_dir / "people" / f"{person.name.lower().replace(' ', '_')}.md"
                ),
            }

            # Add character name if person has manuscript mapping
            if hasattr(person, "manuscript") and person.manuscript:
                character_info["character_name"] = person.manuscript.character
                character_info["character_link"] = relative_link(
                    path,
                    wiki_dir / "manuscript" / "characters" / f"{person.manuscript.character.lower().replace(' ', '_')}.md"
                )

            characters.append(character_info)

        # Themes (manuscript themes)
        themes = [theme.theme for theme in manuscript_entry.themes] if manuscript_entry.themes else []

        # Previous/next entries
        prev_dict = None
        if prev_entry:
            prev_year = prev_entry.date.year
            prev_filename = f"{prev_entry.date.isoformat()}.md"
            prev_path = wiki_dir / "manuscript" / "entries" / str(prev_year) / prev_filename
            prev_link = relative_link(path, prev_path)
            prev_dict = {"date": prev_entry.date, "link": prev_link}

        next_dict = None
        if next_entry:
            next_year = next_entry.date.year
            next_filename = f"{next_entry.date.isoformat()}.md"
            next_path = wiki_dir / "manuscript" / "entries" / str(next_year) / next_filename
            next_link = relative_link(path, next_path)
            next_dict = {"date": next_entry.date, "link": next_link}

        return cls(
            path=path,
            wiki_dir=wiki_dir,
            date=db_entry.date,
            source_entry_path=source_entry_path,
            source_md_path=source_md_path,
            status=manuscript_entry.status.value,
            edited=manuscript_entry.edited,
            entry_type=manuscript_entry.entry_type.value if manuscript_entry.entry_type else None,
            narrative_arc=manuscript_entry.narrative_arc,
            notes=manuscript_entry.notes,
            character_notes=manuscript_entry.character_notes,
            characters=characters,
            themes=themes,
            prev_entry=prev_dict,
            next_entry=next_dict,
            word_count=db_entry.word_count,
            reading_time=db_entry.reading_time,
            age_display=db_entry.age_display,
        )

    def to_wiki(self) -> List[str]:
        """
        Convert manuscript entry to vimwiki markdown.

        Returns:
            List of markdown lines
        """
        lines = [
            "# Palimpsest — Manuscript Entry",
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
            f"## {self.date.isoformat()}",
            "",
        ])

        # Source links
        source_entry_link = relative_link(self.path, self.source_entry_path)
        source_md_link = relative_link(self.path, self.source_md_path)

        lines.extend([
            "### Source",
            f"- **Original Entry**: [[{source_entry_link}|View in Main Wiki]]",
            f"- **Journal**: [[{source_md_link}|Read Full Entry]]",
            f"- **Date**: {self.date.isoformat()}",
            f"- **Word Count**: {self.word_count} words",
            f"- **Status**: {self.status}",
            f"- **Edited**: {'Yes' if self.edited else 'No'}",
            "",
        ])

        # Manuscript metadata
        lines.extend(["### Manuscript Metadata"])
        if self.entry_type:
            lines.append(f"- **Entry Type**: {self.entry_type}")
        if self.narrative_arc:
            # Try to link to arc page
            arc_link = f"../../arcs/{self.narrative_arc.lower().replace(' ', '_')}.md"
            lines.append(f"- **Narrative Arc**: [[{arc_link}|{self.narrative_arc}]]")
        if self.themes:
            lines.append("- **Themes**:")
            for theme in self.themes:
                theme_link = f"../../themes/{theme.lower().replace(' ', '_')}.md"
                lines.append(f"  - [[{theme_link}|{theme}]]")

        lines.append("")

        # Characters
        if self.characters:
            lines.extend(["### Characters"])
            for char in self.characters:
                if "character_name" in char:
                    # Has manuscript character mapping
                    lines.append(
                        f"- [[{char['character_link']}|{char['character_name']}]] "
                        f"(based on [[{char['link']}|{char['real_name']}]])"
                    )
                else:
                    # No manuscript mapping yet
                    lines.append(f"- [[{char['link']}|{char['real_name']}]] (no character mapping)")
            lines.append("")

        # Adaptation notes
        if self.notes:
            lines.extend([
                "### Adaptation Notes",
                self.notes,
                "",
            ])

        # Character notes
        if self.character_notes:
            lines.extend([
                "### Character Notes",
                self.character_notes,
                "",
            ])

        # Navigation
        lines.extend(["### Navigation"])
        if self.prev_entry:
            lines.append(f"- **Previous**: [[{self.prev_entry['link']}|{self.prev_entry['date']}]]")
        if self.next_entry:
            lines.append(f"- **Next**: [[{self.next_entry['link']}|{self.next_entry['date']}]]")

        if not self.prev_entry and not self.next_entry:
            lines.append("")

        return lines

    @classmethod
    def from_file(cls, path: Path) -> Optional["ManuscriptEntry"]:
        """
        Parse manuscript entry wiki file to extract editable fields.

        Args:
            path: Path to manuscript entry wiki file

        Returns:
            ManuscriptEntry with editable fields populated
        """
        if not path.exists():
            return None

        try:
            from dev.utils.wiki_parser import parse_wiki_file, extract_notes
            from datetime import datetime

            sections = parse_wiki_file(path)

            # Extract date from filename
            date_str = path.stem  # YYYY-MM-DD
            entry_date = datetime.strptime(date_str, "%Y-%m-%d").date()

            # Extract editable fields
            notes = extract_notes(sections)

            # Extract character notes
            character_notes = None
            if "character notes" in sections:
                character_notes = "\n".join(sections["character notes"]).strip()

            return cls(
                path=path,
                wiki_dir=Path("."),  # Placeholder
                date=entry_date,
                source_entry_path=Path("."),  # Placeholder
                source_md_path=Path("."),  # Placeholder
                notes=notes,
                character_notes=character_notes,
            )

        except Exception as e:
            import sys
            sys.stderr.write(f"Error parsing {path}: {e}\n")
            return None
