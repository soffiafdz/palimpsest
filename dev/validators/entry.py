#!/usr/bin/env python3
"""
entry.py
--------
Unified validation for journal entries (MD frontmatter + metadata YAML).

This module provides a single entry point for validating journal data,
designed to be called from nvim on file save or from CLI.

Validation Scope:
    - MD Frontmatter: required fields, field types, format
    - Metadata YAML: structure, scene/event naming, required fields
    - Consistency: MD ↔ YAML people matching, scene subsets

Output Format:
    Returns ValidationResult with errors in quickfix-compatible format:
    {file}:{line}:{col}: {severity}: {message}

Usage:
    from dev.validators.entry import validate_entry, validate_file

    # Validate by entry date (checks both MD and YAML)
    result = validate_entry("2024-12-03")

    # Validate single file (auto-detects type)
    result = validate_file(Path("path/to/file.md"))
    result = validate_file(Path("path/to/file.yaml"))

    # For nvim integration (quickfix format)
    for error in result.errors:
        print(error.quickfix_line())

CLI Integration:
    plm validate-entry 2024-12-03
    plm validate-entry --file path/to/file.yaml
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# --- Third-party imports ---
import yaml

# --- Local imports ---
from dev.core.paths import JOURNAL_YAML_DIR, MD_DIR
from dev.utils.name_matching import (
    extract_people_keys,
    get_person_keys,
    normalize_name,
    person_in_set,
)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ValidationIssue:
    """
    A single validation issue.

    Attributes:
        file_path: Path to the file with the issue
        line: Line number (1-indexed, 0 if unknown)
        col: Column number (1-indexed, 0 if unknown)
        severity: 'error' or 'warning'
        message: Description of the issue
        field: Optional field name where issue was found
    """

    file_path: str
    line: int
    col: int
    severity: str  # 'error' or 'warning'
    message: str
    field: Optional[str] = None

    def quickfix_line(self) -> str:
        """Format for nvim quickfix list."""
        return f"{self.file_path}:{self.line}:{self.col}: {self.severity}: {self.message}"

    def __str__(self) -> str:
        return self.quickfix_line()


@dataclass
class ValidationResult:
    """
    Result of validation.

    Attributes:
        errors: List of error issues (block import)
        warnings: List of warning issues (informational)
        file_path: Primary file that was validated
    """

    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    file_path: str = ""

    @property
    def is_valid(self) -> bool:
        """True if no errors (warnings are OK)."""
        return len(self.errors) == 0

    @property
    def all_issues(self) -> List[ValidationIssue]:
        """All issues (errors + warnings)."""
        return self.errors + self.warnings

    def add_error(
        self,
        message: str,
        line: int = 0,
        col: int = 0,
        field: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> None:
        """Add an error issue."""
        self.errors.append(
            ValidationIssue(
                file_path=file_path or self.file_path,
                line=line,
                col=col,
                severity="error",
                message=message,
                field=field,
            )
        )

    def add_warning(
        self,
        message: str,
        line: int = 0,
        col: int = 0,
        field: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> None:
        """Add a warning issue."""
        self.warnings.append(
            ValidationIssue(
                file_path=file_path or self.file_path,
                line=line,
                col=col,
                severity="warning",
                message=message,
                field=field,
            )
        )

    def merge(self, other: "ValidationResult") -> None:
        """Merge another result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)

    def quickfix_output(self) -> str:
        """Get all issues in quickfix format."""
        return "\n".join(issue.quickfix_line() for issue in self.all_issues)


# =============================================================================
# MD Frontmatter Parsing
# =============================================================================


def parse_md_frontmatter(md_path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Parse frontmatter from an MD file.

    Args:
        md_path: Path to MD file

    Returns:
        Tuple of (frontmatter_dict, error_message)
    """
    if not md_path.exists():
        return None, f"File not found: {md_path}"

    content = md_path.read_text(encoding="utf-8")

    if not content.startswith("---"):
        return None, "Missing frontmatter (file must start with ---)"

    # Find end of frontmatter
    end_match = re.search(r"\n---\n", content[3:])
    if not end_match:
        return None, "Malformed frontmatter (missing closing ---)"

    frontmatter_text = content[4 : end_match.start() + 3]

    try:
        data = yaml.safe_load(frontmatter_text)
        return data or {}, None
    except yaml.YAMLError as e:
        return None, f"YAML parse error: {e}"


def parse_metadata_yaml(yaml_path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Parse a metadata YAML file.

    Args:
        yaml_path: Path to YAML file

    Returns:
        Tuple of (data_dict, error_message)
    """
    if not yaml_path.exists():
        return None, f"File not found: {yaml_path}"

    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        return data or {}, None
    except yaml.YAMLError as e:
        return None, f"YAML parse error: {e}"


# =============================================================================
# MD Frontmatter Validation
# =============================================================================


def validate_md_frontmatter(
    md_path: Path,
    frontmatter: Dict[str, Any],
) -> ValidationResult:
    """
    Validate MD frontmatter structure.

    Checks:
        - Required fields: date
        - Field types: people (list), locations (dict or list), narrated_dates (list)
        - Date format

    Args:
        md_path: Path to MD file
        frontmatter: Parsed frontmatter dict

    Returns:
        ValidationResult with errors/warnings
    """
    result = ValidationResult(file_path=str(md_path))

    # Required: date
    if "date" not in frontmatter:
        result.add_error("Missing required field: date", field="date")
    else:
        entry_date = frontmatter["date"]
        if not isinstance(entry_date, (str, date)):
            result.add_error(f"date must be string or date, got {type(entry_date).__name__}", field="date")

    # Optional: people (list)
    if "people" in frontmatter:
        people = frontmatter["people"]
        if not isinstance(people, list):
            result.add_error(f"people must be list, got {type(people).__name__}", field="people")

    # Optional: locations (dict grouped by city)
    if "locations" in frontmatter:
        locations = frontmatter["locations"]
        if not isinstance(locations, dict):
            result.add_error(
                f"locations must be dict (city: [locations]), got {type(locations).__name__}",
                field="locations",
            )
        else:
            for city, locs in locations.items():
                if not isinstance(locs, list):
                    result.add_error(
                        f"locations[{city}] must be list, got {type(locs).__name__}",
                        field="locations",
                    )

    # Optional: narrated_dates (list)
    if "narrated_dates" in frontmatter:
        dates = frontmatter["narrated_dates"]
        if not isinstance(dates, list):
            result.add_error(
                f"narrated_dates must be list, got {type(dates).__name__}",
                field="narrated_dates",
            )

    return result


# =============================================================================
# Metadata YAML Validation
# =============================================================================


def validate_metadata_yaml(
    yaml_path: Path,
    metadata: Dict[str, Any],
) -> ValidationResult:
    """
    Validate metadata YAML structure.

    Checks:
        - Required fields: date
        - Scene structure: name, description, date required
        - Event structure: name, scenes required
        - Scene names unique within entry
        - Event scenes reference existing scenes
        - Thread structure: name, from, to, content required

    Args:
        yaml_path: Path to YAML file
        metadata: Parsed YAML dict

    Returns:
        ValidationResult with errors/warnings
    """
    result = ValidationResult(file_path=str(yaml_path))

    # Required: date
    if "date" not in metadata:
        result.add_error("Missing required field: date", field="date")

    # Validate scenes
    scene_names: Set[str] = set()
    for i, scene in enumerate(metadata.get("scenes", []) or []):
        if not isinstance(scene, dict):
            result.add_error(f"scenes[{i}] must be dict", field="scenes")
            continue

        # Required scene fields
        scene_name = scene.get("name")
        if not scene_name:
            result.add_error(f"scenes[{i}] missing required field: name", field="scenes")
        else:
            # Check uniqueness
            if scene_name in scene_names:
                result.add_error(f"Duplicate scene name: '{scene_name}'", field="scenes")
            scene_names.add(scene_name)

        if not scene.get("description"):
            result.add_error(
                f"Scene '{scene_name or i}' missing required field: description",
                field="scenes",
            )

        if not scene.get("date"):
            result.add_error(
                f"Scene '{scene_name or i}' missing required field: date",
                field="scenes",
            )

    # Validate events
    for i, event in enumerate(metadata.get("events", []) or []):
        if not isinstance(event, dict):
            result.add_error(f"events[{i}] must be dict", field="events")
            continue

        event_name = event.get("name")
        if not event_name:
            result.add_error(f"events[{i}] missing required field: name", field="events")

        event_scenes = event.get("scenes", [])
        if not event_scenes:
            result.add_error(
                f"Event '{event_name or i}' missing required field: scenes",
                field="events",
            )
        else:
            # Check scene references
            for scene_ref in event_scenes:
                if scene_ref not in scene_names:
                    result.add_error(
                        f"Event '{event_name}' references unknown scene: '{scene_ref}'",
                        field="events",
                    )

    # Validate threads
    for i, thread in enumerate(metadata.get("threads", []) or []):
        if not isinstance(thread, dict):
            result.add_error(f"threads[{i}] must be dict", field="threads")
            continue

        thread_name = thread.get("name")
        if not thread_name:
            result.add_error(f"threads[{i}] missing required field: name", field="threads")

        if not thread.get("from"):
            result.add_error(
                f"Thread '{thread_name or i}' missing required field: from",
                field="threads",
            )

        if not thread.get("to"):
            result.add_error(
                f"Thread '{thread_name or i}' missing required field: to",
                field="threads",
            )

        if not thread.get("content"):
            result.add_error(
                f"Thread '{thread_name or i}' missing required field: content",
                field="threads",
            )

    # Validate people section
    for i, person in enumerate(metadata.get("people", []) or []):
        if not isinstance(person, dict):
            result.add_error(f"people[{i}] must be dict", field="people")
            continue

        name = person.get("name")
        if not name:
            result.add_error(f"people[{i}] missing required field: name", field="people")
            continue

        # Data quality: must have lastname OR disambiguator
        if not person.get("lastname") and not person.get("disambiguator"):
            result.add_error(
                f"Person '{name}' missing both lastname and disambiguator",
                field="people",
            )

    return result


# =============================================================================
# Consistency Validation
# =============================================================================


def validate_consistency(
    md_path: Path,
    yaml_path: Path,
    md_frontmatter: Dict[str, Any],
    metadata: Dict[str, Any],
) -> ValidationResult:
    """
    Validate consistency between MD frontmatter and metadata YAML.

    Checks:
        - MD people ↔ YAML people bidirectional match
        - Scene people ⊆ YAML people
        - Scene locations ⊆ MD locations
        - Thread people ⊆ YAML people
        - Thread locations ⊆ MD locations

    Args:
        md_path: Path to MD file
        yaml_path: Path to YAML file
        md_frontmatter: Parsed MD frontmatter
        metadata: Parsed metadata YAML

    Returns:
        ValidationResult with errors/warnings
    """
    result = ValidationResult(file_path=str(yaml_path))

    # Build people key sets
    md_people = md_frontmatter.get("people", []) or []
    yaml_people = metadata.get("people", []) or []

    md_people_keys = extract_people_keys(md_people)
    yaml_people_keys = extract_people_keys(yaml_people)

    # Check MD people exist in YAML
    for person in md_people:
        person_keys = get_person_keys(person)
        if not (person_keys & yaml_people_keys):
            name = person if isinstance(person, str) else person.get("name", str(person))
            result.add_error(
                f"MD person '{name}' not found in metadata YAML people section",
                file_path=str(md_path),
                field="people",
            )

    # Check YAML people exist in MD
    for person in yaml_people:
        if not isinstance(person, dict):
            continue
        name = person.get("name", "")
        person_keys = get_person_keys(person)
        if not (person_keys & md_people_keys):
            result.add_error(
                f"YAML person '{name}' not found in MD frontmatter people",
                field="people",
            )

    # Build locations set from MD
    md_locations: Set[str] = set()
    locations_data = md_frontmatter.get("locations", {})
    if isinstance(locations_data, dict):
        for city_locs in locations_data.values():
            if isinstance(city_locs, list):
                md_locations.update(normalize_name(loc) for loc in city_locs)
    elif isinstance(locations_data, list):
        md_locations.update(normalize_name(loc) for loc in locations_data)

    # Validate scene subsets
    for scene in metadata.get("scenes", []) or []:
        if not isinstance(scene, dict):
            continue

        scene_name = scene.get("name", "unknown")

        # Scene people must be in YAML people
        for person_name in scene.get("people", []) or []:
            if not person_in_set(str(person_name), yaml_people_keys):
                result.add_error(
                    f"Scene '{scene_name}' person '{person_name}' not in YAML people section",
                    field="scenes",
                )

        # Scene locations must be in MD locations
        for loc_name in scene.get("locations", []) or []:
            if normalize_name(str(loc_name)) not in md_locations:
                result.add_error(
                    f"Scene '{scene_name}' location '{loc_name}' not in MD frontmatter locations",
                    field="scenes",
                )

    # Validate thread subsets
    for thread in metadata.get("threads", []) or []:
        if not isinstance(thread, dict):
            continue

        thread_name = thread.get("name", "unknown")

        # Thread people must be in YAML people
        for person_name in thread.get("people", []) or []:
            if not person_in_set(str(person_name), yaml_people_keys):
                result.add_error(
                    f"Thread '{thread_name}' person '{person_name}' not in YAML people section",
                    field="threads",
                )

        # Thread locations must be in MD locations
        for loc_name in thread.get("locations", []) or []:
            if normalize_name(str(loc_name)) not in md_locations:
                result.add_error(
                    f"Thread '{thread_name}' location '{loc_name}' not in MD frontmatter locations",
                    field="threads",
                )

    return result


# =============================================================================
# Public API
# =============================================================================


def get_entry_paths(entry_date: str) -> Tuple[Path, Path]:
    """
    Get MD and YAML paths for an entry date.

    Args:
        entry_date: Date string (YYYY-MM-DD)

    Returns:
        Tuple of (md_path, yaml_path)
    """
    year = entry_date[:4]
    md_path = MD_DIR / year / f"{entry_date}.md"
    yaml_path = JOURNAL_YAML_DIR / year / f"{entry_date}.yaml"
    return md_path, yaml_path


def validate_entry(entry_date: str) -> ValidationResult:
    """
    Validate a journal entry by date.

    Validates both MD frontmatter and metadata YAML, plus consistency.

    Args:
        entry_date: Date string (YYYY-MM-DD)

    Returns:
        ValidationResult with all issues
    """
    md_path, yaml_path = get_entry_paths(entry_date)
    result = ValidationResult(file_path=str(yaml_path))

    # Parse MD frontmatter
    md_frontmatter, md_error = parse_md_frontmatter(md_path)
    if md_error:
        result.add_error(md_error, file_path=str(md_path))
        md_frontmatter = {}

    # Parse metadata YAML
    metadata, yaml_error = parse_metadata_yaml(yaml_path)
    if yaml_error:
        result.add_error(yaml_error, file_path=str(yaml_path))
        return result  # Can't continue without YAML

    # Validate MD frontmatter
    if md_frontmatter:
        md_result = validate_md_frontmatter(md_path, md_frontmatter)
        result.merge(md_result)

    # Validate metadata YAML
    yaml_result = validate_metadata_yaml(yaml_path, metadata)
    result.merge(yaml_result)

    # Validate consistency
    if md_frontmatter and metadata:
        consistency_result = validate_consistency(
            md_path, yaml_path, md_frontmatter, metadata
        )
        result.merge(consistency_result)

    return result


def validate_file(file_path: Path) -> ValidationResult:
    """
    Validate a single file (auto-detects MD or YAML).

    For MD files: validates frontmatter structure
    For YAML files: validates structure and consistency with paired MD

    Args:
        file_path: Path to file

    Returns:
        ValidationResult with all issues
    """
    file_path = Path(file_path)
    result = ValidationResult(file_path=str(file_path))

    if not file_path.exists():
        result.add_error(f"File not found: {file_path}")
        return result

    # Determine file type and entry date
    suffix = file_path.suffix.lower()
    stem = file_path.stem  # YYYY-MM-DD

    if suffix == ".md":
        # Validate MD frontmatter
        frontmatter, error = parse_md_frontmatter(file_path)
        if error:
            result.add_error(error)
            return result

        md_result = validate_md_frontmatter(file_path, frontmatter)
        result.merge(md_result)

        # Also check consistency if YAML exists
        yaml_path = JOURNAL_YAML_DIR / file_path.parent.name / f"{stem}.yaml"
        if yaml_path.exists():
            metadata, yaml_error = parse_metadata_yaml(yaml_path)
            if not yaml_error and metadata:
                consistency_result = validate_consistency(
                    file_path, yaml_path, frontmatter, metadata
                )
                result.merge(consistency_result)

    elif suffix in (".yaml", ".yml"):
        # Validate YAML structure
        metadata, error = parse_metadata_yaml(file_path)
        if error:
            result.add_error(error)
            return result

        yaml_result = validate_metadata_yaml(file_path, metadata)
        result.merge(yaml_result)

        # Check consistency with MD
        md_path = MD_DIR / file_path.parent.name / f"{stem}.md"
        if md_path.exists():
            frontmatter, md_error = parse_md_frontmatter(md_path)
            if not md_error and frontmatter:
                consistency_result = validate_consistency(
                    md_path, file_path, frontmatter, metadata
                )
                result.merge(consistency_result)
        else:
            result.add_warning(f"No MD file found at {md_path}")

    else:
        result.add_error(f"Unsupported file type: {suffix}")

    return result


def validate_directory(
    directory: Path,
    pattern: str = "*.yaml",
) -> Dict[str, ValidationResult]:
    """
    Validate all files in a directory.

    Args:
        directory: Directory to validate
        pattern: Glob pattern for files

    Returns:
        Dict mapping file paths to their ValidationResult
    """
    results: Dict[str, ValidationResult] = {}

    for file_path in sorted(directory.glob(pattern)):
        results[str(file_path)] = validate_file(file_path)

    return results
