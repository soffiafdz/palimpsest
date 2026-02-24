"""
test_metadata_entry.py
----------------------
Unit tests for dev.dataclasses.metadata_entry module.

Tests the MetadataEntry dataclass which parses standalone metadata YAML files
for the jumpstart pipeline.

Target Coverage: 85%+
"""
import pytest
from datetime import date

from dev.dataclasses.metadata_entry import MetadataEntry, MetadataValidationResult
from dev.core.exceptions import MetadataValidationError


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def minimal_metadata_content():
    """Minimal valid metadata YAML with only required fields."""
    return """
date: '2024-12-03'
summary: ''
rating: null
rating_justification: ''
arcs: []
tags: []
themes: []
motifs: []
scenes: []
events: []
"""


@pytest.fixture
def complex_metadata_content():
    """Complex metadata YAML with all fields populated."""
    return """
date: '2024-12-03'
summary: The entry chronicles the onset of a depressive episode.
rating: 4.5
rating_justification: 'This entry marks a crucial turning point.'

arcs:
  - The Long Wanting
  - The March Crisis
  - The Chemical Refuge

tags:
  - depression
  - medication
  - alcohol

themes:
  - Cyclical Behavior
  - Self-Medication

motifs:
  - name: The Spiral
    description: The onset of depressive episode.
  - name: The Bottle
    description: Breaking sobriety mid-entry with raki.

scenes:
  - name: Psychiatric Session
    description: Sofia tells Dr Franck she feels depression coming.
    date: 2024-12-03
    people:
      - Dr Franck
    locations:
      - Apartment - Jarry
  - name: The Two Sips
    description: Stopping mid-entry for two sips of raki.
    date: 2024-12-03
    locations:
      - Apartment - Jarry

events:
  - name: The Raki Afternoon
    scenes:
      - The Two Sips
  - name: The Dose Increase
    scenes:
      - Psychiatric Session

threads:
  - name: Chekhov's Raki
    from: '2024-12-03'
    to: '2024-12-08'
    entry: '2024-12-08'
    content: The two sips foreshadow the full relapse.
    people:
      - Sofia

poems:
  - title: Muse
    content: I miss the idea I built of you.

references:
  - description: Brief description
    mode: direct
    source:
      title: Work Title
      author: Author Name
      type: book
"""


@pytest.fixture
def metadata_with_multiday_scene():
    """Metadata with a scene spanning multiple days."""
    return """
date: '2024-12-05'
summary: A scene across multiple days.
scenes:
  - name: The Weekend Visit
    description: Visiting family over the weekend.
    date:
      - 2024-12-05
      - 2024-12-06
      - 2024-12-07
    people:
      - Family
    locations:
      - Home
events: []
"""


@pytest.fixture
def minimal_metadata_file(tmp_dir, minimal_metadata_content):
    """Create a minimal metadata YAML file."""
    file_path = tmp_dir / "2024-12-03.yaml"
    file_path.write_text(minimal_metadata_content)
    return file_path


@pytest.fixture
def complex_metadata_file(tmp_dir, complex_metadata_content):
    """Create a complex metadata YAML file."""
    file_path = tmp_dir / "2024-12-03-complex.yaml"
    file_path.write_text(complex_metadata_content)
    return file_path


# =============================================================================
# Construction Tests
# =============================================================================


class TestMetadataEntryConstruction:
    """Tests for MetadataEntry construction methods."""

    def test_from_file_minimal(self, minimal_metadata_file):
        """Test parsing minimal metadata file."""
        entry = MetadataEntry.from_file(minimal_metadata_file)

        assert entry.date == date(2024, 12, 3)
        assert entry.summary == ""
        assert entry.rating is None
        assert entry.arcs == []
        assert entry.scenes == []
        assert entry.events == []
        assert entry.file_path == minimal_metadata_file

    def test_from_file_complex(self, complex_metadata_file):
        """Test parsing complex metadata file."""
        entry = MetadataEntry.from_file(complex_metadata_file)

        assert entry.date == date(2024, 12, 3)
        assert "depressive episode" in entry.summary
        assert entry.rating == 4.5
        assert "This entry marks" in entry.rating_justification

        # Arcs
        assert len(entry.arcs) == 3
        assert "The Long Wanting" in entry.arcs

        # Tags
        assert len(entry.tags) == 3
        assert "depression" in entry.tags

        # Themes
        assert len(entry.themes) == 2
        assert "Self-Medication" in entry.themes

        # Motifs
        assert len(entry.motifs) == 2
        assert entry.motifs[0]["name"] == "The Spiral"

        # Scenes
        assert len(entry.scenes) == 2
        assert entry.scenes[0]["name"] == "Psychiatric Session"
        assert "Dr Franck" in entry.scenes[0].get("people", [])

        # Events
        assert len(entry.events) == 2
        assert entry.events[0]["name"] == "The Raki Afternoon"

        # Threads
        assert len(entry.threads) == 1
        assert entry.threads[0]["name"] == "Chekhov's Raki"

        # Poems
        assert len(entry.poems) == 1
        assert entry.poems[0]["title"] == "Muse"

        # References
        assert len(entry.references) == 1

    def test_from_file_not_found(self, tmp_dir):
        """Test error when file not found."""
        with pytest.raises(FileNotFoundError):
            MetadataEntry.from_file(tmp_dir / "nonexistent.yaml")

    def test_from_yaml_text_invalid_yaml(self):
        """Test error on invalid YAML."""
        invalid_yaml = "date: [invalid: yaml"
        with pytest.raises(MetadataValidationError, match="Invalid YAML"):
            MetadataEntry.from_yaml_text(invalid_yaml)

    def test_from_yaml_text_missing_date(self):
        """Test error when date field is missing."""
        no_date_yaml = "summary: No date here\narcs: []"
        with pytest.raises(MetadataValidationError, match="Missing required 'date'"):
            MetadataEntry.from_yaml_text(no_date_yaml)

    def test_from_yaml_text_invalid_date_format(self):
        """Test error on invalid date format."""
        invalid_date = "date: not-a-date\nsummary: Test"
        with pytest.raises(MetadataValidationError, match="Invalid date format"):
            MetadataEntry.from_yaml_text(invalid_date)

    def test_from_yaml_text_non_dict(self):
        """Test error when YAML is not a dictionary."""
        list_yaml = "- item1\n- item2"
        with pytest.raises(MetadataValidationError, match="must be a dictionary"):
            MetadataEntry.from_yaml_text(list_yaml)


# =============================================================================
# Parsing Tests
# =============================================================================


class TestMetadataEntryParsing:
    """Tests for field parsing methods."""

    def test_parse_rating_float(self):
        """Test parsing float rating."""
        entry = MetadataEntry.from_yaml_text("date: 2024-01-01\nrating: 3.5")
        assert entry.rating == 3.5

    def test_parse_rating_int(self):
        """Test parsing integer rating."""
        entry = MetadataEntry.from_yaml_text("date: 2024-01-01\nrating: 4")
        assert entry.rating == 4.0

    def test_parse_rating_null(self):
        """Test parsing null rating."""
        entry = MetadataEntry.from_yaml_text("date: 2024-01-01\nrating: null")
        assert entry.rating is None

    def test_parse_rating_invalid(self):
        """Test parsing invalid rating returns None."""
        entry = MetadataEntry.from_yaml_text("date: 2024-01-01\nrating: 'not a number'")
        assert entry.rating is None

    def test_parse_string_list_from_list(self):
        """Test parsing list of strings."""
        entry = MetadataEntry.from_yaml_text("date: 2024-01-01\ntags:\n  - a\n  - b")
        assert entry.tags == ["a", "b"]

    def test_parse_string_list_from_single(self):
        """Test parsing single string as list."""
        entry = MetadataEntry.from_yaml_text("date: 2024-01-01\ntags: single-tag")
        assert entry.tags == ["single-tag"]

    def test_parse_string_list_null(self):
        """Test parsing null as empty list."""
        entry = MetadataEntry.from_yaml_text("date: 2024-01-01\ntags: null")
        assert entry.tags == []

    def test_parse_motifs(self):
        """Test parsing motifs with name and description."""
        yaml_content = """
date: 2024-01-01
motifs:
  - name: The Loop
    description: A recurring pattern.
  - name: The Mirror
    description: Reflection of self.
"""
        entry = MetadataEntry.from_yaml_text(yaml_content)
        assert len(entry.motifs) == 2
        assert entry.motifs[0]["name"] == "The Loop"
        assert entry.motifs[1]["description"] == "Reflection of self."

    def test_parse_scenes_with_optional_fields(self):
        """Test parsing scenes with and without optional fields."""
        yaml_content = """
date: 2024-01-01
scenes:
  - name: Scene with people
    description: Has people and locations.
    date: 2024-01-01
    people:
      - Alice
    locations:
      - Cafe
  - name: Scene without optionals
    description: No people or locations.
    date: 2024-01-01
"""
        entry = MetadataEntry.from_yaml_text(yaml_content)
        assert len(entry.scenes) == 2
        assert entry.scenes[0].get("people") == ["Alice"]
        assert entry.scenes[0].get("locations") == ["Cafe"]
        assert "people" not in entry.scenes[1] or entry.scenes[1].get("people") == []

    def test_parse_threads(self, tmp_dir):
        """Test parsing threads with from/to dates."""
        yaml_content = """
date: 2024-01-01
threads:
  - name: Echo Thread
    from: '2024-01-01'
    to: '2023-06'
    entry: '2023-06-15'
    content: Connection to past.
    people:
      - Someone
"""
        entry = MetadataEntry.from_yaml_text(yaml_content)
        assert len(entry.threads) == 1
        assert entry.threads[0]["name"] == "Echo Thread"
        assert entry.threads[0]["from_"] == "2024-01-01"
        assert entry.threads[0]["to"] == "2023-06"

    def test_parse_multiday_scene(self, metadata_with_multiday_scene):
        """Test parsing scene with multiple dates."""
        entry = MetadataEntry.from_yaml_text(metadata_with_multiday_scene)
        assert len(entry.scenes) == 1
        scene_dates = entry.scenes[0].get("date")
        assert isinstance(scene_dates, list)
        assert len(scene_dates) == 3


# =============================================================================
# Validation Tests
# =============================================================================


class TestMetadataEntryValidation:
    """Tests for validation methods."""

    def test_validate_structure_valid(self, complex_metadata_file):
        """Test structural validation passes for valid file."""
        entry = MetadataEntry.from_file(complex_metadata_file)
        result = entry.validate_structure()

        assert result.is_valid
        # May have warnings for missing descriptions, but no errors
        assert len(result.errors) == 0

    def test_validate_structure_duplicate_scenes(self, tmp_dir):
        """Test error for duplicate scene names."""
        yaml_content = """
date: 2024-01-01
scenes:
  - name: Duplicate Scene
    description: First occurrence.
    date: 2024-01-01
  - name: Duplicate Scene
    description: Second occurrence.
    date: 2024-01-01
"""
        file_path = tmp_dir / "duplicate.yaml"
        file_path.write_text(yaml_content)

        entry = MetadataEntry.from_file(file_path)
        result = entry.validate_structure()

        assert result.has_errors
        assert any("Duplicate scene names" in e for e in result.errors)

    def test_validate_structure_unknown_scene_reference(self, tmp_dir):
        """Test error when event references unknown scene."""
        yaml_content = """
date: 2024-01-01
scenes:
  - name: Real Scene
    description: This exists.
    date: 2024-01-01
events:
  - name: Test Event
    scenes:
      - Real Scene
      - Fake Scene
"""
        file_path = tmp_dir / "unknown_scene.yaml"
        file_path.write_text(yaml_content)

        entry = MetadataEntry.from_file(file_path)
        result = entry.validate_structure()

        assert result.has_errors
        assert any("unknown scene: Fake Scene" in e for e in result.errors)

    def test_validate_structure_motif_missing_description(self, tmp_dir):
        """Test warning for motif without description."""
        yaml_content = """
date: 2024-01-01
motifs:
  - name: No Description Motif
"""
        file_path = tmp_dir / "no_desc.yaml"
        file_path.write_text(yaml_content)

        entry = MetadataEntry.from_file(file_path)
        result = entry.validate_structure()

        assert any("missing description" in w for w in result.warnings)


# =============================================================================
# Accessor Tests
# =============================================================================


class TestMetadataEntryAccessors:
    """Tests for accessor methods."""

    def test_get_all_people(self, complex_metadata_file):
        """Test getting all unique people from scenes and threads."""
        entry = MetadataEntry.from_file(complex_metadata_file)
        people = entry.get_all_people()

        assert "Dr Franck" in people
        assert "Sofia" in people
        assert len(people) == len(set(people))  # No duplicates

    def test_get_all_locations(self, complex_metadata_file):
        """Test getting all unique locations from scenes and threads."""
        entry = MetadataEntry.from_file(complex_metadata_file)
        locations = entry.get_all_locations()

        assert "Apartment - Jarry" in locations
        assert len(locations) == len(set(locations))  # No duplicates

    def test_get_all_people_empty(self, minimal_metadata_file):
        """Test getting people from entry with no scenes."""
        entry = MetadataEntry.from_file(minimal_metadata_file)
        people = entry.get_all_people()
        assert people == []

    def test_get_all_locations_empty(self, minimal_metadata_file):
        """Test getting locations from entry with no scenes."""
        entry = MetadataEntry.from_file(minimal_metadata_file)
        locations = entry.get_all_locations()
        assert locations == []


# =============================================================================
# Conversion Tests
# =============================================================================


class TestMetadataEntryConversion:
    """Tests for conversion methods."""

    def test_to_database_metadata(self, complex_metadata_file):
        """Test conversion to database-ready format."""
        entry = MetadataEntry.from_file(complex_metadata_file)
        db_meta = entry.to_database_metadata()

        assert db_meta["date"] == date(2024, 12, 3)
        assert "summary" in db_meta
        assert db_meta["rating"] == 4.5
        assert "arcs" in db_meta
        assert "scenes" in db_meta
        assert "threads" in db_meta

        # Thread 'from_' should be converted back to 'from'
        if db_meta.get("threads"):
            assert "from" in db_meta["threads"][0]
            assert "from_" not in db_meta["threads"][0]

    def test_to_database_metadata_minimal(self, minimal_metadata_file):
        """Test conversion of minimal entry."""
        entry = MetadataEntry.from_file(minimal_metadata_file)
        db_meta = entry.to_database_metadata()

        assert db_meta["date"] == date(2024, 12, 3)
        assert db_meta["summary"] == ""
        assert db_meta["rating"] is None
        # Empty lists should not be included
        assert "arcs" not in db_meta or db_meta.get("arcs") == []


# =============================================================================
# Representation Tests
# =============================================================================


class TestMetadataEntryRepresentation:
    """Tests for string representations."""

    def test_repr(self, complex_metadata_file):
        """Test __repr__ output."""
        entry = MetadataEntry.from_file(complex_metadata_file)
        repr_str = repr(entry)

        assert "MetadataEntry" in repr_str
        assert "2024-12-03" in repr_str

    def test_str(self, complex_metadata_file):
        """Test __str__ output."""
        entry = MetadataEntry.from_file(complex_metadata_file)
        str_output = str(entry)

        assert "MetadataEntry" in str_output
        assert "scenes" in str_output
        assert "events" in str_output


# =============================================================================
# Validation Result Tests
# =============================================================================


class TestMetadataValidationResult:
    """Tests for MetadataValidationResult dataclass."""

    def test_has_errors_false(self):
        """Test has_errors is False with no errors."""
        result = MetadataValidationResult()
        assert not result.has_errors
        assert result.is_valid

    def test_has_errors_true(self):
        """Test has_errors is True after adding error."""
        result = MetadataValidationResult()
        result.add_error("Test error")
        assert result.has_errors
        assert not result.is_valid

    def test_add_warning_does_not_invalidate(self):
        """Test that warnings don't affect validity."""
        result = MetadataValidationResult()
        result.add_warning("Test warning")
        assert result.is_valid
        assert len(result.warnings) == 1

    def test_summary_valid(self):
        """Test summary output for valid result."""
        result = MetadataValidationResult()
        assert result.summary() == "Valid"

    def test_summary_valid_with_warnings(self):
        """Test summary output for valid result with warnings."""
        result = MetadataValidationResult()
        result.add_warning("Warning 1")
        result.add_warning("Warning 2")
        assert "Valid" in result.summary()
        assert "2 warnings" in result.summary()

    def test_summary_invalid(self):
        """Test summary output for invalid result."""
        result = MetadataValidationResult()
        result.add_error("Error 1")
        result.add_warning("Warning 1")
        assert "Invalid" in result.summary()
        assert "1 errors" in result.summary()
