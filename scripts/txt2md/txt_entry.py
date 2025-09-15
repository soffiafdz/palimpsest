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
from typing import cast, List, Match, Optional, Tuple

# --- Third party ---
from ftfy import fix_text  # type: ignore

# --- Local imports ---
from scripts.metadata import MetadataRegistry, MetaEntry
from scripts.txt2md.txt_utils import (
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
        date (Optional[datetime.date]): Parsed date of the entry.
        header (str): Title or formatted date extracted from the entry.
        body (List[str]): Cleaned lines representing the entry's body content.
        metadata (dict): Metadata with the following keys:
            - word_count (int): Number of words in the entry.
            - reading_time_min (float): Estimated reading time in minutes.
            - status (str): Curation status ('source', 'quote', 'curated', ...).
            - excerpted (bool): Whether content has been used on manuscript.
            - epigraph (str): If/type of epigraph utilised.
            - people (Set[str]): Names of referenced people (besides narrator).
            - references (Set[str]): Dates/events referenced in the entry.
            - themes (Set[str]): Thematic tags for the entry.
            - tags (Set[str]): Additional tags or keywords.
            - manuscript_links (Set[str]): Link(s) to manuscript usage.
            - notes (str): Reviewer notes or curation comments.

    Methods:
        from_txt(cls, path: Path) -> List["TxtEntry"]:
            Parses the given .txt file and returns a list of TxtEntry instances.
        markdown_lines(self) -> List[str]:
            Returns the Markdown-formatted lines representing this entry.
        to_markdown(self) -> str:
            Returns the joined Markdown-formatted lines.
    """

    # ---- Attributes ----
    date: date
    header: str
    body: List[str]
    metadata: MetaEntry = field(default_factory=lambda: cast(MetaEntry, {}))

    # ---- Public constructors ----
    # -- Inner --
    @classmethod
    def from_lines(
        cls,
        lines: List[str],
        # TODO: Change this JSON implementation to SQLite/SQLAlchemy
        # metadata_registry: Optional[MetadataRegistry] = None,
        verbose: bool = False,
    ) -> "TxtEntry":
        if verbose:
            print("[TxtEntry] →  Parsing single entry lines...")

        # Parse entry
        date, header, raw_body = cls._parse_entry(lines)
        if verbose:
            print(f"[TxtEntry] →  Header: {header}, Date: {date}")

        # Format and reflow body
        raw_body = format_body(raw_body)
        if verbose:
            print(f"[TxtEntry] →  Body lines formatted: {len(raw_body)} lines")

        plain_lines = [txt for txt, _ in raw_body]
        wc, rt = compute_metrics(plain_lines)
        if verbose:
            print(f"[TxtEntry] →  Entry is {wc} words long; ~{rt} min reading time")

        metadata: MetaEntry = {"word_count": wc, "reading_time": rt}

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

        return cls(header=header, date=date, body=body, metadata=metadata)

    # -- Outer --
    @classmethod
    def from_file(
        cls,
        path: Path,
        metadata_registry: Optional[MetadataRegistry] = None,
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
                cls.from_lines(entry, metadata_registry, verbose=verbose)  # type: ignore
            )
        return txt_entries

    # ---- Serialization ----
    # -- Inner --
    def markdown_lines(self) -> List[str]:
        """
        Generate the lines to be written in the Markdown file.
        Including a YAML front-matter with the metadata:
            date:             self-explanatory
            word_count:       self-explanatory
            reading_time:     calculated reading time in minutes
            status
              unreviewed:     self-explanatory
              discard:        not usable
              reference:      important events, but content unusable
              fragments:      potentially useful lines/snippets
              source:         content will be rewritten
              quote:          (some) content will be adapted as is
            excerpted:        content has been pulled into manuscript draft
            epigraph
              reference:      fragment of a book|song|movie|tv series
              quote:          a quotation from someone in real life
              intention:      something that I planned/intended to say
              poem:           a poem
            location:         geographical location(s) (City, Country)
            people:           list of people referenced (besides narrator)
            references:       list of dates referenced (incl. same day)
            events:           list of events (arcs/phases) referenced
            themes:           self-explanatory
            tags:             self-explanatory
            manuscript_links: where has been utilised on
            notes:            reviewer notes
        """

        def yaml_block_list(items):
            items = sorted(items) if isinstance(items, (set, list)) else []
            if not items:
                return "[]"
            return "\n" + "\n".join(f"  - {item}" for item in items)

        location_yaml = yaml_block_list(self.metadata.get("location", []))
        people_yaml = yaml_block_list(self.metadata.get("people", []))
        references_yaml = yaml_block_list(self.metadata.get("references", []))
        events_yaml = yaml_block_list(self.metadata.get("events", []))
        themes_yaml = yaml_block_list(self.metadata.get("themes", []))
        tags_yaml = yaml_block_list(self.metadata.get("tags", []))
        links_yaml = yaml_block_list(self.metadata.get("manuscript_links", []))

        notes = self.metadata.get("notes", "")
        if notes:
            indented = ("  " + line for line in notes.splitlines())
            notes_yaml = "|\n" + "\n".join(indented)
        else:
            notes_yaml = '""'

        excerpted_val = self.metadata.get("excerpted", False)
        excerpted_yaml = "true" if excerpted_val else "false"

        # Front-matter
        fm = dedent(
            f"""\
            ---
            date: {self.date.isoformat()}
            word_count: {self.metadata.get('word_count', 0)} words
            reading_time: {self.metadata.get('reading_time', 0.0):.1f} min
            status: {self.metadata.get('status', 'unreviewed')}
            excerpted: {excerpted_yaml}
            epigraph: {self.metadata.get('epigraph', '')}
            location: {location_yaml}
            people: {people_yaml}
            references: {references_yaml}
            events: {events_yaml}
            themes: {themes_yaml}
            tags: {tags_yaml}
            manuscript_links: {links_yaml}
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
    def load_metadata(
        self, registry: Optional[MetadataRegistry], verbose: bool = False
    ) -> None:
        """Loads metadata for this entry from the registry if available."""
        if registry and self.date:
            key = self.date.isoformat()
            meta = registry.get(key)
            if meta:
                if verbose:
                    print(f"[TxtEntry] →  Found metadata for entry ({key})")
                self.metadata.update(meta)  # merges in loaded metadata
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
            - date: (optional) datetime.date parsed from metadata
            - header: a string, either TITLE or formatted DATE
            - body: list of lines after the metadata
        Supports both:
            - === DATE: YYYY-MM-DD === / === TITLE: ... ===
            - Date: YYYY-MM-DD / Title : ...
        process:
            * Recognizes both Date & Title, in any order
            * If “=== BODY ===” marker exists, body starts after it
            * Otherwise, body starts after the first blank line following metadata
            * Formats header_text: TITLE if present, else “Day, DDth Month, YYYY”
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
