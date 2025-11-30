"""
MdEntry Validator

Provides validation functions for MdEntry objects and their metadata.
This handles structural validation of the dataclass itself, not the
frontmatter YAML (which is handled by dev/validators/md.py).
"""

from __future__ import annotations

from typing import List, Dict, Any, TYPE_CHECKING

from dev.core.validators import DataValidator

if TYPE_CHECKING:
    from datetime import date


class MdEntryValidator:
    """
    Validator for MdEntry objects.

    Performs structural validation on MdEntry instances to ensure
    required fields are present and metadata values are valid.
    """

    @staticmethod
    def validate_entry(
        entry_date: date,
        body: List[str],
        metadata: Dict[str, Any],
    ) -> List[str]:
        """
        Validate entry data and return list of issues.

        Args:
            entry_date: The entry's date
            body: The entry's body content lines
            metadata: The entry's metadata dictionary

        Returns:
            List of validation error messages (empty if valid)

        Examples:
            >>> MdEntryValidator.validate_entry(
            ...     date(2024, 1, 15),
            ...     ["Content here"],
            ...     {"word_count": 10, "reading_time": 0.5}
            ... )
            []
            >>> MdEntryValidator.validate_entry(
            ...     None,
            ...     [],
            ...     {"word_count": -5}
            ... )
            ["Missing date", "Empty body content", "Word count cannot be negative"]
        """
        issues: List[str] = []

        # Required fields
        if not entry_date:
            issues.append("Missing date")

        if not body:
            issues.append("Empty body content")

        # Validate word_count
        if "word_count" in metadata:
            wc = DataValidator.normalize_int(metadata["word_count"])
            if wc is not None and wc < 0:
                issues.append("Word count cannot be negative")
            elif wc is None:
                issues.append("Word count must be a number")

        # Validate dates
        if "dates" in metadata:
            for date_item in metadata["dates"]:
                if isinstance(date_item, dict):
                    if "date" not in date_item:
                        issues.append("Date item missing 'date' field")
                    else:
                        date_val = date_item["date"]
                        # Allow '.' as shorthand for entry date
                        if date_val != "." and not DataValidator.validate_date_string(
                            str(date_val)
                        ):
                            issues.append(f"Invalid date format: {date_val}")
                elif isinstance(date_item, str):
                    # Skip '~' (opt-out marker) and don't validate it as a date
                    if date_item != "~":
                        # Extract date part (before any context in parentheses)
                        date_part = date_item.split("(")[0].strip()
                        if not DataValidator.validate_date_string(date_part):
                            issues.append(f"Invalid date format: {date_part}")

        return issues
