#!/usr/bin/env python3
"""
person.py
-------------------

Defines the `Person` class, representing an individual tracked in the wiki.

Each person is associated with:
- a name and category
- a list of themes
- multiple appearances (entries they appear in)
- optional vignettes and notes

This class handles parsing from and serializing to Markdown wiki files under
`wiki/people/`.
It also integrates with journal entries to track mentions and presence.
"""
from __future__ import annotations

# --- Standard Library ---
# TODO: Check that there are no imports missing
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from datetime import date
from typing import Any, Dict, List, Optional, Set, Pattern

# --- Local ---
from .wiki_entity import WikiEntity
from dev.utils.wiki import extract_section, parse_bullets, resolve_relative_link, relative_link


@dataclass
class Person(WikiEntity):
    """
    Represents a person tracked within the vimwiki system.

    Fields:
    - path:           Path to person's vimwiki file (wiki/people/<person>.md)
    - name:           Person's real name
    - category:       Classification/grouping
    - alias:          Person's alias(es) used in the manuscript.
    - appearance(s):  Dictionary of appearances
        - date:       Date of entry
        - md:         Path to entry.md
        - link:       Relative path to md from person.md
        - note:       Note added to entry
    - themes:         themes they are included in
    - vignette(s):    Dictionary of vignettes
        - title:      Title of the vignette
        - md:         Path to entry.md
        - link:       Relative path to md from person.md
        - note:       Note added to the vignette
    - notes:          Notes for the person
    Populated from journal entries.
    Tracks mentions, presence, and narrative weight.
    """
    path:         Path
    name:         str
    category:     Optional[str]        = None
    alias:        Set[str]             = field(default_factory = set)
    appearances:  List[Dict[str, Any]] = field(default_factory = list)
    themes:       Set[str]             = field(default_factory = set)
    vignettes:    List[Dict[str, Any]] = field(default_factory = list)
    notes:        Optional[str]        = None


    # ---- Public constructors ----
    @classmethod
    def from_file(cls, path: Path) -> Optional["Person"]:
        """Parse a people/person.md file to create a Person object."""
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception as e:
            sys.stderr.write(f"Error reading {path}: {e}\n")
            return None

        # --- Construction ---
        # -- name --
        name = cls._parse_name(lines)
        # -- category --
        category = cls._parse_category(lines)
        # -- alias --
        alias = cls._parse_alias(lines)
        # -- themes --
        themes = cls._parse_themes(lines)
        # -- vignettes --
        vignettes = cls._parse_vignettes(lines, path.parent)
        # -- notes --
        notes = cls._parse_notes(lines)

        return cls(
            path=path,
            name=name,
            category=category,
            alias=alias,
            # appearances are constructed fully from Markdown Entries
            themes=themes,
            vignettes=vignettes,
            notes=notes
        )

    @classmethod
    def from_database(
        cls,
        db_person: Any,  # models.Person type
        wiki_dir: Path,
        journal_dir: Path,
    ) -> "Person":
        """
        Construct a Person wiki entity from a database Person model.

        Args:
            db_person: SQLAlchemy Person ORM instance with relationships loaded
            wiki_dir: Base vimwiki directory (e.g., /path/to/vimwiki)
            journal_dir: Base journal directory (e.g., /path/to/journal/md)

        Returns:
            Person wiki entity ready for serialization

        Notes:
            - Generates appearances from db_person.dates (MentionedDate objects)
            - Generates themes from related entries
            - Preserves category and notes from existing wiki file if present
            - Creates relative links from wiki/people/{name}.md to entries
        """
        # Determine output path
        person_filename = db_person.display_name.lower().replace(" ", "_") + ".md"
        path = wiki_dir / "people" / person_filename

        # Get category and notes from existing file if it exists, otherwise use database
        category = None
        existing_notes = None
        vignettes = []

        if path.exists():
            try:
                existing = cls.from_file(path)
                if existing:
                    category = existing.category
                    existing_notes = existing.notes
                    vignettes = existing.vignettes
            except Exception as e:
                sys.stderr.write(f"Warning: Could not parse existing {path}: {e}\n")

        # Use database relation_type as category if no existing category
        if not category and db_person.relation_type:
            category = db_person.relation_type.display_name

        # Build appearances from database dates
        appearances: List[Dict[str, Any]] = []
        for mentioned_date in sorted(db_person.dates, key=lambda d: d.date):
            # Find entry for this date
            entry = next(
                (e for e in mentioned_date.entries if e.date == mentioned_date.date),
                None
            )
            if entry:
                entry_path = Path(entry.file_path)
                # Generate relative link from people/person.md to entry
                link = relative_link(path, entry_path)

                appearances.append({
                    "date": mentioned_date.date,
                    "md": entry_path,
                    "link": link,
                    "note": mentioned_date.context or "",
                })

        # Collect aliases from database
        alias_set: Set[str] = {alias_obj.alias for alias_obj in db_person.aliases}

        # Collect themes from entries
        themes: Set[str] = set()
        for entry in db_person.entries:
            # Check if entry has manuscript themes
            if hasattr(entry, 'manuscript') and entry.manuscript:
                if hasattr(entry.manuscript, 'themes') and entry.manuscript.themes:
                    themes.update(entry.manuscript.themes)

        # Use database notes if no existing notes
        notes = existing_notes if existing_notes else (db_person.notes if hasattr(db_person, 'notes') else None)

        return cls(
            path=path,
            name=db_person.display_name,
            category=category,
            alias=alias_set,
            appearances=appearances,
            themes=themes,
            vignettes=vignettes,
            notes=notes,
        )

    # ---- Serialization ----
    def to_wiki(self) -> List[str]:
        """Replace people/<person>.md from current Person metadata."""
        # -- header --
        lines = [
            "# Palimpsest — People", "",
            f"## {self.name.title()}", "",
            "### Category", f"{self.category or 'Unsorted'}", "",
        ]

        # -- alias(es) --
        lines.append(f"### Alias")
        if self.alias:
            lines += [f"- {a}" for a in sorted(self.alias)]
        else:
            lines.append("- ")

        # -- presence --
        lines += ["", "### Presence"]
        if self.mentions == 0:
            lines.append("- No appearances recorded")
        elif self.mentions == 1:
            lines.extend([
                f"- Appearance: {self.first_app_date}",
                "- Mentions: 1 entry",
                self._appearance_line("entry")
            ])
        else:
            lines.extend([
                f"- Range: {self.first_app_date} -> {self.last_app_date}",
                f"- Mentions: {self.mentions} entries",
                self._appearance_line("first"),
                self._appearance_line("last")
            ])

        # -- themes --
        lines += ["", "### Themes"]
        if self.themes:
            lines += [f"- {t}" for t in sorted(self.themes)]
        else:
            lines.append("- ")

        # -- vignettes --
        lines += ["", "### Vignettes"]
        if self.vignettes:
            lines += self._vignette_lines()
        else:
            lines.append("- ")

        # -- notes --
        lines += ["", "### Notes"]
        lines.append(self.notes or "")
        return lines


    # ---- properties----
    # -- mentions --
    @property
    def mentions(self) -> int:
        """Number of entries where the person is mentioned."""
        return len(self.appearances)


    # -- first appearance --
    @property
    def first_appearance(self) -> Optional[Dict[str, Any]]:
        """Get the person first appearance's metadata"""
        if not self.appearances:
            return None
        return min(self.appearances, key=lambda a: a["date"])


    @property
    def first_app_date(self) -> Optional[date]:
        """Return first appearance's date."""
        return self.first_appearance_value("date")


    @property
    def first_app_link(self) -> Optional[str]:
        """Return first appearance's link to entry."""
        return self.first_appearance_value("link")


    @property
    def first_app_note(self) -> Optional[str]:
        """Return first appearance's note."""
        return self.first_appearance_value("note")


    # -- last appearance --
    @property
    def last_appearance(self) -> Optional[Dict[str, Any]]:
        """Get the person last appearance's metadata"""
        if not self.appearances:
            return None
        return max(self.appearances, key=lambda a: a["date"])


    @property
    def last_app_date(self) -> Optional[date]:
        """Return last appearance's date."""
        return self.last_appearance_value("date")


    @property
    def last_app_link(self) -> Optional[str]:
        """Return last appearance's link to entry."""
        return self.last_appearance_value("link")


    @property
    def last_app_note(self) -> Optional[str]:
        """Return last appearance's note."""
        return self.last_appearance_value("note")


    # ---- appearance helpers ----
    def first_appearance_value(self, key:str) -> Optional[Any]:
        """Return specific value for key from first appearance dictionary."""
        fa = self.first_appearance
        return fa.get(key) if fa else None


    def last_appearance_value(self, key:str) -> Optional[Any]:
        """Return specific value for key from last appearance dictionary."""
        la = self.last_appearance
        return la.get(key) if la else None


    def _appearance_line(self, appearance: str) -> Optional[str]:
        """Return a formatted link-line for entry|first|last appearance."""
        if appearance not in ["entry", "first", "last"]:
            raise ValueError(
                "Argument appearance must be: 'entry', 'first' or 'last'."
            )

        if not self.first_appearance or not self.last_appearance:
            return None

        intro: str = f"-> {appearance.title()}:"

        full_link: str = f" [[{self.last_app_link}|{self.last_app_date}]]" \
                if appearance.lower() == "last" \
                else f"[[{self.first_app_link}|{self.first_app_date}]]"

        note: str = f"— {self.last_app_note}" \
                if appearance.lower() == "last" \
                else f"— {self.first_app_note}"

        return " ".join([intro, full_link, note])


    # ---- vignette helpers ----
    def _vignette_lines(self) -> List[str]:
        """Return a list of formatted link-lines for all vignettes."""
        vignette_lines: List[str] = []

        if not self.vignettes:
            return vignette_lines

        for vignette in self.vignettes:
            line_fragments: List[str] = [
                "->",
                f"[[{vignette['link']}|{vignette['title']}]]"
            ]

            if vignette["note"]:
                line_fragments.append(f"— {vignette['note']}")

            vignette_lines.append(" ".join(line_fragments))

        return vignette_lines


    # ---- parser helpers ----
    # -- name --
    @staticmethod
    def _parse_name(lines: List[str]) -> str:
        """Look into people/person.md to extract person's name."""
        name: Optional[str] = None
        for ln in lines:
            if ln.startswith("## ") and not ln.startswith("###"):
                name = ln[3:].strip()
                break
        return name if name else None


    # -- category --
    @staticmethod
    def _parse_category(lines: List[str]) -> str:
        """Look into people/person.md to extract person's category."""
        category_section: List[str] = extract_section(lines, "### Category")
        if not category_section:
            return "Unsorted"
        category: str = category_section[0]
        return category if category else "Unsorted"


    # -- alias --
    @staticmethod
    def _parse_alias(lines: List[str]) -> Set[str]:
        """Look into people/person.md to extract person's alias(es)."""
        alias_section: List[str] = extract_section(lines, "### Alias")
        alias: Set[str] = parse_bullets(alias_section)
        return alias


    # -- themes --
    @staticmethod
    def _parse_themes(lines: List[str]) -> Set[str]:
        """Extract themes written in the People/<person>.md themes section."""
        themes_section: List[str] = extract_section(lines, "### Themes")
        themes: Set[str] = parse_bullets(themes_section)
        return themes


    # -- vignettes --
    @staticmethod
    def _parse_vignettes(lines: List[str], path: Path) -> List[Dict[str, Any]]:
        """Construct vignettes dictionary from People/<person>.md."""
        vignettes: List[Dict[str, Any]] = []
        vignettes_section: List[str] = extract_section(lines, "### Vignettes")
        VIGNETTE_PATTERN: Pattern[str] = re.compile(
            r"^->\s*\[\[([^|\]]+)\|*([^\]]+)\]\](?:\s*—\s*(.*))?"
        )
        for ln in vignettes_section:
            if m := VIGNETTE_PATTERN.match(ln):
                link, title, note = m.groups()
                vignette = {
                    "md":    resolve_relative_link(path, link),
                    "link":  link,
                    "title": title,
                    "note":  note or None,
                }
                vignettes.append(vignette)
        return vignettes


    # -- notes --
    @staticmethod
    def _parse_notes(lines: List[str]) -> Optional[str]:
        """Extract notes writte in People/<person>.md"""
        notes_section: List = extract_section(lines, "### Notes")
        if notes_section:
            return "\n".join(notes_section)
        else:
            return None
