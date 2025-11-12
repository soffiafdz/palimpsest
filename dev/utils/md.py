#!/usr/bin/env python3
"""
md.py
-------------------
Markdown-specific utilities for the Palimpsest project.

Provides functions for parsing and formatting Markdown files with YAML
frontmatter, including:
- Frontmatter extraction and splitting
- YAML formatting helpers
- Content hashing for change detection

This module handles Markdown structure but delegates type conversion
and validation to DataValidator.

Intended for use by md2wiki, metadata workflows, and MdEntry dataclass.
"""
from __future__ import annotations

# --- Standard library imports ---
import hashlib
from pathlib import Path
from datetime import date
from typing import Any, List

from .parsers import spaces_to_hyphenated


# ----- YAML Frontmatter Parsing -----
def split_frontmatter(content: str) -> tuple[str, List[str]]:
    """
    Split markdown content into YAML frontmatter and body.

    Expected format:
        ---
        yaml: content
        ---

        Body content here...

    Args:
        content: Full markdown file content

    Returns:
        Tuple of (frontmatter_text, body_lines)
        - frontmatter_text: YAML content as string (empty if no frontmatter)
        - body_lines: List of body content lines

    Examples:
        >>> content = "---\\ndate: 2024-01-15\\n---\\n\\nBody text"
        >>> fm, body = split_frontmatter(content)
        >>> fm
        'date: 2024-01-15'
        >>> body
        ['Body text']
    """
    lines = content.splitlines()

    if not lines or lines[0].strip() != "---":
        return "", lines

    # Find closing ---
    frontmatter_end = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            frontmatter_end = i
            break

    if frontmatter_end is None:
        return "", lines

    frontmatter_lines = lines[1:frontmatter_end]
    body_lines = lines[frontmatter_end + 1 :]

    # Remove empty lines at start of body
    while body_lines and body_lines[0].strip() == "":
        body_lines.pop(0)

    return "\n".join(frontmatter_lines), body_lines


# ----- YAML Formatting Helpers -----
def yaml_escape(value: str) -> str:
    """
    Escape string for safe YAML output.

    Handles quotes and newlines that could break YAML syntax.

    Args:
        value: String to escape

    Returns:
        Escaped string safe for YAML

    Examples:
        >>> yaml_escape('He said "hello"')
        'He said \\\\"hello\\\\"'
        >>> yaml_escape('Line 1\\nLine 2')
        'Line 1\\\\nLine 2'
    """
    return value.replace('"', '\\"').replace("\n", "\\n")


def yaml_list(items: List[Any], hyphenated: bool = False) -> str:
    """
    Format list for inline YAML output.

    Generates compact bracket notation for lists, properly quoting
    strings that contain special characters.

    Args:
        items: List of items to format
        hyphenated: Whether to hyphenate items

    Returns:
        YAML inline list string

    Examples:
        >>> yaml_list(["simple", "list"])
        '[simple, list]'
        >>> yaml_list(["Has spaces", "Has: colon"])
        '["Has spaces", "Has: colon"]'
        >>> yaml_list(["Has spaces"], hyphenated=True)
        '["Has-spaces"]'
        >>> yaml_list([])
        '[]'
    """
    if not items:
        return "[]"

    formatted = []
    for item in items:
        if isinstance(item, str) and (" " in item or ":" in item or '"' in item):
            item = (
                yaml_escape(spaces_to_hyphenated(item))
                if hyphenated
                else yaml_escape(item)
            )
            formatted.append(f'"{item}"')
        else:
            formatted.append(str(item))

    return f"[{', '.join(formatted)}]"


def yaml_multiline(text: str) -> str:
    """
    Format text for YAML multiline output.

    Uses pipe notation (|) for multiline strings, or quotes for single lines.

    Args:
        text: Text to format

    Returns:
        YAML-formatted string (multiline or quoted)

    Examples:
        >>> yaml_multiline("Single line")
        '"Single line"'
        >>> yaml_multiline("Line 1\\nLine 2")
        '|\\n  Line 1\\n  Line 2'
    """
    if "\n" in text:
        lines = ["|\n"]
        for line in text.splitlines():
            lines.append(f"  {line}\n")
        return "".join(lines).rstrip()
    else:
        return f'"{yaml_escape(text)}"'


# ----- Content Hashing -----
def get_text_hash(text: str) -> str:
    """
    Compute MD5 hash of text content for change detection.

    Note: MD5 is used for change detection only, not cryptographic security.
    Useful for detecting changes in file content without full comparison.

    Args:
        text: Input string to hash

    Returns:
        Hexadecimal MD5 hash string

    Examples:
        >>> get_text_hash("Hello, world!")
        '6cd3556deb0da54bca060b4c39479839'
    """
    return hashlib.md5(text.encode("utf-8")).hexdigest()


# ----- Entries -----
def read_entry_body(file_path: Path) -> List[str]:
    """Read body content from markdown file (everything after frontmatter)."""
    if not file_path.exists():
        return []
    content = file_path.read_text(encoding="utf-8")
    _, body_lines = split_frontmatter(content)
    return body_lines


def generate_placeholder_body(entry_date: date) -> List[str]:
    """Generate placeholder body for entries without content."""
    return [
        f"# {entry_date.strftime('%A, %B %d, %Y')}",
        "",
        "*Body content not available - add your journal entry here*",
    ]
