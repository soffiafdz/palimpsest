#!/usr/bin/env python3
"""
name_matching.py
----------------
Shared utilities for flexible person name matching.

This module provides name normalization and matching functions used by
validators and importers to handle the variety of name formats in the
Palimpsest data.

Name Formats Handled:
    - Simple: "John"
    - Full name: "Jane Smith"
    - Accented: "María José", "Amélie"
    - Hyphenated: "Marc-Antoine" (treated as "Marc Antoine")
    - With apostrophe: "O'Brien" (normalized to "obrien")
    - Aliases: "@Johnny", "Johnny (alias for John)"

Matching Strategy:
    Each person generates multiple lookup keys for flexible matching.
    Matching succeeds if ANY key from source matches ANY key from target.

Usage:
    from dev.utils.name_matching import normalize_name, get_person_keys, names_match

    # Normalize for comparison
    normalized = normalize_name("María José")  # "maria jose"

    # Get all keys for a person dict
    keys = get_person_keys({"name": "María José", "lastname": "Castro", "alias": "Majo"})
    # Returns: {"maria jose", "maria jose castro", "majo", "castro"}

    # Check if names match
    matches = names_match("Majo", person_dict)  # True
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import re
import unicodedata
from typing import Any, Dict, List, Optional, Set, Union


def normalize_name(name: str) -> str:
    """
    Normalize a name for comparison.

    Transformations:
        - Lowercase
        - Remove accents (María → maria)
        - Replace hyphens with spaces (Marc-Antoine → marc antoine)
        - Remove apostrophes (O'Brien → obrien)
        - Collapse multiple spaces

    Args:
        name: Name string to normalize

    Returns:
        Normalized name for comparison
    """
    if not name:
        return ""

    # Lowercase
    result = name.lower()

    # Remove accents (NFD decomposition + remove combining marks)
    result = unicodedata.normalize("NFD", result)
    result = "".join(c for c in result if unicodedata.category(c) != "Mn")

    # Replace hyphens with spaces
    result = result.replace("-", " ")

    # Remove apostrophes
    result = result.replace("'", "").replace("'", "")

    # Collapse multiple spaces
    result = re.sub(r"\s+", " ", result).strip()

    return result


def get_person_keys(person: Union[str, Dict[str, Any]]) -> Set[str]:
    """
    Generate all lookup keys for a person.

    For a person dict with name/lastname/alias, generates multiple keys
    to allow flexible matching.

    Args:
        person: Either a string name or a dict with name/lastname/alias fields

    Returns:
        Set of normalized keys for matching

    Example:
        >>> get_person_keys({"name": "María José", "lastname": "Castro", "alias": "Majo"})
        {"maria jose", "maria jose castro", "majo", "castro"}

        >>> get_person_keys("John Smith")
        {"john smith", "john", "smith"}
    """
    keys: Set[str] = set()

    if isinstance(person, str):
        normalized = normalize_name(person)
        if normalized:
            keys.add(normalized)
            # Add individual words for multi-word names
            parts = normalized.split()
            if len(parts) > 1:
                keys.update(parts)
        return keys

    # Dict format
    name = person.get("name", "")
    lastname = person.get("lastname", "")
    alias = person.get("alias")

    # Add normalized name
    if name:
        norm_name = normalize_name(name)
        if norm_name:
            keys.add(norm_name)
            # Add parts of multi-word names
            parts = norm_name.split()
            if len(parts) > 1:
                keys.update(parts)

    # Add normalized lastname
    if lastname:
        norm_lastname = normalize_name(lastname)
        if norm_lastname:
            keys.add(norm_lastname)

    # Add full name (name + lastname)
    if name and lastname:
        full = normalize_name(f"{name} {lastname}")
        if full:
            keys.add(full)

    # Add aliases
    if alias:
        aliases = alias if isinstance(alias, list) else [alias]
        for a in aliases:
            if a:
                norm_alias = normalize_name(a)
                if norm_alias:
                    keys.add(norm_alias)

    return keys


def extract_people_keys(
    people: List[Union[str, Dict[str, Any]]]
) -> Set[str]:
    """
    Extract all lookup keys from a list of people.

    Args:
        people: List of people (strings or dicts)

    Returns:
        Set of all normalized keys
    """
    all_keys: Set[str] = set()
    for person in people:
        all_keys.update(get_person_keys(person))
    return all_keys


def names_match(
    name: str,
    person: Union[str, Dict[str, Any]],
) -> bool:
    """
    Check if a name matches a person.

    Matching succeeds if any normalized key from the name matches
    any key from the person.

    Args:
        name: Name to match
        person: Person to match against (string or dict)

    Returns:
        True if names match
    """
    name_keys = get_person_keys(name)
    person_keys = get_person_keys(person)
    return bool(name_keys & person_keys)


def find_matching_person(
    name: str,
    people: List[Union[str, Dict[str, Any]]],
) -> Optional[Union[str, Dict[str, Any]]]:
    """
    Find a person in a list that matches the given name.

    Args:
        name: Name to find
        people: List of people to search

    Returns:
        Matching person or None
    """
    name_keys = get_person_keys(name)
    for person in people:
        person_keys = get_person_keys(person)
        if name_keys & person_keys:
            return person
    return None


def person_in_set(name: str, people_keys: Set[str]) -> bool:
    """
    Check if a name matches any key in a pre-computed key set.

    This is more efficient when checking multiple names against
    the same people list.

    Args:
        name: Name to check
        people_keys: Pre-computed set from extract_people_keys()

    Returns:
        True if name matches any key in the set
    """
    name_keys = get_person_keys(name)
    return bool(name_keys & people_keys)
