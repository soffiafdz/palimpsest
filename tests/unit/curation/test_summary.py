"""
test_summary.py
---------------
Unit tests for dev.curation.summary module.

Tests frequency-based summary report generation for curated entities,
including aggregation functions, sorting options, and report formatting.

Target Coverage: 95%+
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from typing import Dict

# --- Third-party imports ---
import pytest
import yaml

# --- Local imports ---
from dev.curation.summary import (
    load_yaml,
    extract_year,
    format_year_breakdown,
    total_count,
    aggregate_people,
    aggregate_locations,
    format_people_report,
    format_locations_report,
    generate_summary,
)
from dev.curation.models import SummaryData


# =============================================================================
# Test Utilities
# =============================================================================

class TestLoadYaml:
    """Test load_yaml function."""

    def test_load_valid_yaml(self, tmp_dir):
        """Test loading a valid YAML file."""
        yaml_file = tmp_dir / "test.yaml"
        data = {"name": "Alice", "count": 5}
        yaml_file.write_text(yaml.dump(data))

        result = load_yaml(yaml_file)
        assert result == data

    def test_load_empty_yaml(self, tmp_dir):
        """Test loading an empty YAML file returns empty dict."""
        yaml_file = tmp_dir / "empty.yaml"
        yaml_file.write_text("")

        result = load_yaml(yaml_file)
        assert result == {}

    def test_load_nested_yaml(self, tmp_dir):
        """Test loading nested YAML structure."""
        yaml_file = tmp_dir / "nested.yaml"
        data = {
            "Montreal": {
                "Cafe X": {"dates": ["2024-01-15", "2024-02-20"]},
                "Library": {"dates": ["2024-03-10"]},
            }
        }
        yaml_file.write_text(yaml.dump(data))

        result = load_yaml(yaml_file)
        assert result == data


class TestExtractYear:
    """Test extract_year function."""

    def test_extract_year_from_people_curation(self, tmp_dir):
        """Test extracting year from people curation filename."""
        path = tmp_dir / "2024_people_curation.yaml"
        assert extract_year(path) == "2024"

    def test_extract_year_from_locations_curation(self, tmp_dir):
        """Test extracting year from locations curation filename."""
        path = tmp_dir / "2025_locations_curation.yaml"
        assert extract_year(path) == "2025"

    def test_extract_year_different_format(self, tmp_dir):
        """Test extracting year from different naming pattern."""
        path = tmp_dir / "2023_entities.yaml"
        assert extract_year(path) == "2023"


class TestFormatYearBreakdown:
    """Test format_year_breakdown function."""

    def test_single_year(self):
        """Test formatting single year count."""
        year_counts = {"2024": 10}
        result = format_year_breakdown(year_counts)
        assert result == "2024(10)"

    def test_multiple_years_sorted_descending(self):
        """Test multiple years sorted descending."""
        year_counts = {"2023": 5, "2025": 18, "2024": 23}
        result = format_year_breakdown(year_counts)
        assert result == "2025(18), 2024(23), 2023(5)"

    def test_empty_dict(self):
        """Test empty year counts."""
        result = format_year_breakdown({})
        assert result == ""


class TestTotalCount:
    """Test total_count function."""

    def test_single_year_count(self):
        """Test summing single year."""
        year_counts = {"2024": 10}
        assert total_count(year_counts) == 10

    def test_multiple_years(self):
        """Test summing multiple years."""
        year_counts = {"2023": 5, "2024": 23, "2025": 18}
        assert total_count(year_counts) == 46

    def test_empty_counts(self):
        """Test summing empty dict."""
        assert total_count({}) == 0


# =============================================================================
# Test Aggregation Functions
# =============================================================================

class TestAggregatePeople:
    """Test aggregate_people function."""

    @pytest.fixture
    def people_curation_2024(self, tmp_dir):
        """Create 2024 people curation file."""
        curation_dir = tmp_dir / "curation"
        curation_dir.mkdir()

        path = curation_dir / "2024_people_curation.yaml"
        data = {
            "Alice": {
                "canonical": "Alice Johnson",
                "dates": ["2024-01-15", "2024-02-20", "2024-03-10"],
            },
            "Bob": {
                "canonical": "Bob Smith",
                "dates": ["2024-01-15"],
            },
            "Clara": {
                "canonical": "Clara Martinez",
                "dates": ["2024-05-01", "2024-06-15"],
            },
        }
        path.write_text(yaml.dump(data))
        return curation_dir

    @pytest.fixture
    def people_curation_2025(self, tmp_dir):
        """Create 2025 people curation file."""
        curation_dir = tmp_dir / "curation"
        curation_dir.mkdir(exist_ok=True)

        path = curation_dir / "2025_people_curation.yaml"
        data = {
            "Alice": {
                "canonical": "Alice Johnson",
                "dates": ["2025-01-10", "2025-01-20"],
            },
            "David": {
                "canonical": "David Lee",
                "dates": ["2025-02-05"],
            },
        }
        path.write_text(yaml.dump(data))
        return curation_dir

    def test_aggregate_single_year(self, people_curation_2024, monkeypatch):
        """Test aggregating people from single year."""
        monkeypatch.setattr("dev.curation.summary.CURATION_DIR", people_curation_2024)

        result = aggregate_people()

        assert result.entity_type == "people"
        assert result.total_unique == 3
        assert "Alice" in result.by_name
        assert "Bob" in result.by_name
        assert "Clara" in result.by_name
        assert result.by_name["Alice"]["2024"] == 3
        assert result.by_name["Bob"]["2024"] == 1
        assert result.by_name["Clara"]["2024"] == 2

    def test_aggregate_multiple_years(self, people_curation_2024, people_curation_2025, monkeypatch):
        """Test aggregating people from multiple years."""
        curation_dir = people_curation_2024  # Same dir contains both files
        monkeypatch.setattr("dev.curation.summary.CURATION_DIR", curation_dir)

        result = aggregate_people()

        assert result.total_unique == 4
        assert "Alice" in result.by_name
        assert result.by_name["Alice"]["2024"] == 3
        assert result.by_name["Alice"]["2025"] == 2
        assert "David" in result.by_name
        assert result.by_name["David"]["2025"] == 1

    def test_aggregate_empty_directory(self, tmp_dir, monkeypatch):
        """Test aggregating with no curation files."""
        empty_dir = tmp_dir / "empty"
        empty_dir.mkdir()
        monkeypatch.setattr("dev.curation.summary.CURATION_DIR", empty_dir)

        result = aggregate_people()

        assert result.total_unique == 0
        assert result.by_name == {}

    def test_aggregate_skips_invalid_entries(self, tmp_dir, monkeypatch):
        """Test aggregation skips entries without dates field."""
        curation_dir = tmp_dir / "curation"
        curation_dir.mkdir()

        path = curation_dir / "2024_people_curation.yaml"
        data = {
            "Alice": {
                "canonical": "Alice Johnson",
                "dates": ["2024-01-15"],
            },
            "Invalid": "not a dict",  # Invalid entry
            "NoDate": {
                "canonical": "No Date Person",
                # Missing dates field
            },
        }
        path.write_text(yaml.dump(data))
        monkeypatch.setattr("dev.curation.summary.CURATION_DIR", curation_dir)

        result = aggregate_people()

        assert result.total_unique == 1
        assert "Alice" in result.by_name
        assert "Invalid" not in result.by_name
        assert "NoDate" not in result.by_name


class TestAggregateLocations:
    """Test aggregate_locations function."""

    @pytest.fixture
    def locations_curation_2024(self, tmp_dir):
        """Create 2024 locations curation file."""
        curation_dir = tmp_dir / "curation"
        curation_dir.mkdir()

        path = curation_dir / "2024_locations_curation.yaml"
        data = {
            "Montreal": {
                "Cafe X": {
                    "canonical": "Cafe Experience",
                    "dates": ["2024-01-15", "2024-02-20"],
                },
                "Library": {
                    "canonical": "McGill Library",
                    "dates": ["2024-03-10"],
                },
            },
            "Toronto": {
                "Museum": {
                    "canonical": "Royal Ontario Museum",
                    "dates": ["2024-04-05"],
                },
            },
        }
        path.write_text(yaml.dump(data))
        return curation_dir

    @pytest.fixture
    def locations_curation_2025(self, tmp_dir):
        """Create 2025 locations curation file."""
        curation_dir = tmp_dir / "curation"
        curation_dir.mkdir(exist_ok=True)

        path = curation_dir / "2025_locations_curation.yaml"
        data = {
            "Montreal": {
                "Cafe X": {
                    "canonical": "Cafe Experience",
                    "dates": ["2025-01-10"],
                },
                "Park": {
                    "canonical": "Mount Royal Park",
                    "dates": ["2025-02-05", "2025-03-12"],
                },
            },
        }
        path.write_text(yaml.dump(data))
        return curation_dir

    def test_aggregate_single_year(self, locations_curation_2024, monkeypatch):
        """Test aggregating locations from single year."""
        monkeypatch.setattr("dev.curation.summary.CURATION_DIR", locations_curation_2024)

        result = aggregate_locations()

        assert result.entity_type == "locations"
        assert result.total_unique == 3
        assert "Montreal" in result.by_city
        assert "Toronto" in result.by_city
        assert result.by_city["Montreal"]["Cafe X"]["2024"] == 2
        assert result.by_city["Montreal"]["Library"]["2024"] == 1
        assert result.by_city["Toronto"]["Museum"]["2024"] == 1

    def test_aggregate_multiple_years(self, locations_curation_2024, locations_curation_2025, monkeypatch):
        """Test aggregating locations from multiple years."""
        curation_dir = locations_curation_2024
        monkeypatch.setattr("dev.curation.summary.CURATION_DIR", curation_dir)

        result = aggregate_locations()

        assert result.total_unique == 4
        assert result.by_city["Montreal"]["Cafe X"]["2024"] == 2
        assert result.by_city["Montreal"]["Cafe X"]["2025"] == 1
        assert result.by_city["Montreal"]["Park"]["2025"] == 2

    def test_aggregate_empty_directory(self, tmp_dir, monkeypatch):
        """Test aggregating with no curation files."""
        empty_dir = tmp_dir / "empty"
        empty_dir.mkdir()
        monkeypatch.setattr("dev.curation.summary.CURATION_DIR", empty_dir)

        result = aggregate_locations()

        assert result.total_unique == 0
        assert result.by_city == {}

    def test_aggregate_skips_invalid_entries(self, tmp_dir, monkeypatch):
        """Test aggregation skips invalid entries."""
        curation_dir = tmp_dir / "curation"
        curation_dir.mkdir()

        path = curation_dir / "2024_locations_curation.yaml"
        data = {
            "Montreal": {
                "Cafe X": {
                    "canonical": "Cafe Experience",
                    "dates": ["2024-01-15"],
                },
                "Invalid": "not a dict",
                "NoDate": {
                    "canonical": "No Date Location",
                },
            },
            "InvalidCity": "not a dict",
        }
        path.write_text(yaml.dump(data))
        monkeypatch.setattr("dev.curation.summary.CURATION_DIR", curation_dir)

        result = aggregate_locations()

        assert result.total_unique == 1
        assert "Cafe X" in result.by_city["Montreal"]
        assert "Invalid" not in result.by_city["Montreal"]
        assert "NoDate" not in result.by_city["Montreal"]


# =============================================================================
# Test Report Formatting
# =============================================================================

class TestFormatPeopleReport:
    """Test format_people_report function."""

    @pytest.fixture
    def people_summary_data(self):
        """Create sample people summary data."""
        by_name = {
            "Alice": {"2024": 10, "2025": 5},
            "Bob": {"2024": 3},
            "Clara": {"2024": 7, "2025": 8},
            "David": {"2025": 2},
        }
        return SummaryData(
            entity_type="people",
            total_unique=4,
            by_name=by_name,
        )

    def test_format_by_frequency(self, people_summary_data):
        """Test formatting with frequency sorting."""
        lines = format_people_report(people_summary_data, alphabetical=False)

        assert "=== People Summary (by frequency) ===" in lines[0]
        assert "Total unique names: 4" in lines[1]

        # Check order: Alice(15), Clara(15), Bob(3), David(2)
        content = "\n".join(lines)
        alice_pos = content.find("Alice")
        clara_pos = content.find("Clara")
        bob_pos = content.find("Bob")
        david_pos = content.find("David")

        assert alice_pos < bob_pos
        assert clara_pos < bob_pos
        assert bob_pos < david_pos

    def test_format_alphabetically(self, people_summary_data):
        """Test formatting with alphabetical sorting."""
        lines = format_people_report(people_summary_data, alphabetical=True)

        assert "=== People Summary (by alphabetical) ===" in lines[0]

        # Check order: Alice, Bob, Clara, David
        content = "\n".join(lines)
        alice_pos = content.find("Alice")
        bob_pos = content.find("Bob")
        clara_pos = content.find("Clara")
        david_pos = content.find("David")

        assert alice_pos < bob_pos < clara_pos < david_pos

    def test_format_includes_year_breakdown(self, people_summary_data):
        """Test formatting includes year breakdowns."""
        lines = format_people_report(people_summary_data, alphabetical=False)

        content = "\n".join(lines)
        assert "2025(5), 2024(10)" in content  # Alice
        assert "2024(3)" in content  # Bob

    def test_format_empty_data(self):
        """Test formatting empty data."""
        empty_data = SummaryData(entity_type="people", total_unique=0, by_name={})
        lines = format_people_report(empty_data, alphabetical=False)

        assert "Total unique names: 0" in lines[1]

    def test_format_singular_vs_plural_entry(self):
        """Test correct use of 'entry' vs 'entries'."""
        by_name = {
            "Alice": {"2024": 1},
            "Bob": {"2024": 5},
        }
        data = SummaryData(entity_type="people", total_unique=2, by_name=by_name)
        lines = format_people_report(data, alphabetical=False)

        content = "\n".join(lines)
        assert "1 entry " in content  # Singular for Alice
        assert "5 entries" in content  # Plural for Bob


class TestFormatLocationsReport:
    """Test format_locations_report function."""

    @pytest.fixture
    def locations_summary_data(self):
        """Create sample locations summary data."""
        by_city = {
            "Montreal": {
                "Cafe X": {"2024": 5, "2025": 3},
                "Library": {"2024": 2},
            },
            "Toronto": {
                "Museum": {"2025": 4},
            },
            "_unassigned": {
                "Unknown Place": {"2024": 1},
            },
        }
        return SummaryData(
            entity_type="locations",
            total_unique=4,
            by_city=by_city,
        )

    def test_format_by_frequency(self, locations_summary_data):
        """Test formatting with frequency sorting."""
        lines = format_locations_report(locations_summary_data, alphabetical=False)

        assert "=== Locations Summary (by frequency) ===" in lines[0]

        # Check Montreal section
        content = "\n".join(lines)
        assert "--- Montreal ---" in content
        assert "--- Toronto ---" in content
        assert "--- _unassigned ---" in content

    def test_format_alphabetically(self, locations_summary_data):
        """Test formatting with alphabetical sorting."""
        lines = format_locations_report(locations_summary_data, alphabetical=True)

        assert "=== Locations Summary (by alphabetical) ===" in lines[0]

        content = "\n".join(lines)
        # Within Montreal, alphabetical: Cafe X before Library
        montreal_section = content[content.find("--- Montreal ---"):content.find("--- Toronto ---")]
        cafe_pos = montreal_section.find("Cafe X")
        library_pos = montreal_section.find("Library")
        assert cafe_pos < library_pos

    def test_format_cities_sorted_with_unassigned_last(self, locations_summary_data):
        """Test _unassigned city appears last."""
        lines = format_locations_report(locations_summary_data, alphabetical=False)

        content = "\n".join(lines)
        montreal_pos = content.find("--- Montreal ---")
        toronto_pos = content.find("--- Toronto ---")
        unassigned_pos = content.find("--- _unassigned ---")

        assert montreal_pos < toronto_pos < unassigned_pos

    def test_format_empty_data(self):
        """Test formatting empty data."""
        empty_data = SummaryData(entity_type="locations", total_unique=0, by_city={})
        lines = format_locations_report(empty_data, alphabetical=False)

        assert "=== Locations Summary (by frequency) ===" in lines[0]
        assert len(lines) == 2  # Header and blank line

    def test_format_includes_year_breakdown(self, locations_summary_data):
        """Test formatting includes year breakdowns."""
        lines = format_locations_report(locations_summary_data, alphabetical=False)

        content = "\n".join(lines)
        assert "2025(3), 2024(5)" in content  # Cafe X


# =============================================================================
# Test Main Summary Function
# =============================================================================

class TestGenerateSummary:
    """Test generate_summary function."""

    @pytest.fixture
    def sample_curation(self, tmp_dir):
        """Create sample curation files."""
        curation_dir = tmp_dir / "curation"
        curation_dir.mkdir()

        # People curation
        people_path = curation_dir / "2024_people_curation.yaml"
        people_data = {
            "Alice": {
                "canonical": "Alice Johnson",
                "dates": ["2024-01-15", "2024-02-20"],
            },
            "Bob": {
                "canonical": "Bob Smith",
                "dates": ["2024-01-15"],
            },
        }
        people_path.write_text(yaml.dump(people_data))

        # Locations curation
        locations_path = curation_dir / "2024_locations_curation.yaml"
        locations_data = {
            "Montreal": {
                "Cafe X": {
                    "canonical": "Cafe Experience",
                    "dates": ["2024-01-15"],
                },
            },
        }
        locations_path.write_text(yaml.dump(locations_data))

        return curation_dir

    def test_generate_both_summaries(self, sample_curation, monkeypatch):
        """Test generating both people and locations summaries."""
        monkeypatch.setattr("dev.curation.summary.CURATION_DIR", sample_curation)

        people_data, locations_data, report_lines = generate_summary()

        assert people_data is not None
        assert people_data.total_unique == 2
        assert locations_data is not None
        assert locations_data.total_unique == 1
        assert len(report_lines) > 0

    def test_generate_people_only(self, sample_curation, monkeypatch):
        """Test generating only people summary."""
        monkeypatch.setattr("dev.curation.summary.CURATION_DIR", sample_curation)

        people_data, locations_data, report_lines = generate_summary(entity_type="people")

        assert people_data is not None
        assert locations_data is None
        assert "People Summary" in "\n".join(report_lines)
        assert "Locations Summary" not in "\n".join(report_lines)

    def test_generate_locations_only(self, sample_curation, monkeypatch):
        """Test generating only locations summary."""
        monkeypatch.setattr("dev.curation.summary.CURATION_DIR", sample_curation)

        people_data, locations_data, report_lines = generate_summary(entity_type="locations")

        assert people_data is None
        assert locations_data is not None
        assert "Locations Summary" in "\n".join(report_lines)
        assert "People Summary" not in "\n".join(report_lines)

    def test_generate_alphabetical(self, sample_curation, monkeypatch):
        """Test generating with alphabetical sorting."""
        monkeypatch.setattr("dev.curation.summary.CURATION_DIR", sample_curation)

        _, _, report_lines = generate_summary(alphabetical=True)

        content = "\n".join(report_lines)
        assert "by alphabetical" in content

    def test_generate_frequency(self, sample_curation, monkeypatch):
        """Test generating with frequency sorting."""
        monkeypatch.setattr("dev.curation.summary.CURATION_DIR", sample_curation)

        _, _, report_lines = generate_summary(alphabetical=False)

        content = "\n".join(report_lines)
        assert "by frequency" in content

    def test_generate_with_logger(self, sample_curation, monkeypatch, tmp_dir):
        """Test generating with custom logger."""
        from dev.core.logging_manager import PalimpsestLogger

        monkeypatch.setattr("dev.curation.summary.CURATION_DIR", sample_curation)

        log_dir = tmp_dir / "logs"
        log_dir.mkdir()
        logger = PalimpsestLogger(log_dir, component_name="test_summary")

        people_data, locations_data, _ = generate_summary(logger=logger)

        assert people_data is not None
        assert locations_data is not None
