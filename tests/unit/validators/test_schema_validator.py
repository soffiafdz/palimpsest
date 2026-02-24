import pytest

from dev.validators.schema import SchemaValidator, SchemaIssue


class TestSchemaValidator:
    """Tests for the SchemaValidator class."""

    @pytest.fixture
    def validator(self):
        """Create a SchemaValidator instance."""
        return SchemaValidator()

    # ========== Enum Provider Tests ==========

    def test_get_valid_reference_types(self, validator):
        """Test that reference types are imported from authoritative source."""
        types = validator.get_valid_reference_types()
        assert isinstance(types, list)
        assert len(types) > 0
        # Verify key types are present
        assert "book" in types
        assert "poem" in types
        assert "website" in types  # Recently added
        assert "other" in types

    def test_get_valid_reference_modes(self, validator):
        """Test that reference modes are imported from authoritative source."""
        modes = validator.get_valid_reference_modes()
        assert isinstance(modes, list)
        assert len(modes) > 0
        # Verify key modes are present
        assert "direct" in modes
        assert "indirect" in modes

    # ========== Field Validator Tests ==========

    def test_validate_reference_mode_valid(self, validator):
        """Test validation of valid reference mode."""
        issue = validator.validate_reference_mode("direct", "test.mode")
        assert issue is None

    def test_validate_reference_mode_invalid(self, validator):
        """Test validation of invalid reference mode."""
        issue = validator.validate_reference_mode("invalid_mode", "test.mode")
        assert isinstance(issue, SchemaIssue)
        assert issue.severity == "error"
        assert "Invalid reference mode" in issue.message
        assert issue.field_path == "test.mode"
        assert issue.actual_value == "invalid_mode"
        assert issue.suggestion is not None

    def test_validate_reference_type_valid(self, validator):
        """Test validation of valid reference type."""
        issue = validator.validate_reference_type("book", "test.type")
        assert issue is None

    def test_validate_reference_type_website(self, validator):
        """Test validation of website reference type (recently added)."""
        issue = validator.validate_reference_type("website", "test.type")
        assert issue is None

    def test_validate_reference_type_invalid(self, validator):
        """Test validation of invalid reference type."""
        issue = validator.validate_reference_type("invalid_type", "test.type")
        assert isinstance(issue, SchemaIssue)
        assert issue.severity == "error"
        assert "Invalid reference type" in issue.message
        assert issue.field_path == "test.type"
        assert issue.actual_value == "invalid_type"
        assert issue.suggestion is not None

    def test_validate_manuscript_status_valid(self, validator):
        """Test validation of valid manuscript status."""
        valid_statuses = ["draft", "revised", "final"]
        for status in valid_statuses:
            issue = validator.validate_manuscript_status(status, "test.status")
            assert issue is None, f"Status '{status}' should be valid"

    def test_validate_manuscript_status_invalid(self, validator):
        """Test validation of invalid manuscript status."""
        issue = validator.validate_manuscript_status("invalid_status", "test.status")
        assert isinstance(issue, SchemaIssue)
        assert issue.severity == "error"
        assert "Invalid manuscript status" in issue.message
        assert issue.field_path == "test.status"
        assert issue.actual_value == "invalid_status"
        assert issue.suggestion is not None

    def test_validate_date_format_valid(self, validator):
        """Test validation of valid date formats."""
        valid_dates = ["2024-01-01", "2024-12-31", "2024-06-15"]
        for date_val in valid_dates:
            issue = validator.validate_date_format(date_val, "test.date")
            assert issue is None, f"Date '{date_val}' should be valid"

    def test_validate_date_format_invalid(self, validator):
        """Test validation of invalid date formats."""
        invalid_dates = ["01-01-2024", "2024/01/01", "January 1, 2024", "not a date"]
        for date_val in invalid_dates:
            issue = validator.validate_date_format(date_val, "test.date")
            assert isinstance(issue, SchemaIssue), f"Date '{date_val}' should be invalid"
            assert issue.severity == "error"
            assert "Invalid date format" in issue.message

    # ========== Complex Structure Validator Tests ==========

    def test_validate_reference_structure_valid(self, validator):
        """Test validation of valid reference structure."""
        reference = {
            "content": "Quote text",
            "mode": "direct",
            "source": {
                "title": "Book Title",
                "type": "book"
            }
        }
        issues = validator.validate_reference_structure(reference, 0)
        assert not issues

    def test_validate_reference_structure_with_website(self, validator):
        """Test validation of reference with website type."""
        reference = {
            "content": "Article content",
            "mode": "indirect",
            "source": {
                "title": "Article Title",
                "type": "website",
                "url": "https://example.com"
            }
        }
        issues = validator.validate_reference_structure(reference, 0)
        assert not issues

    def test_validate_reference_structure_invalid_mode(self, validator):
        """Test validation detects invalid reference mode."""
        reference = {
            "content": "Quote",
            "mode": "invalid_mode"
        }
        issues = validator.validate_reference_structure(reference, 0)
        assert len(issues) == 1
        assert "Invalid reference mode" in issues[0].message

    def test_validate_reference_structure_invalid_type(self, validator):
        """Test validation detects invalid reference type."""
        reference = {
            "content": "Quote",
            "source": {
                "title": "Source",
                "type": "invalid_type"
            }
        }
        issues = validator.validate_reference_structure(reference, 0)
        assert len(issues) == 1
        assert "Invalid reference type" in issues[0].message

    def test_validate_reference_structure_not_dict(self, validator):
        """Test validation detects non-dict reference."""
        reference = "Not a dict"
        issues = validator.validate_reference_structure(reference, 0)
        assert len(issues) == 1
        assert "Reference must be a dict" in issues[0].message

    def test_validate_reference_structure_source_not_dict(self, validator):
        """Test validation detects non-dict source."""
        reference = {
            "content": "Quote",
            "source": "Not a dict"
        }
        issues = validator.validate_reference_structure(reference, 0)
        assert len(issues) == 1
        assert "Source must be a dict" in issues[0].message

    def test_validate_references_schema_valid(self, validator):
        """Test validation of valid references list."""
        references = [
            {"content": "Quote 1", "mode": "direct"},
            {"description": "Desc 2", "mode": "indirect"},
            {"content": "Quote 3", "source": {"title": "Book", "type": "book"}}
        ]
        issues = validator.validate_references_schema(references)
        assert not issues

    def test_validate_references_schema_not_list(self, validator):
        """Test validation detects non-list references."""
        references = {"content": "Not a list"}
        issues = validator.validate_references_schema(references)
        assert len(issues) == 1
        assert "References must be a list" in issues[0].message

    def test_validate_references_schema_multiple_issues(self, validator):
        """Test validation detects multiple issues in references list."""
        references = [
            {"content": "Valid"},
            "Not a dict",
            {"content": "Invalid mode", "mode": "bad_mode"},
            {"content": "Invalid type", "source": {"title": "Source", "type": "bad_type"}}
        ]
        issues = validator.validate_references_schema(references)
        # Should have at least 3 issues (not dict, bad mode, bad type)
        assert len(issues) >= 3
        assert any("must be a dict" in i.message for i in issues)
        assert any("Invalid reference mode" in i.message for i in issues)
        assert any("Invalid reference type" in i.message for i in issues)

    def test_validate_manuscript_schema_valid(self, validator):
        """Test validation of valid manuscript structure."""
        manuscript = {
            "status": "draft",
            "edited": True,
            "themes": ["Theme1", "Theme2"]
        }
        issues = validator.validate_manuscript_schema(manuscript)
        assert not issues

    def test_validate_manuscript_schema_not_dict(self, validator):
        """Test validation detects non-dict manuscript."""
        manuscript = "Not a dict"
        issues = validator.validate_manuscript_schema(manuscript)
        assert len(issues) == 1
        assert "Manuscript must be a dict" in issues[0].message

    def test_validate_manuscript_schema_invalid_status(self, validator):
        """Test validation detects invalid manuscript status."""
        manuscript = {"status": "invalid_status"}
        issues = validator.validate_manuscript_schema(manuscript)
        assert len(issues) == 1
        assert "Invalid manuscript status" in issues[0].message

    def test_validate_manuscript_schema_valid_statuses(self, validator):
        """Test all valid manuscript statuses."""
        valid_statuses = ["draft", "revised", "final"]
        for status in valid_statuses:
            manuscript = {"status": status}
            issues = validator.validate_manuscript_schema(manuscript)
            assert not issues, f"Status '{status}' should be valid"

    # ========== Integration Tests ==========

    def test_enum_values_imported_from_models(self, validator):
        """Test that enum values are actually imported from models (not hardcoded)."""
        # This is more of a code review test - we verify the pattern
        types = validator.get_valid_reference_types()
        modes = validator.get_valid_reference_modes()

        # These should come from ReferenceType and ReferenceMode enums
        # If the enums are updated, these values will automatically update
        assert isinstance(types, list)
        assert isinstance(modes, list)

        # Verify the lists are not empty (would indicate import failure)
        assert len(types) > 0
        assert len(modes) > 0

    def test_schema_issue_dataclass(self):
        """Test SchemaIssue dataclass structure."""
        issue = SchemaIssue(
            field_path="test.field",
            severity="error",
            message="Test message",
            suggestion="Test suggestion",
            actual_value="test_value"
        )
        assert issue.field_path == "test.field"
        assert issue.severity == "error"
        assert issue.message == "Test message"
        assert issue.suggestion == "Test suggestion"
        assert issue.actual_value == "test_value"

    def test_schema_issue_optional_fields(self):
        """Test SchemaIssue with optional fields omitted."""
        issue = SchemaIssue(
            field_path="test.field",
            severity="warning",
            message="Test message"
        )
        assert issue.field_path == "test.field"
        assert issue.severity == "warning"
        assert issue.message == "Test message"
        assert issue.suggestion is None
        assert issue.actual_value is None
