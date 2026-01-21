"""
test_yaml_to_db_parser.py
-------------------------
Unit tests for dev.dataclasses.parsers.yaml_to_db module.

Tests the YamlToDbParser class which converts YAML frontmatter to database format.
Covers all parsing methods including cities, locations, people, dates, references,
and poems.

Target Coverage: 90%+
"""
import pytest
from datetime import date

from dev.dataclasses.parsers.yaml_to_db import YamlToDbParser


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def parser():
    """Create a parser with a standard test date."""
    return YamlToDbParser(date(2024, 1, 15), {})


@pytest.fixture
def parser_with_date():
    """Create a parser factory for specific dates."""
    def _create(entry_date: date):
        return YamlToDbParser(entry_date, {})
    return _create


# =============================================================================
# Test parse_city_field
# =============================================================================


class TestParseCityField:
    """Test parse_city_field method."""

    def test_single_city_string(self, parser):
        """Test parsing a single city as string."""
        result = parser.parse_city_field("Montreal")
        assert result == ["Montreal"]

    def test_city_string_with_whitespace(self, parser):
        """Test that whitespace is trimmed from city names."""
        result = parser.parse_city_field("  Toronto  ")
        assert result == ["Toronto"]

    def test_list_of_cities(self, parser):
        """Test parsing a list of cities."""
        result = parser.parse_city_field(["Montreal", "Toronto", "Vancouver"])
        assert result == ["Montreal", "Toronto", "Vancouver"]

    def test_list_with_whitespace(self, parser):
        """Test that whitespace is trimmed from list items."""
        result = parser.parse_city_field(["  Montreal  ", " Toronto "])
        assert result == ["Montreal", "Toronto"]

    def test_list_with_empty_strings(self, parser):
        """Test that empty strings are filtered out."""
        result = parser.parse_city_field(["Montreal", "", "  ", "Toronto"])
        assert result == ["Montreal", "Toronto"]

    def test_empty_list(self, parser):
        """Test parsing an empty list."""
        result = parser.parse_city_field([])
        assert result == []

    def test_invalid_type_returns_empty(self, parser):
        """Test that invalid types return empty list."""
        result = parser.parse_city_field(123)
        assert result == []

    def test_none_returns_empty(self, parser):
        """Test that None returns empty list."""
        result = parser.parse_city_field(None)
        assert result == []

    def test_mixed_types_in_list(self, parser):
        """Test list with mixed types converts to strings."""
        result = parser.parse_city_field(["Montreal", 123, "Toronto"])
        assert result == ["Montreal", "123", "Toronto"]


# =============================================================================
# Test parse_locations_field
# =============================================================================


class TestParseLocationsField:
    """Test parse_locations_field method."""

    def test_flat_list_single_city(self, parser):
        """Test flat list with single city."""
        result = parser.parse_locations_field(
            ["Café X", "Park Y"],
            ["Montreal"]
        )
        assert result == {"Montreal": ["Café X", "Park Y"]}

    def test_nested_dict_multiple_cities(self, parser):
        """Test nested dict with multiple cities."""
        result = parser.parse_locations_field(
            {"Montreal": ["Café X"], "Toronto": ["Park Y"]},
            ["Montreal", "Toronto"]
        )
        assert result == {"Montreal": ["Café X"], "Toronto": ["Park Y"]}

    def test_hyphen_to_space_conversion(self, parser):
        """Test that hyphens are converted to spaces in location names."""
        result = parser.parse_locations_field(
            ["Cinema-Moderne", "Café-Replika"],
            ["Montreal"]
        )
        assert result == {"Montreal": ["Cinema Moderne", "Café Replika"]}

    def test_underscore_preserves_hyphen(self, parser):
        """Test that underscore preserves hyphens in names."""
        result = parser.parse_locations_field(
            ["Rue_St-Hubert", "Place_Jean-Paul"],
            ["Montreal"]
        )
        # Underscore becomes space, hyphen preserved after underscore
        assert result == {"Montreal": ["Rue St-Hubert", "Place Jean-Paul"]}

    def test_flat_list_multiple_cities_returns_empty(self, parser):
        """Test flat list with multiple cities logs warning and returns empty."""
        result = parser.parse_locations_field(
            ["Café X", "Park Y"],
            ["Montreal", "Toronto"]
        )
        assert result == {}

    def test_nested_dict_single_location_string(self, parser):
        """Test nested dict with single location as string instead of list."""
        result = parser.parse_locations_field(
            {"Montreal": "Café X"},
            ["Montreal"]
        )
        assert result == {"Montreal": ["Café X"]}

    def test_whitespace_trimmed(self, parser):
        """Test that whitespace is trimmed from locations."""
        result = parser.parse_locations_field(
            ["  Café X  ", " Park Y "],
            ["Montreal"]
        )
        assert result == {"Montreal": ["Café X", "Park Y"]}

    def test_empty_list(self, parser):
        """Test parsing empty location list."""
        result = parser.parse_locations_field([], ["Montreal"])
        assert result == {"Montreal": []}

    def test_empty_dict(self, parser):
        """Test parsing empty location dict."""
        result = parser.parse_locations_field({}, ["Montreal"])
        assert result == {}


# =============================================================================
# Test parse_people_field
# =============================================================================


class TestParsePeopleField:
    """Test parse_people_field method."""

    def test_single_word_name(self, parser):
        """Test single word treated as name only."""
        result = parser.parse_people_field(["John"])
        assert result["people"] == [{"name": "John", "full_name": None}]
        assert result["alias"] == []

    def test_hyphenated_single_name(self, parser):
        """Test hyphenated single name converted to spaces."""
        result = parser.parse_people_field(["Jean-Paul"])
        assert result["people"] == [{"name": "Jean Paul", "full_name": None}]

    def test_multiple_word_name(self, parser):
        """Test multiple words treated as full_name."""
        result = parser.parse_people_field(["John Smith"])
        assert result["people"] == [{"name": "John", "full_name": "John Smith"}]

    def test_hyphenated_first_name_with_last_name(self, parser):
        """Test hyphenated first name with last name."""
        result = parser.parse_people_field(["María-José Castro"])
        assert result["people"] == [{"name": "María José", "full_name": "María José Castro"}]

    def test_name_with_expansion(self, parser):
        """Test name with full_name in parentheses."""
        result = parser.parse_people_field(["John (John Smith)"])
        assert result["people"] == [{"name": "John", "full_name": "John Smith"}]

    def test_hyphenated_name_with_expansion(self, parser):
        """Test hyphenated name with expansion."""
        result = parser.parse_people_field(["Jean-Paul (Jean-Paul Sartre)"])
        assert result["people"] == [{"name": "Jean Paul", "full_name": "Jean-Paul Sartre"}]

    def test_alias_simple(self, parser):
        """Test simple alias format."""
        result = parser.parse_people_field(["@Johnny"])
        assert result["alias"] == [{"alias": "Johnny"}]
        assert result["people"] == []

    def test_alias_with_name(self, parser):
        """Test alias with associated name."""
        result = parser.parse_people_field(["@Johnny (John)"])
        assert result["alias"] == [{"alias": "Johnny", "name": "John"}]

    def test_dict_format_person(self, parser):
        """Test dict format for person."""
        result = parser.parse_people_field([{"name": "John", "full_name": "John Smith"}])
        assert result["people"] == [{"name": "John", "full_name": "John Smith"}]

    def test_dict_format_alias(self, parser):
        """Test dict format for alias."""
        result = parser.parse_people_field([{"alias": "Johnny", "name": "John"}])
        assert result["alias"] == [{"alias": "Johnny", "name": "John"}]

    def test_mixed_formats(self, parser):
        """Test mixed string and dict formats."""
        result = parser.parse_people_field([
            "John",
            "@Johnny",
            {"name": "Jane", "full_name": "Jane Doe"}
        ])
        assert len(result["people"]) == 2
        assert len(result["alias"]) == 1

    def test_empty_string_filtered(self, parser):
        """Test empty strings are filtered out."""
        result = parser.parse_people_field(["", "  ", "John"])
        assert result["people"] == [{"name": "John", "full_name": None}]

    def test_non_string_non_dict_filtered(self, parser):
        """Test non-string non-dict items are filtered."""
        result = parser.parse_people_field([123, None, "John"])
        assert result["people"] == [{"name": "John", "full_name": None}]

    def test_empty_list(self, parser):
        """Test empty list returns empty structure."""
        result = parser.parse_people_field([])
        assert result == {"people": [], "alias": []}


# =============================================================================
# Test find_person_in_parsed
# =============================================================================


class TestFindPersonInParsed:
    """Test find_person_in_parsed static method."""

    def test_exact_name_match(self):
        """Test finding person by exact name match."""
        people_parsed = {
            "people": [{"name": "John", "full_name": "John Smith"}],
            "alias": []
        }
        result = YamlToDbParser.find_person_in_parsed("John", people_parsed)
        assert result == {"name": "John", "full_name": "John Smith"}

    def test_exact_full_name_match(self):
        """Test finding person by exact full_name match."""
        people_parsed = {
            "people": [{"name": "John", "full_name": "John Smith"}],
            "alias": []
        }
        result = YamlToDbParser.find_person_in_parsed("John Smith", people_parsed)
        assert result == {"name": "John", "full_name": "John Smith"}

    def test_alias_lookup(self):
        """Test finding person by @alias format."""
        people_parsed = {
            "people": [],
            "alias": [{"alias": "Johnny", "name": "John"}]
        }
        result = YamlToDbParser.find_person_in_parsed("@Johnny", people_parsed)
        assert result == {"alias": "Johnny", "name": "John"}

    def test_alias_not_found(self):
        """Test alias not found returns None."""
        people_parsed = {
            "people": [],
            "alias": [{"alias": "Johnny", "name": "John"}]
        }
        result = YamlToDbParser.find_person_in_parsed("@Bobby", people_parsed)
        assert result is None

    def test_person_not_found(self):
        """Test person not found returns None."""
        people_parsed = {"people": [{"name": "John"}], "alias": []}
        result = YamlToDbParser.find_person_in_parsed("Jane", people_parsed)
        assert result is None

    def test_first_name_partial_match(self):
        """Test matching first word of compound name."""
        people_parsed = {
            "people": [{"name": "Daniel", "full_name": "Daniel Andrews"}],
            "alias": []
        }
        # This should match because "Daniel" is the name field
        result = YamlToDbParser.find_person_in_parsed("Daniel", people_parsed)
        assert result == {"name": "Daniel", "full_name": "Daniel Andrews"}

    def test_whitespace_trimmed(self):
        """Test that search string whitespace is trimmed."""
        people_parsed = {"people": [{"name": "John"}], "alias": []}
        result = YamlToDbParser.find_person_in_parsed("  John  ", people_parsed)
        assert result == {"name": "John"}

    def test_empty_people_parsed(self):
        """Test searching in empty structure."""
        people_parsed = {"people": [], "alias": []}
        result = YamlToDbParser.find_person_in_parsed("John", people_parsed)
        assert result is None


# =============================================================================
# Test parse_dates_field
# =============================================================================


class TestParseDatesField:
    """Test parse_dates_field method."""

    def test_simple_date_string(self, parser):
        """Test parsing simple date string."""
        dates, exclude = parser.parse_dates_field(["2024-06-01"], None)
        assert len(dates) == 1
        assert dates[0]["date"] == "2024-06-01"
        assert exclude is False

    def test_date_with_inline_context(self, parser):
        """Test parsing date with inline context."""
        dates, exclude = parser.parse_dates_field(
            ["2024-06-01 (birthday party)"], None
        )
        assert dates[0]["date"] == "2024-06-01"
        assert "context" in dates[0]
        assert "birthday party" in dates[0]["context"]

    def test_nested_dict_format(self, parser):
        """Test parsing nested dict format."""
        dates, exclude = parser.parse_dates_field(
            [{"date": "2024-06-01", "context": "celebration"}], None
        )
        assert dates[0]["date"] == "2024-06-01"
        assert dates[0]["context"] == "celebration"

    def test_entry_date_shorthand(self, parser):
        """Test '.' shorthand for entry date."""
        dates, exclude = parser.parse_dates_field(
            [{"date": "."}], None
        )
        assert dates[0]["date"] == "2024-01-15"  # parser fixture date

    def test_opt_out_marker(self, parser):
        """Test '~' marker sets exclude flag."""
        dates, exclude = parser.parse_dates_field(["~"], None)
        assert dates == []
        assert exclude is True

    def test_none_sets_exclude_flag(self, parser):
        """Test None sets exclude flag."""
        dates, exclude = parser.parse_dates_field([None], None)
        assert dates == []
        assert exclude is True

    def test_invalid_date_skipped(self, parser):
        """Test invalid date format is skipped with warning."""
        dates, exclude = parser.parse_dates_field(["invalid-date"], None)
        assert dates == []

    def test_date_dict_missing_date_field(self, parser):
        """Test dict missing 'date' field is skipped."""
        dates, exclude = parser.parse_dates_field(
            [{"context": "celebration"}], None
        )
        assert dates == []

    def test_date_with_locations(self, parser):
        """Test date with locations field."""
        dates, exclude = parser.parse_dates_field(
            [{"date": "2024-06-01", "locations": ["Café X", "Park Y"]}], None
        )
        assert "locations" in dates[0]
        assert "Café X" in dates[0]["locations"]
        assert "Park Y" in dates[0]["locations"]

    def test_date_with_single_location_string(self, parser):
        """Test date with single location as string."""
        dates, exclude = parser.parse_dates_field(
            [{"date": "2024-06-01", "locations": "Café X"}], None
        )
        assert dates[0]["locations"] == ["Café X"]

    def test_date_with_people_lookup(self, parser):
        """Test date with people field that looks up in people_parsed."""
        people_parsed = {
            "people": [{"name": "Alice", "full_name": "Alice Smith"}],
            "alias": []
        }
        dates, exclude = parser.parse_dates_field(
            [{"date": "2024-06-01", "people": "Alice"}],
            people_parsed
        )
        assert "people" in dates[0]
        assert dates[0]["people"][0] == {"name": "Alice", "full_name": "Alice Smith"}

    def test_date_with_people_list(self, parser):
        """Test date with list of people."""
        people_parsed = {
            "people": [
                {"name": "Alice"},
                {"name": "Bob"}
            ],
            "alias": []
        }
        dates, exclude = parser.parse_dates_field(
            [{"date": "2024-06-01", "people": ["Alice", "Bob"]}],
            people_parsed
        )
        assert len(dates[0]["people"]) == 2

    def test_date_with_people_dict(self, parser):
        """Test date with people as dict (passed through as-is)."""
        dates, exclude = parser.parse_dates_field(
            [{"date": "2024-06-01", "people": [{"name": "Custom"}]}],
            {"people": [], "alias": []}
        )
        assert dates[0]["people"][0] == {"name": "Custom"}

    def test_context_with_people_refs(self, parser):
        """Test context with @person references extracted."""
        people_parsed = {
            "people": [{"name": "Alice"}],
            "alias": []
        }
        dates, exclude = parser.parse_dates_field(
            [{"date": "2024-06-01", "context": "Meeting with @Alice"}],
            people_parsed
        )
        assert "people" in dates[0]

    def test_context_with_location_refs(self, parser):
        """Test context with #location references extracted."""
        dates, exclude = parser.parse_dates_field(
            [{"date": "2024-06-01", "context": "Coffee at #Cafe"}],
            None
        )
        assert "locations" in dates[0]
        assert "Cafe" in dates[0]["locations"]

    def test_single_dict_converted_to_list(self, parser):
        """Test single dict input is converted to list."""
        dates, exclude = parser.parse_dates_field(
            {"date": "2024-06-01"},
            None
        )
        assert len(dates) == 1

    def test_datetime_date_object(self, parser):
        """Test date field as datetime.date object."""
        dates, exclude = parser.parse_dates_field(
            [{"date": date(2024, 6, 1)}],
            None
        )
        assert dates[0]["date"] == "2024-06-01"

    def test_multiple_dates(self, parser):
        """Test parsing multiple dates."""
        dates, exclude = parser.parse_dates_field(
            ["2024-06-01", "2024-06-15", "2024-07-01"],
            None
        )
        assert len(dates) == 3

    def test_date_with_events_string(self, parser):
        """Test date with single event as string."""
        dates, exclude = parser.parse_dates_field(
            [{"date": "2024-06-01", "events": "summer-trip"}],
            None
        )
        assert "events" in dates[0]
        assert dates[0]["events"] == ["summer trip"]

    def test_date_with_events_list(self, parser):
        """Test date with multiple events as list."""
        dates, exclude = parser.parse_dates_field(
            [{"date": "2024-06-01", "events": ["summer-trip", "europe-2024"]}],
            None
        )
        assert "events" in dates[0]
        assert len(dates[0]["events"]) == 2
        assert "summer trip" in dates[0]["events"]
        assert "europe 2024" in dates[0]["events"]

    def test_date_with_events_and_other_fields(self, parser):
        """Test date with events combined with people, locations, context."""
        people_parsed = {
            "people": [{"name": "Alice"}],
            "alias": []
        }
        dates, exclude = parser.parse_dates_field(
            [{
                "date": "2024-06-01",
                "context": "First day of vacation",
                "events": ["summer-trip"],
                "locations": ["Airport"],
                "people": "Alice"
            }],
            people_parsed
        )
        assert dates[0]["events"] == ["summer trip"]
        assert dates[0]["locations"] == ["Airport"]
        assert "people" in dates[0]
        assert "context" in dates[0]

    def test_date_with_empty_events(self, parser):
        """Test date with empty events list is not included."""
        dates, exclude = parser.parse_dates_field(
            [{"date": "2024-06-01", "events": []}],
            None
        )
        assert "events" not in dates[0]

    # --- Reference type tests ---

    def test_simple_date_has_moment_type(self, parser):
        """Test simple date string defaults to 'moment' type."""
        dates, exclude = parser.parse_dates_field(["2024-06-01"], None)
        assert dates[0]["type"] == "moment"

    def test_dict_date_defaults_to_moment_type(self, parser):
        """Test dict date defaults to 'moment' type."""
        dates, exclude = parser.parse_dates_field(
            [{"date": "2024-06-01", "context": "meeting"}],
            None
        )
        assert dates[0]["type"] == "moment"

    def test_reference_prefix_string(self, parser):
        """Test ~prefix marks date as reference type."""
        dates, exclude = parser.parse_dates_field(
            ["~2024-01-11 (negatives from anti-date)"],
            None
        )
        assert len(dates) == 1
        assert dates[0]["date"] == "2024-01-11"
        assert dates[0]["type"] == "reference"
        assert "negatives from anti-date" in dates[0]["context"]

    def test_reference_prefix_simple_date(self, parser):
        """Test ~prefix on simple date (no context)."""
        dates, exclude = parser.parse_dates_field(["~2024-01-11"], None)
        assert dates[0]["date"] == "2024-01-11"
        assert dates[0]["type"] == "reference"

    def test_reference_prefix_with_space(self, parser):
        """Test ~prefix with space after tilde."""
        dates, exclude = parser.parse_dates_field(
            ["~ 2024-01-11 (with space)"],
            None
        )
        assert dates[0]["date"] == "2024-01-11"
        assert dates[0]["type"] == "reference"

    def test_dict_with_type_reference(self, parser):
        """Test dict with explicit type: reference."""
        dates, exclude = parser.parse_dates_field(
            [{"date": "2024-01-11", "type": "reference", "context": "old negatives"}],
            None
        )
        assert dates[0]["type"] == "reference"
        assert dates[0]["date"] == "2024-01-11"

    def test_dict_with_type_moment_explicit(self, parser):
        """Test dict with explicit type: moment."""
        dates, exclude = parser.parse_dates_field(
            [{"date": "2024-06-01", "type": "moment", "context": "actual event"}],
            None
        )
        assert dates[0]["type"] == "moment"

    def test_invalid_type_defaults_to_moment(self, parser):
        """Test invalid type value defaults to 'moment'."""
        dates, exclude = parser.parse_dates_field(
            [{"date": "2024-06-01", "type": "invalid"}],
            None
        )
        assert dates[0]["type"] == "moment"

    def test_tilde_alone_still_opt_out(self, parser):
        """Test ~ alone (without date) still triggers opt-out."""
        dates, exclude = parser.parse_dates_field(["~"], None)
        assert dates == []
        assert exclude is True

    def test_mixed_moments_and_references(self, parser):
        """Test mixing moments and references in same dates field."""
        dates, exclude = parser.parse_dates_field([
            "2024-06-01 (actual event)",
            "~2024-01-11 (reference to old date)",
            {"date": "2024-07-01", "type": "reference", "context": "another ref"}
        ], None)
        assert len(dates) == 3
        assert dates[0]["type"] == "moment"
        assert dates[1]["type"] == "reference"
        assert dates[2]["type"] == "reference"

    def test_reference_with_locations(self, parser):
        """Test reference type with locations."""
        dates, exclude = parser.parse_dates_field(
            [{"date": "2024-01-11", "type": "reference", "locations": ["Old Café"]}],
            None
        )
        assert dates[0]["type"] == "reference"
        assert "locations" in dates[0]

    def test_reference_with_people(self, parser):
        """Test reference type with people."""
        people_parsed = {"people": [{"name": "Clara"}], "alias": []}
        dates, exclude = parser.parse_dates_field(
            [{"date": "2024-01-11", "type": "reference", "people": ["Clara"]}],
            people_parsed
        )
        assert dates[0]["type"] == "reference"
        assert "people" in dates[0]


# =============================================================================
# Test parse_references_field
# =============================================================================


class TestParseReferencesField:
    """Test parse_references_field method."""

    def test_reference_with_content(self, parser):
        """Test reference with content field."""
        refs = parser.parse_references_field([{
            "content": "Quote text here"
        }])
        assert refs[0]["content"] == "Quote text here"

    def test_reference_with_description(self, parser):
        """Test reference with description field."""
        refs = parser.parse_references_field([{
            "description": "Summary of the idea"
        }])
        assert refs[0]["description"] == "Summary of the idea"

    def test_reference_with_mode(self, parser):
        """Test reference with mode field."""
        refs = parser.parse_references_field([{
            "content": "Quote",
            "mode": "paraphrase"
        }])
        assert refs[0]["mode"] == "paraphrase"

    def test_reference_with_speaker(self, parser):
        """Test reference with speaker field."""
        refs = parser.parse_references_field([{
            "content": "Quote",
            "speaker": "Alice"
        }])
        assert refs[0]["speaker"] == "Alice"

    def test_reference_with_source(self, parser):
        """Test reference with source object."""
        refs = parser.parse_references_field([{
            "content": "Quote",
            "source": {
                "title": "Book Title",
                "type": "book",
                "author": "Author Name"
            }
        }])
        assert refs[0]["source"]["title"] == "Book Title"
        assert refs[0]["source"]["type"] == "book"
        assert refs[0]["source"]["author"] == "Author Name"

    def test_reference_source_partial(self, parser):
        """Test reference with partial source (no author)."""
        refs = parser.parse_references_field([{
            "content": "Quote",
            "source": {
                "title": "Article Title",
                "type": "article"
            }
        }])
        assert "author" not in refs[0]["source"]

    def test_non_dict_item_filtered(self, parser):
        """Test non-dict items are filtered out."""
        refs = parser.parse_references_field([
            "string item",
            {"content": "Valid ref"}
        ])
        assert len(refs) == 1
        assert refs[0]["content"] == "Valid ref"

    def test_empty_ref_dict_filtered(self, parser):
        """Test empty dict is filtered out."""
        refs = parser.parse_references_field([{}])
        assert refs == []

    def test_multiple_references(self, parser):
        """Test parsing multiple references."""
        refs = parser.parse_references_field([
            {"content": "Quote 1"},
            {"content": "Quote 2", "mode": "direct"},
            {"description": "Summary"}
        ])
        assert len(refs) == 3

    def test_empty_list(self, parser):
        """Test parsing empty list."""
        refs = parser.parse_references_field([])
        assert refs == []


# =============================================================================
# Test parse_poems_field
# =============================================================================


class TestParsePoemsField:
    """Test parse_poems_field method."""

    def test_complete_poem(self, parser):
        """Test parsing complete poem with all fields."""
        poems = parser.parse_poems_field([{
            "title": "Ode to Joy",
            "content": "Beautiful spark of divinity...",
            "revision_date": "2024-01-10",
            "notes": "First draft"
        }])
        assert poems[0]["title"] == "Ode to Joy"
        assert poems[0]["content"] == "Beautiful spark of divinity..."
        assert poems[0]["revision_date"] == date(2024, 1, 10)
        assert poems[0]["notes"] == "First draft"

    def test_poem_minimal(self, parser):
        """Test poem with only required fields."""
        poems = parser.parse_poems_field([{
            "title": "Short Poem",
            "content": "Line one..."
        }])
        assert poems[0]["title"] == "Short Poem"
        assert poems[0]["content"] == "Line one..."
        # Default to entry date when not specified
        assert poems[0]["revision_date"] == date(2024, 1, 15)

    def test_poem_missing_title(self, parser):
        """Test poem missing title is skipped."""
        poems = parser.parse_poems_field([{
            "content": "Content without title"
        }])
        assert poems == []

    def test_poem_empty_title(self, parser):
        """Test poem with empty title is skipped."""
        poems = parser.parse_poems_field([{
            "title": "",
            "content": "Content"
        }])
        assert poems == []

    def test_poem_missing_content(self, parser):
        """Test poem missing content is skipped."""
        poems = parser.parse_poems_field([{
            "title": "Title without content"
        }])
        assert poems == []

    def test_poem_empty_content(self, parser):
        """Test poem with empty content is skipped."""
        poems = parser.parse_poems_field([{
            "title": "Title",
            "content": ""
        }])
        assert poems == []

    def test_poem_invalid_revision_date_uses_entry_date(self, parser):
        """Test invalid revision_date falls back to entry date."""
        poems = parser.parse_poems_field([{
            "title": "Poem",
            "content": "Content",
            "revision_date": "invalid-date"
        }])
        assert poems[0]["revision_date"] == date(2024, 1, 15)

    def test_poem_revision_date_as_date_object(self, parser):
        """Test revision_date as datetime.date object."""
        poems = parser.parse_poems_field([{
            "title": "Poem",
            "content": "Content",
            "revision_date": date(2024, 3, 20)
        }])
        assert poems[0]["revision_date"] == date(2024, 3, 20)

    def test_non_dict_item_filtered(self, parser):
        """Test non-dict items are filtered out."""
        poems = parser.parse_poems_field([
            "string item",
            {"title": "Valid", "content": "Poem"}
        ])
        assert len(poems) == 1

    def test_multiple_poems(self, parser):
        """Test parsing multiple poems."""
        poems = parser.parse_poems_field([
            {"title": "Poem 1", "content": "Content 1"},
            {"title": "Poem 2", "content": "Content 2"},
        ])
        assert len(poems) == 2

    def test_empty_list(self, parser):
        """Test parsing empty list."""
        poems = parser.parse_poems_field([])
        assert poems == []

    def test_poem_notes_normalized(self, parser):
        """Test that notes field is normalized (whitespace trimmed)."""
        poems = parser.parse_poems_field([{
            "title": "Poem",
            "content": "Content",
            "notes": "  Some notes  "
        }])
        assert poems[0]["notes"] == "Some notes"

    def test_poem_empty_notes_omitted(self, parser):
        """Test that empty notes are omitted."""
        poems = parser.parse_poems_field([{
            "title": "Poem",
            "content": "Content",
            "notes": "   "
        }])
        assert "notes" not in poems[0]
