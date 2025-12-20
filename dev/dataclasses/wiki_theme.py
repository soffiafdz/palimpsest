#!/usr/bin/env python3
"""
wiki_theme.py
-------------------

Defines the `WikiTheme` class, which represents a conceptual or emotional thread
that recurs across entries in the journal.

Each theme may be linked to:
- a list of entries where it appears
- associated people
- a description or annotation

Themes are compiled into `wiki/themes.md` and help structure the emotional or
narrative logic of the project.
"""
from __future__ import annotations

# --- Standard Library ---
import sys
from dataclasses import dataclass, field
from pathlib import Path
from datetime import date
from typing import Any, Dict, List, Optional, Set

# --- Local ---
from .wiki_entity import WikiEntity
from dev.utils.md import relative_link
from dev.utils.wiki import entity_path


@dataclass
class Theme(WikiEntity):
    """
    Represents a recurring conceptual thread in the journal and wiki.

    Fields:
    - path:        Path to theme's vimwiki file (wiki/themes/<theme>.md)
    - name:        Name of the theme (e.g., solitude, memory, desire)
    - description: Optional description or prose expansion
    - entries:     List of entry appearances with metadata
        - date:    Date of entry
        - md:      Path to entry.md
        - link:    Relative path to md from theme.md
        - note:    Optional note about this appearance
    - people:      Set of people associated with this theme
    - related_themes: Set of related theme names
    - notes:       Optional editorial notes

    Themes help organize the emotional and narrative arcs of the Palimpsest project.
    """
    path:           Path
    name:           str
    description:    Optional[str]        = None
    entries:        List[Dict[str, Any]] = field(default_factory=list)
    people:         Set[str]             = field(default_factory=set)
    related_themes: Set[str]             = field(default_factory=set)
    notes:          Optional[str]        = None

    # ---- Public constructors ----
    @classmethod
    def from_file(cls, path: Path) -> Optional["Theme"]:
        """
        Parse a themes/theme.md file to extract editable fields.

        Only extracts wiki-editable fields (notes, description).
        Other fields remain empty as they are database-computed.

        Args:
            path: Path to theme wiki file

        Returns:
            Theme instance with only editable fields populated, or None on error
        """
        if not path.exists():
            return None

        try:
            from dev.utils.wiki import parse_wiki_file, extract_notes

            sections = parse_wiki_file(path)

            # Extract theme name from filename
            name = path.stem.replace("_", " ").replace("-", "/").title()

            # Extract editable fields
            notes = extract_notes(sections)

            # Description is in the content right after the ## header
            description = None
            if "Description" in sections:
                desc_text = sections["Description"].strip()
                if desc_text and not desc_text.startswith("["):  # Not a placeholder
                    description = desc_text

            return cls(
                path=path,
                name=name,
                description=description,
                notes=notes,
                # All other fields left empty - they're database-computed
            )

        except Exception as e:
            sys.stderr.write(f"Error parsing {path}: {e}\n")
            return None

    @classmethod
    def from_database(
        cls,
        db_theme: Any,  # models_manuscript.Theme type
        wiki_dir: Path,
        journal_dir: Path,
    ) -> "Theme":
        """
        Construct a Theme wiki entity from a database Theme model.

        Args:
            db_theme: SQLAlchemy Theme ORM instance with relationships loaded
            wiki_dir: Base vimwiki directory (e.g., /path/to/vimwiki)
            journal_dir: Base journal directory (e.g., /path/to/journal/md)

        Returns:
            Theme wiki entity ready for serialization

        Notes:
            - Generates entry list from db_theme.entries (ManuscriptEntry objects)
            - Collects people from entries that use this theme
            - Preserves description and notes from existing wiki file if present
            - Creates relative links from wiki/themes/{name}.md to entries
        """
        # Determine output path
        path = entity_path(wiki_dir, "themes", db_theme.theme)

        # Get description and notes from existing file if it exists
        description = None
        existing_notes = None

        if path.exists():
            try:
                existing = cls.from_file(path)
                if existing:
                    description = existing.description
                    existing_notes = existing.notes
            except NotImplementedError:
                # from_file not implemented yet, skip
                pass
            except Exception as e:
                sys.stderr.write(f"Warning: Could not parse existing {path}: {e}\n")

        # Build entries list from database
        entries: List[Dict[str, Any]] = []
        people_set: Set[str] = set()

        for manuscript_entry in sorted(db_theme.entries, key=lambda e: e.date):
            if manuscript_entry.entry and manuscript_entry.entry.file_path:
                entry_path = Path(manuscript_entry.entry.file_path)
                link = relative_link(path, entry_path)

                entries.append({
                    "date": manuscript_entry.date,
                    "md": entry_path,
                    "link": link,
                    "note": "",  # Could add context from manuscript notes
                })

                # Collect people from this entry
                if hasattr(manuscript_entry.entry, 'people'):
                    for person in manuscript_entry.entry.people:
                        people_set.add(person.display_name)

        # Use existing notes if available
        notes = existing_notes if existing_notes else None

        return cls(
            path=path,
            name=db_theme.theme,
            description=description,
            entries=entries,
            people=people_set,
            related_themes=set(),  # Could analyze co-occurrence
            notes=notes,
        )

    # ---- Serialization ----
    def to_wiki(self) -> List[str]:
        """Generate vimwiki markdown for this theme using template."""
        from dev.utils.templates import render_template

        # Generate appearances list
        appearances_lines = []
        if self.entries:
            for entry in self.entries:
                date_str = entry["date"].isoformat() if isinstance(entry["date"], date) else str(entry["date"])
                link_text = f"[[{entry['link']}|{date_str}]]"
                note = f" — {entry['note']}" if entry.get('note') else ""
                appearances_lines.append(f"- {link_text}{note}")
        else:
            appearances_lines.append("- No appearances recorded")
        appearances = "\n".join(appearances_lines)

        # Generate people list
        if self.people:
            people_involved = "\n".join(f"- {person}" for person in sorted(self.people))
        else:
            people_involved = "- "

        # Prepare template variables
        variables = {
            "name": self.name.title(),
            "description": self.description or "",
            "appearances": appearances,
            "people_involved": people_involved,
            "notes": self.notes or "",
        }

        return render_template("theme", variables)

    # ---- Properties ----
    @property
    def usage_count(self) -> int:
        """Number of entries where this theme appears."""
        return len(self.entries)

    @property
    def first_appearance(self) -> Optional[date]:
        """Date of first appearance."""
        if not self.entries:
            return None
        return min(e["date"] for e in self.entries if e.get("date"))

    @property
    def last_appearance(self) -> Optional[date]:
        """Date of last appearance."""
        if not self.entries:
            return None
        return max(e["date"] for e in self.entries if e.get("date"))
