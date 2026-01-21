#!/usr/bin/env python3
"""
parser.py
---------
Wiki file parser for extracting editable fields.

Parses wiki markdown files to extract user-editable fields (notes, vignettes)
for import back to the database. This replaces the wiki dataclass from_file methods.

Usage:
    from dev.wiki.parser import parse_wiki_notes

    # Extract notes from any wiki file
    notes = parse_wiki_notes(Path("wiki/people/john_doe.md"))

    # Extract with entity identifier
    data = parse_entity_file(Path("wiki/people/john_doe.md"), "person")
    # Returns: {"name": "john doe", "notes": "...", "vignettes": "..."}
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

# --- Local imports ---
from dev.utils.wiki import parse_wiki_file, extract_notes


def parse_wiki_notes(file_path: Path) -> Optional[str]:
    """
    Extract notes section from a wiki file.

    Args:
        file_path: Path to wiki markdown file

    Returns:
        Notes content or None if file doesn't exist or has no notes
    """
    if not file_path.exists():
        return None

    sections = parse_wiki_file(file_path)
    return extract_notes(sections)


def parse_person_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parse a person wiki file for import.

    Args:
        file_path: Path to person wiki file

    Returns:
        Dict with name, notes, vignettes or None if invalid
    """
    if not file_path.exists():
        return None

    sections = parse_wiki_file(file_path)
    name = file_path.stem.replace("_", " ")

    return {
        "name": name,
        "notes": extract_notes(sections),
        "vignettes": sections.get("Vignettes", "").strip() or None,
    }


def parse_entry_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parse an entry wiki file for import.

    Args:
        file_path: Path to entry wiki file (YYYY-MM-DD.md)

    Returns:
        Dict with date, notes or None if invalid
    """
    if not file_path.exists():
        return None

    sections = parse_wiki_file(file_path)

    # Extract date from filename
    try:
        entry_date = date.fromisoformat(file_path.stem)
    except ValueError:
        return None

    return {
        "date": entry_date,
        "notes": extract_notes(sections),
    }


def parse_event_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parse an event wiki file for import.

    Args:
        file_path: Path to event wiki file

    Returns:
        Dict with event name, notes or None if invalid
    """
    if not file_path.exists():
        return None

    sections = parse_wiki_file(file_path)
    event_name = file_path.stem.replace("_", " ")

    return {
        "event": event_name,
        "notes": extract_notes(sections),
    }


def parse_tag_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parse a tag wiki file for import.

    Args:
        file_path: Path to tag wiki file

    Returns:
        Dict with tag name, notes or None if invalid
    """
    if not file_path.exists():
        return None

    sections = parse_wiki_file(file_path)
    tag_name = file_path.stem.replace("_", " ")

    return {
        "tag": tag_name,
        "notes": extract_notes(sections),
    }


def parse_theme_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parse a theme wiki file for import.

    Args:
        file_path: Path to theme wiki file

    Returns:
        Dict with theme name, notes, description or None if invalid
    """
    if not file_path.exists():
        return None

    sections = parse_wiki_file(file_path)
    theme_name = file_path.stem.replace("_", " ").replace("-", "/").title()

    return {
        "theme": theme_name,
        "notes": extract_notes(sections),
        "description": sections.get("Description", "").strip() or None,
    }


def parse_manuscript_entry_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parse a manuscript entry wiki file for import.

    Args:
        file_path: Path to manuscript entry wiki file

    Returns:
        Dict with date, notes, character_notes or None if invalid
    """
    if not file_path.exists():
        return None

    sections = parse_wiki_file(file_path)

    # Extract date from filename
    try:
        entry_date = date.fromisoformat(file_path.stem)
    except ValueError:
        return None

    # Extract adaptation notes
    notes = sections.get("Adaptation Notes", "").strip() or None

    # Extract character notes
    character_notes = sections.get("Character Notes", "").strip() or None

    return {
        "date": entry_date,
        "notes": notes,
        "character_notes": character_notes,
    }


def parse_manuscript_character_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parse a manuscript character wiki file for import.

    Args:
        file_path: Path to manuscript character wiki file

    Returns:
        Dict with character fields or None if invalid
    """
    if not file_path.exists():
        return None

    sections = parse_wiki_file(file_path)
    name = file_path.stem.replace("_", " ").title()

    return {
        "name": name,
        "character_description": sections.get("Character Description", "").strip() or None,
        "character_arc": sections.get("Character Arc", "").strip() or None,
        "voice_notes": sections.get("Voice Notes", "").strip() or None,
        "appearance_notes": sections.get("Appearance Notes", "").strip() or None,
    }


def parse_manuscript_event_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parse a manuscript event wiki file for import.

    Args:
        file_path: Path to manuscript event wiki file

    Returns:
        Dict with event name, notes or None if invalid
    """
    if not file_path.exists():
        return None

    sections = parse_wiki_file(file_path)
    name = file_path.stem.replace("_", " ").title()

    # Support both header names
    notes = sections.get("Adaptation Notes", "").strip()
    if not notes:
        notes = sections.get("Manuscript Notes", "").strip()

    return {
        "name": name,
        "notes": notes or None,
    }
