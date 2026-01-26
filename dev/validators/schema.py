#!/usr/bin/env python3
"""
schema.py
---------
Centralized schema validation using authoritative enum sources.

This module provides schema-level validation by importing enum values
directly from their authoritative sources (database models). This eliminates
the need for hardcoded enum lists in multiple validators.

Key Principles:
- Single Source of Truth: All enum values imported from models/enums.py
- Type Safety: Validates field types against expected schemas
- Reusability: Used by both md.py and metadata.py validators
- Maintainability: When enums change, validators automatically stay in sync

Usage:
    from dev.validators.schema import SchemaValidator

    validator = SchemaValidator()
    issues = validator.validate_references(references_list)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# --- Local imports ---
from dev.database.models.enums import ChapterStatus, ReferenceMode, ReferenceType
from dev.core.validators import DataValidator


@dataclass
class SchemaIssue:
    """Represents a schema validation issue."""

    field_path: str  # e.g., "references[0].source.type"
    severity: str  # error, warning
    message: str
    suggestion: Optional[str] = None
    actual_value: Optional[Any] = None


class SchemaValidator:
    """
    Validates metadata structures against schema definitions.

    This validator checks:
    - Enum values match authoritative sources
    - Field types match expected types
    - Required fields are present
    - Value formats are correct

    It does NOT check:
    - Parser-specific compatibility (see metadata.py)
    - Database referential integrity (see db.py)
    - Cross-entry consistency (see consistency.py)
    """

    # ========== Enum Value Providers ==========
    # These methods provide the authoritative enum values
    # directly from the database models.

    @staticmethod
    def get_valid_reference_types() -> List[str]:
        """Get valid reference types from authoritative enum."""
        return ReferenceType.choices()

    @staticmethod
    def get_valid_reference_modes() -> List[str]:
        """Get valid reference modes from authoritative enum."""
        return ReferenceMode.choices()

    @staticmethod
    def get_valid_chapter_status() -> List[str]:
        """Get valid manuscript status values."""
        return ChapterStatus.choices()

    # ========== Field Validators ==========

    def _validate_enum_field(
        self,
        value: str,
        valid_values: List[str],
        field_name: str,
        field_path: str,
    ) -> Optional[SchemaIssue]:
        """
        Generic enum field validator.

        Args:
            value: The value to validate
            valid_values: List of valid enum values
            field_name: Human-readable field name for error messages
            field_path: Path to the field (for error reporting)

        Returns:
            SchemaIssue if invalid, None if valid
        """
        if value not in valid_values:
            return SchemaIssue(
                field_path=field_path,
                severity="error",
                message=f"Invalid {field_name}: '{value}'",
                suggestion=f"Valid values: {', '.join(valid_values)}",
                actual_value=value,
            )
        return None

    def validate_reference_mode(
        self, mode: str, field_path: str = "mode"
    ) -> Optional[SchemaIssue]:
        """Validate a reference mode value."""
        return self._validate_enum_field(
            mode, self.get_valid_reference_modes(), "reference mode", field_path
        )

    def validate_reference_type(
        self, ref_type: str, field_path: str = "type"
    ) -> Optional[SchemaIssue]:
        """Validate a reference type value."""
        return self._validate_enum_field(
            ref_type, self.get_valid_reference_types(), "reference type", field_path
        )

    def validate_manuscript_status(
        self, status: str, field_path: str = "manuscript.status"
    ) -> Optional[SchemaIssue]:
        """Validate a manuscript status value."""
        return self._validate_enum_field(
            status, self.get_valid_chapter_status(), "manuscript status", field_path
        )

    def validate_date_format(
        self, date_value: Any, field_path: str = "date"
    ) -> Optional[SchemaIssue]:
        """
        Validate a date format.

        Args:
            date_value: The date value to validate
            field_path: Path to the field (for error reporting)

        Returns:
            SchemaIssue if invalid, None if valid
        """
        if not DataValidator.normalize_date(date_value):
            return SchemaIssue(
                field_path=field_path,
                severity="error",
                message=f"Invalid date format: '{date_value}'",
                suggestion="Use YYYY-MM-DD format (e.g., 2024-01-15)",
                actual_value=date_value,
            )
        return None

    # ========== Complex Structure Validators ==========

    def validate_reference_structure(
        self, reference: Dict[str, Any], index: int = 0
    ) -> List[SchemaIssue]:
        """
        Validate a single reference structure.

        Checks:
        - Reference is a dict
        - Mode value (if present) is valid enum
        - Source structure (if present) is valid
        - Source type (if present) is valid enum

        Args:
            reference: The reference dict to validate
            index: Index in the references list (for error reporting)

        Returns:
            List of SchemaIssues found
        """
        issues = []
        base_path = f"references[{index}]"

        # Must be a dict
        if not isinstance(reference, dict):
            issues.append(
                SchemaIssue(
                    field_path=base_path,
                    severity="error",
                    message=f"Reference must be a dict, got {type(reference).__name__}",
                    suggestion="Use dict format with content/description and source",
                    actual_value=str(reference),
                )
            )
            return issues  # Can't continue if not a dict

        # Validate mode (if present)
        if "mode" in reference:
            mode_issue = self.validate_reference_mode(
                reference["mode"], f"{base_path}.mode"
            )
            if mode_issue:
                issues.append(mode_issue)

        # Validate source structure (if present)
        if "source" in reference:
            source = reference["source"]
            source_path = f"{base_path}.source"

            if not isinstance(source, dict):
                issues.append(
                    SchemaIssue(
                        field_path=source_path,
                        severity="error",
                        message="Source must be a dict",
                        suggestion="Use: source: {title: '...', type: '...'}",
                    )
                )
            else:
                # Validate type (if present)
                if "type" in source:
                    type_issue = self.validate_reference_type(
                        source["type"], f"{source_path}.type"
                    )
                    if type_issue:
                        issues.append(type_issue)

        return issues

    def validate_references_schema(
        self, references_list: List[Any]
    ) -> List[SchemaIssue]:
        """
        Validate a list of references against schema.

        Args:
            references_list: List of reference dicts from YAML

        Returns:
            List of SchemaIssues found
        """
        issues = []

        if not isinstance(references_list, list):
            issues.append(
                SchemaIssue(
                    field_path="references",
                    severity="error",
                    message=f"References must be a list, got {type(references_list).__name__}",
                    suggestion="Use: references: [{content: '...'}, ...]",
                )
            )
            return issues

        for idx, ref in enumerate(references_list):
            issues.extend(self.validate_reference_structure(ref, idx))

        return issues

    def validate_manuscript_schema(
        self, manuscript: Dict[str, Any]
    ) -> List[SchemaIssue]:
        """
        Validate manuscript metadata structure.

        Args:
            manuscript: Manuscript dict from YAML

        Returns:
            List of SchemaIssues found
        """
        issues = []

        if not isinstance(manuscript, dict):
            issues.append(
                SchemaIssue(
                    field_path="manuscript",
                    severity="error",
                    message=f"Manuscript must be a dict, got {type(manuscript).__name__}",
                    suggestion="Use: manuscript: {status: 'draft'}",
                )
            )
            return issues

        # Validate status (if present)
        if "status" in manuscript:
            status_issue = self.validate_manuscript_status(
                manuscript["status"], "manuscript.status"
            )
            if status_issue:
                issues.append(status_issue)

        return issues
