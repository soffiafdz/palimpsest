#!/usr/bin/env python3
"""
metadata.py
-----------
Metadata structure validation for Palimpsest journal entries.

Validates that YAML frontmatter structures match parser expectations.
This is NOT semantic validation (checking if people/entries exist),
but STRUCTURAL validation (checking if the parser can handle it).

Based on comprehensive parsing specification derived from:
- dev/dataclasses/md_entry.py (all _parse_* methods)
- dev/utils/parsers.py (parsing utilities)
- docs/metadata-quick-reference.md
- docs/example-yaml.md

Validates:
- Field structure compatibility (list vs dict vs string)
- Cross-field dependencies (city-locations)
- Nested structure formats (dates with people/locations)
- Special character usage (@, #, ~, -, ())
- Required subfields in complex structures
- Enum value compatibility

Usage:
    validate metadata all
    validate metadata people
    validate metadata locations
    validate metadata references
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


@dataclass
class MetadataIssue:
    """Represents a metadata validation issue."""

    file_path: Path
    field_name: str
    severity: str  # error, warning
    message: str
    suggestion: Optional[str] = None
    yaml_value: Optional[Any] = None


@dataclass
class MetadataValidationReport:
    """Complete metadata validation report."""

    files_checked: int = 0
    files_with_errors: int = 0
    files_with_warnings: int = 0
    total_errors: int = 0
    total_warnings: int = 0
    issues: List[MetadataIssue] = field(default_factory=list)

    def add_issue(self, issue: MetadataIssue) -> None:
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


class MetadataValidator:
    """Validates metadata structure for parser compatibility."""

    # Valid manuscript status values (from models_manuscript.py and validation)
    VALID_MANUSCRIPT_STATUS = [
        "unspecified",
        "draft",
        "reviewed",
        "included",
        "excluded",
        "final",
    ]

    # Valid reference modes (from models.py)
    VALID_REFERENCE_MODES = ["direct", "indirect", "paraphrase", "visual"]

    # Valid reference types (from models.py)
    VALID_REFERENCE_TYPES = [
        "book",
        "poem",
        "article",
        "film",
        "song",
        "podcast",
        "interview",
        "speech",
        "tv_show",
        "video",
        "other",
    ]

    def __init__(
        self,
        md_dir: Path,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize metadata validator.

        Args:
            md_dir: Directory containing markdown files
            logger: Optional logger instance
        """
        self.md_dir = md_dir
        self.logger = logger

    def validate_people_field(
        self, file_path: Path, people_data: Any
    ) -> List[MetadataIssue]:
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

        if not isinstance(people_data, list):
            issues.append(
                MetadataIssue(
                    file_path=file_path,
                    field_name="people",
                    severity="error",
                    message="People field must be a list",
                    suggestion="Use: people: [name1, name2] or people:\n  - name1\n  - name2",
                    yaml_value=type(people_data).__name__,
                )
            )
            return issues

        for idx, person in enumerate(people_data):
            if isinstance(person, str):
                # Check for unbalanced parentheses
                if ")" in person and "(" not in person:
                    issues.append(
                        MetadataIssue(
                            file_path=file_path,
                            field_name=f"people[{idx}]",
                            severity="error",
                            message=f"Unbalanced parenthesis in: '{person}'",
                            suggestion="Check parentheses pairing",
                            yaml_value=person,
                        )
                    )

                # Check for parentheses format
                if "(" in person:
                    if not person.endswith(")"):
                        issues.append(
                            MetadataIssue(
                                file_path=file_path,
                                field_name=f"people[{idx}]",
                                severity="error",
                                message=f"Malformed parentheses in: '{person}'",
                                suggestion="Use format: Name (Full Name) or @Alias (Name)",
                                yaml_value=person,
                            )
                        )
                    # Check for space before parenthesis
                    # Allow @Alias (Name) but catch @Alias(Name) and Name(Full Name)
                    elif not re.search(r'\s+\(', person):
                        issues.append(
                            MetadataIssue(
                                file_path=file_path,
                                field_name=f"people[{idx}]",
                                severity="warning",
                                message=f"Missing space before parenthesis in: '{person}'",
                                suggestion="Use format: Name (Full Name) not Name(Full Name)",
                                yaml_value=person,
                            )
                        )

                # Check for alias format
                if person.startswith("@"):
                    # Alias should have format @Alias or @Alias (Name)
                    if "(" not in person:
                        # Just @Alias is valid but limited
                        pass
                    elif not person.endswith(")"):
                        issues.append(
                            MetadataIssue(
                                file_path=file_path,
                                field_name=f"people[{idx}]",
                                severity="error",
                                message=f"Malformed alias format: '{person}'",
                                suggestion="Use format: @Alias (Name) or @Alias (Full Name)",
                                yaml_value=person,
                            )
                        )

            elif isinstance(person, dict):
                # Check dict has at least one required field
                if not any(key in person for key in ["name", "full_name", "alias"]):
                    issues.append(
                        MetadataIssue(
                            file_path=file_path,
                            field_name=f"people[{idx}]",
                            severity="error",
                            message="Person dict missing required field (name, full_name, or alias)",
                            suggestion="Add at least one of: name, full_name, or alias",
                            yaml_value=str(person),
                        )
                    )

                # Check for unknown fields
                known_fields = {"name", "full_name", "alias"}
                unknown = set(person.keys()) - known_fields
                if unknown:
                    issues.append(
                        MetadataIssue(
                            file_path=file_path,
                            field_name=f"people[{idx}]",
                            severity="warning",
                            message=f"Unknown fields in person dict: {', '.join(unknown)}",
                            suggestion="Valid fields: name, full_name, alias",
                        )
                    )
            else:
                issues.append(
                    MetadataIssue(
                        file_path=file_path,
                        field_name=f"people[{idx}]",
                        severity="error",
                        message=f"Invalid people entry type: {type(person).__name__}",
                        suggestion="Use string or dict format",
                        yaml_value=str(person),
                    )
                )

        return issues

    def validate_locations_field(
        self, file_path: Path, locations_data: Any, city_data: Any
    ) -> List[MetadataIssue]:
        """
        Validate locations field structure and city dependency.

        Based on: md_entry.py:_parse_locations_field()

        CRITICAL RULE: Flat list requires exactly 1 city
        """
        issues = []

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
                issues.append(
                    MetadataIssue(
                        file_path=file_path,
                        field_name="locations",
                        severity="error",
                        message="Flat locations list requires city field",
                        suggestion="Add: city: CityName",
                    )
                )
            elif city_count > 1:
                issues.append(
                    MetadataIssue(
                        file_path=file_path,
                        field_name="locations",
                        severity="error",
                        message=f"Flat locations list with {city_count} cities (ambiguous)",
                        suggestion="Use nested dict:\nlocations:\n  City1:\n    - Location1\n  City2:\n    - Location2",
                        yaml_value=f"cities: {city_data}",
                    )
                )

        elif isinstance(locations_data, dict):
            # Nested dict format
            city_list = city_data if isinstance(city_data, list) else [city_data] if city_data else []

            # Check if dict keys match cities
            for city_key in locations_data.keys():
                if city_list and city_key not in city_list:
                    issues.append(
                        MetadataIssue(
                            file_path=file_path,
                            field_name="locations",
                            severity="warning",
                            message=f"Location city '{city_key}' not in city list: {city_list}",
                            suggestion=f"Add '{city_key}' to city field or check for typos",
                        )
                    )

            # Check dict values are lists or strings
            for city_key, city_locs in locations_data.items():
                if not isinstance(city_locs, (list, str)):
                    issues.append(
                        MetadataIssue(
                            file_path=file_path,
                            field_name=f"locations.{city_key}",
                            severity="error",
                            message=f"Invalid locations type for {city_key}: {type(city_locs).__name__}",
                            suggestion="Use list or string for location names",
                        )
                    )

        else:
            issues.append(
                MetadataIssue(
                    file_path=file_path,
                    field_name="locations",
                    severity="error",
                    message=f"Invalid locations type: {type(locations_data).__name__}",
                    suggestion="Use list (single city) or dict (multiple cities)",
                )
            )

        return issues

    def validate_dates_field(
        self, file_path: Path, dates_data: Any
    ) -> List[MetadataIssue]:
        """
        Validate dates field structure.

        Based on: md_entry.py:_parse_dates_field()

        Formats:
        - Simple: "2024-01-15"
        - With context: "2024-01-15 (context)"
        - With refs: "2024-01-15 (meeting with @John at #Café)"
        - Dict: {date: "2024-01-15", context: "...", people: [...], locations: [...]}
        - Opt-out: "~"
        """
        issues = []

        if not isinstance(dates_data, list):
            issues.append(
                MetadataIssue(
                    file_path=file_path,
                    field_name="dates",
                    severity="error",
                    message="Dates field must be a list",
                    suggestion="Use: dates: [date1, date2]",
                )
            )
            return issues

        # ISO date pattern
        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}')

        for idx, date_entry in enumerate(dates_data):
            if isinstance(date_entry, str):
                # Check for opt-out marker
                if date_entry.strip() == "~":
                    continue

                # Check for date format
                if not date_pattern.match(date_entry.strip()):
                    issues.append(
                        MetadataIssue(
                            file_path=file_path,
                            field_name=f"dates[{idx}]",
                            severity="error",
                            message=f"Invalid date format: '{date_entry}'",
                            suggestion="Use YYYY-MM-DD format, optionally with (context)",
                            yaml_value=date_entry,
                        )
                    )

                # Check parentheses balance
                if "(" in date_entry:
                    if not date_entry.rstrip().endswith(")"):
                        issues.append(
                            MetadataIssue(
                                file_path=file_path,
                                field_name=f"dates[{idx}]",
                                severity="error",
                                message=f"Unclosed parenthesis in: '{date_entry}'",
                                suggestion="Use format: YYYY-MM-DD (context)",
                            )
                        )

            elif isinstance(date_entry, dict):
                # Dict format requires 'date' key
                if "date" not in date_entry:
                    issues.append(
                        MetadataIssue(
                            file_path=file_path,
                            field_name=f"dates[{idx}]",
                            severity="error",
                            message="Date dict missing required 'date' key",
                            suggestion="Add: date: YYYY-MM-DD",
                            yaml_value=str(date_entry),
                        )
                    )
                else:
                    # Validate date value
                    if not date_pattern.match(str(date_entry["date"]).strip()):
                        issues.append(
                            MetadataIssue(
                                file_path=file_path,
                                field_name=f"dates[{idx}].date",
                                severity="error",
                                message=f"Invalid date value: '{date_entry['date']}'",
                                suggestion="Use YYYY-MM-DD format",
                            )
                        )

                # Check valid subfields
                valid_keys = {"date", "context", "people", "locations"}
                unknown = set(date_entry.keys()) - valid_keys
                if unknown:
                    issues.append(
                        MetadataIssue(
                            file_path=file_path,
                            field_name=f"dates[{idx}]",
                            severity="warning",
                            message=f"Unknown fields in date dict: {', '.join(unknown)}",
                            suggestion="Valid fields: date, context, people, locations",
                        )
                    )

                # Check types of subfields
                if "people" in date_entry and not isinstance(date_entry["people"], list):
                    issues.append(
                        MetadataIssue(
                            file_path=file_path,
                            field_name=f"dates[{idx}].people",
                            severity="warning",
                            message="Date people should be a list",
                            suggestion="Use: people: [name1, name2]",
                        )
                    )

                if "locations" in date_entry and not isinstance(date_entry["locations"], list):
                    issues.append(
                        MetadataIssue(
                            file_path=file_path,
                            field_name=f"dates[{idx}].locations",
                            severity="warning",
                            message="Date locations should be a list",
                            suggestion="Use: locations: [loc1, loc2]",
                        )
                    )

            else:
                issues.append(
                    MetadataIssue(
                        file_path=file_path,
                        field_name=f"dates[{idx}]",
                        severity="error",
                        message=f"Invalid date entry type: {type(date_entry).__name__}",
                        suggestion="Use string (YYYY-MM-DD) or dict format",
                    )
                )

        return issues

    def validate_references_field(
        self, file_path: Path, references_data: Any
    ) -> List[MetadataIssue]:
        """
        Validate references field structure.

        Based on: md_entry.py:_parse_references_field()

        Required: At least one of 'content' or 'description'
        Optional: mode, speaker, source
        If source: requires title and type
        """
        issues = []

        if not isinstance(references_data, list):
            issues.append(
                MetadataIssue(
                    file_path=file_path,
                    field_name="references",
                    severity="error",
                    message="References field must be a list",
                    suggestion="Use: references:\n  - content: \"...\"",
                )
            )
            return issues

        for idx, ref in enumerate(references_data):
            if not isinstance(ref, dict):
                issues.append(
                    MetadataIssue(
                        file_path=file_path,
                        field_name=f"references[{idx}]",
                        severity="error",
                        message=f"Reference must be a dict, got {type(ref).__name__}",
                        suggestion="Use dict format with content/description",
                    )
                )
                continue

            # Check for content or description
            if "content" not in ref and "description" not in ref:
                issues.append(
                    MetadataIssue(
                        file_path=file_path,
                        field_name=f"references[{idx}]",
                        severity="error",
                        message="Reference missing both 'content' and 'description'",
                        suggestion="Add at least one: content or description",
                        yaml_value=str(ref),
                    )
                )

            # Check mode enum
            if "mode" in ref and ref["mode"] not in self.VALID_REFERENCE_MODES:
                issues.append(
                    MetadataIssue(
                        file_path=file_path,
                        field_name=f"references[{idx}].mode",
                        severity="error",
                        message=f"Invalid reference mode: '{ref['mode']}'",
                        suggestion=f"Valid modes: {', '.join(self.VALID_REFERENCE_MODES)}",
                        yaml_value=ref["mode"],
                    )
                )

            # Check source structure
            if "source" in ref:
                if not isinstance(ref["source"], dict):
                    issues.append(
                        MetadataIssue(
                            file_path=file_path,
                            field_name=f"references[{idx}].source",
                            severity="error",
                            message="Reference source must be a dict",
                            suggestion="Use: source:\n  title: \"...\"\n  type: book",
                        )
                    )
                else:
                    source = ref["source"]

                    # Check required fields
                    if "title" not in source:
                        issues.append(
                            MetadataIssue(
                                file_path=file_path,
                                field_name=f"references[{idx}].source",
                                severity="error",
                                message="Reference source missing 'title'",
                                suggestion="Add: title: \"Source Title\"",
                            )
                        )

                    if "type" not in source:
                        issues.append(
                            MetadataIssue(
                                file_path=file_path,
                                field_name=f"references[{idx}].source",
                                severity="error",
                                message="Reference source missing 'type'",
                                suggestion=f"Add: type: {self.VALID_REFERENCE_TYPES[0]}",
                            )
                        )
                    elif source["type"] not in self.VALID_REFERENCE_TYPES:
                        issues.append(
                            MetadataIssue(
                                file_path=file_path,
                                field_name=f"references[{idx}].source.type",
                                severity="error",
                                message=f"Invalid source type: '{source['type']}'",
                                suggestion=f"Valid types: {', '.join(self.VALID_REFERENCE_TYPES)}",
                                yaml_value=source["type"],
                            )
                        )

        return issues

    def validate_poems_field(
        self, file_path: Path, poems_data: Any
    ) -> List[MetadataIssue]:
        """
        Validate poems field structure.

        Based on: md_entry.py:_parse_poems_field()

        Required: title, content
        Optional: revision_date, notes
        """
        issues = []

        if not isinstance(poems_data, list):
            issues.append(
                MetadataIssue(
                    file_path=file_path,
                    field_name="poems",
                    severity="error",
                    message="Poems field must be a list",
                    suggestion="Use: poems:\n  - title: \"...\"\n    content: |",
                )
            )
            return issues

        # ISO date pattern for revision_date
        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')

        for idx, poem in enumerate(poems_data):
            if not isinstance(poem, dict):
                issues.append(
                    MetadataIssue(
                        file_path=file_path,
                        field_name=f"poems[{idx}]",
                        severity="error",
                        message=f"Poem must be a dict, got {type(poem).__name__}",
                        suggestion="Use dict format with title and content",
                    )
                )
                continue

            # Check required fields
            if "title" not in poem:
                issues.append(
                    MetadataIssue(
                        file_path=file_path,
                        field_name=f"poems[{idx}]",
                        severity="error",
                        message="Poem missing required 'title' field",
                        suggestion="Add: title: \"Poem Title\"",
                    )
                )

            if "content" not in poem:
                issues.append(
                    MetadataIssue(
                        file_path=file_path,
                        field_name=f"poems[{idx}]",
                        severity="error",
                        message="Poem missing required 'content' field",
                        suggestion="Add: content: |\n  Line 1\n  Line 2",
                    )
                )

            # Check revision_date format if present
            if "revision_date" in poem:
                if not date_pattern.match(str(poem["revision_date"]).strip()):
                    issues.append(
                        MetadataIssue(
                            file_path=file_path,
                            field_name=f"poems[{idx}].revision_date",
                            severity="warning",
                            message=f"Invalid revision_date format: '{poem['revision_date']}'",
                            suggestion="Use YYYY-MM-DD format (will default to entry date)",
                            yaml_value=poem["revision_date"],
                        )
                    )

        return issues

    def validate_manuscript_field(
        self, file_path: Path, manuscript_data: Any
    ) -> List[MetadataIssue]:
        """
        Validate manuscript field structure.

        Based on: models_manuscript.py and validation constants

        Required: status, edited
        Optional: themes, notes
        """
        issues = []

        if not isinstance(manuscript_data, dict):
            issues.append(
                MetadataIssue(
                    file_path=file_path,
                    field_name="manuscript",
                    severity="error",
                    message=f"Manuscript field must be a dict, got {type(manuscript_data).__name__}",
                    suggestion="Use: manuscript:\n  status: draft\n  edited: false",
                )
            )
            return issues

        # Check status
        if "status" in manuscript_data:
            if manuscript_data["status"] not in self.VALID_MANUSCRIPT_STATUS:
                issues.append(
                    MetadataIssue(
                        file_path=file_path,
                        field_name="manuscript.status",
                        severity="error",
                        message=f"Invalid manuscript status: '{manuscript_data['status']}'",
                        suggestion=f"Valid statuses: {', '.join(self.VALID_MANUSCRIPT_STATUS)}",
                        yaml_value=manuscript_data["status"],
                    )
                )

        # Check edited field type
        if "edited" in manuscript_data:
            if not isinstance(manuscript_data["edited"], bool):
                issues.append(
                    MetadataIssue(
                        file_path=file_path,
                        field_name="manuscript.edited",
                        severity="warning",
                        message=f"Manuscript edited should be boolean, got {type(manuscript_data['edited']).__name__}",
                        suggestion="Use: edited: true or edited: false",
                        yaml_value=manuscript_data["edited"],
                    )
                )

        # Check themes is list
        if "themes" in manuscript_data:
            if not isinstance(manuscript_data["themes"], list):
                issues.append(
                    MetadataIssue(
                        file_path=file_path,
                        field_name="manuscript.themes",
                        severity="warning",
                        message="Manuscript themes should be a list",
                        suggestion="Use: themes:\n  - theme1\n  - theme2",
                    )
                )

        return issues

    def validate_file(self, file_path: Path) -> List[MetadataIssue]:
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
        if "people" in metadata:
            issues.extend(self.validate_people_field(file_path, metadata["people"]))

        if "locations" in metadata:
            city_data = metadata.get("city")
            issues.extend(
                self.validate_locations_field(file_path, metadata["locations"], city_data)
            )

        if "dates" in metadata:
            issues.extend(self.validate_dates_field(file_path, metadata["dates"]))

        if "references" in metadata:
            issues.extend(self.validate_references_field(file_path, metadata["references"]))

        if "poems" in metadata:
            issues.extend(self.validate_poems_field(file_path, metadata["poems"]))

        if "manuscript" in metadata:
            issues.extend(self.validate_manuscript_field(file_path, metadata["manuscript"]))

        return issues

    def validate_all(self) -> MetadataValidationReport:
        """
        Validate all markdown files in directory.

        Returns:
            Complete validation report
        """
        report = MetadataValidationReport()
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


def format_metadata_report(report: MetadataValidationReport) -> str:
    """
    Format metadata validation report as readable text.

    Args:
        report: Validation report to format

    Returns:
        Formatted report string
    """
    lines = []
    lines.append("\n" + "=" * 60)
    lines.append("METADATA VALIDATION REPORT")
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
        lines.append("✅ ALL METADATA STRUCTURES VALID")
    else:
        lines.append("❌ METADATA VALIDATION FAILED")
    lines.append("")

    # Group issues by file
    if report.issues:
        issues_by_file: Dict[Path, List[MetadataIssue]] = {}
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
