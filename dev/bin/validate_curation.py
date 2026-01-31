#!/usr/bin/env python3
"""
validate_curation.py
--------------------
Validate per-year curation files before jumpstart import.

Checks per-file validity and cross-year consistency. Detects potential
merges (same key across years with different canonicals) and unlinked
duplicates (same key without same_as).

Curation Conventions:
    People:
        - canonical with all null fields -> name = key
        - canonical key deleted -> skip
        - skip: true -> skip
        - same_as: OtherName -> references another entry
        - self: true -> author reference

    Locations:
        - canonical: null -> canonical = key (raw name)
        - canonical key deleted -> skip
        - skip: true -> skip
        - same_as: OtherLocation -> references another entry

Usage:
    python -m dev.bin.validate_curation [--year YYYY] [--type people|locations]
    python -m dev.bin.validate_curation --check-consistency

Output:
    Reports errors, warnings, and potential merge conflicts.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import argparse
import re
import sys
import unicodedata
from collections import defaultdict
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


def normalize_name(name: str) -> str:
    """Normalize a name for comparison (lowercase, strip accents, normalize spaces)."""
    name = name.lower().strip()
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = re.sub(r"[-\s]+", " ", name)
    return name.strip()


def is_all_null_canonical(canonical: Any) -> bool:
    """Check if a canonical dict has all null values."""
    if not isinstance(canonical, dict):
        return False
    return all(v is None for v in canonical.values())


def resolve_people_entry(_raw_name: str, entry: Dict[str, Any]) -> Optional[str]:
    """
    Determine the effective state of a people entry.

    Returns:
        'canonical', 'skip', 'self', 'same_as', or None if invalid
    """
    if entry.get("skip") is True:
        return "skip"
    if entry.get("self") is True:
        return "self"
    if "same_as" in entry and entry["same_as"] is not None:
        return "same_as"
    if "canonical" in entry:
        return "canonical"
    # No canonical key -> skip
    return "skip"


def resolve_locations_entry(_raw_name: str, entry: Dict[str, Any]) -> Optional[str]:
    """
    Determine the effective state of a locations entry.

    Returns:
        'canonical', 'skip', 'same_as', or None if invalid
    """
    if entry.get("skip") is True:
        return "skip"
    if "same_as" in entry and entry["same_as"] is not None:
        return "same_as"
    if "canonical" in entry:
        return "canonical"
    # No canonical key -> skip
    return "skip"


def get_effective_people_canonical(
    raw_name: str, entry: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Get the effective canonical for a people entry, applying conventions.

    - All null fields -> name = key
    - Filled in -> use as-is
    """
    canonical = entry.get("canonical")
    if canonical is None:
        return None

    if not isinstance(canonical, dict):
        return None

    # All null convention: name = key
    if is_all_null_canonical(canonical):
        return {"name": raw_name, "lastname": None, "alias": None}

    return canonical


def get_effective_location_canonical(
    raw_name: str, entry: Dict[str, Any]
) -> Optional[str]:
    """
    Get the effective canonical for a location entry, applying conventions.

    - canonical: null -> canonical = key
    - canonical: "SomeName" -> use as-is
    """
    canonical = entry.get("canonical")
    if "canonical" not in entry:
        return None

    # null convention: canonical = key
    if canonical is None:
        return raw_name

    return str(canonical)


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
    same_as_targets: Dict[str, str] = {}

    for raw_name, entry in data.items():
        if not isinstance(entry, dict):
            errors.append(f"[{raw_name}] Invalid entry format")
            continue

        state = resolve_people_entry(raw_name, entry)

        if state == "skip" or state == "self":
            continue

        if state == "same_as":
            same_as_targets[raw_name] = entry["same_as"]
            continue

        if state == "canonical":
            canonical = entry["canonical"]
            if isinstance(canonical, list):
                # Multi-person entry
                for i, c in enumerate(canonical):
                    if not isinstance(c, dict):
                        errors.append(f"[{raw_name}] canonical[{i}] must be a dict")
                    elif not c.get("name"):
                        errors.append(f"[{raw_name}] canonical[{i}].name is required")
            else:
                effective = get_effective_people_canonical(raw_name, entry)
                if effective and not effective.get("name"):
                    errors.append(f"[{raw_name}] canonical.name is required")

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

            state = resolve_locations_entry(raw_name, entry)

            if state == "skip":
                continue

            if state == "same_as":
                same_as_targets[raw_name] = entry["same_as"]
                continue

            if state == "canonical":
                effective = get_effective_location_canonical(raw_name, entry)
                if effective is not None and not isinstance(effective, str):
                    errors.append(f"[{city}/{raw_name}] canonical must be a string")

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


# =============================================================================
# Cross-Year Consistency Check
# =============================================================================

def check_people_consistency() -> Tuple[List[str], List[str]]:
    """
    Check cross-year consistency for people curation files.

    Detects:
        - Same key across years with different canonicals (potential merge conflict)
        - Same key across years without same_as linking (unlinked duplicate)

    Returns:
        Tuple of (conflicts, suggestions)
    """
    conflicts: List[str] = []
    suggestions: List[str] = []

    # Collect all entries across years: raw_name -> [(year, canonical_dict)]
    all_entries: Dict[str, List[Tuple[str, Dict[str, Any]]]] = defaultdict(list)

    people_files = sorted(CURATION_DIR.glob("*_people_curation.yaml"))

    for path in people_files:
        year = path.stem.split("_")[0]
        data = load_yaml(path)
        if not data:
            continue

        for raw_name, entry in data.items():
            if not isinstance(entry, dict):
                continue

            state = resolve_people_entry(raw_name, entry)

            if state == "skip" or state == "self":
                continue

            if state == "same_as":
                # Resolve same_as to get effective canonical
                target = entry["same_as"]
                if not isinstance(target, str):
                    continue
                if target in data:
                    target_entry = data[target]
                    if isinstance(target_entry, dict):
                        effective = get_effective_people_canonical(target, target_entry)
                        if effective:
                            all_entries[raw_name].append((year, effective))
                continue

            if state == "canonical":
                effective = get_effective_people_canonical(raw_name, entry)
                if effective:
                    all_entries[raw_name].append((year, effective))

    # Check for conflicts
    for raw_name, year_entries in sorted(all_entries.items()):
        if len(year_entries) <= 1:
            continue

        # Compare canonicals across years
        canonicals_by_key: Dict[str, List[str]] = defaultdict(list)
        for year, canonical in year_entries:
            name = canonical.get("name") or ""
            lastname = canonical.get("lastname") or ""
            alias = canonical.get("alias") or ""
            key = f"{name}|{lastname}|{alias}".lower()
            canonicals_by_key[key].append(year)

        if len(canonicals_by_key) > 1:
            details = []
            for key, years in canonicals_by_key.items():
                parts = key.split("|")
                detail = f"  {', '.join(years)}: name={parts[0]}, lastname={parts[1]}, alias={parts[2]}"
                details.append(detail)

            conflicts.append(
                f"[{raw_name}] Different canonicals across years:\n" +
                "\n".join(details)
            )

    # Check for similar names that might be the same person but aren't linked
    all_normalized: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    for path in people_files:
        year = path.stem.split("_")[0]
        data = load_yaml(path)
        if not data:
            continue

        for raw_name, entry in data.items():
            if not isinstance(entry, dict):
                continue
            state = resolve_people_entry(raw_name, entry)
            if state in ("skip", "self"):
                continue
            normalized = normalize_name(raw_name)
            all_normalized[normalized].append((year, raw_name))

    for normalized, entries in sorted(all_normalized.items()):
        # Get unique raw names
        unique_names = set(name for _, name in entries)
        if len(unique_names) > 1:
            years_by_name: Dict[str, List[str]] = defaultdict(list)
            for year, name in entries:
                years_by_name[name].append(year)

            details = [f"  {name} ({', '.join(years)})" for name, years in sorted(years_by_name.items())]
            suggestions.append(
                f"Similar names (may need same_as):\n" +
                "\n".join(details)
            )

    return conflicts, suggestions


def check_locations_consistency() -> Tuple[List[str], List[str]]:
    """
    Check cross-year consistency for locations curation files.

    Returns:
        Tuple of (conflicts, suggestions)
    """
    conflicts: List[str] = []
    suggestions: List[str] = []

    # Collect: city -> raw_name -> [(year, canonical_name)]
    all_entries: Dict[str, Dict[str, List[Tuple[str, str]]]] = defaultdict(lambda: defaultdict(list))

    locations_files = sorted(CURATION_DIR.glob("*_locations_curation.yaml"))

    for path in locations_files:
        year = path.stem.split("_")[0]
        data = load_yaml(path)
        if not data:
            continue

        for city, locations in data.items():
            if not isinstance(locations, dict):
                continue

            for raw_name, entry in locations.items():
                if not isinstance(entry, dict):
                    continue

                state = resolve_locations_entry(raw_name, entry)
                if state == "skip":
                    continue

                if state == "same_as":
                    target = entry["same_as"]
                    if target in locations:
                        target_entry = locations[target]
                        if isinstance(target_entry, dict):
                            effective = get_effective_location_canonical(target, target_entry)
                            if effective:
                                all_entries[city][raw_name].append((year, effective))
                    continue

                if state == "canonical":
                    effective = get_effective_location_canonical(raw_name, entry)
                    if effective:
                        all_entries[city][raw_name].append((year, effective))

    # Check for conflicts within each city
    for city, locs in sorted(all_entries.items()):
        for raw_name, year_entries in sorted(locs.items()):
            if len(year_entries) <= 1:
                continue

            canonicals: Dict[str, List[str]] = defaultdict(list)
            for year, canonical_name in year_entries:
                canonicals[canonical_name.lower()].append(year)

            if len(canonicals) > 1:
                details = [f"  {', '.join(years)}: {name}" for name, years in canonicals.items()]
                conflicts.append(
                    f"[{city}/{raw_name}] Different canonicals:\n" +
                    "\n".join(details)
                )

    # Check for same location across different cities (might need merging)
    loc_by_normalized: Dict[str, List[Tuple[str, str, str]]] = defaultdict(list)
    for city, locs in all_entries.items():
        for raw_name in locs:
            normalized = normalize_name(raw_name)
            years = [y for y, _ in locs[raw_name]]
            loc_by_normalized[normalized].append((city, raw_name, ", ".join(years)))

    for normalized, entries in sorted(loc_by_normalized.items()):
        cities = set(city for city, _, _ in entries)
        if len(cities) > 1:
            details = [f"  {city}: {name} ({years})" for city, name, years in entries]
            suggestions.append(
                f"Same location in multiple cities:\n" +
                "\n".join(details)
            )

    return conflicts, suggestions


# =============================================================================
# Main Validation
# =============================================================================

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


def run_consistency_check(entity_type: Optional[str] = None) -> bool:
    """
    Run cross-year consistency checks.

    Args:
        entity_type: 'people', 'locations', or None for both

    Returns:
        True if no conflicts found, False otherwise
    """
    has_conflicts = False

    if entity_type in (None, "people"):
        print(f"\n{'='*60}")
        print("Cross-year consistency: PEOPLE")
        print("=" * 60)

        conflicts, suggestions = check_people_consistency()

        if conflicts:
            has_conflicts = True
            print(f"\nCONFLICTS ({len(conflicts)}) — must resolve before import:")
            for conflict in conflicts:
                print(f"\n  ✗ {conflict}")

        if suggestions:
            print(f"\nSUGGESTIONS ({len(suggestions)}) — review for potential merges:")
            for suggestion in suggestions:
                print(f"\n  ? {suggestion}")

        if not conflicts and not suggestions:
            print("\n✓ No conflicts or suggestions")

    if entity_type in (None, "locations"):
        print(f"\n{'='*60}")
        print("Cross-year consistency: LOCATIONS")
        print("=" * 60)

        conflicts, suggestions = check_locations_consistency()

        if conflicts:
            has_conflicts = True
            print(f"\nCONFLICTS ({len(conflicts)}) — must resolve before import:")
            for conflict in conflicts:
                print(f"\n  ✗ {conflict}")

        if suggestions:
            print(f"\nSUGGESTIONS ({len(suggestions)}) — review for potential merges:")
            for suggestion in suggestions:
                print(f"\n  ? {suggestion}")

        if not conflicts and not suggestions:
            print("\n✓ No conflicts or suggestions")

    return not has_conflicts


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
    parser.add_argument(
        "--check-consistency",
        action="store_true",
        help="Run cross-year consistency checks (potential merges, conflicts)"
    )
    args = parser.parse_args()

    if args.check_consistency:
        valid = run_consistency_check(entity_type=args.type)
    else:
        valid = validate_all(year=args.year, entity_type=args.type)

    sys.exit(0 if valid else 1)


if __name__ == "__main__":
    main()
