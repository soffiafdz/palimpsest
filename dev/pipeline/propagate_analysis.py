#!/usr/bin/env python3
"""
propagate_analysis.py
---------------------
Use propagation mappings to auto-assign tag categories and thematic arcs
to narrative analysis files based on their tags and themes.

This script reads each analysis file, applies the keyword mappings from
_propagation_mappings.py, and updates the Tag Categories and Thematic Arcs
sections accordingly.

Usage:
    # Preview changes (dry-run)
    python -m dev.pipeline.propagate_analysis --dry-run

    # Apply propagation
    python -m dev.pipeline.propagate_analysis

    # Verbose output showing all changes
    python -m dev.pipeline.propagate_analysis --dry-run --verbose
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Set, Tuple

from dev.core.paths import JOURNAL_DIR

# Import propagation functions
sys.path.insert(0, str(JOURNAL_DIR / "narrative_analysis"))
from _propagation_mappings import (
    clean_tags,
    get_tag_categories,
    get_thematic_arcs,
)

ANALYSIS_DIR = JOURNAL_DIR / "narrative_analysis"


def extract_section(content: str, section_name: str) -> str:
    """Extract content of a section from markdown."""
    pattern = rf"## {re.escape(section_name)}\s*\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def extract_tags(content: str) -> List[str]:
    """Extract raw tags from the Tags section."""
    tags_section = extract_section(content, "Tags")
    if not tags_section or tags_section.lower() in ["none", "none."]:
        return []
    return [t.strip() for t in tags_section.split(",") if t.strip()]


def extract_themes(content: str) -> List[str]:
    """Extract theme names from the Themes section."""
    themes_section = extract_section(content, "Themes")
    if not themes_section or "none" in themes_section.lower():
        return []

    themes = []
    # Match "- **Theme Name:**" or "- *Theme Name*:" patterns
    pattern = r"-\s*\*{1,2}([^*:]+):\*{1,2}"
    matches = re.findall(pattern, themes_section)
    themes.extend([m.strip() for m in matches])

    # Also try simpler pattern for themes without descriptions
    if not themes:
        pattern = r"-\s*\*{1,2}([^*]+)\*{1,2}"
        matches = re.findall(pattern, themes_section)
        themes.extend([m.strip() for m in matches])

    return themes


def extract_current_categories(content: str) -> Set[str]:
    """Extract current tag categories from file."""
    section = extract_section(content, "Tag Categories")
    if not section or section.lower() in ["none", "none.", "none significant."]:
        return set()
    return {c.strip() for c in section.split(",") if c.strip()}


def extract_current_arcs(content: str) -> Set[str]:
    """Extract current thematic arcs from file."""
    section = extract_section(content, "Thematic Arcs")
    if not section or section.lower() in ["none", "none.", "none applicable.", "(none identified)"]:
        return set()
    return {a.strip() for a in section.split(",") if a.strip()}


def update_section(content: str, section_name: str, new_value: str) -> str:
    """Update a section's content in the markdown."""
    pattern = rf"(## {re.escape(section_name)}\s*\n)(.*?)(?=\n## |\Z)"

    def replacement(match):
        return match.group(1) + new_value + "\n"

    return re.sub(pattern, replacement, content, flags=re.DOTALL)


def process_file(
    filepath: Path,
    dry_run: bool = False,
    verbose: bool = False,
    categories_only: bool = False,
    arcs_only: bool = False,
) -> Tuple[int, int, List[str]]:
    """
    Process a single analysis file and propagate categories/arcs.

    Returns:
        Tuple of (category_changes, arc_changes, change_descriptions)
    """
    content = filepath.read_text()
    changes = []

    # Extract raw data
    raw_tags = extract_tags(content)
    themes = extract_themes(content)

    # Get current assignments
    current_categories = extract_current_categories(content)
    current_arcs = extract_current_arcs(content)

    # Compute what should be assigned using propagation mappings
    cleaned_tags = clean_tags(", ".join(raw_tags)) if raw_tags else []
    computed_categories = set(get_tag_categories(cleaned_tags)) if cleaned_tags else set()
    computed_arcs = set(get_thematic_arcs(themes)) if themes else set()

    # Merge: keep existing + add computed
    # (Don't remove manually assigned ones, only add missing)
    new_categories = current_categories | computed_categories
    new_arcs = current_arcs | computed_arcs

    # Track changes (respecting filter flags)
    added_categories = set()
    added_arcs = set()

    if not arcs_only:
        added_categories = new_categories - current_categories
    if not categories_only:
        added_arcs = new_arcs - current_arcs

    category_changes = len(added_categories)
    arc_changes = len(added_arcs)

    if added_categories:
        changes.append(f"  +Categories: {', '.join(sorted(added_categories))}")
    if added_arcs:
        changes.append(f"  +Arcs: {', '.join(sorted(added_arcs))}")

    # Update file if changes needed
    if (category_changes > 0 or arc_changes > 0) and not dry_run:
        new_content = content

        if category_changes > 0:
            new_cat_str = ", ".join(sorted(new_categories))
            new_content = update_section(new_content, "Tag Categories", new_cat_str)

        if arc_changes > 0:
            new_arc_str = ", ".join(sorted(new_arcs))
            new_content = update_section(new_content, "Thematic Arcs", new_arc_str)

        filepath.write_text(new_content)

    return category_changes, arc_changes, changes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Propagate tag categories and thematic arcs using keyword mappings"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying files"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed changes per file"
    )
    parser.add_argument(
        "--categories-only",
        action="store_true",
        help="Only propagate tag categories, skip thematic arcs"
    )
    parser.add_argument(
        "--arcs-only",
        action="store_true",
        help="Only propagate thematic arcs, skip tag categories"
    )
    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN - no files will be modified\n")

    # Find all analysis files (recursively in year subdirectories)
    analysis_files = sorted(ANALYSIS_DIR.glob("**/*_analysis.md"))

    total_cat_changes = 0
    total_arc_changes = 0
    files_changed = 0

    for filepath in analysis_files:
        cat_changes, arc_changes, changes = process_file(
            filepath,
            dry_run=args.dry_run,
            verbose=args.verbose,
            categories_only=args.categories_only,
            arcs_only=args.arcs_only,
        )

        if cat_changes > 0 or arc_changes > 0:
            files_changed += 1
            total_cat_changes += cat_changes
            total_arc_changes += arc_changes

            if args.verbose:
                print(f"{filepath.name}:")
                for change in changes:
                    print(change)
                print()

    print(f"Summary:")
    print(f"  Files scanned: {len(analysis_files)}")
    print(f"  Files {'would be ' if args.dry_run else ''}changed: {files_changed}")
    print(f"  Categories added: {total_cat_changes}")
    print(f"  Arcs added: {total_arc_changes}")

    if args.dry_run and files_changed > 0:
        print(f"\nRun without --dry-run to apply changes")

    return 0


if __name__ == "__main__":
    sys.exit(main())
