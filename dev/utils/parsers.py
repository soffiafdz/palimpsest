#!/usr/bin/env python3
"""
parsers.py
--------------------
General parsing utilities for extracting structured data.

Provides parsing functions used across multiple modules for extracting
names, abbreviations, and other structured information from formatted text.
"""
from __future__ import annotations

from typing import Optional, Tuple


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

    Examples:
        >>> split_hyphenated_to_spaces("María-José")
        'María José'
        >>> split_hyphenated_to_spaces("San-Diego")
        'San Diego'
    """
    return text.replace("-", " ")


def spaces_to_hyphenated(text: str) -> str:
    """
    Convert spaces to a single word (for names and locations.

    Examples:
        >>> spaces_to_hyphenated("María José")
        'María-José'
        >>> spaces_to_hyphenated("San Diego")
        'San-Diego'
    """
    return text.replace(" ", "-")
