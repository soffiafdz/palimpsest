import pytest
from click.testing import CliRunner
from pathlib import Path
from datetime import date, datetime, timezone
from unittest.mock import patch

from dev.database.cli import cli
from dev.database.manager import PalimpsestDB
from dev.database.models import Entry, Person, RelationType, Base
from dev.database.sync_state_manager import SyncStateManager

class TestCliQuerySync:
    """Integration tests for query and sync CLI commands."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def test_dirs(self, tmp_path):
        dirs = {
            "db_path": tmp_path / "test.db",
            "alembic_dir": tmp_path / "alembic",
            "log_dir": tmp_path / "logs",
            "backup_dir": tmp_path / "backups"
        }
        dirs["log_dir"].mkdir()
        dirs["backup_dir"].mkdir()
        return dirs

    @pytest.fixture
    def populated_db(self, test_dirs):
        """Initialize DB and populate with sample data."""
        # Use a real PalimpsestDB for setup
        # Note: In integration tests, we need to handle the alembic dependency.
        # Assuming the environment has alembic installed or we mock the init.
        # But `initialize_schema` runs `alembic upgrade head`.
        # If real alembic is tricky in this environment without full config,
        # we might need to mock `_setup_alembic`.
        # BUT, `test_database_cli.py` uses `init` command which runs alembic.
        # So it should work if we patch `PalimpsestDB._setup_alembic` to not fail or setup properly.
        
        # Let's try to use the real DB logic but mock the Alembic config generation if needed.
        # Or rely on `Base.metadata.create_all` if we bypass alembic.
        
        # For integration tests, creating tables via metadata is faster/safer than running migrations
        # if we don't need to test migrations specifically.
        
        with patch("dev.database.manager.PalimpsestDB._setup_alembic"), \
             patch("dev.database.manager.PalimpsestDB.initialize_schema"):
            
            db = PalimpsestDB(
                db_path=test_dirs["db_path"],
                alembic_dir=test_dirs["alembic_dir"],
                log_dir=test_dirs["log_dir"],
                backup_dir=test_dirs["backup_dir"],
                enable_auto_backup=False,
            )
            
            # Create tables directly
            Base.metadata.create_all(db.engine)
            
            with db.session_scope() as session:
                # Create Entry
                e1 = Entry(
                    date=date(2024, 1, 1),
                    word_count=100,
                    reading_time=1.0,
                    file_path=str(test_dirs["log_dir"] / "2024-01-01.md"),
                    file_hash="dummy_hash"
                )
                session.add(e1)
                
                # Create Person
                p1 = Person(
                    name="Alice",
                    relation_type=RelationType.FRIEND
                )
                e1.people.append(p1)
                
                # Create SyncState
                sync_mgr = SyncStateManager(session, db.logger)
                sync_mgr.update_or_create(
                    entity_type="Entry",
                    entity_id=1, # Assuming ID 1
                    last_synced_at=datetime.now(timezone.utc),
                    sync_source="test",
                    sync_hash="hash123",
                    machine_id="test-machine"
                )
                
                session.commit()
                
        return db

    def invoke_cli(self, runner, test_dirs, args):
        """Helper to invoke CLI."""
        base_args = [
            "--db-path", str(test_dirs["db_path"]),
            "--alembic-dir", str(test_dirs["alembic_dir"]),
            "--log-dir", str(test_dirs["log_dir"]),
            "--backup-dir", str(test_dirs["backup_dir"]),
        ]
        # We need to mock DB init inside the CLI command too to avoid Alembic issues
        with patch("dev.database.manager.PalimpsestDB._setup_alembic"), \
             patch("dev.database.manager.PalimpsestDB.initialize_schema"):
            return runner.invoke(cli, base_args + args)

    def test_query_show(self, runner, test_dirs, populated_db):
        """Test 'query show' command."""
        result = self.invoke_cli(runner, test_dirs, ["query", "show", "2024-01-01"])
        assert result.exit_code == 0
        assert "2024-01-01" in result.output
        assert "100 words" in result.output

    def test_query_show_missing(self, runner, test_dirs, populated_db):
        """Test 'query show' with missing date."""
        result = self.invoke_cli(runner, test_dirs, ["query", "show", "2099-01-01"])
        assert result.exit_code == 1
        assert "No entry found" in result.output

    def test_query_years(self, runner, test_dirs, populated_db):
        """Test 'query years' command."""
        result = self.invoke_cli(runner, test_dirs, ["query", "years"])
        assert result.exit_code == 0
        assert "2024:    1 entries" in result.output

    def test_query_months(self, runner, test_dirs, populated_db):
        """Test 'query months' command."""
        result = self.invoke_cli(runner, test_dirs, ["query", "months", "2024"])
        assert result.exit_code == 0
        assert "Jan (01):   1 entries" in result.output

    def test_sync_status_summary(self, runner, test_dirs, populated_db):
        """Test 'sync status' command (summary)."""
        result = self.invoke_cli(runner, test_dirs, ["sync", "status"])
        assert result.exit_code == 0
        assert "Total entities tracked: 1" in result.output

    def test_sync_stats(self, runner, test_dirs, populated_db):
        """Test 'sync stats' command."""
        result = self.invoke_cli(runner, test_dirs, ["sync", "stats"])
        assert result.exit_code == 0
        assert "Total entities tracked: 1" in result.output
        assert "test: 1" in result.output # source
        assert "test-machine: 1" in result.output # machine

    def test_sync_conflicts_none(self, runner, test_dirs, populated_db):
        """Test 'sync conflicts' with no conflicts."""
        result = self.invoke_cli(runner, test_dirs, ["sync", "conflicts"])
        assert result.exit_code == 0
        assert "No unresolved conflicts" in result.output
