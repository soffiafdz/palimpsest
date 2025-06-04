#!/usr/bin/env python3
"""
dataclasses.py
-------------------

Defines the TxtEntry dataclass representing individual journal entries parsed
from raw 750words .txt export files.

Each TxtEntry instance contains:
- raw source lines
- extracted metadata
- body content

It supports construction from raw text and formatting for Markdown output.

This class is used exclusively within the txt2md pipeline.
"""

from dataclasses import dataclass
from typing import List, Optional
import datetime
from pathlib import Path

# from ..paths import ROOT

@dataclass
class TxtEntry:
    """
    Represents a single journal entry parsed from raw text export (.txt).

    Attributes:
        raw_lines (List[str]): Original raw text lines from the source file.
        header (str): Title or formatted date extracted from the entry.
        body (List[str]): Cleaned lines representing the entry's body content.
        date (Optional[datetime.date]): Parsed date of the entry.
        word_count (int): Number of words in the entry.
        reading_time_min (float): Estimated reading time in minutes.

    Methods:
        from_txt(cls, path: Path) -> List["TxtEntry"]:
            Parses the given .txt file and returns a list of TxtEntry instances.
        to_markdown(self) -> List[str]:
            Returns the Markdown-formatted lines representing this entry.
    """

    raw_lines: List[str]
    header: str
    body: List[str]
    date: Optional[datetime.date]
    word_count: int
    reading_time_min: float

    # Implement your parsing, formatting methods here...
    @classmethod
    def from_file(cls, path: Path) -> List["TxtEntry"]:
        """Parse a people/person.md file to create a Person object."""
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception as e:
            sys.stderr.write(f"Error reading {path}: {e}\n")
            return None

        # --- Construction ---
        # -- name --
        name = cls._parse_name(lines)
        # -- category --
        category = cls._parse_category(lines)
        # -- alias --
        alias = cls._parse_alias(lines)
        # -- themes --
        themes = cls._parse_themes(lines)
        # -- vignettes --
        vignettes = cls._parse_vignettes(lines, path.parent)
        # -- notes --
        notes = cls._parse_notes(lines)

        return cls(
            path=path,
            name=name,
            category=category,
            alias=alias,
            # appearances are constructed fully from Markdown Entries
            themes=themes,
            vignettes=vignettes,
            notes=notes
        )

