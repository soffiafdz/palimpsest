#!/usr/bin/env python3
"""
extract_notes.py
----------------
Extract notes fields from MD frontmatter to legacy archive.

Reads all journal MD files, extracts any 'notes' field from frontmatter,
and saves to data/legacy/notes_archive.yaml for preservation before
the MD migration removes them.

Usage:
    python -m dev.pipeline.extract_notes [--dry-run]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from dev.core.paths import MD_DIR, LEGACY_DIR, NOTES_ARCHIVE


def extract_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return {}

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}

    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}


def extract_notes(dry_run: bool = False) -> dict:
    """
    Extract notes from all MD files.

    Args:
        dry_run: If True, don't write output file

    Returns:
        Dict mapping dates to notes content
    """
    notes_archive = {}

    # Find all MD files
    md_files = sorted(MD_DIR.glob("**/*.md"))
    print(f"Scanning {len(md_files)} MD files...")

    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        frontmatter = extract_frontmatter(content)

        if "notes" in frontmatter and frontmatter["notes"]:
            # Use filename (date) as key
            date_str = md_file.stem  # e.g., "2024-12-03"
            notes_archive[date_str] = frontmatter["notes"]

    print(f"Found {len(notes_archive)} entries with notes")

    if not dry_run and notes_archive:
        # Ensure legacy directory exists
        LEGACY_DIR.mkdir(parents=True, exist_ok=True)

        # Write archive
        with open(NOTES_ARCHIVE, "w", encoding="utf-8") as f:
            yaml.dump(
                notes_archive,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=True,
            )
        print(f"Saved to {NOTES_ARCHIVE}")
    elif dry_run:
        print("[DRY RUN] Would save to", NOTES_ARCHIVE)
        # Show sample
        if notes_archive:
            sample_date = next(iter(notes_archive))
            print(f"\nSample ({sample_date}):")
            print(notes_archive[sample_date][:200] + "..." if len(notes_archive[sample_date]) > 200 else notes_archive[sample_date])

    return notes_archive


def main():
    parser = argparse.ArgumentParser(description="Extract notes from MD frontmatter")
    parser.add_argument("--dry-run", action="store_true", help="Don't write output")
    args = parser.parse_args()

    extract_notes(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
