import pytest
from unittest.mock import MagicMock, patch
from datetime import date

from dev.builders.wiki_pages.index import export_index
from dev.database.manager import PalimpsestDB
from dev.database.models import Entry, Person, RelationType

class TestIndexBuilder:
    
    @pytest.fixture
    def mock_db(self):
        db = MagicMock(spec=PalimpsestDB)
        session = MagicMock()
        db.session_scope.return_value.__enter__.return_value = session
        return db

    @pytest.fixture
    def mock_write(self):
        with patch("dev.builders.wiki_pages.index.write_if_changed") as mock:
            yield mock

    @pytest.fixture
    def sample_data(self):
        e1 = MagicMock(spec=Entry)
        e1.date = date(2024, 1, 1)
        e1.word_count = 500
        
        p1 = MagicMock(spec=Person)
        p1.display_name = "Alice"
        p1.name = "Alice"
        p1.relation_type = RelationType.FRIEND
        p1.relationship_display = "Friend"
        p1.entries = [e1]

        return {
            "entries": [e1],
            "people": [p1],
            "counts": {
                "tags": 5,
                "poems": 2,
                "refs": 3,
                "locs": 10,
                "cities": 4,
                "events": 1,
                "themes": 6
            }
        }

    def test_export_index_success(self, mock_db, mock_write, tmp_path, sample_data):
        """Test successful index page generation."""
        session = mock_db.session_scope.return_value.__enter__.return_value
        
        # Configure mocks
        mock_entries_result = MagicMock()
        mock_entries_result.scalars.return_value.all.return_value = sample_data["entries"]
        
        mock_people_result = MagicMock()
        mock_people_result.scalars.return_value.all.return_value = sample_data["people"]
        
        # Counts
        counts = sample_data["counts"]
        mock_tags = MagicMock()
        mock_tags.scalar.return_value = counts["tags"]
        mock_poems = MagicMock()
        mock_poems.scalar.return_value = counts["poems"]
        mock_refs = MagicMock()
        mock_refs.scalar.return_value = counts["refs"]
        mock_locs = MagicMock()
        mock_locs.scalar.return_value = counts["locs"]
        mock_cities = MagicMock()
        mock_cities.scalar.return_value = counts["cities"]
        mock_events = MagicMock()
        mock_events.scalar.return_value = counts["events"]
        mock_themes = MagicMock()
        mock_themes.scalar.return_value = counts["themes"]

        session.execute.side_effect = [
            mock_entries_result,
            mock_people_result,
            mock_tags,
            mock_poems,
            mock_refs,
            mock_locs,
            mock_cities,
            mock_events,
            mock_themes
        ]
        
        mock_write.return_value = "created"
        
        status = export_index(mock_db, tmp_path, tmp_path, force=True)
        
        assert status == "created"
        
        args, _ = mock_write.call_args
        path, content, force = args
        
        assert path == tmp_path / "index.md"
        
        # Navigation
        assert "[[entries.md|Journal Entries]]" in content
        assert "[[people.md|People]]" in content
        assert "1 person" in content
        assert "1 category" in content # Friend
        
        assert "[[locations.md|Locations]]" in content
        assert "10 locations" in content
        
        assert "[[cities.md|Cities]]" in content
        assert "4 cities" in content
        
        assert "[[events.md|Events]]" in content
        assert "1 event" in content
        
        assert "[[themes.md|Themes]]" in content
        assert "6 themes" in content
        
        assert "[[tags.md|Tags]]" in content
        assert "5 tags" in content
        
        assert "[[poems.md|Poems]]" in content
        assert "2 poems" in content
        
        assert "[[references.md|References]]" in content
        assert "3 references" in content
        
        # Statistics
        assert "**Total Entries:** 1" in content
        assert "**Total Words:** 500" in content
        
        # Recent Activity
        assert "[[entries/2024/2024-01-01.md|2024-01-01]] — 500 words" in content
        
        # Most mentioned people
        assert "[[people/alice.md|Alice]] — 1 mention (friend)" in content

    def test_export_index_empty(self, mock_db, mock_write, tmp_path):
        """Test index generation with empty database."""
        session = mock_db.session_scope.return_value.__enter__.return_value
        
        # Return empty lists and 0 counts
        mock_empty_list = MagicMock()
        mock_empty_list.scalars.return_value.all.return_value = []
        
        mock_zero = MagicMock()
        mock_zero.scalar.return_value = 0
        
        session.execute.side_effect = [
            mock_empty_list, # entries
            mock_empty_list, # people
            mock_zero, # tags
            mock_zero, # poems
            mock_zero, # refs
            mock_zero, # locs
            mock_zero, # cities
            mock_zero, # events
            mock_zero, # themes
        ]
        
        export_index(mock_db, tmp_path, tmp_path)
        
        _, content, _ = mock_write.call_args[0]
        
        assert "(empty)" in content
        assert "**Total Entries:** 0" in content
