import pytest
from unittest.mock import MagicMock, patch
from datetime import date

from dev.builders.wiki_pages.analysis import export_analysis_report
from dev.database.manager import PalimpsestDB
from dev.database.models import Entry, Person, Location, City, Event, Tag

class TestAnalysisBuilder:
    
    @pytest.fixture
    def mock_db(self):
        db = MagicMock(spec=PalimpsestDB)
        session = MagicMock()
        db.session_scope.return_value.__enter__.return_value = session
        return db

    @pytest.fixture
    def mock_write(self):
        with patch("dev.builders.wiki_pages.analysis.write_if_changed") as mock:
            yield mock

    @pytest.fixture
    def sample_entries(self):
        # Create related objects
        p1 = MagicMock(spec=Person)
        p1.display_name = "Alice"
        
        p2 = MagicMock(spec=Person)
        p2.display_name = "Bob"

        l1 = MagicMock(spec=Location)
        l1.name = "Cafe"
        
        c1 = MagicMock(spec=City)
        c1.city = "Paris"
        
        e1 = MagicMock(spec=Event)
        e1.display_name = "Meeting"
        
        t1 = MagicMock(spec=Tag)
        t1.tag = "work"

        # Create entries
        entry1 = MagicMock(spec=Entry)
        entry1.date = date(2023, 1, 1) # Sunday
        entry1.word_count = 500
        entry1.people = [p1, p2]
        entry1.locations = [l1]
        entry1.cities = [c1]
        entry1.events = [e1]
        entry1.tags = [t1]

        entry2 = MagicMock(spec=Entry)
        entry2.date = date(2023, 1, 2) # Monday
        entry2.word_count = 300
        entry2.people = [p1] # Alice again
        entry2.locations = []
        entry2.cities = [c1] # Paris again
        entry2.events = []
        entry2.tags = [t1]

        return [entry1, entry2]

    def test_export_analysis_skipped_empty(self, mock_db, mock_write, tmp_path):
        """Test export skips when no entries found."""
        session = mock_db.session_scope.return_value.__enter__.return_value
        
        # Mock query execution
        mock_result = MagicMock()
        mock_result.unique.return_value.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_result
        
        status = export_analysis_report(mock_db, tmp_path, tmp_path)
        
        assert status == "skipped"
        mock_write.assert_not_called()

    def test_export_analysis_success(self, mock_db, mock_write, tmp_path, sample_entries):
        """Test successful analysis report generation."""
        session = mock_db.session_scope.return_value.__enter__.return_value
        
        mock_result = MagicMock()
        mock_result.unique.return_value.scalars.return_value.all.return_value = sample_entries
        session.execute.return_value = mock_result
        
        mock_write.return_value = "created"
        
        status = export_analysis_report(mock_db, tmp_path, tmp_path, force=True)
        
        assert status == "created"
        
        # Verify content
        args, _ = mock_write.call_args
        path, content, force = args
        
        assert path == tmp_path / "analysis.md"
        assert force is True
        
        # Overview
        assert "| **Total Entries** | 2 |" in content
        assert "| **Unique People** | 2 |" in content # Alice, Bob
        assert "| **Unique Cities** | 1 |" in content # Paris
        assert "| **Total Words** | 800 |" in content
        
        # Top Entities
        # Alice appeared twice, Bob once
        assert "2× [[people/alice.md|Alice]]" in content
        # Paris appeared twice
        assert "2× [[cities/paris.md|Paris]]" in content
        # Tag 'work' appeared twice
        assert "2× [[tags/work.md|#work]]" in content
        
        # Temporal
        # 2023 has 2 entries
        assert "2023: ██████████████████████████████████████████████████ 2 entries" in content
        
        # Day of week: Jan 1 2023 is Sunday, Jan 2 is Monday
        # max_dow_count is 1, so bar length is 40
        assert "Sunday   : ████████████████████████████████████████ 1" in content
        assert "Monday   : ████████████████████████████████████████ 1" in content
        
        # Co-location: Alice in Paris (2x)
        assert "- **[[people/alice.md|Alice]]**: Paris (2×)" in content

    def test_export_analysis_no_word_count(self, mock_db, mock_write, tmp_path):
        """Test robust against None word_count."""
        session = mock_db.session_scope.return_value.__enter__.return_value
        
        entry = MagicMock(spec=Entry)
        entry.date = date(2023, 1, 1)
        entry.word_count = None # Issue potential
        entry.people = []
        entry.locations = []
        entry.cities = []
        entry.events = []
        entry.tags = []
        
        mock_result = MagicMock()
        mock_result.unique.return_value.scalars.return_value.all.return_value = [entry]
        session.execute.return_value = mock_result
        
        export_analysis_report(mock_db, tmp_path, tmp_path)
        
        # Should not crash
        _, content, _ = mock_write.call_args[0]
        assert "| **Total Words** | 0 |" in content
