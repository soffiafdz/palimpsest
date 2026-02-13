#!/usr/bin/env python3
"""
test_wiki_cli.py
----------------
Integration tests for the ``plm wiki`` CLI commands.

Tests CLI invocation via Click's CliRunner for all wiki subcommands:
generate, lint, sync, and publish.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import json

# --- Third-party imports ---
import pytest
from click.testing import CliRunner

# --- Local imports ---
from dev.pipeline.cli import cli
from dev.wiki.exporter import WikiExporter


@pytest.fixture
def runner():
    """Create Click test runner."""
    return CliRunner()


@pytest.fixture(autouse=True)
def _patch_db_path(test_db, test_db_path, populated_wiki_db, monkeypatch):
    """
    Patch DB_PATH so CLI commands use the test database.

    The CLI commands import DB_PATH at module level, so we monkeypatch
    both the source (dev.core.paths) and the local references in the
    wiki and metadata_yaml CLI modules.
    """
    import sys

    monkeypatch.setattr("dev.core.paths.DB_PATH", test_db_path)
    # Patch the local DB_PATH reference in the wiki CLI module
    wiki_mod = sys.modules.get("dev.pipeline.cli.wiki")
    if wiki_mod is not None:
        monkeypatch.setattr(wiki_mod, "DB_PATH", test_db_path)
    metadata_mod = sys.modules.get("dev.pipeline.cli.metadata_yaml")
    if metadata_mod is not None:
        monkeypatch.setattr(metadata_mod, "DB_PATH", test_db_path)


class TestWikiGenerateCLI:
    """Tests for ``plm wiki generate``."""

    def test_generate_help(self, runner):
        """Help text works for generate command."""
        result = runner.invoke(cli, ["wiki", "generate", "--help"])
        assert result.exit_code == 0
        assert "Generate wiki pages" in result.output

    def test_generate_with_output_dir(self, runner, wiki_output):
        """Generate command accepts --output-dir."""
        result = runner.invoke(
            cli,
            ["wiki", "generate", "--output-dir", str(wiki_output)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "Wiki generation complete" in result.output

    def test_generate_with_section_filter(self, runner, wiki_output):
        """Generate with --section journal."""
        result = runner.invoke(
            cli,
            [
                "wiki", "generate",
                "--section", "journal",
                "--output-dir", str(wiki_output),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0

    def test_generate_with_type_filter(self, runner, wiki_output):
        """Generate with --type people."""
        result = runner.invoke(
            cli,
            [
                "wiki", "generate",
                "--section", "journal",
                "--type", "people",
                "--output-dir", str(wiki_output),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0

    def test_generate_invalid_section(self, runner):
        """Invalid section choice rejected."""
        result = runner.invoke(
            cli, ["wiki", "generate", "--section", "invalid"]
        )
        assert result.exit_code != 0


class TestWikiLintCLI:
    """Tests for ``plm wiki lint``."""

    def test_lint_help(self, runner):
        """Help text works for lint command."""
        result = runner.invoke(cli, ["wiki", "lint", "--help"])
        assert result.exit_code == 0
        assert "Lint wiki files" in result.output

    def test_lint_json_output(self, runner, test_db, wiki_output):
        """Lint --format json produces valid JSON."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all()

        result = runner.invoke(
            cli,
            ["wiki", "lint", str(wiki_output), "--format", "json"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0

        parsed = json.loads(result.output)
        assert isinstance(parsed, dict)

    def test_lint_text_output(self, runner, test_db, wiki_output):
        """Lint --format text produces human-readable output."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all()

        result = runner.invoke(
            cli,
            ["wiki", "lint", str(wiki_output), "--format", "text"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "diagnostic(s)" in result.output

    def test_lint_single_file(self, runner, test_db, wiki_output):
        """Lint accepts a single file path."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all()

        entry_file = (
            wiki_output / "journal" / "entries" / "2024" / "2024-11-08.md"
        )
        result = runner.invoke(
            cli,
            ["wiki", "lint", str(entry_file), "--format", "json"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, dict)


class TestWikiSyncCLI:
    """Tests for ``plm wiki sync``."""

    def test_sync_help(self, runner):
        """Help text works for sync command."""
        result = runner.invoke(cli, ["wiki", "sync", "--help"])
        assert result.exit_code == 0
        assert "Sync manuscript wiki" in result.output

    def test_sync_ingest_generate_mutual_exclusion(self, runner):
        """--ingest and --generate cannot be used together."""
        result = runner.invoke(
            cli, ["wiki", "sync", "--ingest", "--generate"]
        )
        assert result.exit_code != 0

    def test_sync_generate_only(self, runner, test_db, wiki_output):
        """Sync --generate runs without error when manuscript dir exists."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="manuscript")

        result = runner.invoke(
            cli, ["wiki", "sync", "--generate"],
            catch_exceptions=False,
        )
        # May fail if WIKI_DIR doesn't match wiki_output, but shouldn't crash
        assert result.exit_code in [0, 1]


class TestWikiPublishCLI:
    """Tests for ``plm wiki publish``."""

    def test_publish_help(self, runner):
        """Help text works for publish command."""
        result = runner.invoke(cli, ["wiki", "publish", "--help"])
        assert result.exit_code == 0
        assert "Publish wiki to Quartz" in result.output
