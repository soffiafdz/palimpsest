#!/usr/bin/env python3
"""
normalize_analysis.py
---------------------
Normalize inconsistencies in narrative analysis files.

Applies mappings to standardize tag categories and motifs across
all analysis files, fixing naming inconsistencies.

Usage:
    # Preview changes (dry-run)
    python -m dev.pipeline.normalize_analysis --dry-run

    # Apply normalization
    python -m dev.pipeline.normalize_analysis
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

from dev.core.paths import JOURNAL_DIR

ANALYSIS_DIR = JOURNAL_DIR / "narrative_analysis"

# ============================================================================
# TAG CATEGORY MAPPINGS
# ============================================================================
# Maps inconsistent category names to their normalized form
TAG_CATEGORY_MAPPINGS: Dict[str, str] = {
    # Renames
    "HRT/Medication": "Medication",
    "Sex/Intimacy": "Intimacy",
    "Self-Harm": "Crisis/Suicidality",
    "BDSM/Kink": "Sexual",
    # Placeholders to remove (map to empty)
    "None significant.": "",
    "None.": "",
    "None": "",
}

# New categories to add to _propagation_mappings.py
NEW_TAG_CATEGORIES = {
    "Mental Health": [
        "mental health", "psychological", "emotional wellbeing"
    ],
}

# ============================================================================
# MOTIF MAPPINGS
# ============================================================================
# Maps inconsistent motif names to their normalized form
MOTIF_MAPPINGS: Dict[str, str] = {
    # Renames
    "MENTAL HEALTH & MEDICATION": "MENTAL HEALTH",
    "TRANSITION": "THE BODY",  # Merge - only 1 file, already paired
    "SCARCITY": "BUREAUCRATIC TRAUMA",  # Merge - about HRT shortage
    "FRIENDSHIPS": "SUPPORT NETWORK",
    # Placeholders to remove
    "None.": "",
    "None applicable.": "",
    "(None identified)": "",
    "None": "",
}

# New motifs to add to _propagation_mappings.py
NEW_MOTIFS = {
    "MENTAL HEALTH": [
        "mental health", "psychological", "emotional state", "mood",
        "depression", "anxiety", "crisis", "breakdown"
    ],
    "BUREAUCRATIC TRAUMA": [
        "bureaucra", "paperwork", "system", "institution", "denied",
        "waiting", "red tape", "government", "admin"
    ],
    "SUPPORT NETWORK": [
        "friend", "support", "help", "care", "community", "network",
        "accompan", "there for"
    ],
    "LANGUAGE & IDENTITY": [
        "bilingual", "language", "accent", "tongue", "linguistic",
        "translation", "code-switch", "immigrant identity"
    ],
    "MOTHERHOOD/CHILDLESSNESS": [
        "mother", "child", "fertility", "womb", "maternal", "childless",
        "biological clock", "parenthood"
    ],
}


def normalize_line(line: str, section: str, mappings: Dict[str, str]) -> Tuple[str, bool]:
    """
    Normalize a line based on section type and mappings.

    Args:
        line: The line to normalize
        section: Current section ("tag_categories" or "thematic_arcs")
        mappings: Mapping dict to apply

    Returns:
        Tuple of (normalized_line, was_changed)
    """
    original = line

    # Parse comma-separated values
    if "," in line or line.strip():
        items = [item.strip() for item in line.split(",")]
        normalized_items = []

        for item in items:
            if item in mappings:
                mapped = mappings[item]
                if mapped:  # Non-empty mapping
                    normalized_items.append(mapped)
                # Empty mapping = remove the item
            else:
                normalized_items.append(item)

        # Remove duplicates while preserving order
        seen: Set[str] = set()
        unique_items = []
        for item in normalized_items:
            if item and item not in seen:
                seen.add(item)
                unique_items.append(item)

        if unique_items:
            line = ", ".join(unique_items)
        else:
            line = ""

    return line, line != original


def process_file(filepath: Path, dry_run: bool = False) -> Tuple[int, int, List[str]]:
    """
    Process a single analysis file and normalize inconsistencies.

    Args:
        filepath: Path to the analysis file
        dry_run: If True, don't write changes

    Returns:
        Tuple of (tag_changes, motif_changes, change_descriptions)
    """
    content = filepath.read_text()
    lines = content.split("\n")

    tag_changes = 0
    motif_changes = 0
    changes: List[str] = []

    current_section = None
    new_lines = []

    for i, line in enumerate(lines):
        # Detect section headers
        if line.startswith("## Tag Categories"):
            current_section = "tag_categories"
            new_lines.append(line)
            continue
        elif line.startswith("## Thematic Arcs"):
            current_section = "thematic_arcs"
            new_lines.append(line)
            continue
        elif line.startswith("## "):
            current_section = None
            new_lines.append(line)
            continue

        # Process content lines based on section
        if current_section == "tag_categories" and line.strip() and not line.startswith("#"):
            new_line, changed = normalize_line(line, current_section, TAG_CATEGORY_MAPPINGS)
            if changed:
                tag_changes += 1
                changes.append(f"  Tag Categories: '{line.strip()}' → '{new_line.strip()}'")
            new_lines.append(new_line)
        elif current_section == "thematic_arcs" and line.strip() and not line.startswith("#"):
            new_line, changed = normalize_line(line, current_section, MOTIF_MAPPINGS)
            if changed:
                motif_changes += 1
                changes.append(f"  Thematic Arcs: '{line.strip()}' → '{new_line.strip()}'")
            new_lines.append(new_line)
        else:
            new_lines.append(line)

    # Write back if changes were made
    if (tag_changes > 0 or motif_changes > 0) and not dry_run:
        filepath.write_text("\n".join(new_lines))

    return tag_changes, motif_changes, changes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize narrative analysis file inconsistencies"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying files"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed changes"
    )
    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN - no files will be modified\n")

    # Find all analysis files (recursively in year subdirectories)
    analysis_files = sorted(ANALYSIS_DIR.glob("**/*_analysis.md"))

    total_tag_changes = 0
    total_motif_changes = 0
    files_changed = 0

    for filepath in analysis_files:
        tag_changes, motif_changes, changes = process_file(filepath, args.dry_run)

        if tag_changes > 0 or motif_changes > 0:
            files_changed += 1
            total_tag_changes += tag_changes
            total_motif_changes += motif_changes

            if args.verbose:
                print(f"{filepath.name}:")
                for change in changes:
                    print(change)
                print()

    print(f"Summary:")
    print(f"  Files scanned: {len(analysis_files)}")
    print(f"  Files {'would be ' if args.dry_run else ''}changed: {files_changed}")
    print(f"  Tag category changes: {total_tag_changes}")
    print(f"  Motif changes: {total_motif_changes}")

    if args.dry_run and files_changed > 0:
        print(f"\nRun without --dry-run to apply changes")

    return 0


if __name__ == "__main__":
    sys.exit(main())
