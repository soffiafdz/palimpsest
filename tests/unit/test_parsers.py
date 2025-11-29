"""
test_parsers.py
---------------
Unit tests for dev.utils.parsers module.

Tests parsing functions for extracting structured data from formatted text,
including names, expansions, context references, and date contexts.

Target Coverage: 95%+
"""
from dev.utils.parsers import (
    extract_name_and_expansion,
    extract_context_refs,
    format_person_ref,
    format_location_ref,
    parse_date_context,
    split_hyphenated_to_spaces,
    spaces_to_hyphenated,
)


class TestExtractNameAndExpansion:
    """Test extract_name_and_expansion function."""

    def test_basic_parenthetical_notation(self):
        """Test basic name with expansion."""
        name, expansion = extract_name_and_expansion("Mtl (Montreal)")
        assert name == "Mtl"
        assert expansion == "Montreal"

    def test_no_parentheses(self):
        """Test name without expansion."""
        name, expansion = extract_name_and_expansion("Madrid")
        assert name == "Madrid"
        assert expansion is None

    def test_hyphenated_name_with_expansion(self):
        """Test hyphenated name with full expansion."""
        name, expansion = extract_name_and_expansion("María-José (María José García)")
        assert name == "María-José"
        assert expansion == "María José García"

    def test_name_with_spaces(self):
        """Test name with internal spaces."""
        name, expansion = extract_name_and_expansion("New York (New York City)")
        assert name == "New York"
        assert expansion == "New York City"

    def test_whitespace_trimmed(self):
        """Test leading/trailing whitespace is trimmed."""
        name, expansion = extract_name_and_expansion("  Bob   (  Robert Smith  )  ")
        assert name == "Bob"
        assert expansion == "Robert Smith"

    def test_empty_expansion(self):
        """Test empty parentheses."""
        name, expansion = extract_name_and_expansion("Name ()")
        assert name == "Name"
        assert expansion == ""

    def test_unicode_characters(self):
        """Test unicode characters in name and expansion."""
        name, expansion = extract_name_and_expansion("Café (Café de l'Époque)")
        assert name == "Café"
        assert expansion == "Café de l'Époque"

    def test_parentheses_in_middle_not_extracted(self):
        """Test parentheses not at end are not treated as expansion."""
        name, expansion = extract_name_and_expansion("Bob (middle) Smith")
        assert name == "Bob (middle) Smith"
        assert expansion is None

    def test_nested_parentheses(self):
        """Test nested parentheses in expansion."""
        name, expansion = extract_name_and_expansion("Short (Long (Very Long))")
        assert name == "Short"
        assert expansion == "Long (Very Long"  # Only strips last )


class TestExtractContextRefs:
    """Test extract_context_refs function."""

    def test_people_references(self):
        """Test extracting @people references."""
        result = extract_context_refs("Dinner with @Alice and @Bob")
        assert result["context"] == "Dinner with Alice and Bob"
        assert "Alice" in result["people"]
        assert "Bob" in result["people"]
        assert len(result["people"]) == 2

    def test_location_references(self):
        """Test extracting #location references."""
        result = extract_context_refs("Meeting at #Cafe and #Library")
        assert result["context"] == "Meeting at Cafe and Library"
        assert "Cafe" in result["locations"]
        assert "Library" in result["locations"]
        assert len(result["locations"]) == 2

    def test_mixed_references(self):
        """Test extracting both people and location references."""
        result = extract_context_refs("Dinner with @Majo and @Aliza at #Aliza's")
        assert result["context"] == "Dinner with Majo and Aliza at Aliza's"
        assert set(result["people"]) == {"Majo", "Aliza"}
        assert "Aliza's" in result["locations"]

    def test_hyphenated_names_converted_to_spaces(self):
        """Test hyphenated names are converted to spaces."""
        result = extract_context_refs("Meeting @María-José at #Café-Central")
        assert "María José" in result["people"]
        assert "Café Central" in result["locations"]

    def test_punctuation_stripped(self):
        """Test punctuation is stripped from references."""
        result = extract_context_refs("Met @Alice, @Bob, and @Charlie!")
        assert len(result["people"]) == 3
        assert "Alice" in result["people"]
        assert "Bob" in result["people"]
        assert "Charlie" in result["people"]

    def test_location_with_punctuation(self):
        """Test location references with punctuation."""
        result = extract_context_refs("At #Cafe, then #Library.")
        assert len(result["locations"]) == 2
        assert "Cafe" in result["locations"]
        assert "Library" in result["locations"]

    def test_empty_context(self):
        """Test empty context returns empty dict."""
        result = extract_context_refs("")
        assert result == {}

    def test_none_context(self):
        """Test None context returns empty dict."""
        result = extract_context_refs(None)  # type: ignore
        assert result == {}

    def test_no_references(self):
        """Test text without @ or # references."""
        result = extract_context_refs("Just plain text")
        assert result["context"] == "Just plain text"
        assert "people" not in result
        assert "locations" not in result

    def test_multiple_word_reference(self):
        """Test @ reference treated as @ for location when specified."""
        result = extract_context_refs("Thesis seminar at @The-Neuro")
        # Based on the docstring example, @ can reference locations sometimes
        assert result["context"] == "Thesis seminar at The Neuro"

    def test_reference_at_start(self):
        """Test reference at start of context."""
        result = extract_context_refs("@Alice went to #Cafe")
        assert result["context"] == "Alice went to Cafe"
        assert "Alice" in result["people"]
        assert "Cafe" in result["locations"]

    def test_reference_at_end(self):
        """Test reference at end of context."""
        result = extract_context_refs("Went with @Alice")
        assert result["context"] == "Went with Alice"
        assert "Alice" in result["people"]


class TestFormatPersonRef:
    """Test format_person_ref function."""

    def test_single_word_name(self):
        """Test formatting single word name."""
        assert format_person_ref("Alice") == "@Alice"

    def test_multi_word_name(self):
        """Test multi-word names are hyphenated."""
        assert format_person_ref("Bob Smith") == "@Bob-Smith"

    def test_already_hyphenated(self):
        """Test already hyphenated name."""
        assert format_person_ref("María-José") == "@María-José"

    def test_three_word_name(self):
        """Test three word name."""
        assert format_person_ref("John Doe Jr") == "@John-Doe-Jr"


class TestFormatLocationRef:
    """Test format_location_ref function."""

    def test_single_word_location(self):
        """Test formatting single word location."""
        assert format_location_ref("Montreal") == "#Montreal"

    def test_multi_word_location(self):
        """Test multi-word locations are hyphenated."""
        assert format_location_ref("New York") == "#New-York"

    def test_already_hyphenated(self):
        """Test already hyphenated location."""
        assert format_location_ref("San-Diego") == "#San-Diego"


class TestParseDateContext:
    """Test parse_date_context function."""

    def test_date_with_context(self):
        """Test parsing date with context."""
        date_str, context = parse_date_context("2024-01-15 (therapy)")
        assert date_str == "2024-01-15"
        assert context == "therapy"

    def test_date_without_context(self):
        """Test parsing date without context."""
        date_str, context = parse_date_context("2024-01-15")
        assert date_str == "2024-01-15"
        assert context is None

    def test_multi_word_context(self):
        """Test context with multiple words."""
        date_str, context = parse_date_context("2024-06-01 (thesis defense exam)")
        assert date_str == "2024-06-01"
        assert context == "thesis defense exam"

    def test_whitespace_trimmed(self):
        """Test whitespace is trimmed."""
        date_str, context = parse_date_context("  2024-01-15  (  therapy  )  ")
        assert date_str == "2024-01-15"
        assert context == "therapy"

    def test_empty_context_parentheses(self):
        """Test empty parentheses."""
        date_str, context = parse_date_context("2024-01-15 ()")
        assert date_str == "2024-01-15"
        assert context == ""

    def test_parentheses_in_middle(self):
        """Test parentheses not at end are not treated as context."""
        date_str, context = parse_date_context("2024 (year) -01-15")
        assert date_str == "2024 (year) -01-15"
        assert context is None


class TestSplitHyphenatedToSpaces:
    """Test split_hyphenated_to_spaces function."""

    def test_single_hyphen(self):
        """Test converting single hyphen to space."""
        assert split_hyphenated_to_spaces("María-José") == "María José"

    def test_multiple_hyphens(self):
        """Test converting multiple hyphens."""
        assert split_hyphenated_to_spaces("New-York-City") == "New York City"

    def test_no_hyphens(self):
        """Test text without hyphens unchanged."""
        assert split_hyphenated_to_spaces("Montreal") == "Montreal"

    def test_hyphen_at_start(self):
        """Test hyphen at start."""
        assert split_hyphenated_to_spaces("-Start") == " Start"

    def test_hyphen_at_end(self):
        """Test hyphen at end."""
        assert split_hyphenated_to_spaces("End-") == "End "

    def test_consecutive_hyphens(self):
        """Test consecutive hyphens."""
        assert split_hyphenated_to_spaces("A--B") == "A  B"


class TestSpacesToHyphenated:
    """Test spaces_to_hyphenated function."""

    def test_single_space(self):
        """Test converting single space to hyphen."""
        assert spaces_to_hyphenated("María José") == "María-José"

    def test_multiple_spaces(self):
        """Test converting multiple spaces."""
        assert spaces_to_hyphenated("New York City") == "New-York-City"

    def test_no_spaces(self):
        """Test text without spaces unchanged."""
        assert spaces_to_hyphenated("Montreal") == "Montreal"

    def test_space_at_start(self):
        """Test space at start."""
        assert spaces_to_hyphenated(" Start") == "-Start"

    def test_space_at_end(self):
        """Test space at end."""
        assert spaces_to_hyphenated("End ") == "End-"

    def test_consecutive_spaces(self):
        """Test consecutive spaces."""
        assert spaces_to_hyphenated("A  B") == "A--B"

    def test_round_trip_conversion(self):
        """Test converting back and forth."""
        original = "María José García"
        hyphenated = spaces_to_hyphenated(original)
        assert hyphenated == "María-José-García"
        restored = split_hyphenated_to_spaces(hyphenated)
        assert restored == original
