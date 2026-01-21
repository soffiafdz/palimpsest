"""
test_validators.py
------------------
Unit tests for dev.core.validators module.

Tests the DataValidator class which provides type-safe conversion
and validation functions used across the project.

Target Coverage: 95%+
"""
import pytest
from datetime import date, datetime
from dev.core.validators import DataValidator
from dev.core.exceptions import ValidationError


class TestValidateRequiredFields:
    """Test validate_required_fields method."""

    def test_all_required_fields_present(self):
        """Test validation passes when all fields present."""
        data = {"name": "Alice", "date": "2024-01-15"}
        # Should not raise
        DataValidator.validate_required_fields(data, ["name", "date"])

    def test_missing_field_raises_error(self):
        """Test validation fails when field is missing."""
        data = {"name": "Alice"}
        with pytest.raises(ValidationError) as exc_info:
            DataValidator.validate_required_fields(data, ["name", "date"])
        assert "date" in str(exc_info.value)

    def test_none_value_raises_error(self):
        """Test validation fails when field is None."""
        data = {"name": "Alice", "date": None}
        with pytest.raises(ValidationError) as exc_info:
            DataValidator.validate_required_fields(data, ["name", "date"])
        assert "date" in str(exc_info.value)

    def test_empty_string_raises_error_by_default(self):
        """Test validation fails for empty string when allow_falsy=False."""
        data = {"name": ""}
        with pytest.raises(ValidationError):
            DataValidator.validate_required_fields(data, ["name"], allow_falsy=False)

    def test_zero_raises_error_by_default(self):
        """Test validation fails for 0 when allow_falsy=False."""
        data = {"count": 0}
        with pytest.raises(ValidationError):
            DataValidator.validate_required_fields(data, ["count"], allow_falsy=False)

    def test_allow_falsy_accepts_zero(self):
        """Test validation passes for 0 when allow_falsy=True."""
        data = {"count": 0}
        # Should not raise
        DataValidator.validate_required_fields(data, ["count"], allow_falsy=True)

    def test_allow_falsy_accepts_empty_string(self):
        """Test validation passes for empty string when allow_falsy=True."""
        data = {"name": ""}
        # Should not raise
        DataValidator.validate_required_fields(data, ["name"], allow_falsy=True)

    def test_allow_falsy_accepts_false(self):
        """Test validation passes for False when allow_falsy=True."""
        data = {"flag": False}
        # Should not raise
        DataValidator.validate_required_fields(data, ["flag"], allow_falsy=True)

    def test_multiple_missing_fields(self):
        """Test error message includes all missing fields."""
        data = {"age": 25}
        with pytest.raises(ValidationError) as exc_info:
            DataValidator.validate_required_fields(data, ["name", "email", "date"])
        error_msg = str(exc_info.value)
        assert "name" in error_msg
        assert "email" in error_msg
        assert "date" in error_msg


class TestNormalizeDate:
    """Test normalize_date method."""

    def test_date_object_returned_as_is(self):
        """Test date object is returned unchanged."""
        test_date = date(2024, 1, 15)
        result = DataValidator.normalize_date(test_date)
        assert result == test_date
        assert isinstance(result, date)

    def test_datetime_converted_to_date(self):
        """Test datetime is converted to date."""
        test_datetime = datetime(2024, 1, 15, 10, 30, 45)
        result = DataValidator.normalize_date(test_datetime)
        assert result == date(2024, 1, 15)
        assert isinstance(result, date)

    def test_valid_iso_string_parsed(self):
        """Test valid ISO format string is parsed."""
        result = DataValidator.normalize_date("2024-01-15")
        assert result == date(2024, 1, 15)

    def test_string_with_whitespace_parsed(self):
        """Test string with whitespace is trimmed and parsed."""
        result = DataValidator.normalize_date("  2024-01-15  ")
        assert result == date(2024, 1, 15)

    def test_invalid_string_returns_none(self):
        """Test invalid date string returns None."""
        assert DataValidator.normalize_date("invalid") is None
        assert DataValidator.normalize_date("2024-13-01") is None  # Invalid month
        assert DataValidator.normalize_date("not-a-date") is None

    def test_none_returns_none(self):
        """Test None input returns None."""
        assert DataValidator.normalize_date(None) is None

    def test_empty_string_returns_none(self):
        """Test empty string returns None."""
        assert DataValidator.normalize_date("") is None
        assert DataValidator.normalize_date("   ") is None

    def test_wrong_format_returns_none(self):
        """Test non-ISO format returns None."""
        assert DataValidator.normalize_date("01/15/2024") is None  # US format
        assert DataValidator.normalize_date("15-01-2024") is None  # European format


class TestNormalizeString:
    """Test normalize_string method."""

    def test_strips_whitespace(self):
        """Test leading/trailing whitespace is removed."""
        assert DataValidator.normalize_string("  hello  ") == "hello"
        assert DataValidator.normalize_string("\thello\n") == "hello"

    def test_empty_string_returns_none(self):
        """Test empty string returns None."""
        assert DataValidator.normalize_string("") is None
        assert DataValidator.normalize_string("   ") is None
        assert DataValidator.normalize_string("\t\n") is None

    def test_none_returns_none(self):
        """Test None input returns None."""
        assert DataValidator.normalize_string(None) is None

    def test_converts_non_string_to_string(self):
        """Test non-string values are converted."""
        assert DataValidator.normalize_string(123) == "123"
        assert DataValidator.normalize_string(45.67) == "45.67"

    def test_preserves_internal_whitespace(self):
        """Test internal whitespace is preserved."""
        assert DataValidator.normalize_string("  hello world  ") == "hello world"

    def test_unicode_strings(self):
        """Test unicode strings are handled correctly."""
        assert DataValidator.normalize_string("  café  ") == "café"
        assert DataValidator.normalize_string("  日本語  ") == "日本語"


class TestNormalizeInt:
    """Test normalize_int method."""

    def test_integer_returned_as_is(self):
        """Test integer input is returned unchanged."""
        assert DataValidator.normalize_int(42) == 42
        assert DataValidator.normalize_int(-10) == -10
        assert DataValidator.normalize_int(0) == 0

    def test_numeric_string_converted(self):
        """Test numeric string is converted to int."""
        assert DataValidator.normalize_int("42") == 42
        assert DataValidator.normalize_int("-10") == -10
        assert DataValidator.normalize_int("0") == 0

    def test_float_converted_to_int(self):
        """Test float is converted to int (truncated)."""
        assert DataValidator.normalize_int(3.14) == 3
        assert DataValidator.normalize_int(9.99) == 9

    def test_invalid_string_returns_none(self):
        """Test non-numeric string returns None."""
        assert DataValidator.normalize_int("not a number") is None
        assert DataValidator.normalize_int("12.34.56") is None

    def test_none_returns_none(self):
        """Test None input returns None."""
        assert DataValidator.normalize_int(None) is None

    def test_empty_string_returns_none(self):
        """Test empty string returns None."""
        assert DataValidator.normalize_int("") is None
        assert DataValidator.normalize_int(" ") is None


class TestNormalizeFloat:
    """Test normalize_float method."""

    def test_float_returned_as_is(self):
        """Test float input is returned unchanged."""
        assert DataValidator.normalize_float(3.14) == 3.14
        assert DataValidator.normalize_float(-2.5) == -2.5
        assert DataValidator.normalize_float(0.0) == 0.0

    def test_integer_converted_to_float(self):
        """Test integer is converted to float."""
        assert DataValidator.normalize_float(42) == 42.0
        assert isinstance(DataValidator.normalize_float(42), float)

    def test_numeric_string_converted(self):
        """Test numeric string is converted to float."""
        assert DataValidator.normalize_float("3.14") == 3.14
        assert DataValidator.normalize_float("-2.5") == -2.5
        assert DataValidator.normalize_float("42") == 42.0

    def test_invalid_string_returns_none(self):
        """Test non-numeric string returns None."""
        assert DataValidator.normalize_float("not a number") is None
        assert DataValidator.normalize_float("12.34.56") is None

    def test_none_returns_none(self):
        """Test None input returns None."""
        assert DataValidator.normalize_float(None) is None

    def test_empty_string_returns_none(self):
        """Test empty string returns None."""
        assert DataValidator.normalize_float("") is None
        assert DataValidator.normalize_float(" ") is None


class TestNormalizeBool:
    """Test normalize_bool method."""

    def test_bool_returned_as_is(self):
        """Test boolean input is returned unchanged."""
        assert DataValidator.normalize_bool(True) is True
        assert DataValidator.normalize_bool(False) is False

    def test_integer_zero_is_false(self):
        """Test 0 converts to False."""
        assert DataValidator.normalize_bool(0) is False

    def test_integer_one_is_true(self):
        """Test 1 converts to True."""
        assert DataValidator.normalize_bool(1) is True

    def test_other_integers_raise_error(self):
        """Test integers other than 0 or 1 raise ValidationError."""
        with pytest.raises(ValidationError):
            DataValidator.normalize_bool(2)
        with pytest.raises(ValidationError):
            DataValidator.normalize_bool(-1)

    def test_float_zero_is_false(self):
        """Test 0.0 converts to False."""
        assert DataValidator.normalize_bool(0.0) is False

    def test_float_one_is_true(self):
        """Test 1.0 converts to True."""
        assert DataValidator.normalize_bool(1.0) is True

    def test_other_floats_raise_error(self):
        """Test floats other than 0.0 or 1.0 raise ValidationError."""
        with pytest.raises(ValidationError):
            DataValidator.normalize_bool(2.5)

    def test_string_true_variants(self):
        """Test various true string values."""
        for value in ["true", "True", "TRUE", "yes", "Yes", "on", "1"]:
            assert DataValidator.normalize_bool(value) is True

    def test_string_false_variants(self):
        """Test various false string values."""
        for value in ["false", "False", "FALSE", "no", "No", "off", "0"]:
            assert DataValidator.normalize_bool(value) is False

    def test_string_with_whitespace(self):
        """Test strings with whitespace are trimmed."""
        assert DataValidator.normalize_bool("  true  ") is True
        assert DataValidator.normalize_bool("  false  ") is False

    def test_invalid_string_raises_error(self):
        """Test invalid string raises ValidationError."""
        with pytest.raises(ValidationError):
            DataValidator.normalize_bool("maybe")
        with pytest.raises(ValidationError):
            DataValidator.normalize_bool("invalid")

    def test_none_returns_none(self):
        """Test None input returns None."""
        assert DataValidator.normalize_bool(None) is None


class TestExtractNumber:
    """Test extract_number method."""

    def test_integer_returned_as_float(self):
        """Test integer input is converted to float."""
        result = DataValidator.extract_number(42)
        assert result == 42.0
        assert isinstance(result, float)

    def test_float_returned_as_is(self):
        """Test float input is returned unchanged."""
        assert DataValidator.extract_number(3.14) == 3.14

    def test_extract_from_string(self):
        """Test extracting number from string."""
        assert DataValidator.extract_number("150 words") == 150.0
        assert DataValidator.extract_number("Price: $45.99") == 45.99

    def test_extract_negative_number(self):
        """Test extracting negative number."""
        assert DataValidator.extract_number("-2.5 degrees") == -2.5
        assert DataValidator.extract_number("Temperature: -10C") == -10.0

    def test_extract_first_number(self):
        """Test only first number is extracted."""
        assert DataValidator.extract_number("10 out of 20") == 10.0

    def test_no_number_returns_zero(self):
        """Test string without number returns 0.0."""
        assert DataValidator.extract_number("no numbers here") == 0.0

    def test_none_returns_zero(self):
        """Test None input returns 0.0."""
        assert DataValidator.extract_number(None) == 0.0


class TestValidateDateString:
    """Test validate_date_string method."""

    def test_valid_iso_format(self):
        """Test valid ISO format returns True."""
        assert DataValidator.validate_date_string("2024-01-15") is True
        assert DataValidator.validate_date_string("2023-12-31") is True

    def test_invalid_format_returns_false(self):
        """Test invalid format returns False."""
        assert DataValidator.validate_date_string("01/15/2024") is False  # US format
        assert DataValidator.validate_date_string("15-01-2024") is False  # European format
        assert DataValidator.validate_date_string("invalid") is False

    def test_invalid_date_returns_false(self):
        """Test invalid date values return False."""
        assert DataValidator.validate_date_string("2024-13-01") is False  # Invalid month
        assert DataValidator.validate_date_string("2024-02-30") is False  # Invalid day

    def test_none_returns_false(self):
        """Test None input returns False."""
        assert DataValidator.validate_date_string(None) is False  # type: ignore


class TestNormalizeEnum:
    """Test normalize_enum method."""

    def test_enum_instance_returned_as_is(self):
        """Test enum instance is returned unchanged."""
        from dev.database.models import ReferenceMode
        mode = ReferenceMode.DIRECT
        result = DataValidator.normalize_enum(mode, ReferenceMode, "mode")
        assert result == ReferenceMode.DIRECT

    def test_valid_string_converted_to_enum(self):
        """Test valid string is converted to enum."""
        from dev.database.models import ReferenceMode
        result = DataValidator.normalize_enum("direct", ReferenceMode, "mode")
        assert result == ReferenceMode.DIRECT

    def test_case_insensitive_string(self):
        """Test string matching is case-insensitive."""
        from dev.database.models import ReferenceMode
        result = DataValidator.normalize_enum("DIRECT", ReferenceMode, "mode")
        assert result == ReferenceMode.DIRECT

    def test_invalid_string_raises_error(self):
        """Test invalid string raises ValidationError."""
        from dev.database.models import ReferenceMode
        with pytest.raises(ValidationError) as exc_info:
            DataValidator.normalize_enum("invalid", ReferenceMode, "mode")
        assert "Invalid mode" in str(exc_info.value)
        assert "direct" in str(exc_info.value).lower()  # Should show valid options

    def test_none_returns_none(self):
        """Test None input returns None."""
        from dev.database.models import ReferenceMode
        assert DataValidator.normalize_enum(None, ReferenceMode, "mode") is None

    def test_empty_string_returns_none(self):
        """Test empty string returns None."""
        from dev.database.models import ReferenceMode
        assert DataValidator.normalize_enum("", ReferenceMode, "mode") is None
        assert DataValidator.normalize_enum("  ", ReferenceMode, "mode") is None


