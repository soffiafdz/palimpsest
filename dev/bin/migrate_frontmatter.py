#!/usr/bin/env python3
"""
migrate_frontmatter.py
----------------------
Migrate MD frontmatter to minimal format.

Transforms journal MD files from the old verbose frontmatter format
to the new minimal format that only keeps source-text focused fields.

Target format:
    ---
    date: 2024-12-03
    word_count: 749
    reading_time: 2.9
    locations:
      Montréal: [The Neuro, Home]
    people: [Dr-Franck, Fabiola, Aliza]
    narrated_dates: [2024-11-29, 2024-11-30]
    ---

Fields REMOVED (now live in wiki/DB):
    - scenes, events, arcs, threads
    - tags, themes, motifs
    - references, poems
    - epigraph, epigraph_attribution
    - notes (extracted to legacy archive first)
    - city (merged into locations)
    - manuscript

Usage:
    python -m dev.pipeline.migrate_frontmatter [--dry-run] [--file PATH]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from dev.core.paths import MD_DIR


# Fields to KEEP in frontmatter
KEEP_FIELDS = {"date", "word_count", "reading_time", "locations", "people", "narrated_dates"}

# Fields to REMOVE
REMOVE_FIELDS = {
    "scenes", "events", "arcs", "threads",
    "tags", "themes", "motifs",
    "references", "poems",
    "epigraph", "epigraph_attribution",
    "notes", "city", "manuscript",
    "dates",  # old name for narrated_dates
}


def extract_frontmatter_and_body(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and body from markdown content."""
    if not content.startswith("---"):
        return {}, content

    # Find the closing ---
    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", content, re.DOTALL)
    if not match:
        return {}, content

    try:
        frontmatter = yaml.safe_load(match.group(1)) or {}
        body = match.group(2)
        return frontmatter, body
    except yaml.YAMLError:
        return {}, content


def normalize_people(people: Any) -> Optional[List[str]]:
    """
    Normalize people field to list of simple names.

    Removes @ prefixes and parenthetical full names.
    """
    if not people:
        return None

    if isinstance(people, str):
        people = [people]

    normalized = []
    for p in people:
        if isinstance(p, str):
            # Remove @ prefix
            name = p.lstrip("@")
            # Remove parenthetical (full name)
            name = re.sub(r"\s*\([^)]+\)\s*$", "", name)
            normalized.append(name.strip())
        elif isinstance(p, dict):
            # Handle dict format: {"name": "X"} or {"full_name": "X"}
            name = p.get("name") or p.get("full_name") or ""
            if name:
                normalized.append(name.strip())

    return normalized if normalized else None


def normalize_locations(
    locations: Any,
    city: Optional[str] = None
) -> Optional[Dict[str, List[str]]]:
    """
    Normalize locations to nested dict format: {City: [loc1, loc2]}.

    Args:
        locations: Current locations value (list or dict)
        city: City field value if present (for merging)
    """
    if not locations and not city:
        return None

    # If already dict format, return as-is
    if isinstance(locations, dict):
        return locations

    # If list format, need city context
    if isinstance(locations, list):
        if city:
            return {city: locations}
        # No city context - can't convert properly
        return {"Unknown": locations}

    return None


def migrate_frontmatter(frontmatter: dict) -> dict:
    """
    Migrate frontmatter to minimal format.

    Args:
        frontmatter: Original frontmatter dict

    Returns:
        Migrated frontmatter with only KEEP_FIELDS
    """
    migrated = {}

    # Keep simple fields
    for field in ["date", "word_count", "reading_time"]:
        if field in frontmatter:
            migrated[field] = frontmatter[field]

    # Normalize locations (merge with city if present)
    locations = normalize_locations(
        frontmatter.get("locations"),
        frontmatter.get("city")
    )
    if locations:
        migrated["locations"] = locations

    # Normalize people
    people = normalize_people(frontmatter.get("people"))
    if people:
        migrated["people"] = people

    # Handle narrated_dates (may be under 'dates' key)
    narrated_dates = frontmatter.get("narrated_dates") or frontmatter.get("dates")
    if narrated_dates:
        # Extract just dates if complex format
        if isinstance(narrated_dates, list):
            dates = []
            for d in narrated_dates:
                if isinstance(d, str):
                    # Skip marker entries like "~"
                    if d.startswith("~"):
                        continue
                    dates.append(d)
                elif isinstance(d, dict) and "date" in d:
                    dates.append(d["date"])
            if dates:
                migrated["narrated_dates"] = dates

    return migrated


def format_frontmatter(frontmatter: dict) -> str:
    """Format frontmatter dict as YAML string."""
    if not frontmatter:
        return "---\n---\n"

    # Custom formatting for readability
    lines = ["---"]

    # Date first
    if "date" in frontmatter:
        lines.append(f"date: {frontmatter['date']}")

    # Metrics
    if "word_count" in frontmatter:
        lines.append(f"word_count: {frontmatter['word_count']}")
    if "reading_time" in frontmatter:
        lines.append(f"reading_time: {frontmatter['reading_time']}")

    # Locations (nested dict)
    if "locations" in frontmatter:
        lines.append("locations:")
        for city, locs in frontmatter["locations"].items():
            if len(locs) <= 3:
                lines.append(f"  {city}: [{', '.join(locs)}]")
            else:
                lines.append(f"  {city}:")
                for loc in locs:
                    lines.append(f"    - {loc}")

    # People (inline if short)
    if "people" in frontmatter:
        people = frontmatter["people"]
        inline = ", ".join(people)
        if len(inline) < 70:
            lines.append(f"people: [{inline}]")
        else:
            lines.append("people:")
            for p in people:
                lines.append(f"  - {p}")

    # Narrated dates
    if "narrated_dates" in frontmatter:
        dates = frontmatter["narrated_dates"]
        if len(dates) <= 5:
            lines.append(f"narrated_dates: [{', '.join(dates)}]")
        else:
            lines.append("narrated_dates:")
            for d in dates:
                lines.append(f"  - {d}")

    lines.append("---")
    return "\n".join(lines) + "\n"


def migrate_file(md_file: Path, dry_run: bool = False) -> bool:
    """
    Migrate a single MD file.

    Args:
        md_file: Path to MD file
        dry_run: If True, don't write changes

    Returns:
        True if file was modified, False otherwise
    """
    content = md_file.read_text(encoding="utf-8")
    frontmatter, body = extract_frontmatter_and_body(content)

    if not frontmatter:
        return False

    # Check if migration needed
    has_remove_fields = any(f in frontmatter for f in REMOVE_FIELDS)
    if not has_remove_fields:
        return False

    # Migrate
    new_frontmatter = migrate_frontmatter(frontmatter)
    new_content = format_frontmatter(new_frontmatter) + body

    if not dry_run:
        md_file.write_text(new_content, encoding="utf-8")

    return True


def migrate_all(dry_run: bool = False, single_file: Optional[Path] = None) -> int:
    """
    Migrate all MD files or a single file.

    Args:
        dry_run: If True, don't write changes
        single_file: If provided, only migrate this file

    Returns:
        Count of migrated files
    """
    if single_file:
        files = [single_file]
    else:
        files = sorted(MD_DIR.glob("**/*.md"))

    print(f"{'[DRY RUN] ' if dry_run else ''}Processing {len(files)} files...")

    migrated_count = 0
    for md_file in files:
        if migrate_file(md_file, dry_run):
            migrated_count += 1
            if dry_run:
                print(f"  Would migrate: {md_file.name}")

    print(f"{'Would migrate' if dry_run else 'Migrated'}: {migrated_count} files")
    return migrated_count


def main():
    parser = argparse.ArgumentParser(description="Migrate MD frontmatter to minimal format")
    parser.add_argument("--dry-run", action="store_true", help="Don't write changes")
    parser.add_argument("--file", type=Path, help="Migrate single file only")
    args = parser.parse_args()

    migrate_all(dry_run=args.dry_run, single_file=args.file)


if __name__ == "__main__":
    main()
