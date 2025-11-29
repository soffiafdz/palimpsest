#!/usr/bin/env python3
"""
Integration tests for database CLI (metadb).

Tests the database management CLI commands including init, backup, and maintenance.
"""
import pytest
from click.testing import CliRunner
from dev.database.cli import cli

class TestDatabaseCLI:
    """Test database CLI commands with a temporary database."""

    @pytest.fixture
    def runner(self):
        """Create Click test runner."""
        return CliRunner()

    @pytest.fixture
    def test_dirs(self, tmp_path):
        """Create temporary directories for testing."""
        dirs = {
            "db_path": tmp_path / "test.db",
            "alembic_dir": tmp_path / "alembic",
            "log_dir": tmp_path / "logs",
            "backup_dir": tmp_path / "backups"
        }
        
        # Create directories
        dirs["log_dir"].mkdir()
        dirs["backup_dir"].mkdir()
        
        return dirs

    def invoke_cli(self, runner, test_dirs, args, **kwargs):
        """Helper to invoke CLI with test configuration."""
        base_args = [
            "--db-path", str(test_dirs["db_path"]),
            "--alembic-dir", str(test_dirs["alembic_dir"]),
            "--log-dir", str(test_dirs["log_dir"]),
            "--backup-dir", str(test_dirs["backup_dir"]),
        ]
        return runner.invoke(cli, base_args + args, **kwargs)

    def test_cli_help(self, runner):
        """Test that CLI help message works."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "database" in result.output.lower()

    def test_init_command(self, runner, test_dirs):
        """Test 'init' command creates database."""
        # Run init command (full init to ensure Alembic is set up)
        result = self.invoke_cli(runner, test_dirs, ["init"])
        
        # Check success
        assert result.exit_code == 0
        assert "Initializing Alembic" in result.output
        assert "Initializing database schema" in result.output
        assert "Complete setup finished" in result.output
        
        # Verify file creation
        assert test_dirs["db_path"].exists()
        assert (test_dirs["alembic_dir"] / "env.py").exists()
        
        # Verify tables created (basic check by size or connect)
        assert test_dirs["db_path"].stat().st_size > 0

    def test_backup_flow(self, runner, test_dirs):
        """Test backup creation and listing."""
        # First init the DB
        self.invoke_cli(runner, test_dirs, ["init"])
        
        # Create backup
        result = self.invoke_cli(runner, test_dirs, ["backup", "--type", "manual", "--suffix", "test"])
        
        assert result.exit_code == 0
        assert "Backup created" in result.output
        
        # Verify backup file exists
        manual_backup_dir = test_dirs["backup_dir"] / "database" / "manual"
        assert manual_backup_dir.exists()
        backups = list(manual_backup_dir.glob("*.db"))
        assert len(backups) == 1
        assert "test" in backups[0].name

        # List backups
        result_list = self.invoke_cli(runner, test_dirs, ["backups"])
        assert result_list.exit_code == 0
        assert "MANUAL" in result_list.output
        assert backups[0].name in result_list.output

    def test_stats_command(self, runner, test_dirs):
        """Test 'stats' command on initialized DB."""
        self.invoke_cli(runner, test_dirs, ["init"])
        
        result = self.invoke_cli(runner, test_dirs, ["stats"])
        assert result.exit_code == 0
        # Depending on implementation, it might show 0 entries or similar
        # Just checking it doesn't crash

    def test_reset_command(self, runner, test_dirs):
        """Test 'reset' command recreates the DB."""
        self.invoke_cli(runner, test_dirs, ["init"])
        
        # Write something to it? Or just check file timestamp
        test_dirs["db_path"].stat().st_mtime
        
        # Run reset
        # We need to pass input "y" for confirmation
        result = self.invoke_cli(runner, test_dirs, ["reset", "--keep-backups"], input="y\n")
        
        assert result.exit_code == 0
        assert "Resetting database" in result.output
        assert "Database reset complete" in result.output
        
        # Verify file still exists
        assert test_dirs["db_path"].exists()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
