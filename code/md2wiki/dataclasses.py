#!/usr/bin/env python3
"""
dataclasses.py
-------------------

Defines the MarkdownEntry dataclass representing individual journal entries
loaded from Markdown files in the wiki.

Each MarkdownEntry instance encapsulates header, body, and metadata parsed
from .md files, and is used as read-only source material for wiki population.

This class is used exclusively within the md2wiki pipeline.
"""

from dataclasses import dataclass
from typing import List, Optional
import datetime
from pathlib import Path

@dataclass
class MarkdownEntry:
    """
    Represents a single journal entry loaded from a Markdown file.

    Attributes:
        path (Path): Filesystem path to the Markdown file.
        header (str): Entry header, typically a date or title line.
        body_lines (List[str]): Markdown lines comprising the entry body.
        date (Optional[datetime.date]): Parsed date from front matter or header.

    Methods:
        from_file(cls, path: Path) -> "MarkdownEntry":
            Loads and parses the Markdown file into an entry instance.
    """

    path: Path
    header: str
    body_lines: List[str]
    date: Optional[datetime.date]

    # Implement your file reading, parsing methods here...
