import pytest
from unittest.mock import MagicMock, patch, ANY
from pathlib import Path
from datetime import date, timedelta

from dev.builders.wiki_pages.stats import export_stats
from dev.database.manager import PalimpsestDB
from dev.database.models import Entry, Person, Tag, Location, City, Event, RelationType

class TestStatsBuilder:
    
    @pytest.fixture
    def mock_db(self):
        db = MagicMock(spec=PalimpsestDB)
        session = MagicMock()
        db.session_scope.return_value.__enter__.return_value = session
        return db

    @pytest.fixture
    def mock_write(self):
        with patch("dev.builders.wiki_pages.stats.write_if_changed") as mock:
            yield mock

    @pytest.fixture
    def sample_data(self):
        # Entries
        e1 = MagicMock(spec=Entry)
        e1.date = date(2023, 1, 1)
        e1.word_count = 100
        
        e2 = MagicMock(spec=Entry)
        e2.date = date(2023, 6, 1)
        e2.word_count = 200
        
        e3 = MagicMock(spec=Entry)
        e3.date = date(2024, 1, 1)
        e3.word_count = 300

        # People
        p1 = MagicMock(spec=Person)
        p1.name = "Alice"
        p1.display_name = "Alice"
        p1.relation_type = RelationType.FRIEND
        p1.relationship_display = "Friend"
        p1.entries = [e1, e2] # 2 entries

        p2 = MagicMock(spec=Person)
        p2.name = "Bob"
        p2.display_name = "Bob"
        p2.relation_type = None
        p2.relationship_display = "Unknown"
        p2.entries = [e3] # 1 entry

        # Tags
        t1 = MagicMock(spec=Tag)
        t1.tag = "journal"
        t1.entries = [e1, e2, e3]

        return {
            "entries": [e1, e2, e3],
            "people": [p1, p2],
            "tags": [t1],
            "locations_count": 10,
            "cities_count": 5,
            "events_count": 2,
            "themes_count": 3
        }

    def test_export_stats_skipped_empty(self, mock_db, mock_write, tmp_path):
        """Test export skips when no entries found."""
        session = mock_db.session_scope.return_value.__enter__.return_value
        
        # Mock first query (entries) to return empty list
        # session.execute().scalars().all() -> []
        session.execute.return_value.scalars.return_value.all.return_value = []
        
        status = export_stats(mock_db, tmp_path, tmp_path)
        
        assert status == "skipped"
        mock_write.assert_not_called()

    def test_export_stats_success(self, mock_db, mock_write, tmp_path, sample_data):
        """Test successful stats export with data."""
        session = mock_db.session_scope.return_value.__enter__.return_value
        
        # Configure side effects for session.execute()
        # We need to handle different queries.
        # Sequence: Entries, People, Tags, LocCount, CityCount, EventCount, ThemeCount
        
        mock_entries_result = MagicMock()
        mock_entries_result.scalars.return_value.all.return_value = sample_data["entries"]
        
        mock_people_result = MagicMock()
        mock_people_result.scalars.return_value.all.return_value = sample_data["people"]
        
        mock_tags_result = MagicMock()
        mock_tags_result.scalars.return_value.all.return_value = sample_data["tags"]
        
        # For scalar counts
        mock_scalar_loc = MagicMock()
        mock_scalar_loc.scalar.return_value = sample_data["locations_count"]
        
        mock_scalar_city = MagicMock()
        mock_scalar_city.scalar.return_value = sample_data["cities_count"]
        
        mock_scalar_event = MagicMock()
        mock_scalar_event.scalar.return_value = sample_data["events_count"]
        
        mock_scalar_theme = MagicMock()
        mock_scalar_theme.scalar.return_value = sample_data["themes_count"]

        session.execute.side_effect = [
            mock_entries_result, # Entries
            mock_people_result,  # People
            mock_tags_result,    # Tags
            mock_scalar_loc,     # Locations count
            mock_scalar_city,    # Cities count
            mock_scalar_event,   # Events count
            mock_scalar_theme,   # Themes count
        ]
        
        mock_write.return_value = "created"
        
        status = export_stats(mock_db, tmp_path, tmp_path, force=True)
        
        assert status == "created"
        
        # Verify content
        args, _ = mock_write.call_args
        path, content, force = args
        
        assert path == tmp_path / "stats.md"
        assert force is True
        
        # Check specific content
        assert "**Total Entries:** 3" in content
        assert "**Total Words:** 600" in content
        assert "**Total People:** 2" in content
        assert "**Total Locations:** 10" in content
        assert "**Total Cities:** 5" in content
        assert "**Alice** — 2 mentions" in content
        assert "**Bob** — 1 mentions" in content
        assert "**journal** — 3 entries" in content
        assert "2023: ██████████████████████████████ (2 entries)" in content
        assert "2024: ███████████████ (1 entries)" in content

    def test_export_stats_word_count_distribution(self, mock_db, mock_write, tmp_path, sample_data):
        """Test word count distribution logic."""
        session = mock_db.session_scope.return_value.__enter__.return_value
        
        # Reuse generic setup but focus on output
        mock_entries_result = MagicMock()
        mock_entries_result.scalars.return_value.all.return_value = sample_data["entries"]
        
        # We need to mock all subsequent calls to avoid StopIteration
        # Using default mocks for others
        mock_default_list = MagicMock()
        mock_default_list.scalars.return_value.all.return_value = []
        mock_default_scalar = MagicMock()
        mock_default_scalar.scalar.return_value = 0
        
        session.execute.side_effect = [
            mock_entries_result,
            mock_default_list, # People
            mock_default_list, # Tags
            mock_default_scalar, # Locs
            mock_default_scalar, # Cities
            mock_default_scalar, # Events
            mock_default_scalar, # Themes
        ]
        
        export_stats(mock_db, tmp_path, tmp_path)
        
        _, content, _ = mock_write.call_args[0]
        
        # e1=100 -> 0-100
        # e2=200 -> 101-250
        # e3=300 -> 251-500
        assert "0-100        █" in content
        assert "101-250      █" in content
        assert "251-500      █" in content
