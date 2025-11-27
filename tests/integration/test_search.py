#!/usr/bin/env python3
"""
Integration tests for full-text search functionality.

Tests:
- FTS5 index creation and management
- Search query parsing
- Text search with filters
- Metadata filtering
- Sorting and pagination
"""
import pytest
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dev.database.models import Base, Entry, Person, Tag, Event, City, RelationType
from dev.database.models_manuscript import ManuscriptEntry, ManuscriptStatus
from dev.search.search_engine import SearchQuery, SearchQueryParser, SearchEngine
from dev.search.search_index import SearchIndexManager


@pytest.fixture
def test_db():
    """Create in-memory database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session, engine
    session.close()


class TestSearchIndex:
    """Test FTS5 search index creation and management."""

    def test_create_index(self, test_db):
        """Test creating FTS5 index."""
        session, engine = test_db

        mgr = SearchIndexManager(engine)
        mgr.create_index()

        # Verify table exists
        assert mgr.index_exists()

    def test_populate_index(self, test_db, tmp_path):
        """Test populating index from entries."""
        session, engine = test_db

        # Create entries with files
        file1 = tmp_path / "entry1.md"
        file1.write_text("""---
title: Entry 1
---

This is about Alice and her therapy session.
She discussed anxiety and growth.
""")

        entry1 = Entry(
            date=date(2024, 11, 1),
            file_path=str(file1),
            word_count=100,
            reading_time=0.5,
            epigraph="To be or not to be",
            notes="Important reflection",
        )

        session.add(entry1)
        session.commit()

        # Create and populate index
        mgr = SearchIndexManager(engine)
        mgr.create_index()
        count = mgr.populate_index(session)

        assert count == 1

    def test_search_fts(self, test_db, tmp_path):
        """Test FTS5 search functionality."""
        session, engine = test_db

        # Create entry with searchable text
        file1 = tmp_path / "entry1.md"
        file1.write_text("""---
title: Test
---

Alice went to therapy today. We discussed anxiety management.
""")

        entry1 = Entry(
            date=date(2024, 11, 1),
            file_path=str(file1),
            word_count=100,
            reading_time=0.5,
        )

        session.add(entry1)
        session.commit()

        # Build index
        mgr = SearchIndexManager(engine)
        mgr.create_index()
        mgr.populate_index(session)
        mgr.setup_triggers()

        # Search
        results = mgr.search("therapy", limit=10, highlight=True)

        assert len(results) == 1
        assert results[0]['entry_id'] == entry1.id
        assert 'therapy' in results[0]['snippet'].lower()

    def test_rebuild_index(self, test_db, tmp_path):
        """Test rebuilding index."""
        session, engine = test_db

        # Create entry
        file1 = tmp_path / "entry1.md"
        file1.write_text("Test content")

        entry1 = Entry(
            date=date(2024, 11, 1),
            file_path=str(file1),
            word_count=100,
            reading_time=0.5,
        )

        session.add(entry1)
        session.commit()

        # Rebuild
        mgr = SearchIndexManager(engine)
        count = mgr.rebuild_index(session)

        assert count == 1
        assert mgr.index_exists()


class TestQueryParser:
    """Test search query string parsing."""

    def test_parse_simple_text(self):
        """Test parsing simple text query."""
        query = SearchQueryParser.parse("alice therapy")

        assert query.text == "alice therapy"
        assert not query.people
        assert not query.tags

    def test_parse_person_filter(self):
        """Test parsing person filter."""
        query = SearchQueryParser.parse("therapy person:alice")

        assert query.text == "therapy"
        assert "alice" in query.people

    def test_parse_multiple_filters(self):
        """Test parsing multiple filters."""
        query = SearchQueryParser.parse(
            "reflection person:alice tag:therapy city:montreal in:2024"
        )

        assert query.text == "reflection"
        assert "alice" in query.people
        assert "therapy" in query.tags
        assert "montreal" in query.cities
        assert query.year == 2024

    def test_parse_word_count_range(self):
        """Test parsing word count range."""
        query = SearchQueryParser.parse("anxiety words:100-500")

        assert query.text == "anxiety"
        assert query.min_words == 100
        assert query.max_words == 500

    def test_parse_date_range(self):
        """Test parsing date range."""
        query = SearchQueryParser.parse("therapy from:2024-01-01 to:2024-12-31")

        assert query.text == "therapy"
        assert query.date_from == date(2024, 1, 1)
        assert query.date_to == date(2024, 12, 31)

    def test_parse_manuscript_filter(self):
        """Test parsing manuscript filters."""
        query = SearchQueryParser.parse("alice has:manuscript status:source")

        assert query.text == "alice"
        assert query.has_manuscript is True
        assert query.manuscript_status == "source"

    def test_parse_sort_filter(self):
        """Test parsing sort filter."""
        query = SearchQueryParser.parse("therapy sort:date limit:20")

        assert query.text == "therapy"
        assert query.sort_by == "date"
        assert query.limit == 20


class TestSearchEngine:
    """Test search execution with filters."""

    def test_text_search(self, test_db, tmp_path):
        """Test basic text search."""
        session, engine = test_db

        # Create entries
        file1 = tmp_path / "entry1.md"
        file1.write_text("Alice went to therapy")

        file2 = tmp_path / "entry2.md"
        file2.write_text("Bob went to the store")

        entry1 = Entry(
            date=date(2024, 11, 1),
            file_path=str(file1),
            word_count=100,
            reading_time=0.5,
        )

        entry2 = Entry(
            date=date(2024, 11, 2),
            file_path=str(file2),
            word_count=100,
            reading_time=0.5,
        )

        session.add_all([entry1, entry2])
        session.commit()

        # Build index
        mgr = SearchIndexManager(engine)
        mgr.rebuild_index(session)

        # Search
        search_engine = SearchEngine(session)
        query = SearchQueryParser.parse("therapy")
        results = search_engine.search(query)

        assert len(results) == 1
        assert results[0]['entry'].id == entry1.id

    def test_person_filter(self, test_db, tmp_path):
        """Test filtering by person."""
        session, engine = test_db

        file1 = tmp_path / "entry1.md"
        file1.write_text("Content")

        entry1 = Entry(
            date=date(2024, 11, 1),
            file_path=str(file1),
            word_count=100,
            reading_time=0.5,
        )

        alice = Person(name="Alice", relation_type=RelationType.FRIEND)
        entry1.people.append(alice)

        session.add_all([entry1, alice])
        session.commit()

        # Search with person filter
        search_engine = SearchEngine(session)
        query = SearchQueryParser.parse("person:Alice")
        results = search_engine.search(query)

        assert len(results) == 1
        assert results[0]['entry'].id == entry1.id

    def test_year_filter(self, test_db, tmp_path):
        """Test filtering by year."""
        session, engine = test_db

        file1 = tmp_path / "entry1.md"
        file1.write_text("Content")

        file2 = tmp_path / "entry2.md"
        file2.write_text("Content")

        entry1 = Entry(
            date=date(2024, 11, 1),
            file_path=str(file1),
            word_count=100,
            reading_time=0.5,
        )

        entry2 = Entry(
            date=date(2023, 11, 1),
            file_path=str(file2),
            word_count=100,
            reading_time=0.5,
        )

        session.add_all([entry1, entry2])
        session.commit()

        # Search for 2024 only
        search_engine = SearchEngine(session)
        query = SearchQueryParser.parse("in:2024")
        results = search_engine.search(query)

        assert len(results) == 1
        assert results[0]['entry'].date.year == 2024

    def test_word_count_filter(self, test_db, tmp_path):
        """Test filtering by word count."""
        session, engine = test_db

        file1 = tmp_path / "entry1.md"
        file1.write_text("Content")

        file2 = tmp_path / "entry2.md"
        file2.write_text("Content")

        entry1 = Entry(
            date=date(2024, 11, 1),
            file_path=str(file1),
            word_count=300,
            reading_time=1.5,
        )

        entry2 = Entry(
            date=date(2024, 11, 2),
            file_path=str(file2),
            word_count=100,
            reading_time=0.5,
        )

        session.add_all([entry1, entry2])
        session.commit()

        # Search for entries with 200+ words
        search_engine = SearchEngine(session)
        query = SearchQueryParser.parse("words:200-")
        results = search_engine.search(query)

        assert len(results) == 1
        assert results[0]['entry'].word_count == 300

    def test_manuscript_filter(self, test_db, tmp_path):
        """Test filtering by manuscript presence."""
        session, engine = test_db

        file1 = tmp_path / "entry1.md"
        file1.write_text("Content")

        file2 = tmp_path / "entry2.md"
        file2.write_text("Content")

        entry1 = Entry(
            date=date(2024, 11, 1),
            file_path=str(file1),
            word_count=100,
            reading_time=0.5,
        )

        ms_entry = ManuscriptEntry(
            entry=entry1,
            status=ManuscriptStatus.SOURCE,
            edited=True,
        )

        entry2 = Entry(
            date=date(2024, 11, 2),
            file_path=str(file2),
            word_count=100,
            reading_time=0.5,
        )

        session.add_all([entry1, ms_entry, entry2])
        session.commit()

        # Search for manuscript entries only
        search_engine = SearchEngine(session)
        query = SearchQueryParser.parse("has:manuscript")
        results = search_engine.search(query)

        assert len(results) == 1
        assert results[0]['entry'].id == entry1.id

    def test_combined_text_and_filters(self, test_db, tmp_path):
        """Test combining text search with metadata filters."""
        session, engine = test_db

        # Create entries
        file1 = tmp_path / "entry1.md"
        file1.write_text("Alice went to therapy")

        file2 = tmp_path / "entry2.md"
        file2.write_text("Alice went shopping")

        alice = Person(name="Alice", relation_type=RelationType.FRIEND)

        entry1 = Entry(
            date=date(2024, 11, 1),
            file_path=str(file1),
            word_count=100,
            reading_time=0.5,
        )
        entry1.people.append(alice)

        entry2 = Entry(
            date=date(2024, 11, 2),
            file_path=str(file2),
            word_count=100,
            reading_time=0.5,
        )
        entry2.people.append(alice)

        session.add_all([entry1, entry2, alice])
        session.commit()

        # Build index
        mgr = SearchIndexManager(engine)
        mgr.rebuild_index(session)

        # Search: "therapy" + person:Alice
        search_engine = SearchEngine(session)
        query = SearchQueryParser.parse("therapy person:Alice")
        results = search_engine.search(query)

        # Should only match entry1
        assert len(results) == 1
        assert results[0]['entry'].id == entry1.id

    def test_sorting(self, test_db, tmp_path):
        """Test result sorting."""
        session, engine = test_db

        file1 = tmp_path / "entry1.md"
        file1.write_text("Content")

        file2 = tmp_path / "entry2.md"
        file2.write_text("Content")

        entry1 = Entry(
            date=date(2024, 11, 1),
            file_path=str(file1),
            word_count=100,
            reading_time=0.5,
        )

        entry2 = Entry(
            date=date(2024, 11, 5),
            file_path=str(file2),
            word_count=500,
            reading_time=2.5,
        )

        session.add_all([entry1, entry2])
        session.commit()

        # Sort by date descending
        search_engine = SearchEngine(session)
        query = SearchQueryParser.parse("sort:date")
        query.sort_order = "desc"
        results = search_engine.search(query)

        assert results[0]['entry'].date > results[1]['entry'].date

        # Sort by word count ascending
        query = SearchQueryParser.parse("sort:word_count")
        query.sort_order = "asc"
        results = search_engine.search(query)

        assert results[0]['entry'].word_count < results[1]['entry'].word_count


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
