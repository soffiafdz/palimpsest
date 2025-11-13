#!/usr/bin/env python3
"""
wiki_tag.py
-------------------

Defines the WikiTag class representing a metadata tag used in the Palimpsest vimwiki system.

Tags are simple textual labels applied to entries to aid categorization,
search, and filtering within the wiki.

This module handles parsing, serialization, and management of tags.
"""
from __future__ import annotations

# --- Standard Library ---
import sys
from dataclasses import dataclass, field
from pathlib import Path
from datetime import date
from typing import Any, Dict, List, Optional

# --- Local ---
from .wiki_entity import WikiEntity
from dev.utils.wiki import relative_link


@dataclass
class Tag(WikiEntity):
    """
    Represents a single metadata tag in the wiki system.

    Fields:
    - path:        Path to tag's vimwiki file (wiki/tags/<tag>.md)
    - name:        The tag label (e.g., 'conference', 'friends', 'research')
    - description: Optional description or notes about the tag
    - entries:     List of entry appearances with metadata
        - date:    Date of entry
        - md:      Path to entry.md
        - link:    Relative path to md from tag.md
        - note:    Optional note about this appearance
    - notes:       Optional editorial notes

    Tags are used to classify and group content across entries.
    """
    path:        Path
    name:        str
    description: Optional[str]        = None
    entries:     List[Dict[str, Any]] = field(default_factory=list)
    notes:       Optional[str]        = None

    # ---- Public constructors ----
    @classmethod
    def from_file(cls, path: Path) -> Optional["Tag"]:
        """
        Parse a tags/tag.md file to extract editable fields.

        Only extracts wiki-editable fields (notes).
        Other fields remain empty as they are database-computed.

        Args:
            path: Path to tag wiki file

        Returns:
            Tag instance with only editable fields populated, or None on error
        """
        if not path.exists():
            return None

        try:
            from dev.utils.wiki_parser import parse_wiki_file, extract_notes
            import sys

            sections = parse_wiki_file(path)

            # Extract tag name from filename
            name = path.stem.replace("_", " ")

            # Extract editable fields
            notes = extract_notes(sections)

            return cls(
                path=path,
                name=name,
                notes=notes,
                # All other fields left empty - they're database-computed
            )

        except Exception as e:
            sys.stderr.write(f"Error parsing {path}: {e}\n")
            return None

    @classmethod
    def from_database(
        cls,
        db_tag: Any,  # models.Tag type
        wiki_dir: Path,
        journal_dir: Path,
    ) -> "Tag":
        """
        Construct a Tag wiki entity from a database Tag model.

        Args:
            db_tag: SQLAlchemy Tag ORM instance with relationships loaded
            wiki_dir: Base vimwiki directory (e.g., /path/to/vimwiki)
            journal_dir: Base journal directory (e.g., /path/to/journal/md)

        Returns:
            Tag wiki entity ready for serialization

        Notes:
            - Generates entry list from db_tag.entries
            - Preserves description and notes from existing wiki file if present
            - Creates relative links from wiki/tags/{name}.md to entries
            - Sorts entries chronologically
        """
        # Determine output path
        tag_filename = db_tag.tag.lower().replace(" ", "_").replace("/", "-") + ".md"
        path = wiki_dir / "tags" / tag_filename

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

        for entry in sorted(db_tag.entries, key=lambda e: e.date):
            if entry.file_path:
                entry_path = Path(entry.file_path)
                link = relative_link(path, entry_path)

                entries.append({
                    "date": entry.date,
                    "md": entry_path,
                    "link": link,
                    "note": "",  # Could add context if available
                })

        # Use existing notes if available
        notes = existing_notes if existing_notes else None

        return cls(
            path=path,
            name=db_tag.tag,
            description=description,
            entries=entries,
            notes=notes,
        )

    # ---- Serialization ----
    def to_wiki(self) -> List[str]:
        """Generate vimwiki markdown for this tag."""
        lines = [
            "# Palimpsest — Tags",
            "",
            f"## {self.name}",
            "",
        ]

        # Description
        lines.append("### Description")
        if self.description:
            lines.append(self.description)
        else:
            lines.append("")
        lines.append("")

        # Usage/Entries
        lines.append("### Entries")
        if self.entries:
            for entry in self.entries:
                date_str = entry["date"].isoformat() if isinstance(entry["date"], date) else str(entry["date"])
                link_text = f"[[{entry['link']}|{date_str}]]"
                note = f" — {entry['note']}" if entry.get('note') else ""
                lines.append(f"- {link_text}{note}")
        else:
            lines.append("- No entries with this tag")
        lines.append("")

        # Statistics
        lines.append("### Statistics")
        if self.entries:
            first = self.first_used
            last = self.last_used
            span = (last - first).days if first and last else 0
            lines.extend([
                f"- Usage count: {self.usage_count}",
                f"- First used: {first}",
                f"- Last used: {last}",
                f"- Span: {span} days",
            ])
        else:
            lines.append("- No usage data")
        lines.append("")

        # Notes
        lines.append("### Notes")
        lines.append(self.notes or "")

        return lines

    # ---- Properties ----
    @property
    def usage_count(self) -> int:
        """Number of entries using this tag."""
        return len(self.entries)

    @property
    def first_used(self) -> Optional[date]:
        """Date when tag was first used."""
        if not self.entries:
            return None
        return min(e["date"] for e in self.entries if e.get("date"))

    @property
    def last_used(self) -> Optional[date]:
        """Date when tag was last used."""
        if not self.entries:
            return None
        return max(e["date"] for e in self.entries if e.get("date"))
