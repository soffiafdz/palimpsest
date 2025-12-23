#!/usr/bin/env python3
"""
narrative_analysis.py
---------------------
Parser for narrative analysis markdown files.

Extracts structured data from *_analysis.md files generated during
narrative analysis of journal entries for the manuscript.

Key Features:
    - Parses markdown sections (Summary, Rating, Tags, Themes, etc.)
    - Extracts cleaned tags and tag categories
    - Extracts themes with descriptions
    - Extracts thematic motifs (arcs)
    - Returns structured AnalysisData dataclass

Usage:
    from dev.dataclasses.parsers.narrative_analysis import (
        parse_analysis_file,
        parse_all_analyses,
    )

    # Parse single file
    analysis = parse_analysis_file(Path("2025-12-05_analysis.md"))

    # Parse all files in directory
    analyses = parse_all_analyses(Path("data/journal/narrative_analysis"))
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# --- Standard library logging ---
import logging

logger = logging.getLogger(__name__)


@dataclass
class ThemeData:
    """Represents a theme extracted from analysis."""
    name: str
    description: Optional[str] = None


@dataclass
class AnalysisData:
    """
    Structured data extracted from a narrative analysis file.

    Attributes:
        entry_date: The date of the journal entry being analyzed
        summary: Narrative summary of the entry
        rating: Narrative quality rating (1-5, can be float like 3.5)
        rating_justification: Text explaining the rating
        raw_tags: Original tags including people/locations
        cleaned_tags: Tags with people/locations removed
        tag_categories: Semantic categories (e.g., "Digital Surveillance")
        themes: List of ThemeData with name and description
        motifs: List of thematic motifs (e.g., "THE OBSESSIVE LOOP")
        people: People mentioned (if explicitly listed)
        locations: Locations mentioned (if explicitly listed)
    """
    entry_date: date
    summary: Optional[str] = None
    rating: Optional[float] = None
    rating_justification: Optional[str] = None
    raw_tags: List[str] = field(default_factory=list)
    cleaned_tags: List[str] = field(default_factory=list)
    tag_categories: List[str] = field(default_factory=list)
    themes: List[ThemeData] = field(default_factory=list)
    motifs: List[str] = field(default_factory=list)
    people: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)


def parse_date_from_filename(filename: str) -> Optional[date]:
    """
    Extract date from analysis filename.

    Args:
        filename: Filename like "2025-12-05_analysis.md"

    Returns:
        Parsed date or None if invalid
    """
    match = re.match(r"(\d{4}-\d{2}-\d{2})_analysis\.md", filename)
    if match:
        try:
            return date.fromisoformat(match.group(1))
        except ValueError:
            return None
    return None


def parse_rating(text: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Extract rating value and justification from rating section.

    Args:
        text: Text like "4/5" or "4.5/5\\n\\nJustification text..."

    Returns:
        Tuple of (rating, justification)
    """
    # Match patterns like "4/5", "4.5/5", "3.5 / 5"
    rating_match = re.search(r"(\d+(?:\.\d+)?)\s*/\s*5", text)
    rating = float(rating_match.group(1)) if rating_match else None

    # Get justification (everything after the rating line)
    justification = None
    if rating_match:
        # Find where the rating ends and get the rest
        after_rating = text[rating_match.end():].strip()
        # Remove "Justification:" prefix if present
        after_rating = re.sub(r"^\*?\*?Justification:?\*?\*?\s*", "", after_rating, flags=re.IGNORECASE)
        if after_rating:
            justification = after_rating.strip()

    return rating, justification


def parse_tags(text: str) -> List[str]:
    """
    Parse comma-separated tags from text.

    Args:
        text: Comma-separated tags like "Bea, Instagram Story, Lab Retreat"

    Returns:
        List of individual tags
    """
    if not text.strip():
        return []
    return [tag.strip() for tag in text.split(",") if tag.strip()]


def parse_themes(text: str) -> List[ThemeData]:
    """
    Parse themes section with names and descriptions.

    Handles markdown format where colon is inside bold markers:
        - **Theme Name:** Description text here...

    Args:
        text: Themes section like:
            - **Digital Anxiety:** The fear of being watched...
            - **The Palimpsest of Lovers:** How past relationships...

    Returns:
        List of ThemeData objects with formatting removed
    """
    themes = []
    # Match "- **Theme Name:** Description" where colon is INSIDE the asterisks
    pattern = r"-\s*\*{1,2}([^*:]+):\*{1,2}\s*(.+?)(?=\n-|\n\n|\Z)"
    matches = re.findall(pattern, text, re.DOTALL)

    for name, description in matches:
        # Strip formatting and whitespace
        clean_name = name.strip()
        clean_desc = description.strip() if description.strip() else None
        themes.append(ThemeData(
            name=clean_name,
            description=clean_desc
        ))

    return themes


def parse_motifs(text: str) -> List[str]:
    """
    Parse thematic arcs/motifs from text.

    Args:
        text: Comma-separated motifs like
            "THE OBSESSIVE LOOP, THE UNRELIABLE NARRATOR, WRITING AS SURVIVAL"

    Returns:
        List of motif names
    """
    if not text.strip():
        return []
    return [motif.strip() for motif in text.split(",") if motif.strip()]


def extract_section(content: str, section_name: str) -> Optional[str]:
    """
    Extract content of a markdown section.

    Args:
        content: Full markdown content
        section_name: Section heading (without ##)

    Returns:
        Section content or None if not found
    """
    # Match "## Section Name" or "## Section Name: value" followed by content
    # The heading might have additional content like "## Narrative Rating: 4/5"
    pattern = rf"##\s*{re.escape(section_name)}[^\n]*\n(.*?)(?=\n##|\Z)"
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def extract_section_with_heading(content: str, section_name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract both the heading line and content of a markdown section.

    Args:
        content: Full markdown content
        section_name: Section heading prefix (without ##)

    Returns:
        Tuple of (heading_line, section_content)
    """
    # Match full heading line and content
    pattern = rf"##\s*({re.escape(section_name)}[^\n]*)\n(.*?)(?=\n##|\Z)"
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return None, None


def parse_analysis_file(file_path: Path) -> Optional[AnalysisData]:
    """
    Parse a single narrative analysis markdown file.

    Args:
        file_path: Path to the *_analysis.md file

    Returns:
        AnalysisData object or None if parsing fails

    Examples:
        >>> analysis = parse_analysis_file(Path("2025-12-05_analysis.md"))
        >>> print(analysis.rating)
        4.0
        >>> print(analysis.motifs)
        ['THE OBSESSIVE LOOP', 'WRITING AS SURVIVAL']
    """
    if not file_path.exists():
        logger.warning(f"Analysis file not found: {file_path}")
        return None

    # Extract date from filename
    entry_date = parse_date_from_filename(file_path.name)
    if not entry_date:
        logger.warning(f"Could not parse date from filename: {file_path.name}")
        return None

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return None

    analysis = AnalysisData(entry_date=entry_date)

    # Extract Summary
    summary = extract_section(content, "Summary")
    if summary:
        analysis.summary = summary

    # Extract Rating (rating might be in heading like "## Narrative Rating: 4/5")
    heading, rating_section = extract_section_with_heading(content, "Narrative Rating")
    if heading:
        # Check heading for rating first
        rating, _ = parse_rating(heading)
        analysis.rating = rating
        if rating_section:
            analysis.rating_justification = rating_section

    # Extract Tags (raw)
    tags_section = extract_section(content, "Tags")
    if tags_section:
        analysis.raw_tags = parse_tags(tags_section)

    # Extract Cleaned Tags
    cleaned_section = extract_section(content, "Cleaned Tags")
    if cleaned_section:
        analysis.cleaned_tags = parse_tags(cleaned_section)

    # Extract Tag Categories
    categories_section = extract_section(content, "Tag Categories")
    if categories_section:
        analysis.tag_categories = parse_tags(categories_section)

    # Extract Themes
    themes_section = extract_section(content, "Themes")
    if themes_section:
        analysis.themes = parse_themes(themes_section)

    # Extract Thematic Arcs (Motifs)
    arcs_section = extract_section(content, "Thematic Arcs")
    if arcs_section:
        analysis.motifs = parse_motifs(arcs_section)

    # Extract People (if present)
    people_section = extract_section(content, "People")
    if people_section:
        analysis.people = parse_tags(people_section)

    # Extract Locations (if present)
    locations_section = extract_section(content, "Locations")
    if locations_section:
        # Handle "None significant." or similar
        if not re.match(r"none\s+significant", locations_section, re.IGNORECASE):
            analysis.locations = parse_tags(locations_section)

    logger.debug(f"Parsed analysis for {entry_date}: {len(analysis.themes)} themes, {len(analysis.motifs)} motifs")
    return analysis


def parse_all_analyses(directory: Path) -> Dict[date, AnalysisData]:
    """
    Parse all analysis files in a directory.

    Args:
        directory: Path to directory containing *_analysis.md files

    Returns:
        Dictionary mapping entry dates to AnalysisData objects

    Examples:
        >>> analyses = parse_all_analyses(Path("data/journal/narrative_analysis"))
        >>> print(len(analyses))
        229
        >>> print(analyses[date(2025, 12, 5)].rating)
        4.0
    """
    analyses = {}

    if not directory.exists():
        logger.warning(f"Directory not found: {directory}")
        return analyses

    for file_path in sorted(directory.glob("**/*_analysis.md")):
        analysis = parse_analysis_file(file_path)
        if analysis:
            analyses[analysis.entry_date] = analysis

    logger.info(f"Parsed {len(analyses)} analysis files from {directory}")
    return analyses


def get_all_motifs(analyses: Dict[date, AnalysisData]) -> List[str]:
    """
    Extract unique motif names across all analyses.

    Args:
        analyses: Dictionary of parsed analyses

    Returns:
        Sorted list of unique motif names
    """
    motifs = set()
    for analysis in analyses.values():
        motifs.update(analysis.motifs)
    return sorted(motifs)


def get_all_tag_categories(analyses: Dict[date, AnalysisData]) -> List[str]:
    """
    Extract unique tag category names across all analyses.

    Args:
        analyses: Dictionary of parsed analyses

    Returns:
        Sorted list of unique category names
    """
    categories = set()
    for analysis in analyses.values():
        categories.update(analysis.tag_categories)
    return sorted(categories)


def get_all_themes(analyses: Dict[date, AnalysisData]) -> Dict[str, Optional[str]]:
    """
    Extract unique theme names and their most recent descriptions.

    Args:
        analyses: Dictionary of parsed analyses

    Returns:
        Dictionary mapping theme names to descriptions
    """
    themes: Dict[str, Optional[str]] = {}
    for analysis in analyses.values():
        for theme in analysis.themes:
            # Keep the description if we don't have one yet
            if theme.name not in themes or (theme.description and not themes[theme.name]):
                themes[theme.name] = theme.description
    return themes
