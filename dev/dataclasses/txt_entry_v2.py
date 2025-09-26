#!/usr/bin/env python3
"""
txt_entry.py
-------------------

Defines the Entry dataclass representing individual journal entries parsed
from raw 750words .txt export files.

Each Entry instance contains:
- raw source lines
- extracted metadata
- body content

It supports construction from raw text and formatting for Markdown output.

This class is used exclusively within the txt2md pipeline.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from textwrap import dedent
from typing import cast, List, Match, Optional, Tuple, Dict, Any, Union

# --- Third party ---
from ftfy import fix_text  # type: ignore

# --- Local imports ---
from code.utils.txt import (
    ordinal,
    format_body,
    reflow_paragraph,
    compute_metrics,
)


# ----- Entry markers-----
MARKERS: List[str] = ["------ ENTRY ------", "===== ENTRY ====="]


# ----- Dataclass -----
@dataclass
class TxtEntry:
    """
    Represents a single journal entry parsed from raw text export (.txt).

    Attributes:
        date (date): Parsed date of the entry.
        header (str): Title or formatted date extracted from the entry.
        body (List[str]): Cleaned lines representing the entry's body content.
        metadata (Dict[str, Any]): Metadata compatible with PalimpsestDB structure:
            Core fields:
            - word_count (int): Number of words in the entry.
            - reading_time (float): Estimated reading time in minutes.
            - epigraph (Optional[str]): If/type of epigraph utilised.
            - notes (Optional[str]): Reviewer notes or curation comments.

            Relationship fields (for database integration):
            - dates (List[str]): ISO date strings referenced in the entry.
            - locations (List[str]): geographical location names.
            - people (List[str]): Names of referenced people (besides narrator).
            - references (List[Dict[str, str]]): External references with content/speaker.
            - events (List[str]): Main narrative events related to the entry.
            - poems (List[Dict[str, str]]): Poems with title/content.
            - tags (List[str]): Additional tags or keywords.

            Manuscript fields:
            - manuscript (Optional[Dict[str, Any]]): Manuscript-specific metadata
                - status (str): ManuscriptStatus enum value
                - edited (bool): Whether entry has been edited
                - themes (List[str]): Manuscript themes

    Methods:
        from_file(cls, path: Path, ...) -> List["TxtEntry"]:
            Parses the given .txt file and returns a list of TxtEntry instances.
        markdown_lines(self) -> List[str]:
            Returns the Markdown-formatted lines representing this entry.
        to_markdown(self) -> str:
            Returns the joined Markdown-formatted lines.
        get_database_metadata(self) -> Dict[str, Any]:
            Returns metadata dict formatted for PalimpsestDB.create_entry()
    """

    # ---- Attributes ----
    date: date
    header: str
    body: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ---- Public constructors ----
    # -- Inner --
    @classmethod
    def from_lines(
        cls,
        lines: List[str],
        metadata_registry=None,
        verbose: bool = False,
    ) -> "TxtEntry":
        if verbose:
            print("[TxtEntry] →  Parsing single entry lines...")

        # Parse entry
        date_obj, header, raw_body = cls._parse_entry(lines)
        if verbose:
            print(f"[TxtEntry] →  Header: {header}, Date: {date_obj}")

        # Format and reflow body
        raw_body = format_body(raw_body)
        if verbose:
            print(f"[TxtEntry] →  Body lines formatted: {len(raw_body)} lines")

        plain_lines = [txt for txt, _ in raw_body]
        wc, rt = compute_metrics(plain_lines)
        if verbose:
            print(f"[TxtEntry] →  Entry is {wc} words long; ~{rt} min reading time")

        # Initialize metadata with computed metrics
        meta: Dict[str, Any] = {
            "word_count": wc,
            "reading_time": rt,
            # Initialize empty relationship lists
            "dates": [],
            "locations": [],
            "people": [],
            "references": [],
            "events": [],
            "poems": [],
            "tags": [],
        }

        # Load from registry if available
        if metadata_registry and date_obj:
            key = date_obj.isoformat()
            registry_meta = metadata_registry.get(key, {})
            if verbose:
                if registry_meta:
                    print(f"[TxtEntry] →  Found metadata in registry for {key}")
                else:
                    print(f"[TxtEntry] →  No metadata found in registry for {key}")

            # Merge registry metadata, keeping computed metrics
            meta.update(registry_meta)
            meta["word_count"] = wc  # Always use computed values
            meta["reading_time"] = rt

        # Process paragraphs (existing logic)
        paragraphs: List[List[Tuple[str, bool]]] = []
        buffer: List[Tuple[str, bool]] = []
        for ln, soft in raw_body + [("", False)]:
            if ln == "":
                if buffer:
                    paragraphs.append(buffer)
                    buffer = []
            else:
                buffer.append((ln, soft))

        body: List[str] = []
        for paragraph in paragraphs:
            if any(soft for _, soft in paragraph):
                body.extend([txt for txt, _ in paragraph])
            else:
                body.extend(reflow_paragraph([txt for txt, _ in paragraph]))
            body.append("")  # blank line after each paragraph

        if verbose:
            print(f"[TxtEntry] →  Paragraphs processed: {len(paragraphs)}")

        return cls(header=header, date=date_obj, body=body, metadata=meta)

    # -- Outer --
    @classmethod
    def from_file(
        cls,
        path: Path,
        metadata_registry=None,
        verbose: bool = False,
    ) -> List["TxtEntry"]:
        """
        Parse a single .txt monthly compilation. Generate a list of Entries
        """
        if verbose:
            print(f"[TxtEntry] →  Reading file: {str(path)}")

        try:
            all_lines = path.read_text(encoding="utf-8")
        except Exception:
            raise OSError(f"Cannot read input file: {str(path)}")

        # Use ftfy to fix text before any processing is done
        all_lines = fix_text(all_lines)
        lines = all_lines.splitlines()

        if verbose:
            print(f"[TxtEntry] →  Total lines read: {len(lines)}")

        # Separate entries
        entries = cls._split_entries(lines, MARKERS)

        if verbose:
            print(f"[TxtEntry] →  Entries found: {len(entries)}")

        # Return List of TxtEntries
        txt_entries: List["TxtEntry"] = []
        for idx, entry in enumerate(entries):
            if verbose:
                print(f"[TxtEntry] →  Parsing entry {idx + 1}/{len(entries)}")
            txt_entries.append(
                cls.from_lines(entry, metadata_registry, verbose=verbose)
            )
        return txt_entries

    # ---- Database integration ----
    def get_database_metadata(self) -> Dict[str, Any]:
        """
        Returns metadata dict formatted for PalimpsestDB.create_entry().

        Transforms TxtEntry metadata into the format expected by the database manager.
        """
        db_meta: Dict[str, Any] = {
            "date": self.date,
            "word_count": self.metadata.get("word_count", 0),
            "reading_time": self.metadata.get("reading_time", 0.0),
            "epigraph": self.metadata.get("epigraph"),
            "notes": self.metadata.get("notes"),
        }

        # Add relationship data if present
        for field in ["dates", "locations", "people", "events", "tags"]:
            if field in self.metadata and self.metadata[field]:
                db_meta[field] = self.metadata[field]

        # Handle references (need to be dicts for database)
        if "references" in self.metadata and self.metadata["references"]:
            refs = self.metadata["references"]
            if isinstance(refs, list) and refs:
                # If already formatted as dicts, use as-is
                if isinstance(refs[0], dict):
                    db_meta["references"] = refs
                else:
                    # Convert strings to dict format
                    db_meta["references"] = [{"content": str(ref)} for ref in refs]

        # Handle poems (need to be dicts for database)
        if "poems" in self.metadata and self.metadata["poems"]:
            poems = self.metadata["poems"]
            if isinstance(poems, list) and poems:
                # If already formatted as dicts, use as-is
                if isinstance(poems[0], dict):
                    db_meta["poems"] = poems
                else:
                    # Convert strings to dict format (assume they're titles)
                    db_meta["poems"] = [
                        {
                            "title": str(poem),
                            "content": "",
                        }  # Content will be extracted later
                        for poem in poems
                    ]

        # Handle manuscript metadata
        if "manuscript" in self.metadata:
            db_meta["manuscript"] = self.metadata["manuscript"]

        return db_meta

    # ---- Serialization ----
    def markdown_lines(self) -> List[str]:
        """
        Generate the lines to be written in the Markdown file.
        Updated to match current database schema.
        """

        def yaml_block_list(items: Union[List, None]) -> str:
            """Format a list for YAML output."""
            if not items:
                return "[]"
            # Handle both string lists and dict lists
            formatted_items = []
            for item in items:
                if isinstance(item, dict):
                    # For complex items like references/poems, just show primary field
                    if "content" in item:
                        formatted_items.append(f'"{item["content"][:50]}..."')
                    elif "title" in item:
                        formatted_items.append(f'"{item["title"]}"')
                    else:
                        formatted_items.append(str(item))
                else:
                    formatted_items.append(f'"{item}"')

            return "\n" + "\n".join(f"  - {item}" for item in sorted(formatted_items))

        # Extract metadata with defaults
        locations_yaml = yaml_block_list(self.metadata.get("locations", []))
        people_yaml = yaml_block_list(self.metadata.get("people", []))
        references_yaml = yaml_block_list(self.metadata.get("references", []))
        events_yaml = yaml_block_list(self.metadata.get("events", []))
        poems_yaml = yaml_block_list(self.metadata.get("poems", []))
        tags_yaml = yaml_block_list(self.metadata.get("tags", []))

        # Handle notes with proper indentation
        notes = self.metadata.get("notes", "")
        if notes:
            indented = ("  " + line for line in notes.splitlines())
            notes_yaml = "|\n" + "\n".join(indented)
        else:
            notes_yaml = '""'

        # Handle manuscript fields
        manuscript = self.metadata.get("manuscript", {})
        status = manuscript.get("status", "unreviewed") if manuscript else "unreviewed"
        edited = manuscript.get("edited", False) if manuscript else False
        themes_yaml = (
            yaml_block_list(manuscript.get("themes", [])) if manuscript else "[]"
        )

        # Front-matter matching database schema
        fm = dedent(
            f"""\
            ---
            date: {self.date.isoformat()}
            word_count: {self.metadata.get('word_count', 0)}
            reading_time: {self.metadata.get('reading_time', 0.0):.1f}
            epigraph: "{self.metadata.get('epigraph', '')}"
            locations: {locations_yaml}
            people: {people_yaml}
            references: {references_yaml}
            events: {events_yaml}
            poems: {poems_yaml}
            tags: {tags_yaml}
            manuscript:
              status: {status}
              edited: {str(edited).lower()}
              themes: {themes_yaml}
            notes: {notes_yaml}
            ---
        """
        ).rstrip()

        md_lines: List[str] = [fm, "", f"# {self.header}", ""]
        md_lines.extend(self.body)
        return md_lines

    # -- Outer --
    def to_markdown(self) -> str:
        """Generate the final Markdown text."""
        return "\n".join(self.markdown_lines())

    # ---- Metadata loading ----
    def load_metadata(self, registry, verbose: bool = False) -> None:
        """Loads metadata for this entry from the registry if available."""
        if registry and self.date:
            key = self.date.isoformat()
            meta = registry.get(key, {})
            if meta:
                if verbose:
                    print(f"[TxtEntry] →  Found metadata for entry ({key})")
                # Preserve computed metrics
                wc, rt = self.metadata.get("word_count", 0), self.metadata.get(
                    "reading_time", 0.0
                )
                self.metadata.update(meta)
                self.metadata["word_count"] = wc
                self.metadata["reading_time"] = rt
            elif verbose:
                print(f"[TxtEntry] →  Metadata for entry ({key}) not found")

    # ---- Parser helpers ----
    # -- Entry splitter --
    @staticmethod
    def _split_entries(lines: List[str], markers: List[str]) -> List[List[str]]:
        """
        input: lines, a list of strings (each raw line from the .txt)
        output: a list of entries, where each entry is itself a list of lines
        process: splits on any line matching the two different ENTRY markers,
                 discarding the marker lines and grouping surrounding lines
        """
        entries: List[List[str]] = []
        cur: List[str] = []

        marker = re.compile(rf"^(?:{'|'.join(re.escape(m) for m in markers)})\s*$")

        for ln in lines:
            if marker.match(ln):
                if cur:
                    entries.append(cur)
                cur = []
            else:
                cur.append(ln)

        if cur:
            entries.append(cur)

        return entries

    # -- Metadata extracter --
    @staticmethod
    def _parse_entry(entry: List[str]) -> Tuple[date, str, List[str]]:
        """
        input: Entry, a list of lines belonging to a single journal entry
        output: a Tuple with
            - date: datetime.date parsed from metadata
            - header: a string, either TITLE or formatted DATE
            - body: list of lines after the metadata
        Supports both:
            - === DATE: YYYY-MM-DD === / === TITLE: ... ===
            - Date: YYYY-MM-DD / Title : ...
        process:
            * Recognizes both Date & Title, in any order
            * If "=== BODY ===" marker exists, body starts after it
            * Otherwise, body starts after the first blank line following metadata
            * Formats header_text: TITLE if present, else "Day, DDth Month, YYYY"
        """
        header_text: str
        body_lines: List[str]

        title: Optional[str] = None
        date_obj: Optional[date] = None
        date_idx: Optional[int] = None
        body_start: Optional[int] = None

        m: Optional[Match[str]]
        for i, ln in enumerate(entry):
            # `= TITLE =` marker
            m = re.match(r"^===\s*TITLE:\s*(.+?)\s*===", ln)
            if m and title is None:
                title = m.group(1).strip()
                continue

            # `Title:` marker
            m = re.match(r"^Title:\s*(.+)$", ln)
            if m and title is None:
                title = m.group(1).strip()
                continue

            #  `= DATE =` marker
            m = re.match(r"^===\s*DATE:\s*(\d{4}-\d{2}-\d{2})\s*===", ln)
            if m and date_obj is None:
                date_obj = date.fromisoformat(m.group(1))
                date_idx = i
                continue

            # `Date:` marker
            m = re.match(r"^Date:\s*(\d{4}-\d{2}-\d{2})$", ln)
            if m and date_obj is None:
                date_obj = date.fromisoformat(m.group(1))
                date_idx = i
                continue

            # explicit BODY marker
            if ln.strip() == "=== BODY ===":
                body_start = i + 1
                break

        # if no BODY marker, find first blank line after medatada block
        if body_start is None and date_idx is not None:
            for j in range(date_idx + 1, len(entry)):
                if entry[j].strip() == "":
                    body_start = j + 1
                    break

        # FALLBACK:
        # If no blankline, both legacy and new --- format ---:
        # have only `Words:` and `Minutes:` after the `Date:`
        if body_start is None:
            body_start = (date_idx + 3) if date_idx is not None else 0

        assert date_obj is not None, "Entry does not contain a valid date"

        # build header
        if title:
            header_text = title
        else:
            header_text = (
                f"{date_obj.strftime('%A')}, "
                f"{date_obj.strftime('%B')} {ordinal(date_obj.day)}, "
                f"{date_obj.year}"
            )

        body_lines = entry[body_start:]

        return date_obj, header_text, body_lines
