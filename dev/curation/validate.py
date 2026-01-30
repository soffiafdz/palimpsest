#!/usr/bin/env python3
"""
validate.py
-----------
Validate per-year curation files before database import.

This module provides validation for curation files, checking both
per-file validity and cross-year consistency. It detects potential
conflicts (same key with different canonicals) and suggests possible
merges (similar names without same_as links).

Curation Conventions:
    People:
        - canonical with all null fields -> name = key
        - canonical key missing -> skip
        - skip: true -> skip
        - same_as: OtherName -> references another entry
        - self: true -> author reference

    Locations:
        - canonical: null -> canonical = key (raw name)
        - canonical key missing -> skip
        - skip: true -> skip
        - same_as: OtherLocation -> references another entry

Key Features:
    - Per-file validation (required fields, format)
    - Cross-year consistency checks (conflicts, suggestions)
    - Circular reference detection in same_as chains
    - Similar name detection for potential merges

Usage:
    from dev.curation.validate import validate_all, check_consistency

    # Validate all files
    results = validate_all()

    # Check cross-year consistency
    consistency = check_consistency(entity_type="people")
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# --- Third-party imports ---
import yaml

# --- Local imports ---
from dev.core.logging_manager import PalimpsestLogger
from dev.core.paths import CURATION_DIR, LOG_DIR
from dev.curation.models import ConsistencyResult, ValidationResult


# =============================================================================
# Utility Functions
# =============================================================================

def load_yaml(path: Path) -> Optional[Dict[str, Any]]:
    """
    Load a YAML file, returning None on error.

    Args:
        path: Path to the YAML file

    Returns:
        Parsed YAML content, or None if loading fails
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return None


def normalize_name(name: str) -> str:
    """
    Normalize a name for comparison.

    Converts to lowercase, strips accents, and normalizes whitespace.

    Args:
        name: Name to normalize

    Returns:
        Normalized name string
    """
    name = name.lower().strip()
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = re.sub(r"[-\s]+", " ", name)
    return name.strip()


def is_all_null_canonical(canonical: Any) -> bool:
    """
    Check if a canonical dict has all null values.

    Args:
        canonical: Canonical dict to check

    Returns:
        True if all values are None
    """
    if not isinstance(canonical, dict):
        return False
    return all(v is None for v in canonical.values())


# =============================================================================
# Entry Resolution
# =============================================================================

def resolve_people_entry(_raw_name: str, entry: Dict[str, Any]) -> Optional[str]:
    """
    Determine the effective state of a people entry.

    Args:
        _raw_name: Raw name key (unused but kept for signature consistency)
        entry: Entry dict from curation file

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

    Args:
        _raw_name: Raw name key (unused but kept for signature consistency)
        entry: Entry dict from curation file

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

    Args:
        raw_name: Raw name key
        entry: Entry dict from curation file

    Returns:
        Effective canonical dict, or None if entry should be skipped
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

    Args:
        raw_name: Raw name key
        entry: Entry dict from curation file

    Returns:
        Effective canonical string, or None if entry should be skipped
    """
    canonical = entry.get("canonical")
    if "canonical" not in entry:
        return None

    # null convention: canonical = key
    if canonical is None:
        return raw_name

    return str(canonical)


# =============================================================================
# Per-File Validation
# =============================================================================

def validate_people_file(path: Path) -> ValidationResult:
    """
    Validate a people curation file.

    Checks for:
        - Valid YAML format
        - Required fields (canonical.name for non-skip entries)
        - Valid same_as references
        - No circular same_as chains

    Args:
        path: Path to the curation file

    Returns:
        ValidationResult with errors and warnings
    """
    result = ValidationResult(file_path=str(path))

    data = load_yaml(path)
    if data is None:
        result.add_error(f"Failed to load {path.name}")
        return result

    all_names = set(data.keys())
    same_as_targets: Dict[str, str] = {}

    for raw_name, entry in data.items():
        if not isinstance(entry, dict):
            result.add_error(f"[{raw_name}] Invalid entry format")
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
                        result.add_error(f"[{raw_name}] canonical[{i}] must be a dict")
                    elif not c.get("name"):
                        result.add_error(f"[{raw_name}] canonical[{i}].name is required")
            else:
                effective = get_effective_people_canonical(raw_name, entry)
                if effective and not effective.get("name"):
                    result.add_error(f"[{raw_name}] canonical.name is required")

        # Check dates exist
        if "dates" not in entry or not entry["dates"]:
            result.add_warning(f"[{raw_name}] No dates listed")

    # Validate same_as references
    for name, target in same_as_targets.items():
        if target not in all_names:
            result.add_error(
                f"[{name}] same_as references non-existent entry: {target}"
            )

    # Check for cycles in same_as
    for name in same_as_targets:
        visited: Set[str] = set()
        current = name
        while current in same_as_targets:
            if current in visited:
                result.add_error(f"[{name}] Circular same_as reference detected")
                break
            visited.add(current)
            current = same_as_targets[current]

    return result


def validate_locations_file(path: Path) -> ValidationResult:
    """
    Validate a locations curation file.

    Checks for:
        - Valid YAML format
        - Valid city/location structure
        - Valid same_as references within city
        - No circular same_as chains

    Args:
        path: Path to the curation file

    Returns:
        ValidationResult with errors and warnings
    """
    result = ValidationResult(file_path=str(path))

    data = load_yaml(path)
    if data is None:
        result.add_error(f"Failed to load {path.name}")
        return result

    for city, locations in data.items():
        if not isinstance(locations, dict):
            result.add_error(f"[{city}] Invalid city format")
            continue

        all_locs = set(locations.keys())
        same_as_targets: Dict[str, str] = {}

        for raw_name, entry in locations.items():
            if not isinstance(entry, dict):
                result.add_error(f"[{city}/{raw_name}] Invalid entry format")
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
                    result.add_error(f"[{city}/{raw_name}] canonical must be a string")

            # Check dates exist
            if "dates" not in entry or not entry["dates"]:
                result.add_warning(f"[{city}/{raw_name}] No dates listed")

        # Validate same_as references within city
        for name, target in same_as_targets.items():
            if target not in all_locs:
                result.add_error(
                    f"[{city}/{name}] same_as references non-existent entry: {target}"
                )

        # Check for cycles
        for name in same_as_targets:
            visited: Set[str] = set()
            current = name
            while current in same_as_targets:
                if current in visited:
                    result.add_error(
                        f"[{city}/{name}] Circular same_as reference detected"
                    )
                    break
                visited.add(current)
                current = same_as_targets[current]

    return result


# =============================================================================
# Cross-Year Consistency Checks
# =============================================================================

def check_people_consistency() -> ConsistencyResult:
    """
    Check cross-year consistency for people curation files.

    Detects:
        - Same key across years with different canonicals (conflict)
        - Similar names that might be the same person (suggestion)

    Returns:
        ConsistencyResult with conflicts and suggestions
    """
    result = ConsistencyResult(entity_type="people")

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
                detail = (
                    f"  {', '.join(years)}: "
                    f"name={parts[0]}, lastname={parts[1]}, alias={parts[2]}"
                )
                details.append(detail)

            result.conflicts.append(
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

            details = [
                f"  {name} ({', '.join(years)})"
                for name, years in sorted(years_by_name.items())
            ]
            result.suggestions.append(
                f"Similar names (may need same_as):\n" +
                "\n".join(details)
            )

    return result


def check_locations_consistency() -> ConsistencyResult:
    """
    Check cross-year consistency for locations curation files.

    Detects:
        - Same location across years with different canonicals (conflict)
        - Same location in multiple cities (suggestion)

    Returns:
        ConsistencyResult with conflicts and suggestions
    """
    result = ConsistencyResult(entity_type="locations")

    # Collect: city -> raw_name -> [(year, canonical_name)]
    all_entries: Dict[str, Dict[str, List[Tuple[str, str]]]] = defaultdict(
        lambda: defaultdict(list)
    )

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
                            effective = get_effective_location_canonical(
                                target, target_entry
                            )
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
                details = [
                    f"  {', '.join(years)}: {name}"
                    for name, years in canonicals.items()
                ]
                result.conflicts.append(
                    f"[{city}/{raw_name}] Different canonicals:\n" +
                    "\n".join(details)
                )

    # Check for same location across different cities
    loc_by_normalized: Dict[str, List[Tuple[str, str, str]]] = defaultdict(list)
    for city, locs in all_entries.items():
        for raw_name in locs:
            normalized = normalize_name(raw_name)
            years = [y for y, _ in locs[raw_name]]
            loc_by_normalized[normalized].append((city, raw_name, ", ".join(years)))

    for normalized, entries in sorted(loc_by_normalized.items()):
        cities = set(city for city, _, _ in entries)
        if len(cities) > 1:
            details = [
                f"  {city}: {name} ({years})"
                for city, name, years in entries
            ]
            result.suggestions.append(
                f"Same location in multiple cities:\n" +
                "\n".join(details)
            )

    return result


# =============================================================================
# Main Validation Functions
# =============================================================================

def validate_all(
    year: Optional[str] = None,
    entity_type: Optional[str] = None,
    logger: Optional[PalimpsestLogger] = None,
) -> List[ValidationResult]:
    """
    Validate curation files.

    Args:
        year: Specific year to validate, or None for all
        entity_type: 'people', 'locations', or None for both
        logger: Optional logger for operation tracking

    Returns:
        List of ValidationResult objects
    """
    if logger is None:
        log_dir = LOG_DIR / "operations"
        log_dir.mkdir(parents=True, exist_ok=True)
        logger = PalimpsestLogger(log_dir, component_name="validate")

    results: List[ValidationResult] = []

    # Find files to validate
    people_files: List[Path] = []
    locations_files: List[Path] = []

    if entity_type in (None, "people"):
        pattern = f"{year}_people_curation.yaml" if year else "*_people_curation.yaml"
        people_files = sorted(CURATION_DIR.glob(pattern))

    if entity_type in (None, "locations"):
        pattern = (
            f"{year}_locations_curation.yaml" if year else "*_locations_curation.yaml"
        )
        locations_files = sorted(CURATION_DIR.glob(pattern))

    if not people_files and not locations_files:
        logger.log_warning("No curation files found.")
        return results

    # Validate people files
    for path in people_files:
        logger.log_info(f"Validating: {path.name}")
        result = validate_people_file(path)
        results.append(result)

        if result.errors:
            for err in result.errors[:10]:
                logger.log_error(err)
        if result.warnings:
            for warn in result.warnings[:5]:
                logger.log_warning(warn)

        logger.log_info(result.summary())

    # Validate locations files
    for path in locations_files:
        logger.log_info(f"Validating: {path.name}")
        result = validate_locations_file(path)
        results.append(result)

        if result.errors:
            for err in result.errors[:10]:
                logger.log_error(err)
        if result.warnings:
            for warn in result.warnings[:5]:
                logger.log_warning(warn)

        logger.log_info(result.summary())

    return results


def check_consistency(
    entity_type: Optional[str] = None,
    logger: Optional[PalimpsestLogger] = None,
) -> List[ConsistencyResult]:
    """
    Run cross-year consistency checks.

    Args:
        entity_type: 'people', 'locations', or None for both
        logger: Optional logger for operation tracking

    Returns:
        List of ConsistencyResult objects
    """
    if logger is None:
        log_dir = LOG_DIR / "operations"
        log_dir.mkdir(parents=True, exist_ok=True)
        logger = PalimpsestLogger(log_dir, component_name="validate")

    results: List[ConsistencyResult] = []

    if entity_type in (None, "people"):
        logger.log_info("Checking cross-year consistency: PEOPLE")
        result = check_people_consistency()
        results.append(result)

        if result.conflicts:
            logger.log_warning(f"{len(result.conflicts)} conflicts found")
            for conflict in result.conflicts[:5]:
                logger.log_warning(conflict)

        if result.suggestions:
            logger.log_info(f"{len(result.suggestions)} suggestions")

    if entity_type in (None, "locations"):
        logger.log_info("Checking cross-year consistency: LOCATIONS")
        result = check_locations_consistency()
        results.append(result)

        if result.conflicts:
            logger.log_warning(f"{len(result.conflicts)} conflicts found")
            for conflict in result.conflicts[:5]:
                logger.log_warning(conflict)

        if result.suggestions:
            logger.log_info(f"{len(result.suggestions)} suggestions")

    return results
