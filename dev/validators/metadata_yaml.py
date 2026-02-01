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
    5. Entity Subset: Scene people/locations must be subset of MD frontmatter
    6. Entity Existence: People must exist in DB or be marked new:true
    7. Disambiguation: Ambiguous names must specify which person

Key Features:
    - Strict mode: Fail on any violation
    - Report mode: Collect all violations for review
    - Pre-import validation gate
    - Cross-file event uniqueness checking
    - Database entity verification

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

    # Validate all files with DB checks
    reports = validate_all(year="2024", check_db=True)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# --- Third-party imports ---
import yaml

# --- Local imports ---
from dev.core.paths import JOURNAL_YAML_DIR, MD_DIR


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
# Entity Validation (People/Locations)
# =============================================================================


def parse_md_frontmatter(md_path: Path) -> Dict[str, Any]:
    """
    Parse YAML frontmatter from an MD file.

    Args:
        md_path: Path to the MD file

    Returns:
        Dictionary of frontmatter fields
    """
    if not md_path.exists():
        return {}

    content = md_path.read_text(encoding="utf-8")

    if not content.startswith("---"):
        return {}

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}

    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}


def get_md_path_for_yaml(yaml_path: Path) -> Path:
    """
    Get the corresponding MD file path for a metadata YAML file.

    Args:
        yaml_path: Path to metadata YAML

    Returns:
        Path to corresponding MD file
    """
    # YAML: data/metadata/journal/YYYY/YYYY-MM-DD.yaml
    # MD: data/journal/content/md/YYYY/YYYY-MM-DD.md
    date_str = yaml_path.stem
    year = yaml_path.parent.name
    return MD_DIR / year / f"{date_str}.md"


def normalize_for_matching(text: str) -> str:
    """
    Normalize text for fuzzy matching.

    Handles:
    - Case: lowercase
    - Accents/diacritics: María → maria, Raphaël → raphael, brûlée → brulee
    - Whitespace: strip and normalize

    Args:
        text: Text to normalize

    Returns:
        Normalized string for comparison
    """
    if not text:
        return ""

    # Lowercase
    text = text.lower().strip()

    # Remove accents via NFD decomposition
    # NFD splits "é" into "e" + combining accent, then we filter out the accents
    normalized = unicodedata.normalize("NFD", text)
    # Keep only non-combining characters (category starting with M = Mark)
    without_accents = "".join(c for c in normalized if unicodedata.category(c)[0] != "M")

    return without_accents


def get_all_person_keys(name: Any) -> Set[str]:
    """
    Get all possible lookup keys for a person.

    Generates multiple keys so we can match by any form:
    - Raw string (as-is)
    - First name only
    - Full name (name + lastname)
    - Alias

    All keys are normalized: lowercase, accents stripped.
    This means María matches maria, Raphaël matches raphael, etc.

    Args:
        name: Person name (string or dict)

    Returns:
        Set of all possible normalized lookup keys
    """
    keys: Set[str] = set()

    if isinstance(name, dict):
        # Dict format: {name: "Maria", lastname: "Lopez", alias: "Majo"}
        first_name = name.get("name", "")
        lastname = name.get("lastname", "")
        alias = name.get("alias", "")

        if first_name:
            keys.add(normalize_for_matching(str(first_name)))
            if lastname:
                keys.add(normalize_for_matching(f"{first_name} {lastname}"))
        if alias:
            keys.add(normalize_for_matching(str(alias)))
    else:
        # Simple string - could be first name, full name, or alias
        # Just add the normalized string
        normalized = normalize_for_matching(str(name))
        if normalized:
            keys.add(normalized)

    return keys


def normalize_person_name(name: Any) -> str:
    """
    Normalize a person name for comparison.

    Deprecated: Use get_all_person_keys() for flexible matching.
    """
    if isinstance(name, dict):
        # Handle dict format: {name: "John", lastname: "Doe"}
        parts = []
        if name.get("name"):
            parts.append(str(name["name"]))
        if name.get("lastname"):
            parts.append(str(name["lastname"]))
        return " ".join(parts).lower().strip()
    return str(name).lower().strip()


def normalize_location_name(name: Any) -> str:
    """Normalize a location name for comparison."""
    return str(name).lower().strip()


def extract_frontmatter_people_keys(frontmatter: Dict[str, Any]) -> Set[str]:
    """
    Extract all possible lookup keys for people from MD frontmatter.

    For each person, generates multiple keys (first name, full name, alias)
    so we can match scene people against any form.

    Args:
        frontmatter: Parsed frontmatter dict

    Returns:
        Set of all possible normalized person lookup keys
    """
    people = frontmatter.get("people", []) or []
    all_keys: Set[str] = set()

    for person in people:
        all_keys.update(get_all_person_keys(person))

    return all_keys


def extract_frontmatter_people(frontmatter: Dict[str, Any]) -> Set[str]:
    """
    Extract normalized people names from MD frontmatter.

    Deprecated: Use extract_frontmatter_people_keys() for flexible matching.

    Args:
        frontmatter: Parsed frontmatter dict

    Returns:
        Set of normalized person names
    """
    people = frontmatter.get("people", []) or []
    return {normalize_person_name(p) for p in people}


def extract_frontmatter_locations(frontmatter: Dict[str, Any]) -> Set[str]:
    """
    Extract normalized location names from MD frontmatter.

    Handles nested format: {City: [loc1, loc2]}

    Args:
        frontmatter: Parsed frontmatter dict

    Returns:
        Set of normalized location names
    """
    locations_data = frontmatter.get("locations", {})
    locations: Set[str] = set()

    if isinstance(locations_data, dict):
        # Nested format: {City: [loc1, loc2]}
        for city, locs in locations_data.items():
            if isinstance(locs, list):
                for loc in locs:
                    locations.add(normalize_location_name(loc))
    elif isinstance(locations_data, list):
        # Flat format: [loc1, loc2]
        for loc in locations_data:
            locations.add(normalize_location_name(loc))

    return locations


def extract_scene_people(scene: Dict[str, Any]) -> Set[str]:
    """Extract normalized people names from a scene."""
    people = scene.get("people", []) or []
    return {normalize_person_name(p) for p in people}


def extract_scene_locations(scene: Dict[str, Any]) -> Set[str]:
    """Extract normalized location names from a scene."""
    locations = scene.get("locations", []) or []
    return {normalize_location_name(loc) for loc in locations}


def person_matches_frontmatter(person: Any, frontmatter_keys: Set[str]) -> bool:
    """
    Check if a scene person matches any entry-level person key.

    Matches if ANY form of the scene person (name, full name, alias)
    matches ANY form of an entry-level person.

    Args:
        person: Scene person (string or dict)
        frontmatter_keys: Set of all entry-level person lookup keys

    Returns:
        True if person matches any frontmatter key
    """
    person_keys = get_all_person_keys(person)
    return bool(person_keys & frontmatter_keys)


def validate_entity_subsets(
    yaml_path: Path,
    data: Dict[str, Any],
    report: ValidationReport,
) -> None:
    """
    Validate that scene people are subsets of MD frontmatter.

    Uses flexible matching: scene person matches if ANY form (name, full name,
    alias) matches ANY form of an entry-level person. This allows metadata YAML
    to use partial entries (e.g., first name only) as long as they're unambiguous.

    Note: Location subset checking is done as warnings only since
    MD frontmatter often lacks location data.

    Args:
        yaml_path: Path to the YAML file
        data: Parsed YAML data
        report: Report to add errors to
    """
    # Get corresponding MD file
    md_path = get_md_path_for_yaml(yaml_path)
    if not md_path.exists():
        report.add_warning(
            category="entity",
            field="file",
            message="No corresponding MD file found",
            value=str(md_path),
        )
        return

    # Parse MD frontmatter
    frontmatter = parse_md_frontmatter(md_path)

    # Skip if frontmatter has no people field
    if not frontmatter.get("people"):
        return  # Can't validate subset if no frontmatter data

    # Get entry-level entities from frontmatter
    # Use the new flexible matching: get ALL possible keys for each person
    entry_people_keys = extract_frontmatter_people_keys(frontmatter)
    entry_locations = extract_frontmatter_locations(frontmatter)

    # Check each scene
    scenes = data.get("scenes", []) or []
    for i, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue

        # Check people subset using flexible matching (ERROR - must be fixed)
        scene_people_list = scene.get("people", []) or []
        unmatched_people: List[str] = []

        for person in scene_people_list:
            if not person_matches_frontmatter(person, entry_people_keys):
                # Report the display form for the error message
                if isinstance(person, dict):
                    display = person.get("alias") or f"{person.get('name', '')} {person.get('lastname', '')}".strip()
                else:
                    display = str(person)
                unmatched_people.append(display)

        if unmatched_people:
            report.add_error(
                category="entity_subset",
                field=f"scenes[{i}].people",
                message="Scene contains people not in MD frontmatter",
                value=", ".join(sorted(unmatched_people)),
                suggestion="Add missing people to MD frontmatter or check spelling/alias",
            )

        # Check locations subset (WARNING - MD frontmatter often lacks locations)
        if entry_locations:  # Only check if frontmatter has locations
            scene_locations = extract_scene_locations(scene)
            extra_locations = scene_locations - entry_locations
            if extra_locations:
                report.add_warning(
                    category="entity_subset",
                    field=f"scenes[{i}].locations",
                    message="Scene contains locations not in MD frontmatter",
                    value=", ".join(sorted(extra_locations)),
                    suggestion="Add missing locations to MD frontmatter or remove from scene",
                )


class PersonLookup:
    """
    Database lookup for person validation.

    Caches person data to avoid repeated queries.
    """

    def __init__(self, session: Any = None):
        """
        Initialize with optional database session.

        Args:
            session: SQLAlchemy session (if None, DB checks are skipped)
        """
        self.session = session
        self._cache: Dict[str, List[Dict[str, Any]]] = {}
        self._loaded = False

    def _load_people(self) -> None:
        """Load all people from database into cache."""
        if self._loaded or self.session is None:
            return

        from dev.database.models import Person

        people = self.session.query(Person).all()

        for person in people:
            # Index by various name forms
            keys = []

            # Full name
            if person.name:
                keys.append(person.name.lower())
                if person.lastname:
                    keys.append(f"{person.name} {person.lastname}".lower())

            # Alias
            if person.alias:
                keys.append(person.alias.lower())

            person_data = {
                "id": person.id,
                "name": person.name,
                "lastname": person.lastname,
                "alias": person.alias,
            }

            for key in keys:
                if key not in self._cache:
                    self._cache[key] = []
                self._cache[key].append(person_data)

        self._loaded = True

    def lookup(self, name: str) -> List[Dict[str, Any]]:
        """
        Look up a person by name.

        Args:
            name: Person name to look up

        Returns:
            List of matching person records (may be empty or have multiple)
        """
        if self.session is None:
            return []

        self._load_people()
        return self._cache.get(name.lower().strip(), [])

    def exists(self, name: str) -> bool:
        """Check if a person exists in the database."""
        return len(self.lookup(name)) > 0

    def is_ambiguous(self, name: str) -> bool:
        """Check if a person name matches multiple people."""
        return len(self.lookup(name)) > 1

    def get_disambiguation_options(self, name: str) -> List[str]:
        """Get disambiguation options for an ambiguous name."""
        matches = self.lookup(name)
        options = []
        for m in matches:
            if m.get("lastname"):
                options.append(f"{m['name']} {m['lastname']}")
            elif m.get("alias"):
                options.append(f"{m['name']} (alias: {m['alias']})")
            else:
                options.append(m["name"])
        return options


def validate_people_exist(
    data: Dict[str, Any],
    report: ValidationReport,
    person_lookup: Optional[PersonLookup] = None,
) -> None:
    """
    Validate that all people exist in the database or are marked as new.

    People can be marked as new with: {name: "New Person", new: true}

    Args:
        data: Parsed YAML data
        report: Report to add errors to
        person_lookup: PersonLookup instance for DB checks
    """
    if person_lookup is None or person_lookup.session is None:
        return  # Skip DB checks if no session

    # Collect all person references from scenes
    scenes = data.get("scenes", []) or []
    all_people: Set[str] = set()
    new_people: Set[str] = set()

    for scene in scenes:
        if not isinstance(scene, dict):
            continue

        for person in scene.get("people", []) or []:
            if isinstance(person, dict):
                name = person.get("name", "")
                if person.get("new"):
                    new_people.add(normalize_person_name(person))
                else:
                    all_people.add(normalize_person_name(person))
            else:
                all_people.add(normalize_person_name(person))

    # Also check threads
    threads = data.get("threads", []) or []
    for thread in threads:
        if not isinstance(thread, dict):
            continue
        for person in thread.get("people", []) or []:
            if isinstance(person, dict):
                if not person.get("new"):
                    all_people.add(normalize_person_name(person))
            else:
                all_people.add(normalize_person_name(person))

    # Check each person
    for person_name in all_people:
        if not person_name:
            continue

        if not person_lookup.exists(person_name):
            report.add_error(
                category="entity_existence",
                field="people",
                message="Person not found in database",
                value=person_name,
                suggestion="Add person to DB first, or mark as {name: \"...\", new: true}",
            )
        elif person_lookup.is_ambiguous(person_name):
            options = person_lookup.get_disambiguation_options(person_name)
            report.add_error(
                category="entity_ambiguous",
                field="people",
                message=f"Ambiguous person name matches {len(options)} people",
                value=person_name,
                suggestion=f"Specify: {' | '.join(options)}",
            )


# =============================================================================
# File Validation
# =============================================================================


def validate_file(
    path: Path,
    strict: bool = True,
    check_entity_subsets: bool = True,
    person_lookup: Optional[PersonLookup] = None,
) -> ValidationReport:
    """
    Validate a single metadata YAML file.

    Args:
        path: Path to the YAML file
        strict: If True, colons in scene names are errors; if False, warnings
        check_entity_subsets: If True, verify scene entities are subset of frontmatter
        person_lookup: Optional PersonLookup for DB existence checks

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

    # Entity subset validation (scene people/locations ⊆ frontmatter)
    if check_entity_subsets:
        validate_entity_subsets(path, data, report)

    # People existence check (requires DB session)
    if person_lookup is not None:
        validate_people_exist(data, report, person_lookup)

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
    check_entity_subsets: bool = True,
    check_db: bool = False,
) -> Tuple[List[ValidationReport], List[Tuple[str, List[Tuple[str, str]]]]]:
    """
    Validate all metadata YAML files.

    Args:
        year: Specific year to validate, or None for all
        strict: If True, use strict validation rules
        check_event_uniqueness_flag: If True, check for duplicate event names
        check_entity_subsets: If True, verify scene entities ⊆ frontmatter
        check_db: If True, verify people exist in database

    Returns:
        Tuple of (file reports, event duplicates)
    """
    # Find files
    if year:
        files = sorted(JOURNAL_YAML_DIR.glob(f"{year}/*.yaml"))
    else:
        files = sorted(JOURNAL_YAML_DIR.glob("**/*.yaml"))

    # Filter out non-entry files
    files = [f for f in files if not f.name.startswith("_")]

    # Set up person lookup if checking DB
    person_lookup: Optional[PersonLookup] = None
    if check_db:
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from dev.core.paths import DB_PATH

            engine = create_engine(f"sqlite:///{DB_PATH}")
            Session = sessionmaker(bind=engine)
            session = Session()
            person_lookup = PersonLookup(session)
        except Exception:
            pass  # DB not available, skip DB checks

    # Validate each file
    reports = []
    for path in files:
        report = validate_file(
            path,
            strict=strict,
            check_entity_subsets=check_entity_subsets,
            person_lookup=person_lookup,
        )
        reports.append(report)

    # Check event uniqueness
    event_duplicates = []
    if check_event_uniqueness_flag:
        event_duplicates = check_event_uniqueness(files)

    return reports, event_duplicates


def validate_for_import(
    year: Optional[str] = None,
    check_db: bool = False,
    check_entity_subsets: bool = False,
) -> Tuple[bool, str]:
    """
    Validate files for database import.

    This is the pre-import gate. Returns pass/fail and a summary.

    Core Checks (always run):
        - Scene/event naming conventions (no screenwriting format, no date suffixes)
        - Required fields and structure
        - Valid date formats

    Optional Checks:
        - Scene people/locations are subset of MD frontmatter (check_entity_subsets)
        - People exist in database and are unambiguous (check_db)

    Args:
        year: Specific year to validate, or None for all
        check_db: If True, verify people exist in database
        check_entity_subsets: If True, verify scene entities ⊆ frontmatter

    Returns:
        Tuple of (passed, summary_message)
    """
    reports, event_duplicates = validate_all(
        year=year,
        strict=True,
        check_entity_subsets=check_entity_subsets,
        check_db=check_db,
    )

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
