#!/usr/bin/env python3
"""
fix_rating_justification.py
---------------------------
Strip **Justification:** prefix from rating_justification field in metadata YAML files.

This is a one-time data cleanup script to fix the 243 files that have the
**Justification:** markdown prefix in their rating_justification field.

Usage:
    python -m dev.bin.fix_rating_justification [--dry-run]
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import argparse
import re
import sys
from pathlib import Path

# --- Third-party imports ---
import yaml

# --- Local imports ---
from dev.core.paths import JOURNAL_YAML_DIR


def strip_justification_prefix(text: str) -> str:
    """
    Remove **Justification:** prefix from text.

    Args:
        text: The rating_justification text

    Returns:
        Text with prefix removed
    """
    if not text:
        return text

    # Match **Justification:** at the start, with optional whitespace
    pattern = r"^\*\*Justification:\*\*\s*"
    return re.sub(pattern, "", text, flags=re.IGNORECASE)


def process_file(file_path: Path, dry_run: bool) -> bool:
    """
    Process a single YAML file to fix rating_justification.

    Args:
        file_path: Path to the YAML file
        dry_run: If True, don't write changes

    Returns:
        True if file was modified
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check if file has the prefix
    if "**Justification:**" not in content:
        return False

    # Load YAML
    data = yaml.safe_load(content)
    if not data:
        return False

    rating_justification = data.get("rating_justification")
    if not rating_justification:
        return False

    # Strip prefix
    fixed = strip_justification_prefix(rating_justification)
    if fixed == rating_justification:
        return False

    # Update the value
    data["rating_justification"] = fixed

    if not dry_run:
        # Preserve the original YAML formatting as much as possible
        # by doing a regex replacement on the content
        # This is safer than re-dumping the entire YAML
        pattern = r"(rating_justification:\s*>-?\n\s*)\*\*Justification:\*\*\s*"
        new_content = re.sub(pattern, r"\1", content)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    return True


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Strip **Justification:** prefix from rating_justification"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without writing files",
    )

    args = parser.parse_args()

    print("Scanning for files with **Justification:** prefix...")

    # Find all YAML files
    yaml_files = sorted(JOURNAL_YAML_DIR.glob("**/*.yaml"))
    fixed_count = 0

    for yaml_file in yaml_files:
        if process_file(yaml_file, args.dry_run):
            fixed_count += 1
            if args.dry_run:
                print(f"  Would fix: {yaml_file}")
            else:
                print(f"  Fixed: {yaml_file.name}")

    print(f"\n{'Would fix' if args.dry_run else 'Fixed'}: {fixed_count} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
