"""Tests for WikiExporter class."""
import pytest
from datetime import date, datetime
from unittest.mock import MagicMock

from dev.wiki.exporter import WikiExporter
from dev.database.manager import PalimpsestDB
from dev.database.models import Entry, Person, Tag, City, RelationType


class TestWikiExporter:
    """Tests for WikiExporter class."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database manager."""
        db = MagicMock(spec=PalimpsestDB)
        session = MagicMock()
        db.session_scope.return_value.__enter__.return_value = session
        return db

    @pytest.fixture
    def wiki_dir(self, tmp_path):
        """Create a temporary wiki directory with templates."""
        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir()

        # Create template directory
        template_dir = wiki_path / "templates" / "indexes"
        template_dir.mkdir(parents=True)

        return wiki_path

    @pytest.fixture
    def exporter(self, mock_db, wiki_dir):
        """Create a WikiExporter instance."""
        return WikiExporter(mock_db, wiki_dir)

    @pytest.fixture
    def sample_entries(self):
        """Create sample entry data."""
        entries = []
        for i, (year, month, wc) in enumerate([
            (2023, 1, 100),
            (2023, 6, 200),
            (2024, 1, 300),
        ]):
            e = MagicMock(spec=Entry)
            e.id = i + 1
            e.date = date(year, month, 1)
            e.word_count = wc
            e.people = []
            e.locations = []
            e.cities = []
            e.events = []
            e.tags = []
            entries.append(e)
        return entries

    @pytest.fixture
    def sample_people(self, sample_entries):
        """Create sample person data."""
        p1 = MagicMock(spec=Person)
        p1.name = "Alice"
        p1.display_name = "Alice"
        p1.relation_type = RelationType.FRIEND
        p1.relationship_display = "Friend"
        p1.entries = sample_entries[:2]
        p1.deleted_at = None

        p2 = MagicMock(spec=Person)
        p2.name = "Bob"
        p2.display_name = "Bob"
        p2.relation_type = None
        p2.relationship_display = "Unknown"
        p2.entries = sample_entries[2:]
        p2.deleted_at = None

        return [p1, p2]

    @pytest.fixture
    def sample_tags(self, sample_entries):
        """Create sample tag data."""
        t1 = MagicMock(spec=Tag)
        t1.id = 1
        t1.tag = "journal"
        t1.entries = sample_entries
        t1.deleted_at = None
        return [t1]


class TestExportStats(TestWikiExporter):
    """Tests for export_stats method."""

    def test_export_stats_empty(self, mock_db, wiki_dir):
        """Test export_stats returns empty stats when no entries."""
        session = mock_db.session_scope.return_value.__enter__.return_value
        session.query.return_value.order_by.return_value.all.return_value = []

        exporter = WikiExporter(mock_db, wiki_dir)
        stats = exporter.export_stats()

        assert stats.entries_created == 0
        assert stats.entries_updated == 0
        assert stats.entries_skipped == 0

    def test_export_stats_success(
        self, mock_db, wiki_dir, sample_entries, sample_people, sample_tags
    ):
        """Test successful stats export."""
        session = mock_db.session_scope.return_value.__enter__.return_value

        # Configure mocks for all queries
        entry_query = MagicMock()
        entry_query.order_by.return_value.all.return_value = sample_entries

        person_query = MagicMock()
        person_query.filter.return_value.all.return_value = sample_people

        tag_query = MagicMock()
        tag_query.filter.return_value.all.return_value = sample_tags

        count_query = MagicMock()
        count_query.count.return_value = 5
        count_query.filter.return_value.count.return_value = 3

        def query_side_effect(model):
            if model.__name__ == "Entry":
                return entry_query
            elif model.__name__ == "Person":
                return person_query
            elif model.__name__ == "Tag":
                return tag_query
            else:
                return count_query

        session.query.side_effect = query_side_effect

        exporter = WikiExporter(mock_db, wiki_dir)
        stats = exporter.export_stats(force=True)

        # Should have created/updated the file
        assert stats.entries_created + stats.entries_updated == 1

        # Check file was written
        stats_file = wiki_dir / "stats.md"
        assert stats_file.exists()

        content = stats_file.read_text()
        assert "Statistics Dashboard" in content
        assert "Total Entries" in content


class TestExportTimeline(TestWikiExporter):
    """Tests for export_timeline method."""

    def test_export_timeline_empty(self, mock_db, wiki_dir):
        """Test export_timeline returns empty stats when no entries."""
        session = mock_db.session_scope.return_value.__enter__.return_value

        query = MagicMock()
        query.options.return_value.order_by.return_value.all.return_value = []
        session.query.return_value = query

        exporter = WikiExporter(mock_db, wiki_dir)
        stats = exporter.export_timeline()

        assert stats.entries_created == 0
        assert stats.entries_updated == 0

    def test_export_timeline_success(self, mock_db, wiki_dir, sample_entries):
        """Test successful timeline export."""
        session = mock_db.session_scope.return_value.__enter__.return_value

        # Add moments to entries for the new template
        for entry in sample_entries:
            entry.moments = []

        entry_query = MagicMock()
        entry_query.options.return_value.order_by.return_value.all.return_value = sample_entries

        session.query.return_value = entry_query

        exporter = WikiExporter(mock_db, wiki_dir)
        stats = exporter.export_timeline(force=True)

        assert stats.entries_created + stats.entries_updated == 1

        timeline_file = wiki_dir / "timeline.md"
        assert timeline_file.exists()

        content = timeline_file.read_text()
        assert "Timeline" in content
        assert "2023" in content
        assert "2024" in content


class TestExportAnalysis(TestWikiExporter):
    """Tests for export_analysis method."""

    def test_export_analysis_empty(self, mock_db, wiki_dir):
        """Test export_analysis returns empty stats when no entries."""
        session = mock_db.session_scope.return_value.__enter__.return_value

        query = MagicMock()
        query.options.return_value.order_by.return_value.all.return_value = []
        session.query.return_value = query

        exporter = WikiExporter(mock_db, wiki_dir)
        stats = exporter.export_analysis()

        assert stats.entries_created == 0
        assert stats.entries_updated == 0

    def test_export_analysis_success(
        self, mock_db, wiki_dir, sample_entries, sample_people
    ):
        """Test successful analysis export."""
        session = mock_db.session_scope.return_value.__enter__.return_value

        # Add relationships to entries for analysis
        sample_entries[0].people = sample_people[:1]
        sample_entries[1].people = sample_people[:1]
        sample_entries[2].people = sample_people[1:]

        city = MagicMock(spec=City)
        city.city = "Test City"
        sample_entries[0].cities = [city]
        sample_entries[1].cities = [city]

        tag = MagicMock(spec=Tag)
        tag.tag = "test"
        sample_entries[0].tags = [tag]

        query = MagicMock()
        query.options.return_value.order_by.return_value.all.return_value = sample_entries
        session.query.return_value = query

        exporter = WikiExporter(mock_db, wiki_dir)
        stats = exporter.export_analysis(force=True)

        assert stats.entries_created + stats.entries_updated == 1

        analysis_file = wiki_dir / "analysis.md"
        assert analysis_file.exists()

        content = analysis_file.read_text()
        assert "Analysis Report" in content
        assert "Activity Patterns" in content


class TestExportHome(TestWikiExporter):
    """Tests for export_home method."""

    def test_export_home_success(
        self, mock_db, wiki_dir, sample_entries, sample_people
    ):
        """Test successful home page export."""
        session = mock_db.session_scope.return_value.__enter__.return_value

        # Add required attributes to mock people
        for person in sample_people:
            person.created_at = datetime.now()
            person.moments = []

        # Configure Entry query with options
        entry_query = MagicMock()
        entry_query.options.return_value.all.return_value = sample_entries

        person_query = MagicMock()
        person_query.filter.return_value.all.return_value = sample_people

        # For Location and Moment queries
        location_query = MagicMock()
        location_query.all.return_value = []

        moment_query = MagicMock()
        moment_query.all.return_value = []

        count_query = MagicMock()
        count_query.count.return_value = 5
        count_query.filter.return_value.count.return_value = 3
        count_query.all.return_value = []  # For countries query

        def query_side_effect(model):
            name = getattr(model, "__name__", str(model))
            if name == "Entry":
                return entry_query
            elif name == "Person":
                return person_query
            elif name == "Location":
                return location_query
            elif name == "Moment":
                return moment_query
            else:
                return count_query

        session.query.side_effect = query_side_effect

        exporter = WikiExporter(mock_db, wiki_dir)
        stats = exporter.export_home(force=True)

        assert stats.entries_created + stats.entries_updated == 1

        home_file = wiki_dir / "index.md"
        assert home_file.exists()

        content = home_file.read_text()
        assert "Palimpsest" in content
        # Updated assertion for new template
        assert "Journal" in content
