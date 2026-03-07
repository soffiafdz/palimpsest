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
from pathlib import Path
from typing import Dict, List, Optional

# --- Third party imports ---
import yaml

# --- Local imports ---
from dev.utils.md import split_frontmatter
from dev.core.validators import DataValidator
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.validators.schema import SchemaValidator
from dev.validators.frontmatter import FrontmatterValidator
from dev.validators.diagnostic import Diagnostic, ValidationReport


# Map diagnostic code prefixes to frontmatter field names for line lookup
_CODE_FIELD_MAP = {
    "PEOPLE": "people",
    "LOCATION": "locations",
    "DATE": "dates",
    "REFERENCE": "references",
    "POEM": "poems",
    "MANUSCRIPT": "manuscript",
    "UNKNOWN": None,
}


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
        self._files_checked = 0
        self._files_with_errors = 0
        self._files_with_warnings = 0
        self._all_diagnostics: List[Diagnostic] = []

    def validate_file(self, file_path: Path) -> List[Diagnostic]:
        """
        Validate a single markdown file.

        Args:
            file_path: Path to markdown file

        Returns:
            List of Diagnostic instances found
        """
        diagnostics: List[Diagnostic] = []
        self._files_checked += 1

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            diagnostics.append(Diagnostic(
                file=str(file_path), line=0, col=0, end_line=0, end_col=0,
                severity="error", code="FRONTMATTER_SYNTAX",
                message=f"File encoding error: {e}",
            ))
            self._all_diagnostics.extend(diagnostics)
            return diagnostics

        # Split frontmatter and body
        try:
            frontmatter_text, body_lines = split_frontmatter(content)
            body = "\n".join(body_lines) if isinstance(body_lines, list) else body_lines
        except Exception as e:
            diagnostics.append(Diagnostic(
                file=str(file_path), line=1, col=0, end_line=1, end_col=0,
                severity="error", code="FRONTMATTER_SYNTAX",
                message=f"Failed to parse frontmatter: {e}",
            ))
            self._all_diagnostics.extend(diagnostics)
            return diagnostics

        # Validate frontmatter if present
        if frontmatter_text:
            frontmatter_issues = self._validate_frontmatter(
                file_path, frontmatter_text
            )
            diagnostics.extend(frontmatter_issues)

        # Validate body
        body_issues = self._validate_body(file_path, body, len(frontmatter_text.split('\n')) if frontmatter_text else 0)
        diagnostics.extend(body_issues)

        # Track files with issues
        if any(d.severity == "error" for d in diagnostics):
            self._files_with_errors += 1
        if any(d.severity == "warning" for d in diagnostics):
            self._files_with_warnings += 1

        self._all_diagnostics.extend(diagnostics)
        return diagnostics

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
    ) -> List[Diagnostic]:
        """Validate YAML frontmatter structure and content."""
        diagnostics: List[Diagnostic] = []

        # Parse YAML
        try:
            frontmatter_data = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as e:
            problem_mark = getattr(e, 'problem_mark', None)
            line_num = problem_mark.line + 1 if problem_mark else 0
            diagnostics.append(Diagnostic(
                file=str(file_path), line=line_num, col=0, end_line=line_num, end_col=0,
                severity="error", code="FRONTMATTER_SYNTAX",
                message=f"Invalid YAML syntax: {e}",
            ))
            return diagnostics

        if not isinstance(frontmatter_data, dict):
            diagnostics.append(Diagnostic(
                file=str(file_path), line=1, col=0, end_line=1, end_col=0,
                severity="error", code="FRONTMATTER_SYNTAX",
                message="Frontmatter must be a dictionary/object",
            ))
            return diagnostics

        # Check required fields
        for field_name in self.REQUIRED_FIELDS:
            if field_name not in frontmatter_data:
                diagnostics.append(Diagnostic(
                    file=str(file_path), line=1, col=0, end_line=1, end_col=0,
                    severity="error", code="FRONTMATTER_FIELD",
                    message=f"Required field '{field_name}' missing",
                ))
            elif frontmatter_data[field_name] is None or frontmatter_data[field_name] == "":
                diagnostics.append(Diagnostic(
                    file=str(file_path), line=1, col=0, end_line=1, end_col=0,
                    severity="error", code="FRONTMATTER_FIELD",
                    message=f"Required field '{field_name}' is empty",
                ))

        # Validate date format
        if "date" in frontmatter_data:
            date_value = frontmatter_data["date"]
            if not DataValidator.normalize_date(date_value):
                diagnostics.append(Diagnostic(
                    file=str(file_path), line=1, col=0, end_line=1, end_col=0,
                    severity="error", code="FRONTMATTER_FIELD",
                    message=f"Invalid date format: '{date_value}'",
                ))

        # Check field types
        for field_key, expected_type in self.OPTIONAL_FIELDS.items():
            if field_key in frontmatter_data and frontmatter_data[field_key] is not None:
                value = frontmatter_data[field_key]
                if not isinstance(value, expected_type):
                    data_loss_fields = {"locations", "people", "events", "tags", "references", "poems", "dates", "related_entries"}
                    severity = "error" if field_key in data_loss_fields else "warning"
                    line_num = self._find_field_line_number(frontmatter_text, field_key)

                    diagnostics.append(Diagnostic(
                        file=str(file_path), line=line_num, col=0,
                        end_line=line_num, end_col=0,
                        severity=severity, code="FRONTMATTER_FIELD",
                        message=f"Field '{field_key}' has unexpected type: {type(value).__name__}",
                    ))

        # Validate manuscript section using schema validator
        if "manuscript" in frontmatter_data and isinstance(frontmatter_data["manuscript"], dict):
            schema_issues = self.schema_validator.validate_manuscript_schema(
                frontmatter_data["manuscript"]
            )
            for schema_issue in schema_issues:
                line_num = self._find_field_line_number(frontmatter_text, "status")
                if line_num == 1:
                    line_num = self._find_field_line_number(frontmatter_text, "manuscript")
                diagnostics.append(Diagnostic(
                    file=str(file_path), line=line_num, col=0,
                    end_line=line_num, end_col=0,
                    severity=schema_issue.severity, code="FRONTMATTER_FIELD",
                    message=schema_issue.message,
                ))

        # Validate references using schema validator
        if "references" in frontmatter_data and isinstance(frontmatter_data["references"], list):
            ref_line_num = self._find_field_line_number(frontmatter_text, "references")
            schema_issues = self.schema_validator.validate_references_schema(
                frontmatter_data["references"]
            )
            for schema_issue in schema_issues:
                diagnostics.append(Diagnostic(
                    file=str(file_path), line=ref_line_num, col=0,
                    end_line=ref_line_num, end_col=0,
                    severity=schema_issue.severity, code="FRONTMATTER_FIELD",
                    message=schema_issue.message,
                ))

        # --- Delegate detailed structure validation to FrontmatterValidator ---
        frontmatter_validator = FrontmatterValidator(self.md_dir, self.logger)
        frontmatter_diagnostics = frontmatter_validator.validate_file(file_path)
        for diag in frontmatter_diagnostics:
            # Try to look up line number from the code prefix
            prefix = diag.code.split("_")[0] if diag.code else ""
            field = _CODE_FIELD_MAP.get(prefix, "")
            if field:
                line_num = self._find_field_line_number(frontmatter_text, field)
                diagnostics.append(Diagnostic(
                    file=diag.file, line=line_num, col=0,
                    end_line=line_num, end_col=0,
                    severity=diag.severity, code=diag.code,
                    message=diag.message,
                ))
            else:
                diagnostics.append(diag)

        # Warn about unknown fields
        known_fields = set(self.REQUIRED_FIELDS) | set(self.OPTIONAL_FIELDS.keys())
        unknown_fields = set(frontmatter_data.keys()) - known_fields
        if unknown_fields:
            diagnostics.append(Diagnostic(
                file=str(file_path), line=1, col=0, end_line=1, end_col=0,
                severity="warning", code="UNKNOWN_FIELD",
                message=f"Unknown fields: {', '.join(unknown_fields)}",
            ))

        return diagnostics

    def _validate_body(
        self, file_path: Path, body: str, frontmatter_lines: int
    ) -> List[Diagnostic]:
        """Validate markdown body content."""
        diagnostics: List[Diagnostic] = []

        # Check if body is empty
        if not body or not body.strip():
            diagnostics.append(Diagnostic(
                file=str(file_path),
                line=frontmatter_lines + 3, col=0,
                end_line=frontmatter_lines + 3, end_col=0,
                severity="warning", code="EMPTY_BODY",
                message="Entry body is empty",
            ))

        # Check for placeholder text
        placeholders = ["TODO", "FIXME", "XXX", "PLACEHOLDER"]
        for placeholder in placeholders:
            if placeholder in body:
                line_no = body[:body.index(placeholder)].count('\n') + frontmatter_lines + 3
                diagnostics.append(Diagnostic(
                    file=str(file_path),
                    line=line_no, col=0, end_line=line_no, end_col=0,
                    severity="warning", code="PLACEHOLDER",
                    message=f"Placeholder text found: {placeholder}",
                ))

        return diagnostics

    def validate_all(self) -> ValidationReport:
        """
        Validate all markdown files in the directory.

        Returns:
            ValidationReport with all diagnostics
        """
        md_files = list(self.md_dir.glob("**/*.md"))

        if not md_files:
            safe_logger(self.logger).log_warning(f"No markdown files found in {self.md_dir}")

        for md_file in md_files:
            self.validate_file(md_file)

        report = ValidationReport()
        report.diagnostics = list(self._all_diagnostics)
        return report

    def validate_links(self) -> List[Diagnostic]:
        """
        Validate internal markdown links between files.

        Returns:
            List of BROKEN_LINK diagnostics
        """
        diagnostics: List[Diagnostic] = []

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
                            diagnostics.append(Diagnostic(
                                file=str(md_file),
                                line=line_no, col=0, end_line=line_no, end_col=0,
                                severity="error", code="BROKEN_LINK",
                                message=f"Broken link: [{link_text}]({link_path})",
                            ))
                    except (ValueError, OSError) as e:
                        line_no = content[:match.start()].count('\n') + 1
                        diagnostics.append(Diagnostic(
                            file=str(md_file),
                            line=line_no, col=0, end_line=line_no, end_col=0,
                            severity="error", code="BROKEN_LINK",
                            message=f"Invalid link path: {link_path} ({e})",
                        ))
            except Exception as e:
                diagnostics.append(Diagnostic(
                    file=str(md_file), line=0, col=0, end_line=0, end_col=0,
                    severity="error", code="BROKEN_LINK",
                    message=f"Error checking links: {e}",
                ))

        return diagnostics
