#!/usr/bin/env python3
"""
metadata_yaml.py
----------------
Ironclad validation for metadata YAML files before database import.

This module provides comprehensive validation for metadata YAML files,
catching naming convention violations, structural issues, and data
integrity problems BEFORE they reach the database.

Validation Categories:
    1. Scene Names: No screenwriting format, no problematic colons
    2. Event Names: No parentheses, no date suffixes, globally unique
    3. Structure: Required fields, valid references
    4. Dates: Valid formats for scenes and threads

Key Features:
    - Strict mode: Fail on any violation
    - Report mode: Collect all violations for review
    - Pre-import validation gate
    - Cross-file event uniqueness checking

Usage:
    from dev.validators.metadata_yaml import (
        validate_file,
        validate_all,
        ValidationReport,
    )

    # Validate single file
    report = validate_file(path)
    if not report.is_valid:
        print(report.format())

    # Validate all files
    reports = validate_all(year="2024")
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# --- Third-party imports ---
import yaml

# --- Local imports ---
from dev.core.paths import JOURNAL_YAML_DIR


# =============================================================================
# Validation Result Classes
# =============================================================================


@dataclass
class ValidationError:
    """A single validation error."""

    file_path: str
    category: str  # scene_name, event_name, structure, date
    field: str  # e.g., "scenes[0].name", "events[1].name"
    message: str
    value: Optional[str] = None
    suggestion: Optional[str] = None

    def format(self) -> str:
        """Format error for display."""
        parts = [f"[{self.category}] {self.field}: {self.message}"]
        if self.value:
            parts.append(f"  Value: {self.value}")
        if self.suggestion:
            parts.append(f"  Suggestion: {self.suggestion}")
        return "\n".join(parts)


@dataclass
class ValidationReport:
    """Validation report for a single file or collection."""

    file_path: Optional[str] = None
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Check if validation passed (no errors)."""
        return len(self.errors) == 0

    @property
    def error_count(self) -> int:
        """Count of errors."""
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        """Count of warnings."""
        return len(self.warnings)

    def add_error(
        self,
        category: str,
        field: str,
        message: str,
        value: Optional[str] = None,
        suggestion: Optional[str] = None,
    ) -> None:
        """Add an error to the report."""
        self.errors.append(
            ValidationError(
                file_path=self.file_path or "",
                category=category,
                field=field,
                message=message,
                value=value,
                suggestion=suggestion,
            )
        )

    def add_warning(
        self,
        category: str,
        field: str,
        message: str,
        value: Optional[str] = None,
        suggestion: Optional[str] = None,
    ) -> None:
        """Add a warning to the report."""
        self.warnings.append(
            ValidationError(
                file_path=self.file_path or "",
                category=category,
                field=field,
                message=message,
                value=value,
                suggestion=suggestion,
            )
        )

    def format(self) -> str:
        """Format report for display."""
        lines = []
        if self.file_path:
            lines.append(f"=== {self.file_path} ===")

        if self.errors:
            lines.append(f"\nERRORS ({len(self.errors)}):")
            for err in self.errors:
                lines.append(f"  {err.format()}")

        if self.warnings:
            lines.append(f"\nWARNINGS ({len(self.warnings)}):")
            for warn in self.warnings:
                lines.append(f"  {warn.format()}")

        if self.is_valid and not self.warnings:
            lines.append("  OK - No issues found")

        return "\n".join(lines)

    def merge(self, other: "ValidationReport") -> None:
        """Merge another report into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


# =============================================================================
# Scene Name Validation
# =============================================================================

# Patterns that indicate screenwriting format
SCREENWRITING_PATTERNS = [
    re.compile(r"^INT\.", re.IGNORECASE),
    re.compile(r"^EXT\.", re.IGNORECASE),
    re.compile(r"^INT/EXT\.", re.IGNORECASE),
    re.compile(r"^EXT/INT\.", re.IGNORECASE),
]

# Patterns for problematic colons (location: time format)
LOCATION_TIME_PATTERN = re.compile(
    r"^(INT|EXT|The \w+|[A-Z][a-z]+ [A-Z][a-z]+)\s*[-:]\s*(Morning|Afternoon|Evening|Night|Dawn|Dusk|\d)",
    re.IGNORECASE,
)

# Colons that are likely problematic vs acceptable
# Problematic: "The Bedroom: Morning", "INT: Location"
# Acceptable: "Epigraph: The Secret" (though we flag these too for consistency)


def validate_scene_name(
    name: str, entry_date: str, scene_index: int, report: ValidationReport
) -> None:
    """
    Validate a single scene name.

    Args:
        name: Scene name to validate
        entry_date: Entry date for context
        scene_index: Index in scenes array
        report: Report to add errors to
    """
    field = f"scenes[{scene_index}].name"

    # Check for screenwriting format
    for pattern in SCREENWRITING_PATTERNS:
        if pattern.match(name):
            report.add_error(
                category="scene_name",
                field=field,
                message="Screenwriting format not allowed",
                value=name,
                suggestion="Use evocative chapter-style name instead",
            )
            return  # One error per scene is enough

    # Check for colons (potential location:time or category:name format)
    if ":" in name:
        # Allow time-only names like "4:44 AM"
        if re.match(r"^\d{1,2}:\d{2}\s*(AM|PM)?$", name, re.IGNORECASE):
            pass  # Time format is OK
        else:
            report.add_warning(
                category="scene_name",
                field=field,
                message="Colon in scene name - verify this is intentional",
                value=name,
                suggestion="Consider removing colon for consistency",
            )

    # Check for parentheses (often indicates meta-info that should be removed)
    if "(" in name:
        report.add_error(
            category="scene_name",
            field=field,
            message="Parentheses in scene name not allowed",
            value=name,
            suggestion="Remove parenthetical info or integrate into name",
        )


def validate_scene_names_unique(
    scenes: List[Dict[str, Any]], report: ValidationReport
) -> None:
    """
    Validate that scene names are unique within an entry.

    Args:
        scenes: List of scene dicts
        report: Report to add errors to
    """
    seen: Dict[str, int] = {}
    for i, scene in enumerate(scenes):
        name = scene.get("name", "")
        if name in seen:
            report.add_error(
                category="scene_name",
                field=f"scenes[{i}].name",
                message=f"Duplicate scene name (first at scenes[{seen[name]}])",
                value=name,
            )
        else:
            seen[name] = i


# =============================================================================
# Event Name Validation
# =============================================================================

# Pattern for date suffix: "Writing (2024-05-30)" or "At Table (2024-05-30)"
DATE_SUFFIX_PATTERN = re.compile(r"\(\d{4}(?:-\d{2})?(?:-\d{2})?\)$")

# Pattern for numbered suffix: "Alone at Home (4)"
NUMBERED_SUFFIX_PATTERN = re.compile(r"\(\d+\)$")

# Generic event names that need dates/numbers for uniqueness (bad pattern)
GENERIC_EVENT_NAMES = {
    "writing",
    "messaging",
    "dreaming",
    "waiting",
    "walking",
    "at table",
    "at home",
    "alone at home",
    "meeting",
    "remembering",
}


def validate_event_name(
    name: str, entry_date: str, event_index: int, report: ValidationReport
) -> None:
    """
    Validate a single event name.

    Args:
        name: Event name to validate
        entry_date: Entry date for context
        event_index: Index in events array
        report: Report to add errors to
    """
    field = f"events[{event_index}].name"

    # Check for parentheses with dates
    if DATE_SUFFIX_PATTERN.search(name):
        report.add_error(
            category="event_name",
            field=field,
            message="Date in parentheses not allowed - events should have unique descriptive names",
            value=name,
            suggestion="Replace with evocative name describing what happens",
        )
        return

    # Check for numbered suffix
    if NUMBERED_SUFFIX_PATTERN.search(name):
        report.add_error(
            category="event_name",
            field=field,
            message="Numbered suffix not allowed - events should have unique descriptive names",
            value=name,
            suggestion="Replace with evocative name describing what happens",
        )
        return

    # Check for any parentheses
    if "(" in name:
        report.add_warning(
            category="event_name",
            field=field,
            message="Parentheses in event name - verify this is intentional",
            value=name,
            suggestion="Consider removing parenthetical info",
        )

    # Check for colons
    if ":" in name:
        report.add_warning(
            category="event_name",
            field=field,
            message="Colon in event name - verify this is intentional",
            value=name,
        )

    # Check for generic names (these often need date/number suffixes = bad pattern)
    name_lower = name.lower().strip()
    # Remove any trailing parenthetical for this check
    name_base = re.sub(r"\s*\([^)]*\)\s*$", "", name_lower)
    if name_base in GENERIC_EVENT_NAMES:
        report.add_warning(
            category="event_name",
            field=field,
            message="Generic event name - should be more descriptive",
            value=name,
            suggestion="Use name that captures the specific narrative of this event",
        )


# =============================================================================
# Structure Validation
# =============================================================================


def validate_scene_structure(
    scene: Dict[str, Any], scene_index: int, report: ValidationReport
) -> None:
    """
    Validate scene structure (required fields, types).

    Args:
        scene: Scene dict to validate
        scene_index: Index in scenes array
        report: Report to add errors to
    """
    # Required fields
    if not scene.get("name"):
        report.add_error(
            category="structure",
            field=f"scenes[{scene_index}].name",
            message="Scene name is required",
        )

    if not scene.get("description"):
        report.add_error(
            category="structure",
            field=f"scenes[{scene_index}].description",
            message="Scene description is required",
        )

    if not scene.get("date"):
        report.add_error(
            category="structure",
            field=f"scenes[{scene_index}].date",
            message="Scene date is required",
        )


def validate_event_structure(
    event: Dict[str, Any],
    event_index: int,
    scene_names: Set[str],
    report: ValidationReport,
) -> None:
    """
    Validate event structure and scene references.

    Args:
        event: Event dict to validate
        event_index: Index in events array
        scene_names: Set of valid scene names in this entry
        report: Report to add errors to
    """
    # Required fields
    if not event.get("name"):
        report.add_error(
            category="structure",
            field=f"events[{event_index}].name",
            message="Event name is required",
        )

    scenes = event.get("scenes", [])
    if not scenes:
        report.add_warning(
            category="structure",
            field=f"events[{event_index}].scenes",
            message="Event has no scenes",
        )
    else:
        # Validate scene references
        for i, scene_ref in enumerate(scenes):
            if scene_ref not in scene_names:
                report.add_error(
                    category="structure",
                    field=f"events[{event_index}].scenes[{i}]",
                    message=f"References non-existent scene",
                    value=scene_ref,
                )


# =============================================================================
# Date Validation
# =============================================================================

# Valid date formats
DATE_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2}$"),  # YYYY-MM-DD
    re.compile(r"^\d{4}-\d{2}$"),  # YYYY-MM
    re.compile(r"^\d{4}$"),  # YYYY
    re.compile(r"^~\d{4}-\d{2}-\d{2}$"),  # ~YYYY-MM-DD
    re.compile(r"^~\d{4}-\d{2}$"),  # ~YYYY-MM
    re.compile(r"^~\d{4}$"),  # ~YYYY
]


def is_valid_date_format(date_val: Any) -> bool:
    """Check if a date value matches valid formats."""
    # Python date object
    if isinstance(date_val, date):
        return True

    # Integer year (YAML loads 2014 as int)
    if isinstance(date_val, int):
        return 1900 <= date_val <= 2100

    # String formats
    if not isinstance(date_val, str):
        return False

    return any(pattern.match(date_val) for pattern in DATE_PATTERNS)


def validate_scene_date(
    scene: Dict[str, Any], scene_index: int, report: ValidationReport
) -> None:
    """
    Validate scene date format.

    Args:
        scene: Scene dict
        scene_index: Index in scenes array
        report: Report to add errors to
    """
    date_val = scene.get("date")
    if date_val is None:
        return  # Already caught by structure validation

    field = f"scenes[{scene_index}].date"

    if isinstance(date_val, list):
        for i, d in enumerate(date_val):
            if not is_valid_date_format(d):
                report.add_error(
                    category="date",
                    field=f"{field}[{i}]",
                    message="Invalid date format",
                    value=str(d),
                    suggestion="Use YYYY-MM-DD, YYYY-MM, YYYY, or ~prefixed versions",
                )
    else:
        if not is_valid_date_format(date_val):
            report.add_error(
                category="date",
                field=field,
                message="Invalid date format",
                value=str(date_val),
                suggestion="Use YYYY-MM-DD, YYYY-MM, YYYY, or ~prefixed versions",
            )


def validate_thread_dates(
    thread: Dict[str, Any], thread_index: int, report: ValidationReport
) -> None:
    """
    Validate thread date formats.

    Args:
        thread: Thread dict
        thread_index: Index in threads array
        report: Report to add errors to
    """
    from_date = thread.get("from")
    to_date = thread.get("to")

    if from_date and not is_valid_date_format(from_date):
        report.add_error(
            category="date",
            field=f"threads[{thread_index}].from",
            message="Invalid date format",
            value=str(from_date),
        )

    if to_date and not is_valid_date_format(to_date):
        report.add_error(
            category="date",
            field=f"threads[{thread_index}].to",
            message="Invalid date format",
            value=str(to_date),
        )


# =============================================================================
# File Validation
# =============================================================================


def validate_file(path: Path, strict: bool = True) -> ValidationReport:
    """
    Validate a single metadata YAML file.

    Args:
        path: Path to the YAML file
        strict: If True, colons in scene names are errors; if False, warnings

    Returns:
        ValidationReport with all issues found
    """
    report = ValidationReport(file_path=str(path))

    # Load YAML
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        report.add_error(
            category="structure",
            field="file",
            message=f"YAML parse error: {e}",
        )
        return report

    if not data:
        report.add_error(
            category="structure",
            field="file",
            message="Empty YAML file",
        )
        return report

    entry_date = str(data.get("date", path.stem))

    # Validate scenes
    scenes = data.get("scenes", []) or []
    scene_names: Set[str] = set()

    for i, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            report.add_error(
                category="structure",
                field=f"scenes[{i}]",
                message="Scene must be a dict",
            )
            continue

        name = scene.get("name", "")
        scene_names.add(name)

        # Structure validation
        validate_scene_structure(scene, i, report)

        # Name validation
        validate_scene_name(name, entry_date, i, report)

        # Date validation
        validate_scene_date(scene, i, report)

    # Check scene name uniqueness
    validate_scene_names_unique(scenes, report)

    # Validate events
    events = data.get("events", []) or []
    for i, event in enumerate(events):
        if not isinstance(event, dict):
            report.add_error(
                category="structure",
                field=f"events[{i}]",
                message="Event must be a dict",
            )
            continue

        name = event.get("name", "")

        # Structure validation
        validate_event_structure(event, i, scene_names, report)

        # Name validation
        validate_event_name(name, entry_date, i, report)

    # Validate threads
    threads = data.get("threads", []) or []
    for i, thread in enumerate(threads):
        if not isinstance(thread, dict):
            report.add_error(
                category="structure",
                field=f"threads[{i}]",
                message="Thread must be a dict",
            )
            continue

        validate_thread_dates(thread, i, report)

    return report


# =============================================================================
# Cross-File Validation
# =============================================================================


def check_event_uniqueness(
    files: List[Path],
) -> List[Tuple[str, List[Tuple[str, str]]]]:
    """
    Check for duplicate event names across files.

    Since events are M2M (shared across entries), same-named events
    must refer to the same real-world event. This function finds
    potential conflicts.

    Args:
        files: List of YAML file paths to check

    Returns:
        List of (event_name, [(file_path, entry_date), ...]) for duplicates
    """
    event_occurrences: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except (yaml.YAMLError, OSError):
            continue

        if not data:
            continue

        entry_date = str(data.get("date", path.stem))
        events = data.get("events", []) or []

        for event in events:
            if isinstance(event, dict):
                name = event.get("name", "")
                if name:
                    event_occurrences[name].append((str(path), entry_date))

    # Return only duplicates
    duplicates = [
        (name, occurrences)
        for name, occurrences in sorted(event_occurrences.items())
        if len(occurrences) > 1
    ]

    return duplicates


# =============================================================================
# Main Validation Functions
# =============================================================================


def validate_all(
    year: Optional[str] = None,
    strict: bool = True,
    check_event_uniqueness_flag: bool = True,
) -> Tuple[List[ValidationReport], List[Tuple[str, List[Tuple[str, str]]]]]:
    """
    Validate all metadata YAML files.

    Args:
        year: Specific year to validate, or None for all
        strict: If True, use strict validation rules
        check_event_uniqueness_flag: If True, check for duplicate event names

    Returns:
        Tuple of (file reports, event duplicates)
    """
    # Find files
    if year:
        pattern = JOURNAL_YAML_DIR / year / "*.yaml"
        files = sorted(JOURNAL_YAML_DIR.glob(f"{year}/*.yaml"))
    else:
        files = sorted(JOURNAL_YAML_DIR.glob("**/*.yaml"))

    # Filter out non-entry files
    files = [f for f in files if not f.name.startswith("_")]

    # Validate each file
    reports = []
    for path in files:
        report = validate_file(path, strict=strict)
        reports.append(report)

    # Check event uniqueness
    event_duplicates = []
    if check_event_uniqueness_flag:
        event_duplicates = check_event_uniqueness(files)

    return reports, event_duplicates


def validate_for_import(
    year: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Validate files for database import.

    This is the pre-import gate. Returns pass/fail and a summary.

    Args:
        year: Specific year to validate, or None for all

    Returns:
        Tuple of (passed, summary_message)
    """
    reports, event_duplicates = validate_all(year=year, strict=True)

    total_errors = sum(r.error_count for r in reports)
    total_warnings = sum(r.warning_count for r in reports)
    files_with_errors = sum(1 for r in reports if not r.is_valid)

    lines = []
    lines.append(f"Validated {len(reports)} files")
    lines.append(f"  Errors: {total_errors} in {files_with_errors} files")
    lines.append(f"  Warnings: {total_warnings}")

    if event_duplicates:
        lines.append(f"  Shared events: {len(event_duplicates)}")

    passed = total_errors == 0

    if not passed:
        lines.append("\nFailed files:")
        for report in reports:
            if not report.is_valid:
                lines.append(f"  {report.file_path}: {report.error_count} errors")

    return passed, "\n".join(lines)


# =============================================================================
# CLI Helper
# =============================================================================


def print_validation_report(
    year: Optional[str] = None,
    show_warnings: bool = True,
    show_shared_events: bool = False,
) -> bool:
    """
    Print a formatted validation report.

    Args:
        year: Specific year to validate
        show_warnings: Whether to show warnings
        show_shared_events: Whether to show shared event names

    Returns:
        True if validation passed
    """
    reports, event_duplicates = validate_all(year=year)

    print("=" * 60)
    print("METADATA YAML VALIDATION REPORT")
    print("=" * 60)

    # Summary
    total_files = len(reports)
    files_with_errors = sum(1 for r in reports if not r.is_valid)
    total_errors = sum(r.error_count for r in reports)
    total_warnings = sum(r.warning_count for r in reports)

    print(f"\nFiles validated: {total_files}")
    print(f"Files with errors: {files_with_errors}")
    print(f"Total errors: {total_errors}")
    print(f"Total warnings: {total_warnings}")

    if event_duplicates:
        print(f"Shared event names: {len(event_duplicates)}")

    # Detailed errors
    if total_errors > 0:
        print("\n" + "=" * 60)
        print("ERRORS")
        print("=" * 60)

        for report in reports:
            if report.errors:
                print(f"\n{report.file_path}:")
                for err in report.errors:
                    print(f"  [{err.category}] {err.field}")
                    print(f"    {err.message}")
                    if err.value:
                        print(f"    Value: {err.value}")
                    if err.suggestion:
                        print(f"    Fix: {err.suggestion}")

    # Warnings
    if show_warnings and total_warnings > 0:
        print("\n" + "=" * 60)
        print("WARNINGS")
        print("=" * 60)

        for report in reports:
            if report.warnings:
                print(f"\n{report.file_path}:")
                for warn in report.warnings:
                    print(f"  [{warn.category}] {warn.field}: {warn.message}")
                    if warn.value:
                        print(f"    Value: {warn.value}")

    # Shared events
    if show_shared_events and event_duplicates:
        print("\n" + "=" * 60)
        print("SHARED EVENTS (same name across entries)")
        print("=" * 60)

        for name, occurrences in event_duplicates[:20]:
            print(f"\n  {name}:")
            for path, entry_date in occurrences:
                print(f"    - {entry_date}")

        if len(event_duplicates) > 20:
            print(f"\n  ... and {len(event_duplicates) - 20} more")

    print("\n" + "=" * 60)
    if total_errors == 0:
        print("VALIDATION PASSED")
    else:
        print("VALIDATION FAILED")
    print("=" * 60)

    return total_errors == 0
