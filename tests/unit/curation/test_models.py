"""
test_models.py
--------------
Unit tests for dev.curation.models module.

Tests all dataclasses used in the curation workflow including
statistics tracking, validation results, and import outcomes.

Target Coverage: 95%+
"""
import pytest
from datetime import datetime
from dev.curation.models import (
    ExtractionStats,
    ValidationResult,
    ConsistencyResult,
    ConsolidationResult,
    ImportStats,
    FailedImport,
    SummaryData,
)


class TestExtractionStats:
    """Test ExtractionStats dataclass."""

    def test_default_initialization(self):
        """Test default values are set correctly."""
        stats = ExtractionStats()
        assert stats.files_scanned_md == 0
        assert stats.files_scanned_yaml == 0
        assert stats.years_found == set()
        assert stats.people_count == 0
        assert stats.locations_count == 0
        assert stats.people_by_year == {}
        assert stats.locations_by_year == {}

    def test_initialization_with_values(self):
        """Test initialization with custom values."""
        years = {"2023", "2024"}
        people_by_year = {"2023": 10, "2024": 15}
        locations_by_year = {"2023": 5, "2024": 8}

        stats = ExtractionStats(
            files_scanned_md=50,
            files_scanned_yaml=20,
            years_found=years,
            people_count=25,
            locations_count=13,
            people_by_year=people_by_year,
            locations_by_year=locations_by_year,
        )

        assert stats.files_scanned_md == 50
        assert stats.files_scanned_yaml == 20
        assert stats.years_found == years
        assert stats.people_count == 25
        assert stats.locations_count == 13
        assert stats.people_by_year == people_by_year
        assert stats.locations_by_year == locations_by_year

    def test_summary_empty_stats(self):
        """Test summary with empty stats."""
        stats = ExtractionStats()
        summary = stats.summary()

        assert "0 MD files" in summary
        assert "0 YAML files" in summary
        assert "0 people" in summary
        assert "0 locations" in summary
        assert "0 years" in summary

    def test_summary_with_data(self):
        """Test summary with actual data."""
        stats = ExtractionStats(
            files_scanned_md=100,
            files_scanned_yaml=50,
            years_found={"2022", "2023", "2024"},
            people_count=42,
            locations_count=17,
        )
        summary = stats.summary()

        assert "100 MD files" in summary
        assert "50 YAML files" in summary
        assert "42 people" in summary
        assert "17 locations" in summary
        assert "3 years" in summary

    def test_years_found_is_mutable_set(self):
        """Test that years_found can be modified."""
        stats = ExtractionStats()
        stats.years_found.add("2023")
        stats.years_found.add("2024")

        assert len(stats.years_found) == 2
        assert "2023" in stats.years_found
        assert "2024" in stats.years_found


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_default_initialization(self):
        """Test default values are set correctly."""
        result = ValidationResult()
        assert result.file_path == ""
        assert result.errors == []
        assert result.warnings == []
        assert result.is_valid is True

    def test_initialization_with_values(self):
        """Test initialization with custom values."""
        result = ValidationResult(
            file_path="/path/to/file.yaml",
            errors=["Error 1", "Error 2"],
            warnings=["Warning 1"],
        )

        assert result.file_path == "/path/to/file.yaml"
        assert len(result.errors) == 2
        assert len(result.warnings) == 1

    def test_post_init_sets_invalid_with_errors(self):
        """Test __post_init__ marks result as invalid when errors exist."""
        result = ValidationResult(errors=["Some error"])
        assert result.is_valid is False

    def test_post_init_keeps_valid_without_errors(self):
        """Test __post_init__ keeps result valid when no errors."""
        result = ValidationResult(warnings=["Some warning"])
        assert result.is_valid is True

    def test_add_error_appends_to_list(self):
        """Test add_error adds message to errors list."""
        result = ValidationResult()
        result.add_error("First error")
        result.add_error("Second error")

        assert len(result.errors) == 2
        assert "First error" in result.errors
        assert "Second error" in result.errors

    def test_add_error_marks_invalid(self):
        """Test add_error sets is_valid to False."""
        result = ValidationResult()
        assert result.is_valid is True

        result.add_error("Error occurred")
        assert result.is_valid is False

    def test_add_warning_appends_to_list(self):
        """Test add_warning adds message to warnings list."""
        result = ValidationResult()
        result.add_warning("First warning")
        result.add_warning("Second warning")

        assert len(result.warnings) == 2
        assert "First warning" in result.warnings
        assert "Second warning" in result.warnings

    def test_add_warning_keeps_valid(self):
        """Test add_warning doesn't affect validity."""
        result = ValidationResult()
        assert result.is_valid is True

        result.add_warning("Warning message")
        assert result.is_valid is True

    def test_summary_valid_no_warnings(self):
        """Test summary for valid result without warnings."""
        result = ValidationResult()
        assert result.summary() == "Valid"

    def test_summary_valid_with_warnings(self):
        """Test summary for valid result with warnings."""
        result = ValidationResult(warnings=["Warning 1", "Warning 2"])
        assert result.summary() == "Valid (with 2 warnings)"

    def test_summary_invalid_with_errors_and_warnings(self):
        """Test summary for invalid result with both errors and warnings."""
        result = ValidationResult(
            errors=["Error 1", "Error 2", "Error 3"],
            warnings=["Warning 1"],
        )
        summary = result.summary()

        assert "Invalid" in summary
        assert "3 errors" in summary
        assert "1 warnings" in summary

    def test_summary_invalid_with_errors_only(self):
        """Test summary for invalid result with only errors."""
        result = ValidationResult(errors=["Error 1"])
        summary = result.summary()

        assert "Invalid" in summary
        assert "1 errors" in summary
        assert "0 warnings" in summary


class TestConsistencyResult:
    """Test ConsistencyResult dataclass."""

    def test_default_initialization(self):
        """Test default values are set correctly."""
        result = ConsistencyResult()
        assert result.entity_type == ""
        assert result.conflicts == []
        assert result.suggestions == []

    def test_initialization_with_values(self):
        """Test initialization with custom values."""
        result = ConsistencyResult(
            entity_type="people",
            conflicts=["Conflict 1", "Conflict 2"],
            suggestions=["Suggestion 1"],
        )

        assert result.entity_type == "people"
        assert len(result.conflicts) == 2
        assert len(result.suggestions) == 1

    def test_has_conflicts_false_when_empty(self):
        """Test has_conflicts property returns False when no conflicts."""
        result = ConsistencyResult()
        assert result.has_conflicts is False

    def test_has_conflicts_true_when_present(self):
        """Test has_conflicts property returns True when conflicts exist."""
        result = ConsistencyResult(conflicts=["Conflict 1"])
        assert result.has_conflicts is True

    def test_summary_no_conflicts_or_suggestions(self):
        """Test summary when clean."""
        result = ConsistencyResult(entity_type="locations")
        summary = result.summary()

        assert "locations" in summary
        assert "No conflicts or suggestions" in summary

    def test_summary_with_conflicts_and_suggestions(self):
        """Test summary with both conflicts and suggestions."""
        result = ConsistencyResult(
            entity_type="people",
            conflicts=["C1", "C2"],
            suggestions=["S1", "S2", "S3"],
        )
        summary = result.summary()

        assert "people" in summary
        assert "2 conflicts" in summary
        assert "3 suggestions" in summary

    def test_summary_with_conflicts_only(self):
        """Test summary with only conflicts."""
        result = ConsistencyResult(
            entity_type="locations",
            conflicts=["C1"],
        )
        summary = result.summary()

        assert "1 conflicts" in summary
        assert "0 suggestions" in summary


class TestConsolidationResult:
    """Test ConsolidationResult dataclass."""

    def test_default_initialization(self):
        """Test default values are set correctly."""
        result = ConsolidationResult()
        assert result.years_processed == []
        assert result.merged_count == 0
        assert result.skipped_count == 0
        assert result.self_count == 0
        assert result.conflicts == []
        assert result.output_path == ""

    def test_initialization_with_values(self):
        """Test initialization with custom values."""
        result = ConsolidationResult(
            years_processed=["2022", "2023", "2024"],
            merged_count=100,
            skipped_count=5,
            self_count=3,
            conflicts=["Conflict 1"],
            output_path="/path/to/output.yaml",
        )

        assert result.years_processed == ["2022", "2023", "2024"]
        assert result.merged_count == 100
        assert result.skipped_count == 5
        assert result.self_count == 3
        assert len(result.conflicts) == 1
        assert result.output_path == "/path/to/output.yaml"

    def test_has_conflicts_false_when_empty(self):
        """Test has_conflicts property returns False when no conflicts."""
        result = ConsolidationResult()
        assert result.has_conflicts is False

    def test_has_conflicts_true_when_present(self):
        """Test has_conflicts property returns True when conflicts exist."""
        result = ConsolidationResult(conflicts=["Conflict"])
        assert result.has_conflicts is True

    def test_summary_without_conflicts(self):
        """Test summary without conflicts."""
        result = ConsolidationResult(
            years_processed=["2023", "2024"],
            merged_count=50,
            skipped_count=2,
            self_count=1,
        )
        summary = result.summary()

        assert "2023, 2024" in summary
        assert "Merged: 50" in summary
        assert "Skipped: 2" in summary
        assert "Self: 1" in summary
        assert "Conflicts" not in summary

    def test_summary_with_conflicts(self):
        """Test summary with conflicts."""
        result = ConsolidationResult(
            years_processed=["2023"],
            merged_count=25,
            skipped_count=1,
            self_count=0,
            conflicts=["C1", "C2", "C3"],
        )
        summary = result.summary()

        assert "2023" in summary
        assert "Merged: 25" in summary
        assert "Conflicts: 3" in summary

    def test_summary_empty_years(self):
        """Test summary with empty years list."""
        result = ConsolidationResult(merged_count=10)
        summary = result.summary()

        assert "Years: " in summary
        assert "Merged: 10" in summary


class TestImportStats:
    """Test ImportStats dataclass."""

    def test_default_initialization(self):
        """Test default values are set correctly."""
        stats = ImportStats()

        # Processing counts
        assert stats.total_files == 0
        assert stats.processed == 0
        assert stats.succeeded == 0
        assert stats.failed == 0
        assert stats.skipped == 0
        assert stats.consecutive_failures == 0

        # Entity counts
        assert stats.entries_created == 0
        assert stats.scenes_created == 0
        assert stats.events_created == 0
        assert stats.threads_created == 0
        assert stats.people_created == 0
        assert stats.locations_created == 0
        assert stats.cities_created == 0
        assert stats.arcs_created == 0
        assert stats.tags_created == 0
        assert stats.themes_created == 0
        assert stats.motifs_created == 0
        assert stats.references_created == 0
        assert stats.poems_created == 0

        # Thresholds
        assert stats.MAX_CONSECUTIVE_FAILURES == 5
        assert stats.MAX_FAILURE_RATE == 0.05

    def test_initialization_with_values(self):
        """Test initialization with custom values."""
        stats = ImportStats(
            total_files=100,
            processed=50,
            succeeded=45,
            failed=5,
            skipped=10,
            entries_created=40,
            scenes_created=120,
            people_created=25,
        )

        assert stats.total_files == 100
        assert stats.processed == 50
        assert stats.succeeded == 45
        assert stats.failed == 5
        assert stats.skipped == 10
        assert stats.entries_created == 40
        assert stats.scenes_created == 120
        assert stats.people_created == 25

    def test_failure_rate_zero_when_no_processing(self):
        """Test failure_rate returns 0.0 when nothing processed."""
        stats = ImportStats()
        assert stats.failure_rate == 0.0

    def test_failure_rate_calculation(self):
        """Test failure_rate calculates correctly."""
        stats = ImportStats(processed=100, failed=5)
        assert stats.failure_rate == 0.05

    def test_failure_rate_all_failed(self):
        """Test failure_rate when all files failed."""
        stats = ImportStats(processed=10, failed=10)
        assert stats.failure_rate == 1.0

    def test_should_stop_false_initially(self):
        """Test should_stop returns False with no failures."""
        stats = ImportStats()
        assert stats.should_stop() is False

    def test_should_stop_true_on_consecutive_failures(self):
        """Test should_stop returns True when consecutive failures exceeded."""
        stats = ImportStats(consecutive_failures=5)
        assert stats.should_stop() is True

    def test_should_stop_false_just_under_consecutive_threshold(self):
        """Test should_stop returns False just under consecutive threshold."""
        stats = ImportStats(consecutive_failures=4)
        assert stats.should_stop() is False

    def test_should_stop_true_on_high_failure_rate(self):
        """Test should_stop returns True when failure rate exceeded."""
        stats = ImportStats(processed=20, failed=2)  # 10% failure rate
        assert stats.should_stop() is True

    def test_should_stop_false_with_high_rate_but_low_sample(self):
        """Test should_stop returns False with high rate but < 20 processed."""
        stats = ImportStats(processed=10, failed=5)  # 50% but < 20 processed
        assert stats.should_stop() is False

    def test_should_stop_false_just_under_rate_threshold(self):
        """Test should_stop returns False just under failure rate threshold."""
        stats = ImportStats(processed=100, failed=4)  # 4% failure rate
        assert stats.should_stop() is False

    def test_summary_basic(self):
        """Test summary formatting."""
        stats = ImportStats(
            total_files=100,
            processed=50,
            succeeded=45,
            failed=3,
            skipped=2,
        )
        summary = stats.summary()

        assert "50/100" in summary
        assert "Succeeded: 45" in summary
        assert "Failed: 3" in summary
        assert "Skipped: 2" in summary

    def test_entity_summary(self):
        """Test entity_summary formatting."""
        stats = ImportStats(
            entries_created=100,
            scenes_created=300,
            events_created=150,
            threads_created=50,
            people_created=75,
            locations_created=40,
        )
        summary = stats.entity_summary()

        assert "Entries: 100" in summary
        assert "Scenes: 300" in summary
        assert "Events: 150" in summary
        assert "Threads: 50" in summary
        assert "People: 75" in summary
        assert "Locations: 40" in summary

    def test_to_dict_structure(self):
        """Test to_dict creates proper structure."""
        stats = ImportStats(
            total_files=100,
            processed=50,
            succeeded=45,
            failed=5,
            entries_created=40,
            scenes_created=120,
        )
        data = stats.to_dict()

        assert "processing" in data
        assert "entities" in data

        # Check processing section
        assert data["processing"]["total_files"] == 100
        assert data["processing"]["processed"] == 50
        assert data["processing"]["succeeded"] == 45
        assert data["processing"]["failed"] == 5
        assert data["processing"]["failure_rate"] == 0.1

        # Check entities section
        assert data["entities"]["entries"] == 40
        assert data["entities"]["scenes"] == 120

    def test_to_dict_includes_all_entities(self):
        """Test to_dict includes all entity types."""
        stats = ImportStats()
        data = stats.to_dict()

        entities = data["entities"]
        assert "entries" in entities
        assert "scenes" in entities
        assert "events" in entities
        assert "threads" in entities
        assert "people" in entities
        assert "locations" in entities
        assert "cities" in entities
        assert "arcs" in entities
        assert "tags" in entities
        assert "themes" in entities
        assert "motifs" in entities
        assert "references" in entities
        assert "poems" in entities


class TestFailedImport:
    """Test FailedImport dataclass."""

    def test_initialization_with_all_fields(self):
        """Test initialization with explicit timestamp."""
        timestamp = "2024-01-15T10:30:00"
        failed = FailedImport(
            file_path="/path/to/file.yaml",
            error_type="ValidationError",
            error_message="Invalid field",
            timestamp=timestamp,
        )

        assert failed.file_path == "/path/to/file.yaml"
        assert failed.error_type == "ValidationError"
        assert failed.error_message == "Invalid field"
        assert failed.timestamp == timestamp

    def test_initialization_auto_timestamp(self):
        """Test initialization generates timestamp automatically."""
        failed = FailedImport(
            file_path="/path/to/file.yaml",
            error_type="DatabaseError",
            error_message="Connection failed",
        )

        # Timestamp should be ISO format
        assert failed.timestamp
        datetime.fromisoformat(failed.timestamp)  # Should not raise

    def test_to_dict_structure(self):
        """Test to_dict creates proper dictionary."""
        failed = FailedImport(
            file_path="/test/file.yaml",
            error_type="KeyError",
            error_message="Missing key 'name'",
            timestamp="2024-01-15T12:00:00",
        )
        data = failed.to_dict()

        assert data["file_path"] == "/test/file.yaml"
        assert data["error_type"] == "KeyError"
        assert data["error_message"] == "Missing key 'name'"
        assert data["timestamp"] == "2024-01-15T12:00:00"

    def test_to_dict_includes_all_fields(self):
        """Test to_dict includes all required fields."""
        failed = FailedImport(
            file_path="/path",
            error_type="Error",
            error_message="Message",
        )
        data = failed.to_dict()

        assert "file_path" in data
        assert "error_type" in data
        assert "error_message" in data
        assert "timestamp" in data


class TestSummaryData:
    """Test SummaryData dataclass."""

    def test_default_initialization(self):
        """Test default values are set correctly."""
        data = SummaryData()
        assert data.entity_type == ""
        assert data.total_unique == 0
        assert data.by_name == {}
        assert data.by_city is None

    def test_initialization_with_values(self):
        """Test initialization with custom values."""
        by_name = {
            "Alice": {"2023": 5, "2024": 3},
            "Bob": {"2024": 2},
        }
        data = SummaryData(
            entity_type="people",
            total_unique=2,
            by_name=by_name,
        )

        assert data.entity_type == "people"
        assert data.total_unique == 2
        assert data.by_name == by_name
        assert data.by_city is None

    def test_initialization_with_city_data(self):
        """Test initialization with by_city data."""
        by_city = {
            "Montreal": {
                "Café Central": {"2023": 5, "2024": 3},
                "Library": {"2023": 2},
            },
            "Toronto": {
                "Museum": {"2024": 1},
            },
        }
        data = SummaryData(
            entity_type="locations",
            total_unique=3,
            by_name={},
            by_city=by_city,
        )

        assert data.entity_type == "locations"
        assert data.total_unique == 3
        assert data.by_city == by_city

    def test_summary_simple_entity_type(self):
        """Test summary for entity type without cities."""
        data = SummaryData(
            entity_type="people",
            total_unique=42,
            by_name={"Alice": {"2023": 1}},
        )
        summary = data.summary()

        assert "people" in summary
        assert "42 unique names" in summary

    def test_summary_with_city_data(self):
        """Test summary for entity type with cities."""
        by_city = {
            "Montreal": {"Place1": {"2023": 1}},
            "Toronto": {"Place2": {"2024": 1}},
            "Vancouver": {"Place3": {"2023": 1}},
        }
        data = SummaryData(
            entity_type="locations",
            total_unique=3,
            by_name={},
            by_city=by_city,
        )
        summary = data.summary()

        assert "locations" in summary
        assert "3 unique" in summary
        assert "3 cities" in summary

    def test_summary_zero_count(self):
        """Test summary with zero entities."""
        data = SummaryData(entity_type="tags", total_unique=0)
        summary = data.summary()

        assert "tags" in summary
        assert "0 unique names" in summary

    def test_summary_single_city(self):
        """Test summary with single city."""
        data = SummaryData(
            entity_type="locations",
            total_unique=5,
            by_city={"Montreal": {}},
        )
        summary = data.summary()

        assert "1 cities" in summary  # Grammatically incorrect but follows pattern
