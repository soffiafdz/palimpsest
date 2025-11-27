#!/usr/bin/env python3
"""
wiki_reference.py
-------------------

Defines the WikiReference class for tracking external references cited in journal entries.
References include quotes, citations, and references from books, articles, films, etc.
References are grouped by their source for organization.
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
class Reference(WikiEntity):
    """
    Represents an external reference or citation.

    Fields:
    - path:        Path to reference's vimwiki file (wiki/references/<source>.md)
    - source_name: Name of the source (book title, article, film, etc.)
    - source_type: Type of source (book, article, film, poem, etc.)
    - author:      Author or creator of the source
    - citations:   List of citations from this source
        - content:      The quoted or referenced content
        - description:  Brief description if no content
        - speaker:      Who said/wrote this
        - mode:         Reference mode (direct, indirect, paraphrase)
        - entry_date:   Date of entry with this citation
        - entry_link:   Link to entry
    - notes:       Optional notes about the source

    References track external sources cited throughout the journal.
    """
    path:        Path
    source_name: str
    source_type: str
    author:      Optional[str]        = None
    citations:   List[Dict[str, Any]] = field(default_factory=list)
    notes:       Optional[str]        = None

    # ---- Public constructors ----
    @classmethod
    def from_file(cls, path: Path) -> Optional["Reference"]:
        """
        Parse a references/source.md file to extract editable fields.

        Only extracts:
        - notes: User notes about the reference source

        Other fields (source_type, author, citations) are read-only and come from database.

        Args:
            path: Path to reference wiki file

        Returns:
            Reference with only editable fields populated, or None if file doesn't exist
        """
        if not path.exists():
            return None

        try:
            from dev.utils.wiki import parse_wiki_file, extract_notes

            sections = parse_wiki_file(path)

            # Extract source name from filename
            source_name = path.stem.replace("_", " ").replace("-", "/")

            # Extract notes (editable field)
            notes = extract_notes(sections)

            return cls(
                path=path,
                source_name=source_name,
                source_type="",  # Not parsed from wiki, comes from database
                author=None,  # Not parsed from wiki, comes from database
                citations=[],  # Not parsed from wiki, comes from database
                notes=notes,
            )
        except Exception as e:
            sys.stderr.write(f"Error parsing {path}: {e}\n")
            return None

    @classmethod
    def from_database(
        cls,
        db_source: Any,  # models.ReferenceSource type
        wiki_dir: Path,
        journal_dir: Path,
    ) -> "Reference":
        """
        Construct a Reference wiki entity from a database ReferenceSource model.

        Args:
            db_source: SQLAlchemy ReferenceSource ORM instance with references loaded
            wiki_dir: Base vimwiki directory
            journal_dir: Base journal directory

        Returns:
            Reference wiki entity ready for serialization

        Notes:
            - Generates citations list from db_source.references
            - Sorts citations chronologically by entry date
            - Creates relative links from wiki/references/{source}.md to entries
            - Groups all citations from the same source
        """
        # Determine output path
        source_filename = db_source.title.lower().replace(" ", "_").replace("/", "-") + ".md"
        path = wiki_dir / "references" / source_filename

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

        # Build citations list from database
        citations: List[Dict[str, Any]] = []

        for db_ref in sorted(db_source.references, key=lambda r: r.entry.date if r.entry else date.min):
            if db_ref.entry and db_ref.entry.file_path:
                entry_path = Path(db_ref.entry.file_path)
                link = relative_link(path, entry_path)

                citation_data = {
                    "content": db_ref.content,
                    "description": db_ref.description,
                    "speaker": db_ref.speaker,
                    "mode": db_ref.mode.value if hasattr(db_ref.mode, 'value') else str(db_ref.mode),
                    "entry_date": db_ref.entry.date,
                    "entry_link": link,
                }
                citations.append(citation_data)

        # Use existing notes if available
        notes = existing_notes if existing_notes else None

        return cls(
            path=path,
            source_name=db_source.title,
            source_type=db_source.type.value if hasattr(db_source.type, 'value') else str(db_source.type),
            author=db_source.author,
            citations=citations,
            notes=notes,
        )

    # ---- Serialization ----
    def to_wiki(self) -> List[str]:
        """Generate vimwiki markdown for this reference source using template."""
        from dev.utils.templates import render_template

        # Generate source info section
        source_info_lines = [f"- **Type:** {self.source_type}"]
        if self.author:
            source_info_lines.append(f"- **Author:** {self.author}")
        source_info_lines.append(f"- **Citations:** {len(self.citations)}")
        source_info = "\n".join(source_info_lines)

        # Generate citations section
        citations_content = ""
        if self.citations:
            citations_lines = []

            for citation in self.citations:
                # Citation header with date and entry link
                entry_date = citation["entry_date"]
                citations_lines.append(f"#### [[{citation['entry_link']}|{entry_date}]]")
                citations_lines.append("")

                # Mode and speaker if available
                metadata_parts = []
                if citation.get("mode"):
                    metadata_parts.append(f"*Mode: {citation['mode']}*")
                if citation.get("speaker"):
                    metadata_parts.append(f"*Speaker: {citation['speaker']}*")

                if metadata_parts:
                    citations_lines.append(" • ".join(metadata_parts))
                    citations_lines.append("")

                # Content or description
                if citation.get("content"):
                    citations_lines.append("> " + citation["content"].replace("\n", "\n> "))
                elif citation.get("description"):
                    citations_lines.append(f"*{citation['description']}*")

                citations_lines.append("")

            # Add notes at the end of citations if present
            if self.notes:
                citations_lines.append("### Notes")
                citations_lines.append(self.notes)
                citations_lines.append("")

            citations_content = "\n".join(citations_lines)
        else:
            if self.notes:
                citations_content = f"No citations recorded.\n\n### Notes\n{self.notes}\n"
            else:
                citations_content = "No citations recorded."

        # Prepare template variables
        variables = {
            "source_name": self.source_name,
            "source_info": source_info,
            "citations": citations_content,
        }

        return render_template("reference", variables)

    # ---- Properties ----
    @property
    def citation_count(self) -> int:
        """Number of citations from this source."""
        return len(self.citations)

    @property
    def first_cited(self) -> Optional[date]:
        """Date of first citation."""
        if not self.citations:
            return None
        dates = [c.get("entry_date") for c in self.citations if c.get("entry_date")]
        return min(dates) if dates else None

    @property
    def last_cited(self) -> Optional[date]:
        """Date of last citation."""
        if not self.citations:
            return None
        dates = [c.get("entry_date") for c in self.citations if c.get("entry_date")]
        return max(dates) if dates else None
