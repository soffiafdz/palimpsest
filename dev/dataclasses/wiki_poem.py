#!/usr/bin/env python3
"""
wiki_poem.py
-------------------

Defines the WikiPoem class for tracking original poems written during or alongside the journal.
Each poem has a title and potentially multiple versions/revisions.
Poems can be referenced in journal entries and stored in dedicated wiki pages.
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
from dev.utils.md import relative_link


@dataclass
class Poem(WikiEntity):
    """
    Represents a poem with potentially multiple versions.

    Fields:
    - path:        Path to poem's vimwiki file (wiki/poems/<title>.md)
    - title:       Title of the poem
    - versions:    List of poem versions with metadata
        - revision_date: Date of this version
        - content:       Poem text
        - entry_date:    Date of entry where it appears (if any)
        - entry_link:    Link to entry
        - notes:         Notes about this version
    - notes:       Optional editorial notes about the poem overall

    Poems track creative writing within the journal system.
    """
    path:     Path
    title:    str
    versions: List[Dict[str, Any]] = field(default_factory=list)
    notes:    Optional[str]        = None

    # ---- Public constructors ----
    @classmethod
    def from_file(cls, path: Path) -> Optional["Poem"]:
        """
        Parse a poems/poem.md file to extract editable fields.

        Only extracts:
        - notes: User notes about the poem

        Other fields (versions, content) are read-only and come from database.

        Args:
            path: Path to poem wiki file

        Returns:
            Poem with only editable fields populated, or None if file doesn't exist
        """
        if not path.exists():
            return None

        try:
            from dev.utils.wiki import parse_wiki_file, extract_notes

            sections = parse_wiki_file(path)

            # Extract title from filename
            title = path.stem.replace("_", " ").replace("-", "/")

            # Extract notes (editable field)
            notes = extract_notes(sections)

            return cls(
                path=path,
                title=title,
                versions=[],  # Not parsed from wiki, comes from database
                notes=notes,
            )
        except Exception as e:
            sys.stderr.write(f"Error parsing {path}: {e}\n")
            return None

    @classmethod
    def from_database(
        cls,
        db_poem: Any,  # models.Poem type
        wiki_dir: Path,
        journal_dir: Path,
    ) -> "Poem":
        """
        Construct a Poem wiki entity from a database Poem model.

        Args:
            db_poem: SQLAlchemy Poem ORM instance with versions loaded
            wiki_dir: Base vimwiki directory
            journal_dir: Base journal directory

        Returns:
            Poem wiki entity ready for serialization

        Notes:
            - Generates version list from db_poem.versions
            - Sorts versions chronologically
            - Links to journal entries where poems appear
            - Creates relative links from wiki/poems/{title}.md to entries
        """
        # Determine output path
        poem_filename = db_poem.title.lower().replace(" ", "_").replace("/", "-") + ".md"
        path = wiki_dir / "poems" / poem_filename

        # Get notes from existing file if it exists
        existing_notes = None

        if path.exists():
            try:
                existing = cls.from_file(path)
                if existing:
                    existing_notes = existing.notes
            except NotImplementedError:
                pass
            except Exception as e:
                sys.stderr.write(f"Warning: Could not parse existing {path}: {e}\n")

        # Build versions list from database
        versions: List[Dict[str, Any]] = []

        for poem_version in sorted(db_poem.versions, key=lambda v: v.revision_date or date.min):
            version_data = {
                "revision_date": poem_version.revision_date,
                "content": poem_version.content,
                "entry_date": None,
                "entry_link": None,
                "notes": poem_version.notes,
            }

            # Add entry link if this version is linked to an entry
            if poem_version.entry and poem_version.entry.file_path:
                entry_path = Path(poem_version.entry.file_path)
                link = relative_link(path, entry_path)
                version_data["entry_date"] = poem_version.entry.date
                version_data["entry_link"] = link

            versions.append(version_data)

        # Use existing notes if available
        notes = existing_notes if existing_notes else None

        return cls(
            path=path,
            title=db_poem.title,
            versions=versions,
            notes=notes,
        )

    # ---- Serialization ----
    def to_wiki(self) -> List[str]:
        """Generate vimwiki markdown for this poem using template."""
        from dev.utils.templates import render_template

        # Generate version history content
        version_history_lines = []

        if len(self.versions) > 1:
            version_history_lines.append(f"### Version History ({len(self.versions)} versions)")
            version_history_lines.append("")

        for i, version in enumerate(self.versions, 1):
            # Version header
            if len(self.versions) > 1:
                version_history_lines.append(f"#### Version {i}")
                if version.get("revision_date"):
                    version_history_lines.append(f"*Revision date: {version['revision_date']}*")
                if version.get("entry_date") and version.get("entry_link"):
                    entry_date = version["entry_date"]
                    version_history_lines.append(f"*From entry: [[{version['entry_link']}|{entry_date}]]*")
                version_history_lines.append("")
            else:
                # Single version - show metadata inline
                if version.get("revision_date"):
                    version_history_lines.append(f"**Date:** {version['revision_date']}")
                if version.get("entry_date") and version.get("entry_link"):
                    entry_date = version["entry_date"]
                    version_history_lines.append(f"**Entry:** [[{version['entry_link']}|{entry_date}]]")
                version_history_lines.append("")

            # Poem content
            version_history_lines.append("```")
            version_history_lines.append(version["content"].strip())
            version_history_lines.append("```")
            version_history_lines.append("")

            # Version notes
            if version.get("notes"):
                version_history_lines.append(f"*Note: {version['notes']}*")
                version_history_lines.append("")

        # Overall notes
        if self.notes:
            version_history_lines.append("### Notes")
            version_history_lines.append(self.notes)
            version_history_lines.append("")

        version_history = "\n".join(version_history_lines)

        # Prepare template variables
        variables = {
            "title": self.title,
            "version_history": version_history,
        }

        return render_template("poem", variables)

    # ---- Properties ----
    @property
    def version_count(self) -> int:
        """Number of versions of this poem."""
        return len(self.versions)

    @property
    def latest_version(self) -> Optional[Dict[str, Any]]:
        """Get the most recent version."""
        if not self.versions:
            return None
        return max(self.versions, key=lambda v: v.get("revision_date") or date.min)

    @property
    def first_written(self) -> Optional[date]:
        """Date of first version."""
        if not self.versions:
            return None
        dates = [v.get("revision_date") for v in self.versions if v.get("revision_date")]
        return min(dates) if dates else None
