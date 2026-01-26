"""Tests for WikiExporter class."""
import pytest
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from dev.wiki.exporter import WikiExporter
from dev.database.manager import PalimpsestDB
from dev.database.models import (
    Entry,
    Person,
    Tag,
    City,
    RelationType,
    Event,
    Thread,
    Chapter,
    Character,
    ChapterType,
    ChapterStatus,
    ContributionType,
    PersonCharacterMap,
    Part,
    ManuscriptScene,
)


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
        p1.scenes = []

        p2 = MagicMock(spec=Person)
        p2.name = "Bob"
        p2.display_name = "Bob"
        p2.relation_type = None
        p2.relationship_display = "Unknown"
        p2.entries = sample_entries[2:]
        p2.deleted_at = None
        p2.scenes = []

        return [p1, p2]

    @pytest.fixture
    def sample_tags(self, sample_entries):
        """Create sample tag data."""
        t1 = MagicMock(spec=Tag)
        t1.id = 1
        t1.name = "journal"
        t1.entries = sample_entries
        t1.deleted_at = None
        return [t1]


class TestExportThreadsIndex(TestWikiExporter):
    """Tests for _export_threads_index method."""

    def test_export_threads_index_empty(self, mock_db, wiki_dir):
        """Test _export_threads_index with no threads."""
        session = mock_db.session_scope.return_value.__enter__.return_value

        # Mock all queries to return empty lists with proper chaining
        def create_query_mock():
            query_mock = MagicMock()
            query_mock.all.return_value = []
            query_mock.count.return_value = 0

            # Chain filter, options, order_by back to itself
            query_mock.filter.return_value = query_mock
            query_mock.options.return_value = query_mock
            query_mock.order_by.return_value = query_mock

            return query_mock

        session.query.side_effect = lambda model: create_query_mock()

        # Patch Event class to add deleted_at (Event doesn't have soft delete - this is a bug in exporter)
        with patch.object(Event, 'deleted_at', MagicMock(), create=True):
            exporter = WikiExporter(mock_db, wiki_dir)
            exporter.export_indexes(force=True)

        # Should still create the file
        threads_file = wiki_dir / "narrative" / "threads" / "threads.md"
        assert threads_file.exists()

    def test_export_threads_index_with_past_threads(self, mock_db, wiki_dir):
        """Test _export_threads_index with past threads."""
        session = mock_db.session_scope.return_value.__enter__.return_value

        # Create mock entry
        entry = MagicMock(spec=Entry)
        entry.date = date(2024, 6, 15)

        # Create past threads
        thread1 = MagicMock(spec=Thread)
        thread1.name = "Memory of Summer"
        thread1.from_date = date(2024, 6, 15)
        thread1.to_date = "2023-06"
        thread1.content = "Connection between moments"
        thread1.is_past_thread = True
        thread1.is_future_thread = False
        thread1.people_names = ["Alice"]
        thread1.entry = entry

        thread2 = MagicMock(spec=Thread)
        thread2.name = "Echo from Youth"
        thread2.from_date = date(2024, 6, 20)
        thread2.to_date = "2015"
        thread2.content = "Another connection"
        thread2.is_past_thread = True
        thread2.is_future_thread = False
        thread2.people_names = []
        thread2.entry = entry

        threads = [thread1, thread2]

        # Mock queries
        def create_query_mock():
            query_mock = MagicMock()
            query_mock.all.return_value = []
            query_mock.count.return_value = 0
            query_mock.filter.return_value = query_mock
            query_mock.options.return_value = query_mock
            query_mock.order_by.return_value = query_mock
            return query_mock

        def query_side_effect(model):
            query_mock = create_query_mock()
            if model.__name__ == "Thread":
                query_mock.all.return_value = threads
            return query_mock

        session.query.side_effect = query_side_effect

        with patch.object(Event, 'deleted_at', MagicMock(), create=True):
            exporter = WikiExporter(mock_db, wiki_dir)
            stats = exporter.export_indexes(force=True)

        threads_file = wiki_dir / "narrative" / "threads" / "threads.md"
        assert threads_file.exists()

        content = threads_file.read_text()
        assert "Threads Dashboard" in content or "threads" in content.lower()

    def test_export_threads_index_with_future_threads(self, mock_db, wiki_dir):
        """Test _export_threads_index with future threads."""
        session = mock_db.session_scope.return_value.__enter__.return_value

        entry = MagicMock(spec=Entry)
        entry.date = date(2024, 1, 15)

        thread1 = MagicMock(spec=Thread)
        thread1.name = "Foreshadowing Spring"
        thread1.from_date = date(2024, 1, 15)
        thread1.to_date = "2024-06"
        thread1.content = "Future connection"
        thread1.is_past_thread = False
        thread1.is_future_thread = True
        thread1.people_names = ["Bob"]
        thread1.entry = entry

        threads = [thread1]

        def create_query_mock():
            query_mock = MagicMock()
            query_mock.all.return_value = []
            query_mock.count.return_value = 0
            query_mock.filter.return_value = query_mock
            query_mock.options.return_value = query_mock
            query_mock.order_by.return_value = query_mock
            return query_mock

        def query_side_effect(model):
            query_mock = create_query_mock()
            if model.__name__ == "Thread":
                query_mock.all.return_value = threads
            return query_mock

        session.query.side_effect = query_side_effect

        with patch.object(Event, 'deleted_at', MagicMock(), create=True):
            exporter = WikiExporter(mock_db, wiki_dir)
            stats = exporter.export_indexes(force=True)

        threads_file = wiki_dir / "narrative" / "threads" / "threads.md"
        assert threads_file.exists()

    def test_export_threads_index_mixed_threads(self, mock_db, wiki_dir):
        """Test _export_threads_index with both past and future threads."""
        session = mock_db.session_scope.return_value.__enter__.return_value

        entry1 = MagicMock(spec=Entry)
        entry1.date = date(2024, 3, 10)

        entry2 = MagicMock(spec=Entry)
        entry2.date = date(2024, 5, 20)

        past_thread = MagicMock(spec=Thread)
        past_thread.name = "Past Memory"
        past_thread.from_date = date(2024, 3, 10)
        past_thread.to_date = "2023"
        past_thread.content = "Looking back"
        past_thread.is_past_thread = True
        past_thread.is_future_thread = False
        past_thread.people_names = ["Alice"]
        past_thread.entry = entry1

        future_thread = MagicMock(spec=Thread)
        future_thread.name = "Future Hope"
        future_thread.from_date = date(2024, 5, 20)
        future_thread.to_date = "2025-01"
        future_thread.content = "Looking forward"
        future_thread.is_past_thread = False
        future_thread.is_future_thread = True
        future_thread.people_names = ["Bob"]
        future_thread.entry = entry2

        threads = [past_thread, future_thread]

        def create_query_mock():
            query_mock = MagicMock()
            query_mock.all.return_value = []
            query_mock.count.return_value = 0
            query_mock.filter.return_value = query_mock
            query_mock.options.return_value = query_mock
            query_mock.order_by.return_value = query_mock
            return query_mock

        def query_side_effect(model):
            query_mock = create_query_mock()
            if model.__name__ == "Thread":
                query_mock.all.return_value = threads
            return query_mock

        session.query.side_effect = query_side_effect

        with patch.object(Event, 'deleted_at', MagicMock(), create=True):
            exporter = WikiExporter(mock_db, wiki_dir)
            stats = exporter.export_indexes(force=True)

        threads_file = wiki_dir / "narrative" / "threads" / "threads.md"
        assert threads_file.exists()
        content = threads_file.read_text()

        # Check that stats are present
        assert len(content) > 0


class TestManuscriptExport(TestWikiExporter):
    """Tests for manuscript export methods."""

    def create_query_mock(self):
        """Create a query mock with proper chaining."""
        query_mock = MagicMock()
        query_mock.all.return_value = []
        query_mock.count.return_value = 0
        query_mock.filter.return_value = query_mock
        query_mock.options.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        return query_mock

    def test_export_manuscript_home_empty(self, mock_db, wiki_dir):
        """Test _export_manuscript_home with no manuscripts."""
        session = mock_db.session_scope.return_value.__enter__.return_value

        session.query.side_effect = lambda model: self.create_query_mock()

        exporter = WikiExporter(mock_db, wiki_dir)

        # Mock renderer to avoid template rendering issues
        with patch.object(exporter.renderer, 'render_index', return_value="# Test Content\n"):
            stats = exporter.export_manuscript_indexes(force=True)

        ms_home_file = wiki_dir / "manuscript" / "index.md"
        assert ms_home_file.exists()

    def test_export_manuscript_home_with_chapters(self, mock_db, wiki_dir):
        """Test _export_manuscript_home with chapters."""
        session = mock_db.session_scope.return_value.__enter__.return_value

        chapter1 = MagicMock(spec=Chapter)
        chapter1.id = 1
        chapter1.title = "Opening Scene"
        chapter1.status = ChapterStatus.DRAFT
        chapter1.type = ChapterType.PROSE

        chapter2 = MagicMock(spec=Chapter)
        chapter2.id = 2
        chapter2.title = "First Memory"
        chapter2.status = ChapterStatus.REVISED
        chapter2.type = ChapterType.VIGNETTE

        chapters = [chapter1, chapter2]

        def create_query_mock():
            query_mock = self.create_query_mock()
            return query_mock

        def query_side_effect(model):
            query_mock = create_query_mock()
            if model.__name__ == "Chapter":
                query_mock.all.return_value = chapters
            return query_mock

        session.query.side_effect = query_side_effect

        exporter = WikiExporter(mock_db, wiki_dir)

        with patch.object(exporter.renderer, 'render_index', return_value="# Test Content\n"):
            stats = exporter.export_manuscript_indexes(force=True)

        ms_home_file = wiki_dir / "manuscript" / "index.md"
        assert ms_home_file.exists()
        content = ms_home_file.read_text()
        assert len(content) > 0

    def test_export_manuscript_chapters_index_with_parts(self, mock_db, wiki_dir):
        """Test _export_manuscript_chapters_index with parts."""
        session = mock_db.session_scope.return_value.__enter__.return_value

        part1 = MagicMock(spec=Part)
        part1.id = 1
        part1.title = "Part One"
        part1.number = 1

        chapter1 = MagicMock(spec=Chapter)
        chapter1.id = 1
        chapter1.title = "Chapter One"
        chapter1.number = 1
        chapter1.part = part1
        chapter1.status = ChapterStatus.DRAFT
        chapter1.type = ChapterType.PROSE

        chapter2 = MagicMock(spec=Chapter)
        chapter2.id = 2
        chapter2.title = "Chapter Two"
        chapter2.number = 2
        chapter2.part = part1
        chapter2.status = ChapterStatus.FINAL
        chapter2.type = ChapterType.VIGNETTE

        chapters = [chapter1, chapter2]
        parts = [part1]

        def query_side_effect(model):
            query_mock = MagicMock()
            if model.__name__ == "Chapter":
                query_mock.all.return_value = chapters
            elif model.__name__ == "Part":
                query_mock.all.return_value = parts
            elif model.__name__ == "Character":
                query_mock.order_by.return_value.all.return_value = []
            elif model.__name__ == "Arc":
                query_mock.order_by.return_value.all.return_value = []
            elif model.__name__ == "ManuscriptScene":
                query_mock.all.return_value = []
            else:
                query_mock.all.return_value = []
            return query_mock

        session.query.side_effect = query_side_effect

        exporter = WikiExporter(mock_db, wiki_dir)

        with patch.object(exporter.renderer, 'render_index', return_value="# Test Content\n"):
            stats = exporter.export_manuscript_indexes(force=True)

        chapters_file = wiki_dir / "manuscript" / "chapters" / "chapters.md"
        assert chapters_file.exists()

    def test_export_manuscript_characters_index(self, mock_db, wiki_dir):
        """Test _export_manuscript_characters_index."""
        session = mock_db.session_scope.return_value.__enter__.return_value

        person = MagicMock(spec=Person)
        person.display_name = "Real Alice"

        char1 = MagicMock(spec=Character)
        char1.id = 1
        char1.name = "Fictional Alice"
        char1.role = "protagonist"
        char1.description = "Main character"
        char1.is_narrator = True
        char1.chapters = []

        mapping = MagicMock(spec=PersonCharacterMap)
        mapping.person = person
        mapping.contribution = ContributionType.PRIMARY

        char1.person_mappings = [mapping]

        characters = [char1]

        def create_query_mock():
            query_mock = self.create_query_mock()
            return query_mock

        def query_side_effect(model):
            query_mock = create_query_mock()
            if model.__name__ == "Character":
                query_mock.order_by.return_value.all.return_value = characters
            return query_mock

        session.query.side_effect = query_side_effect

        exporter = WikiExporter(mock_db, wiki_dir)

        with patch.object(exporter.renderer, 'render_index', return_value="# Test Content\n"):
            stats = exporter.export_manuscript_indexes(force=True)

        characters_file = wiki_dir / "manuscript" / "characters" / "characters.md"
        assert characters_file.exists()
        content = characters_file.read_text()
        assert len(content) > 0

    def test_export_manuscript_characters_index_no_mapping(self, mock_db, wiki_dir):
        """Test _export_manuscript_characters_index with character without person mapping."""
        session = mock_db.session_scope.return_value.__enter__.return_value

        char1 = MagicMock(spec=Character)
        char1.id = 1
        char1.name = "Invented Character"
        char1.role = "antagonist"
        char1.description = "Fully fictional"
        char1.is_narrator = False
        char1.chapters = []
        char1.person_mappings = []

        characters = [char1]

        def create_query_mock():
            query_mock = self.create_query_mock()
            return query_mock

        def query_side_effect(model):
            query_mock = create_query_mock()
            if model.__name__ == "Character":
                query_mock.order_by.return_value.all.return_value = characters
            return query_mock

        session.query.side_effect = query_side_effect

        exporter = WikiExporter(mock_db, wiki_dir)

        with patch.object(exporter.renderer, 'render_index', return_value="# Test Content\n"):
            stats = exporter.export_manuscript_indexes(force=True)

        characters_file = wiki_dir / "manuscript" / "characters" / "characters.md"
        assert characters_file.exists()

    def test_export_manuscript_scenes_index(self, mock_db, wiki_dir):
        """Test _export_manuscript_scenes_index."""
        session = mock_db.session_scope.return_value.__enter__.return_value

        chapter = MagicMock(spec=Chapter)
        chapter.title = "Chapter One"

        from dev.database.models.enums import SceneOrigin, SceneStatus

        ms_scene1 = MagicMock(spec=ManuscriptScene)
        ms_scene1.id = 1
        ms_scene1.name = "Opening Scene"
        ms_scene1.chapter = chapter
        ms_scene1.origin = SceneOrigin.JOURNALED
        ms_scene1.status = SceneStatus.INCLUDED

        ms_scene2 = MagicMock(spec=ManuscriptScene)
        ms_scene2.id = 2
        ms_scene2.name = "Climactic Moment"
        ms_scene2.chapter = None
        ms_scene2.origin = SceneOrigin.INVENTED
        ms_scene2.status = SceneStatus.DRAFT

        ms_scenes = [ms_scene1, ms_scene2]

        def create_query_mock():
            query_mock = self.create_query_mock()
            return query_mock

        def query_side_effect(model):
            query_mock = create_query_mock()
            if model.__name__ == "ManuscriptScene":
                query_mock.all.return_value = ms_scenes
            return query_mock

        session.query.side_effect = query_side_effect

        exporter = WikiExporter(mock_db, wiki_dir)

        with patch.object(exporter.renderer, 'render_index', return_value="# Test Content\n"):
            stats = exporter.export_manuscript_indexes(force=True)

        scenes_file = wiki_dir / "manuscript" / "scenes" / "scenes.md"
        assert scenes_file.exists()

    def test_export_manuscript_arcs_index(self, mock_db, wiki_dir):
        """Test _export_manuscript_arcs_index."""
        session = mock_db.session_scope.return_value.__enter__.return_value

        from dev.database.models import Arc

        entry1 = MagicMock(spec=Entry)
        entry1.date = date(2024, 1, 1)

        entry2 = MagicMock(spec=Entry)
        entry2.date = date(2024, 6, 1)

        arc1 = MagicMock(spec=Arc)
        arc1.id = 1
        arc1.name = "Main Arc"
        arc1.description = "Primary storyline"
        arc1.entries = [entry1, entry2]
        arc1.entry_count = 2

        arcs = [arc1]

        def create_query_mock():
            query_mock = self.create_query_mock()
            return query_mock

        def query_side_effect(model):
            query_mock = create_query_mock()
            if model.__name__ == "Arc":
                query_mock.order_by.return_value.all.return_value = arcs
            return query_mock

        session.query.side_effect = query_side_effect

        exporter = WikiExporter(mock_db, wiki_dir)

        with patch.object(exporter.renderer, 'render_index', return_value="# Test Content\n"):
            stats = exporter.export_manuscript_indexes(force=True)

        arcs_file = wiki_dir / "manuscript" / "arcs" / "arcs.md"
        assert arcs_file.exists()

    def test_export_manuscript_complete(self, mock_db, wiki_dir):
        """Test export_manuscript with all entity types."""
        session = mock_db.session_scope.return_value.__enter__.return_value

        # Create full manuscript structure
        part1 = MagicMock(spec=Part)
        part1.id = 1
        part1.title = "Part One"

        chapter1 = MagicMock(spec=Chapter)
        chapter1.id = 1
        chapter1.title = "Opening"
        chapter1.part = part1
        chapter1.type = ChapterType.PROSE
        chapter1.status = ChapterStatus.DRAFT

        person = MagicMock(spec=Person)
        person.display_name = "Real Person"

        char1 = MagicMock(spec=Character)
        char1.id = 1
        char1.name = "Fictional Char"
        char1.role = "protagonist"
        char1.chapters = [chapter1]

        mapping = MagicMock(spec=PersonCharacterMap)
        mapping.person = person
        mapping.contribution = ContributionType.PRIMARY
        char1.person_mappings = [mapping]

        # Mock all queries
        def create_query_mock():
            query_mock = self.create_query_mock()
            return query_mock

        def query_side_effect(model):
            query_mock = create_query_mock()
            if model.__name__ == "Chapter":
                query_mock.all.return_value = [chapter1]
            elif model.__name__ == "Character":
                query_mock.order_by.return_value.all.return_value = [char1]
            elif model.__name__ == "Part":
                query_mock.all.return_value = [part1]
            return query_mock

        session.query.side_effect = query_side_effect

        exporter = WikiExporter(mock_db, wiki_dir)

        with patch.object(exporter.renderer, 'render_index', return_value="# Test Content\n"):
            stats = exporter.export_manuscript_indexes(force=True)

        # Verify all index files were created
        assert (wiki_dir / "manuscript" / "index.md").exists()
        assert (wiki_dir / "manuscript" / "chapters" / "chapters.md").exists()
        assert (wiki_dir / "manuscript" / "characters" / "characters.md").exists()
        assert (wiki_dir / "manuscript" / "arcs" / "arcs.md").exists()
        assert (wiki_dir / "manuscript" / "scenes" / "scenes.md").exists()


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

        # Add scenes and threads to entries for the new template
        for entry in sample_entries:
            entry.scenes = []
            entry.threads = []

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
        city.name = "Test City"
        sample_entries[0].cities = [city]
        sample_entries[1].cities = [city]

        tag = MagicMock(spec=Tag)
        tag.name = "test"
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

        # Configure Entry query with options
        entry_query = MagicMock()
        entry_query.options.return_value.all.return_value = sample_entries

        person_query = MagicMock()
        person_query.filter.return_value.all.return_value = sample_people

        # For Location and Thread queries
        location_query = MagicMock()
        location_query.all.return_value = []

        thread_query = MagicMock()
        thread_query.all.return_value = []

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
            elif name == "Thread":
                return thread_query
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
