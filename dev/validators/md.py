#!/usr/bin/env python3
"""
md.py
-----
Markdown file validation for Palimpsest journal entries.

Validates:
- YAML frontmatter structure and syntax
- Required and optional fields
- Internal markdown links
- File naming conventions
- Entry body content

Usage:
    # Validate all markdown files
    validate md all

    # Check frontmatter only
    validate md frontmatter

    # Check internal links
    validate md links

    # Find orphaned files
    validate md orphans
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# --- Third party imports ---
import yaml

# --- Local imports ---
from dev.utils.md import split_frontmatter
from dev.core.validators import DataValidator
from dev.core.logging_manager import PalimpsestLogger
from dev.validators.schema import SchemaValidator


@dataclass
class MarkdownIssue:
    """Represents a validation issue in a markdown file."""

    file_path: Path
    line_number: Optional[int]
    severity: str  # error, warning, info
    category: str  # frontmatter, link, structure, content
    message: str
    suggestion: Optional[str] = None


@dataclass
class MarkdownValidationReport:
    """Complete markdown validation report."""

    files_checked: int = 0
    files_with_errors: int = 0
    files_with_warnings: int = 0
    total_errors: int = 0
    total_warnings: int = 0
    issues: List[MarkdownIssue] = field(default_factory=list)

    def add_issue(self, issue: MarkdownIssue) -> None:
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


class MarkdownValidator:
    """Validates markdown journal entry files."""

    # Required frontmatter fields
    REQUIRED_FIELDS = ["date"]

    # Schema validator for enum and type checking
    schema_validator = SchemaValidator()

    # Optional frontmatter fields with types
    OPTIONAL_FIELDS = {
        "word_count": int,
        "reading_time": (int, float),
        "epigraph": str,
        "epigraph_attribution": str,
        "notes": str,
        "city": (str, list),
        "locations": (list, dict),
        "people": list,
        "dates": list,
        "events": list,
        "tags": list,
        "related_entries": list,
        "references": list,
        "poems": list,
        "manuscript": dict,
    }

    # Note: Enum values are now imported from schema validator
    # which gets them from the authoritative source (models/enums.py).
    # No more hardcoded enum lists!

    def __init__(
        self,
        md_dir: Path,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize markdown validator.

        Args:
            md_dir: Directory containing markdown files
            logger: Optional logger instance
        """
        self.md_dir = md_dir
        self.logger = logger
        self.report = MarkdownValidationReport()

    def validate_file(self, file_path: Path) -> List[MarkdownIssue]:
        """
        Validate a single markdown file.

        Args:
            file_path: Path to markdown file

        Returns:
            List of issues found in the file
        """
        issues = []
        self.report.files_checked += 1

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            issue = MarkdownIssue(
                file_path=file_path,
                line_number=None,
                severity="error",
                category="structure",
                message=f"File encoding error: {e}",
                suggestion="Ensure file is UTF-8 encoded",
            )
            issues.append(issue)
            self.report.add_issue(issue)
            return issues

        # Split frontmatter and body
        try:
            frontmatter_text, body_lines = split_frontmatter(content)
            body = "\n".join(body_lines) if isinstance(body_lines, list) else body_lines
        except Exception as e:
            issue = MarkdownIssue(
                file_path=file_path,
                line_number=1,
                severity="error",
                category="frontmatter",
                message=f"Failed to parse frontmatter: {e}",
                suggestion="Check that frontmatter is enclosed in ---",
            )
            issues.append(issue)
            self.report.add_issue(issue)
            return issues

        # Validate frontmatter if present
        if frontmatter_text:
            frontmatter_issues = self._validate_frontmatter(
                file_path, frontmatter_text
            )
            issues.extend(frontmatter_issues)
            for issue in frontmatter_issues:
                self.report.add_issue(issue)

        # Validate body
        body_issues = self._validate_body(file_path, body, len(frontmatter_text.split('\n')) if frontmatter_text else 0)
        issues.extend(body_issues)
        for issue in body_issues:
            self.report.add_issue(issue)

        # Track files with issues
        if any(i.severity == "error" for i in issues):
            self.report.files_with_errors += 1
        if any(i.severity == "warning" for i in issues):
            self.report.files_with_warnings += 1

        return issues

    def _find_field_line_number(self, frontmatter_text: str, field_name: str) -> int:
        """
        Find the line number where a field appears in the frontmatter.

        Args:
            frontmatter_text: The YAML frontmatter text
            field_name: The field name to search for

        Returns:
            Line number (1-indexed) where the field appears in the original file,
            accounting for the opening "---" delimiter (adds 1 to the frontmatter line number)
        """
        lines = frontmatter_text.split('\n')
        for i, line in enumerate(lines, start=1):
            # Look for "field_name:" at the start of a line (possibly with indentation)
            if re.match(rf'^\s*{re.escape(field_name)}\s*:', line):
                # Add 1 to account for the opening "---" delimiter
                return i + 1
        return 1

    def _validate_frontmatter(
        self, file_path: Path, frontmatter_text: str
    ) -> List[MarkdownIssue]:
        """Validate YAML frontmatter structure and content."""
        issues = []

        # Parse YAML
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as e:
            problem_mark = getattr(e, 'problem_mark', None)
            line_num = problem_mark.line + 1 if problem_mark else None
            issues.append(
                MarkdownIssue(
                    file_path=file_path,
                    line_number=line_num,
                    severity="error",
                    category="frontmatter",
                    message=f"Invalid YAML syntax: {e}",
                    suggestion="Check YAML formatting (indentation, colons, quotes)",
                )
            )
            return issues

        if not isinstance(frontmatter, dict):
            issues.append(
                MarkdownIssue(
                    file_path=file_path,
                    line_number=1,
                    severity="error",
                    category="frontmatter",
                    message="Frontmatter must be a dictionary/object",
                )
            )
            return issues

        # Check required fields
        for field_name in self.REQUIRED_FIELDS:
            if field_name not in frontmatter:
                issues.append(
                    MarkdownIssue(
                        file_path=file_path,
                        line_number=1,
                        severity="error",
                        category="frontmatter",
                        message=f"Required field '{field_name}' missing",
                        suggestion=f"Add '{field_name}: <value>' to frontmatter",
                    )
                )
            elif frontmatter[field_name] is None or frontmatter[field_name] == "":
                issues.append(
                    MarkdownIssue(
                        file_path=file_path,
                        line_number=1,
                        severity="error",
                        category="frontmatter",
                        message=f"Required field '{field_name}' is empty",
                    )
                )

        # Validate date format
        if "date" in frontmatter:
            date_value = frontmatter["date"]
            if not DataValidator.normalize_date(date_value):
                issues.append(
                    MarkdownIssue(
                        file_path=file_path,
                        line_number=1,
                        severity="error",
                        category="frontmatter",
                        message=f"Invalid date format: '{date_value}'",
                        suggestion="Use YYYY-MM-DD format (e.g., 2024-01-15)",
                    )
                )

        # Check field types
        for field_key, expected_type in self.OPTIONAL_FIELDS.items():
            if field_key in frontmatter and frontmatter[field_key] is not None:
                value = frontmatter[field_key]
                if not isinstance(value, expected_type):
                    # Fields that cause data loss if wrong type should be errors
                    # Fields that are just formatting issues can be warnings
                    data_loss_fields = {"locations", "people", "events", "tags", "references", "poems", "dates", "related_entries"}
                    severity = "error" if field_key in data_loss_fields else "warning"

                    # Find the actual line number for this field
                    line_num = self._find_field_line_number(frontmatter_text, field_key)

                    issues.append(
                        MarkdownIssue(
                            file_path=file_path,
                            line_number=line_num,
                            severity=severity,
                            category="frontmatter",
                            message=f"Field '{field_key}' has unexpected type: {type(value).__name__}",
                            suggestion=f"Expected: {expected_type if isinstance(expected_type, type) else ' or '.join(t.__name__ for t in expected_type)}. Data will be lost if not fixed.",
                        )
                    )

        # Validate manuscript section using schema validator
        if "manuscript" in frontmatter and isinstance(frontmatter["manuscript"], dict):
            schema_issues = self.schema_validator.validate_manuscript_schema(
                frontmatter["manuscript"]
            )
            for schema_issue in schema_issues:
                # Find line number for manuscript or status field
                line_num = self._find_field_line_number(frontmatter_text, "status")
                if line_num == 1:  # If status not found, try manuscript
                    line_num = self._find_field_line_number(frontmatter_text, "manuscript")

                issues.append(
                    MarkdownIssue(
                        file_path=file_path,
                        line_number=line_num,
                        severity=schema_issue.severity,
                        category="frontmatter",
                        message=schema_issue.message,
                        suggestion=schema_issue.suggestion,
                    )
                )

        # Validate references using schema validator
        if "references" in frontmatter and isinstance(frontmatter["references"], list):
            # Find line number for references field
            ref_line_num = self._find_field_line_number(frontmatter_text, "references")

            schema_issues = self.schema_validator.validate_references_schema(
                frontmatter["references"]
            )
            for schema_issue in schema_issues:
                issues.append(
                    MarkdownIssue(
                        file_path=file_path,
                        line_number=ref_line_num,
                        severity=schema_issue.severity,
                        category="frontmatter",
                        message=schema_issue.message,
                        suggestion=schema_issue.suggestion,
                    )
                )

        # Validate dates field structure
        if "dates" in frontmatter and isinstance(frontmatter["dates"], list):
            dates_line_num = self._find_field_line_number(frontmatter_text, "dates")

            # Get the main people list for validation
            main_people = []
            if "people" in frontmatter and isinstance(frontmatter["people"], list):
                for person in frontmatter["people"]:
                    if isinstance(person, str):
                        # Extract all name variations from the string
                        # Formats: "Name", "Name (Full Name)", "@Alias", "@Alias (Name)"

                        # Check for parenthetical expansion
                        if '(' in person and person.endswith(')'):
                            before_paren, in_paren = person.split('(', 1)
                            before_paren = before_paren.strip().lstrip('@')
                            in_paren = in_paren.rstrip(')').strip()

                            # Add both parts (e.g., "@Majo (María)" → ["majo", "maría"])
                            if before_paren:
                                # Replace hyphens/underscores with spaces for matching
                                normalized = before_paren.replace('_', ' ').replace('-', ' ') if '_' not in before_paren else before_paren.replace('_', ' ')
                                main_people.append(normalized.lower())
                            if in_paren:
                                # Replace hyphens/underscores with spaces for matching
                                normalized = in_paren.replace('_', ' ').replace('-', ' ') if '_' not in in_paren else in_paren.replace('_', ' ')
                                main_people.append(normalized.lower())
                        else:
                            # Simple name without parentheses
                            name = person.strip().lstrip('@')
                            if name:
                                # Replace hyphens/underscores with spaces for matching
                                normalized = name.replace('_', ' ').replace('-', ' ') if '_' not in name else name.replace('_', ' ')
                                main_people.append(normalized.lower())
                    elif isinstance(person, dict):
                        if "name" in person:
                            main_people.append(person["name"].lower())
                        if "full_name" in person:
                            main_people.append(person["full_name"].lower())
                        if "alias" in person:
                            main_people.append(person["alias"].lower())

            for idx, date_item in enumerate(frontmatter["dates"]):
                # Skip the opt-out markers
                if date_item == "~" or date_item is None:
                    continue

                # String dates are valid
                if isinstance(date_item, str):
                    continue

                # Dict dates should have required fields
                if isinstance(date_item, dict):
                    import datetime
                    date_value = date_item.get("date")

                    # Check if date field is missing or None
                    if "date" not in date_item or date_value is None:
                        issues.append(
                            MarkdownIssue(
                                file_path=file_path,
                                line_number=dates_line_num,
                                severity="error",
                                category="frontmatter",
                                message=f"Date entry {idx+1}: Missing required 'date' field" + (" (date: ~ is invalid, use just ~ at list level)" if date_value is None else ""),
                                suggestion="To exclude entry date, use '~' or 'null' as a list item, not as a dict value. Example: dates: [~, ...]",
                            )
                        )
                    # Accept '.' as shorthand for entry date, or string, or datetime.date object
                    elif date_value != "." and not isinstance(date_value, (str, datetime.date)):
                        issues.append(
                            MarkdownIssue(
                                file_path=file_path,
                                line_number=dates_line_num,
                                severity="error",
                                category="frontmatter",
                                message=f"Date entry {idx+1}: 'date' field must be a string or date (or '.' for entry date)",
                                suggestion="Use YYYY-MM-DD format or '.' for the entry's date",
                            )
                        )

                    # Validate people field if present
                    if "people" in date_item:
                        people_field = date_item["people"]
                        # Accept string or list for people in dates
                        if not isinstance(people_field, (str, list)):
                            issues.append(
                                MarkdownIssue(
                                    file_path=file_path,
                                    line_number=dates_line_num,
                                    severity="error",
                                    category="frontmatter",
                                    message=f"Date entry {idx+1}: Field 'people' must be string or list",
                                    suggestion="Use a string for single person or list for multiple people",
                                )
                            )
                        else:
                            # Check that people exist in main people field
                            people_list = [people_field] if isinstance(people_field, str) else people_field
                            for person_name in people_list:
                                if isinstance(person_name, str):
                                    # Extract just the name part (handle @Alias format)
                                    check_name = person_name.split('(')[0].strip().lstrip('@')
                                    # Replace hyphens/underscores with spaces for matching (consistent with parser)
                                    check_name = (check_name.replace('_', ' ').replace('-', ' ') if '_' not in check_name else check_name.replace('_', ' ')).lower()

                                    if check_name and main_people:
                                        # Try exact match first
                                        found = check_name in main_people

                                        # If not found, try matching as first name against full names
                                        if not found:
                                            for main_person in main_people:
                                                # Check if check_name is the first word of a full name
                                                first_word = main_person.split()[0] if ' ' in main_person else main_person
                                                if first_word == check_name:
                                                    found = True
                                                    break

                                        if not found:
                                            issues.append(
                                                MarkdownIssue(
                                                    file_path=file_path,
                                                    line_number=dates_line_num,
                                                    severity="error",
                                                    category="frontmatter",
                                                    message=f"Date entry {idx+1}: Person '{person_name}' not found in main 'people' field",
                                                    suggestion=f"Add '{person_name}' to the main 'people' field at the top of the frontmatter",
                                                )
                                            )

                    # Validate locations field if present
                    if "locations" in date_item:
                        locations_field = date_item["locations"]
                        # Accept string or list for locations in dates
                        if not isinstance(locations_field, (str, list)):
                            issues.append(
                                MarkdownIssue(
                                    file_path=file_path,
                                    line_number=dates_line_num,
                                    severity="error",
                                    category="frontmatter",
                                    message=f"Date entry {idx+1}: Field 'locations' must be string or list",
                                    suggestion="Use a string for single location or list for multiple locations",
                                )
                            )

        # Warn about unknown fields
        known_fields = set(self.REQUIRED_FIELDS) | set(self.OPTIONAL_FIELDS.keys())
        unknown_fields = set(frontmatter.keys()) - known_fields
        if unknown_fields:
            issues.append(
                MarkdownIssue(
                    file_path=file_path,
                    line_number=1,
                    severity="warning",
                    category="frontmatter",
                    message=f"Unknown fields: {', '.join(unknown_fields)}",
                    suggestion="These fields will be ignored during processing",
                )
            )

        return issues

    def _validate_body(
        self, file_path: Path, body: str, frontmatter_lines: int
    ) -> List[MarkdownIssue]:
        """Validate markdown body content."""
        issues = []

        # Check if body is empty
        if not body or not body.strip():
            issues.append(
                MarkdownIssue(
                    file_path=file_path,
                    line_number=frontmatter_lines + 3,
                    severity="warning",
                    category="content",
                    message="Entry body is empty",
                    suggestion="Add content after the frontmatter",
                )
            )

        # Check for placeholder text
        placeholders = ["TODO", "FIXME", "XXX", "PLACEHOLDER"]
        for placeholder in placeholders:
            if placeholder in body:
                line_no = body[:body.index(placeholder)].count('\n') + frontmatter_lines + 3
                issues.append(
                    MarkdownIssue(
                        file_path=file_path,
                        line_number=line_no,
                        severity="warning",
                        category="content",
                        message=f"Placeholder text found: {placeholder}",
                        suggestion="Replace placeholder with actual content",
                    )
                )

        return issues

    def validate_all(self) -> MarkdownValidationReport:
        """
        Validate all markdown files in the directory.

        Returns:
            Complete validation report
        """
        md_files = list(self.md_dir.glob("**/*.md"))

        if not md_files:
            if self.logger:
                self.logger.log_warning(f"No markdown files found in {self.md_dir}")

        for md_file in md_files:
            self.validate_file(md_file)

        return self.report

    def validate_links(self) -> List[MarkdownIssue]:
        """
        Validate internal markdown links between files.

        Returns:
            List of broken link issues
        """
        issues = []

        # Pattern for markdown links: [text](path)
        link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')

        for md_file in self.md_dir.glob("**/*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                for match in link_pattern.finditer(content):
                    link_text, link_path = match.groups()

                    # Skip external links
                    if link_path.startswith(('http://', 'https://', 'mailto:')):
                        continue

                    # Resolve relative path
                    try:
                        target_path = (md_file.parent / link_path).resolve()
                        if not target_path.exists():
                            line_no = content[:match.start()].count('\n') + 1
                            issues.append(
                                MarkdownIssue(
                                    file_path=md_file,
                                    line_number=line_no,
                                    severity="error",
                                    category="link",
                                    message=f"Broken link: [{link_text}]({link_path})",
                                    suggestion=f"Target file not found: {target_path}",
                                )
                            )
                    except (ValueError, OSError) as e:
                        line_no = content[:match.start()].count('\n') + 1
                        issues.append(
                            MarkdownIssue(
                                file_path=md_file,
                                line_number=line_no,
                                severity="error",
                                category="link",
                                message=f"Invalid link path: {link_path}",
                                suggestion=str(e),
                            )
                        )
            except Exception as e:
                issues.append(
                    MarkdownIssue(
                        file_path=md_file,
                        line_number=None,
                        severity="error",
                        category="link",
                        message=f"Error checking links: {e}",
                    )
                )

        return issues


def format_markdown_report(report: MarkdownValidationReport) -> str:
    """
    Format markdown validation report as readable text.

    Args:
        report: Validation report to format

    Returns:
        Formatted report string
    """
    lines = []
    lines.append("\n" + "=" * 60)
    lines.append("MARKDOWN VALIDATION REPORT")
    lines.append("=" * 60)
    lines.append("")

    # Summary
    lines.append(f"Files Checked: {report.files_checked}")
    lines.append(f"✅ Clean Files: {report.files_checked - report.files_with_errors - report.files_with_warnings}")
    lines.append(f"⚠️  Files with Warnings: {report.files_with_warnings}")
    lines.append(f"❌ Files with Errors: {report.files_with_errors}")
    lines.append("")
    lines.append(f"Total Warnings: {report.total_warnings}")
    lines.append(f"Total Errors: {report.total_errors}")
    lines.append("")

    # Overall status
    if report.is_healthy:
        lines.append("✅ ALL FILES VALID")
    else:
        lines.append("❌ VALIDATION FAILED")
    lines.append("")

    # Group issues by file
    if report.issues:
        issues_by_file: Dict[Path, List[MarkdownIssue]] = {}
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
                line_info = f":{issue.line_number}" if issue.line_number else ""
                lines.append(f"   {severity_icon} [{issue.category}]{line_info} {issue.message}")
                if issue.suggestion:
                    lines.append(f"      💡 {issue.suggestion}")

            lines.append("")

    lines.append("=" * 60)

    return "\n".join(lines)
