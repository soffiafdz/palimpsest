#!/usr/bin/env python3
"""
validators.py
--------------------
Data validation and normalization utilities for all Palimpsest operations.

Provides type-safe conversion, validation, and normalization functions
used across database operations, conversion pipelines, and utilities.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from .exceptions import ValidationError


class DataValidator:
    """Centralized data validation for database operations."""

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
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValidationError(f"Required field '{field}' missing or empty")

    @staticmethod
    def normalize_date(date_value: Any) -> Optional[date]:
        """
        Normalize various date inputs to date object.

        Args:
            date_value: Date string, date object, or datetime

        Returns:
            Normalized date object or None
        """
        if isinstance(date_value, date):
            return date_value
        elif isinstance(date_value, datetime):
            return date_value.date()
        elif isinstance(date_value, str):
            # TODO: This is redundant. Move that functionality here.
            return md.parse_date(date_value)
        return None

    @staticmethod
    def normalize_string(value: Any) -> Optional[str]:
        """
        Normalize string value.

        Args:
            value: Value to normalize

        Returns:
            Normalized string or None
        """
        return md.normalize_str(value) if value else None

    @staticmethod
    def normalize_bool(value: Any) -> Optional[bool]:
        """
        Convert various inputs to boolean.

        Args:
            value: Value to convert

        Returns:
            Boolean value or None

        Raises:
            ValidationError: If conversion fails
        """
        if isinstance(value, bool):
            return value
        elif isinstance(value, (int, float)):
            if value == 0:
                return False
            elif value == 1:
                return True
            else:
                raise ValidationError(f"Cannot convert numeric '{value}' to boolean")
        elif isinstance(value, str):
            if value.lower() in ("true", "1", "yes", "on"):
                return True
            elif value.lower() in ("false", "0", "no", "off"):
                return False
            else:
                raise ValidationError(f"Cannot convert '{value}' to boolean")
        elif value is not None:
            return bool(value)
        return None

    @staticmethod
    def normalize_int(value: Any) -> Optional[int]:
        """
        Convert value to integer safely.

        Args:
            value: Value to convert

        Returns:
            Integer value or None
        """
        return md.safe_int(value) if value is not None else None

    @staticmethod
    def normalize_float(value: Any) -> Optional[float]:
        """
        Convert value to float safely.

        Args:
            value: Value to convert

        Returns:
            Float value or None
        """
        return md.safe_float(value) if value is not None else None
