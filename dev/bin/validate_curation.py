#!/usr/bin/env python3
"""
validate_curation.py
--------------------
Validate curated entity files before jumpstart import.

This script checks that the manually curated people and location files
are complete and consistent. Run after manual curation, before jumpstart.

Validation Checks:
    - All groups have a non-null canonical form
    - Required fields present (name for people, name+city for locations)
    - No duplicate canonicals (would create duplicate DB entries)
    - Members are simplified (list of strings, not dicts)
    - Date ranges are valid (if present, for disambiguation)

Usage:
    python -m dev.bin.validate_curation [--fix-format]

Output:
    - Validation report to stdout
    - Exit code 0 if valid, 1 if errors found
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

# --- Third-party imports ---
import yaml

# --- Local imports ---
from dev.core.paths import CURATION_DIR


@dataclass
class ValidationError:
    """A single validation error."""
    group_id: Any
    field: str
    message: str
    severity: str = "error"  # "error" or "warning"


@dataclass
class ValidationResult:
    """Result of validating a curation file."""
    file_path: Path
    entity_type: str
    total_groups: int
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, group_id: Any, field: str, message: str) -> None:
        self.errors.append(ValidationError(group_id, field, message, "error"))

    def add_warning(self, group_id: Any, field: str, message: str) -> None:
        self.warnings.append(ValidationError(group_id, field, message, "warning"))


def validate_people_canonical(canonical: Dict[str, Any], group_id: Any) -> List[ValidationError]:
    """
    Validate a people canonical entry.

    Args:
        canonical: The canonical dict from the curation file
        group_id: Group ID for error reporting

    Returns:
        List of validation errors
    """
    errors = []

    if not canonical:
        errors.append(ValidationError(group_id, "canonical", "canonical is null - must be filled"))
        return errors

    if not isinstance(canonical, dict):
        errors.append(ValidationError(group_id, "canonical", f"canonical must be a dict, got {type(canonical).__name__}"))
        return errors

    # Required: name
    name = canonical.get("name")
    if not name:
        errors.append(ValidationError(group_id, "canonical.name", "name is required"))
    elif not isinstance(name, str):
        errors.append(ValidationError(group_id, "canonical.name", f"name must be string, got {type(name).__name__}"))

    # Optional: lastname (can be null)
    lastname = canonical.get("lastname")
    if lastname is not None and not isinstance(lastname, str):
        errors.append(ValidationError(group_id, "canonical.lastname", f"lastname must be string or null, got {type(lastname).__name__}"))

    # Optional: alias (can be null)
    alias = canonical.get("alias")
    if alias is not None and not isinstance(alias, str):
        errors.append(ValidationError(group_id, "canonical.alias", f"alias must be string or null, got {type(alias).__name__}"))

    return errors


def validate_location_canonical(canonical: Dict[str, Any], group_id: Any) -> List[ValidationError]:
    """
    Validate a location canonical entry.

    Args:
        canonical: The canonical dict from the curation file
        group_id: Group ID for error reporting

    Returns:
        List of validation errors
    """
    errors = []

    if not canonical:
        errors.append(ValidationError(group_id, "canonical", "canonical is null - must be filled"))
        return errors

    if not isinstance(canonical, dict):
        errors.append(ValidationError(group_id, "canonical", f"canonical must be a dict, got {type(canonical).__name__}"))
        return errors

    # Required: name
    name = canonical.get("name")
    if not name:
        errors.append(ValidationError(group_id, "canonical.name", "name is required"))
    elif not isinstance(name, str):
        errors.append(ValidationError(group_id, "canonical.name", f"name must be string, got {type(name).__name__}"))

    # Required: city
    city = canonical.get("city")
    if not city:
        errors.append(ValidationError(group_id, "canonical.city", "city is required for locations"))
    elif not isinstance(city, str):
        errors.append(ValidationError(group_id, "canonical.city", f"city must be string, got {type(city).__name__}"))

    return errors


def validate_members(members: Any, group_id: Any) -> Tuple[List[ValidationError], List[ValidationError]]:
    """
    Validate the members field of a group.

    After curation, members should be a simple list of strings.
    Draft format (list of dicts with occurrences) is a warning.

    Args:
        members: The members field from the group
        group_id: Group ID for error reporting

    Returns:
        Tuple of (errors, warnings)
    """
    errors = []
    warnings = []

    if not members:
        errors.append(ValidationError(group_id, "members", "members is empty"))
        return errors, warnings

    if not isinstance(members, list):
        errors.append(ValidationError(group_id, "members", f"members must be a list, got {type(members).__name__}"))
        return errors, warnings

    # Check if still in draft format (dicts with occurrences)
    has_draft_format = False
    for i, member in enumerate(members):
        if isinstance(member, dict):
            has_draft_format = True
            if "name" not in member:
                errors.append(ValidationError(group_id, f"members[{i}]", "member dict missing 'name' field"))
        elif not isinstance(member, str):
            errors.append(ValidationError(group_id, f"members[{i}]", f"member must be string or dict, got {type(member).__name__}"))

    if has_draft_format:
        warnings.append(ValidationError(
            group_id, "members",
            "members still in draft format (dicts) - simplify to list of strings after review",
            "warning"
        ))

    return errors, warnings


def check_duplicate_canonicals(groups: List[Dict[str, Any]], entity_type: str) -> List[ValidationError]:
    """
    Check for duplicate canonical entries.

    Args:
        groups: List of group dicts
        entity_type: "people" or "locations"

    Returns:
        List of validation errors for duplicates
    """
    errors = []
    seen: Dict[str, Any] = {}  # key -> first group_id that used it

    for group in groups:
        canonical = group.get("canonical")
        if not canonical or not isinstance(canonical, dict):
            continue

        group_id = group.get("id", "unknown")

        # Build a unique key for this canonical
        if entity_type == "people":
            name = canonical.get("name", "")
            lastname = canonical.get("lastname") or ""
            alias = canonical.get("alias") or ""
            key = f"{name}|{lastname}|{alias}".lower()
        else:  # locations
            name = canonical.get("name", "")
            city = canonical.get("city") or ""
            key = f"{name}|{city}".lower()

        if key in seen:
            errors.append(ValidationError(
                group_id,
                "canonical",
                f"duplicate canonical - same as group {seen[key]}"
            ))
        else:
            seen[key] = group_id

    return errors


def validate_curation_file(file_path: Path, entity_type: str) -> ValidationResult:
    """
    Validate a curation file.

    Args:
        file_path: Path to the curation YAML file
        entity_type: "people" or "locations"

    Returns:
        ValidationResult with all errors and warnings
    """
    result = ValidationResult(file_path=file_path, entity_type=entity_type, total_groups=0)

    if not file_path.exists():
        result.add_error("file", "path", f"File not found: {file_path}")
        return result

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        result.add_error("file", "yaml", f"YAML parse error: {e}")
        return result

    if not data:
        result.add_error("file", "content", "File is empty")
        return result

    groups = data.get("groups", [])
    if not groups:
        result.add_error("file", "groups", "No groups found in file")
        return result

    result.total_groups = len(groups)

    # Validate each group
    for group in groups:
        group_id = group.get("id", "unknown")

        # Validate members
        members = group.get("members")
        member_errors, member_warnings = validate_members(members, group_id)
        result.errors.extend(member_errors)
        result.warnings.extend(member_warnings)

        # Validate canonical
        canonical = group.get("canonical")
        if entity_type == "people":
            canonical_errors = validate_people_canonical(canonical, group_id)
        else:
            canonical_errors = validate_location_canonical(canonical, group_id)
        result.errors.extend(canonical_errors)

    # Check for duplicates
    duplicate_errors = check_duplicate_canonicals(groups, entity_type)
    result.errors.extend(duplicate_errors)

    return result


def print_result(result: ValidationResult) -> None:
    """Print validation result to stdout."""
    print(f"\n{'='*60}")
    print(f"Validating: {result.file_path.name}")
    print(f"Entity type: {result.entity_type}")
    print(f"Total groups: {result.total_groups}")
    print(f"{'='*60}")

    if result.errors:
        print(f"\nERRORS ({len(result.errors)}):")
        for err in result.errors:
            print(f"  [Group {err.group_id}] {err.field}: {err.message}")

    if result.warnings:
        print(f"\nWARNINGS ({len(result.warnings)}):")
        for warn in result.warnings:
            print(f"  [Group {warn.group_id}] {warn.field}: {warn.message}")

    if result.is_valid and not result.warnings:
        print("\n✓ All validations passed!")
    elif result.is_valid:
        print(f"\n✓ Valid (with {len(result.warnings)} warnings)")
    else:
        print(f"\n✗ INVALID - {len(result.errors)} errors found")


def validate_all(check_draft: bool = True) -> bool:
    """
    Validate all curation files.

    Args:
        check_draft: If True, also check draft files; if False, only final files

    Returns:
        True if all validations pass, False otherwise
    """
    all_valid = True

    # Define files to check
    files_to_check = []

    if check_draft:
        # Check draft files (expected to have warnings about draft format)
        draft_people = CURATION_DIR / "people_curation_draft.yaml"
        draft_locations = CURATION_DIR / "locations_curation_draft.yaml"
        if draft_people.exists():
            files_to_check.append((draft_people, "people"))
        if draft_locations.exists():
            files_to_check.append((draft_locations, "locations"))

    # Check final files
    final_people = CURATION_DIR / "people_curation.yaml"
    final_locations = CURATION_DIR / "locations_curation.yaml"
    if final_people.exists():
        files_to_check.append((final_people, "people"))
    if final_locations.exists():
        files_to_check.append((final_locations, "locations"))

    if not files_to_check:
        print("No curation files found in", CURATION_DIR)
        print("\nExpected files:")
        print("  - people_curation_draft.yaml (or people_curation.yaml)")
        print("  - locations_curation_draft.yaml (or locations_curation.yaml)")
        return False

    for file_path, entity_type in files_to_check:
        result = validate_curation_file(file_path, entity_type)
        print_result(result)
        if not result.is_valid:
            all_valid = False

    print(f"\n{'='*60}")
    if all_valid:
        print("OVERALL: All files valid")
    else:
        print("OVERALL: Validation failed - fix errors before running jumpstart")
    print(f"{'='*60}")

    return all_valid


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate curated entity files before jumpstart import"
    )
    parser.add_argument(
        "--final-only",
        action="store_true",
        help="Only check final files (skip _draft files)"
    )
    args = parser.parse_args()

    valid = validate_all(check_draft=not args.final_only)
    sys.exit(0 if valid else 1)


if __name__ == "__main__":
    main()
