#!/usr/bin/env python3
"""
Integration tests for database CLI (metadb).

Tests the database management CLI commands.
"""
import pytest
from click.testing import CliRunner
from dev.database.cli import cli


class TestDatabaseCLIBasics:
    """Test basic database CLI functionality."""

    @pytest.fixture
    def runner(self):
        """Create Click test runner."""
        return CliRunner()

    def test_cli_help(self, runner):
        """Test that CLI help message works."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "database" in result.output.lower() or "metadb" in result.output.lower()

    def test_stats_help(self, runner):
        """Test stats command help."""
        result = runner.invoke(cli, ["stats", "--help"])
        assert result.exit_code == 0

    def test_backup_help(self, runner):
        """Test backup command help."""
        result = runner.invoke(cli, ["backup", "--help"])
        assert result.exit_code == 0
        assert "backup" in result.output.lower()

    def test_health_help(self, runner):
        """Test health command help."""
        result = runner.invoke(cli, ["health", "--help"])
        assert result.exit_code == 0

    def test_init_help(self, runner):
        """Test init command help."""
        result = runner.invoke(cli, ["init", "--help"])
        assert result.exit_code == 0


class TestDatabaseOperations:
    """Test database operations that should work without setup."""

    @pytest.fixture
    def runner(self):
        """Create Click test runner."""
        return CliRunner()

    def test_stats_command(self, runner):
        """Test stats command runs."""
        result = runner.invoke(cli, ["stats"])
        # May fail if DB not initialized, but shouldn't crash
        assert result.exit_code in [0, 1]

    def test_health_command(self, runner):
        """Test health command runs."""
        result = runner.invoke(cli, ["health"])
        # May report issues, but shouldn't crash
        assert result.exit_code in [0, 1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
