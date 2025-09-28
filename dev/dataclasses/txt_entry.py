#!/usr/bin/env python3
"""
txt_entry.py
-------------------

Defines the TxtEntry dataclass representing individual journal entries
parsed from raw 750words .txt export files.

Each TxtEntry instance contains:
- raw source lines
- extracted metadata
    - date
    - word_count
    - reading_time
- body content

It supports construction from raw text and formatting for basic Markdown output.

This class is used exclusively within the txt2md pipeline and handles ONLY
basic text conversion - no complex YAML processing nor database integration.
"""
# ----- Imports -----
# ---- Annotations ----
from __future__ import annotations

# ---- Standard library imports ----
import re
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from textwrap import dedent
from typing import List, Match, Optional, Tuple

# ---- Third party ----
from ftfy import fix_text  # type: ignore

# ---- Local imports ----
from dev.utils import txt


# ----- Logging ----
logger = logging.getLogger(__name__)


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
        word_count (int): Number of words in the entry.
        reading_time (float): Estimated reading time in minutes.

    Methods:
        from_file(cls, path: Path) -> List["TxtEntry"]:
            IN: Parses the given .txt file (monthly)
            OUT: Returns a list of TxtEntry instances (daily)
        to_markdown(self) -> str:
            Returns basic Markdown with minimal YAML frontmatter.
    """

    # ---- Attributes ----
    date: date
    header: str
    body: List[str]
    word_count: int = 0
    reading_time: float = 0.0

    # ---- Public constructors ----
    # --- Outer ---
    @classmethod
    def from_lines(
        cls,
        lines: List[str],
        verbose: bool = False,
    ) -> TxtEntry:
        if verbose:
            logger.debug("Parsing single entry lines...")

        # Parse entry
        date_obj, header, raw_body = cls._parse_entry(lines)
        if verbose:
            logger.debug(f"Header: {header}, Date: {date_obj}")

        # Format and reflow body
        raw_body = txt.format_body(raw_body)
        if verbose:
            logger.debug(f"Body lines formatted: {len(raw_body)} lines")

        # Compute metrics
        plain_lines = [txt for txt, _ in raw_body]
        wc, rt = txt.compute_metrics(plain_lines)
        if verbose:
            logger.debug(f"Entry is {wc} words long; ~{rt} min reading time")

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
                body.extend(txt.reflow_paragraph([txt for txt, _ in paragraph]))
            body.append("")  # blank line after each paragraph

        if verbose:
            logger.debug(f"Paragraphs processed: {len(paragraphs)}")

        return cls(
            date=date_obj, header=header, body=body, word_count=wc, reading_time=rt
        )

    # --- Outer ---
    @classmethod
    def from_file(
        cls,
        path: Path,
        verbose: bool = False,
    ) -> List[TxtEntry]:
        """
        Parse a single .txt monthly compilation. Generate a list of Entries.
        """
        if verbose:
            logger.debug(f"Reading file: {str(path)}")

        try:
            all_lines = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Cannot read input file: {str(path)}")
            raise OSError(f"Cannot read input file: {str(path)}") from e

        # Use ftfy to fix text before any processing is done
        all_lines = fix_text(all_lines)
        lines = all_lines.splitlines()

        if verbose:
            logger.debug(f"Total lines read: {len(lines)}")

        # Separate entries
        entries = cls._split_entries(lines, MARKERS)

        if verbose:
            logger.debug(f"Entries found: {len(entries)}")

        # Return List of TxtEntries
        txt_entries: List[TxtEntry] = []
        for idx, entry in enumerate(entries):
            if verbose:
                logger.debug(f"Parsing entry {idx + 1}/{len(entries)}")
            try:
                txt_entries.append(cls.from_lines(entry, verbose=verbose))
            except Exception as e:
                logger.error(f"Failed to parse entry {idx + 1}: {e}")
                raise

        logger.info(f"Successfully parsed {len(txt_entries)} entries from {path.name}")
        return txt_entries

    # ---- Serialization ----
    def to_markdown(self) -> str:
        """
        Generate basic Markdown content with minimal YAML frontmatter.

        Only includes computed fields: date, word_count, reading_time.
        No complex metadata - that's handled by yaml2sql/MdEntry.
        """
        # --- YAML frontmatter ---
        yaml_content = dedent(
            f"""\
            ---
            date: {self.date.isoformat()}
            word_count: {self.word_count}
            reading_time: {self.reading_time:.1f}
            ---
        """
        ).rstrip()

        # Frontmatter + header + body
        md_lines: List[str] = [yaml_content, "", f"# {self.header}", ""]
        md_lines.extend(self.body)

        return "\n".join(md_lines)

    # ---- Parser helpers ----
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
            Recognizes both Date & Title, in any order
            If “=== BODY ===” marker exists, body starts after it
            Otherwise, body starts after the first blank line following metadata
            Formats header_text: TITLE if present, else “Day, DDth Month, YYYY”
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

        if date_obj is None:
            error_msg = "Entry does not contain a valid date"
            logger.error(f"{error_msg} - first few lines: {entry[:5]}")
            raise ValueError(error_msg)

        # build header
        if title:
            header_text = title
        else:
            header_text = (
                f"{date_obj.strftime('%A')}, "
                f"{date_obj.strftime('%B')} {txt.ordinal(date_obj.day)}, "
                f"{date_obj.year}"
            )

        body_lines = entry[body_start:]

        return date_obj, header_text, body_lines
