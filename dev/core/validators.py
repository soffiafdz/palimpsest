#!/usr/bin/env python3
"""
validators.py
--------------------
Data validation and normalization utilities for all Palimpsest operations.

Provides type-safe conversion, validation, and normalization functions
used across database operations, conversion pipelines, and utilities.

This module is format-agnostic and should not depend on specific file
formats (Markdown, YAML, etc.). It provides pure data type conversions.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from enum import Enum
from typing import cast, Any, Dict, List, Optional, Type, TYPE_CHECKING

from .exceptions import ValidationError

if TYPE_CHECKING:
    from dev.database.models import ReferenceMode, ReferenceType, RelationType


class DataValidator:
    """
    Centralized data validation and normalization.

    Provides type-safe conversion functions that handle various input formats
    and return None for invalid/empty values rather than raising exceptions
    (except where noted).
    """

    @staticmethod
    def validate_required_fields(
        data: Dict[str, Any], required_fields: List[str]
    ) -> None:
        """
        Validate that required fields are present and non-empty.

        Args:
            data: Data dictionary to validate
            required_fields: List of required field names

        Raises:
            ValidationError: If validation fails
        """
        missing_fields = []
        for field in required_fields:
            if field not in data or not data[field]:
                missing_fields.append(field)

        if missing_fields:
            fields_str = "', '".join(missing_fields)
            raise ValidationError(f"Required field(s) missing or empty: '{fields_str}'")

    @staticmethod
    def normalize_date(date_value: Any) -> Optional[date]:
        """
        Normalize various date inputs to date object.

        Accepts:
        - date objects (returned as-is)
        - datetime objects (converted to date)
        - ISO format strings "YYYY-MM-DD"

        Args:
            date_value: Date string, date object, or datetime

        Returns:
            Normalized date object or None if invalid/empty

        Examples:
            >>> DataValidator.normalize_date("2024-01-15")
            date(2024, 1, 15)
            >>> DataValidator.normalize_date(datetime(2024, 1, 15, 10, 30))
            date(2024, 1, 15)
            >>> DataValidator.normalize_date("invalid")
            None
        """
        if date_value is None:
            return None

        if isinstance(date_value, date) and not isinstance(date_value, datetime):
            return date_value

        if isinstance(date_value, datetime):
            return date_value.date()

        if isinstance(date_value, str):
            try:
                return datetime.strptime(date_value.strip(), "%Y-%m-%d").date()
            except (ValueError, AttributeError):
                return None

        return None

    @staticmethod
    def normalize_string(value: Any) -> Optional[str]:
        """
        Normalize string value, stripping whitespace.

        Args:
            value: Value to normalize

        Returns:
            Normalized non-empty string or None

        Examples:
            >>> DataValidator.normalize_string("  hello  ")
            'hello'
            >>> DataValidator.normalize_string("")
            None
            >>> DataValidator.normalize_string(None)
            None
        """
        if value is None:
            return None

        str_value = str(value).strip()
        return str_value if str_value else None

    @staticmethod
    def normalize_int(value: Any) -> Optional[int]:
        """
        Convert value to integer safely.

        Args:
            value: Value to convert (int, float, numeric string)

        Returns:
            Integer value or None if conversion fails

        Examples:
            >>> DataValidator.normalize_int("42")
            42
            >>> DataValidator.normalize_int(3.14)
            3
            >>> DataValidator.normalize_int("not a number")
            None
        """
        if value is None or value == "" or value == " ":
            return None

        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def normalize_float(value: Any) -> Optional[float]:
        """
        Convert value to float safely.

        Args:
            value: Value to convert (int, float, numeric string)

        Returns:
            Float value or None if conversion fails

        Examples:
            >>> DataValidator.normalize_float("3.14")
            3.14
            >>> DataValidator.normalize_float(42)
            42.0
            >>> DataValidator.normalize_float("not a number")
            None
        """
        if value is None or value == "" or value == " ":
            return None

        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def normalize_bool(value: Any) -> Optional[bool]:
        """
        Convert various inputs to boolean.

        Accepts:
        - Booleans (returned as-is)
        - Integers: 0 → False, 1 → True
        - Strings: "true"/"yes"/"on"/"1" → True, "false"/"no"/"off"/"0" → False

        Args:
            value: Value to convert

        Returns:
            Boolean value or None

        Raises:
            ValidationError: If conversion is ambiguous (e.g., int != 0 or 1)

        Examples:
            >>> DataValidator.normalize_bool("yes")
            True
            >>> DataValidator.normalize_bool(0)
            False
            >>> DataValidator.normalize_bool("maybe")  # raises ValidationError
        """
        if value is None:
            return None

        if isinstance(value, bool):
            return value

        if isinstance(value, (int, float)):
            if value == 0:
                return False
            elif value == 1:
                return True
            else:
                raise ValidationError(
                    f"Cannot convert numeric '{value}' to boolean (must be 0 or 1)"
                )

        if isinstance(value, str):
            lower_value = value.lower().strip()
            if lower_value in ("true", "1", "yes", "on"):
                return True
            elif lower_value in ("false", "0", "no", "off"):
                return False
            else:
                raise ValidationError(
                    f"Cannot convert '{value}' to boolean "
                    "(must be true/false, yes/no, on/off, or 1/0)"
                )

        # For other types, use truthiness
        return bool(value)

    @staticmethod
    def extract_number(value: Any) -> float:
        """
        Extract first numeric value from string or return number.

        Useful for parsing metadata like "150 words" → 150.0

        Args:
            value: Input string or number

        Returns:
            Extracted numeric value or 0.0 if none found

        Examples:
            >>> DataValidator.extract_number("150 words")
            150.0
            >>> DataValidator.extract_number("2.5 min")
            2.5
            >>> DataValidator.extract_number(42)
            42.0
        """
        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            match = re.search(r"(\d+(?:\.\d+)?)", value)
            if match:
                return float(match.group(1))

        return 0.0

    @staticmethod
    def validate_date_string(date_str: str) -> bool:
        """
        Check if string is valid ISO date format.

        Args:
            date_str: Date string to validate

        Returns:
            True if valid YYYY-MM-DD format

        Examples:
            >>> DataValidator.validate_date_string("2024-01-15")
            True
            >>> DataValidator.validate_date_string("2024-1-5")
            False
        """
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except (ValueError, TypeError, AttributeError):
            return False

    # --- Enums ---
    @staticmethod
    def normalize_enum(
        value: Any, enum_class: Type[Enum], field_name: str = "value"
    ) -> Optional[Enum]:
        """
        Normalize value to enum instance.

        Args:
            value: Value to convert (string, enum instance, or None)
            enum_class: The Enum class to convert to
            field_name: Field name for error messages

        Returns:
            Enum instance or None if value is None/empty

        Raises:
            ValidationError: If value is invalid for the enum

        Examples:
            >>> DataValidator.normalize_enum("venue", LocationType, "location_type")
            LocationType.VENUE
            >>> DataValidator.normalize_enum(LocationType.CITY, LocationType)
            LocationType.CITY
            >>> DataValidator.normalize_enum(None, LocationType)
            None
        """
        if value is None:
            return None

        # Already an enum instance of correct type
        if isinstance(value, enum_class):
            return value

        # Convert string to enum
        if isinstance(value, str):
            normalized = value.strip().lower()
            if not normalized:
                return None

            try:
                return enum_class(normalized)
            except ValueError:
                # Get valid choices for error message
                valid_choices = [e.value for e in enum_class]
                raise ValidationError(
                    f"Invalid {field_name} '{value}'. "
                    f"Valid options: {', '.join(valid_choices)}"
                )

        raise ValidationError(
            f"Cannot convert {type(value).__name__} to {enum_class.__name__}"
        )

    @staticmethod
    def normalize_reference_mode(value: Any) -> Optional[ReferenceMode]:
        """Normalize value to ReferenceMode enum."""
        result = DataValidator.normalize_enum(value, ReferenceMode, "reference_mode")
        return cast(Optional[ReferenceMode], result)

    @staticmethod
    def normalize_reference_type(value: Any) -> Optional[ReferenceType]:
        """Normalize value to ReferenceType enum."""
        result = DataValidator.normalize_enum(value, ReferenceType, "reference_type")
        return cast(Optional[ReferenceType], result)

    @staticmethod
    def normalize_relation_type(value: Any) -> Optional[RelationType]:
        """Normalize value to RelationType enum."""
        result = DataValidator.normalize_enum(value, RelationType, "relation_type")
        return cast(Optional[RelationType], result)
