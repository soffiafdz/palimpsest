#!/usr/bin/env python3
"""
narrative_to_yaml.py
--------------------
Convert narrative analysis markdown files to YAML format.

This script parses the structured markdown format used in narrative analyses
and outputs equivalent YAML files for easier programmatic processing.

Key Features:
    - Parses all 7 sections: Summary, Rating, Tags, Themes, Motifs, Scenes, Events
    - Handles older format with sub-ratings (Clara Manuscript, Early Transition)
    - Preserves descriptions as primary data
    - Logs parsing failures for manual review

Usage:
    # Convert a single file
    python -m dev.pipeline.narrative_to_yaml --file path/to/analysis.md

    # Convert all files in a directory
    python -m dev.pipeline.narrative_to_yaml --dir path/to/narrative_analysis/

    # Dry run (parse but don't write)
    python -m dev.pipeline.narrative_to_yaml --dir path/ --dry-run
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


class NarrativeParser:
    """
    Parse narrative analysis markdown files into structured data.

    The parser handles the standard markdown format with sections:
    - Summary, Narrative Rating, Tags, Themes, Motifs, Scenes, Events
    """

    def __init__(self, content: str, file_path: Optional[Path] = None):
        """
        Initialize parser with markdown content.

        Args:
            content: Raw markdown text
            file_path: Optional path for error reporting
        """
        self.content = content
        self.file_path = file_path
        self.errors: List[str] = []

    def parse(self) -> Dict[str, Any]:
        """
        Parse the markdown content into a structured dictionary.

        Returns:
            Dictionary matching the target YAML schema
        """
        result = {
            "date": self._extract_date(),
            "summary": self._extract_summary(),
            "rating": None,
            "rating_justification": "",
            "arcs": [],  # Placeholder for future
            "tags": [],
            "themes": [],
            "motifs": [],
            "scenes": [],
            "events": [],
        }

        # Parse rating (may include sub-ratings)
        rating_data = self._extract_rating()
        result["rating"] = rating_data.get("rating")
        result["rating_justification"] = rating_data.get("justification", "")
        if rating_data.get("sub_ratings"):
            result["sub_ratings"] = rating_data["sub_ratings"]

        result["tags"] = self._extract_tags()
        result["themes"] = self._extract_themes()
        result["motifs"] = self._extract_motifs()
        result["scenes"] = self._extract_scenes()
        result["events"] = self._extract_events()

        return result

    def _extract_date(self) -> Optional[str]:
        """Extract date from the title line."""
        match = re.search(r"# Narrative Analysis: (\d{4}-\d{2}-\d{2})", self.content)
        if match:
            return match.group(1)
        self.errors.append("Could not extract date from title")
        return None

    def _extract_section(self, section_name: str, next_sections: List[str]) -> str:
        """
        Extract content between a section header and the next section.

        Args:
            section_name: Name of the section to extract
            next_sections: Possible names of following sections

        Returns:
            Section content as string, or empty string if not found
        """
        # Build pattern for section header
        pattern = rf"## {re.escape(section_name)}[^\n]*\n"
        match = re.search(pattern, self.content)
        if not match:
            return ""

        start = match.end()

        # Find the next section
        if next_sections:
            next_pattern = "|".join(rf"## {re.escape(s)}" for s in next_sections)
            next_match = re.search(next_pattern, self.content[start:])
            if next_match:
                end = start + next_match.start()
            else:
                end = len(self.content)
        else:
            # No next sections specified, take everything to end of file
            end = len(self.content)

        return self.content[start:end].strip()

    def _extract_summary(self) -> str:
        """Extract the Summary section."""
        return self._extract_section(
            "Summary",
            ["Narrative Rating", "Tags", "Themes", "Motifs", "Scenes", "Events"]
        )

    def _extract_rating(self) -> Dict[str, Any]:
        """
        Extract rating and justification, handling sub-ratings.

        Returns:
            Dict with rating (int), justification (str), and optional sub_ratings
        """
        result: Dict[str, Any] = {"rating": None, "justification": "", "sub_ratings": {}}

        # Find the rating header
        header_match = re.search(
            r"## Narrative Rating:\s*(\d+(?:\.\d+)?)/5",
            self.content
        )
        if header_match:
            result["rating"] = float(header_match.group(1))
            if result["rating"] == int(result["rating"]):
                result["rating"] = int(result["rating"])

        # Extract full rating section
        section = self._extract_section(
            "Narrative Rating",
            ["Tags", "Themes", "Motifs", "Scenes", "Events"]
        )

        if not section:
            return result

        lines = section.split("\n")
        justification_lines = []
        current_sub = None

        for line in lines:
            # Check for sub-rating header
            sub_match = re.match(r"###\s*(.+?):\s*(\d+(?:\.\d+)?)/5", line)
            if sub_match:
                current_sub = sub_match.group(1).strip()
                sub_rating = float(sub_match.group(2))
                if sub_rating == int(sub_rating):
                    sub_rating = int(sub_rating)
                result["sub_ratings"][current_sub] = {
                    "rating": sub_rating,
                    "justification": ""
                }
                continue

            # If we're in a sub-rating, add to its justification
            if current_sub and line.strip():
                result["sub_ratings"][current_sub]["justification"] += line.strip() + " "
            elif line.strip() and not current_sub:
                justification_lines.append(line.strip())

        result["justification"] = " ".join(justification_lines)

        # Clean up sub_ratings justifications
        for key in result["sub_ratings"]:
            result["sub_ratings"][key]["justification"] = (
                result["sub_ratings"][key]["justification"].strip()
            )

        # Remove empty sub_ratings
        if not result["sub_ratings"]:
            del result["sub_ratings"]

        return result

    def _extract_tags(self) -> List[str]:
        """Extract tags as a list."""
        section = self._extract_section(
            "Tags",
            ["Themes", "Motifs", "Scenes", "Events"]
        )
        if not section:
            return []

        # Tags are comma-separated on one or more lines
        tags = []
        for part in section.split(","):
            tag = part.strip()
            if tag:
                tags.append(tag)
        return tags

    def _extract_themes(self) -> List[Dict[str, str]]:
        """Extract themes with names and descriptions."""
        section = self._extract_section(
            "Themes",
            ["Motifs", "Scenes", "Events"]
        )
        return self._parse_bulleted_items(section)

    def _extract_motifs(self) -> List[Dict[str, str]]:
        """Extract motifs with names and descriptions."""
        section = self._extract_section(
            "Motifs",
            ["Scenes", "Events"]
        )
        return self._parse_bulleted_items(section)

    def _parse_bulleted_items(self, section: str) -> List[Dict[str, str]]:
        """
        Parse bulleted items with **Name:** description or **Name** - description format.

        Args:
            section: Section content with bulleted items

        Returns:
            List of dicts with 'name' and 'description' keys
        """
        items = []
        if not section:
            return items

        # Handle two formats:
        # 1. **Name:** description (colon inside bold)
        # 2. **Name** - description (separator after bold)
        pattern1 = r"[-*]\s*\*\*(.+?):\*\*\s*(.+)"  # Colon inside bold
        pattern2 = r"[-*]\s*\*\*(.+?)\*\*\s*[-–—:]\s*(.+)"  # Separator after bold

        for line in section.split("\n"):
            line = line.strip()
            match = re.match(pattern1, line) or re.match(pattern2, line)
            if match:
                name = match.group(1).strip()
                description = match.group(2).strip()
                items.append({"name": name, "description": description})

        return items

    def _extract_scenes(self) -> List[Dict[str, str]]:
        """Extract scenes with names and descriptions."""
        section = self._extract_section("Scenes", ["Events"])
        return self._parse_numbered_items(section)

    def _parse_numbered_items(self, section: str) -> List[Dict[str, str]]:
        """
        Parse numbered items with N. **Name** - description format.

        Handles multiple formats:
        - 1. **Name** - description
        - 1. **Name**: description
        - 1. **INT. LOCATION - TIME - Name**: description

        Args:
            section: Section content with numbered items

        Returns:
            List of dicts with 'name' and 'description' keys
        """
        items = []
        if not section:
            return items

        # Match numbered items: 1. **Name** followed by - or : and description
        # The name may contain dashes (like INT. APARTMENT - DAY - Name)
        # May also have parenthetical context after: **Name** (context): desc
        pattern = r"(\d+)\.\s*\*\*(.+?)\*\*(?:\s*\([^)]*\))?\s*[:–—-]\s*"

        # Split by numbered items
        parts = re.split(pattern, section)

        # parts[0] is empty or preamble, then groups of (number, name, description)
        i = 1
        while i + 2 < len(parts):
            # number = parts[i]
            name = parts[i + 1].strip()
            description = parts[i + 2].strip()

            # Clean up description (may have extra newlines)
            description = " ".join(description.split())

            items.append({"name": name, "description": description})
            i += 3

        return items

    def _extract_events(self) -> List[Dict[str, Any]]:
        """
        Extract events with metadata.

        Events have format:
        1. **Event Name**
           - Type: present/flashback/memory/continuation
           - Date: YYYY-MM-DD (optional)
           - Scenes: 1, 2, 3
           - Description: ... (optional)
        """
        section = self._extract_section("Events", [])
        if not section:
            return []

        events = []

        # Split by numbered items
        event_pattern = r"\d+\.\s*\*\*(.+?)\*\*"
        parts = re.split(event_pattern, section)

        # parts[0] is preamble, then alternating (name, content)
        i = 1
        while i + 1 < len(parts):
            name = parts[i].strip()
            content = parts[i + 1].strip()

            event: Dict[str, Any] = {"name": name}

            # Parse metadata lines
            type_match = re.search(r"-\s*Type:\s*(\w+)", content)
            if type_match:
                event["type"] = type_match.group(1).lower()

            date_match = re.search(r"-\s*Date:\s*(\d{4}-\d{2}-\d{2})", content)
            if date_match:
                event["dates"] = [date_match.group(1)]

            scenes_match = re.search(r"-\s*Scenes:\s*(.+?)(?:\n|$)", content)
            if scenes_match:
                scenes_str = scenes_match.group(1)
                # Parse scene numbers
                scene_nums = [int(s.strip()) for s in scenes_str.split(",") if s.strip().isdigit()]
                event["scenes"] = scene_nums

            desc_match = re.search(r"-\s*Description:\s*(.+)", content, re.DOTALL)
            if desc_match:
                event["description"] = desc_match.group(1).strip()

            events.append(event)
            i += 2

        return events


def convert_to_yaml(data: Dict[str, Any]) -> str:
    """
    Convert parsed data to YAML string.

    Args:
        data: Parsed narrative data dictionary

    Returns:
        YAML formatted string
    """
    # Custom representer for multi-line strings
    def str_representer(dumper, data):
        if "\n" in data or len(data) > 80:
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data)

    yaml.add_representer(str, str_representer)

    return yaml.dump(
        data,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=100,
    )


def convert_file(
    input_path: Path,
    output_path: Optional[Path] = None,
    dry_run: bool = False
) -> bool:
    """
    Convert a single markdown file to YAML.

    Args:
        input_path: Path to input markdown file
        output_path: Path for output YAML file (default: same name with .yaml)
        dry_run: If True, parse but don't write

    Returns:
        True if successful, False otherwise
    """
    if output_path is None:
        output_path = input_path.with_suffix(".yaml")

    try:
        content = input_path.read_text(encoding="utf-8")
        parser = NarrativeParser(content, input_path)
        data = parser.parse()

        if parser.errors:
            for error in parser.errors:
                logger.warning(f"{input_path}: {error}")

        if dry_run:
            logger.info(f"Would write: {output_path}")
            return True

        yaml_content = convert_to_yaml(data)
        output_path.write_text(yaml_content, encoding="utf-8")
        logger.debug(f"Converted: {input_path} -> {output_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to convert {input_path}: {e}")
        return False


def convert_directory(
    input_dir: Path,
    dry_run: bool = False,
    pattern: str = "*_analysis.md"
) -> Dict[str, int]:
    """
    Convert all markdown files in a directory.

    Args:
        input_dir: Directory containing markdown files
        dry_run: If True, parse but don't write
        pattern: Glob pattern for finding files

    Returns:
        Dict with counts: success, failed, total
    """
    files = list(input_dir.rglob(pattern))
    results = {"success": 0, "failed": 0, "total": len(files)}

    logger.info(f"Found {len(files)} files to convert")

    for file_path in sorted(files):
        if convert_file(file_path, dry_run=dry_run):
            results["success"] += 1
        else:
            results["failed"] += 1

    return results


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Convert narrative analysis markdown files to YAML"
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Convert a single file"
    )
    parser.add_argument(
        "--dir",
        type=Path,
        help="Convert all files in directory (recursive)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse files but don't write output"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show verbose output"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.file:
        success = convert_file(args.file, dry_run=args.dry_run)
        return 0 if success else 1

    if args.dir:
        results = convert_directory(args.dir, dry_run=args.dry_run)
        logger.info(
            f"Converted {results['success']}/{results['total']} files "
            f"({results['failed']} failed)"
        )
        return 0 if results["failed"] == 0 else 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    exit(main())
