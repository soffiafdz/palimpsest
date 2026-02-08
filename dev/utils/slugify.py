#!/usr/bin/env python3
"""
slugify.py
----------
String slugification utilities for generating filesystem-safe filenames.

Provides functions for converting human-readable names into URL-safe,
filesystem-friendly slugs suitable for filenames and paths.

Key Features:
    - Lowercase transformation
    - Accent/diacritic normalization (María → maria)
    - Special character handling (apostrophes, parentheses, etc.)
    - Space to hyphen conversion
    - Maximum length enforcement

Usage:
    from dev.utils.slugify import slugify

    # Basic slugification
    slug = slugify("María José")  # "maria-jose"

    # Person filename
    first = slugify("María José")  # "maria-jose"
    last = slugify("Castro Lopez")  # "castro-lopez"
    filename = f"{first}_{last}.json"  # "maria-jose_castro-lopez.json"
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import re
import unicodedata


def slugify(text: str, max_length: int = 200) -> str:
    """
    Convert text to filesystem-safe slug.

    Applies transformations to make text safe for filenames and URLs:
    - Lowercase
    - Normalize accents (María → maria)
    - Remove apostrophes (maria's → marias)
    - Remove parentheses and brackets
    - Replace spaces with hyphens
    - Strip special characters
    - Collapse multiple hyphens

    Args:
        text: Input text to slugify
        max_length: Maximum slug length (default 200)

    Returns:
        Slugified string safe for filenames

    Examples:
        >>> slugify("María José")
        'maria-jose'
        >>> slugify("Castro Lopez")
        'castro-lopez'
        >>> slugify("maria's friend")
        'marias-friend'
        >>> slugify("neighbor (2023)")
        'neighbor-2023'
    """
    if not text:
        return ""

    # Normalize unicode (decompose accents)
    text = unicodedata.normalize('NFKD', text)

    # Remove accent marks (keep only ASCII)
    text = text.encode('ascii', 'ignore').decode('ascii')

    # Lowercase
    text = text.lower()

    # Remove apostrophes
    text = text.replace("'", "")

    # Remove parentheses and brackets, replace with space
    text = re.sub(r'[(){}\[\]]', ' ', text)

    # Replace ampersands with 'and'
    text = text.replace('&', 'and')

    # Replace slashes with hyphen
    text = text.replace('/', '-')

    # Replace spaces and underscores with hyphens
    text = re.sub(r'[\s_]+', '-', text)

    # Remove all non-alphanumeric characters except hyphens
    text = re.sub(r'[^a-z0-9-]', '', text)

    # Collapse multiple hyphens
    text = re.sub(r'-+', '-', text)

    # Strip leading/trailing hyphens
    text = text.strip('-')

    # Enforce maximum length
    if len(text) > max_length:
        text = text[:max_length].rstrip('-')

    return text


def generate_person_filename(
    name: str,
    lastname: str | None,
    disambiguator: str | None,
) -> str:
    """
    Generate filename for person entity following design spec.

    Format: {first}_{last|disambig}.json

    Validation: lastname OR disambiguator must be provided (design requirement)

    Args:
        name: Person's first name
        lastname: Person's last name (optional if disambiguator provided)
        disambiguator: Disambiguator (optional if lastname provided)

    Returns:
        Filename in format first_last.json or first_disambig.json

    Raises:
        ValueError: If both lastname and disambiguator are None

    Examples:
        >>> generate_person_filename("Clara", "Dubois", None)
        'clara_dubois.json'
        >>> generate_person_filename("María José", "Castro Lopez", None)
        'maria-jose_castro-lopez.json'
        >>> generate_person_filename("Vlad", None, "work colleague")
        'vlad_work-colleague.json'
    """
    if not lastname and not disambiguator:
        raise ValueError(
            f"Person '{name}' must have lastname OR disambiguator. "
            "This is a design requirement for filename uniqueness."
        )

    first_slug = slugify(name)

    if lastname:
        last_slug = slugify(lastname)
        filename = f"{first_slug}_{last_slug}.json"
    else:
        disambig_slug = slugify(disambiguator)  # type: ignore
        filename = f"{first_slug}_{disambig_slug}.json"

    # Truncate extremely long names
    if len(filename) > 250:
        filename = f"{filename[:246]}.json"

    return filename


def generate_location_path(city_name: str, location_name: str) -> str:
    """
    Generate filepath for location entity.

    Format: {city}/{location}.json

    Args:
        city_name: Name of the city
        location_name: Name of the location

    Returns:
        Relative path: city/location.json

    Examples:
        >>> generate_location_path("Montréal", "The Neuro")
        'montreal/the-neuro.json'
    """
    city_slug = slugify(city_name)
    location_slug = slugify(location_name)
    return f"{city_slug}/{location_slug}.json"


def generate_scene_path(entry_date: str, scene_name: str) -> str:
    """
    Generate filepath for scene entity.

    Format: {YYYY-MM-DD}/{scene-name}.json

    Args:
        entry_date: Entry date in YYYY-MM-DD format
        scene_name: Name of the scene

    Returns:
        Relative path: YYYY-MM-DD/scene-name.json

    Examples:
        >>> generate_scene_path("2024-12-03", "Psychiatric Session")
        '2024-12-03/psychiatric-session.json'
    """
    scene_slug = slugify(scene_name)
    return f"{entry_date}/{scene_slug}.json"


def generate_entry_path(entry_date: str) -> str:
    """
    Generate filepath for entry entity.

    Format: {YYYY}/{YYYY-MM-DD}.json

    Args:
        entry_date: Entry date in YYYY-MM-DD format

    Returns:
        Relative path: YYYY/YYYY-MM-DD.json

    Examples:
        >>> generate_entry_path("2024-12-03")
        '2024/2024-12-03.json'
    """
    year = entry_date[:4]
    return f"{year}/{entry_date}.json"
