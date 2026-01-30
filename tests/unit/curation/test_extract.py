#!/usr/bin/env python3
"""
test_extract.py
---------------
Unit tests for dev.curation.extract module.

Tests entity extraction from MD frontmatter and narrative_analysis YAML,
YAML generation for people and locations, and the full extraction pipeline.

Target Coverage: 95%+
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from datetime import date as date_type
from typing import Dict, Any

# --- Third-party imports ---
import pytest
import yaml

# --- Local imports ---
from dev.curation.extract import (
    extract_frontmatter,
    extract_from_md,
    extract_from_narrative_yaml,
    generate_people_yaml,
    generate_locations_yaml,
    write_yaml_file,
    extract_all,
    PeopleData,
    LocationsData,
)
from dev.curation.models import ExtractionStats


# =============================================================================
# Frontmatter Extraction Tests
# =============================================================================

class TestExtractFrontmatter:
    """Test extract_frontmatter function."""

    def test_valid_frontmatter(self, tmp_dir):
        """Test extracting valid YAML frontmatter."""
        content = """---
date: 2024-01-15
people:
  - Alice
  - Bob
locations:
  Montreal:
    - Cafe
---

# Entry content

Body text here.
"""
        md_file = tmp_dir / "test.md"
        md_file.write_text(content)

        result = extract_frontmatter(md_file)
        assert result is not None
        # YAML safe_load parses YYYY-MM-DD as date object
        assert result["date"] == date_type(2024, 1, 15)
        assert "Alice" in result["people"]
        assert "Bob" in result["people"]
        assert "Cafe" in result["locations"]["Montreal"]

    def test_frontmatter_with_date_object(self, tmp_dir):
        """Test frontmatter with Python date object."""
        data = {
            "date": date_type(2024, 1, 15),
            "people": ["Alice"],
        }
        content = f"---\n{yaml.dump(data)}---\n\nBody"
        md_file = tmp_dir / "test.md"
        md_file.write_text(content)

        result = extract_frontmatter(md_file)
        assert result is not None
        assert result["date"] == date_type(2024, 1, 15)

    def test_no_frontmatter(self, tmp_dir):
        """Test file without frontmatter."""
        content = "# Just a title\n\nNo frontmatter here."
        md_file = tmp_dir / "test.md"
        md_file.write_text(content)

        result = extract_frontmatter(md_file)
        assert result is None

    def test_malformed_yaml(self, tmp_dir):
        """Test file with malformed YAML frontmatter."""
        content = """---
date: 2024-01-15
people: [invalid yaml
---

Body
"""
        md_file = tmp_dir / "test.md"
        md_file.write_text(content)

        result = extract_frontmatter(md_file)
        assert result is None

    def test_empty_frontmatter(self, tmp_dir):
        """Test file with empty frontmatter."""
        content = """---
---

Body
"""
        md_file = tmp_dir / "test.md"
        md_file.write_text(content)

        result = extract_frontmatter(md_file)
        assert result is None or result == {}

    def test_missing_closing_delimiter(self, tmp_dir):
        """Test frontmatter without closing delimiter."""
        content = """---
date: 2024-01-15

Body without closing delimiter
"""
        md_file = tmp_dir / "test.md"
        md_file.write_text(content)

        result = extract_frontmatter(md_file)
        assert result is None

    def test_file_not_found(self, tmp_dir):
        """Test reading non-existent file."""
        md_file = tmp_dir / "nonexistent.md"
        result = extract_frontmatter(md_file)
        assert result is None

    def test_unicode_content(self, tmp_dir):
        """Test frontmatter with unicode characters."""
        content = """---
date: 2024-01-15
people:
  - María-José
  - François
locations:
  Montréal:
    - Café de l'Époque
---

Body
"""
        md_file = tmp_dir / "test.md"
        md_file.write_text(content, encoding="utf-8")

        result = extract_frontmatter(md_file)
        assert result is not None
        assert "María-José" in result["people"]
        assert "François" in result["people"]
        assert "Café de l'Époque" in result["locations"]["Montréal"]

    def test_special_characters(self, tmp_dir):
        """Test frontmatter with special characters."""
        content = """---
date: 2024-01-15
people:
  - "@Alice (Alice Smith)"
  - "Bob & Charlie"
locations:
  Montreal:
    - "Library (McGill)"
---

Body
"""
        md_file = tmp_dir / "test.md"
        md_file.write_text(content)

        result = extract_frontmatter(md_file)
        assert result is not None
        assert "@Alice (Alice Smith)" in result["people"]
        assert "Bob & Charlie" in result["people"]


# =============================================================================
# MD Extraction Tests
# =============================================================================

class TestExtractFromMd:
    """Test extract_from_md function."""

    def test_extract_people_from_md(self, tmp_dir):
        """Test extracting people from MD frontmatter."""
        content = """---
date: 2024-01-15
people:
  - Alice
  - Bob
---

Body
"""
        md_file = tmp_dir / "2024-01-15.md"
        md_file.write_text(content)

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_md(md_file, people_data, locations_data)

        assert "2024" in people_data
        assert "Alice" in people_data["2024"]
        assert "Bob" in people_data["2024"]
        assert "2024-01-15" in people_data["2024"]["Alice"]
        assert "2024-01-15" in people_data["2024"]["Bob"]

    def test_extract_locations_from_md(self, tmp_dir):
        """Test extracting locations from MD frontmatter."""
        content = """---
date: 2024-01-15
locations:
  Montreal:
    - Cafe
    - Library
  Toronto:
    - Museum
---

Body
"""
        md_file = tmp_dir / "2024-01-15.md"
        md_file.write_text(content)

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_md(md_file, people_data, locations_data)

        assert "2024" in locations_data
        assert "Montreal" in locations_data["2024"]
        assert "Toronto" in locations_data["2024"]
        assert "Cafe" in locations_data["2024"]["Montreal"]
        assert "Library" in locations_data["2024"]["Montreal"]
        assert "Museum" in locations_data["2024"]["Toronto"]

    def test_extract_with_date_object(self, tmp_dir):
        """Test extraction when date is a Python date object."""
        data = {
            "date": date_type(2024, 3, 20),
            "people": ["Alice"],
        }
        content = f"---\n{yaml.dump(data)}---\n\nBody"
        md_file = tmp_dir / "test.md"
        md_file.write_text(content)

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_md(md_file, people_data, locations_data)

        assert "2024" in people_data
        assert "Alice" in people_data["2024"]
        assert "2024-03-20" in people_data["2024"]["Alice"]

    def test_extract_without_date_uses_filename(self, tmp_dir):
        """Test extraction falls back to filename when date missing."""
        content = """---
people:
  - Alice
---

Body
"""
        md_file = tmp_dir / "2024-01-15.md"
        md_file.write_text(content)

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_md(md_file, people_data, locations_data)

        assert "2024" in people_data
        assert "Alice" in people_data["2024"]
        assert "2024-01-15" in people_data["2024"]["Alice"]

    def test_extract_handles_invalid_year(self, tmp_dir):
        """Test extraction with invalid date format."""
        content = """---
date: invalid
people:
  - Alice
---

Body
"""
        md_file = tmp_dir / "test.md"
        md_file.write_text(content)

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_md(md_file, people_data, locations_data)

        # Should use first 4 chars "inva" as year or "unknown"
        assert "inva" in people_data or "unknown" in people_data

    def test_extract_empty_lists_ignored(self, tmp_dir):
        """Test extraction ignores empty people/locations lists."""
        content = """---
date: 2024-01-15
people: []
locations: {}
---

Body
"""
        md_file = tmp_dir / "2024-01-15.md"
        md_file.write_text(content)

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_md(md_file, people_data, locations_data)

        # Year key may be created but should have no data
        if "2024" in people_data:
            assert len(people_data["2024"]) == 0
        if "2024" in locations_data:
            assert len(locations_data["2024"]) == 0

    def test_extract_null_entries_skipped(self, tmp_dir):
        """Test extraction skips null entries."""
        content = """---
date: 2024-01-15
people:
  - Alice
  - null
  - Bob
locations:
  Montreal:
    - Cafe
    - null
---

Body
"""
        md_file = tmp_dir / "2024-01-15.md"
        md_file.write_text(content)

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_md(md_file, people_data, locations_data)

        assert "Alice" in people_data["2024"]
        assert "Bob" in people_data["2024"]
        assert len(people_data["2024"]) == 2  # null excluded

    def test_extract_locations_with_string_value(self, tmp_dir):
        """Test extraction when location is a string instead of list."""
        content = """---
date: 2024-01-15
locations:
  Montreal: Cafe
---

Body
"""
        md_file = tmp_dir / "2024-01-15.md"
        md_file.write_text(content)

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_md(md_file, people_data, locations_data)

        assert "2024" in locations_data
        assert "Montreal" in locations_data["2024"]
        assert "Cafe" in locations_data["2024"]["Montreal"]

    def test_extract_no_frontmatter(self, tmp_dir):
        """Test extraction from file without frontmatter."""
        content = "# Just a title\n\nNo frontmatter."
        md_file = tmp_dir / "test.md"
        md_file.write_text(content)

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_md(md_file, people_data, locations_data)

        assert len(people_data) == 0
        assert len(locations_data) == 0

    def test_extract_accumulates_multiple_files(self, tmp_dir):
        """Test extraction accumulates data from multiple files."""
        content1 = """---
date: 2024-01-15
people:
  - Alice
---
"""
        content2 = """---
date: 2024-01-16
people:
  - Alice
  - Bob
---
"""
        md_file1 = tmp_dir / "2024-01-15.md"
        md_file2 = tmp_dir / "2024-01-16.md"
        md_file1.write_text(content1)
        md_file2.write_text(content2)

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_md(md_file1, people_data, locations_data)
        extract_from_md(md_file2, people_data, locations_data)

        assert "Alice" in people_data["2024"]
        assert "Bob" in people_data["2024"]
        assert len(people_data["2024"]["Alice"]) == 2  # 2 dates
        assert len(people_data["2024"]["Bob"]) == 1  # 1 date


# =============================================================================
# Narrative YAML Extraction Tests
# =============================================================================

class TestExtractFromNarrativeYaml:
    """Test extract_from_narrative_yaml function."""

    def test_extract_from_scenes(self, tmp_dir):
        """Test extracting people and locations from scenes."""
        data = {
            "date": "2024-01-15",
            "city": "Montreal",
            "scenes": [
                {
                    "name": "Morning Coffee",
                    "people": ["Alice", "Bob"],
                    "locations": ["Cafe"],
                },
                {
                    "name": "Afternoon Walk",
                    "people": ["Charlie"],
                    "locations": ["Park", "Bridge"],
                },
            ],
        }
        yaml_file = tmp_dir / "2024-01-15_analysis.yaml"
        yaml_file.write_text(yaml.dump(data))

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_narrative_yaml(yaml_file, people_data, locations_data)

        assert "2024" in people_data
        assert "Alice" in people_data["2024"]
        assert "Bob" in people_data["2024"]
        assert "Charlie" in people_data["2024"]

        assert "2024" in locations_data
        assert "Montreal" in locations_data["2024"]
        assert "Cafe" in locations_data["2024"]["Montreal"]
        assert "Park" in locations_data["2024"]["Montreal"]
        assert "Bridge" in locations_data["2024"]["Montreal"]

    def test_extract_from_threads(self, tmp_dir):
        """Test extracting people and locations from threads."""
        data = {
            "date": "2024-01-15",
            "city": "Montreal",
            "threads": [
                {
                    "name": "Memory Thread",
                    "people": ["Alice"],
                    "locations": ["Library"],
                },
            ],
        }
        yaml_file = tmp_dir / "2024-01-15_analysis.yaml"
        yaml_file.write_text(yaml.dump(data))

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_narrative_yaml(yaml_file, people_data, locations_data)

        assert "Alice" in people_data["2024"]
        assert "Library" in locations_data["2024"]["Montreal"]

    def test_extract_with_date_object(self, tmp_dir):
        """Test extraction when date is a Python date object."""
        data = {
            "date": date_type(2024, 3, 20),
            "city": "Montreal",
            "scenes": [{"people": ["Alice"]}],
        }
        yaml_file = tmp_dir / "test.yaml"
        yaml_file.write_text(yaml.dump(data))

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_narrative_yaml(yaml_file, people_data, locations_data)

        assert "2024" in people_data
        assert "2024-03-20" in people_data["2024"]["Alice"]

    def test_extract_without_date_uses_filename(self, tmp_dir):
        """Test extraction falls back to filename for date."""
        data = {
            "city": "Montreal",
            "scenes": [{"people": ["Alice"]}],
        }
        yaml_file = tmp_dir / "2024-01-15_analysis.yaml"
        yaml_file.write_text(yaml.dump(data))

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_narrative_yaml(yaml_file, people_data, locations_data)

        assert "2024" in people_data
        assert "2024-01-15" in people_data["2024"]["Alice"]

    def test_extract_without_city_uses_unassigned(self, tmp_dir):
        """Test extraction uses _unassigned when city missing."""
        data = {
            "date": "2024-01-15",
            "scenes": [{"locations": ["Unknown Place"]}],
        }
        yaml_file = tmp_dir / "test.yaml"
        yaml_file.write_text(yaml.dump(data))

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_narrative_yaml(yaml_file, people_data, locations_data)

        assert "_unassigned" in locations_data["2024"]
        assert "Unknown Place" in locations_data["2024"]["_unassigned"]

    def test_extract_malformed_yaml(self, tmp_dir):
        """Test extraction from malformed YAML file."""
        yaml_file = tmp_dir / "invalid.yaml"
        yaml_file.write_text("invalid: yaml: [")

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_narrative_yaml(yaml_file, people_data, locations_data)

        # Should handle gracefully
        assert len(people_data) == 0
        assert len(locations_data) == 0

    def test_extract_malformed_yaml_with_logger(self, tmp_dir):
        """Test extraction from malformed YAML logs warning with logger."""
        from dev.core.logging_manager import PalimpsestLogger

        yaml_file = tmp_dir / "invalid.yaml"
        yaml_file.write_text("invalid: yaml: [")

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        # Create logger
        log_dir = tmp_dir / "logs"
        log_dir.mkdir()
        logger = PalimpsestLogger(log_dir, component_name="test")

        extract_from_narrative_yaml(yaml_file, people_data, locations_data, logger)

        # Should handle gracefully and log warning
        assert len(people_data) == 0
        assert len(locations_data) == 0

    def test_extract_empty_file(self, tmp_dir):
        """Test extraction from empty YAML file."""
        yaml_file = tmp_dir / "empty.yaml"
        yaml_file.write_text("")

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_narrative_yaml(yaml_file, people_data, locations_data)

        assert len(people_data) == 0
        assert len(locations_data) == 0

    def test_extract_null_scenes(self, tmp_dir):
        """Test extraction when scenes is null."""
        data = {
            "date": "2024-01-15",
            "city": "Montreal",
            "scenes": None,
        }
        yaml_file = tmp_dir / "test.yaml"
        yaml_file.write_text(yaml.dump(data))

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_narrative_yaml(yaml_file, people_data, locations_data)

        assert len(people_data) == 0
        assert len(locations_data) == 0

    def test_extract_scene_not_dict(self, tmp_dir):
        """Test extraction when scene is not a dict."""
        data = {
            "date": "2024-01-15",
            "city": "Montreal",
            "scenes": ["not a dict", {"people": ["Alice"]}],
        }
        yaml_file = tmp_dir / "test.yaml"
        yaml_file.write_text(yaml.dump(data))

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_narrative_yaml(yaml_file, people_data, locations_data)

        # Should skip invalid scene but process valid one
        assert "Alice" in people_data["2024"]

    def test_extract_empty_people_locations_lists(self, tmp_dir):
        """Test extraction with empty people/locations lists."""
        data = {
            "date": "2024-01-15",
            "city": "Montreal",
            "scenes": [{"people": [], "locations": []}],
        }
        yaml_file = tmp_dir / "test.yaml"
        yaml_file.write_text(yaml.dump(data))

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_narrative_yaml(yaml_file, people_data, locations_data)

        assert len(people_data) == 0
        assert len(locations_data) == 0


# =============================================================================
# YAML Generation Tests
# =============================================================================

class TestGeneratePeopleYaml:
    """Test generate_people_yaml function."""

    def test_generate_basic_structure(self):
        """Test generating basic people YAML structure."""
        year_data = {
            "Alice": {"2024-01-15", "2024-01-16"},
            "Bob": {"2024-01-20"},
        }

        result = generate_people_yaml(year_data)

        assert "Alice" in result
        assert "Bob" in result
        assert result["Alice"]["dates"] == ["2024-01-15", "2024-01-16"]
        assert result["Bob"]["dates"] == ["2024-01-20"]
        assert result["Alice"]["canonical"]["name"] is None
        assert result["Alice"]["canonical"]["lastname"] is None
        assert result["Alice"]["canonical"]["alias"] is None

    def test_generate_alphabetical_sorting(self):
        """Test entries are sorted alphabetically."""
        year_data = {
            "Charlie": {"2024-01-01"},
            "Alice": {"2024-01-02"},
            "Bob": {"2024-01-03"},
        }

        result = generate_people_yaml(year_data)

        keys = list(result.keys())
        assert keys == ["Alice", "Bob", "Charlie"]

    def test_generate_case_insensitive_sorting(self):
        """Test sorting is case-insensitive."""
        year_data = {
            "charlie": {"2024-01-01"},
            "Alice": {"2024-01-02"},
            "BOB": {"2024-01-03"},
        }

        result = generate_people_yaml(year_data)

        keys = list(result.keys())
        assert keys == ["Alice", "BOB", "charlie"]

    def test_generate_dates_sorted(self):
        """Test dates are sorted within each entry."""
        year_data = {
            "Alice": {"2024-03-15", "2024-01-10", "2024-02-20"},
        }

        result = generate_people_yaml(year_data)

        assert result["Alice"]["dates"] == ["2024-01-10", "2024-02-20", "2024-03-15"]

    def test_generate_empty_data(self):
        """Test generating YAML from empty data."""
        year_data: Dict[str, Any] = {}

        result = generate_people_yaml(year_data)

        assert result == {}

    def test_generate_unicode_names(self):
        """Test generating YAML with unicode names."""
        year_data = {
            "María-José": {"2024-01-15"},
            "François": {"2024-01-16"},
        }

        result = generate_people_yaml(year_data)

        assert "María-José" in result
        assert "François" in result


class TestGenerateLocationsYaml:
    """Test generate_locations_yaml function."""

    def test_generate_basic_structure(self):
        """Test generating basic locations YAML structure."""
        year_data = {
            "Montreal": {
                "Cafe": {"2024-01-15", "2024-01-16"},
                "Library": {"2024-01-20"},
            },
            "Toronto": {
                "Museum": {"2024-02-01"},
            },
        }

        result = generate_locations_yaml(year_data)

        assert "Montreal" in result
        assert "Toronto" in result
        assert "Cafe" in result["Montreal"]
        assert "Library" in result["Montreal"]
        assert "Museum" in result["Toronto"]
        assert result["Montreal"]["Cafe"]["dates"] == ["2024-01-15", "2024-01-16"]
        assert result["Montreal"]["Cafe"]["canonical"] is None

    def test_generate_alphabetical_sorting_cities(self):
        """Test cities are sorted alphabetically."""
        year_data = {
            "Toronto": {"Museum": {"2024-01-01"}},
            "Montreal": {"Cafe": {"2024-01-02"}},
            "Vancouver": {"Park": {"2024-01-03"}},
        }

        result = generate_locations_yaml(year_data)

        keys = list(result.keys())
        assert keys == ["Montreal", "Toronto", "Vancouver"]

    def test_generate_alphabetical_sorting_locations(self):
        """Test locations within city are sorted alphabetically."""
        year_data = {
            "Montreal": {
                "Park": {"2024-01-01"},
                "Cafe": {"2024-01-02"},
                "Library": {"2024-01-03"},
            },
        }

        result = generate_locations_yaml(year_data)

        keys = list(result["Montreal"].keys())
        assert keys == ["Cafe", "Library", "Park"]

    def test_generate_dates_sorted(self):
        """Test dates are sorted within each location."""
        year_data = {
            "Montreal": {
                "Cafe": {"2024-03-15", "2024-01-10", "2024-02-20"},
            },
        }

        result = generate_locations_yaml(year_data)

        assert result["Montreal"]["Cafe"]["dates"] == [
            "2024-01-10",
            "2024-02-20",
            "2024-03-15",
        ]

    def test_generate_empty_data(self):
        """Test generating YAML from empty data."""
        year_data: Dict[str, Any] = {}

        result = generate_locations_yaml(year_data)

        assert result == {}

    def test_generate_unicode_names(self):
        """Test generating YAML with unicode names."""
        year_data = {
            "Montréal": {
                "Café de l'Époque": {"2024-01-15"},
            },
        }

        result = generate_locations_yaml(year_data)

        assert "Montréal" in result
        assert "Café de l'Époque" in result["Montréal"]


class TestWriteYamlFile:
    """Test write_yaml_file function."""

    def test_write_basic_file(self, tmp_dir):
        """Test writing basic YAML file with header."""
        data = {"key": "value", "number": 42}
        header = "# Test header\n# Line 2"
        output_path = tmp_dir / "output.yaml"

        write_yaml_file(output_path, data, header)

        assert output_path.exists()
        content = output_path.read_text()
        assert "# Test header" in content
        assert "# Line 2" in content
        assert "key: value" in content
        assert "number: 42" in content

    def test_write_preserves_order(self, tmp_dir):
        """Test writing preserves dictionary order."""
        data = {
            "first": 1,
            "second": 2,
            "third": 3,
        }
        header = "# Header"
        output_path = tmp_dir / "output.yaml"

        write_yaml_file(output_path, data, header)

        content = output_path.read_text()
        # Should preserve insertion order
        first_idx = content.index("first:")
        second_idx = content.index("second:")
        third_idx = content.index("third:")
        assert first_idx < second_idx < third_idx

    def test_write_unicode_content(self, tmp_dir):
        """Test writing unicode content."""
        data = {"name": "María-José", "city": "Montréal"}
        header = "# Header"
        output_path = tmp_dir / "output.yaml"

        write_yaml_file(output_path, data, header)

        content = output_path.read_text(encoding="utf-8")
        assert "María-José" in content
        assert "Montréal" in content


# =============================================================================
# Full Extraction Tests
# =============================================================================

class TestExtractAll:
    """Test extract_all function."""

    def setup_test_files(self, tmp_dir):
        """Helper to set up test MD and YAML files."""
        # Create MD directory structure
        md_dir = tmp_dir / "md"
        md_dir.mkdir(parents=True)
        (md_dir / "2023").mkdir()
        (md_dir / "2024").mkdir()

        # Create MD files
        md_content_2023 = """---
date: 2023-01-15
people:
  - Alice
locations:
  Montreal:
    - Cafe
---
"""
        md_content_2024 = """---
date: 2024-01-20
people:
  - Alice
  - Bob
locations:
  Montreal:
    - Library
  Toronto:
    - Museum
---
"""
        (md_dir / "2023" / "2023-01-15.md").write_text(md_content_2023)
        (md_dir / "2024" / "2024-01-20.md").write_text(md_content_2024)

        # Create narrative_analysis directory structure
        narrative_dir = tmp_dir / "narrative_analysis"
        narrative_dir.mkdir(parents=True)

        # Create narrative YAML files
        narrative_data_2023 = {
            "date": "2023-06-10",
            "city": "Montreal",
            "scenes": [{"people": ["Charlie"], "locations": ["Park"]}],
        }
        narrative_data_2024 = {
            "date": "2024-03-15",
            "city": "Toronto",
            "scenes": [{"people": ["Alice"], "locations": ["Museum"]}],
        }
        (narrative_dir / "2023-06-10_analysis.yaml").write_text(
            yaml.dump(narrative_data_2023)
        )
        (narrative_dir / "2024-03-15_analysis.yaml").write_text(
            yaml.dump(narrative_data_2024)
        )

        # Create curation output directory
        curation_dir = tmp_dir / "curation"
        curation_dir.mkdir(parents=True)

        return md_dir, narrative_dir, curation_dir

    def test_extract_all_dry_run(self, tmp_dir, monkeypatch):
        """Test extract_all in dry run mode."""
        md_dir, narrative_dir, curation_dir = self.setup_test_files(tmp_dir)

        monkeypatch.setattr("dev.curation.extract.MD_DIR", md_dir)
        monkeypatch.setattr("dev.curation.extract.NARRATIVE_ANALYSIS_DIR", narrative_dir)
        monkeypatch.setattr("dev.curation.extract.CURATION_DIR", curation_dir)

        stats = extract_all(dry_run=True)

        assert stats.files_scanned_md == 2
        assert stats.files_scanned_yaml == 2
        assert stats.people_count > 0
        assert stats.locations_count > 0
        assert len(stats.years_found) == 2
        assert "2023" in stats.years_found
        assert "2024" in stats.years_found

        # No files should be written in dry run
        assert len(list(curation_dir.glob("*.yaml"))) == 0

    def test_extract_all_writes_files(self, tmp_dir, monkeypatch):
        """Test extract_all writes output files."""
        md_dir, narrative_dir, curation_dir = self.setup_test_files(tmp_dir)

        monkeypatch.setattr("dev.curation.extract.MD_DIR", md_dir)
        monkeypatch.setattr("dev.curation.extract.NARRATIVE_ANALYSIS_DIR", narrative_dir)
        monkeypatch.setattr("dev.curation.extract.CURATION_DIR", curation_dir)
        monkeypatch.setattr("dev.curation.extract.LOG_DIR", tmp_dir / "logs")

        stats = extract_all(dry_run=False)

        assert stats.files_scanned_md == 2
        assert stats.files_scanned_yaml == 2

        # Check files were created
        assert (curation_dir / "2023_people_curation.yaml").exists()
        assert (curation_dir / "2024_people_curation.yaml").exists()
        assert (curation_dir / "2023_locations_curation.yaml").exists()
        assert (curation_dir / "2024_locations_curation.yaml").exists()

    def test_extract_all_file_contents(self, tmp_dir, monkeypatch):
        """Test extract_all file contents are correct."""
        md_dir, narrative_dir, curation_dir = self.setup_test_files(tmp_dir)

        monkeypatch.setattr("dev.curation.extract.MD_DIR", md_dir)
        monkeypatch.setattr("dev.curation.extract.NARRATIVE_ANALYSIS_DIR", narrative_dir)
        monkeypatch.setattr("dev.curation.extract.CURATION_DIR", curation_dir)
        monkeypatch.setattr("dev.curation.extract.LOG_DIR", tmp_dir / "logs")

        stats = extract_all(dry_run=False)

        # Read and verify people file
        people_2024 = yaml.safe_load(
            (curation_dir / "2024_people_curation.yaml").read_text()
        )
        assert "Alice" in people_2024
        assert "Bob" in people_2024
        assert people_2024["Alice"]["canonical"]["name"] is None
        assert "2024-01-20" in people_2024["Alice"]["dates"]

        # Read and verify locations file
        locations_2024 = yaml.safe_load(
            (curation_dir / "2024_locations_curation.yaml").read_text()
        )
        assert "Montreal" in locations_2024
        assert "Toronto" in locations_2024
        assert "Library" in locations_2024["Montreal"]
        assert "Museum" in locations_2024["Toronto"]

    def test_extract_all_statistics(self, tmp_dir, monkeypatch):
        """Test extract_all returns correct statistics."""
        md_dir, narrative_dir, curation_dir = self.setup_test_files(tmp_dir)

        monkeypatch.setattr("dev.curation.extract.MD_DIR", md_dir)
        monkeypatch.setattr("dev.curation.extract.NARRATIVE_ANALYSIS_DIR", narrative_dir)
        monkeypatch.setattr("dev.curation.extract.CURATION_DIR", curation_dir)
        monkeypatch.setattr("dev.curation.extract.LOG_DIR", tmp_dir / "logs")

        stats = extract_all(dry_run=False)

        # Verify counts
        assert stats.people_by_year["2023"] > 0
        assert stats.people_by_year["2024"] > 0
        assert stats.locations_by_year["2023"] > 0
        assert stats.locations_by_year["2024"] > 0

        # Verify summary
        summary = stats.summary()
        assert "2 MD files" in summary
        assert "2 YAML files" in summary

    def test_extract_all_skips_underscore_files(self, tmp_dir, monkeypatch):
        """Test extract_all skips narrative_analysis files starting with underscore."""
        md_dir, narrative_dir, curation_dir = self.setup_test_files(tmp_dir)

        # Add a file starting with underscore
        (narrative_dir / "_template.yaml").write_text(
            yaml.dump({"date": "2024-01-01", "scenes": [{"people": ["Test"]}]})
        )

        monkeypatch.setattr("dev.curation.extract.MD_DIR", md_dir)
        monkeypatch.setattr("dev.curation.extract.NARRATIVE_ANALYSIS_DIR", narrative_dir)
        monkeypatch.setattr("dev.curation.extract.CURATION_DIR", curation_dir)
        monkeypatch.setattr("dev.curation.extract.LOG_DIR", tmp_dir / "logs")

        stats = extract_all(dry_run=False)

        # Should still be 2, not 3
        assert stats.files_scanned_yaml == 2

    def test_extract_all_empty_directories(self, tmp_dir, monkeypatch):
        """Test extract_all with empty source directories."""
        md_dir = tmp_dir / "md"
        narrative_dir = tmp_dir / "narrative_analysis"
        curation_dir = tmp_dir / "curation"
        md_dir.mkdir()
        narrative_dir.mkdir()
        curation_dir.mkdir()

        monkeypatch.setattr("dev.curation.extract.MD_DIR", md_dir)
        monkeypatch.setattr("dev.curation.extract.NARRATIVE_ANALYSIS_DIR", narrative_dir)
        monkeypatch.setattr("dev.curation.extract.CURATION_DIR", curation_dir)
        monkeypatch.setattr("dev.curation.extract.LOG_DIR", tmp_dir / "logs")

        stats = extract_all(dry_run=False)

        assert stats.files_scanned_md == 0
        assert stats.files_scanned_yaml == 0
        assert stats.people_count == 0
        assert stats.locations_count == 0
        assert len(stats.years_found) == 0


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and complex scenarios."""

    def test_same_person_multiple_dates(self, tmp_dir):
        """Test same person appearing on multiple dates accumulates."""
        content1 = """---
date: 2024-01-15
people:
  - Alice
---
"""
        content2 = """---
date: 2024-01-20
people:
  - Alice
---
"""
        md_file1 = tmp_dir / "2024-01-15.md"
        md_file2 = tmp_dir / "2024-01-20.md"
        md_file1.write_text(content1)
        md_file2.write_text(content2)

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_md(md_file1, people_data, locations_data)
        extract_from_md(md_file2, people_data, locations_data)

        assert "Alice" in people_data["2024"]
        assert len(people_data["2024"]["Alice"]) == 2
        assert "2024-01-15" in people_data["2024"]["Alice"]
        assert "2024-01-20" in people_data["2024"]["Alice"]

    def test_cross_year_entities(self, tmp_dir):
        """Test entities appearing across multiple years."""
        content_2023 = """---
date: 2023-12-31
people:
  - Alice
---
"""
        content_2024 = """---
date: 2024-01-01
people:
  - Alice
---
"""
        md_file1 = tmp_dir / "2023-12-31.md"
        md_file2 = tmp_dir / "2024-01-01.md"
        md_file1.write_text(content_2023)
        md_file2.write_text(content_2024)

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_md(md_file1, people_data, locations_data)
        extract_from_md(md_file2, people_data, locations_data)

        assert "2023" in people_data
        assert "2024" in people_data
        assert "Alice" in people_data["2023"]
        assert "Alice" in people_data["2024"]

    def test_mixed_md_and_yaml_sources(self, tmp_dir):
        """Test extraction from both MD and narrative YAML sources."""
        # MD file
        md_content = """---
date: 2024-01-15
people:
  - Alice
locations:
  Montreal:
    - Cafe
---
"""
        md_file = tmp_dir / "2024-01-15.md"
        md_file.write_text(md_content)

        # YAML file
        yaml_data = {
            "date": "2024-01-15",
            "city": "Montreal",
            "scenes": [{"people": ["Bob"], "locations": ["Library"]}],
        }
        yaml_file = tmp_dir / "2024-01-15_analysis.yaml"
        yaml_file.write_text(yaml.dump(yaml_data))

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_md(md_file, people_data, locations_data)
        extract_from_narrative_yaml(yaml_file, people_data, locations_data)

        # Should have both sources
        assert "Alice" in people_data["2024"]
        assert "Bob" in people_data["2024"]
        assert "Cafe" in locations_data["2024"]["Montreal"]
        assert "Library" in locations_data["2024"]["Montreal"]

    def test_duplicate_dates_deduplicated(self, tmp_dir):
        """Test duplicate dates for same entity are deduplicated."""
        yaml_data = {
            "date": "2024-01-15",
            "city": "Montreal",
            "scenes": [
                {"people": ["Alice"]},
                {"people": ["Alice"]},  # Duplicate
            ],
        }
        yaml_file = tmp_dir / "test.yaml"
        yaml_file.write_text(yaml.dump(yaml_data))

        people_data: PeopleData = {}
        locations_data: LocationsData = {}

        extract_from_narrative_yaml(yaml_file, people_data, locations_data)

        # Should only have one date (sets deduplicate)
        assert len(people_data["2024"]["Alice"]) == 1
        assert "2024-01-15" in people_data["2024"]["Alice"]

    def test_extraction_stats_summary(self):
        """Test ExtractionStats summary method."""
        stats = ExtractionStats()
        assert "0 MD files" in stats.summary()
        assert "0 YAML files" in stats.summary()

        stats.files_scanned_md = 100
        stats.files_scanned_yaml = 50
        stats.people_count = 42
        stats.locations_count = 17
        stats.years_found = {"2023", "2024"}

        summary = stats.summary()
        assert "100 MD files" in summary
        assert "50 YAML files" in summary
        assert "42 people" in summary
        assert "17 locations" in summary
        assert "2 years" in summary
