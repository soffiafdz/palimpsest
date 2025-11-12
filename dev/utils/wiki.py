#!/usr/bin/env python3
"""
wiki.py
-------------------
Set of utilities for parsing, extracting, and modifying Markdown documents.

This module provides functions to:
- extract Markdown sections based on header names and levels
- parse bullet list items
- read YAML front-matter blocks
- compute relative links between files
- compute absolute links back from relative
- update or locate sections within a document by header

It is designed to work with the markdown documents used in the
Palimpsest project, especially those generated from journal entries and used
to populate vimwiki files.

Intended to be imported by both txt2md and md2wiki workflows.
"""
from __future__ import annotations

# --- Standard Library ---
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

# --- Third-party ---
import yaml
import logging

# Module logger
logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Extract a specific section
# ----------------------------------------------------------------------
def extract_section(lines: List[str], header_name: str) -> List[str]:
    """
    Extracts lines under a Markdown section (e.g., '### Themes'),
    stopping at the next header of the same or higher level.
    The `header_name` can be 'Themes', 'Category', etc.
    Returns a list of lines belonging to that section
    (excluding the header itself).
    """
    section: List[str] = []
    in_section: bool = False
    header_level: Optional[int] = None

    # Remove leading '#' and whitespace for matching section titles
    clean_header: str = header_name.lstrip("#").strip()

    for ln in lines:
        stripped: str = ln.strip()

        # Match any Markdown header
        if m := re.match(r"^(#+)\s+(.*)", stripped):
            level: int = len(m.group(1))
            title: str = m.group(2).strip()

            if in_section:
                if level <= header_level:
                    break  # stop at same or higher header level
            elif title == clean_header:
                in_section = True
                header_level = level
                continue  # skip the header line itself

        elif in_section:
            section.append(ln.rstrip())
    return section


# ----------------------------------------------------------------------
# Obtain all the headers present
# ----------------------------------------------------------------------
def get_all_headers(lines: List[str]) -> List[Tuple[int, str]]:
    """
    Returns a list of (level, title) tuples for all headers in the document.
    """
    headers: List[Tuple[int, str]] = []
    for ln in lines:
        if m := re.match(r"^(#+)\s+(.*)", ln):
            level: int = len(m.group(1))
            title: str = m.group(2).strip()
            headers.append((level, title))
    return headers


# ----------------------------------------------------------------------
# Parse elements in a list (bullets)
# ----------------------------------------------------------------------
def parse_bullets(lines: List[str]) -> Set[str]:
    """
    Returns all bullet items (lines starting with '-') in the given lines.
    """
    elements: Set[str] = {
        ln[1:].strip()
        for ln in lines
        if ln.strip().startswith("-") and ln.strip() != "-"
    }
    return elements


# ----------------------------------------------------------------------
# Parse YAML
# ----------------------------------------------------------------------
def extract_yaml_front_matter(path: Path) -> Dict[str, Any]:
    """
    Reads YAML front-matter (delimited by ---) from a markdown file.
    Returns a dict or empty dict on failure.
    """
    try:
        with path.open(encoding="utf-8") as fh:
            if fh.readline().rstrip() != "---":
                return {}
            lines: List[str] = []
            for line in fh:
                if line.rstrip() == "---":
                    break
                lines.append(line)
            yaml_text: str = "".join(lines)
        return yaml.safe_load(yaml_text) or {}
    except Exception as exc:
        logger.warning(f"YAML parse error in {path.name}: {exc}")
        return {}


# ----------------------------------------------------------------------
# Relative links
# ----------------------------------------------------------------------
def relative_link(from_path: Path, to_path: Path) -> str:
    """Computes a Markdown-style relative link from one file to another."""
    try:
        return str(to_path.relative_to(from_path.parent))
    except ValueError:
        # fallback for unrelated paths
        return str(to_path)


def resolve_relative_link(from_path: Path, rel_link: str) -> Path:
    """Resolves a Markdown-style relative link back to absolute."""
    combined = from_path.parent / rel_link
    # Resolve any '..' or '.' parts and return absolute path
    return combined.resolve()


# ----------------------------------------------------------------------
# Search for a section and obtain its place in document (line numbers)
# ----------------------------------------------------------------------
def find_section_line_indexes(
    lines: List[str],
    header_name: str,
) -> Optional[Tuple[int, int]]:
    """
    Returns (start, end) line indexes for a given section.
    Section header is not included.
    End is exclusive.
    Returns None if not found.
    """
    clean_header: str = header_name.lstrip("#").strip()
    start: Optional[int] = None
    header_level: Optional[int] = None
    for idx, ln in enumerate(lines):
        if m := re.match(r"^(#+)\s+(.*)", ln.strip()):
            level: int = len(m.group(1))
            title: str = m.group(2).strip()
            if start is not None and level <= header_level:
                return (start, idx)
            if start is None and title == clean_header:
                start = idx + 1  # section starts after header
                header_level = level
    if start is not None:
        return (start, len(lines))
    return None


# ----------------------------------------------------------------------
# Rewrite a whole section with new content
# ----------------------------------------------------------------------
def update_section(
    lines: List[str],
    header_name: str,
    new_lines: List[str],
) -> List[str]:
    """
    Replaces the section under header_name with new_lines.
    Preserves the header and rest of the document.
    Returns a new list of lines.
    """
    clean_header: str = header_name.lstrip("#").strip()
    out: List[str] = []
    in_section: bool = False
    header_level: Optional[int] = None

    for ln in lines:
        stripped: str = ln.strip()
        if m := re.match(r"^(#+)\s+(.*)", stripped):
            level: int = len(m.group(1))
            title: str = m.group(2).strip()
            if in_section:
                if level <= header_level:
                    # Insert new section and continue
                    out.extend(new_lines)
                    in_section = False
            if not in_section and title == clean_header:
                out.append(ln)
                in_section = True
                header_level = level
                continue
        if not in_section:
            out.append(ln)
    # If the section was at the end, append new_lines
    if in_section:
        out.extend(new_lines)
    return out
