#!/usr/bin/env python3
"""
frontmatter.py
--------------
YAML frontmatter validation for Palimpsest journal entries.

Comprehensive validation of YAML frontmatter structure and content.
This is NOT semantic validation (checking if people/entries exist),
but STRUCTURAL validation (checking if the parser can handle it).

Based on comprehensive parsing specification derived from:
- dev/dataclasses/md_entry.py (all _parse_* methods)
- dev/utils/parsers.py (parsing utilities)
- docs/reference/metadata-field-reference.md

Validates:
- YAML syntax and basic structure
- Required fields (date)
- Field types (string, list, dict)
- Field structure compatibility (list vs dict vs string)
- Cross-field dependencies (city-locations)
- Nested structure formats (dates with people/locations)
- Special character usage (@, #, ~, -, ())
- Required subfields in complex structures
- Enum value compatibility (manuscript status, reference modes/types)
- Unknown fields (warnings)

Usage:
    validate frontmatter [FILE]
    validate frontmatter --help
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- Local imports ---
from dev.utils.md import split_frontmatter
from dev.core.logging_manager import PalimpsestLogger
from dev.validators.schema import SchemaValidator


@dataclass
class FrontmatterIssue:
    """Represents a frontmatter validation issue."""

    file_path: Path
    field_name: str
    severity: str  # error, warning
    message: str
    suggestion: Optional[str] = None
    yaml_value: Optional[Any] = None


@dataclass
class FrontmatterValidationReport:
    """Complete frontmatter validation report."""

    files_checked: int = 0
    files_with_errors: int = 0
    files_with_warnings: int = 0
    total_errors: int = 0
    total_warnings: int = 0
    issues: List[FrontmatterIssue] = field(default_factory=list)

    def add_issue(self, issue: FrontmatterIssue) -> None:
        """Add an issue to the report."""
        self.issues.append(issue)
        if issue.severity == "error":
            self.total_errors += 1
        elif issue.severity == "warning":
            self.total_warnings += 1

    @property
    def has_errors(self) -> bool:
        """Check if any errors were found."""
        return self.total_errors > 0

    @property
    def has_warnings(self) -> bool:
        """Check if any warnings were found."""
        return self.total_warnings > 0

    @property
    def is_healthy(self) -> bool:
        """Check if all files are healthy (no errors)."""
        return not self.has_errors


class FrontmatterValidator:
    """Validates YAML frontmatter structure comprehensively."""

    # Schema validator for enum and type checking
    schema_validator = SchemaValidator()

    # Note: Enum values are now imported from schema validator
    # which gets them from the authoritative source (models/enums.py).
    # No more hardcoded enum lists!

    def __init__(
        self,
        md_dir: Path,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize frontmatter validator.

        Args:
            md_dir: Directory containing markdown files
            logger: Optional logger instance
        """
        self.md_dir = md_dir
        self.logger = logger

    # --- Helper Methods ---

    def _require_type(
        self,
        file_path: Path,
        field_name: str,
        value: Any,
        expected_type: type,
        suggestion: str,
    ) -> Optional[FrontmatterIssue]:
        """
        Create type validation error if value doesn't match expected type.

        Args:
            file_path: File being validated
            field_name: Name of the field
            value: Actual value
            expected_type: Expected Python type
            suggestion: User-friendly suggestion

        Returns:
            FrontmatterIssue if type mismatch, None otherwise
        """
        if not isinstance(value, expected_type):
            return FrontmatterIssue(
                file_path=file_path,
                field_name=field_name,
                severity="error",
                message=f"{field_name.capitalize()} field must be a {expected_type.__name__}",
                suggestion=suggestion,
                yaml_value=type(value).__name__,
            )
        return None

    def _error(
        self,
        file_path: Path,
        field_name: str,
        message: str,
        suggestion: Optional[str] = None,
        yaml_value: Optional[Any] = None,
    ) -> FrontmatterIssue:
        """
        Create an error-level FrontmatterIssue.

        Args:
            file_path: File being validated
            field_name: Name of the field
            message: Error message
            suggestion: Optional suggestion for fix
            yaml_value: Optional YAML value that caused issue

        Returns:
            FrontmatterIssue with severity="error"
        """
        return FrontmatterIssue(
            file_path=file_path,
            field_name=field_name,
            severity="error",
            message=message,
            suggestion=suggestion,
            yaml_value=yaml_value,
        )

    def _warning(
        self,
        file_path: Path,
        field_name: str,
        message: str,
        suggestion: Optional[str] = None,
        yaml_value: Optional[Any] = None,
    ) -> FrontmatterIssue:
        """
        Create a warning-level FrontmatterIssue.

        Args:
            file_path: File being validated
            field_name: Name of the field
            message: Warning message
            suggestion: Optional suggestion for fix
            yaml_value: Optional YAML value that caused issue

        Returns:
            FrontmatterIssue with severity="warning"
        """
        return FrontmatterIssue(
            file_path=file_path,
            field_name=field_name,
            severity="warning",
            message=message,
            suggestion=suggestion,
            yaml_value=yaml_value,
        )

    def _check_duplicate_person(
        self,
        file_path: Path,
        idx: int,
        person: Any,
        person_name: Optional[str],
        person_full_name: Optional[str],
        referenced_people: List[tuple],
        people_data: List[Any],
    ) -> Optional[FrontmatterIssue]:
        """
        Check if a person has already been referenced in the people list.

        Args:
            file_path: File being validated
            idx: Current person index
            person: Current person value (string or dict)
            person_name: Normalized person name
            person_full_name: Normalized person full name
            referenced_people: List of previously seen (name, full_name) tuples
            people_data: Full people list for comparison

        Returns:
            FrontmatterIssue if duplicate found, None otherwise
        """
        if not (person_name or person_full_name):
            return None

        # Check if this person was already referenced
        for prev_idx, prev_person_id in enumerate(referenced_people):
            prev_name, prev_full_name = prev_person_id

            # Check for match on either name or full_name
            match = False
            if person_name and prev_name and person_name.lower() == prev_name.lower():
                match = True
            if person_full_name and prev_full_name and person_full_name.lower() == prev_full_name.lower():
                match = True
            # Also check if one's name matches the other's full_name
            if person_name and prev_full_name and person_name.lower() == prev_full_name.lower():
                match = True
            if person_full_name and prev_name and person_full_name.lower() == prev_name.lower():
                match = True

            if match:
                person_display = person_full_name or person_name
                prev_person_value = people_data[prev_idx]

                # Determine if both are aliases (starting with @)
                current_is_alias = isinstance(person, str) and person.strip().startswith("@")
                prev_is_alias = isinstance(prev_person_value, str) and str(prev_person_value).strip().startswith("@")

                if current_is_alias and prev_is_alias:
                    # Both are aliases for the same person
                    return self._error(
                        file_path, f"people[{idx}]",
                        f"Multiple aliases for '{person_display}': people[{prev_idx}] and people[{idx}]",
                        f"Combine into single entry: {{name: {person_display}, alias: [Alias1, Alias2]}}",
                        str(person)
                    )
                else:
                    # Same person referenced multiple times
                    return self._warning(
                        file_path, f"people[{idx}]",
                        f"Person '{person_display}' appears multiple times in people field",
                        "For multiple nicknames, use: {name: Person, alias: [Nick1, Nick2]}",
                        str(person)
                    )

        return None

    def validate_people_field(
        self, file_path: Path, people_data: Any
    ) -> List[FrontmatterIssue]:
        """
        Validate people field structure.

        Based on: md_entry.py:_parse_people_field()

        Valid formats:
        - Simple name: "John"
        - Full name: "Jane Smith"
        - Hyphenated: "María-José" (hyphen → space)
        - With expansion: "Bob (Robert Johnson)"
        - Alias: "@Johnny"
        - Alias with name: "@Johnny (John)"
        - Dict: {"name": "John", "full_name": "John Smith"}
        - Dict with alias: {"alias": "Johnny", "name": "John"}
        """
        issues = []

        # Type check using helper
        type_error = self._require_type(
            file_path, "people", people_data, list,
            "Use: people: [name1, name2] or people:\n  - name1\n  - name2"
        )
        if type_error:
            return [type_error]

        # Track referenced people to detect duplicates
        referenced_people = []  # List of (name, full_name) tuples for comparison

        for idx, person in enumerate(people_data):
            # Track the person being referenced for duplicate detection
            person_name = None
            person_full_name = None

            if isinstance(person, str):
                # Extract name and full_name from string format
                if "(" in person and person.endswith(")"):
                    # Format: "Name (Full Name)" or "@Alias (Name)"
                    parts = person.split("(", 1)
                    prefix = parts[0].strip()
                    expansion = parts[1].rstrip(")").strip()

                    if prefix.startswith("@"):
                        # Alias format: @Alias (Name)
                        # The expansion is the person being referenced
                        if " " in expansion:
                            person_full_name = expansion.replace("-", " ")
                        else:
                            person_name = expansion.replace("-", " ")
                    else:
                        # Name expansion format: Name (Full Name)
                        if " " in prefix:
                            person_full_name = prefix.replace("-", " ")
                        else:
                            person_name = prefix.replace("-", " ")
                        # Full name is in expansion
                        if " " in expansion:
                            person_full_name = expansion.replace("-", " ")
                else:
                    # Simple name or alias without expansion
                    name_str = person.lstrip("@").replace("-", " ")
                    if " " in name_str:
                        person_full_name = name_str
                    else:
                        person_name = name_str

                # Check for unbalanced parentheses
                if ")" in person and "(" not in person:
                    issues.append(self._error(
                        file_path, f"people[{idx}]",
                        f"Unbalanced parenthesis in: '{person}'",
                        "Check parentheses pairing",
                        person
                    ))

                # Check for parentheses format
                if "(" in person:
                    if not person.endswith(")"):
                        issues.append(self._error(
                            file_path, f"people[{idx}]",
                            f"Malformed parentheses in: '{person}'",
                            "Use format: Name (Full Name) or @Alias (Name)",
                            person
                        ))
                    # Check for space before parenthesis
                    # Allow @Alias (Name) but catch @Alias(Name) and Name(Full Name)
                    elif not re.search(r'\s+\(', person):
                        issues.append(self._warning(
                            file_path, f"people[{idx}]",
                            f"Missing space before parenthesis in: '{person}'",
                            "Use format: Name (Full Name) not Name(Full Name)",
                            person
                        ))

                # Check for alias format
                if person.startswith("@"):
                    # Alias should have format @Alias or @Alias (Name)
                    if "(" not in person:
                        # Just @Alias is valid but limited
                        pass
                    elif not person.endswith(")"):
                        issues.append(self._error(
                            file_path, f"people[{idx}]",
                            f"Malformed alias format: '{person}'",
                            "Use format: @Alias (Name) or @Alias (Full Name)",
                            person
                        ))

            elif isinstance(person, dict):
                # Extract name and full_name from dict format
                person_name = person.get("name")
                person_full_name = person.get("full_name")

                # Normalize hyphens to spaces
                if person_name:
                    person_name = person_name.replace("-", " ")
                if person_full_name:
                    person_full_name = person_full_name.replace("-", " ")

                # Check dict has at least one required field
                if not any(key in person for key in ["name", "full_name", "alias"]):
                    issues.append(self._error(
                        file_path, f"people[{idx}]",
                        "Person dict missing required field (name, full_name, or alias)",
                        "Add at least one of: name, full_name, or alias",
                        str(person)
                    ))

                # Check for unknown fields
                known_fields = {"name", "full_name", "alias"}
                unknown = set(person.keys()) - known_fields
                if unknown:
                    issues.append(self._warning(
                        file_path, f"people[{idx}]",
                        f"Unknown fields in person dict: {', '.join(unknown)}",
                        "Valid fields: name, full_name, alias"
                    ))
            else:
                issues.append(self._error(
                    file_path, f"people[{idx}]",
                    f"Invalid people entry type: {type(person).__name__}",
                    "Use string or dict format",
                    str(person)
                ))

            # Check for duplicate person references
            duplicate_issue = self._check_duplicate_person(
                file_path, idx, person, person_name, person_full_name,
                referenced_people, people_data
            )
            if duplicate_issue:
                issues.append(duplicate_issue)

            # Track this person for future duplicate checks
            if person_name or person_full_name:
                referenced_people.append((person_name, person_full_name))

        return issues

    def validate_locations_field(
        self, file_path: Path, locations_data: Any, city_data: Any
    ) -> List[FrontmatterIssue]:
        """
        Validate locations field structure and city dependency.

        Based on: md_entry.py:_parse_locations_field()

        CRITICAL RULE: Flat list requires exactly 1 city
        """
        issues = []

        if locations_data is None:
            return issues

        # Parse city count
        city_count = 0
        if isinstance(city_data, str):
            city_count = 1
        elif isinstance(city_data, list):
            city_count = len([c for c in city_data if c])

        # Check locations format
        if isinstance(locations_data, list):
            # Flat list format
            if city_count == 0:
                issues.append(self._error(
                    file_path, "locations",
                    "Flat locations list requires city field",
                    "Add: city: CityName"
                ))
            elif city_count > 1:
                issues.append(self._error(
                    file_path, "locations",
                    f"Flat locations list with {city_count} cities (ambiguous)",
                    "Use nested dict:\nlocations:\n  City1:\n    - Location1\n  City2:\n    - Location2",
                    f"cities: {city_data}"
                ))

        elif isinstance(locations_data, dict):
            # Nested dict format
            city_list = city_data if isinstance(city_data, list) else [city_data] if city_data else []

            # Check if dict keys match cities
            for city_key in locations_data.keys():
                if city_list and city_key not in city_list:
                    issues.append(self._warning(
                        file_path, "locations",
                        f"Location city '{city_key}' not in city list: {city_list}",
                        f"Add '{city_key}' to city field or check for typos"
                    ))

            # Check dict values are lists or strings
            for city_key, city_locs in locations_data.items():
                if not isinstance(city_locs, (list, str)):
                    issues.append(self._error(
                        file_path, f"locations.{city_key}",
                        f"Invalid locations type for {city_key}: {type(city_locs).__name__}",
                        "Use list or string for location names"
                    ))

        else:
            issues.append(self._error(
                file_path, "locations",
                f"Invalid locations type: {type(locations_data).__name__}",
                "Use list (single city) or dict (multiple cities)"
            ))

        return issues

    def validate_dates_field(
        self, file_path: Path, dates_data: Any, people_data: Optional[List[Any]] = None
    ) -> List[FrontmatterIssue]:
        """
        Validate dates field structure.

        Based on: md_entry.py:_parse_dates_field()

        Formats:
        - Simple: "2024-01-15" (moment, default)
        - With context: "2024-01-15 (context)"
        - With refs: "2024-01-15 (meeting with @John at #Café)"
        - Reference prefix: "~2024-01-15 (negatives from anti-date)"
        - Dict: {date: "2024-01-15", context: "...", people: [...], locations: [...]}
        - Dict reference: {date: "2024-01-15", type: "reference", ...}
        - Opt-out: "~" alone (excludes entry date)
        - Entry date shorthand: "."

        The type field distinguishes between:
        - "moment" (default): An event that actually happened on the referenced date
        - "reference": A contextual link where action happens on entry date

        Also validates that referenced people exist in the main people list (if provided).
        """
        issues = []

        # Type check using helper
        type_error = self._require_type(
            file_path, "dates", dates_data, list,
            "Use: dates: [date1, date2]"
        )
        if type_error:
            return [type_error]

        # ISO date pattern
        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}')

        # Prepare main people list for semantic validation
        main_people = []
        if people_data:
            for person in people_data:
                if isinstance(person, str):
                    # Extract name/alias from string format
                    if '(' in person and person.endswith(')'):
                        before_paren, in_paren = person.split('(', 1)
                        before_paren = before_paren.strip().lstrip('@')
                        in_paren = in_paren.rstrip(')').strip()
                        if before_paren:
                            main_people.append(before_paren.replace('_', ' ').replace('-', ' ').lower())
                        if in_paren:
                            main_people.append(in_paren.replace('_', ' ').replace('-', ' ').lower())
                    else:
                        name = person.strip().lstrip('@')
                        if name:
                            main_people.append(name.replace('_', ' ').replace('-', ' ').lower())
                elif isinstance(person, dict):
                    if "name" in person:
                        main_people.append(person["name"].replace('-', ' ').lower())
                    if "full_name" in person:
                        main_people.append(person["full_name"].replace('-', ' ').lower())
                    if "alias" in person:
                        # Alias can be string or list
                        aliases = person["alias"]
                        if isinstance(aliases, str):
                            aliases = [aliases]
                        for alias in aliases:
                            main_people.append(alias.replace('-', ' ').lower())

        from datetime import date as dt_date

        for idx, date_entry in enumerate(dates_data):
            # Handle datetime.date objects (YAML loader might produce these)
            if isinstance(date_entry, dt_date):
                continue

            if isinstance(date_entry, str):
                # Check for reference prefix (~) at start of date string
                work_entry = date_entry
                if date_entry.startswith("~"):
                    # Could be opt-out marker "~" alone or reference "~2024-01-15 (...)"
                    if date_entry.strip() == "~":
                        continue  # Opt-out marker
                    # It's a reference - strip the ~ for date validation
                    work_entry = date_entry[1:].lstrip()

                # Parse context out first
                date_part = work_entry.split("(")[0].strip()

                # Check for entry date shorthand
                if date_part == ".":
                    continue

                # Check for date format
                if not date_pattern.match(date_part):
                    issues.append(self._error(
                        file_path, f"dates[{idx}]",
                        f"Invalid date format: '{date_entry}'",
                        "Use YYYY-MM-DD format, optionally with (context). Use ~ prefix for references.",
                        date_entry
                    ))

                # Check parentheses balance
                if "(" in work_entry:
                    if not work_entry.rstrip().endswith(")"):
                        issues.append(self._error(
                            file_path, f"dates[{idx}]",
                            f"Unclosed parenthesis in: '{date_entry}'",
                            "Use format: YYYY-MM-DD (context) or ~YYYY-MM-DD (context)"
                        ))

            elif isinstance(date_entry, dict):
                # Dict format requires 'date' key
                if "date" not in date_entry:
                    issues.append(self._error(
                        file_path, f"dates[{idx}]",
                        "Date dict missing required 'date' key",
                        "Add: date: YYYY-MM-DD",
                        str(date_entry)
                    ))
                else:
                    # Validate date value
                    date_val = date_entry["date"]
                    if isinstance(date_val, dt_date):
                        pass # Valid
                    else:
                        date_val_str = str(date_val).strip()
                        if date_val_str not in ("~", ".") and not date_pattern.match(date_val_str):
                            issues.append(self._error(
                                file_path, f"dates[{idx}].date",
                                f"Invalid date value: '{date_val}'",
                                "Use YYYY-MM-DD format"
                            ))

                # Validate type field if present
                if "type" in date_entry:
                    type_val = date_entry["type"]
                    if type_val not in ("moment", "reference"):
                        issues.append(self._error(
                            file_path, f"dates[{idx}].type",
                            f"Invalid moment type: '{type_val}'",
                            "Use: type: moment or type: reference",
                            type_val
                        ))

                # Check valid subfields
                valid_keys = {"date", "type", "context", "people", "locations", "events", "description"}
                unknown = set(date_entry.keys()) - valid_keys
                if unknown:
                    issues.append(self._warning(
                        file_path, f"dates[{idx}]",
                        f"Unknown fields in date dict: {', '.join(unknown)}",
                        "Valid fields: date, type, context, people, locations, events"
                    ))

                # Check types of subfields
                people_in_date = []
                if "people" in date_entry:
                    p_field = date_entry["people"]
                    if not isinstance(p_field, (list, str)):
                        issues.append(self._warning(
                            file_path, f"dates[{idx}].people",
                            "Date people should be a list or string",
                            "Use: people: [name1, name2]"
                        ))
                    else:
                        if isinstance(p_field, list):
                            people_in_date.extend(p_field)
                        else:
                            people_in_date.append(p_field)

                if "locations" in date_entry and not isinstance(date_entry["locations"], (list, str)):
                    issues.append(self._warning(
                        file_path, f"dates[{idx}].locations",
                        "Date locations should be a list or string",
                        "Use: locations: [loc1, loc2]"
                    ))

                if "events" in date_entry and not isinstance(date_entry["events"], (list, str)):
                    issues.append(self._warning(
                        file_path, f"dates[{idx}].events",
                        "Date events should be a list or string",
                        "Use: events: [event1, event2]"
                    ))

                # Validate people existence if main people list is available
                if main_people and people_in_date:
                    for person_ref in people_in_date:
                        if isinstance(person_ref, str):
                            # Extract name part (handle @Alias format)
                            check_name = person_ref.split('(')[0].strip().lstrip('@')
                            # Normalize
                            check_name = check_name.replace('_', ' ').replace('-', ' ').lower()

                            if check_name:
                                # Try exact match
                                found = check_name in main_people
                                
                                # Try first word match (e.g. "Daniel" matching "Daniel Andrews")
                                if not found:
                                    for main_person in main_people:
                                        first_word = main_person.split()[0] if ' ' in main_person else main_person
                                        if first_word == check_name:
                                            found = True
                                            break
                                
                                if not found:
                                    issues.append(self._error(
                                        file_path, f"dates[{idx}].people",
                                        f"Person '{person_ref}' not found in main 'people' field",
                                        f"Add '{person_ref}' to the main 'people' field at the top of the frontmatter"
                                    ))

            else:
                issues.append(self._error(
                    file_path, f"dates[{idx}]",
                    f"Invalid date entry type: {type(date_entry).__name__}",
                    "Use string (YYYY-MM-DD) or dict format"
                ))

        return issues

    def validate_references_field(
        self, file_path: Path, references_data: Any
    ) -> List[FrontmatterIssue]:
        """
        Validate references field structure.

        Based on: md_entry.py:_parse_references_field()

        Required: At least one of 'content' or 'description'
        Optional: mode, speaker, source
        If source: requires title and type
        """
        issues = []

        # Type check using helper
        type_error = self._require_type(
            file_path, "references", references_data, list,
            "Use: references:\n  - content: \"...\""
        )
        if type_error:
            return [type_error]

        for idx, ref in enumerate(references_data):
            if not isinstance(ref, dict):
                issues.append(self._error(
                    file_path, f"references[{idx}]",
                    f"Reference must be a dict, got {type(ref).__name__}",
                    "Use dict format with content/description"
                ))
                continue

            # Check for content or description
            if "content" not in ref and "description" not in ref:
                issues.append(self._error(
                    file_path, f"references[{idx}]",
                    "Reference missing both 'content' and 'description'",
                    "Add at least one: content or description",
                    str(ref)
                ))

            # Check mode enum using schema validator
            if "mode" in ref:
                mode_issue = self.schema_validator.validate_reference_mode(
                    ref["mode"], f"references[{idx}].mode"
                )
                if mode_issue:
                    issues.append(self._error(
                        file_path, mode_issue.field_path,
                        mode_issue.message,
                        mode_issue.suggestion,
                        mode_issue.actual_value
                    ) if mode_issue.severity == "error" else self._warning(
                        file_path, mode_issue.field_path,
                        mode_issue.message,
                        mode_issue.suggestion,
                        mode_issue.actual_value
                    ))

            # Check source structure
            if "source" in ref:
                if not isinstance(ref["source"], dict):
                    issues.append(self._error(
                        file_path, f"references[{idx}].source",
                        "Reference source must be a dict",
                        "Use: source:\n  title: \"...\"\n  type: book"
                    ))
                else:
                    source = ref["source"]

                    # Check required fields
                    if "title" not in source:
                        issues.append(self._error(
                            file_path, f"references[{idx}].source",
                            "Reference source missing 'title'",
                            "Add: title: \"Source Title\""
                        ))

                    if "type" not in source:
                        issues.append(self._error(
                            file_path, f"references[{idx}].source",
                            "Reference source missing 'type'",
                            f"Add: type: {self.schema_validator.get_valid_reference_types()[0]}"
                        ))
                    else:
                        # Validate type using schema validator
                        type_issue = self.schema_validator.validate_reference_type(
                            source["type"], f"references[{idx}].source.type"
                        )
                        if type_issue:
                            issues.append(self._error(
                                file_path, type_issue.field_path,
                                type_issue.message,
                                type_issue.suggestion,
                                type_issue.actual_value
                            ) if type_issue.severity == "error" else self._warning(
                                file_path, type_issue.field_path,
                                type_issue.message,
                                type_issue.suggestion,
                                type_issue.actual_value
                            ))

        return issues

    def validate_poems_field(
        self, file_path: Path, poems_data: Any
    ) -> List[FrontmatterIssue]:
        """
        Validate poems field structure.

        Based on: md_entry.py:_parse_poems_field()

        Required: title, content
        Optional: revision_date, notes
        """
        issues = []

        # Type check using helper
        type_error = self._require_type(
            file_path, "poems", poems_data, list,
            "Use: poems:\n  - title: \"...\"\n    content: |"
        )
        if type_error:
            return [type_error]

        # ISO date pattern for revision_date
        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')

        for idx, poem in enumerate(poems_data):
            if not isinstance(poem, dict):
                issues.append(self._error(
                    file_path, f"poems[{idx}]",
                    f"Poem must be a dict, got {type(poem).__name__}",
                    "Use dict format with title and content"
                ))
                continue

            # Check required fields
            if "title" not in poem:
                issues.append(self._error(
                    file_path, f"poems[{idx}]",
                    "Poem missing required 'title' field",
                    "Add: title: \"Poem Title\""
                ))

            if "content" not in poem:
                issues.append(self._error(
                    file_path, f"poems[{idx}]",
                    "Poem missing required 'content' field",
                    "Add: content: |\n  Line 1\n  Line 2"
                ))

            # Check revision_date format if present
            if "revision_date" in poem:
                # Handle raw date object
                from datetime import date as dt_date
                if isinstance(poem["revision_date"], dt_date):
                    continue
                    
                if not date_pattern.match(str(poem["revision_date"]).strip()):
                    issues.append(self._warning(
                        file_path, f"poems[{idx}].revision_date",
                        f"Invalid revision_date format: '{poem['revision_date']}'",
                        "Use YYYY-MM-DD format (will default to entry date)",
                        poem["revision_date"]
                    ))

        return issues

    def validate_manuscript_field(
        self, file_path: Path, manuscript_data: Any
    ) -> List[FrontmatterIssue]:
        """
        Validate manuscript field structure.

        Based on: models_manuscript.py and validation constants

        Required: status, edited
        Optional: themes, notes
        """
        issues = []

        # Type check using helper
        type_error = self._require_type(
            file_path, "manuscript", manuscript_data, dict,
            "Use: manuscript:\n  status: draft\n  edited: false"
        )
        if type_error:
            return [type_error]

        # Check status using schema validator
        if "status" in manuscript_data:
            status_issue = self.schema_validator.validate_manuscript_status(
                manuscript_data["status"], "manuscript.status"
            )
            if status_issue:
                issues.append(self._error(
                    file_path, status_issue.field_path,
                    status_issue.message,
                    status_issue.suggestion,
                    status_issue.actual_value
                ) if status_issue.severity == "error" else self._warning(
                    file_path, status_issue.field_path,
                    status_issue.message,
                    status_issue.suggestion,
                    status_issue.actual_value
                ))

        # Check edited field type
        if "edited" in manuscript_data:
            if not isinstance(manuscript_data["edited"], bool):
                issues.append(self._warning(
                    file_path, "manuscript.edited",
                    f"Manuscript edited should be boolean, got {type(manuscript_data['edited']).__name__}",
                    "Use: edited: true or edited: false",
                    manuscript_data["edited"]
                ))

        # Check themes is list
        if "themes" in manuscript_data:
            if not isinstance(manuscript_data["themes"], list):
                issues.append(self._warning(
                    file_path, "manuscript.themes",
                    "Manuscript themes should be a list",
                    "Use: themes:\n  - theme1\n  - theme2"
                ))

        return issues

    def validate_events_field(
        self, file_path: Path, events_data: Any
    ) -> List[FrontmatterIssue]:
        """
        Validate events field structure.

        Events should be a list of strings (event identifiers).
        """
        issues = []

        # Type check
        type_error = self._require_type(
            file_path, "events", events_data, list,
            "Use: events: [event1, event2]"
        )
        if type_error:
            return [type_error]

        # Check each event is a string
        for idx, event in enumerate(events_data):
            if not isinstance(event, str):
                issues.append(self._warning(
                    file_path, f"events[{idx}]",
                    f"Event should be a string, got {type(event).__name__}",
                    "Use: events: [event-name, another-event]",
                    str(event)
                ))
            elif not event.strip():
                issues.append(self._warning(
                    file_path, f"events[{idx}]",
                    "Event name is empty",
                    "Remove empty events or add a valid name"
                ))

        return issues

    def validate_tags_field(
        self, file_path: Path, tags_data: Any
    ) -> List[FrontmatterIssue]:
        """
        Validate tags field structure.

        Tags should be a list of strings.
        """
        issues = []

        # Type check
        type_error = self._require_type(
            file_path, "tags", tags_data, list,
            "Use: tags: [tag1, tag2]"
        )
        if type_error:
            return [type_error]

        # Check each tag is a string
        for idx, tag in enumerate(tags_data):
            if not isinstance(tag, str):
                issues.append(self._warning(
                    file_path, f"tags[{idx}]",
                    f"Tag should be a string, got {type(tag).__name__}",
                    "Use: tags: [tag-name, another-tag]",
                    str(tag)
                ))
            elif not tag.strip():
                issues.append(self._warning(
                    file_path, f"tags[{idx}]",
                    "Tag name is empty",
                    "Remove empty tags or add a valid name"
                ))

        return issues

    def validate_related_entries_field(
        self, file_path: Path, related_data: Any
    ) -> List[FrontmatterIssue]:
        """
        Validate related_entries field structure.

        Related entries should be a list of date strings (YYYY-MM-DD).
        """
        issues = []

        # Type check
        type_error = self._require_type(
            file_path, "related_entries", related_data, list,
            "Use: related_entries: [2024-01-15, 2024-02-20]"
        )
        if type_error:
            return [type_error]

        # ISO date pattern
        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')

        from datetime import date as dt_date

        for idx, entry_ref in enumerate(related_data):
            # Handle datetime.date objects
            if isinstance(entry_ref, dt_date):
                continue

            if not isinstance(entry_ref, str):
                issues.append(self._error(
                    file_path, f"related_entries[{idx}]",
                    f"Related entry should be a date string, got {type(entry_ref).__name__}",
                    "Use YYYY-MM-DD format",
                    str(entry_ref)
                ))
            elif not date_pattern.match(entry_ref):
                issues.append(self._error(
                    file_path, f"related_entries[{idx}]",
                    f"Invalid date format: '{entry_ref}'",
                    "Use YYYY-MM-DD format"
                ))

        return issues

    def validate_city_field(
        self, file_path: Path, city_data: Any
    ) -> List[FrontmatterIssue]:
        """
        Validate city field structure.

        City can be a single string or list of strings.
        """
        issues = []

        # Accept string or list
        if isinstance(city_data, str):
            if not city_data.strip():
                issues.append(self._warning(
                    file_path, "city",
                    "City name is empty",
                    "Remove empty city or add a valid name"
                ))
        elif isinstance(city_data, list):
            for idx, city in enumerate(city_data):
                if not isinstance(city, str):
                    issues.append(self._warning(
                        file_path, f"city[{idx}]",
                        f"City should be a string, got {type(city).__name__}",
                        "Use: city: [City1, City2]",
                        str(city)
                    ))
                elif not city.strip():
                    issues.append(self._warning(
                        file_path, f"city[{idx}]",
                        "City name is empty",
                        "Remove empty cities or add valid names"
                    ))
        else:
            issues.append(self._error(
                file_path, "city",
                f"City should be a string or list, got {type(city_data).__name__}",
                "Use: city: Montreal or city: [Montreal, Toronto]"
            ))

        return issues

    def validate_file(self, file_path: Path) -> List[FrontmatterIssue]:
        """
        Validate metadata structure in a single file.

        Args:
            file_path: Path to markdown file

        Returns:
            List of metadata issues found
        """
        issues = []

        # Read and parse file
        try:
            content = file_path.read_text(encoding="utf-8")
            frontmatter_text, _ = split_frontmatter(content)

            if not frontmatter_text:
                return issues  # No frontmatter to validate

            import yaml
            metadata = yaml.safe_load(frontmatter_text)

            if not isinstance(metadata, dict):
                return issues  # Not valid YAML dict

        except Exception:
            return issues  # Let frontmatter validator handle syntax errors

        # Validate each field
        if "city" in metadata:
            issues.extend(self.validate_city_field(file_path, metadata["city"]))

        if "people" in metadata:
            issues.extend(self.validate_people_field(file_path, metadata["people"]))

        if "locations" in metadata:
            city_data = metadata.get("city")
            issues.extend(
                self.validate_locations_field(file_path, metadata["locations"], city_data)
            )

        if "dates" in metadata:
            # Pass people data for semantic validation
            people_data = metadata.get("people")
            issues.extend(self.validate_dates_field(file_path, metadata["dates"], people_data))

        if "references" in metadata:
            issues.extend(self.validate_references_field(file_path, metadata["references"]))

        if "poems" in metadata:
            issues.extend(self.validate_poems_field(file_path, metadata["poems"]))

        if "manuscript" in metadata:
            issues.extend(self.validate_manuscript_field(file_path, metadata["manuscript"]))

        if "events" in metadata:
            issues.extend(self.validate_events_field(file_path, metadata["events"]))

        if "tags" in metadata:
            issues.extend(self.validate_tags_field(file_path, metadata["tags"]))

        if "related_entries" in metadata:
            issues.extend(self.validate_related_entries_field(file_path, metadata["related_entries"]))

        return issues

    def validate_all(self) -> FrontmatterValidationReport:
        """
        Validate all markdown files in directory.

        Returns:
            Complete validation report
        """
        report = FrontmatterValidationReport()
        md_files = list(self.md_dir.glob("**/*.md"))

        for md_file in md_files:
            report.files_checked += 1
            file_issues = self.validate_file(md_file)

            for issue in file_issues:
                report.add_issue(issue)

            if any(i.severity == "error" for i in file_issues):
                report.files_with_errors += 1
            if any(i.severity == "warning" for i in file_issues):
                report.files_with_warnings += 1

        return report


def format_frontmatter_report(report: FrontmatterValidationReport) -> str:
    """
    Format frontmatter validation report as readable text.

    Args:
        report: Validation report to format

    Returns:
        Formatted report string
    """
    lines = []
    lines.append("\n" + "=" * 60)
    lines.append("FRONTMATTER VALIDATION REPORT")
    lines.append("=" * 60)
    lines.append("")

    # Summary
    lines.append(f"Files Checked: {report.files_checked}")
    lines.append(
        f"✅ Clean Files: {report.files_checked - report.files_with_errors - report.files_with_warnings}"
    )
    lines.append(f"⚠️  Files with Warnings: {report.files_with_warnings}")
    lines.append(f"❌ Files with Errors: {report.files_with_errors}")
    lines.append("")
    lines.append(f"Total Warnings: {report.total_warnings}")
    lines.append(f"Total Errors: {report.total_errors}")
    lines.append("")

    # Overall status
    if report.is_healthy:
        lines.append("✅ ALL FRONTMATTER VALID")
    else:
        lines.append("❌ FRONTMATTER VALIDATION FAILED")
    lines.append("")

    # Group issues by file
    if report.issues:
        issues_by_file: Dict[Path, List[FrontmatterIssue]] = {}
        for issue in report.issues:
            if issue.file_path not in issues_by_file:
                issues_by_file[issue.file_path] = []
            issues_by_file[issue.file_path].append(issue)

        lines.append("ISSUES BY FILE:")
        lines.append("")

        for file_path in sorted(issues_by_file.keys()):
            file_issues = issues_by_file[file_path]
            errors = [i for i in file_issues if i.severity == "error"]

            icon = "❌" if errors else "⚠️"
            lines.append(f"{icon} {file_path.name}")

            for issue in file_issues:
                severity_icon = "❌" if issue.severity == "error" else "⚠️"
                lines.append(f"   {severity_icon} [{issue.field_name}] {issue.message}")
                if issue.suggestion:
                    lines.append(f"      💡 {issue.suggestion}")

            lines.append("")

    lines.append("=" * 60)

    return "\n".join(lines)
