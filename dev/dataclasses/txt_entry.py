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
# ---- Annotations ----
from __future__ import annotations

# ---- Standard library imports ----
import re
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from textwrap import dedent
from typing import List, Optional, Tuple

# ---- Third party ----
from ftfy import fix_text  # type: ignore

# ---- Local imports ----
from dev.utils import txt
from dev.utils.txt import ENTRY_MARKERS


# ----- Logging ----
logger = logging.getLogger(__name__)


# ----- Constants -----
LEGACY_BODY_OFFSET = 3
"""
Line offset for body start in legacy 750words format.

In the legacy format, the body begins 3 lines after the date line:
- Line 0: Date
- Line 1: Title (or blank)
- Line 2: Blank separator
- Line 3: Body starts here
"""


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
        body = cls._process_body(raw_body, verbose)

        plain_text = "\n".join(body)
        wc, rt = txt.compute_metrics([plain_text])

        if verbose:
            logger.debug(f"Entry is {wc} words long; ~{rt:.1f} min reading time")

        return cls(
            date=date_obj,
            header=header,
            body=body,
            word_count=wc,
            reading_time=rt,
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
        except (OSError, UnicodeDecodeError) as e:
            logger.error(f"Cannot read input file: {str(path)}")
            raise

        # Fix text encoding issues
        all_lines = fix_text(all_lines)
        lines = all_lines.splitlines()

        if verbose:
            logger.debug(f"Total lines read: {len(lines)}")

        # Split into individual entries
        entries = cls._split_entries(lines, list(ENTRY_MARKERS))

        if verbose:
            logger.debug(f"Entries found: {len(entries)}")

        # Parse each entry
        txt_entries: List[TxtEntry] = []
        for idx, entry in enumerate(entries):
            if verbose:
                logger.debug(f"Parsing entry {idx + 1}/{len(entries)}")
            try:
                txt_entries.append(cls.from_lines(entry, verbose=verbose))
            except (ValueError, KeyError, TypeError) as e:
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
        md_lines: List[str] = [
            yaml_content,
            "",
            f"# {self.header}",
            "",
        ]
        md_lines.extend(self.body)

        return "\n".join(md_lines)

    @classmethod
    def _process_body(
        cls,
        raw_body: List[str],
        verbose: bool = False,
    ) -> List[str]:
        """
        Process raw body lines into formatted paragraphs.

        Simplified single-pass processing that:
        1. Formats body (cleans whitespace, etc.)
        2. Groups into paragraphs
        3. Reflows prose paragraphs while preserving soft-break paragraphs
        """
        # Format body
        formatted = txt.format_body(raw_body)

        if verbose:
            logger.debug(f"Body lines formatted: {len(formatted)} lines")

        # Group into paragraphs
        paragraphs: List[List[Tuple[str, bool]]] = []
        buffer: List[Tuple[str, bool]] = []

        for ln, soft in formatted + [("", False)]:
            if ln == "":
                if buffer:
                    paragraphs.append(buffer)
                    buffer = []
            else:
                buffer.append((ln, soft))

        if verbose:
            logger.debug(f"Paragraphs grouped: {len(paragraphs)}")

        # Process paragraphs
        body: List[str] = []
        for paragraph in paragraphs:
            # If any line in paragraph has soft breaks, preserve line structure
            if any(soft for _, soft in paragraph):
                body.extend([txt for txt, _ in paragraph])
            else:
                # Otherwise reflow as prose
                body.extend(txt.reflow_paragraph([txt for txt, _ in paragraph]))
            body.append("")  # blank line after each paragraph

        return body

    # ---- Parser helpers ----
    @staticmethod
    def _split_entries(lines: List[str], markers: List[str]) -> List[List[str]]:
        """
        Split raw text lines into individual entries based on entry markers.

        Splits on any line matching the entry markers, discarding the marker
        lines and grouping surrounding lines into separate entries.

        Args:
            lines: List of raw text lines from the .txt file
            markers: List of entry marker strings to split on

        Returns:
            List of entries, where each entry is a list of lines
        """
        entries: List[List[str]] = []
        current: List[str] = []

        marker_pattern = re.compile(
            rf"^(?:{'|'.join(re.escape(m) for m in markers)})\s*$"
        )

        for line in lines:
            if marker_pattern.match(line):
                if current:
                    entries.append(current)
                current = []
            else:
                current.append(line)

        if current:
            entries.append(current)

        return entries

    @staticmethod
    def _parse_entry(entry: List[str]) -> Tuple[date, str, List[str]]:
        """
        Parse entry metadata and body.

        Supports both formats:
        - === DATE: YYYY-MM-DD === / === TITLE: ... ===
        - Date: YYYY-MM-DD / Title: ...

        Returns:
            Tuple of (date, header_text, body_lines)

        Raises:
            ValueError: If no valid date found
        """
        header_text: str
        body_lines: List[str]

        title: Optional[str] = None
        date_obj: Optional[date] = None
        date_idx: Optional[int] = None
        body_start: Optional[int] = None

        # Compile patterns once for efficiency
        title_patterns = [
            re.compile(r"^===\s*TITLE:\s*(.+?)\s*==="),
            re.compile(r"^Title:\s*(.+)$"),
        ]
        date_patterns = [
            re.compile(r"^===\s*DATE:\s*(\d{4}-\d{2}-\d{2})\s*==="),
            re.compile(r"^Date:\s*(\d{4}-\d{2}-\d{2})$"),
        ]

        for i, line in enumerate(entry):
            # Try title patterns
            if title is None:
                for pattern in title_patterns:
                    match = pattern.match(line)
                    if match:
                        title = match.group(1).strip()
                        break

            # Try date patterns
            if date_obj is None:
                for pattern in date_patterns:
                    match = pattern.match(line)
                    if match:
                        date_obj = date.fromisoformat(match.group(1))
                        date_idx = i
                        break

            # Check for explicit body marker
            if line.strip() == "=== BODY ===":
                body_start = i + 1
                break

        # Find body start if not explicitly marked
        if body_start is None and date_idx is not None:
            # Find first blank line after metadata
            for j in range(date_idx + 1, len(entry)):
                if entry[j].strip() == "":
                    body_start = j + 1
                    break

        # Fallback: body starts LEGACY_BODY_OFFSET lines after date (legacy format)
        if body_start is None:
            body_start = (date_idx + LEGACY_BODY_OFFSET) if date_idx is not None else 0

        # Validate date
        if date_obj is None:
            error_msg = "Entry does not contain a valid date"
            logger.error(f"{error_msg} - first few lines: {entry[:5]}")
            raise ValueError(error_msg)

        # Build header
        if title:
            header_text = title
        else:
            # Format as "Monday, January 1st, 2024"
            header_text = (
                f"{date_obj.strftime('%A')}, "
                f"{date_obj.strftime('%B')} {txt.ordinal(date_obj.day)}, "
                f"{date_obj.year}"
            )

        body_lines = entry[body_start:]

        return date_obj, header_text, body_lines
