#!/usr/bin/env python3
"""
diagnostic.py
-------------
Shared diagnostic types for all Palimpsest validators.

Provides a unified ``Diagnostic`` dataclass that every validator returns,
plus a ``ValidationReport`` container and a ``format_diagnostics()``
helper for CLI output.  The types are JSON-serializable and compatible
with vim.diagnostic.

Key Features:
    - Single diagnostic type across all validator modules
    - JSON and quickfix output formats
    - vim.diagnostic-compatible field layout
    - Convenience helpers on ValidationReport (add_error, add_warning)

Usage:
    from dev.validators.diagnostic import Diagnostic, ValidationReport, format_diagnostics

    report = ValidationReport(file_path="my_file.yaml")
    report.add_error("Missing required field: date", code="ENTRY_MISSING_FIELD")

    # Quickfix output (for nvim)
    print(report.quickfix_output())

    # JSON output (for editor integrations)
    print(report.to_json())

    # Formatted text with severity icons
    print(format_diagnostics(report.diagnostics))
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List


# ==================== Diagnostic ====================


@dataclass
class Diagnostic:
    """
    A single diagnostic finding from validation.

    Represents a structural issue, data inconsistency, or style violation
    found by any Palimpsest validator. Designed for JSON serialization
    and compatibility with vim.diagnostic.

    Attributes:
        file: Path to the file containing the diagnostic
        line: 1-based line number where the issue starts (0 if unknown)
        col: 1-based column number where the issue starts (0 if unknown)
        end_line: 1-based end line (same as line for single-line issues)
        end_col: 1-based end column
        severity: Diagnostic severity: "error", "warning", or "info"
        code: Machine-readable diagnostic code (e.g., UNRESOLVED_WIKILINK)
        message: Human-readable description of the issue
        source: Diagnostic source identifier, always "palimpsest"
    """

    file: str
    line: int
    col: int
    end_line: int
    end_col: int
    severity: str
    code: str
    message: str
    source: str = "palimpsest"

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize diagnostic to dict for JSON output.

        Returns:
            Dict with all diagnostic fields, suitable for
            json.dumps() and vim.diagnostic integration
        """
        return {
            "file": self.file,
            "line": self.line,
            "col": self.col,
            "end_line": self.end_line,
            "end_col": self.end_col,
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "source": self.source,
        }

    def quickfix_line(self) -> str:
        """
        Format diagnostic for nvim quickfix list.

        Returns:
            String in ``file:line:col: severity: message`` format
        """
        return f"{self.file}:{self.line}:{self.col}: {self.severity}: {self.message}"


# ==================== ValidationReport ====================


@dataclass
class ValidationReport:
    """
    Container for a collection of diagnostics from a validation run.

    Wraps a list of ``Diagnostic`` instances with computed properties
    for filtering by severity, merging reports, and output formatting.

    Attributes:
        diagnostics: All diagnostic findings
        file_path: Default file path for diagnostics added via convenience
            methods (can be overridden per-diagnostic)
    """

    diagnostics: List[Diagnostic] = field(default_factory=list)
    file_path: str = ""

    @property
    def errors(self) -> List[Diagnostic]:
        """All diagnostics with severity 'error'."""
        return [d for d in self.diagnostics if d.severity == "error"]

    @property
    def warnings(self) -> List[Diagnostic]:
        """All diagnostics with severity 'warning'."""
        return [d for d in self.diagnostics if d.severity == "warning"]

    @property
    def is_valid(self) -> bool:
        """True if no error-level diagnostics."""
        return not any(d.severity == "error" for d in self.diagnostics)

    @property
    def error_count(self) -> int:
        """Count of error-level diagnostics."""
        return sum(1 for d in self.diagnostics if d.severity == "error")

    @property
    def warning_count(self) -> int:
        """Count of warning-level diagnostics."""
        return sum(1 for d in self.diagnostics if d.severity == "warning")

    def add(self, diagnostic: Diagnostic) -> None:
        """
        Append a diagnostic to the report.

        Args:
            diagnostic: Diagnostic instance to add
        """
        self.diagnostics.append(diagnostic)

    def add_error(
        self,
        message: str,
        code: str = "",
        file: str = "",
        line: int = 0,
        col: int = 0,
    ) -> None:
        """
        Add an error-level diagnostic.

        Args:
            message: Human-readable description
            code: Machine-readable code (e.g., ENTRY_MISSING_FIELD)
            file: File path (defaults to report's file_path)
            line: 1-based line number (0 if unknown)
            col: 1-based column number (0 if unknown)
        """
        self.diagnostics.append(Diagnostic(
            file=file or self.file_path,
            line=line, col=col,
            end_line=line, end_col=col,
            severity="error", code=code, message=message,
        ))

    def add_warning(
        self,
        message: str,
        code: str = "",
        file: str = "",
        line: int = 0,
        col: int = 0,
    ) -> None:
        """
        Add a warning-level diagnostic.

        Args:
            message: Human-readable description
            code: Machine-readable code
            file: File path (defaults to report's file_path)
            line: 1-based line number (0 if unknown)
            col: 1-based column number (0 if unknown)
        """
        self.diagnostics.append(Diagnostic(
            file=file or self.file_path,
            line=line, col=col,
            end_line=line, end_col=col,
            severity="warning", code=code, message=message,
        ))

    def merge(self, other: ValidationReport) -> None:
        """
        Merge another report's diagnostics into this one.

        Args:
            other: Report whose diagnostics will be appended
        """
        self.diagnostics.extend(other.diagnostics)

    def quickfix_output(self) -> str:
        """
        Format all diagnostics for nvim quickfix.

        Returns:
            Newline-separated quickfix lines
        """
        return "\n".join(d.quickfix_line() for d in self.diagnostics)

    def to_json(self) -> str:
        """
        Serialize all diagnostics to JSON.

        Returns:
            JSON string with list of diagnostic dicts
        """
        return json.dumps(
            [d.to_dict() for d in self.diagnostics], indent=2
        )


# ==================== Formatting ====================


def format_diagnostics(
    diagnostics: List[Diagnostic],
    fmt: str = "text",
) -> str:
    """
    Format a list of diagnostics for CLI output.

    Args:
        diagnostics: Diagnostic instances to format
        fmt: Output format — ``"text"`` (emoji severity) or ``"json"``

    Returns:
        Formatted string suitable for terminal or machine consumption
    """
    if fmt == "json":
        return json.dumps(
            [d.to_dict() for d in diagnostics], indent=2
        )

    lines: List[str] = []
    for d in diagnostics:
        icon = {"error": "\u274c", "warning": "\u26a0\ufe0f", "info": "\u2139\ufe0f"}.get(
            d.severity, ""
        )
        if d.file and d.line:
            lines.append(f"{icon} {d.file}:{d.line}:{d.col}: [{d.code}] {d.message}")
        elif d.file:
            lines.append(f"{icon} {d.file}: [{d.code}] {d.message}")
        else:
            lines.append(f"{icon} [{d.code}] {d.message}")
    return "\n".join(lines)
