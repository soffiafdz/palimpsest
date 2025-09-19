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

# import re
# from typing import Any, Dict, Tuple

# --- Third-party library imports ---
# import yaml


def get_file_hash(file_path: str | Path) -> str:
    """
    Compute MD5 hash of a file for change detection.

    Args:
        file_path (str | Path): Path to the file.

    Returns:
        str: Hexadecimal MD5 hash of the file contents.

    Raises:
        FileNotFoundError
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError

    file_bytes = path.read_bytes()
    return hashlib.md5(file_bytes).hexdigest()


# def sync_directory(self, directory: str | Path) -> int:
#     """Sync all markdown files in directory"""
#     path_dir = Path(directory)
#     md_files = path_dir.rglob("*.md")
#     updated_count = 0
#
#     for file_path in md_files:
#         if self.update_entry_from_file(str(file_path)):
#             updated_count += 1
#             if updated_count % 50 == 0:
#                 print(f"Updated {updated_count} files...")
#
#     return updated_count


# def repopulate_from_directory(
#     self, directory: str, force: bool = False
# ) -> Tuple[int, int]:
#     """Repopulate entire database from markdown files"""
#     if force:
#         backup_path = self.backup_database("before_repopulation")
#         print(f"Created backup: {backup_path}")
#         self._clear_all_entries()
#
#     return self._process_directory(directory)


# def _process_directory(self, directory: str) -> Tuple[int, int]:
#     """Process all markdown files in directory"""
#     md_files = list(Path(directory).rglob("*.md"))
#     print(f"Found {len(md_files)} markdown files to process...")
#
#     processed = 0
#     errors = 0
#
#     for file_path in md_files:
#         try:
#             if self.update_entry_from_file(str(file_path)):
#                 processed += 1
#             if processed % 100 == 0:
#                 print(f"Processed {processed} files...")
#         except Exception as e:
#             print(f"Error processing {file_path}: {e}")
#             errors += 1
#
#     print(f"Processing complete: {processed} processed, {errors} errors")
#     return processed, errors


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
    except Exception as e:
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
