#!/usr/bin/env python3
"""
fs.py
-------------------
Set of utilities for dealing with I/O and filesystems.

It is designed to work with metadata and vimwiki integration.

Intended to be imported by the md2wiki and metadata workflow.
"""
from __future__ import annotations

# --- Standard library imports ---
import hashlib
from pathlib import Path
from datetime import date
from typing import List, Optional


def find_markdown_files(directory: Path, pattern: str = "**/*.md") -> List[Path]:
    """Find all markdown files matching pattern."""
    if not directory.exists():
        return []
    return list(directory.glob(pattern))


def should_skip_file(
    file_path: Path, existing_hash: Optional[str], force: bool = False
) -> bool:
    """Determine if file processing should be skipped based on hash comparison."""
    if force or not existing_hash:
        return False
    current_hash = get_file_hash(file_path)
    return current_hash == existing_hash


def get_file_hash(file_path: str | Path) -> str:
    """
    Compute MD5 hash of a file for change detection.

    Note: MD5 is used for change detection only, not cryptographic security.

    Args:
        file_path (str | Path): Path to the file.

    Returns:
        str: Hexadecimal MD5 hash of the file contents.

    Raises:
        FileNotFoundError: If file does not exist or is not a regular file.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found or not a regular file: {path}")

    file_bytes = path.read_bytes()
    return hashlib.md5(file_bytes).hexdigest()


def parse_date_from_filename(path: Path) -> date:
    """
    Parse a date from a filename formatted as:
        - YYYY
        - YYYY-MM
        - YYYY-MM-DD

    Falls back to the first day of the year/month if incomplete.

    Args:
        path: Path object or filename containing the date.

    Returns:
        datetime.date object corresponding to the parsed date.

    Raises:
        ValueError: If the filename does not match a supported format.
    """
    stem = path.stem  # "2023", "2023-09", or "2023-09-15"
    try:
        if len(stem) == 4:  # YYYY
            return date(int(stem), 1, 1)
        elif "-" in stem and len(stem) == 7:  # YYYY-MM
            year, month = map(int, stem.split("-"))
            return date(year, month, 1)
        elif "-" in stem and len(stem) == 10:  # YYYY-MM-DD
            year, month, day = map(int, stem.split("-"))
            return date(year, month, day)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid date format in filename: {stem}") from e

    raise ValueError(f"Unsupported date format in filename: {stem}")


def date_to_filename(date: date, precision: str = "day") -> str:
    """
    Convert a datetime.date to a filename string.

    Args:
        date: datetime.date object.
        precision: One of 'year', 'month', 'day'.

    Returns:
        Filename string without extension (e.g., '2023-09-16').
    """
    if precision == "year":
        return f"{date.year:04d}"
    elif precision == "month":
        return f"{date.year:04d}-{date.month:02d}"
    elif precision == "day":
        return date.isoformat()
    else:
        raise ValueError("precision must be 'year', 'month', or 'day'")
