#!/usr/bin/env python3
"""
parsers.py
--------------------
General parsing utilities for extracting structured data.

Provides parsing functions used across multiple modules for extracting
names, abbreviations, and other structured information from formatted text.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from typing import Optional, Tuple, Dict, List


def extract_name_and_expansion(text: str) -> Tuple[str, Optional[str]]:
    """
    Extract name and expansion from text with optional parenthetical notation.

    Handles format: "Short (Full Expansion)" or just "Name"

    Args:
        text: Text potentially containing parenthetical expansion

    Returns:
        Tuple of (name, expansion) where expansion is None if no parentheses

    Examples:
        >>> extract_name_and_expansion("Mtl (Montreal)")
        ('Mtl', 'Montreal')
        >>> extract_name_and_expansion("QC (Quebec)")
        ('QC', 'Quebec')
        >>> extract_name_and_expansion("María-José (María José García)")
        ('María-José', 'María José García')
        >>> extract_name_and_expansion("Madrid")
        ('Madrid', None)
    """
    text = text.strip()

    if "(" in text and text.endswith(")"):
        # Split on first opening paren
        parts = text.split("(", 1)
        name = parts[0].strip()
        expansion = parts[1].rstrip(")").strip()
        return name, expansion

    return text, None


def extract_context_refs(context: str) -> Dict[str, List | str]:
    """
    Parse context for #location and @people references.

    Examples:
        >>> extract_context_refs("Dinner with @Majo and @Aliza at #Aliza's")
        {
            "context": "Dinner with Majo and Aliza at Aliza's",
            "people": ["Majo", "Aliza"],
            "locations": ["Aliza's"],
        }
        >>> extract_context_refs("Thesis seminar at @The-Neuro")
        {
            "context": "Thesis seminar at @The-Neuro",
            "locations": ["The Neuro"],
        }
    """
    out_dict = {}
    if not context:
        return out_dict

    locations: Optional[List[str]] = []
    people: Optional[List[str]] = []
    words = context.split()
    cleaned_words = []

    for word in words:
        if word.startswith("@"):
            person = word[1:].strip(".,;:!?")
            person = split_hyphenated_to_spaces(person)
            if person:
                people.append(person)
                cleaned_words.append(person)
        elif word.startswith("#"):
            loc_name = word[1:].strip(".,;:!?")
            loc_name = split_hyphenated_to_spaces(loc_name)
            if loc_name:
                locations.append(loc_name)
                cleaned_words.append(loc_name)
        else:
            cleaned_words.append(word)

    out_dict["context"] = " ".join(cleaned_words).strip()
    if locations:
        out_dict["locations"] = locations
    if people:
        out_dict["people"] = people

    return out_dict


def format_person_ref(person_ref: str) -> str:
    """Format person name as @reference for YAML."""
    hyphenated = spaces_to_hyphenated(person_ref)
    return f"@{hyphenated}"


def format_location_ref(location_name: str) -> str:
    """Format location name as @reference for YAML."""
    hyphenated = spaces_to_hyphenated(location_name)
    return f"#{hyphenated}"


def parse_date_context(date_str: str) -> Tuple[str, Optional[str]]:
    """
    Parse date with optional context annotation.

    Examples:
        >>> parse_date_context("2024-01-15 (therapy)")
        ('2024-01-15', 'therapy')
        >>> parse_date_context("2024-01-15")
        ('2024-01-15', None)
    """
    date_str = date_str.strip()

    if "(" in date_str and date_str.endswith(")"):
        # Split on first opening paren
        parts = date_str.split("(", 1)
        date = parts[0].strip()
        context = parts[1].rstrip(")").strip()
        return date, context

    return date_str, None


def split_hyphenated_to_spaces(text: str) -> str:
    """
    Convert hyphens to spaces (for names and locations).

    If the text contains underscores, use underscores as space markers
    and preserve hyphens. This allows explicit control over spacing.

    Rules:
    - If text contains '_': replace '_' with space, preserve '-'
    - Otherwise: replace '-' with space (default behavior)

    Examples:
        >>> split_hyphenated_to_spaces("María-José")
        'María José'
        >>> split_hyphenated_to_spaces("San-Diego")
        'San Diego'
        >>> split_hyphenated_to_spaces("Rue_St-Hubert")
        'Rue St-Hubert'
        >>> split_hyphenated_to_spaces("Jean_Pierre-Marie")
        'Jean Pierre-Marie'
    """
    if "_" in text:
        # Underscore mode: replace underscores with spaces, preserve hyphens
        return text.replace("_", " ")
    else:
        # Default mode: replace hyphens with spaces
        return text.replace("-", " ")


def spaces_to_hyphenated(text: str) -> str:
    """
    Convert spaces to hyphens (for names and locations).

    Examples:
        >>> spaces_to_hyphenated("María José")
        'María-José'
        >>> spaces_to_hyphenated("San Diego")
        'San-Diego'
    """
    return text.replace(" ", "-")
