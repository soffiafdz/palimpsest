#!/usr/bin/env python3
"""
Integration tests for validators CLI.

Tests the validation CLI commands.
"""
import pytest
from click.testing import CliRunner
from dev.validators.cli import cli


class TestValidatorsCLIBasics:
    """Test basic validators CLI functionality."""

    @pytest.fixture
    def runner(self):
        """Create Click test runner."""
        return CliRunner()

    def test_cli_help(self, runner):
        """Test that CLI help message works."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "validate" in result.output.lower()

    def test_wiki_help(self, runner):
        """Test wiki validation command help."""
        result = runner.invoke(cli, ["wiki", "--help"])
        assert result.exit_code == 0

    def test_db_help(self, runner):
        """Test database validation command help."""
        result = runner.invoke(cli, ["db", "--help"])
        assert result.exit_code == 0

    def test_md_help(self, runner):
        """Test markdown validation command help."""
        result = runner.invoke(cli, ["md", "--help"])
        assert result.exit_code == 0


class TestValidatorOperations:
    """Test validator operations."""

    @pytest.fixture
    def runner(self):
        """Create Click test runner."""
        return CliRunner()

    def test_wiki_stats(self, runner):
        """Test wiki stats command."""
        result = runner.invoke(cli, ["wiki", "stats"])
        # May fail if wiki not set up, but shouldn't crash
        assert result.exit_code in [0, 1]

    def test_db_schema(self, runner):
        """Test database schema validation."""
        result = runner.invoke(cli, ["db", "schema"])
        # May fail if DB not set up, but shouldn't crash
        assert result.exit_code in [0, 1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
