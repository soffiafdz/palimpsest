#!/usr/bin/env python3
"""
test_validate.py
----------------
Unit tests for dev.curation.validate module.

Tests validation functions for per-year curation files, including:
- YAML loading and normalization
- Entry state resolution (canonical, skip, same_as)
- Per-file validation (format, fields, references)
- Cross-year consistency checks (conflicts, suggestions)
- Circular reference detection

Target Coverage: 95%+
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from typing import Dict, Any

# --- Third-party imports ---
import pytest
import yaml

# --- Local imports ---
from dev.curation.validate import (
    load_yaml,
    normalize_name,
    is_all_null_canonical,
    resolve_people_entry,
    resolve_locations_entry,
    get_effective_people_canonical,
    get_effective_location_canonical,
    validate_people_file,
    validate_locations_file,
    check_people_consistency,
    check_locations_consistency,
)
from dev.curation.models import ValidationResult, ConsistencyResult


# =============================================================================
# Utility Function Tests
# =============================================================================

class TestLoadYaml:
    """Test load_yaml function."""

    def test_load_valid_yaml(self, tmp_dir):
        """Test loading valid YAML file."""
        yaml_file = tmp_dir / "test.yaml"
        data = {"key": "value", "number": 42}
        yaml_file.write_text(yaml.dump(data))

        result = load_yaml(yaml_file)
        assert result == data

    def test_load_invalid_yaml(self, tmp_dir):
        """Test loading invalid YAML returns None."""
        yaml_file = tmp_dir / "invalid.yaml"
        yaml_file.write_text("invalid: yaml: content: [")

        result = load_yaml(yaml_file)
        assert result is None

    def test_load_nonexistent_file(self, tmp_dir):
        """Test loading nonexistent file returns None."""
        yaml_file = tmp_dir / "nonexistent.yaml"

        result = load_yaml(yaml_file)
        assert result is None

    def test_load_empty_yaml(self, tmp_dir):
        """Test loading empty YAML file."""
        yaml_file = tmp_dir / "empty.yaml"
        yaml_file.write_text("")

        result = load_yaml(yaml_file)
        assert result is None


class TestNormalizeName:
    """Test normalize_name function."""

    def test_lowercase_conversion(self):
        """Test converts to lowercase."""
        assert normalize_name("Alice") == "alice"
        assert normalize_name("ALICE") == "alice"
        assert normalize_name("AlIcE") == "alice"

    def test_strip_whitespace(self):
        """Test strips leading/trailing whitespace."""
        assert normalize_name("  Alice  ") == "alice"
        assert normalize_name("\tAlice\n") == "alice"

    def test_strip_accents(self):
        """Test removes accents."""
        assert normalize_name("María") == "maria"
        assert normalize_name("José") == "jose"
        assert normalize_name("Café") == "cafe"

    def test_normalize_whitespace(self):
        """Test normalizes internal whitespace."""
        assert normalize_name("María  José") == "maria jose"
        assert normalize_name("María-José") == "maria jose"
        assert normalize_name("María - José") == "maria jose"

    def test_combined_normalization(self):
        """Test full normalization pipeline."""
        assert normalize_name("  María-José García  ") == "maria jose garcia"
        assert normalize_name("Café de l'Époque") == "cafe de l'epoque"


class TestIsAllNullCanonical:
    """Test is_all_null_canonical function."""

    def test_all_null_values(self):
        """Test dict with all null values."""
        canonical = {"name": None, "lastname": None, "alias": None}
        assert is_all_null_canonical(canonical) is True

    def test_some_null_values(self):
        """Test dict with some null values."""
        canonical = {"name": "Alice", "lastname": None, "alias": None}
        assert is_all_null_canonical(canonical) is False

    def test_no_null_values(self):
        """Test dict with no null values."""
        canonical = {"name": "Alice", "lastname": "Smith", "alias": "Al"}
        assert is_all_null_canonical(canonical) is False

    def test_empty_dict(self):
        """Test empty dict."""
        assert is_all_null_canonical({}) is True

    def test_non_dict(self):
        """Test non-dict returns False."""
        assert is_all_null_canonical("not a dict") is False
        assert is_all_null_canonical(None) is False
        assert is_all_null_canonical([None, None]) is False


# =============================================================================
# Entry Resolution Tests
# =============================================================================

class TestResolvePeopleEntry:
    """Test resolve_people_entry function."""

    def test_skip_explicit(self):
        """Test explicit skip entry."""
        entry = {"skip": True}
        assert resolve_people_entry("Alice", entry) == "skip"

    def test_skip_no_canonical_key(self):
        """Test entry without canonical key is skipped."""
        entry = {"dates": ["2024-01-15"]}
        assert resolve_people_entry("Alice", entry) == "skip"

    def test_self_entry(self):
        """Test self (author) entry."""
        entry = {"self": True, "canonical": {"name": None, "lastname": None, "alias": None}}
        assert resolve_people_entry("Sofia", entry) == "self"

    def test_same_as_entry(self):
        """Test same_as reference."""
        entry = {"same_as": "Alice"}
        assert resolve_people_entry("Alicia", entry) == "same_as"

    def test_canonical_entry(self):
        """Test canonical entry."""
        entry = {"canonical": {"name": "Alice", "lastname": None, "alias": None}}
        assert resolve_people_entry("Alice", entry) == "canonical"

    def test_canonical_all_null(self):
        """Test canonical with all null values."""
        entry = {"canonical": {"name": None, "lastname": None, "alias": None}}
        assert resolve_people_entry("Alice", entry) == "canonical"


class TestResolveLocationsEntry:
    """Test resolve_locations_entry function."""

    def test_skip_explicit(self):
        """Test explicit skip entry."""
        entry = {"skip": True}
        assert resolve_locations_entry("Cafe", entry) == "skip"

    def test_skip_no_canonical_key(self):
        """Test entry without canonical key is skipped."""
        entry = {"dates": ["2024-01-15"]}
        assert resolve_locations_entry("Cafe", entry) == "skip"

    def test_same_as_entry(self):
        """Test same_as reference."""
        entry = {"same_as": "Coffee Shop"}
        assert resolve_locations_entry("Cafe", entry) == "same_as"

    def test_canonical_entry(self):
        """Test canonical entry."""
        entry = {"canonical": "Coffee Shop"}
        assert resolve_locations_entry("Cafe", entry) == "canonical"

    def test_canonical_null(self):
        """Test canonical with null value."""
        entry = {"canonical": None}
        assert resolve_locations_entry("Cafe", entry) == "canonical"


class TestGetEffectivePeopleCanonical:
    """Test get_effective_people_canonical function."""

    def test_no_canonical_key(self):
        """Test entry without canonical key returns None."""
        entry = {"dates": ["2024-01-15"]}
        result = get_effective_people_canonical("Alice", entry)
        assert result is None

    def test_canonical_is_none(self):
        """Test canonical: null returns None."""
        entry = {"canonical": None}
        result = get_effective_people_canonical("Alice", entry)
        assert result is None

    def test_canonical_not_dict(self):
        """Test canonical that's not a dict returns None."""
        entry = {"canonical": "invalid"}
        result = get_effective_people_canonical("Alice", entry)
        assert result is None

    def test_canonical_all_null_convention(self):
        """Test all-null canonical convention: name = key."""
        entry = {"canonical": {"name": None, "lastname": None, "alias": None}}
        result = get_effective_people_canonical("Alice", entry)
        assert result == {"name": "Alice", "lastname": None, "alias": None}

    def test_canonical_with_values(self):
        """Test canonical with actual values."""
        entry = {"canonical": {"name": "Alice", "lastname": "Smith", "alias": "Al"}}
        result = get_effective_people_canonical("Alice", entry)
        assert result == {"name": "Alice", "lastname": "Smith", "alias": "Al"}

    def test_canonical_partial_null(self):
        """Test canonical with some null values (not convention)."""
        entry = {"canonical": {"name": "Alice", "lastname": None, "alias": None}}
        result = get_effective_people_canonical("Alice", entry)
        assert result == {"name": "Alice", "lastname": None, "alias": None}


class TestGetEffectiveLocationCanonical:
    """Test get_effective_location_canonical function."""

    def test_no_canonical_key(self):
        """Test entry without canonical key returns None."""
        entry = {"dates": ["2024-01-15"]}
        result = get_effective_location_canonical("Cafe", entry)
        assert result is None

    def test_canonical_null_convention(self):
        """Test canonical: null convention: canonical = key."""
        entry = {"canonical": None}
        result = get_effective_location_canonical("Cafe", entry)
        assert result == "Cafe"

    def test_canonical_with_value(self):
        """Test canonical with actual value."""
        entry = {"canonical": "Coffee Shop"}
        result = get_effective_location_canonical("Cafe", entry)
        assert result == "Coffee Shop"


# =============================================================================
# Per-File Validation Tests
# =============================================================================

class TestValidatePeopleFile:
    """Test validate_people_file function."""

    def create_people_file(self, tmp_dir: Path, data: Dict[str, Any]) -> Path:
        """Helper to create a people curation file."""
        file_path = tmp_dir / "2024_people_curation.yaml"
        file_path.write_text(yaml.dump(data))
        return file_path

    def test_valid_people_file(self, tmp_dir):
        """Test validating a valid people file."""
        data = {
            "Alice": {
                "canonical": {"name": "Alice", "lastname": "Smith", "alias": None},
                "dates": ["2024-01-15"],
            },
            "Bob": {
                "canonical": {"name": None, "lastname": None, "alias": None},
                "dates": ["2024-01-16"],
            },
        }
        file_path = self.create_people_file(tmp_dir, data)

        result = validate_people_file(file_path)
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_invalid_yaml(self, tmp_dir):
        """Test invalid YAML file."""
        file_path = tmp_dir / "2024_people_curation.yaml"
        file_path.write_text("invalid: yaml: [")

        result = validate_people_file(file_path)
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "Failed to load" in result.errors[0]

    def test_invalid_entry_format(self, tmp_dir):
        """Test entry that's not a dict."""
        data = {"Alice": "not a dict"}
        file_path = self.create_people_file(tmp_dir, data)

        result = validate_people_file(file_path)
        assert result.is_valid is False
        assert any("Invalid entry format" in err for err in result.errors)

    def test_missing_canonical_name(self, tmp_dir):
        """Test canonical without name field."""
        data = {
            "Alice": {
                "canonical": {"lastname": "Smith", "alias": None},
                "dates": ["2024-01-15"],
            }
        }
        file_path = self.create_people_file(tmp_dir, data)

        result = validate_people_file(file_path)
        assert result.is_valid is False
        assert any("canonical.name is required" in err for err in result.errors)

    def test_skip_entry_no_validation(self, tmp_dir):
        """Test skip entry doesn't trigger validation."""
        data = {"Alice": {"skip": True}}
        file_path = self.create_people_file(tmp_dir, data)

        result = validate_people_file(file_path)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_self_entry_no_validation(self, tmp_dir):
        """Test self entry doesn't trigger validation."""
        data = {"Sofia": {"self": True}}
        file_path = self.create_people_file(tmp_dir, data)

        result = validate_people_file(file_path)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_same_as_valid_reference(self, tmp_dir):
        """Test same_as references existing entry."""
        data = {
            "Alice": {
                "canonical": {"name": "Alice", "lastname": None, "alias": None},
                "dates": ["2024-01-15"],
            },
            "Alicia": {"same_as": "Alice", "dates": ["2024-01-16"]},
        }
        file_path = self.create_people_file(tmp_dir, data)

        result = validate_people_file(file_path)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_same_as_invalid_reference(self, tmp_dir):
        """Test same_as references non-existent entry."""
        data = {"Alicia": {"same_as": "NonExistent", "dates": ["2024-01-15"]}}
        file_path = self.create_people_file(tmp_dir, data)

        result = validate_people_file(file_path)
        assert result.is_valid is False
        assert any("same_as references non-existent entry" in err for err in result.errors)

    def test_circular_same_as_reference(self, tmp_dir):
        """Test circular same_as chain detection."""
        data = {
            "Alice": {"same_as": "Bob"},
            "Bob": {"same_as": "Charlie"},
            "Charlie": {"same_as": "Alice"},
        }
        file_path = self.create_people_file(tmp_dir, data)

        result = validate_people_file(file_path)
        assert result.is_valid is False
        assert any("Circular same_as reference" in err for err in result.errors)

    def test_missing_dates_warning(self, tmp_dir):
        """Test warning for missing dates."""
        data = {
            "Alice": {"canonical": {"name": "Alice", "lastname": None, "alias": None}}
        }
        file_path = self.create_people_file(tmp_dir, data)

        result = validate_people_file(file_path)
        assert result.is_valid is True
        assert len(result.warnings) == 1
        assert "No dates listed" in result.warnings[0]

    def test_multi_person_entry_valid(self, tmp_dir):
        """Test multi-person entry (list of canonicals)."""
        data = {
            "Alice & Bob": {
                "canonical": [
                    {"name": "Alice", "lastname": None, "alias": None},
                    {"name": "Bob", "lastname": None, "alias": None},
                ],
                "dates": ["2024-01-15"],
            }
        }
        file_path = self.create_people_file(tmp_dir, data)

        result = validate_people_file(file_path)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_multi_person_entry_invalid(self, tmp_dir):
        """Test multi-person entry with missing names."""
        data = {
            "Alice & Bob": {
                "canonical": [
                    {"name": "Alice", "lastname": None, "alias": None},
                    {"lastname": "Smith"},  # Missing name
                ],
                "dates": ["2024-01-15"],
            }
        }
        file_path = self.create_people_file(tmp_dir, data)

        result = validate_people_file(file_path)
        assert result.is_valid is False
        assert any("canonical[1].name is required" in err for err in result.errors)

    def test_multi_person_entry_not_dict(self, tmp_dir):
        """Test multi-person entry with non-dict element."""
        data = {
            "Alice & Bob": {
                "canonical": [
                    {"name": "Alice", "lastname": None, "alias": None},
                    "not a dict",
                ],
                "dates": ["2024-01-15"],
            }
        }
        file_path = self.create_people_file(tmp_dir, data)

        result = validate_people_file(file_path)
        assert result.is_valid is False
        assert any("canonical[1] must be a dict" in err for err in result.errors)


class TestValidateLocationsFile:
    """Test validate_locations_file function."""

    def create_locations_file(self, tmp_dir: Path, data: Dict[str, Any]) -> Path:
        """Helper to create a locations curation file."""
        file_path = tmp_dir / "2024_locations_curation.yaml"
        file_path.write_text(yaml.dump(data))
        return file_path

    def test_valid_locations_file(self, tmp_dir):
        """Test validating a valid locations file."""
        data = {
            "Montreal": {
                "Cafe": {"canonical": "Coffee Shop", "dates": ["2024-01-15"]},
                "Library": {"canonical": None, "dates": ["2024-01-16"]},
            }
        }
        file_path = self.create_locations_file(tmp_dir, data)

        result = validate_locations_file(file_path)
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_invalid_yaml(self, tmp_dir):
        """Test invalid YAML file."""
        file_path = tmp_dir / "2024_locations_curation.yaml"
        file_path.write_text("invalid: yaml: [")

        result = validate_locations_file(file_path)
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "Failed to load" in result.errors[0]

    def test_invalid_city_format(self, tmp_dir):
        """Test city that's not a dict."""
        data = {"Montreal": "not a dict"}
        file_path = self.create_locations_file(tmp_dir, data)

        result = validate_locations_file(file_path)
        assert result.is_valid is False
        assert any("Invalid city format" in err for err in result.errors)

    def test_invalid_entry_format(self, tmp_dir):
        """Test location entry that's not a dict."""
        data = {"Montreal": {"Cafe": "not a dict"}}
        file_path = self.create_locations_file(tmp_dir, data)

        result = validate_locations_file(file_path)
        assert result.is_valid is False
        assert any("Invalid entry format" in err for err in result.errors)

    def test_canonical_not_string(self, tmp_dir):
        """Test canonical that's not a string - currently converts to string."""
        # NOTE: Current implementation converts non-string canonicals to str()
        # This test documents current behavior - canonical validation happens
        # after conversion, so dict becomes string representation
        data = {
            "Montreal": {
                "Cafe": {"canonical": {"not": "a string"}, "dates": ["2024-01-15"]}
            }
        }
        file_path = self.create_locations_file(tmp_dir, data)

        result = validate_locations_file(file_path)
        # Current behavior: accepts dict because it's converted to str
        # This may be a bug worth fixing in future
        assert result.is_valid is True

    def test_skip_entry_no_validation(self, tmp_dir):
        """Test skip entry doesn't trigger validation."""
        data = {"Montreal": {"Cafe": {"skip": True}}}
        file_path = self.create_locations_file(tmp_dir, data)

        result = validate_locations_file(file_path)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_same_as_valid_reference(self, tmp_dir):
        """Test same_as references existing entry in same city."""
        data = {
            "Montreal": {
                "Cafe": {"canonical": "Coffee Shop", "dates": ["2024-01-15"]},
                "Coffee": {"same_as": "Cafe", "dates": ["2024-01-16"]},
            }
        }
        file_path = self.create_locations_file(tmp_dir, data)

        result = validate_locations_file(file_path)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_same_as_invalid_reference(self, tmp_dir):
        """Test same_as references non-existent entry."""
        data = {
            "Montreal": {"Coffee": {"same_as": "NonExistent", "dates": ["2024-01-15"]}}
        }
        file_path = self.create_locations_file(tmp_dir, data)

        result = validate_locations_file(file_path)
        assert result.is_valid is False
        assert any("same_as references non-existent entry" in err for err in result.errors)

    def test_circular_same_as_reference(self, tmp_dir):
        """Test circular same_as chain detection."""
        data = {
            "Montreal": {
                "Cafe": {"same_as": "Coffee"},
                "Coffee": {"same_as": "Shop"},
                "Shop": {"same_as": "Cafe"},
            }
        }
        file_path = self.create_locations_file(tmp_dir, data)

        result = validate_locations_file(file_path)
        assert result.is_valid is False
        assert any("Circular same_as reference" in err for err in result.errors)

    def test_missing_dates_warning(self, tmp_dir):
        """Test warning for missing dates."""
        data = {"Montreal": {"Cafe": {"canonical": "Coffee Shop"}}}
        file_path = self.create_locations_file(tmp_dir, data)

        result = validate_locations_file(file_path)
        assert result.is_valid is True
        assert len(result.warnings) == 1
        assert "No dates listed" in result.warnings[0]

    def test_multiple_cities(self, tmp_dir):
        """Test validation across multiple cities."""
        data = {
            "Montreal": {
                "Cafe": {"canonical": "Coffee Shop", "dates": ["2024-01-15"]},
            },
            "Toronto": {
                "Library": {"canonical": None, "dates": ["2024-01-16"]},
            },
        }
        file_path = self.create_locations_file(tmp_dir, data)

        result = validate_locations_file(file_path)
        assert result.is_valid is True
        assert len(result.errors) == 0


# =============================================================================
# Cross-Year Consistency Tests
# =============================================================================

class TestCheckPeopleConsistency:
    """Test check_people_consistency function."""

    def create_people_files(self, tmp_dir: Path, files_data: Dict[str, Dict[str, Any]]) -> None:
        """Helper to create multiple people curation files."""
        for year, data in files_data.items():
            file_path = tmp_dir / f"{year}_people_curation.yaml"
            file_path.write_text(yaml.dump(data))

    def test_no_conflicts_same_canonical(self, tmp_dir, monkeypatch):
        """Test no conflicts when same person has same canonical across years."""
        files_data = {
            "2023": {
                "Alice": {
                    "canonical": {"name": "Alice", "lastname": "Smith", "alias": None},
                    "dates": ["2023-01-15"],
                }
            },
            "2024": {
                "Alice": {
                    "canonical": {"name": "Alice", "lastname": "Smith", "alias": None},
                    "dates": ["2024-01-15"],
                }
            },
        }
        self.create_people_files(tmp_dir, files_data)
        monkeypatch.setattr("dev.curation.validate.CURATION_DIR", tmp_dir)

        result = check_people_consistency()
        assert result.has_conflicts is False
        assert len(result.conflicts) == 0

    def test_conflict_different_canonicals(self, tmp_dir, monkeypatch):
        """Test conflict when same person has different canonicals."""
        files_data = {
            "2023": {
                "Alice": {
                    "canonical": {"name": "Alice", "lastname": "Smith", "alias": None},
                    "dates": ["2023-01-15"],
                }
            },
            "2024": {
                "Alice": {
                    "canonical": {"name": "Alice", "lastname": "Jones", "alias": None},
                    "dates": ["2024-01-15"],
                }
            },
        }
        self.create_people_files(tmp_dir, files_data)
        monkeypatch.setattr("dev.curation.validate.CURATION_DIR", tmp_dir)

        result = check_people_consistency()
        assert result.has_conflicts is True
        assert len(result.conflicts) > 0
        assert "Alice" in result.conflicts[0]
        assert "Different canonicals" in result.conflicts[0]

    def test_suggestion_similar_names(self, tmp_dir, monkeypatch):
        """Test suggestion for similar names that might need same_as."""
        files_data = {
            "2023": {
                "Alice": {
                    "canonical": {"name": "Alice", "lastname": None, "alias": None},
                    "dates": ["2023-01-15"],
                }
            },
            "2024": {
                "ALICE": {
                    "canonical": {"name": "Alice", "lastname": None, "alias": None},
                    "dates": ["2024-01-15"],
                }
            },
        }
        self.create_people_files(tmp_dir, files_data)
        monkeypatch.setattr("dev.curation.validate.CURATION_DIR", tmp_dir)

        result = check_people_consistency()
        assert len(result.suggestions) > 0
        # Should suggest linking "Alice" and "ALICE"

    def test_skip_entries_ignored(self, tmp_dir, monkeypatch):
        """Test skip entries don't appear in consistency checks."""
        files_data = {
            "2023": {"Alice": {"skip": True}},
            "2024": {
                "Alice": {
                    "canonical": {"name": "Alice", "lastname": None, "alias": None},
                    "dates": ["2024-01-15"],
                }
            },
        }
        self.create_people_files(tmp_dir, files_data)
        monkeypatch.setattr("dev.curation.validate.CURATION_DIR", tmp_dir)

        result = check_people_consistency()
        # Should not conflict since 2023 entry is skipped
        assert result.has_conflicts is False

    def test_self_entries_ignored(self, tmp_dir, monkeypatch):
        """Test self entries don't appear in consistency checks."""
        files_data = {
            "2023": {"Sofia": {"self": True}},
            "2024": {"Sofia": {"self": True}},
        }
        self.create_people_files(tmp_dir, files_data)
        monkeypatch.setattr("dev.curation.validate.CURATION_DIR", tmp_dir)

        result = check_people_consistency()
        assert result.has_conflicts is False
        assert len(result.suggestions) == 0

    def test_same_as_resolution(self, tmp_dir, monkeypatch):
        """Test same_as references are resolved to canonical."""
        files_data = {
            "2024": {
                "Alice": {
                    "canonical": {"name": "Alice", "lastname": "Smith", "alias": None},
                    "dates": ["2024-01-15"],
                },
                "Alicia": {"same_as": "Alice", "dates": ["2024-01-16"]},
            }
        }
        self.create_people_files(tmp_dir, files_data)
        monkeypatch.setattr("dev.curation.validate.CURATION_DIR", tmp_dir)

        result = check_people_consistency()
        # Both entries should resolve to the same canonical
        assert result.has_conflicts is False


class TestCheckLocationsConsistency:
    """Test check_locations_consistency function."""

    def create_locations_files(self, tmp_dir: Path, files_data: Dict[str, Dict[str, Any]]) -> None:
        """Helper to create multiple locations curation files."""
        for year, data in files_data.items():
            file_path = tmp_dir / f"{year}_locations_curation.yaml"
            file_path.write_text(yaml.dump(data))

    def test_no_conflicts_same_canonical(self, tmp_dir, monkeypatch):
        """Test no conflicts when same location has same canonical."""
        files_data = {
            "2023": {
                "Montreal": {
                    "Cafe": {"canonical": "Coffee Shop", "dates": ["2023-01-15"]}
                }
            },
            "2024": {
                "Montreal": {
                    "Cafe": {"canonical": "Coffee Shop", "dates": ["2024-01-15"]}
                }
            },
        }
        self.create_locations_files(tmp_dir, files_data)
        monkeypatch.setattr("dev.curation.validate.CURATION_DIR", tmp_dir)

        result = check_locations_consistency()
        assert result.has_conflicts is False
        assert len(result.conflicts) == 0

    def test_conflict_different_canonicals(self, tmp_dir, monkeypatch):
        """Test conflict when same location has different canonicals."""
        files_data = {
            "2023": {
                "Montreal": {
                    "Cafe": {"canonical": "Coffee Shop", "dates": ["2023-01-15"]}
                }
            },
            "2024": {
                "Montreal": {
                    "Cafe": {"canonical": "Cafe Central", "dates": ["2024-01-15"]}
                }
            },
        }
        self.create_locations_files(tmp_dir, files_data)
        monkeypatch.setattr("dev.curation.validate.CURATION_DIR", tmp_dir)

        result = check_locations_consistency()
        assert result.has_conflicts is True
        assert len(result.conflicts) > 0
        assert "Cafe" in result.conflicts[0]
        assert "Different canonicals" in result.conflicts[0]

    def test_suggestion_same_location_different_cities(self, tmp_dir, monkeypatch):
        """Test suggestion for same location in different cities."""
        files_data = {
            "2023": {
                "Montreal": {
                    "Library": {"canonical": None, "dates": ["2023-01-15"]}
                }
            },
            "2024": {
                "Toronto": {
                    "Library": {"canonical": None, "dates": ["2024-01-15"]}
                }
            },
        }
        self.create_locations_files(tmp_dir, files_data)
        monkeypatch.setattr("dev.curation.validate.CURATION_DIR", tmp_dir)

        result = check_locations_consistency()
        assert len(result.suggestions) > 0
        assert "Same location in multiple cities" in result.suggestions[0]

    def test_skip_entries_ignored(self, tmp_dir, monkeypatch):
        """Test skip entries don't appear in consistency checks."""
        files_data = {
            "2023": {"Montreal": {"Cafe": {"skip": True}}},
            "2024": {
                "Montreal": {
                    "Cafe": {"canonical": "Coffee Shop", "dates": ["2024-01-15"]}
                }
            },
        }
        self.create_locations_files(tmp_dir, files_data)
        monkeypatch.setattr("dev.curation.validate.CURATION_DIR", tmp_dir)

        result = check_locations_consistency()
        assert result.has_conflicts is False

    def test_same_as_resolution(self, tmp_dir, monkeypatch):
        """Test same_as references are resolved to canonical."""
        files_data = {
            "2024": {
                "Montreal": {
                    "Cafe": {"canonical": "Coffee Shop", "dates": ["2024-01-15"]},
                    "Coffee": {"same_as": "Cafe", "dates": ["2024-01-16"]},
                }
            }
        }
        self.create_locations_files(tmp_dir, files_data)
        monkeypatch.setattr("dev.curation.validate.CURATION_DIR", tmp_dir)

        result = check_locations_consistency()
        # Both entries should resolve to the same canonical
        assert result.has_conflicts is False

    def test_canonical_null_convention(self, tmp_dir, monkeypatch):
        """Test canonical: null convention (canonical = key)."""
        files_data = {
            "2023": {
                "Montreal": {"Cafe": {"canonical": None, "dates": ["2023-01-15"]}}
            },
            "2024": {
                "Montreal": {"Cafe": {"canonical": None, "dates": ["2024-01-15"]}}
            },
        }
        self.create_locations_files(tmp_dir, files_data)
        monkeypatch.setattr("dev.curation.validate.CURATION_DIR", tmp_dir)

        result = check_locations_consistency()
        # Both should resolve to "Cafe" as canonical
        assert result.has_conflicts is False


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and complex scenarios."""

    def test_people_all_null_canonical_consistency(self, tmp_dir, monkeypatch):
        """Test all-null canonical convention across years."""
        files_data = {
            "2023": {
                "Alice": {
                    "canonical": {"name": None, "lastname": None, "alias": None},
                    "dates": ["2023-01-15"],
                }
            },
            "2024": {
                "Alice": {
                    "canonical": {"name": None, "lastname": None, "alias": None},
                    "dates": ["2024-01-15"],
                }
            },
        }
        for year, data in files_data.items():
            file_path = tmp_dir / f"{year}_people_curation.yaml"
            file_path.write_text(yaml.dump(data))
        monkeypatch.setattr("dev.curation.validate.CURATION_DIR", tmp_dir)

        result = check_people_consistency()
        # Should resolve both to {"name": "Alice", "lastname": None, "alias": None}
        assert result.has_conflicts is False

    def test_empty_curation_directory(self, tmp_dir, monkeypatch):
        """Test consistency check with no curation files."""
        monkeypatch.setattr("dev.curation.validate.CURATION_DIR", tmp_dir)

        result_people = check_people_consistency()
        result_locations = check_locations_consistency()

        assert result_people.has_conflicts is False
        assert len(result_people.suggestions) == 0
        assert result_locations.has_conflicts is False
        assert len(result_locations.suggestions) == 0

    def test_complex_same_as_chain(self, tmp_dir):
        """Test complex but valid same_as chain."""
        data = {
            "Alice": {
                "canonical": {"name": "Alice", "lastname": "Smith", "alias": None},
                "dates": ["2024-01-15"],
            },
            "Alicia": {"same_as": "Alice", "dates": ["2024-01-16"]},
            "Ali": {"same_as": "Alicia", "dates": ["2024-01-17"]},
        }
        file_path = tmp_dir / "2024_people_curation.yaml"
        file_path.write_text(yaml.dump(data))

        result = validate_people_file(file_path)
        # Valid chain: Ali -> Alicia -> Alice
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validation_result_summary(self):
        """Test ValidationResult summary method."""
        result = ValidationResult(file_path="test.yaml")

        assert result.summary() == "Valid"

        result.add_warning("Warning 1")
        assert "1 warnings" in result.summary()

        result.add_error("Error 1")
        assert "Invalid" in result.summary()
        assert "1 errors" in result.summary()

    def test_consistency_result_summary(self):
        """Test ConsistencyResult summary method."""
        result = ConsistencyResult(entity_type="people")

        assert "No conflicts" in result.summary()

        result.conflicts.append("Conflict 1")
        assert "1 conflicts" in result.summary()
        assert result.has_conflicts is True

        result.suggestions.append("Suggestion 1")
        assert "1 suggestions" in result.summary()

    def test_same_as_with_none_value(self, tmp_dir):
        """Test same_as with None value is not treated as same_as."""
        data = {
            "Alice": {
                "same_as": None,
                "canonical": {"name": "Alice", "lastname": None, "alias": None},
                "dates": ["2024-01-15"],
            }
        }
        file_path = tmp_dir / "2024_people_curation.yaml"
        file_path.write_text(yaml.dump(data))

        result = validate_people_file(file_path)
        # same_as: None is not treated as a reference
        assert result.is_valid is True

    def test_accented_names_normalization(self):
        """Test that accented names normalize correctly."""
        # NFD normalization removes combining diacritics
        assert normalize_name("François") == "francois"
        assert normalize_name("Müller") == "muller"
        # Precomposed characters like Ø are not decomposed
        assert normalize_name("Øyvind") == "øyvind"
        assert normalize_name("Søren") == "søren"

    def test_self_and_canonical_both_present(self, tmp_dir):
        """Test entry with both self and canonical (self takes priority)."""
        data = {
            "Sofia": {
                "self": True,
                "canonical": {"name": "Sofia", "lastname": "Smith", "alias": None},
                "dates": ["2024-01-15"],
            }
        }
        file_path = tmp_dir / "2024_people_curation.yaml"
        file_path.write_text(yaml.dump(data))

        result = validate_people_file(file_path)
        # Should be valid - self entry doesn't need validation
        assert result.is_valid is True

    def test_same_as_to_skip_entry(self, tmp_dir):
        """Test same_as referencing a skip entry."""
        data = {
            "Bob": {"skip": True},
            "Robert": {"same_as": "Bob", "dates": ["2024-01-15"]},
        }
        file_path = tmp_dir / "2024_people_curation.yaml"
        file_path.write_text(yaml.dump(data))

        result = validate_people_file(file_path)
        # Currently valid - same_as just checks existence, not state
        assert result.is_valid is True

    def test_same_as_to_self_entry(self, tmp_dir):
        """Test same_as referencing a self entry."""
        data = {
            "Sofia": {"self": True},
            "Sofi": {"same_as": "Sofia", "dates": ["2024-01-15"]},
        }
        file_path = tmp_dir / "2024_people_curation.yaml"
        file_path.write_text(yaml.dump(data))

        result = validate_people_file(file_path)
        # Currently valid - same_as just checks existence
        assert result.is_valid is True

    def test_locations_same_as_cross_city_not_allowed(self, tmp_dir):
        """Test same_as cannot reference location in different city."""
        data = {
            "Montreal": {"Cafe": {"canonical": "Coffee Shop", "dates": ["2024-01-15"]}},
            "Toronto": {"Coffee": {"same_as": "Cafe", "dates": ["2024-01-16"]}},
        }
        file_path = tmp_dir / "2024_locations_curation.yaml"
        file_path.write_text(yaml.dump(data))

        result = validate_locations_file(file_path)
        # Should be invalid - same_as in Toronto references "Cafe" which doesn't exist in Toronto
        assert result.is_valid is False
        assert any("same_as references non-existent entry" in err for err in result.errors)

    def test_consistency_with_all_null_and_explicit_values(self, tmp_dir, monkeypatch):
        """Test consistency when same person has all-null in one year, explicit in another."""
        files_data = {
            "2023": {
                "Alice": {
                    "canonical": {"name": None, "lastname": None, "alias": None},
                    "dates": ["2023-01-15"],
                }
            },
            "2024": {
                "Alice": {
                    "canonical": {"name": "Alice", "lastname": "Smith", "alias": None},
                    "dates": ["2024-01-15"],
                }
            },
        }
        for year, data in files_data.items():
            file_path = tmp_dir / f"{year}_people_curation.yaml"
            file_path.write_text(yaml.dump(data))
        monkeypatch.setattr("dev.curation.validate.CURATION_DIR", tmp_dir)

        result = check_people_consistency()
        # Should conflict: 2023 resolves to "Alice|None|None", 2024 to "Alice|Smith|None"
        assert result.has_conflicts is True

    def test_multi_person_entry_with_all_null_canonical(self, tmp_dir):
        """Test multi-person entry doesn't support all-null canonical."""
        data = {
            "Alice & Bob": {
                "canonical": [
                    {"name": None, "lastname": None, "alias": None},
                    {"name": None, "lastname": None, "alias": None},
                ],
                "dates": ["2024-01-15"],
            }
        }
        file_path = tmp_dir / "2024_people_curation.yaml"
        file_path.write_text(yaml.dump(data))

        result = validate_people_file(file_path)
        # All-null entries in multi-person should require explicit name
        assert result.is_valid is False
        assert any("name is required" in err for err in result.errors)

    def test_dates_empty_list_warning(self, tmp_dir):
        """Test empty dates list triggers warning."""
        data = {
            "Alice": {
                "canonical": {"name": "Alice", "lastname": None, "alias": None},
                "dates": [],
            }
        }
        file_path = tmp_dir / "2024_people_curation.yaml"
        file_path.write_text(yaml.dump(data))

        result = validate_people_file(file_path)
        assert result.is_valid is True
        assert len(result.warnings) == 1
        assert "No dates listed" in result.warnings[0]

    def test_same_as_non_string_value(self, tmp_dir):
        """Test same_as with non-string value (integer)."""
        data = {
            "Alice": {
                "canonical": {"name": "Alice", "lastname": None, "alias": None},
                "dates": ["2024-01-15"],
            },
            "Alicia": {"same_as": 123, "dates": ["2024-01-16"]},
        }
        file_path = tmp_dir / "2024_people_curation.yaml"
        file_path.write_text(yaml.dump(data))

        result = validate_people_file(file_path)
        # Should handle gracefully - won't find integer in all_names set
        assert result.is_valid is False
        assert any("same_as references non-existent entry" in err for err in result.errors)

    def test_consistency_same_as_to_nonexistent_in_same_file(self, tmp_dir, monkeypatch):
        """Test consistency when same_as references non-existent entry."""
        files_data = {
            "2024": {
                "Alice": {
                    "canonical": {"name": "Alice", "lastname": None, "alias": None},
                    "dates": ["2024-01-15"],
                },
                "Alicia": {"same_as": "NonExistent", "dates": ["2024-01-16"]},
            }
        }
        for year, data in files_data.items():
            file_path = tmp_dir / f"{year}_people_curation.yaml"
            file_path.write_text(yaml.dump(data))
        monkeypatch.setattr("dev.curation.validate.CURATION_DIR", tmp_dir)

        # Consistency check should handle this gracefully (validation catches it)
        result = check_people_consistency()
        # Should not crash, just skip invalid same_as
        assert isinstance(result, ConsistencyResult)

    def test_location_canonical_empty_string(self, tmp_dir):
        """Test location with empty string canonical."""
        data = {
            "Montreal": {"Cafe": {"canonical": "", "dates": ["2024-01-15"]}}
        }
        file_path = tmp_dir / "2024_locations_curation.yaml"
        file_path.write_text(yaml.dump(data))

        result = validate_locations_file(file_path)
        # Empty string is still a valid string
        assert result.is_valid is True

    def test_circular_same_as_two_entries(self, tmp_dir):
        """Test circular same_as with just two entries."""
        data = {
            "Alice": {"same_as": "Alicia"},
            "Alicia": {"same_as": "Alice"},
        }
        file_path = tmp_dir / "2024_people_curation.yaml"
        file_path.write_text(yaml.dump(data))

        result = validate_people_file(file_path)
        assert result.is_valid is False
        # Should detect circular reference
        assert any("Circular same_as reference" in err for err in result.errors)

    def test_self_reference_same_as(self, tmp_dir):
        """Test same_as referencing itself."""
        data = {
            "Alice": {"same_as": "Alice"},
        }
        file_path = tmp_dir / "2024_people_curation.yaml"
        file_path.write_text(yaml.dump(data))

        result = validate_people_file(file_path)
        assert result.is_valid is False
        # Should detect self-reference as circular
        assert any("Circular same_as reference" in err for err in result.errors)

    def test_consistency_with_multiple_conflicts(self, tmp_dir, monkeypatch):
        """Test consistency check finds multiple conflicts."""
        files_data = {
            "2023": {
                "Alice": {
                    "canonical": {"name": "Alice", "lastname": "Smith", "alias": None},
                    "dates": ["2023-01-15"],
                },
                "Bob": {
                    "canonical": {"name": "Bob", "lastname": "Jones", "alias": None},
                    "dates": ["2023-01-15"],
                },
            },
            "2024": {
                "Alice": {
                    "canonical": {"name": "Alice", "lastname": "Johnson", "alias": None},
                    "dates": ["2024-01-15"],
                },
                "Bob": {
                    "canonical": {"name": "Bob", "lastname": "Williams", "alias": None},
                    "dates": ["2024-01-15"],
                },
            },
        }
        for year, data in files_data.items():
            file_path = tmp_dir / f"{year}_people_curation.yaml"
            file_path.write_text(yaml.dump(data))
        monkeypatch.setattr("dev.curation.validate.CURATION_DIR", tmp_dir)

        result = check_people_consistency()
        assert result.has_conflicts is True
        # Should find conflicts for both Alice and Bob
        assert len(result.conflicts) >= 2

    def test_normalize_name_preserves_apostrophes(self):
        """Test normalize_name keeps apostrophes."""
        assert "l'epoque" in normalize_name("Café de l'Époque")

    def test_locations_consistency_case_insensitive_canonicals(self, tmp_dir, monkeypatch):
        """Test that location canonicals are compared case-insensitively."""
        files_data = {
            "2023": {
                "Montreal": {
                    "Cafe": {"canonical": "Coffee Shop", "dates": ["2023-01-15"]}
                }
            },
            "2024": {
                "Montreal": {
                    "Cafe": {"canonical": "coffee shop", "dates": ["2024-01-15"]}
                }
            },
        }
        for year, data in files_data.items():
            file_path = tmp_dir / f"{year}_locations_curation.yaml"
            file_path.write_text(yaml.dump(data))
        monkeypatch.setattr("dev.curation.validate.CURATION_DIR", tmp_dir)

        result = check_locations_consistency()
        # Should NOT conflict - "Coffee Shop" and "coffee shop" are same when lowercased
        assert result.has_conflicts is False

    def test_validate_all_with_year_filter(self, tmp_dir, monkeypatch):
        """Test validate_all with year parameter."""
        from dev.curation.validate import validate_all

        # Create files for multiple years
        for year in ["2023", "2024"]:
            people_data = {
                "Alice": {
                    "canonical": {"name": "Alice", "lastname": None, "alias": None},
                    "dates": [f"{year}-01-15"],
                }
            }
            file_path = tmp_dir / f"{year}_people_curation.yaml"
            file_path.write_text(yaml.dump(people_data))

        monkeypatch.setattr("dev.curation.validate.CURATION_DIR", tmp_dir)

        # Validate only 2024
        results = validate_all(year="2024", entity_type="people")
        assert len(results) == 1
        assert "2024" in results[0].file_path

    def test_validate_all_with_entity_type_filter(self, tmp_dir, monkeypatch):
        """Test validate_all with entity_type parameter."""
        from dev.curation.validate import validate_all

        # Create both people and locations files
        people_data = {
            "Alice": {
                "canonical": {"name": "Alice", "lastname": None, "alias": None},
                "dates": ["2024-01-15"],
            }
        }
        locations_data = {
            "Montreal": {
                "Cafe": {"canonical": "Coffee Shop", "dates": ["2024-01-15"]}
            }
        }

        people_file = tmp_dir / "2024_people_curation.yaml"
        people_file.write_text(yaml.dump(people_data))

        locations_file = tmp_dir / "2024_locations_curation.yaml"
        locations_file.write_text(yaml.dump(locations_data))

        monkeypatch.setattr("dev.curation.validate.CURATION_DIR", tmp_dir)

        # Validate only people
        results = validate_all(entity_type="people")
        assert len(results) == 1
        assert "people" in results[0].file_path

        # Validate only locations
        results = validate_all(entity_type="locations")
        assert len(results) == 1
        assert "locations" in results[0].file_path

    def test_check_consistency_with_entity_type_filter(self, tmp_dir, monkeypatch):
        """Test check_consistency with entity_type parameter."""
        from dev.curation.validate import check_consistency

        # Create both people and locations files
        people_data = {
            "Alice": {
                "canonical": {"name": "Alice", "lastname": None, "alias": None},
                "dates": ["2024-01-15"],
            }
        }
        locations_data = {
            "Montreal": {
                "Cafe": {"canonical": "Coffee Shop", "dates": ["2024-01-15"]}
            }
        }

        people_file = tmp_dir / "2024_people_curation.yaml"
        people_file.write_text(yaml.dump(people_data))

        locations_file = tmp_dir / "2024_locations_curation.yaml"
        locations_file.write_text(yaml.dump(locations_data))

        monkeypatch.setattr("dev.curation.validate.CURATION_DIR", tmp_dir)

        # Check only people
        results = check_consistency(entity_type="people")
        assert len(results) == 1
        assert results[0].entity_type == "people"

        # Check only locations
        results = check_consistency(entity_type="locations")
        assert len(results) == 1
        assert results[0].entity_type == "locations"
