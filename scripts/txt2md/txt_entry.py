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
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from textwrap import dedent
from typing import List, Optional

# --- Third party ---
from ftfy import fix_text

# --- Local imports ---
from scripts.txt2md.txt_utils import (
    ordinal, format_body, reflow_paragraph, compute_metrics
)


# ----- Entry markers-----
MARKERS: List[str] = ["------ ENTRY ------", "===== ENTRY ====="]


# ----- Dataclass -----
@dataclass
class TxtEntry:
    """
    Represents a single journal entry parsed from raw text export (.txt).

    Attributes:
        header (str): Title or formatted date extracted from the entry.
        date (Optional[datetime.date]): Parsed date of the entry.
        body (List[str]): Cleaned lines representing the entry's body content.
        word_count (int): Number of words in the entry.
        reading_time_min (float): Estimated reading time in minutes.

    Methods:
        from_txt(cls, path: Path) -> List["TxtEntry"]:
            Parses the given .txt file and returns a list of TxtEntry instances.
        markdown_lines(self) -> List[str]:
            Returns the Markdown-formatted lines representing this entry.
        to_markdown(self) -> str:
            Returns the joined Markdown-formatted lines.
    """
    # ---- Attributes ----
    header: str
    date: Optional[date]
    body: List[str]
    word_count: int
    reading_time_min: float


    # ---- Public constructors ----
    # -- Inner --
    @classmethod
    def from_lines(cls, lines: List[str], verbose: bool = False) -> "TxtEntry":
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
        paragraphs: List[List[str]] = []
        buffer: List[str] = []
        for ln in raw_body + [""]:
            if ln == "":
                if buffer:
                    paragraphs.append(buffer)
                    buffer = []
            else:
                buffer.append(ln)

        body: List[str] = []
        for paragraph in paragraphs:
            # if any line ends with '\' -> emit raw for hard-breaks
            if any(ln.endswith("\\") for ln in paragraph):
                body.extend(paragraph)
            else:
                body.extend(reflow_paragraph(paragraph))
            body.append("") # blank line after each paragraph

        if verbose:
            print(f"[TxtEntry] →  Paragraphs processed: {len(paragraphs)}")

        # Compute wordcount and reading time
        wc, rd = compute_metrics("\n".join(body))

        if verbose:
            print(
                "[TxtEntry] →  Metrics —"
                f"word count {wc}, reading time: {rd:2f} min"
            )

        return cls(
            header=header,
            date=date,
            body=body,
            word_count=wc,
            reading_time_min=rd
        )


    # -- Outer --
    @classmethod
    def from_file(cls, path: Path, verbose: bool = False) -> List["TxtEntry"]:
        """
        Parse a single .txt monthly compilation. Generate a list of Entries
        """
        if verbose:
            print(f"[TxtEntry] →  Reading file: {str(path)}")

        try:
            all_lines = path.read_text(encoding="utf-8")
        except Exception as e:
            raise OSError(f"Cannot read input file: {str(in_path)}")
            return []

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
            txt_entries.append(cls.from_lines(entry, verbose=verbose))
        return txt_entries


    # ---- Serialization ----
    # -- Inner --
    def markdown_lines(self) -> List[str]:
        """Generate the lines to be written in the Markdown file."""
        # Build YAML front-matter
        # Metadata:
        # textmetrics:      word-count & reading time (self-explanatory)
        # status:
        #   unreviewed:     self-explanatory
        #   discard:        not usable
        #   reference:      important events, but content unusable
        #   fragments:      potentially useful lines/snippets
        #   source:         content will be rewritten
        #   quote:          (some) content will be adapted as is
        #   curated:        has been adapted already
        # excerpted:        content has been pulled into manuscript draft
        # people:           list of people referenced (besides narrator)
        # themes:           self-explanatory
        # tags:             self-explanatory
        # manuscript_link:  where has been utilised on
        # notes:            reviewer notes
        fm: str = dedent(f"""\
            ---
            date: {self.date.isoformat()}
            word_count: {self.word_count}
            reading_time: {self.reading_time_min:.1f}
            status: source
            excerpted: false
            people: []
            themes: []
            tags: []
            manuscript_link:
              -
            notes: |
            ---
        """).rstrip()

        md_lines: List[str] = [fm]
        md_lines.extend([
            "",
            f"## {self.header}",
            ""
        ])
        md_lines.extend(self.body)
        return md_lines

    def to_markdown(self) -> str:
        """Generate the final Markdown text."""
        return "\n".join(self.markdown_lines())


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

        marker = re.compile(
            rf"^(?:{'|'.join(re.escape(m) for m in markers)})\s*$"
        )

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
    def _parse_entry(
            entry: List[str]
    ) -> Tuple[Optional[date], str, List[str]]:
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
        date_obj: Optional[date] = None
        body_lines: List[str]

        title: Optional[str] = None
        date_idx: Optional[int] = None
        body_start: Optional[int] = None


        for i, ln in enumerate(entry):
            # `= TITLE =` marker
            m: str = re.match(r"^===\s*TITLE:\s*(.+?)\s*===", ln)
            if m and title is None:
                title: str = m.group(1).strip()
                continue

            # `Title:` marker
            m: str = re.match(r"^Title:\s*(.+)$", ln)
            if m and title is None:
                title: str = m.group(1).strip()
                continue

            #  `= DATE =` marker
            m: str = re.match(r"^===\s*DATE:\s*(\d{4}-\d{2}-\d{2})\s*===", ln)
            if m and date_obj is None:
                date_obj: date = date.fromisoformat(m.group(1))
                date_idx: int = i
                continue

            # `Date:` marker
            m: str = re.match(r"^Date:\s*(\d{4}-\d{2}-\d{2})$", ln)
            if m and date_obj is None:
                date_obj: date = date.fromisoformat(m.group(1))
                date_idx: int = i
                continue

            # explicit BODY marker
            if ln.strip() == "=== BODY ===":
                body_start: int = i + 1
                break

        # if no BODY marker, find first blank line after medatada block
        if body_start is None and date_idx is not None:
            for j in range(date_idx + 1, len(entry)):
                if entry[j].strip() == "":
                    body_start: int = j + 1
                    break

        # FALLBACK:
        # If no blankline, both legacy and new --- format ---:
        # have only `Words:` and `Minutes:` after the `Date:`
        if body_start is None:
            body_start: int = (date_idx + 3) if date_idx is not None else 0

        # build header
        if title:
            header_text = title
        elif date_obj:
            header_text = (
                f"{date_obj.strftime('%A')}, "
                f"{date_obj.day}{ordinal(date_obj.day)} "
                f"{date_obj.strftime('%B')}, {date_obj.year}"
            )
        else:
            header_text = "Unknown Date"

        body_lines = entry[body_start:]

        return date_obj, header_text, body_lines
