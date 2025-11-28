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
from __future__ import annotations

import re
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from dev.utils.md import split_frontmatter
from dev.core.validators import DataValidator
from dev.core.logging_manager import PalimpsestLogger


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
    issues: Optional[List[MarkdownIssue]] = None

    def __post_init__(self):
        if self.issues is None:
            self.issues = []

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

    # Valid manuscript status values
    VALID_MANUSCRIPT_STATUS = [
        "unspecified",
        "draft",
        "reviewed",
        "included",
        "excluded",
        "final",
    ]

    # Valid reference modes
    VALID_REFERENCE_MODES = ["direct", "indirect", "paraphrase", "visual"]

    # Valid reference types
    VALID_REFERENCE_TYPES = [
        "book",
        "article",
        "film",
        "song",
        "album",
        "tv",
        "podcast",
        "video",
        "website",
        "other",
    ]

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
        for field in self.REQUIRED_FIELDS:
            if field not in frontmatter:
                issues.append(
                    MarkdownIssue(
                        file_path=file_path,
                        line_number=1,
                        severity="error",
                        category="frontmatter",
                        message=f"Required field '{field}' missing",
                        suggestion=f"Add '{field}: <value>' to frontmatter",
                    )
                )
            elif frontmatter[field] is None or frontmatter[field] == "":
                issues.append(
                    MarkdownIssue(
                        file_path=file_path,
                        line_number=1,
                        severity="error",
                        category="frontmatter",
                        message=f"Required field '{field}' is empty",
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
        for field, expected_type in self.OPTIONAL_FIELDS.items():
            if field in frontmatter and frontmatter[field] is not None:
                value = frontmatter[field]
                if not isinstance(value, expected_type):
                    issues.append(
                        MarkdownIssue(
                            file_path=file_path,
                            line_number=1,
                            severity="warning",
                            category="frontmatter",
                            message=f"Field '{field}' has unexpected type: {type(value).__name__}",
                            suggestion=f"Expected: {expected_type if isinstance(expected_type, type) else ' or '.join(t.__name__ for t in expected_type)}",
                        )
                    )

        # Validate manuscript section
        if "manuscript" in frontmatter and isinstance(frontmatter["manuscript"], dict):
            manuscript = frontmatter["manuscript"]
            if "status" in manuscript:
                if manuscript["status"] not in self.VALID_MANUSCRIPT_STATUS:
                    issues.append(
                        MarkdownIssue(
                            file_path=file_path,
                            line_number=1,
                            severity="error",
                            category="frontmatter",
                            message=f"Invalid manuscript status: '{manuscript['status']}'",
                            suggestion=f"Valid statuses: {', '.join(self.VALID_MANUSCRIPT_STATUS)}",
                        )
                    )

        # Validate references
        if "references" in frontmatter and isinstance(frontmatter["references"], list):
            for idx, ref in enumerate(frontmatter["references"]):
                if isinstance(ref, dict):
                    # Check mode
                    if "mode" in ref and ref["mode"] not in self.VALID_REFERENCE_MODES:
                        issues.append(
                            MarkdownIssue(
                                file_path=file_path,
                                line_number=1,
                                severity="error",
                                category="frontmatter",
                                message=f"Reference {idx+1}: Invalid mode '{ref['mode']}'",
                                suggestion=f"Valid modes: {', '.join(self.VALID_REFERENCE_MODES)}",
                            )
                        )

                    # Check source type
                    if "source" in ref and isinstance(ref["source"], dict):
                        if "type" in ref["source"] and ref["source"]["type"] not in self.VALID_REFERENCE_TYPES:
                            issues.append(
                                MarkdownIssue(
                                    file_path=file_path,
                                    line_number=1,
                                    severity="error",
                                    category="frontmatter",
                                    message=f"Reference {idx+1}: Invalid source type '{ref['source']['type']}'",
                                    suggestion=f"Valid types: {', '.join(self.VALID_REFERENCE_TYPES)}",
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
        md_files = {f.stem: f for f in self.md_dir.glob("**/*.md")}

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
            warnings = [i for i in file_issues if i.severity == "warning"]

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
