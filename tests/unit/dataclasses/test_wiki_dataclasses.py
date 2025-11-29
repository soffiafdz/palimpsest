import pytest
from pathlib import Path
from unittest.mock import MagicMock
from datetime import date

from dev.dataclasses.wiki_person import Person

class TestWikiDataclasses:
    """Test Wiki-related dataclasses (Person)."""

    @pytest.fixture
    def mock_db_person(self):
        """Create a mock database Person object."""
        db_person = MagicMock()
        db_person.display_name = "Alice Smith"
        db_person.relation_type.display_name = "Friend"
        db_person.notes = "Initial db notes"
        
        # Mock dates/appearances
        date1 = MagicMock()
        date1.date = date(2024, 1, 1)
        date1.context = "Met at coffee shop"
        
        entry1 = MagicMock()
        entry1.date = date(2024, 1, 1)
        entry1.file_path = "/path/to/journal/2024/2024-01-01.md"
        date1.entries = [entry1]
        
        db_person.dates = [date1]
        db_person.entries = [] # Fallback not used if dates present
        
        # Mock aliases
        alias1 = MagicMock()
        alias1.alias = "Alice"
        db_person.aliases = [alias1]
        
        return db_person

    def test_person_roundtrip(self, tmp_path, mock_db_person):
        """Test Person creation from DB, export to Wiki, and parsing from file."""
        wiki_dir = tmp_path / "wiki"
        
        # 1. From Database
        person = Person.from_database(mock_db_person, wiki_dir)
        
        assert person.name == "Alice Smith"
        assert person.category == "Friend"
        assert "Alice" in person.alias
        assert len(person.appearances) == 1
        assert person.appearances[0]["date"] == date(2024, 1, 1)
        assert person.appearances[0]["note"] == "Met at coffee shop"
        
        # 2. To Wiki (Render)
        lines = person.to_wiki()
        content = "\n".join(lines)
        
        assert "# Alice Smith" in content
        assert "Friend" in content
        assert "- Alice" in content
        assert "Met at coffee shop" in content
        
        # 3. Simulate User Edits
        person.path.parent.mkdir(parents=True, exist_ok=True)
        
        # User changes category and adds a note
        # Ensure we don't create duplicate sections if the template output changes
        edited_content = content.replace("Friend", "Best Friend")
        
        # Replace the notes placeholder or section if it exists
        if "### Notes" in edited_content:
             parts = edited_content.split("### Notes")
             edited_content = parts[0] + "### Notes\nUpdated user notes."
        else:
             edited_content += "\n\n### Notes\nUpdated user notes."
        
        person.path.write_text(edited_content)
        
        # 4. From File (Parse)
        parsed_person = Person.from_file(person.path)
        
        assert parsed_person is not None
        assert parsed_person.name == "Alice Smith"
        assert parsed_person.category == "Best Friend" # Changed by user
        assert parsed_person.notes == "Updated user notes." # Added by user
        assert "Alice" in parsed_person.alias # Persisted

    def test_person_fallback_entries(self, tmp_path):
        """Test Person uses entries if dates are empty."""
        wiki_dir = tmp_path / "wiki"
        
        db_person = MagicMock()
        db_person.display_name = "Bob"
        db_person.relation_type = None # No category
        db_person.dates = []
        db_person.aliases = []
        
        entry1 = MagicMock()
        entry1.date = date(2024, 3, 1)
        entry1.file_path = "/journal/2024-03-01.md"
        db_person.entries = [entry1]
        
        person = Person.from_database(db_person, wiki_dir)
        
        assert len(person.appearances) == 1
        assert person.appearances[0]["date"] == date(2024, 3, 1)
        assert person.category is None # Default when no relation_type

    def test_person_from_file_missing(self, tmp_path):
        """Test from_file returns None for missing file."""
        path = tmp_path / "missing.md"
        assert Person.from_file(path) is None
