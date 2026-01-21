#!/usr/bin/env python3
"""
wiki.py
-------
Utilities for parsing vimwiki markdown files and generating entity paths.

Provides functions for parsing wiki page sections, extracting editable fields,
and generating consistent file paths for wiki entities. Used by wiki2sql
for syncing wiki edits back to the database.

Functions:
    parse_wiki_file: Parse wiki file into sections dictionary
    get_section: Get content from a specific section
    extract_notes: Extract Notes section (handles placeholders)
    extract_vignette: Extract Vignette section (Person entities)
    extract_category: Extract category from Metadata section
    extract_list_items: Extract bullet items from section
    extract_metadata_field: Extract specific field from Metadata
    is_placeholder: Check if text is placeholder content
    parse_wiki_links: Parse vimwiki [[path|text]] links
    slugify: Convert name to wiki-safe filename slug
    entity_filename: Generate wiki markdown filename for entity
    entity_path: Generate full path to entity wiki file

Usage:
    from dev.utils.wiki import parse_wiki_file, slugify, entity_path

    # Parse wiki file into sections
    sections = parse_wiki_file(Path("/wiki/people/alice.md"))
    notes = sections.get("Notes")

    # Generate entity paths
    path = entity_path(wiki_dir, "people", "María José")
    # Returns: /wiki/people/maría_josé.md

    # Slugify names for filenames
    slug = slugify("New York City")  # "new_york_city"
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import re
from pathlib import Path
from typing import Dict, Optional, List


def parse_wiki_file(file_path: Path) -> Dict[str, str]:
    """
    Parse wiki file into sections.

    Extracts content under each ### header into a dictionary.

    Args:
        file_path: Path to wiki markdown file

    Returns:
        Dictionary mapping header names to section content

    Example:
        {
            "Notes": "User notes content...",
            "Vignette": "Character description...",
            "Metadata": "- Date: 2024-01-15\\n- Word Count: 500"
        }
    """
    if not file_path.exists():
        return {}

    content = file_path.read_text(encoding="utf-8")
    sections = {}

    # Split by ### headers (level 3)
    # Pattern: ### Header Name
    pattern = r'^###\s+(.+?)$'
    lines = content.split('\n')

    current_header = None
    current_content = []

    for line in lines:
        match = re.match(pattern, line)
        if match:
            # Save previous section
            if current_header:
                sections[current_header] = '\n'.join(current_content).strip()

            # Start new section
            current_header = match.group(1).strip()
            current_content = []
        else:
            if current_header:
                current_content.append(line)

    # Save last section
    if current_header:
        sections[current_header] = '\n'.join(current_content).strip()

    return sections


def get_section(sections: Dict[str, str], header: str) -> Optional[str]:
    """
    Get content from a specific section by header name.

    Simple dictionary lookup wrapper for parsed wiki sections.
    Use md.extract_section() for parsing markdown content directly.

    Args:
        sections: Dictionary from parse_wiki_file()
        header: Section header to get

    Returns:
        Section content or None if not found
    """
    return sections.get(header)


def extract_notes(sections: Dict[str, str]) -> Optional[str]:
    """
    Extract Notes section content.

    Handles placeholder text like "[Add notes...]" by returning None.

    Args:
        sections: Dictionary from parse_wiki_file()

    Returns:
        Notes content or None if empty/placeholder
    """
    notes = get_section(sections, "Notes")

    if not notes:
        return None

    # Check for placeholder text
    placeholders = [
        "[Add notes",
        "[Add your notes",
        "[User notes",
    ]

    for placeholder in placeholders:
        if notes.strip().startswith(placeholder):
            return None

    return notes.strip()


def extract_vignette(sections: Dict[str, str]) -> Optional[str]:
    """
    Extract Vignette section content (Person only).

    Handles placeholder text by returning None.

    Args:
        sections: Dictionary from parse_wiki_file()

    Returns:
        Vignette content or None if empty/placeholder
    """
    vignette = get_section(sections, "Vignette")

    if not vignette:
        return None

    # Check for placeholder text
    placeholders = [
        "[Add character",
        "[Describe character",
        "[Character description",
    ]

    for placeholder in placeholders:
        if vignette.strip().startswith(placeholder):
            return None

    return vignette.strip()


def extract_category(sections: Dict[str, str]) -> Optional[str]:
    """
    Extract category from Metadata section (Person only).

    Looks for "- **Category:** VALUE" in metadata.

    Args:
        sections: Dictionary from parse_wiki_file()

    Returns:
        Category value or None
    """
    metadata = get_section(sections, "Metadata")

    if not metadata:
        return None

    # Look for category line
    pattern = r'-\s*\*\*Category:\*\*\s*(.+?)$'
    for line in metadata.split('\n'):
        match = re.search(pattern, line, re.MULTILINE)
        if match:
            return match.group(1).strip()

    return None


def extract_list_items(section_content: str) -> List[str]:
    """
    Extract list items from markdown section.

    Extracts items starting with "- " or "* ".

    Args:
        section_content: Section content with list items

    Returns:
        List of item texts (without bullet points)
    """
    if not section_content:
        return []

    items = []
    for line in section_content.split('\n'):
        line = line.strip()
        if line.startswith('- '):
            items.append(line[2:].strip())
        elif line.startswith('* '):
            items.append(line[2:].strip())

    return items


def is_placeholder(text: Optional[str]) -> bool:
    """
    Check if text is a placeholder.

    Returns True if text is None, empty, or looks like placeholder text.

    Args:
        text: Text to check

    Returns:
        True if placeholder, False otherwise
    """
    if not text:
        return True

    text = text.strip()

    # Common placeholder patterns
    placeholders = [
        "[Add ",
        "[User ",
        "[Describe ",
        "[Character ",
        "[Write ",
    ]

    for placeholder in placeholders:
        if text.startswith(placeholder):
            return True

    return False


def extract_metadata_field(sections: Dict[str, str], field_name: str) -> Optional[str]:
    """
    Extract a specific field from Metadata section.

    Looks for "- **FieldName:** VALUE" pattern.

    Args:
        sections: Dictionary from parse_wiki_file()
        field_name: Field name to extract (e.g., "Category", "Status")

    Returns:
        Field value or None
    """
    metadata = get_section(sections, "Metadata")

    if not metadata:
        return None

    # Look for field line (case insensitive)
    pattern = rf'-\s*\*\*{re.escape(field_name)}:\*\*\s*(.+?)$'
    for line in metadata.split('\n'):
        match = re.search(pattern, line, re.IGNORECASE | re.MULTILINE)
        if match:
            value = match.group(1).strip()
            return value if value else None

    return None


def parse_wiki_links(text: str) -> List[Dict[str, str]]:
    """
    Parse vimwiki links from text.

    Vimwiki link format: [[path/to/file.md|Display Text]]

    Args:
        text: Text containing wiki links

    Returns:
        List of dicts with 'path' and 'text' keys
    """
    links = []

    # Pattern: [[path|text]]
    pattern = r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]'

    for match in re.finditer(pattern, text):
        path = match.group(1).strip()
        display_text = match.group(2).strip() if match.group(2) else path

        links.append({
            'path': path,
            'text': display_text
        })

    return links


def slugify(name: str) -> str:
    """
    Convert name to wiki-safe filename slug.

    Transforms a display name into a safe slug for use in file paths
    and wiki links. Handles spaces and special characters.

    Rules:
    - Lowercase the string
    - Replace spaces with underscores
    - Replace forward slashes with hyphens

    Args:
        name: Display name to slugify

    Returns:
        Wiki-safe slug

    Examples:
        >>> slugify("María José")
        'maría_josé'
        >>> slugify("The Person/Character")
        'the_person-character'
        >>> slugify("New York City")
        'new_york_city'
    """
    return name.lower().replace(" ", "_").replace("/", "-")


def entity_filename(name: str) -> str:
    """
    Generate wiki markdown filename for an entity.

    Args:
        name: Entity display name

    Returns:
        Filename with .md extension

    Examples:
        >>> entity_filename("María José")
        'maría_josé.md'
    """
    return f"{slugify(name)}.md"


def entity_path(wiki_dir: Path, subdir: str, name: str) -> Path:
    """
    Generate standard entity path within wiki directory.

    Args:
        wiki_dir: Root wiki directory
        subdir: Entity type subdirectory (e.g., "people", "locations")
        name: Entity display name

    Returns:
        Full path to entity wiki file

    Examples:
        >>> entity_path(Path("/wiki"), "people", "María José")
        PosixPath('/wiki/people/maría_josé.md')
    """
    return wiki_dir / subdir / entity_filename(name)
