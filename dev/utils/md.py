#!/usr/bin/env python3
"""
md.py
-----
Markdown utilities for the Palimpsest project.

This module provides comprehensive markdown manipulation functions including:

**Frontmatter & YAML:**
- Frontmatter extraction and splitting
- YAML formatting helpers (escape, list, multiline)
- YAML frontmatter reading from files

**Section Extraction:**
- Extract markdown sections by header name
- Get all headers from document
- Find section line indexes
- Update/replace sections

**Content Manipulation:**
- Parse bullet list items
- Content hashing for change detection
- Read entry body content

**Link Utilities:**
- Compute relative links between files
- Resolve relative links back to absolute paths

Intended for use across txt2md, metadata import workflows, and dataclasses.
"""
from __future__ import annotations

# --- Standard library imports ---
import hashlib
import logging
import re
from pathlib import Path
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

# --- Third-party imports ---
import yaml

# --- Local imports ---
from .parsers import spaces_to_hyphenated

# Module logger
logger = logging.getLogger(__name__)


# --- Frontmatter & YAML ---
# ═══════════════════════════════════════════════════════════════════════════
# FRONTMATTER & YAML
# ═══════════════════════════════════════════════════════════════════════════

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


def extract_yaml_front_matter(path: Path) -> Dict[str, Any]:
    """
    Reads YAML front-matter (delimited by ---) from a markdown file.

    Uses split_frontmatter() utility for consistent parsing behavior.
    Returns a dict or empty dict on failure.

    Args:
        path: Path to markdown file

    Returns:
        Dictionary of YAML frontmatter fields, or empty dict if none/error
    """
    try:
        content = path.read_text(encoding="utf-8")
        yaml_text, _ = split_frontmatter(content)

        if not yaml_text:
            return {}

        return yaml.safe_load(yaml_text) or {}
    except Exception as exc:
        logger.warning(f"YAML parse error in {path.name}: {exc}")
        return {}


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
        hyphenated: Whether to hyphenate items (preserves existing hyphens)

    Returns:
        YAML inline list string

    Examples:
        >>> yaml_list(["simple", "list"])
        '[simple, list]'
        >>> yaml_list(["Has spaces", "Has: colon"])
        '["Has spaces", "Has: colon"]'
        >>> yaml_list(["Has spaces"], hyphenated=True)
        '["Has-spaces"]'
        >>> yaml_list(["Rue St-Hubert"], hyphenated=True)
        '["Rue_St-Hubert"]'
        >>> yaml_list([])
        '[]'
    """
    if not items:
        return "[]"

    formatted = []
    for item in items:
        if isinstance(item, str) and (" " in item or ":" in item or '"' in item):
            if hyphenated:
                item = yaml_escape(spaces_to_hyphenated(item))
            else:
                item = yaml_escape(item)
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


# ═══════════════════════════════════════════════════════════════════════════
# SECTION EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════

def extract_section(lines: List[str], header_name: str) -> List[str]:
    """
    Extracts lines under a Markdown section (e.g., '### Themes'),
    stopping at the next header of the same or higher level.

    Args:
        lines: List of content lines
        header_name: Section header to find (e.g., 'Themes', '### Category')

    Returns:
        List of lines belonging to that section (excluding the header itself)

    Examples:
        >>> lines = ["# Title", "## Section", "Content here", "## Next"]
        >>> extract_section(lines, "Section")
        ['Content here']
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
                if header_level is not None and level <= header_level:
                    break  # stop at same or higher header level
            elif title == clean_header:
                in_section = True
                header_level = level
                continue  # skip the header line itself

        elif in_section:
            section.append(ln.rstrip())
    return section


def extract_section_text(content: str, section_name: str) -> str:
    """
    Extract text content of a markdown section by name.

    Uses regex to find section content between ## headers.
    More convenient than extract_section() when working with
    file content as a string rather than a list of lines.

    Args:
        content: Full markdown content as string
        section_name: Section header to find (without ##)

    Returns:
        Section content as string, or empty string if not found

    Examples:
        >>> content = "## Summary\\nThis is summary.\\n\\n## Tags\\ntag1"
        >>> extract_section_text(content, "Summary")
        'This is summary.'
    """
    pattern = rf"## {re.escape(section_name)}\s*\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def get_all_headers(lines: List[str]) -> List[Tuple[int, str]]:
    """
    Returns a list of (level, title) tuples for all headers in the document.

    Args:
        lines: List of content lines

    Returns:
        List of tuples (header_level, header_title)

    Examples:
        >>> lines = ["# Title", "## Section 1", "### Subsection"]
        >>> get_all_headers(lines)
        [(1, 'Title'), (2, 'Section 1'), (3, 'Subsection')]
    """
    headers: List[Tuple[int, str]] = []
    for ln in lines:
        if m := re.match(r"^(#+)\s+(.*)", ln):
            level: int = len(m.group(1))
            title: str = m.group(2).strip()
            headers.append((level, title))
    return headers


def find_section_line_indexes(
    lines: List[str],
    header_name: str,
) -> Optional[Tuple[int, int]]:
    """
    Returns (start, end) line indexes for a given section.

    Section header is not included in the range.
    End index is exclusive.

    Args:
        lines: List of content lines
        header_name: Section header to find

    Returns:
        Tuple of (start_index, end_index) or None if not found

    Examples:
        >>> lines = ["# Title", "## Section", "Content", "## Next"]
        >>> find_section_line_indexes(lines, "Section")
        (2, 3)  # Content line only
    """
    clean_header: str = header_name.lstrip("#").strip()
    start: Optional[int] = None
    header_level: Optional[int] = None
    for idx, ln in enumerate(lines):
        if m := re.match(r"^(#+)\s+(.*)", ln.strip()):
            level: int = len(m.group(1))
            title: str = m.group(2).strip()
            if start is not None and header_level is not None and level <= header_level:
                return (start, idx)
            if start is None and title == clean_header:
                start = idx + 1  # section starts after header
                header_level = level
    if start is not None:
        return (start, len(lines))
    return None


def update_section(
    lines: List[str],
    header_name: str,
    new_lines: List[str],
) -> List[str]:
    """
    Replaces the section under header_name with new_lines.

    Preserves the header and rest of the document.

    Args:
        lines: Original document lines
        header_name: Section header to replace
        new_lines: New content for the section

    Returns:
        New list of lines with updated section

    Examples:
        >>> lines = ["# Title", "## Section", "Old content", "## Next"]
        >>> update_section(lines, "Section", ["New content"])
        ['# Title', '## Section', 'New content', '## Next']
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
                if header_level is not None and level <= header_level:
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


# ═══════════════════════════════════════════════════════════════════════════
# BULLET PARSING
# ═══════════════════════════════════════════════════════════════════════════

def parse_bullets(lines: List[str]) -> Set[str]:
    """
    Returns all bullet items (lines starting with '-') in the given lines.

    Args:
        lines: List of content lines

    Returns:
        Set of bullet item contents (without the '-' prefix)

    Examples:
        >>> lines = ["- Item 1", "- Item 2", "Not a bullet"]
        >>> parse_bullets(lines)
        {'Item 1', 'Item 2'}
    """
    elements: Set[str] = {
        ln[1:].strip()
        for ln in lines
        if ln.strip().startswith("-") and ln.strip() != "-"
    }
    return elements


# ═══════════════════════════════════════════════════════════════════════════
# LINK UTILITIES
# ═══════════════════════════════════════════════════════════════════════════

def relative_link(from_path: Path, to_path: Path) -> str:
    """
    Computes a Markdown-style relative link from one file to another.

    Args:
        from_path: Source file path (the file containing the link)
        to_path: Target file path (the file being linked to)

    Returns:
        Relative path from from_path to to_path

    Examples:
        >>> relative_link(Path("/wiki/people/alice.md"), Path("/journal/md/2024-01-01.md"))
        '../../journal/md/2024-01-01.md'
    """
    import os
    # Convert to absolute paths first
    from_abs = from_path.resolve()
    to_abs = to_path.resolve()

    # Get relative path from parent directory of source file
    rel_path = os.path.relpath(to_abs, from_abs.parent)

    # Convert backslashes to forward slashes for consistency (Windows)
    return rel_path.replace(os.sep, '/')


def resolve_relative_link(from_path: Path, rel_link: str) -> Path:
    """
    Resolves a Markdown-style relative link back to absolute path.

    Args:
        from_path: Source file path (the file containing the link)
        rel_link: Relative link string

    Returns:
        Absolute path to the target file

    Examples:
        >>> resolve_relative_link(Path("/wiki/people/alice.md"), "../../journal/md/2024-01-01.md")
        Path('/journal/md/2024-01-01.md')
    """
    combined = from_path.parent / rel_link
    # Resolve any '..' or '.' parts and return absolute path
    return combined.resolve()


# ═══════════════════════════════════════════════════════════════════════════
# CONTENT HASHING
# ═══════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY BODY UTILITIES
# ═══════════════════════════════════════════════════════════════════════════

def read_entry_body(file_path: Path) -> List[str]:
    """
    Read body content from markdown file (everything after frontmatter).

    Args:
        file_path: Path to markdown file

    Returns:
        List of body lines (empty list if file doesn't exist)
    """
    if not file_path.exists():
        return []
    content = file_path.read_text(encoding="utf-8")
    _, body_lines = split_frontmatter(content)
    return body_lines


def generate_placeholder_body(entry_date: date) -> List[str]:
    """
    Generate placeholder body for entries without content.

    Args:
        entry_date: Date for the entry

    Returns:
        List of placeholder body lines
    """
    return [
        f"# {entry_date.strftime('%A, %B %d, %Y')}",
        "",
        "*Body content not available - add your journal entry here*",
    ]
