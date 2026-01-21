"""
test_wiki_utils.py
------------------
Unit tests for dev.utils.wiki module.

Tests wiki utilities including slugify, entity paths, and file parsing.

Target Coverage: 95%+
"""
from pathlib import Path

from dev.utils.wiki import (
    slugify,
    entity_filename,
    entity_path,
)


class TestSlugify:
    """Test slugify function."""

    def test_simple_name(self):
        """Test simple name slugification."""
        assert slugify("María José") == "maría_josé"

    def test_multiple_spaces(self):
        """Test name with multiple spaces."""
        assert slugify("New York City") == "new_york_city"

    def test_with_forward_slash(self):
        """Test name with forward slash (category separator)."""
        assert slugify("The Person/Character") == "the_person-character"

    def test_no_spaces(self):
        """Test name without spaces."""
        assert slugify("Montreal") == "montreal"

    def test_mixed_case(self):
        """Test mixed case gets lowercased."""
        assert slugify("CamelCase Name") == "camelcase_name"

    def test_unicode_preserved(self):
        """Test unicode characters are preserved."""
        assert slugify("Café Montréal") == "café_montréal"

    def test_empty_string(self):
        """Test empty string."""
        assert slugify("") == ""


class TestEntityFilename:
    """Test entity_filename function."""

    def test_simple_name(self):
        """Test simple name gets .md extension."""
        assert entity_filename("María José") == "maría_josé.md"

    def test_with_slash(self):
        """Test name with slash."""
        assert entity_filename("Film/Book") == "film-book.md"

    def test_already_lowercase(self):
        """Test already lowercase name."""
        assert entity_filename("simple name") == "simple_name.md"


class TestEntityPath:
    """Test entity_path function."""

    def test_people_path(self):
        """Test path generation for people directory."""
        result = entity_path(Path("/wiki"), "people", "María José")
        assert result == Path("/wiki/people/maría_josé.md")

    def test_locations_path(self):
        """Test path generation for locations directory."""
        result = entity_path(Path("/wiki"), "locations", "Café Central")
        assert result == Path("/wiki/locations/café_central.md")

    def test_events_path(self):
        """Test path generation for events directory."""
        result = entity_path(Path("/wiki"), "events", "Birthday Party")
        assert result == Path("/wiki/events/birthday_party.md")

    def test_nested_wiki_dir(self):
        """Test with nested wiki directory."""
        result = entity_path(Path("/home/user/wiki"), "tags", "My Tag")
        assert result == Path("/home/user/wiki/tags/my_tag.md")
