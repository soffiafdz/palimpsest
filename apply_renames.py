#!/usr/bin/env python3
"""
apply_renames.py
----------------
Apply scene and event name renames from proposal JSON files to YAML metadata.

Safety features:
- Creates backup of each file before modification
- Validates YAML syntax after each change
- Dry-run mode to preview changes
- Logs all changes made
- Updates both names AND cross-references in events' scenes arrays

Usage:
    python apply_renames.py --dry-run    # Preview changes
    python apply_renames.py              # Apply changes
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


# Configuration
BASE_DIR = Path("/home/soffiafdz/Documents/palimpsest")
METADATA_DIR = BASE_DIR / "data/metadata/journal"
BACKUP_DIR = BASE_DIR / "backups" / datetime.now().strftime("%Y%m%d_%H%M%S")

# Proposal files to process
PROPOSAL_FILES = [
    "proposals_2021.json",
    "proposals_2022_jan_mar.json",
    "proposals_2022_apr_nov.json",
    "proposals_2023.json",
    "proposals_2024_jan_feb.json",
    "proposals_2024_mar.json",
    "proposals_2024_apr_jul.json",
]


def load_proposals(filepath: Path) -> Dict[str, List[Dict[str, str]]]:
    """
    Load and normalize proposals from a JSON file.

    Handles multiple formats:
    - Format 1: {date: {scenes: [...], events: [...]}}
    - Format 2: {date: [{current, proposed}]}
    - Format 3: {scenes: {date: [...]}, events: {date: [...]}}

    Returns normalized format: {date: [{old, new, type}]}
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    normalized = {}

    # Check format by examining first key
    first_key = next(iter(data.keys()), None)
    if not first_key:
        return normalized

    # Format 3: {scenes: {...}, events: {...}}
    if first_key in ('scenes', 'events'):
        for change_type in ('scenes', 'events'):
            if change_type not in data:
                continue
            for date, changes in data[change_type].items():
                if date not in normalized:
                    normalized[date] = []
                for change in changes:
                    old = change.get('current') or change.get('old')
                    new = change.get('proposed') or change.get('new')
                    if old and new:
                        normalized[date].append({
                            'old': old,
                            'new': new,
                            'type': 'scene' if change_type == 'scenes' else 'event'
                        })

    # Format 1 or 2
    else:
        for date, value in data.items():
            if date not in normalized:
                normalized[date] = []

            # Format 1: {scenes: [...], events: [...]}
            if isinstance(value, dict) and ('scenes' in value or 'events' in value):
                for change_type in ('scenes', 'events'):
                    for change in value.get(change_type, []):
                        old = change.get('current') or change.get('old')
                        new = change.get('proposed') or change.get('new')
                        if old and new:
                            normalized[date].append({
                                'old': old,
                                'new': new,
                                'type': 'scene' if change_type == 'scenes' else 'event'
                            })

            # Format 2: [{current, proposed}]
            elif isinstance(value, list):
                for change in value:
                    old = change.get('current') or change.get('old')
                    new = change.get('proposed') or change.get('new')
                    if old and new:
                        normalized[date].append({
                            'old': old,
                            'new': new,
                            'type': 'unknown'  # Will be determined by context
                        })

    return normalized


def validate_yaml(filepath: Path) -> bool:
    """Validate that a file contains valid YAML."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            yaml.safe_load(f)
        return True
    except yaml.YAMLError as e:
        print(f"  ERROR: Invalid YAML after changes: {e}")
        return False


def backup_file(filepath: Path) -> Path:
    """Create a backup of a file."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Preserve directory structure in backup
    relative = filepath.relative_to(METADATA_DIR)
    backup_path = BACKUP_DIR / relative
    backup_path.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(filepath, backup_path)
    return backup_path


def escape_for_regex(s: str) -> str:
    """Escape special regex characters in a string."""
    return re.escape(s)


def apply_rename(content: str, old_name: str, new_name: str) -> Tuple[str, int]:
    """
    Apply a single rename to file content.

    Handles:
    - Scene/event name: `  - name: Old Name` or `  - name: "Old Name"`
    - Event scene references: `      - Old Name` or `      - "Old Name"`

    Returns: (new_content, number_of_replacements)
    """
    count = 0
    new_content = content

    # Pattern 1: Scene/event name definition (with or without quotes)
    # Matches: `  - name: Old Name` or `  - name: "Old Name"`
    old_escaped = escape_for_regex(old_name)

    # Try quoted version first
    pattern_quoted = rf'(  - name: "){old_escaped}(")'
    if re.search(pattern_quoted, new_content):
        new_content = re.sub(pattern_quoted, rf'\g<1>{new_name}\g<2>', new_content)
        count += 1
    else:
        # Try unquoted version
        pattern_unquoted = rf'(  - name: ){old_escaped}$'
        matches = list(re.finditer(pattern_unquoted, new_content, re.MULTILINE))
        if matches:
            # Replace from end to preserve positions
            for match in reversed(matches):
                start, end = match.span()
                prefix = match.group(1)
                new_content = new_content[:start] + prefix + new_name + new_content[end:]
                count += 1

    # Pattern 2: Scene references in events' scenes arrays
    # Matches: `      - Old Name` or `      - "Old Name"` (more indented, in scenes list)

    # Quoted reference
    pattern_ref_quoted = rf'(      - "){old_escaped}(")'
    if re.search(pattern_ref_quoted, new_content):
        new_content = re.sub(pattern_ref_quoted, rf'\g<1>{new_name}\g<2>', new_content)
        count += 1

    # Unquoted reference
    pattern_ref_unquoted = rf'(      - ){old_escaped}$'
    matches = list(re.finditer(pattern_ref_unquoted, new_content, re.MULTILINE))
    if matches:
        for match in reversed(matches):
            start, end = match.span()
            prefix = match.group(1)
            new_content = new_content[:start] + prefix + new_name + new_content[end:]
            count += 1

    return new_content, count


def process_file(filepath: Path, changes: List[Dict[str, str]], dry_run: bool = True) -> Tuple[int, int]:
    """
    Process a single YAML file with the given changes.

    Returns: (successful_changes, failed_changes)
    """
    if not filepath.exists():
        print(f"  WARNING: File not found: {filepath}")
        return 0, len(changes)

    # Read original content
    with open(filepath, 'r', encoding='utf-8') as f:
        original_content = f.read()

    content = original_content
    successful = 0
    failed = 0

    for change in changes:
        old_name = change['old']
        new_name = change['new']

        # Skip if already renamed
        if old_name not in content:
            print(f"    SKIP: '{old_name}' not found (may already be renamed)")
            continue

        new_content, count = apply_rename(content, old_name, new_name)

        if count > 0:
            content = new_content
            print(f"    OK: '{old_name}' -> '{new_name}' ({count} occurrence(s))")
            successful += 1
        else:
            print(f"    WARN: Pattern not matched for '{old_name}'")
            failed += 1

    # If changes were made
    if content != original_content:
        if dry_run:
            print(f"  DRY-RUN: Would update {filepath.name}")
        else:
            # Create backup
            backup_path = backup_file(filepath)
            print(f"  BACKUP: {backup_path}")

            # Write new content
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            # Validate YAML
            if not validate_yaml(filepath):
                print(f"  ROLLBACK: Restoring from backup due to invalid YAML")
                shutil.copy2(backup_path, filepath)
                return 0, len(changes)

            print(f"  UPDATED: {filepath.name}")

    return successful, failed


def main():
    parser = argparse.ArgumentParser(description="Apply scene/event renames to YAML files")
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    args = parser.parse_args()

    print("=" * 60)
    print("Scene/Event Rename Script")
    print("=" * 60)
    print(f"Mode: {'DRY-RUN (no changes will be made)' if args.dry_run else 'APPLY CHANGES'}")
    print(f"Metadata directory: {METADATA_DIR}")
    if not args.dry_run:
        print(f"Backup directory: {BACKUP_DIR}")
    print()

    # Load all proposals
    all_proposals = {}
    for proposal_file in PROPOSAL_FILES:
        filepath = BASE_DIR / proposal_file
        if not filepath.exists():
            print(f"WARNING: Proposal file not found: {proposal_file}")
            continue

        print(f"Loading: {proposal_file}")
        proposals = load_proposals(filepath)

        # Merge into all_proposals
        for date, changes in proposals.items():
            if date not in all_proposals:
                all_proposals[date] = []
            all_proposals[date].extend(changes)

    print(f"\nTotal dates with changes: {len(all_proposals)}")
    total_changes = sum(len(c) for c in all_proposals.values())
    print(f"Total changes to apply: {total_changes}")
    print()

    # Process each file
    total_successful = 0
    total_failed = 0

    for date in sorted(all_proposals.keys()):
        changes = all_proposals[date]

        # Determine year from date
        year = date[:4]
        filepath = METADATA_DIR / year / f"{date}.yaml"

        print(f"\nProcessing: {date} ({len(changes)} changes)")

        successful, failed = process_file(filepath, changes, dry_run=args.dry_run)
        total_successful += successful
        total_failed += failed

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Successful changes: {total_successful}")
    print(f"Failed/skipped: {total_failed}")
    if not args.dry_run:
        print(f"Backups saved to: {BACKUP_DIR}")

    return 0 if total_failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
