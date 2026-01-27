#!/usr/bin/env python3
"""
validate_curation.py
--------------------
Validate per-year curation files before jumpstart import.

Checks that all entries have been curated (canonical, same_as, skip, or self)
and that references are valid.

Usage:
    python -m dev.bin.validate_curation [--year YYYY] [--type people|locations]

Output:
    Reports errors and warnings for each file.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# --- Third-party imports ---
import yaml

# --- Local imports ---
from dev.core.paths import CURATION_DIR


def load_yaml(path: Path) -> Optional[Dict[str, Any]]:
    """Load a YAML file, returning None on error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        print(f"Error loading {path}: {e}")
        return None


def validate_people_file(path: Path) -> Tuple[List[str], List[str]]:
    """
    Validate a people curation file.

    Returns:
        Tuple of (errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []

    data = load_yaml(path)
    if data is None:
        errors.append(f"Failed to load {path.name}")
        return errors, warnings

    all_names = set(data.keys())
    same_as_targets: Dict[str, str] = {}  # name -> target

    for raw_name, entry in data.items():
        if not isinstance(entry, dict):
            errors.append(f"[{raw_name}] Invalid entry format")
            continue

        # Check for required fields
        has_canonical = "canonical" in entry and entry["canonical"] is not None
        has_same_as = "same_as" in entry and entry["same_as"] is not None
        has_skip = entry.get("skip") is True
        has_self = entry.get("self") is True

        # Must have exactly one of these
        markers = sum([has_canonical, has_same_as, has_skip, has_self])

        if markers == 0:
            errors.append(f"[{raw_name}] Not curated (missing canonical, same_as, skip, or self)")
        elif markers > 1:
            errors.append(f"[{raw_name}] Multiple markers (should have only one of canonical, same_as, skip, self)")

        # Validate canonical structure
        if has_canonical:
            canonical = entry["canonical"]
            if not isinstance(canonical, dict):
                errors.append(f"[{raw_name}] canonical must be a dict with name, lastname, alias")
            elif not canonical.get("name"):
                errors.append(f"[{raw_name}] canonical.name is required")

        # Track same_as for cycle detection
        if has_same_as:
            same_as_targets[raw_name] = entry["same_as"]

        # Check dates exist
        if "dates" not in entry or not entry["dates"]:
            warnings.append(f"[{raw_name}] No dates listed")

    # Validate same_as references
    for name, target in same_as_targets.items():
        if target not in all_names:
            errors.append(f"[{name}] same_as references non-existent entry: {target}")

    # Check for cycles in same_as
    for name in same_as_targets:
        visited: Set[str] = set()
        current = name
        while current in same_as_targets:
            if current in visited:
                errors.append(f"[{name}] Circular same_as reference detected")
                break
            visited.add(current)
            current = same_as_targets[current]

    return errors, warnings


def validate_locations_file(path: Path) -> Tuple[List[str], List[str]]:
    """
    Validate a locations curation file.

    Returns:
        Tuple of (errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []

    data = load_yaml(path)
    if data is None:
        errors.append(f"Failed to load {path.name}")
        return errors, warnings

    for city, locations in data.items():
        if not isinstance(locations, dict):
            errors.append(f"[{city}] Invalid city format")
            continue

        all_locs = set(locations.keys())
        same_as_targets: Dict[str, str] = {}

        for raw_name, entry in locations.items():
            if not isinstance(entry, dict):
                errors.append(f"[{city}/{raw_name}] Invalid entry format")
                continue

            # Check for required fields
            has_canonical = "canonical" in entry and entry["canonical"] is not None
            has_same_as = "same_as" in entry and entry["same_as"] is not None
            has_skip = entry.get("skip") is True

            markers = sum([has_canonical, has_same_as, has_skip])

            if markers == 0:
                errors.append(f"[{city}/{raw_name}] Not curated (missing canonical, same_as, or skip)")
            elif markers > 1:
                errors.append(f"[{city}/{raw_name}] Multiple markers (should have only one)")

            # Validate canonical is a string
            if has_canonical and not isinstance(entry["canonical"], str):
                errors.append(f"[{city}/{raw_name}] canonical must be a string")

            # Track same_as
            if has_same_as:
                same_as_targets[raw_name] = entry["same_as"]

            # Check dates exist
            if "dates" not in entry or not entry["dates"]:
                warnings.append(f"[{city}/{raw_name}] No dates listed")

        # Validate same_as references within city
        for name, target in same_as_targets.items():
            if target not in all_locs:
                errors.append(f"[{city}/{name}] same_as references non-existent entry: {target}")

        # Check for cycles
        for name in same_as_targets:
            visited: Set[str] = set()
            current = name
            while current in same_as_targets:
                if current in visited:
                    errors.append(f"[{city}/{name}] Circular same_as reference detected")
                    break
                visited.add(current)
                current = same_as_targets[current]

    return errors, warnings


def validate_all(
    year: Optional[str] = None,
    entity_type: Optional[str] = None,
) -> bool:
    """
    Validate curation files.

    Args:
        year: Specific year to validate, or None for all
        entity_type: 'people', 'locations', or None for both

    Returns:
        True if all files are valid, False otherwise
    """
    all_valid = True

    # Find files to validate
    people_files = []
    locations_files = []

    if entity_type in (None, "people"):
        pattern = f"{year}_people_curation.yaml" if year else "*_people_curation.yaml"
        people_files = sorted(CURATION_DIR.glob(pattern))

    if entity_type in (None, "locations"):
        pattern = f"{year}_locations_curation.yaml" if year else "*_locations_curation.yaml"
        locations_files = sorted(CURATION_DIR.glob(pattern))

    if not people_files and not locations_files:
        print("No curation files found.")
        return False

    # Validate people files
    for path in people_files:
        print(f"\n{'='*60}")
        print(f"Validating: {path.name}")
        print("=" * 60)

        errors, warnings = validate_people_file(path)

        if errors:
            all_valid = False
            print(f"\nERRORS ({len(errors)}):")
            for err in errors[:50]:
                print(f"  ✗ {err}")
            if len(errors) > 50:
                print(f"  ... and {len(errors) - 50} more")

        if warnings:
            print(f"\nWARNINGS ({len(warnings)}):")
            for warn in warnings[:10]:
                print(f"  ⚠ {warn}")
            if len(warnings) > 10:
                print(f"  ... and {len(warnings) - 10} more")

        if not errors:
            print(f"\n✓ Valid" + (f" (with {len(warnings)} warnings)" if warnings else ""))

    # Validate locations files
    for path in locations_files:
        print(f"\n{'='*60}")
        print(f"Validating: {path.name}")
        print("=" * 60)

        errors, warnings = validate_locations_file(path)

        if errors:
            all_valid = False
            print(f"\nERRORS ({len(errors)}):")
            for err in errors[:50]:
                print(f"  ✗ {err}")
            if len(errors) > 50:
                print(f"  ... and {len(errors) - 50} more")

        if warnings:
            print(f"\nWARNINGS ({len(warnings)}):")
            for warn in warnings[:10]:
                print(f"  ⚠ {warn}")
            if len(warnings) > 10:
                print(f"  ... and {len(warnings) - 10} more")

        if not errors:
            print(f"\n✓ Valid" + (f" (with {len(warnings)} warnings)" if warnings else ""))

    # Summary
    print(f"\n{'='*60}")
    if all_valid:
        print("OVERALL: All files valid")
    else:
        print("OVERALL: Validation failed - fix errors above")
    print("=" * 60)

    return all_valid


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate per-year curation files"
    )
    parser.add_argument(
        "--year",
        type=str,
        help="Specific year to validate (e.g., 2024)"
    )
    parser.add_argument(
        "--type",
        choices=["people", "locations"],
        help="Validate only people or locations"
    )
    args = parser.parse_args()

    valid = validate_all(year=args.year, entity_type=args.type)
    sys.exit(0 if valid else 1)


if __name__ == "__main__":
    main()
