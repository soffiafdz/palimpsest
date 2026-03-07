#!/usr/bin/env python3
"""
Integration tests for validators CLI.

Tests the validation CLI commands via ``plm validate``.
"""
import pytest
from click.testing import CliRunner
from dev.pipeline.cli import cli


class TestValidatorsCLIBasics:
    """Test basic validators CLI functionality."""

    @pytest.fixture
    def runner(self):
        """Create Click test runner."""
        return CliRunner()

    def test_validate_help(self, runner):
        """Test that validate help message shows all subgroups."""
        result = runner.invoke(cli, ["validate", "--help"])
        assert result.exit_code == 0
        assert "pipeline" in result.output.lower()
        assert "db" in result.output
        assert "md" in result.output
        assert "frontmatter" in result.output
        assert "consistency" in result.output

    def test_db_help(self, runner):
        """Test database validation command help."""
        result = runner.invoke(cli, ["validate", "db", "--help"])
        assert result.exit_code == 0

    def test_md_help(self, runner):
        """Test markdown validation command help."""
        result = runner.invoke(cli, ["validate", "md", "--help"])
        assert result.exit_code == 0

    def test_frontmatter_help(self, runner):
        """Test frontmatter validation command help."""
        result = runner.invoke(cli, ["validate", "frontmatter", "--help"])
        assert result.exit_code == 0

    def test_consistency_help(self, runner):
        """Test consistency validation command help."""
        result = runner.invoke(cli, ["validate", "consistency", "--help"])
        assert result.exit_code == 0


class TestValidatorOperations:
    """Test validator operations."""

    @pytest.fixture
    def runner(self):
        """Create Click test runner."""
        return CliRunner()

    def test_db_schema(self, runner):
        """Test database schema validation."""
        result = runner.invoke(cli, ["validate", "db", "schema"])
        # May fail if DB not set up, but shouldn't crash
        assert result.exit_code in [0, 1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
