#!/usr/bin/env python3
"""
manuscript_character.py
-----------------------
Dataclass for manuscript character wiki pages.

Represents fictional characters adapted from real people in the journal,
with character-specific metadata like descriptions, arcs, and voice notes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from dev.dataclasses.wiki_entity import WikiEntity
from dev.utils.md import relative_link


@dataclass
class Character(WikiEntity):
    """
    Represents a manuscript character (adapted from a real person).

    Maps a real person from the journal to a fictional character in the
    manuscript, with character development notes and appearance tracking.

    Attributes:
        path: Path to character wiki file (wiki/manuscript/characters/character.md)
        wiki_dir: Wiki root directory for breadcrumb generation
        name: Character's fictional name
        real_person_name: Real person's name
        real_person_path: Link to real person in main wiki

        # Character development
        character_description: Physical description of character
        character_arc: Character development notes
        voice_notes: Notes about character's narrative voice
        appearance_notes: Notes about how character appears in manuscript

        # Appearances
        appearances: List of manuscript entries featuring this character
        first_appearance: Date of first appearance
        last_appearance: Date of last appearance
        total_scenes: Number of scenes character appears in
    """

    path: Path
    wiki_dir: Path
    name: str  # Character name
    real_person_name: str
    real_person_path: Path

    # Character development
    character_description: Optional[str] = None
    character_arc: Optional[str] = None
    voice_notes: Optional[str] = None
    appearance_notes: Optional[str] = None

    # Appearances
    appearances: List[Dict[str, Any]] = field(default_factory=list)
    first_appearance: Optional[date] = None
    last_appearance: Optional[date] = None
    total_scenes: int = 0

    @classmethod
    def from_database(
        cls,
        db_person: Any,
        manuscript_person: Any,
        wiki_dir: Path,
        journal_dir: Path,
    ) -> "Character":
        """
        Create Character from database models.

        Args:
            db_person: Person database model
            manuscript_person: ManuscriptPerson database model
            wiki_dir: Wiki root directory
            journal_dir: Journal directory (unused but kept for consistency)

        Returns:
            Character instance
        """
        # Path setup
        character_slug = manuscript_person.character.lower().replace(" ", "_")
        path = wiki_dir / "manuscript" / "characters" / f"{character_slug}.md"

        # Real person path
        person_slug = db_person.name.lower().replace(" ", "_")
        real_person_path = wiki_dir / "people" / f"{person_slug}.md"

        # Appearances (from manuscript entries where this person appears)
        appearances = []
        # We'll need to query manuscript entries for this person
        # For now, we'll populate this in the export function with a separate query
        # This is left empty here and will be filled by the exporter

        return cls(
            path=path,
            wiki_dir=wiki_dir,
            name=manuscript_person.character,
            real_person_name=db_person.display_name,
            real_person_path=real_person_path,
            character_description=manuscript_person.character_description,
            character_arc=manuscript_person.character_arc,
            voice_notes=manuscript_person.voice_notes,
            appearance_notes=manuscript_person.appearance_notes,
            appearances=appearances,
            first_appearance=db_person.first_appearance,
            last_appearance=db_person.last_appearance,
            total_scenes=0,  # Will be calculated from appearances
        )

    def to_wiki(self) -> List[str]:
        """
        Convert character to vimwiki markdown.

        Returns:
            List of markdown lines
        """
        lines = [
            "# Palimpsest — Character",
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

        # Based on
        real_person_link = relative_link(self.path, self.real_person_path)
        lines.extend([
            "### Based On",
            f"**Real Person**: [[{real_person_link}|{self.real_person_name}]]",
            "",
        ])

        # Character description
        if self.character_description:
            lines.extend([
                "### Character Description",
                self.character_description,
                "",
            ])

        # Character arc
        if self.character_arc:
            lines.extend([
                "### Character Arc",
                self.character_arc,
                "",
            ])

        # Voice notes
        if self.voice_notes:
            lines.extend([
                "### Voice Notes",
                self.voice_notes,
                "",
            ])

        # Appearances
        if self.appearances:
            lines.extend(["### Appearances"])
            if self.first_appearance:
                first_link = self.appearances[0].get("link", "")
                first_date = self.first_appearance.isoformat()
                lines.append(f"- **First**: [[{first_link}|{first_date}]]")
            if self.last_appearance:
                last_link = self.appearances[-1].get("link", "")
                last_date = self.last_appearance.isoformat()
                lines.append(f"- **Last**: [[{last_link}|{last_date}]]")
            lines.append(f"- **Total Scenes**: {self.total_scenes}")
            lines.append("")

            # List all appearances
            lines.append("#### Scene List")
            for appearance in self.appearances:
                date_str = appearance.get("date", "")
                link = appearance.get("link", "")
                note = appearance.get("note", "")
                if note:
                    lines.append(f"- [[{link}|{date_str}]] — {note}")
                else:
                    lines.append(f"- [[{link}|{date_str}]]")
            lines.append("")

        # Appearance notes
        if self.appearance_notes:
            lines.extend([
                "### Appearance Notes",
                self.appearance_notes,
                "",
            ])

        return lines

    @classmethod
    def from_file(cls, path: Path) -> Optional["Character"]:
        """
        Parse character wiki file to extract editable fields.

        Args:
            path: Path to character wiki file

        Returns:
            Character with editable fields populated
        """
        if not path.exists():
            return None

        try:
            from dev.utils.wiki import parse_wiki_file

            sections = parse_wiki_file(path)

            # Extract character name from filename
            name = path.stem.replace("_", " ").title()

            # Extract editable fields using extract_section for case-sensitive matching
            from dev.utils.wiki import extract_section

            character_description = extract_section(sections, "Character Description")
            if character_description:
                character_description = character_description.strip() or None

            character_arc = extract_section(sections, "Character Arc")
            if character_arc:
                character_arc = character_arc.strip() or None

            voice_notes = extract_section(sections, "Voice Notes")
            if voice_notes:
                voice_notes = voice_notes.strip() or None

            appearance_notes = extract_section(sections, "Appearance Notes")
            if appearance_notes:
                appearance_notes = appearance_notes.strip() or None

            return cls(
                path=path,
                wiki_dir=Path("."),  # Placeholder
                name=name,
                real_person_name="",  # Unknown from file alone
                real_person_path=Path("."),  # Placeholder
                character_description=character_description,
                character_arc=character_arc,
                voice_notes=voice_notes,
                appearance_notes=appearance_notes,
            )

        except Exception as e:
            import sys
            sys.stderr.write(f"Error parsing {path}: {e}\n")
            return None
