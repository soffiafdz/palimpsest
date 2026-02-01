#!/usr/bin/env python3
"""
add_narrated_dates.py
---------------------
Add narrated_dates field to MD frontmatter from scene dates in metadata YAML files.

This script extracts unique dates from all scenes in the corresponding metadata
YAML file and adds them as `narrated_dates: [YYYY-MM-DD, ...]` to the MD
frontmatter.

The narrated_dates field represents all dates that are narrated within an entry,
which may differ from the entry date itself (entries often narrate events from
previous days).

Usage:
    python -m dev.bin.add_narrated_dates [--dry-run] [--year YYYY]
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import argparse
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional, Set

# --- Third-party imports ---
import yaml

# --- Local imports ---
from dev.core.paths import JOURNAL_YAML_DIR, MD_DIR


def extract_scene_dates(yaml_path: Path) -> List[date]:
    """
    Extract unique dates from all scenes in a metadata YAML file.

    Skips approximate dates (starting with ~) since they represent
    uncertain dates that shouldn't be included in narrated_dates.

    Args:
        yaml_path: Path to the metadata YAML file

    Returns:
        Sorted list of unique exact dates from scenes
    """
    if not yaml_path.exists():
        return []

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data:
        return []

    dates: Set[date] = set()

    for scene in data.get("scenes", []) or []:
        scene_date = scene.get("date")
        if scene_date:
            if isinstance(scene_date, list):
                for d in scene_date:
                    if isinstance(d, date):
                        dates.add(d)
                    elif isinstance(d, str):
                        # Skip approximate dates (starting with ~)
                        if d.startswith("~"):
                            continue
                        try:
                            dates.add(date.fromisoformat(d))
                        except ValueError:
                            pass  # Skip partial dates like YYYY-MM
            elif isinstance(scene_date, date):
                dates.add(scene_date)
            elif isinstance(scene_date, str):
                # Skip approximate dates (starting with ~)
                if scene_date.startswith("~"):
                    continue
                try:
                    dates.add(date.fromisoformat(scene_date))
                except ValueError:
                    pass  # Skip partial dates like YYYY-MM

    return sorted(dates)


def format_narrated_dates(dates: List[date]) -> str:
    """
    Format narrated_dates field for YAML frontmatter.

    Args:
        dates: List of dates to format

    Returns:
        Formatted YAML line
    """
    date_strings = [d.isoformat() for d in dates]
    return f"narrated_dates: [{', '.join(date_strings)}]"


def update_md_frontmatter(md_path: Path, narrated_dates: List[date], dry_run: bool) -> bool:
    """
    Update MD file frontmatter with narrated_dates field.

    Args:
        md_path: Path to the MD file
        narrated_dates: List of dates to add
        dry_run: If True, don't write changes

    Returns:
        True if file was modified (or would be modified in dry-run)
    """
    if not md_path.exists():
        return False

    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check if file already has narrated_dates
    if "narrated_dates:" in content:
        return False

    # Check if file has frontmatter
    if not content.startswith("---"):
        return False

    # Split frontmatter and body
    parts = content.split("---", 2)
    if len(parts) < 3:
        return False

    frontmatter = parts[1]
    body = parts[2]

    # Format the new field
    narrated_dates_line = format_narrated_dates(narrated_dates)

    # Insert before the closing ---
    # Find the last non-empty line in frontmatter and add after it
    fm_lines = frontmatter.rstrip().split("\n")
    fm_lines.append(narrated_dates_line)

    new_frontmatter = "\n".join(fm_lines)
    new_content = f"---{new_frontmatter}\n---{body}"

    if not dry_run:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    return True


def process_entry(year: str, date_str: str, dry_run: bool) -> Optional[str]:
    """
    Process a single entry: extract scene dates and update MD frontmatter.

    Args:
        year: Year string (YYYY)
        date_str: Entry date string (YYYY-MM-DD)
        dry_run: If True, don't write changes

    Returns:
        Status message, or None if skipped
    """
    yaml_path = JOURNAL_YAML_DIR / year / f"{date_str}.yaml"
    md_path = MD_DIR / year / f"{date_str}.md"

    # Skip if no corresponding MD file
    if not md_path.exists():
        return None

    # Extract scene dates
    narrated_dates = extract_scene_dates(yaml_path)
    if not narrated_dates:
        return None

    # Update MD frontmatter
    if update_md_frontmatter(md_path, narrated_dates, dry_run):
        return f"{date_str}: {len(narrated_dates)} dates"

    return None


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Add narrated_dates to MD frontmatter from metadata YAML"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without writing files",
    )
    parser.add_argument(
        "--year",
        type=int,
        help="Process only entries from specific year",
    )

    args = parser.parse_args()

    print("Adding narrated_dates to MD frontmatter...")
    if args.dry_run:
        print("[DRY RUN] No files will be written.\n")

    # Find all year directories
    if not JOURNAL_YAML_DIR.exists():
        print(f"Error: {JOURNAL_YAML_DIR} not found")
        return 1

    year_dirs = sorted([d for d in JOURNAL_YAML_DIR.iterdir() if d.is_dir()])

    total_updated = 0
    total_skipped = 0

    for year_dir in year_dirs:
        year = year_dir.name

        # Apply year filter
        if args.year and year != str(args.year):
            continue

        # Process all YAML files in this year
        yaml_files = sorted(year_dir.glob("*.yaml"))

        year_updated = 0
        for yaml_file in yaml_files:
            date_str = yaml_file.stem  # YYYY-MM-DD

            result = process_entry(year, date_str, args.dry_run)
            if result:
                print(f"  {'Would update' if args.dry_run else 'Updated'}: {result}")
                year_updated += 1
            else:
                total_skipped += 1

        if year_updated > 0:
            print(f"  Year {year}: {year_updated} files\n")
            total_updated += year_updated

    print(f"\n{'Would update' if args.dry_run else 'Updated'}: {total_updated} files")
    print(f"Skipped (no scenes/already has field/no MD): {total_skipped} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
