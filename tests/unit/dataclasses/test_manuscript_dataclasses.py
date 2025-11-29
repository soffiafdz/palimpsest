import pytest
from unittest.mock import MagicMock
from datetime import date

from dev.dataclasses.manuscript_arc import Arc
from dev.dataclasses.manuscript_theme import Theme

class TestManuscriptDataclasses:
    """Test Manuscript-related dataclasses (Arc, Theme)."""

    @pytest.fixture
    def mock_db_arc(self):
        """Create a mock database Arc object."""
        db_arc = MagicMock()
        db_arc.arc = "Test Arc"
        
        # Mock events
        event1 = MagicMock()
        event1.event.event = "Event One"
        event1.event.start_date = date(2024, 1, 1)
        event1.event.end_date = date(2024, 1, 2)
        
        event2 = MagicMock()
        event2.event.event = "Event Two"
        event2.event.start_date = date(2024, 2, 1)
        event2.event.end_date = None
        
        db_arc.events = [event1, event2]
        return db_arc

    @pytest.fixture
    def mock_db_theme(self):
        """Create a mock database Theme object."""
        db_theme = MagicMock()
        db_theme.theme = "Redemption"
        
        # Mock entries
        entry1 = MagicMock()
        entry1.entry.date = date(2024, 1, 15)
        entry1.entry.word_count = 1000
        
        entry2 = MagicMock()
        entry2.entry.date = date(2024, 2, 20)
        entry2.entry.word_count = 2000
        
        db_theme.entries = [entry1, entry2]
        return db_theme

    def test_arc_roundtrip(self, tmp_path, mock_db_arc):
        """Test Arc creation from DB, export to Wiki, and parsing from file."""
        wiki_dir = tmp_path / "wiki"
        journal_dir = tmp_path / "journal"
        
        # 1. From Database
        arc = Arc.from_database(mock_db_arc, wiki_dir, journal_dir)
        
        assert arc.name == "Test Arc"
        assert arc.date_range_start == date(2024, 1, 1)
        assert len(arc.events) == 2
        assert arc.path == wiki_dir / "manuscript" / "arcs" / "test_arc.md"

        # 2. To Wiki (Render)
        lines = arc.to_wiki()
        content = "\n".join(lines)
        
        assert "# Palimpsest — Story Arc" in content
        assert "## Test Arc" in content
        assert "Event One" in content
        
        # 3. Simulate User Edits
        # Create directory structure
        arc.path.parent.mkdir(parents=True, exist_ok=True)
        
        edited_content = content + "\n\n### Arc Notes\nThis is a test note."
        arc.path.write_text(edited_content)
        
        # 4. From File (Parse)
        parsed_arc = Arc.from_file(arc.path)
        
        assert parsed_arc is not None
        assert parsed_arc.name == "Test Arc"
        assert parsed_arc.notes == "This is a test note."

    def test_theme_roundtrip(self, tmp_path, mock_db_theme):
        """Test Theme creation from DB, export to Wiki, and parsing from file."""
        wiki_dir = tmp_path / "wiki"
        journal_dir = tmp_path / "journal"
        
        # 1. From Database
        theme = Theme.from_database(mock_db_theme, wiki_dir, journal_dir)
        
        assert theme.name == "Redemption"
        assert theme.usage_count == 2
        assert theme.total_word_count == 3000
        assert theme.first_used == "2024-01-15"
        assert theme.path == wiki_dir / "manuscript" / "themes" / "redemption.md"

        # 2. To Wiki (Render)
        lines = theme.to_wiki()
        content = "\n".join(lines)
        
        assert "# Palimpsest — Manuscript Theme" in content
        assert "## Redemption" in content
        assert "3,000" in content # Formatting check
        
        # 3. Simulate User Edits
        theme.path.parent.mkdir(parents=True, exist_ok=True)
        
        # Since initial theme has no description, to_wiki won't generate the header.
        # We need to add it.
        if "### Description" in content:
            edited_content = content.replace(
                "### Description\n", 
                "### Description\nA theme about second chances.\n"
            )
        else:
            edited_content = content + "\n\n### Description\nA theme about second chances."

        theme.path.write_text(edited_content)
        
        # 4. From File (Parse)
        parsed_theme = Theme.from_file(theme.path)
        
        assert parsed_theme is not None
        assert parsed_theme.name == "Redemption"
        assert parsed_theme.description == "A theme about second chances."

    def test_arc_from_file_missing(self, tmp_path):
        """Test from_file returns None for missing file."""
        path = tmp_path / "missing.md"
        assert Arc.from_file(path) is None

    def test_theme_from_file_missing(self, tmp_path):
        """Test from_file returns None for missing file."""
        path = tmp_path / "missing.md"
        assert Theme.from_file(path) is None
