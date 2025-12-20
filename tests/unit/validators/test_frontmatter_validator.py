import pytest
from pathlib import Path
import yaml

from dev.validators.frontmatter import FrontmatterValidator

class TestFrontmatterValidator:
    """Tests for the FrontmatterValidator class."""

    @pytest.fixture
    def validator(self, tmp_path):
        """Create a FrontmatterValidator instance with a temporary directory."""
        return FrontmatterValidator(md_dir=tmp_path)

    def create_md_file(self, path: Path, frontmatter: dict):
        """Helper to create a markdown file with given frontmatter."""
        fm_str = yaml.dump(frontmatter)
        content = f"---\n{fm_str}---\nBody content."
        path.write_text(content, encoding="utf-8")

    def test_validate_people_field_valid(self, validator, tmp_path):
        """Test validation of valid people field formats."""
        file_path = tmp_path / "valid_people.md"
        frontmatter = {
            "people": [
                "Alice",
                "Bob (Robert Smith)",
                "@Charlie",
                "@Dave (David Jones)",
                {"name": "Eve", "full_name": "Eve White"},
                {"alias": "Frank", "name": "Frank Black"}
            ]
        }
        self.create_md_file(file_path, frontmatter)
        
        issues = validator.validate_file(file_path)
        assert not issues

    def test_validate_people_field_invalid(self, validator, tmp_path):
        """Test validation of invalid people field formats."""
        file_path = tmp_path / "invalid_people.md"
        frontmatter = {
            "people": [
                "Bob(Robert)", # Missing space
                "Charlie)", # Unbalanced
                "@Dave(David)", # Missing space in alias
                {"age": 30}, # Missing required field
                123 # Invalid type
            ]
        }
        self.create_md_file(file_path, frontmatter)

        issues = validator.validate_file(file_path)
        assert len(issues) >= 5
        assert any("Missing space" in i.message for i in issues)
        assert any("Unbalanced parenthesis" in i.message for i in issues)
        assert any("missing required field" in i.message for i in issues)
        assert any("Invalid people entry type" in i.message for i in issues)

    def test_validate_people_field_duplicates(self, validator, tmp_path):
        """Test validation detects multiple aliases for same person."""
        file_path = tmp_path / "duplicate_people.md"
        frontmatter = {
            "people": [
                "@Clarabelais (Clara)",
                "@Ari (Clara)",  # Same person, different alias
            ]
        }
        self.create_md_file(file_path, frontmatter)

        issues = validator.validate_file(file_path)
        assert len(issues) >= 1
        # Should be an ERROR for multiple aliases
        assert any(i.severity == "error" for i in issues)
        assert any("Multiple aliases for" in i.message for i in issues)
        assert any("Combine into single entry" in i.suggestion for i in issues)

    def test_validate_people_field_same_person_different_formats(self, validator, tmp_path):
        """Test validation detects same person in different formats (not both aliases)."""
        file_path = tmp_path / "same_person_different_formats.md"
        frontmatter = {
            "people": [
                "Clara",
                "@Clarabelais (Clara)",  # Same person, but one is alias, one is not
            ]
        }
        self.create_md_file(file_path, frontmatter)

        issues = validator.validate_file(file_path)
        assert len(issues) >= 1
        # Should be a WARNING (not error) since they're not both aliases
        assert any(i.severity == "warning" for i in issues)
        assert any("appears multiple times" in i.message for i in issues)

    def test_validate_people_field_no_duplicates_different_people(self, validator, tmp_path):
        """Test validation allows different people."""
        file_path = tmp_path / "different_people.md"
        frontmatter = {
            "people": [
                "Alice",
                "Bob",
                "@Charlie (Charles)",
            ]
        }
        self.create_md_file(file_path, frontmatter)

        issues = validator.validate_file(file_path)
        # Should have no duplicate warnings or errors
        assert not any("appears multiple times" in i.message for i in issues)
        assert not any("Multiple aliases" in i.message for i in issues)

    def test_validate_locations_field_valid(self, validator, tmp_path):
        """Test validation of valid locations field formats."""
        file_path = tmp_path / "valid_locations.md"
        frontmatter = {
            "city": "Paris",
            "locations": ["Eiffel Tower", "Louvre"]
        }
        self.create_md_file(file_path, frontmatter)
        
        issues = validator.validate_file(file_path)
        assert not issues

        # Test nested dict
        file_path_dict = tmp_path / "valid_locations_dict.md"
        frontmatter_dict = {
            "city": ["Paris", "London"],
            "locations": {
                "Paris": ["Eiffel Tower"],
                "London": "Big Ben"
            }
        }
        self.create_md_file(file_path_dict, frontmatter_dict)
        issues = validator.validate_file(file_path_dict)
        assert not issues

    def test_validate_locations_field_invalid(self, validator, tmp_path):
        """Test validation of invalid locations field formats."""
        file_path = tmp_path / "invalid_locations.md"
        # Flat list without city
        frontmatter = {
            "locations": ["Somewhere"]
        }
        self.create_md_file(file_path, frontmatter)
        
        issues = validator.validate_file(file_path)
        assert any("requires city field" in i.message for i in issues)

    def test_validate_dates_field_valid(self, validator, tmp_path):
        """Test validation of valid dates field formats."""
        file_path = tmp_path / "valid_dates.md"
        frontmatter = {
            "dates": [
                "2024-01-01",
                "2024-02-01 (Context)",
                {"date": "2024-03-01", "context": "Meeting"},
                "~"
            ]
        }
        self.create_md_file(file_path, frontmatter)
        
        issues = validator.validate_file(file_path)
        assert not issues

    def test_validate_dates_field_invalid(self, validator, tmp_path):
        """Test validation of invalid dates field formats."""
        file_path = tmp_path / "invalid_dates.md"
        frontmatter = {
            "dates": [
                "01-01-2024", # Wrong format
                "2024-01-01 (Unclosed",
                {"context": "Missing date key"},
                123 # Invalid type
            ]
        }
        self.create_md_file(file_path, frontmatter)
        
        issues = validator.validate_file(file_path)
        assert len(issues) >= 4
        assert any("Invalid date format" in i.message for i in issues)
        assert any("Unclosed parenthesis" in i.message for i in issues)
        assert any("missing required 'date' key" in i.message for i in issues)
        assert any("Invalid date entry type" in i.message for i in issues)

    def test_validate_references_field_valid(self, validator, tmp_path):
        """Test validation of valid references field formats."""
        file_path = tmp_path / "valid_refs.md"
        frontmatter = {
            "references": [
                {"content": "Quote"},
                {"description": "Desc", "mode": "indirect"},
                {"content": "Quote", "source": {"title": "Book", "type": "book"}}
            ]
        }
        self.create_md_file(file_path, frontmatter)
        
        issues = validator.validate_file(file_path)
        assert not issues

    def test_validate_references_field_invalid(self, validator, tmp_path):
        """Test validation of invalid references field formats."""
        file_path = tmp_path / "invalid_refs.md"
        frontmatter = {
            "references": [
                "Not a dict",
                {"mode": "invalid"}, # Missing content/desc and invalid mode
                {"content": "Quote", "source": {"title": "Book"}} # Missing source type
            ]
        }
        self.create_md_file(file_path, frontmatter)
        
        issues = validator.validate_file(file_path)
        assert any("must be a dict" in i.message for i in issues)
        assert any("missing both 'content' and 'description'" in i.message for i in issues)
        assert any("Invalid reference mode" in i.message for i in issues)
        assert any("source missing 'type'" in i.message for i in issues)

    def test_validate_manuscript_field_valid(self, validator, tmp_path):
        """Test validation of valid manuscript field formats."""
        file_path = tmp_path / "valid_manuscript.md"
        frontmatter = {
            "manuscript": {
                "status": "quote",
                "edited": True,
                "themes": ["Theme1"]
            }
        }
        self.create_md_file(file_path, frontmatter)

        issues = validator.validate_file(file_path)
        assert not issues

    def test_validate_manuscript_field_invalid(self, validator, tmp_path):
        """Test validation of invalid manuscript field formats."""
        file_path = tmp_path / "invalid_manuscript.md"
        frontmatter = {
            "manuscript": {
                "status": "unknown_status",
                "edited": "not_boolean",
                "themes": "not_a_list"
            }
        }
        self.create_md_file(file_path, frontmatter)
        
        issues = validator.validate_file(file_path)
        assert any("Invalid manuscript status" in i.message for i in issues)
        assert any("edited should be boolean" in i.message for i in issues)
        assert any("themes should be a list" in i.message for i in issues)
