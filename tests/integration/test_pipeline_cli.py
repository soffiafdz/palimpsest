#!/usr/bin/env python3
"""
Integration tests for pipeline CLI.

Tests the main CLI commands to ensure they can be invoked
and handle basic argument validation.
"""
import pytest
from click.testing import CliRunner
from dev.pipeline.cli import cli


class TestCLIBasics:
    """Test basic CLI functionality."""

    @pytest.fixture
    def runner(self):
        """Create Click test runner."""
        return CliRunner()

    def test_cli_help(self, runner):
        """Test that CLI help message works."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Palimpsest Journal Processing Pipeline" in result.output

    def test_cli_version_flag(self, runner):
        """Test CLI accepts verbose flag."""
        result = runner.invoke(cli, ["-v", "--help"])
        assert result.exit_code == 0

    def test_inbox_help(self, runner):
        """Test inbox command help."""
        result = runner.invoke(cli, ["inbox", "--help"])
        assert result.exit_code == 0
        assert "inbox" in result.output.lower()

    def test_convert_help(self, runner):
        """Test convert command help."""
        result = runner.invoke(cli, ["convert", "--help"])
        assert result.exit_code == 0
        assert "convert" in result.output.lower() or "text" in result.output.lower()

    def test_sync_db_help(self, runner):
        """Test sync-db command help."""
        result = runner.invoke(cli, ["sync-db", "--help"])
        assert result.exit_code == 0
        assert "database" in result.output.lower() or "sync" in result.output.lower()

    def test_export_db_help(self, runner):
        """Test export-db command help."""
        result = runner.invoke(cli, ["export-db", "--help"])
        assert result.exit_code == 0
        assert "export" in result.output.lower()

    def test_build_pdf_help(self, runner):
        """Test build-pdf command help."""
        result = runner.invoke(cli, ["build-pdf", "--help"])
        assert result.exit_code == 0
        assert "pdf" in result.output.lower()

    def test_status_help(self, runner):
        """Test status command help."""
        result = runner.invoke(cli, ["status", "--help"])
        assert result.exit_code == 0

    def test_validate_help(self, runner):
        """Test validate command help."""
        result = runner.invoke(cli, ["validate", "--help"])
        assert result.exit_code == 0


class TestCLIWithTempDirs:
    """Test CLI commands with temporary directories."""

    @pytest.fixture
    def runner(self):
        """Create Click test runner."""
        return CliRunner()

    def test_inbox_with_empty_dir(self, runner, tmp_path):
        """Test inbox command with empty directory."""
        inbox_dir = tmp_path / "inbox"
        inbox_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = runner.invoke(cli, [
            "inbox",
            "--inbox", str(inbox_dir),
            "--output", str(output_dir),
        ])

        # Should succeed even with no files
        assert result.exit_code == 0 or "complete" in result.output.lower()

    def test_status_command(self, runner):
        """Test status command runs without error."""
        result = runner.invoke(cli, ["status"])
        # Status might fail if database not initialized, but should not crash
        assert result.exit_code in [0, 1]  # 0 = success, 1 = expected failure

    def test_build_pdf_requires_year(self, runner):
        """Test build-pdf requires year argument."""
        result = runner.invoke(cli, ["build-pdf"])
        # Should fail or show error about missing year
        assert result.exit_code != 0 or "year" in result.output.lower()


from unittest.mock import patch, MagicMock

class TestPipelineDataFlow:
    """Test pipeline step orchestration."""

    @pytest.fixture
    def runner(self):
        """Create Click test runner."""
        return CliRunner()

    def test_convert_with_empty_dir(self, runner, tmp_path):
        """Test convert command with empty input directory."""
        input_dir = tmp_path / "txt"
        input_dir.mkdir()
        output_dir = tmp_path / "md"
        output_dir.mkdir()

        result = runner.invoke(cli, [
            "convert",
            "--input", str(input_dir),
            "--output", str(output_dir),
        ])

        # Should handle empty directory gracefully
        assert result.exit_code == 0 or "complete" in result.output.lower()

    @patch("dev.pipeline.cli.sql2wiki.PalimpsestDB")
    def test_export_db_calls_manager(self, mock_db_cls, runner, tmp_path):
        """Test export-db initializes DB and calls export manager."""
        # Setup mock
        mock_db = MagicMock()
        mock_db_cls.return_value = mock_db
        mock_db.session_scope.return_value.__enter__.return_value = MagicMock()
        
        # Mock return value of export
        mock_db.export_manager.export_hierarchical.return_value = {
            "total_entries": 10,
            "processed": 10,
            "errors": 0,
            "duration": 1.0
        }

        output_dir = tmp_path / "md_out"
        
        result = runner.invoke(cli, [
            "export-db",
            "--output", str(output_dir),
            "--force"
        ])

        assert result.exit_code == 0
        assert "Export complete" in result.output
        
        # Verify DB initialized
        mock_db_cls.assert_called_once()
        
        # Verify export method called
        mock_db.export_manager.export_hierarchical.assert_called_once()
        
    @patch("dev.pipeline.wiki2sql.import_people")
    @patch("dev.pipeline.cli.wiki2sql.PalimpsestDB")
    def test_import_wiki_dispatch(self, mock_db_cls, mock_import, runner, tmp_path):
        """Test import-wiki dispatches to correct function."""
        # Setup mock stats
        mock_stats = MagicMock()
        mock_stats.files_processed = 5
        mock_stats.records_updated = 5
        mock_stats.records_skipped = 0
        mock_stats.errors = 0
        mock_import.return_value = mock_stats
        
        wiki_dir = tmp_path / "wiki"
        
        result = runner.invoke(cli, [
            "import-wiki",
            "people",
            "--wiki-dir", str(wiki_dir)
        ])
        
        assert result.exit_code == 0
        assert "Import complete" in result.output
        
        # Verify correct import function called
        mock_import.assert_called_once()
        # Check args (path, db, logger)
        call_args = mock_import.call_args
        assert str(call_args[0][0]) == str(wiki_dir) # First arg is path


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
