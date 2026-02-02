#!/usr/bin/env python3
"""
update_narrated_dates.py
------------------------
Extract scene dates from metadata YAML and update MD frontmatter narrated_dates.

This script scans metadata YAML files, extracts all dates from scenes
(excluding approximate dates with ~), and updates the corresponding
MD frontmatter with the narrated_dates field.

Usage:
    python -m dev.bin.update_narrated_dates [--year YYYY] [--dry-run]

Examples:
    # Dry run for all years 2021+
    python -m dev.bin.update_narrated_dates --dry-run

    # Update specific year
    python -m dev.bin.update_narrated_dates --year 2024

    # Update all years
    python -m dev.bin.update_narrated_dates
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import argparse
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# --- Third-party imports ---
import yaml

# --- Local imports ---
from dev.core.paths import JOURNAL_YAML_DIR, MD_DIR


def extract_scene_dates(yaml_data: Dict[str, Any]) -> Set[date]:
    """
    Extract all valid dates from scenes in metadata YAML.

    Skips approximate dates (containing ~) and invalid formats.

    Args:
        yaml_data: Parsed metadata YAML dict

    Returns:
        Set of date objects from scenes
    """
    dates: Set[date] = set()
    scenes = yaml_data.get("scenes", []) or []

    for scene in scenes:
        scene_dates = scene.get("date")
        if not scene_dates:
            continue

        # Handle single date or list
        if not isinstance(scene_dates, list):
            scene_dates = [scene_dates]

        for d in scene_dates:
            # Skip approximate dates
            if isinstance(d, str) and "~" in d:
                continue

            # Parse date
            if isinstance(d, date):
                dates.add(d)
            elif isinstance(d, str):
                try:
                    dates.add(date.fromisoformat(d))
                except ValueError:
                    pass  # Skip invalid formats

    return dates


def parse_md_frontmatter(content: str) -> tuple[Dict[str, Any], int, int]:
    """
    Parse MD file and extract frontmatter.

    Args:
        content: Full MD file content

    Returns:
        Tuple of (frontmatter_dict, start_index, end_index)

    Raises:
        ValueError: If no valid frontmatter found
    """
    if not content.startswith("---"):
        raise ValueError("No frontmatter found")

    end_match = re.search(r"\n---\n", content[3:])
    if not end_match:
        raise ValueError("No frontmatter end found")

    end_idx = end_match.start() + 3
    frontmatter_text = content[3:end_idx]
    frontmatter = yaml.safe_load(frontmatter_text)

    return frontmatter, 3, end_idx


def format_narrated_dates(dates: Set[date]) -> str:
    """
    Format narrated_dates for YAML frontmatter.

    Args:
        dates: Set of dates

    Returns:
        YAML-formatted string for narrated_dates field
    """
    sorted_dates = sorted(dates)

    if len(sorted_dates) <= 3:
        # Inline format for short lists
        return "[" + ", ".join(d.isoformat() for d in sorted_dates) + "]"
    else:
        # Block format for longer lists
        lines = [""]
        for d in sorted_dates:
            lines.append(f"  - {d.isoformat()}")
        return "\n".join(lines)


def update_md_frontmatter(
    md_path: Path, narrated_dates: Set[date], dry_run: bool = False
) -> bool:
    """
    Update MD frontmatter with narrated_dates field.

    Args:
        md_path: Path to MD file
        narrated_dates: Set of dates to add
        dry_run: If True, don't write changes

    Returns:
        True if file was updated (or would be), False if no changes needed
    """
    content = md_path.read_text(encoding="utf-8")

    try:
        frontmatter, start_idx, end_idx = parse_md_frontmatter(content)
    except ValueError as e:
        print(f"  Warning: {md_path.name}: {e}")
        return False

    # Get existing narrated_dates
    existing = set()
    for d in frontmatter.get("narrated_dates", []) or []:
        if isinstance(d, date):
            existing.add(d)
        elif isinstance(d, str):
            try:
                existing.add(date.fromisoformat(d))
            except ValueError:
                pass

    # Merge with new dates
    merged = existing | narrated_dates

    if merged == existing:
        return False  # No changes needed

    # Build new frontmatter
    # Remove existing narrated_dates line(s)
    frontmatter_text = content[start_idx:end_idx]

    # Remove existing narrated_dates (handles both inline and block formats)
    # First remove block format
    frontmatter_text = re.sub(
        r"\nnarrated_dates:\n(?:  - [^\n]+\n?)+", "\n", frontmatter_text
    )
    # Then remove inline format
    frontmatter_text = re.sub(r"\nnarrated_dates: \[[^\]]*\]", "", frontmatter_text)

    # Add new narrated_dates before the end
    formatted = format_narrated_dates(merged)
    if formatted.startswith("["):
        new_line = f"\nnarrated_dates: {formatted}"
    else:
        new_line = f"\nnarrated_dates:{formatted}"

    frontmatter_text = frontmatter_text.rstrip() + new_line + "\n"

    # Reconstruct file
    # end_idx points to \n before ---, so skip \n--- (4 chars) to get to content after
    new_content = "---" + frontmatter_text + "---" + content[end_idx + 4:]

    if not dry_run:
        md_path.write_text(new_content, encoding="utf-8")

    return True


def process_year(year: str, dry_run: bool = False) -> tuple[int, int]:
    """
    Process all entries for a given year.

    Args:
        year: Year string (e.g., "2024")
        dry_run: If True, don't write changes

    Returns:
        Tuple of (processed_count, updated_count)
    """
    yaml_dir = JOURNAL_YAML_DIR / year
    md_year_dir = MD_DIR / year

    if not yaml_dir.exists():
        print(f"  No metadata directory for {year}")
        return 0, 0

    processed = 0
    updated = 0

    for yaml_path in sorted(yaml_dir.glob("*.yaml")):
        entry_date = yaml_path.stem
        md_path = md_year_dir / f"{entry_date}.md"

        if not md_path.exists():
            continue

        processed += 1

        # Load YAML and extract dates
        try:
            yaml_data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  Warning: {yaml_path.name}: {e}")
            continue

        scene_dates = extract_scene_dates(yaml_data)

        if not scene_dates:
            continue

        # Update MD
        if update_md_frontmatter(md_path, scene_dates, dry_run):
            updated += 1
            action = "would update" if dry_run else "updated"
            print(f"  {action}: {entry_date} ({len(scene_dates)} dates)")

    return processed, updated


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Update MD frontmatter narrated_dates from scene dates"
    )
    parser.add_argument(
        "--year",
        type=str,
        help="Process only this year (default: 2021+)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without writing",
    )
    args = parser.parse_args()

    if args.year:
        years = [args.year]
    else:
        years = ["2021", "2022", "2023", "2024", "2025"]

    total_processed = 0
    total_updated = 0

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Updating narrated_dates...")
    print()

    for year in years:
        print(f"{year}:")
        processed, updated = process_year(year, args.dry_run)
        total_processed += processed
        total_updated += updated
        if updated == 0:
            print("  (no updates needed)")
        print()

    print(f"Total: {total_processed} files processed, {total_updated} updated")


if __name__ == "__main__":
    main()
