#!/usr/bin/env python3
"""
validators.py
--------------------
Data validation and normalization utilities for all Palimpsest operations.

Provides type-safe conversion, validation, and normalization functions
used across database operations, conversion pipelines, and utilities.

This module is format-agnostic and should not depend on specific file
formats (Markdown, YAML, etc.). It provides pure data type conversions.

Classes:
    DataValidator: Centralized validation with static methods

Key Methods:
    validate_required_fields: Check required fields exist and are non-None
    normalize_date: Convert various inputs to datetime.date
    normalize_string: Strip whitespace, return None if empty
    normalize_int/float: Safe numeric conversion
    normalize_bool: Convert strings/ints to boolean
    normalize_enum: Convert strings to enum instances
    extract_number: Extract first numeric value from string
    validate_date_string: Check ISO date format validity

Usage:
    from dev.core.validators import DataValidator

    # Validate required fields
    DataValidator.validate_required_fields(data, ["date", "content"])

    # Normalize various types
    date_obj = DataValidator.normalize_date("2024-01-15")
    count = DataValidator.normalize_int("42")
    is_active = DataValidator.normalize_bool("yes")

    # Extract numbers from strings
    word_count = DataValidator.extract_number("150 words")  # Returns 150.0

    # Normalize enums
    location_type = DataValidator.normalize_enum("venue", LocationType)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import re
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union

# --- Local imports ---
from .exceptions import ValidationError


class DataValidator:
    """
    Centralized data validation and normalization.

    Provides type-safe conversion functions that handle various input formats
    and return None for invalid/empty values rather than raising exceptions
    (except where noted).
    """

    @staticmethod
    def validate_required_fields(
        data: Dict[str, Any], required_fields: List[str], allow_falsy: bool = False
    ) -> None:
        """
        Validate that required fields are present and non-None.

        Args:
            data: Data dictionary to validate
            required_fields: List of required field names
            allow_falsy: If True, allows 0, False, and empty strings as valid values.
                        If False (default), only checks that field exists and is not None.

        Raises:
            ValidationError: If validation fails

        Examples:
            >>> DataValidator.validate_required_fields({"count": 0}, ["count"], allow_falsy=True)
            # OK - 0 is allowed when allow_falsy=True
            >>> DataValidator.validate_required_fields({"count": 0}, ["count"], allow_falsy=False)
            # Raises - 0 is falsy and allow_falsy=False
        """
        missing_fields = []
        for field in required_fields:
            if field not in data:
                missing_fields.append(field)
            elif data[field] is None:
                # None is always considered missing
                missing_fields.append(field)
            elif not allow_falsy and not data[field]:
                # If allow_falsy=False, check truthiness (rejects 0, False, "", [])
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

        Supports negative numbers. Useful for parsing metadata like "150 words" → 150.0

        Args:
            value: Input string or number

        Returns:
            Extracted numeric value or 0.0 if none found

        Examples:
            >>> DataValidator.extract_number("150 words")
            150.0
            >>> DataValidator.extract_number("-2.5 degrees")
            -2.5
            >>> DataValidator.extract_number(42)
            42.0
        """
        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            # Updated pattern to support negative numbers
            match = re.search(r"(-?\d+(?:\.\d+)?)", value)
            if match:
                return float(match.group(1))

        return 0.0

    @staticmethod
    def validate_date_string(date_input: Union[str, date]) -> bool:
        """
        Check if input is a valid date (string in ISO format or datetime.date object).

        Args:
            date_input: Date string or datetime.date object to validate

        Returns:
            True if valid YYYY-MM-DD format string or datetime.date object

        Examples:
            >>> DataValidator.validate_date_string("2024-01-15")
            True
            >>> DataValidator.validate_date_string("2024-1-5")
            False
            >>> from datetime import date
            >>> DataValidator.validate_date_string(date(2024, 1, 15))
            True
        """
        # Accept datetime.date objects directly
        if isinstance(date_input, date):
            return True

        # Validate string format
        try:
            datetime.strptime(date_input, "%Y-%m-%d")
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

