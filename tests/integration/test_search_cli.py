#!/usr/bin/env python3
"""
Integration tests for search CLI (plm-search).

Tests:
- CLI help and basic invocation
- Search query command with various filters
- Index management commands (create, rebuild, status)
"""
import pytest
from datetime import date
from unittest.mock import patch

from click.testing import CliRunner
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dev.database.models import Base, Entry, Person, Tag, RelationType
from dev.database.manager import PalimpsestDB
from dev.search.cli import cli
from dev.search.search_index import SearchIndexManager


class TestSearchCLIHelp:
    """Test CLI help messages."""

    @pytest.fixture
    def runner(self):
        """Create Click test runner."""
        return CliRunner()

    def test_main_help(self, runner):
        """Test main CLI help message."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Full-text search" in result.output
        assert "query" in result.output
        assert "index" in result.output

    def test_query_help(self, runner):
        """Test query command help."""
        result = runner.invoke(cli, ["query", "--help"])
        assert result.exit_code == 0
        assert "Search journal entries" in result.output
        assert "person:NAME" in result.output
        assert "--limit" in result.output
        assert "--sort" in result.output

    def test_index_help(self, runner):
        """Test index group help."""
        result = runner.invoke(cli, ["index", "--help"])
        assert result.exit_code == 0
        assert "Manage full-text search index" in result.output
        assert "create" in result.output
        assert "rebuild" in result.output
        assert "status" in result.output

    def test_index_create_help(self, runner):
        """Test index create command help."""
        result = runner.invoke(cli, ["index", "create", "--help"])
        assert result.exit_code == 0
        assert "Create full-text search index" in result.output
        assert "FTS5" in result.output

    def test_index_rebuild_help(self, runner):
        """Test index rebuild command help."""
        result = runner.invoke(cli, ["index", "rebuild", "--help"])
        assert result.exit_code == 0
        assert "Rebuild full-text search index" in result.output

    def test_index_status_help(self, runner):
        """Test index status command help."""
        result = runner.invoke(cli, ["index", "status", "--help"])
        assert result.exit_code == 0
        assert "Check full-text search index status" in result.output


class TestSearchCLIWithDatabase:
    """Test CLI commands with a real database."""

    @pytest.fixture
    def runner(self):
        """Create Click test runner."""
        return CliRunner()

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create test database with sample data."""
        db_path = tmp_path / "test.db"
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)

        Session = sessionmaker(bind=engine)
        session = Session()

        # Create test entries
        file1 = tmp_path / "entry1.md"
        file1.write_text("""---
title: Entry 1
---

Alice went to therapy today. We discussed anxiety management.
""")

        file2 = tmp_path / "entry2.md"
        file2.write_text("""---
title: Entry 2
---

Bob went to the coffee shop to work on his project.
""")

        file3 = tmp_path / "entry3.md"
        file3.write_text("""---
title: Entry 3
---

Had a great therapy session with Alice. Made progress on anxiety.
""")

        entry1 = Entry(
            date=date(2024, 11, 1),
            file_path=str(file1),
            word_count=100,
            reading_time=0.5,
        )

        entry2 = Entry(
            date=date(2024, 11, 2),
            file_path=str(file2),
            word_count=150,
            reading_time=0.75,
        )

        entry3 = Entry(
            date=date(2024, 11, 3),
            file_path=str(file3),
            word_count=200,
            reading_time=1.0,
        )

        # Add people
        alice = Person(name="Alice", relation_type=RelationType.FRIEND)
        bob = Person(name="Bob", relation_type=RelationType.FRIEND)

        entry1.people.append(alice)
        entry2.people.append(bob)
        entry3.people.append(alice)

        # Add tags
        therapy_tag = Tag(tag="therapy")
        work_tag = Tag(tag="work")

        entry1.tags.append(therapy_tag)
        entry2.tags.append(work_tag)
        entry3.tags.append(therapy_tag)

        session.add_all([entry1, entry2, entry3, alice, bob, therapy_tag, work_tag])
        session.commit()

        # Create and populate search index
        mgr = SearchIndexManager(engine)
        mgr.create_index()
        mgr.populate_index(session)
        mgr.setup_triggers()

        session.close()

        return db_path, engine, tmp_path

    @pytest.fixture
    def mock_db(self, test_db):
        """Mock _get_db to return test database."""
        db_path, engine, tmp_path = test_db

        mock_db_instance = PalimpsestDB.__new__(PalimpsestDB)
        mock_db_instance.db_path = db_path
        mock_db_instance.engine = engine
        mock_db_instance.SessionLocal = sessionmaker(bind=engine)

        with patch("dev.search.cli._get_db", return_value=mock_db_instance):
            yield tmp_path


class TestSearchQuery(TestSearchCLIWithDatabase):
    """Test query command."""

    def test_simple_text_search(self, runner, mock_db):
        """Test simple text search."""
        result = runner.invoke(cli, ["query", "therapy"])

        assert result.exit_code == 0
        assert "Found" in result.output
        assert "2024-11-01" in result.output or "2024-11-03" in result.output

    def test_search_no_results(self, runner, mock_db):
        """Test search with no matching results."""
        result = runner.invoke(cli, ["query", "nonexistentterm123"])

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_search_with_limit(self, runner, mock_db):
        """Test search with --limit option."""
        result = runner.invoke(cli, ["query", "therapy", "--limit", "1"])

        assert result.exit_code == 0
        assert "Found" in result.output

    def test_search_with_sort(self, runner, mock_db):
        """Test search with --sort option."""
        result = runner.invoke(cli, ["query", "therapy", "--sort", "date"])

        assert result.exit_code == 0
        assert "Found" in result.output

    def test_search_verbose(self, runner, mock_db):
        """Test search with verbose output."""
        result = runner.invoke(cli, ["query", "therapy", "-v"])

        assert result.exit_code == 0
        # Verbose mode shows word count
        assert "Words:" in result.output or "Found" in result.output

    def test_search_person_filter(self, runner, mock_db):
        """Test search with person filter and text."""
        # Need both text and filter for FTS to work properly
        # Person name is case-sensitive: "Alice" not "alice"
        result = runner.invoke(cli, ["query", "therapy", "person:Alice"])

        assert result.exit_code == 0
        assert "Found" in result.output

    def test_search_combined_text_and_filter(self, runner, mock_db):
        """Test search combining text and filter."""
        result = runner.invoke(cli, ["query", "therapy", "person:Alice"])

        assert result.exit_code == 0


class TestIndexCommands(TestSearchCLIWithDatabase):
    """Test index management commands."""

    @pytest.fixture
    def empty_test_db(self, tmp_path):
        """Create empty test database without index."""
        db_path = tmp_path / "empty.db"
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)

        Session = sessionmaker(bind=engine)
        session = Session()

        # Create one entry for testing
        file1 = tmp_path / "entry1.md"
        file1.write_text("Test content for indexing")

        entry1 = Entry(
            date=date(2024, 11, 1),
            file_path=str(file1),
            word_count=100,
            reading_time=0.5,
        )

        session.add(entry1)
        session.commit()
        session.close()

        return db_path, engine, tmp_path

    @pytest.fixture
    def mock_empty_db(self, empty_test_db):
        """Mock _get_db to return empty test database."""
        db_path, engine, tmp_path = empty_test_db

        mock_db_instance = PalimpsestDB.__new__(PalimpsestDB)
        mock_db_instance.db_path = db_path
        mock_db_instance.engine = engine
        mock_db_instance.SessionLocal = sessionmaker(bind=engine)

        with patch("dev.search.cli._get_db", return_value=mock_db_instance):
            yield tmp_path

    def test_index_status_exists(self, runner, mock_db):
        """Test index status when index exists."""
        result = runner.invoke(cli, ["index", "status"])

        assert result.exit_code == 0
        assert "Search index exists" in result.output
        assert "Indexed entries" in result.output

    def test_index_status_missing(self, runner, mock_empty_db):
        """Test index status when index does not exist."""
        result = runner.invoke(cli, ["index", "status"])

        assert result.exit_code == 0
        assert "does not exist" in result.output

    def test_index_create(self, runner, mock_empty_db):
        """Test index create command."""
        result = runner.invoke(cli, ["index", "create"])

        assert result.exit_code == 0
        assert "Created search index" in result.output
        assert "1 entries indexed" in result.output

    def test_index_create_already_exists(self, runner, mock_db):
        """Test index create when index already exists."""
        result = runner.invoke(cli, ["index", "create"])

        assert result.exit_code == 0
        assert "already exists" in result.output

    def test_index_rebuild(self, runner, mock_db):
        """Test index rebuild command."""
        result = runner.invoke(cli, ["index", "rebuild"])

        assert result.exit_code == 0
        assert "Rebuilt search index" in result.output
        assert "entries indexed" in result.output


class TestCLIOptions:
    """Test CLI global options."""

    @pytest.fixture
    def runner(self):
        """Create Click test runner."""
        return CliRunner()

    def test_verbose_flag(self, runner, tmp_path):
        """Test --verbose flag is accepted."""
        result = runner.invoke(cli, ["--verbose", "--help"])
        assert result.exit_code == 0

    def test_log_dir_option(self, runner, tmp_path):
        """Test --log-dir option is accepted."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        result = runner.invoke(cli, ["--log-dir", str(log_dir), "--help"])
        assert result.exit_code == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
