#!/usr/bin/env python3
"""
test_consolidate.py
-------------------
Unit tests for dev.curation.consolidate module.

Tests entity consolidation logic, same_as resolution, canonical merging,
and YAML output formatting for people and locations.

Target Coverage: 95%+
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from typing import Any, Dict

# --- Third-party imports ---
import pytest
import yaml

# --- Local imports ---
from dev.curation.consolidate import (
    is_all_null_canonical,
    get_effective_canonical,
    canonical_key,
    merge_canonicals,
    consolidate_people,
    consolidate_locations,
    consolidate_and_write,
    load_yaml,
)
from dev.curation.models import ConsolidationResult


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_2023_people(tmp_dir):
    """Create sample 2023 people curation file."""
    data = {
        "Alice": {
            "dates": ["2023-01-15", "2023-02-20"],
            "canonical": {
                "name": "Alice",
                "lastname": "Smith",
                "alias": "Al"
            }
        },
        "Bob": {
            "dates": ["2023-03-10"],
            "canonical": {
                "name": "Bob",
                "lastname": None,
                "alias": None
            }
        },
        "Charlie": {
            "dates": ["2023-04-05"],
            "skip": True
        },
        "Dave": {
            "dates": ["2023-05-12"],
            "self": True
        },
        "Eve": {
            "dates": ["2023-06-01"],
            "same_as": "Alice"
        },
        "Frank": {
            "dates": ["2023-07-15"],
            "canonical": None
        }
    }
    path = tmp_dir / "2023_people_curation.yaml"
    with open(path, "w") as f:
        yaml.dump(data, f)
    return path


@pytest.fixture
def sample_2024_people(tmp_dir):
    """Create sample 2024 people curation file."""
    data = {
        "Alice": {
            "dates": ["2024-01-10", "2024-02-15"],
            "canonical": {
                "name": "Alice",
                "lastname": "Smith",
                "alias": ["Al", "Allie"]
            }
        },
        "Bob": {
            "dates": ["2024-03-20"],
            "canonical": {
                "name": "Bob",
                "lastname": "Jones",
                "alias": None
            }
        },
        "Grace": {
            "dates": ["2024-04-10"],
            "canonical": {
                "name": "Grace",
                "lastname": None,
                "alias": None
            }
        }
    }
    path = tmp_dir / "2024_people_curation.yaml"
    with open(path, "w") as f:
        yaml.dump(data, f)
    return path


@pytest.fixture
def sample_2023_locations(tmp_dir):
    """Create sample 2023 locations curation file."""
    data = {
        "Montreal": {
            "Cafe X": {
                "dates": ["2023-01-15", "2023-02-20"],
                "canonical": "Café X"
            },
            "Library": {
                "dates": ["2023-03-10"],
                "canonical": None
            },
            "Museum": {
                "dates": ["2023-04-05"],
                "skip": True
            },
            "Park": {
                "dates": ["2023-05-12"],
                "same_as": "Library"
            }
        },
        "Toronto": {
            "CN Tower": {
                "dates": ["2023-06-01"],
                "canonical": "CN Tower"
            }
        }
    }
    path = tmp_dir / "2023_locations_curation.yaml"
    with open(path, "w") as f:
        yaml.dump(data, f)
    return path


@pytest.fixture
def sample_2024_locations(tmp_dir):
    """Create sample 2024 locations curation file."""
    data = {
        "Montreal": {
            "Cafe X": {
                "dates": ["2024-01-10"],
                "canonical": "Café X"
            },
            "Library": {
                "dates": ["2024-02-15"],
                "canonical": None
            }
        },
        "Vancouver": {
            "Stanley Park": {
                "dates": ["2024-03-20"],
                "canonical": "Stanley Park"
            }
        }
    }
    path = tmp_dir / "2024_locations_curation.yaml"
    with open(path, "w") as f:
        yaml.dump(data, f)
    return path


@pytest.fixture
def circular_same_as_people(tmp_dir):
    """Create file with circular same_as reference."""
    data = {
        "Alice": {
            "dates": ["2023-01-15"],
            "same_as": "Bob"
        },
        "Bob": {
            "dates": ["2023-02-20"],
            "same_as": "Alice"
        }
    }
    path = tmp_dir / "2023_people_curation.yaml"
    with open(path, "w") as f:
        yaml.dump(data, f)
    return path


@pytest.fixture
def all_null_canonical_people(tmp_dir):
    """Create file with all-null canonical convention."""
    data = {
        "SimpleAlice": {
            "dates": ["2023-01-15"],
            "canonical": {
                "name": None,
                "lastname": None,
                "alias": None
            }
        }
    }
    path = tmp_dir / "2023_people_curation.yaml"
    with open(path, "w") as f:
        yaml.dump(data, f)
    return path


@pytest.fixture
def multi_person_entry(tmp_dir):
    """Create file with multi-person entry."""
    data = {
        "Alice and Bob": {
            "dates": ["2023-01-15"],
            "canonical": ["Alice", "Bob"]
        }
    }
    path = tmp_dir / "2023_people_curation.yaml"
    with open(path, "w") as f:
        yaml.dump(data, f)
    return path


# =============================================================================
# Test is_all_null_canonical
# =============================================================================

class TestIsAllNullCanonical:
    """Test is_all_null_canonical function."""

    def test_all_null_values_returns_true(self):
        """Test dict with all null values returns True."""
        canonical = {
            "name": None,
            "lastname": None,
            "alias": None
        }
        assert is_all_null_canonical(canonical) is True

    def test_some_null_values_returns_false(self):
        """Test dict with some non-null values returns False."""
        canonical = {
            "name": "Alice",
            "lastname": None,
            "alias": None
        }
        assert is_all_null_canonical(canonical) is False

    def test_no_null_values_returns_false(self):
        """Test dict with no null values returns False."""
        canonical = {
            "name": "Alice",
            "lastname": "Smith",
            "alias": "Al"
        }
        assert is_all_null_canonical(canonical) is False

    def test_empty_dict_returns_true(self):
        """Test empty dict returns True."""
        assert is_all_null_canonical({}) is True

    def test_non_dict_returns_false(self):
        """Test non-dict input returns False."""
        assert is_all_null_canonical("string") is False
        assert is_all_null_canonical(["list"]) is False
        assert is_all_null_canonical(None) is False


# =============================================================================
# Test get_effective_canonical
# =============================================================================

class TestGetEffectiveCanonical:
    """Test get_effective_canonical function."""

    def test_skip_entry_returns_none(self):
        """Test entry with skip=True returns None."""
        entry = {"skip": True, "canonical": {"name": "Alice"}}
        assert get_effective_canonical("Alice", entry) is None

    def test_self_entry_returns_none(self):
        """Test entry with self=True returns None."""
        entry = {"self": True, "canonical": {"name": "Alice"}}
        assert get_effective_canonical("Alice", entry) is None

    def test_same_as_entry_returns_none(self):
        """Test entry with same_as returns None."""
        entry = {"same_as": "Bob", "canonical": {"name": "Alice"}}
        assert get_effective_canonical("Alice", entry) is None

    def test_no_canonical_returns_none(self):
        """Test entry without canonical returns None."""
        entry = {"dates": ["2023-01-15"]}
        assert get_effective_canonical("Alice", entry) is None

    def test_multi_person_canonical(self):
        """Test multi-person canonical (list) returns _multi format."""
        entry = {"canonical": ["Alice", "Bob"]}
        result = get_effective_canonical("Alice and Bob", entry)
        assert result == {"_multi": ["Alice", "Bob"]}

    def test_non_dict_canonical_returns_none(self):
        """Test non-dict canonical returns None."""
        entry = {"canonical": "Alice"}
        assert get_effective_canonical("Alice", entry) is None

    def test_all_null_canonical_uses_raw_name(self):
        """Test all-null canonical convention uses raw_name."""
        entry = {
            "canonical": {
                "name": None,
                "lastname": None,
                "alias": None
            }
        }
        result = get_effective_canonical("SimpleAlice", entry)
        assert result == {"name": "SimpleAlice", "lastname": None, "alias": None}

    def test_normal_canonical_returns_as_is(self):
        """Test normal canonical dict returns as-is."""
        entry = {
            "canonical": {
                "name": "Alice",
                "lastname": "Smith",
                "alias": "Al"
            }
        }
        result = get_effective_canonical("Alice", entry)
        assert result == entry["canonical"]


# =============================================================================
# Test canonical_key
# =============================================================================

class TestCanonicalKey:
    """Test canonical_key function."""

    def test_key_with_lastname(self):
        """Test key generation with lastname."""
        canonical = {"name": "Alice", "lastname": "Smith"}
        assert canonical_key(canonical) == "alice|smith"

    def test_key_with_disambiguator(self):
        """Test key generation with disambiguator."""
        canonical = {"name": "Alice", "disambiguator": "writer"}
        assert canonical_key(canonical) == "alice||writer"

    def test_key_with_name_only(self):
        """Test key generation with name only."""
        canonical = {"name": "Alice"}
        assert canonical_key(canonical) == "alice|"

    def test_key_case_insensitive(self):
        """Test keys are case-insensitive."""
        canonical1 = {"name": "Alice", "lastname": "Smith"}
        canonical2 = {"name": "ALICE", "lastname": "SMITH"}
        assert canonical_key(canonical1) == canonical_key(canonical2)

    def test_lastname_preferred_over_disambiguator(self):
        """Test lastname takes precedence over disambiguator."""
        canonical = {
            "name": "Alice",
            "lastname": "Smith",
            "disambiguator": "writer"
        }
        assert canonical_key(canonical) == "alice|smith"

    def test_multi_person_key_unique(self):
        """Test multi-person entries get unique keys."""
        canonical1 = {"_multi": ["Alice", "Bob"]}
        canonical2 = {"_multi": ["Alice", "Bob"]}
        # Different objects should have different keys
        assert canonical_key(canonical1) != canonical_key(canonical2)
        # Same object should have same key
        assert canonical_key(canonical1) == canonical_key(canonical1)

    def test_empty_name_handled(self):
        """Test empty name is handled."""
        canonical = {"name": "", "lastname": "Smith"}
        assert canonical_key(canonical) == "|smith"

    def test_none_values_handled(self):
        """Test None values are handled."""
        canonical = {"name": "Alice", "lastname": None, "disambiguator": None}
        assert canonical_key(canonical) == "alice|"


# =============================================================================
# Test merge_canonicals
# =============================================================================

class TestMergeCanonicals:
    """Test merge_canonicals function."""

    def test_merge_prefers_non_null_values(self):
        """Test merge prefers non-null values."""
        c1 = {"name": "Alice", "lastname": None, "alias": None}
        c2 = {"name": "Alice", "lastname": "Smith", "alias": "Al"}
        result = merge_canonicals(c1, c2)
        assert result["lastname"] == "Smith"
        assert result["alias"] == "Al"

    def test_merge_keeps_existing_non_null(self):
        """Test merge keeps existing non-null values."""
        c1 = {"name": "Alice", "lastname": "Smith", "alias": "Al"}
        c2 = {"name": "Alice", "lastname": "Jones", "alias": "Allie"}
        result = merge_canonicals(c1, c2)
        assert result["lastname"] == "Smith"  # c1 value kept

    def test_merge_single_aliases(self):
        """Test merging single string aliases into list."""
        c1 = {"name": "Alice", "alias": "Al"}
        c2 = {"name": "Alice", "alias": "Allie"}
        result = merge_canonicals(c1, c2)
        assert result["alias"] == ["Al", "Allie"]

    def test_merge_alias_list_with_string(self):
        """Test merging alias list with string."""
        c1 = {"name": "Alice", "alias": ["Al", "Allie"]}
        c2 = {"name": "Alice", "alias": "Alice Smith"}
        result = merge_canonicals(c1, c2)
        assert result["alias"] == ["Al", "Allie", "Alice Smith"]

    def test_merge_removes_duplicate_aliases(self):
        """Test merge removes duplicate aliases."""
        c1 = {"name": "Alice", "alias": ["Al", "Allie"]}
        c2 = {"name": "Alice", "alias": ["Allie", "Alice"]}
        result = merge_canonicals(c1, c2)
        assert result["alias"] == ["Al", "Allie", "Alice"]

    def test_merge_empty_aliases(self):
        """Test merge with empty/None aliases."""
        c1 = {"name": "Alice", "alias": None}
        c2 = {"name": "Alice", "alias": None}
        result = merge_canonicals(c1, c2)
        assert "alias" not in result or result["alias"] is None

    def test_merge_single_alias_stays_string(self):
        """Test single merged alias stays as string."""
        c1 = {"name": "Alice", "alias": None}
        c2 = {"name": "Alice", "alias": "Al"}
        result = merge_canonicals(c1, c2)
        assert result["alias"] == "Al"

    def test_merge_preserves_alias_order(self):
        """Test merge preserves alias order."""
        c1 = {"name": "Alice", "alias": ["First", "Second"]}
        c2 = {"name": "Alice", "alias": ["Third"]}
        result = merge_canonicals(c1, c2)
        assert result["alias"] == ["First", "Second", "Third"]


# =============================================================================
# Test consolidate_people
# =============================================================================

class TestConsolidatePeople:
    """Test consolidate_people function."""

    def test_basic_consolidation(self, tmp_dir, sample_2023_people, monkeypatch):
        """Test basic people consolidation from single year."""
        monkeypatch.setattr("dev.curation.consolidate.CURATION_DIR", tmp_dir)

        result, output_data = consolidate_people(["2023"], logger=None)

        assert isinstance(result, ConsolidationResult)
        assert result.merged_count > 0
        assert result.skipped_count > 0
        assert result.self_count > 0

    def test_multi_year_consolidation(self, tmp_dir, sample_2023_people, sample_2024_people, monkeypatch):
        """Test consolidation across multiple years."""
        # Move files to expected locations
        curation_dir = tmp_dir / "curation"
        curation_dir.mkdir(exist_ok=True)
        monkeypatch.setattr("dev.curation.consolidate.CURATION_DIR", curation_dir)

        # Copy files to curation dir
        import shutil
        shutil.copy(sample_2023_people, curation_dir / "2023_people_curation.yaml")
        shutil.copy(sample_2024_people, curation_dir / "2024_people_curation.yaml")

        result, output_data = consolidate_people(["2023", "2024"], logger=None)

        assert result.years_processed == ["2023", "2024"]
        assert result.merged_count > 0

    def test_same_as_resolution(self, tmp_dir, sample_2023_people, monkeypatch):
        """Test same_as chain resolution."""
        monkeypatch.setattr("dev.curation.consolidate.CURATION_DIR", tmp_dir)

        result, output_data = consolidate_people(["2023"], logger=None)

        # Eve points to Alice, should be merged
        # Check that output has Alice with combined dates
        alice_entry = None
        for key, value in output_data.items():
            if "Alice" in key and key != "_skipped" and key != "_self":
                alice_entry = value
                break

        assert alice_entry is not None
        assert "Eve" in alice_entry["raw_names"]

    def test_circular_same_as_skipped(self, tmp_dir, circular_same_as_people, monkeypatch):
        """Test circular same_as references are skipped."""
        monkeypatch.setattr("dev.curation.consolidate.CURATION_DIR", tmp_dir)

        result, output_data = consolidate_people(["2023"], logger=None)

        # Both should be skipped due to circular reference
        assert result.skipped_count == 2
        assert "_skipped" in output_data

    def test_all_null_canonical_convention(self, tmp_dir, all_null_canonical_people, monkeypatch):
        """Test all-null canonical uses raw name."""
        monkeypatch.setattr("dev.curation.consolidate.CURATION_DIR", tmp_dir)

        result, output_data = consolidate_people(["2023"], logger=None)

        # Should have merged entry with raw name
        assert result.merged_count == 1
        # The canonical name should be SimpleAlice
        simple_alice = None
        for key, value in output_data.items():
            if key not in ["_skipped", "_self"] and "SimpleAlice" in value.get("raw_names", []):
                simple_alice = value
                break

        assert simple_alice is not None
        assert simple_alice["canonical"]["name"] == "SimpleAlice"

    def test_multi_person_entry(self, tmp_dir, multi_person_entry, monkeypatch):
        """Test multi-person entry handling."""
        monkeypatch.setattr("dev.curation.consolidate.CURATION_DIR", tmp_dir)

        result, output_data = consolidate_people(["2023"], logger=None)

        # Should have one merged entry
        assert result.merged_count == 1

        # Find the multi-person entry
        multi = None
        for key, value in output_data.items():
            if key not in ["_skipped", "_self"]:
                multi = value
                break

        assert multi is not None
        assert "_multi" in multi["canonical"]

    def test_skip_and_self_tracking(self, tmp_dir, sample_2023_people, monkeypatch):
        """Test skip and self entries are tracked separately."""
        monkeypatch.setattr("dev.curation.consolidate.CURATION_DIR", tmp_dir)

        result, output_data = consolidate_people(["2023"], logger=None)

        assert result.skipped_count > 0
        assert result.self_count > 0
        assert "_skipped" in output_data
        assert "_self" in output_data
        assert "Charlie" in output_data["_skipped"]
        assert "Dave" in output_data["_self"]

    def test_missing_year_file_warning(self, tmp_dir, monkeypatch):
        """Test warning when year file doesn't exist."""
        monkeypatch.setattr("dev.curation.consolidate.CURATION_DIR", tmp_dir)

        result, output_data = consolidate_people(["9999"], logger=None)

        # Should complete without error but with no data
        assert result.merged_count == 0

    def test_alias_merging_across_years(self, tmp_dir, sample_2023_people, sample_2024_people, monkeypatch):
        """Test aliases are merged across years."""
        curation_dir = tmp_dir / "curation"
        curation_dir.mkdir(exist_ok=True)
        monkeypatch.setattr("dev.curation.consolidate.CURATION_DIR", curation_dir)

        import shutil
        shutil.copy(sample_2023_people, curation_dir / "2023_people_curation.yaml")
        shutil.copy(sample_2024_people, curation_dir / "2024_people_curation.yaml")

        result, output_data = consolidate_people(["2023", "2024"], logger=None)

        # Alice has "Al" in 2023 and ["Al", "Allie"] in 2024
        # Should merge to ["Al", "Allie"]
        alice_entry = None
        for key, value in output_data.items():
            if "Alice" in key and key not in ["_skipped", "_self"]:
                alice_entry = value
                break

        assert alice_entry is not None
        alias = alice_entry["canonical"].get("alias")
        if isinstance(alias, list):
            assert "Al" in alias
            assert "Allie" in alias

    def test_dates_merged_by_year(self, tmp_dir, sample_2023_people, sample_2024_people, monkeypatch):
        """Test dates are organized by year."""
        curation_dir = tmp_dir / "curation"
        curation_dir.mkdir(exist_ok=True)
        monkeypatch.setattr("dev.curation.consolidate.CURATION_DIR", curation_dir)

        import shutil
        shutil.copy(sample_2023_people, curation_dir / "2023_people_curation.yaml")
        shutil.copy(sample_2024_people, curation_dir / "2024_people_curation.yaml")

        result, output_data = consolidate_people(["2023", "2024"], logger=None)

        alice_entry = None
        for key, value in output_data.items():
            if "Alice" in key and key not in ["_skipped", "_self"]:
                alice_entry = value
                break

        assert alice_entry is not None
        assert "2023" in alice_entry["dates"]
        assert "2024" in alice_entry["dates"]
        assert len(alice_entry["dates"]["2023"]) == 3  # Alice (2) + Eve (1) via same_as
        assert len(alice_entry["dates"]["2024"]) == 2


# =============================================================================
# Test consolidate_locations
# =============================================================================

class TestConsolidateLocations:
    """Test consolidate_locations function."""

    def test_basic_consolidation(self, tmp_dir, sample_2023_locations, monkeypatch):
        """Test basic locations consolidation from single year."""
        monkeypatch.setattr("dev.curation.consolidate.CURATION_DIR", tmp_dir)

        result, output_data = consolidate_locations(["2023"], logger=None)

        assert isinstance(result, ConsolidationResult)
        assert result.merged_count > 0
        assert "Montreal" in output_data
        assert "Toronto" in output_data

    def test_multi_year_consolidation(self, tmp_dir, sample_2023_locations, sample_2024_locations, monkeypatch):
        """Test consolidation across multiple years."""
        curation_dir = tmp_dir / "curation"
        curation_dir.mkdir(exist_ok=True)
        monkeypatch.setattr("dev.curation.consolidate.CURATION_DIR", curation_dir)

        import shutil
        shutil.copy(sample_2023_locations, curation_dir / "2023_locations_curation.yaml")
        shutil.copy(sample_2024_locations, curation_dir / "2024_locations_curation.yaml")

        result, output_data = consolidate_locations(["2023", "2024"], logger=None)

        assert result.years_processed == ["2023", "2024"]
        assert "Montreal" in output_data
        assert "Vancouver" in output_data

    def test_same_as_resolution(self, tmp_dir, sample_2023_locations, monkeypatch):
        """Test same_as resolution for locations."""
        monkeypatch.setattr("dev.curation.consolidate.CURATION_DIR", tmp_dir)

        result, output_data = consolidate_locations(["2023"], logger=None)

        # Park points to Library (both canonical: None, so use raw names)
        montreal_data = output_data["Montreal"]
        library_entry = montreal_data.get("Library")

        assert library_entry is not None
        assert "Park" in library_entry["raw_names"]

    def test_null_canonical_uses_raw_name(self, tmp_dir, sample_2023_locations, monkeypatch):
        """Test null canonical uses raw name for locations."""
        monkeypatch.setattr("dev.curation.consolidate.CURATION_DIR", tmp_dir)

        result, output_data = consolidate_locations(["2023"], logger=None)

        # Library has canonical: None, should use "Library"
        montreal_data = output_data["Montreal"]
        assert "Library" in montreal_data

    def test_skip_tracked_separately(self, tmp_dir, sample_2023_locations, monkeypatch):
        """Test skipped locations are tracked separately."""
        monkeypatch.setattr("dev.curation.consolidate.CURATION_DIR", tmp_dir)

        result, output_data = consolidate_locations(["2023"], logger=None)

        assert result.skipped_count > 0
        assert "_skipped" in output_data
        assert "Montreal" in output_data["_skipped"]
        assert "Museum" in output_data["_skipped"]["Montreal"]

    def test_dates_merged_by_year(self, tmp_dir, sample_2023_locations, sample_2024_locations, monkeypatch):
        """Test location dates are organized by year."""
        curation_dir = tmp_dir / "curation"
        curation_dir.mkdir(exist_ok=True)
        monkeypatch.setattr("dev.curation.consolidate.CURATION_DIR", curation_dir)

        import shutil
        shutil.copy(sample_2023_locations, curation_dir / "2023_locations_curation.yaml")
        shutil.copy(sample_2024_locations, curation_dir / "2024_locations_curation.yaml")

        result, output_data = consolidate_locations(["2023", "2024"], logger=None)

        # Café X appears in both years
        cafe_entry = output_data["Montreal"]["Café X"]
        assert "2023" in cafe_entry["dates"]
        assert "2024" in cafe_entry["dates"]


# =============================================================================
# Test consolidate_and_write
# =============================================================================

class TestConsolidateAndWrite:
    """Test consolidate_and_write function."""

    def test_write_people_file(self, tmp_dir, sample_2023_people, monkeypatch):
        """Test writing consolidated people file."""
        monkeypatch.setattr("dev.curation.consolidate.CURATION_DIR", tmp_dir)

        output_path = tmp_dir / "consolidated_people.yaml"
        result = consolidate_and_write(
            ["2023"],
            "people",
            output_path=output_path,
            logger=None
        )

        assert output_path.exists()
        assert result.output_path == str(output_path)

        # Verify file is valid YAML
        with open(output_path) as f:
            content = f.read()
            # Should have header
            assert "# Consolidated People Curation File" in content
            # Should be parseable
            f.seek(0)
            # Skip header lines
            yaml_content = "".join(
                line for line in f if not line.startswith("#") or line.strip() == "#"
            )
            data = yaml.safe_load(yaml_content)
            assert isinstance(data, dict)

    def test_write_locations_file(self, tmp_dir, sample_2023_locations, monkeypatch):
        """Test writing consolidated locations file."""
        monkeypatch.setattr("dev.curation.consolidate.CURATION_DIR", tmp_dir)

        output_path = tmp_dir / "consolidated_locations.yaml"
        result = consolidate_and_write(
            ["2023"],
            "locations",
            output_path=output_path,
            logger=None
        )

        assert output_path.exists()
        assert result.output_path == str(output_path)

            # Verify file is valid YAML
        with open(output_path) as f:
            content = f.read()
            assert "# Consolidated Locations Curation File" in content

    def test_default_output_path(self, tmp_dir, sample_2023_people, sample_2024_people, monkeypatch):
        """Test default output path generation."""
        curation_dir = tmp_dir / "curation"
        curation_dir.mkdir(exist_ok=True)
        monkeypatch.setattr("dev.curation.consolidate.CURATION_DIR", curation_dir)

        import shutil
        shutil.copy(sample_2023_people, curation_dir / "2023_people_curation.yaml")
        shutil.copy(sample_2024_people, curation_dir / "2024_people_curation.yaml")

        result = consolidate_and_write(
            ["2023", "2024"],
            "people",
            output_path=None,
            logger=None
        )

        # Should use CURATION_DIR with default filename
        expected_path = curation_dir / "2023-2024_people_curation.yaml"
        assert result.output_path == str(expected_path)
        assert expected_path.exists()

    def test_invalid_entity_type_raises(self, tmp_dir):
        """Test invalid entity type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid entity_type"):
            consolidate_and_write(
                ["2023"],
                "invalid",
                output_path=None,
                logger=None
            )

    def test_people_header_format(self, tmp_dir, sample_2023_people, monkeypatch):
        """Test people file has correct header format."""
        monkeypatch.setattr("dev.curation.consolidate.CURATION_DIR", tmp_dir)

        output_path = tmp_dir / "test.yaml"
        consolidate_and_write(["2023"], "people", output_path, None)

        with open(output_path) as f:
            content = f.read()
            assert "# Consolidated People Curation File" in content
            assert "# _skipped: entries to ignore" in content
            assert "# _self: author references" in content

    def test_locations_header_format(self, tmp_dir, sample_2023_locations, monkeypatch):
        """Test locations file has correct header format."""
        monkeypatch.setattr("dev.curation.consolidate.CURATION_DIR", tmp_dir)

        output_path = tmp_dir / "test.yaml"
        consolidate_and_write(["2023"], "locations", output_path, None)

        with open(output_path) as f:
            content = f.read()
            assert "# Consolidated Locations Curation File" in content
            assert "# _skipped: entries to ignore" in content


# =============================================================================
# Test load_yaml
# =============================================================================

class TestLoadYaml:
    """Test load_yaml function."""

    def test_load_valid_yaml(self, tmp_dir):
        """Test loading valid YAML file."""
        data = {"key": "value", "number": 42}
        path = tmp_dir / "test.yaml"
        with open(path, "w") as f:
            yaml.dump(data, f)

        result = load_yaml(path)
        assert result == data

    def test_load_empty_file_returns_empty_dict(self, tmp_dir):
        """Test loading empty file returns empty dict."""
        path = tmp_dir / "empty.yaml"
        path.write_text("")

        result = load_yaml(path)
        assert result == {}

    def test_load_none_yaml_returns_empty_dict(self, tmp_dir):
        """Test loading file with null returns empty dict."""
        path = tmp_dir / "null.yaml"
        path.write_text("null")

        result = load_yaml(path)
        assert result == {}

    def test_load_unicode_content(self, tmp_dir):
        """Test loading YAML with unicode content."""
        data = {"name": "Café", "city": "Montréal"}
        path = tmp_dir / "unicode.yaml"
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True)

        result = load_yaml(path)
        assert result == data
