import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from datetime import date

from dev.builders.wiki_indexes import (
    build_people_index,
    build_entries_index,
    build_locations_index,
)

# Mock classes to simulate WikiPerson, WikiEntry, WikiLocation
class MockPerson:
    def __init__(self, name, path, category="Unsorted", mentions=1):
        self.name = name
        self.path = path
        self.category = category
        self.mentions = mentions

class MockEntry:
    def __init__(self, date_obj, path, word_count=500):
        self.date = date_obj
        self.path = path
        self.word_count = word_count

class MockLocation:
    def __init__(self, name, path, country="Unknown", region="Unspecified", city="Unknown City", mentions=1):
        self.name = name
        self.path = path
        self.country = country
        self.region = region
        self.city = city
        self.mentions = mentions

class TestWikiIndexes:
    """Test custom index builders for wiki entities."""

    @pytest.fixture
    def wiki_dir(self, tmp_path):
        return tmp_path / "wiki"

    @patch("dev.builders.wiki_indexes.write_if_changed")
    def test_build_people_index(self, mock_write, wiki_dir):
        """Test people index generation grouped by category."""
        people = [
            MockPerson("Alice", wiki_dir / "people/alice.md", category="Friend", mentions=5),
            MockPerson("Bob", wiki_dir / "people/bob.md", category="Family", mentions=10),
            MockPerson("Charlie", wiki_dir / "people/charlie.md", category="Friend", mentions=2),
        ]

        build_people_index(people, wiki_dir)

        # Check call arguments
        args, _ = mock_write.call_args
        path, content, force = args

        assert path == wiki_dir / "people" / "people.md"
        assert "# Palimpsest — People" in content
        assert "## Friend" in content
        assert "## Family" in content
        
        # Check ordering (Family before Friend based on CATEGORY_ORDER if defined, otherwise by insertion/defaultdict)
        # Actually CATEGORY_ORDER is defined in module. Family is index 0, Friend is index 1.
        family_pos = content.find("## Family")
        friend_pos = content.find("## Friend")
        assert family_pos < friend_pos

        # Check sorting within category (Alice 5 mentions vs Charlie 2 mentions)
        alice_pos = content.find("Alice")
        charlie_pos = content.find("Charlie")
        assert alice_pos < charlie_pos

    @patch("dev.builders.wiki_indexes.write_if_changed")
    def test_build_entries_index(self, mock_write, wiki_dir):
        """Test entries index generation grouped by year."""
        entries = [
            MockEntry(date(2024, 1, 15), wiki_dir / "entries/2024/2024-01-15.md"),
            MockEntry(date(2023, 12, 31), wiki_dir / "entries/2023/2023-12-31.md"),
            MockEntry(date(2024, 2, 20), wiki_dir / "entries/2024/2024-02-20.md"),
        ]

        build_entries_index(entries, wiki_dir)

        args, _ = mock_write.call_args
        path, content, _ = args

        assert path == wiki_dir / "entries" / "entries.md"
        assert "# Palimpsest — Journal Entries" in content
        assert "## 2024" in content
        assert "## 2023" in content
        
        # Check reverse chronological year order
        year_2024_pos = content.find("## 2024")
        year_2023_pos = content.find("## 2023")
        assert year_2024_pos < year_2023_pos

        # Check chronological entry order within year
        jan_pos = content.find("January 15")
        feb_pos = content.find("February 20")
        assert jan_pos < feb_pos

    @patch("dev.builders.wiki_indexes.write_if_changed")
    def test_build_locations_index(self, mock_write, wiki_dir):
        """Test locations index generation with hierarchy."""
        locations = [
            MockLocation("Eiffel Tower", wiki_dir / "locations/eiffel.md", country="France", region="IDF", city="Paris"),
            MockLocation("Louvre", wiki_dir / "locations/louvre.md", country="France", region="IDF", city="Paris"),
            MockLocation("Big Ben", wiki_dir / "locations/big_ben.md", country="UK", region="London", city="London"),
        ]

        build_locations_index(locations, wiki_dir)

        args, _ = mock_write.call_args
        path, content, _ = args

        assert path == wiki_dir / "locations" / "locations.md"
        assert "## France" in content
        assert "### IDF" in content
        assert "#### Paris" in content
        assert "Eiffel Tower" in content
        assert "## UK" in content
