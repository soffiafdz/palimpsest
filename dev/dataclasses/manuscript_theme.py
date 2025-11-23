#!/usr/bin/env python3
"""
manuscript_theme.py
-------------------
Dataclass for manuscript theme wiki pages.

Represents thematic elements tracked in manuscript entries (different from main wiki themes).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from dev.dataclasses.wiki_entity import WikiEntity
from dev.utils.md import relative_link


@dataclass
class Theme(WikiEntity):
    """
    Represents a manuscript theme.

    A thematic element tracked specifically for manuscript content,
    separate from general journal tags.

    Attributes:
        path: Path to theme wiki file (wiki/manuscript/themes/theme.md)
        wiki_dir: Wiki root directory for breadcrumb generation
        name: Theme name
        description: Description of the theme

        # Usage
        entries: List of manuscript entries using this theme
        first_used: Date when theme was first used
        last_used: Date when theme was last used
        usage_count: Number of entries using this theme
        total_word_count: Total word count across themed entries

        # Notes
        notes: Editorial notes about this theme
    """

    path: Path
    wiki_dir: Path
    name: str
    description: Optional[str] = None

    # Usage
    entries: List[Dict[str, Any]] = field(default_factory=list)
    first_used: Optional[date] = None
    last_used: Optional[date] = None
    usage_count: int = 0
    total_word_count: int = 0

    # Notes
    notes: Optional[str] = None

    @classmethod
    def from_database(
        cls,
        db_theme: Any,
        wiki_dir: Path,
        journal_dir: Path,
    ) -> "Theme":
        """
        Create Theme from database model.

        Args:
            db_theme: Theme database model
            wiki_dir: Wiki root directory
            journal_dir: Journal directory (unused but kept for consistency)

        Returns:
            Theme instance
        """
        # Path setup
        theme_slug = db_theme.theme.lower().replace(" ", "_")
        path = wiki_dir / "manuscript" / "themes" / f"{theme_slug}.md"

        # Entries using this theme
        entries = []
        for ms_entry in db_theme.entries:
            entry_year = ms_entry.entry.date.year
            entry_path = wiki_dir / "manuscript" / "entries" / str(entry_year) / f"{ms_entry.entry.date.isoformat()}.md"
            entries.append({
                "date": ms_entry.entry.date.isoformat(),
                "link": relative_link(path, entry_path),
                "word_count": ms_entry.entry.word_count,
            })

        # Sort by date
        entries.sort(key=lambda x: x["date"])

        # Usage statistics
        first_used = entries[0]["date"] if entries else None
        last_used = entries[-1]["date"] if entries else None
        usage_count = len(entries)
        total_word_count = sum(entry["word_count"] for entry in entries)

        return cls(
            path=path,
            wiki_dir=wiki_dir,
            name=db_theme.theme,
            description=None,  # Not in database yet
            entries=entries,
            first_used=first_used,
            last_used=last_used,
            usage_count=usage_count,
            total_word_count=total_word_count,
            notes=None,  # Not in database yet
        )

    def to_wiki(self) -> List[str]:
        """
        Convert theme to vimwiki markdown.

        Returns:
            List of markdown lines
        """
        lines = [
            "# Palimpsest — Manuscript Theme",
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

        # Usage statistics
        lines.extend([
            "### Usage",
            f"- **Entries**: {self.usage_count}",
            f"- **Total Words**: {self.total_word_count:,}",
        ])
        if self.usage_count > 0:
            avg_words = self.total_word_count // self.usage_count
            lines.append(f"- **Average Words**: {avg_words}")
        if self.first_used:
            lines.append(f"- **First Used**: {self.first_used}")
        if self.last_used:
            lines.append(f"- **Last Used**: {self.last_used}")
        lines.append("")

        # Entries with this theme
        if self.entries:
            lines.extend(["### Entries with This Theme"])
            for entry in self.entries:
                lines.append(f"- [[{entry['link']}|{entry['date']}]] ({entry['word_count']} words)")
            lines.append("")

        # Notes
        if self.notes:
            lines.extend([
                "### Notes",
                self.notes,
                "",
            ])

        return lines

    @classmethod
    def from_file(cls, path: Path) -> Optional["Theme"]:
        """
        Parse theme wiki file to extract editable fields.

        Args:
            path: Path to theme wiki file

        Returns:
            Theme with editable fields populated
        """
        if not path.exists():
            return None

        try:
            from dev.utils.wiki import parse_wiki_file

            sections = parse_wiki_file(path)

            # Extract theme name from filename
            name = path.stem.replace("_", " ").title()

            # Extract editable fields
            description = None
            if "description" in sections:
                description = "\n".join(sections["description"]).strip()

            notes = None
            if "notes" in sections:
                notes = "\n".join(sections["notes"]).strip()

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
