import pytest
from pathlib import Path
from unittest.mock import MagicMock
import yaml

from dev.validators.md import MarkdownValidator, MarkdownIssue, MarkdownValidationReport

class TestMarkdownValidator:
    """Tests for the MarkdownValidator class."""

    @pytest.fixture
    def validator(self, tmp_path):
        """Create a MarkdownValidator instance with a temporary directory."""
        return MarkdownValidator(md_dir=tmp_path)

    def test_validate_valid_file(self, validator, tmp_path):
        """Test validation of a perfectly valid markdown file."""
        file_path = tmp_path / "valid.md"
        content = """---
date: 2024-01-01
word_count: 100
reading_time: 1
---
# Valid Entry

This is a valid entry content.
"""
        file_path.write_text(content, encoding="utf-8")
        
        issues = validator.validate_file(file_path)
        assert not issues
        assert validator.report.files_checked == 1
        assert validator.report.total_errors == 0
        assert validator.report.total_warnings == 0

    def test_validate_missing_required_field(self, validator, tmp_path):
        """Test validation detects missing required 'date' field."""
        file_path = tmp_path / "missing_date.md"
        content = """---
word_count: 100
---
Body content.
"""
        file_path.write_text(content, encoding="utf-8")
        
        issues = validator.validate_file(file_path)
        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert "Required field 'date' missing" in issues[0].message

    def test_validate_invalid_yaml(self, validator, tmp_path):
        """Test validation detects invalid YAML syntax."""
        file_path = tmp_path / "invalid_yaml.md"
        content = """---
date: 2024-01-01
invalid_yaml: [unclosed list
---
Body content.
"""
        file_path.write_text(content, encoding="utf-8")
        
        issues = validator.validate_file(file_path)
        assert len(issues) > 0
        assert issues[0].severity == "error"
        assert "Invalid YAML syntax" in issues[0].message

    def test_validate_invalid_date_format(self, validator, tmp_path):
        """Test validation detects invalid date format."""
        file_path = tmp_path / "invalid_date.md"
        content = """---
date: "January 1st, 2024"
---
Body content.
"""
        file_path.write_text(content, encoding="utf-8")
        
        issues = validator.validate_file(file_path)
        assert any("Invalid date format" in i.message for i in issues)

    def test_validate_unexpected_type(self, validator, tmp_path):
        """Test validation detects field with incorrect type."""
        file_path = tmp_path / "wrong_type.md"
        content = """---
date: 2024-01-01
word_count: "one hundred"
---
Body content.
"""
        file_path.write_text(content, encoding="utf-8")
        
        issues = validator.validate_file(file_path)
        assert any("unexpected type" in i.message for i in issues)

    def test_validate_unknown_field(self, validator, tmp_path):
        """Test validation warns about unknown fields."""
        file_path = tmp_path / "unknown_field.md"
        content = """---
date: 2024-01-01
custom_field: "value"
---
Body content.
"""
        file_path.write_text(content, encoding="utf-8")
        
        issues = validator.validate_file(file_path)
        assert any("Unknown fields" in i.message for i in issues)
        assert any(i.severity == "warning" for i in issues)

    def test_validate_empty_body(self, validator, tmp_path):
        """Test validation warns about empty body."""
        file_path = tmp_path / "empty_body.md"
        content = """---
date: 2024-01-01
---
"""
        file_path.write_text(content, encoding="utf-8")
        
        issues = validator.validate_file(file_path)
        assert any("Entry body is empty" in i.message for i in issues)

    def test_validate_placeholder_text(self, validator, tmp_path):
        """Test validation warns about placeholder text."""
        file_path = tmp_path / "placeholder.md"
        content = """---
date: 2024-01-01
---
Here is a TODO for later.
"""
        file_path.write_text(content, encoding="utf-8")
        
        issues = validator.validate_file(file_path)
        assert any("Placeholder text found" in i.message for i in issues)

    def test_validate_links_valid(self, validator, tmp_path):
        """Test validation of valid internal links."""
        # Create linked file
        target_file = tmp_path / "target.md"
        target_file.write_text("Target content", encoding="utf-8")
        
        source_file = tmp_path / "source.md"
        source_file.write_text("[Link to target](target.md)", encoding="utf-8")
        
        issues = validator.validate_links()
        assert not issues

    def test_validate_links_broken(self, validator, tmp_path):
        """Test validation detects broken internal links."""
        source_file = tmp_path / "broken_link.md"
        source_file.write_text("[Broken Link](non_existent.md)", encoding="utf-8")
        
        issues = validator.validate_links()
        assert len(issues) == 1
        assert "Broken link" in issues[0].message
        assert "non_existent.md" in issues[0].message

    def test_validate_manuscript_status(self, validator, tmp_path):
        """Test validation of manuscript status."""
        file_path = tmp_path / "manuscript.md"
        content = """---
date: 2024-01-01
manuscript:
  status: invalid_status
---
Body.
"""
        file_path.write_text(content, encoding="utf-8")
        
        issues = validator.validate_file(file_path)
        assert any("Invalid manuscript status" in i.message for i in issues)

    def test_validate_reference_mode(self, validator, tmp_path):
        """Test validation of reference mode."""
        file_path = tmp_path / "refs.md"
        content = """---
date: 2024-01-01
references:
  - content: "Quote"
    mode: invalid_mode
---
Body.
"""
        file_path.write_text(content, encoding="utf-8")
        
        issues = validator.validate_file(file_path)
        assert any("Invalid mode" in i.message for i in issues)
