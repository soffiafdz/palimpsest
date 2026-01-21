#!/usr/bin/env python3
"""
filters.py
----------
Custom Jinja2 filters for wiki generation.

These filters handle wiki-specific operations like generating
relative links, slugifying names, and formatting dates.

Filters:
    - slugify: Convert names to URL-safe slugs
    - format_date: Format date objects
    - pluralize: Generate singular/plural strings

Globals:
    - entity_link: Generate wiki links to entity pages
    - wikilink: Generate relative wiki links between pages
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date
from pathlib import Path
from typing import Any, Optional

# --- Local imports ---
from dev.utils.wiki import slugify


def wikilink(target_path: Path, from_path: Path, label: Optional[str] = None) -> str:
    """
    Generate a relative wiki link from one path to another.

    Args:
        target_path: Absolute path to link target
        from_path: Absolute path of the file containing the link
        label: Optional display label (defaults to filename stem)

    Returns:
        Wiki-style link: [[relative/path|Label]]
    """
    try:
        rel_path = target_path.relative_to(from_path.parent)
    except ValueError:
        # Not relative, compute manually
        rel_path = Path("..") / target_path.relative_to(target_path.parent.parent)

    display = label or target_path.stem
    return f"[[{rel_path}|{display}]]"


def entity_link(entity: Any, entity_type: str, wiki_dir: Path, from_path: Path) -> str:
    """
    Generate a wiki link to an entity page.

    Args:
        entity: Database entity with a name/display_name attribute
        entity_type: Type folder (people, locations, events, etc.)
        wiki_dir: Root wiki directory
        from_path: Path of the file containing this link

    Returns:
        Wiki-style link to the entity
    """
    # Determine name and target path based on entity type
    if entity_type == "entries":
        # Entry uses date for path: entries/YYYY/YYYY-MM-DD.md
        name = entity.date.isoformat()
        year = entity.date.year
        target = wiki_dir / "entries" / str(year) / f"{name}.md"
    elif entity_type == "locations":
        # Location: locations/{city}/{name}.md
        name = entity.name
        city_slug = slugify(entity.city.city)
        target = wiki_dir / "locations" / city_slug / f"{slugify(name)}.md"
    elif entity_type == "people":
        name = entity.display_name
        target = wiki_dir / "people" / f"{slugify(name)}.md"
    elif entity_type == "cities":
        name = entity.city
        target = wiki_dir / "cities" / f"{slugify(name)}.md"
    elif entity_type == "events":
        name = entity.display_name
        target = wiki_dir / "events" / f"{slugify(entity.event)}.md"
    elif entity_type == "tags":
        name = entity.tag
        target = wiki_dir / "tags" / f"{slugify(name)}.md"
    elif entity_type == "themes":
        name = entity.theme
        target = wiki_dir / "themes" / f"{slugify(name)}.md"
    elif entity_type == "references":
        name = entity.title
        target = wiki_dir / "references" / f"{slugify(name)}.md"
    elif entity_type == "poems":
        # Handle both Poem and PoemVersion
        if hasattr(entity, 'poem'):
            # PoemVersion
            name = entity.poem.title
        else:
            # Poem
            name = entity.title
        target = wiki_dir / "poems" / f"{slugify(name)}.md"
    # Manuscript entity types
    elif entity_type == "arcs":
        name = entity.arc
        target = wiki_dir / "manuscript" / "arcs" / f"{slugify(name)}.md"
    elif entity_type == "characters":
        name = entity.character
        target = wiki_dir / "manuscript" / "characters" / f"{slugify(name)}.md"
    elif entity_type == "manuscript_entries":
        # ManuscriptEntry uses date for path: manuscript/entries/YYYY/YYYY-MM-DD.md
        name = entity.date.isoformat() if entity.date else str(entity.entry_id)
        year = entity.date.year if entity.date else "unknown"
        target = wiki_dir / "manuscript" / "entries" / str(year) / f"{name}.md"
    elif entity_type == "manuscript_events":
        name = entity.display_name
        target = wiki_dir / "manuscript" / "events" / f"{slugify(name)}.md"
    else:
        # Fallback: try common name attributes
        if hasattr(entity, 'display_name'):
            name = entity.display_name
        elif hasattr(entity, 'name'):
            name = entity.name
        elif hasattr(entity, 'title'):
            name = entity.title
        else:
            name = str(entity)
        target = wiki_dir / entity_type / f"{slugify(name)}.md"

    # Compute relative path
    try:
        rel = target.relative_to(from_path.parent)
    except ValueError:
        from_parts = from_path.parent.parts
        target_parts = target.parts
        common = 0
        for f, t in zip(from_parts, target_parts):
            if f == t:
                common += 1
            else:
                break
        ups = len(from_parts) - common
        rel = Path("/".join([".."] * ups)) / Path(*target_parts[common:])

    return f"[[{rel}|{name}]]"


def format_date(d: date, fmt: str = "%Y-%m-%d") -> str:
    """
    Format a date object.

    Args:
        d: Date to format
        fmt: strftime format string

    Returns:
        Formatted date string, or empty string if None
    """
    if d is None:
        return ""
    return d.strftime(fmt)


def format_number(n: float, decimals: int = 0) -> str:
    """
    Format a number with thousands separators and optional decimal places.

    Args:
        n: Number to format
        decimals: Number of decimal places (default 0)

    Returns:
        Formatted string with commas (e.g., "1,234,567" or "1,234.56")
    """
    if n is None:
        return ""
    if decimals > 0:
        return f"{n:,.{decimals}f}"
    return f"{int(n):,}"


def ljust(value: str, width: int) -> str:
    """
    Left-justify a string in a field of given width.

    Args:
        value: String to left-justify
        width: Total width of the field

    Returns:
        Left-justified string padded with spaces
    """
    return str(value).ljust(width)


def rjust(value: str, width: int) -> str:
    """
    Right-justify a string in a field of given width.

    Args:
        value: String to right-justify
        width: Total width of the field

    Returns:
        Right-justified string padded with spaces
    """
    return str(value).rjust(width)


def pluralize(count: int, singular: str, plural: Optional[str] = None) -> str:
    """
    Return singular or plural form based on count.

    Args:
        count: Number to check
        singular: Singular form
        plural: Plural form (defaults to singular + 's')

    Returns:
        Formatted string like "5 entries" or "1 entry"
    """
    if plural is None:
        plural = singular + "s"
    word = singular if count == 1 else plural
    return f"{count} {word}"


def register_filters(env) -> None:
    """
    Register all custom filters with a Jinja2 environment.

    Args:
        env: Jinja2 Environment instance
    """
    env.filters['slugify'] = slugify
    env.filters['format_date'] = format_date
    env.filters['format_number'] = format_number
    env.filters['pluralize'] = pluralize
    env.filters['ljust'] = ljust
    env.filters['rjust'] = rjust
    # entity_link and wikilink need context, registered as globals
    env.globals['entity_link'] = entity_link
    env.globals['wikilink'] = wikilink
