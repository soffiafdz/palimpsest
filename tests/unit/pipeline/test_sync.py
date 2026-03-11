#!/usr/bin/env python3
"""
test_sync.py
------------
Unit tests for the ``plm sync`` command.

Verifies sync orchestration logic with mocked importers/exporters:
- Step ordering and conditional execution
- ``--no-wiki`` skips wiki generation
- ``--dry-run`` prevents DB modifications
- ``--commit`` triggers data submodule commit
- No-op sync when nothing changed skips JSON export

Usage:
    pytest tests/unit/pipeline/test_sync.py -v
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import sys
from unittest.mock import MagicMock, patch

# --- Third-party imports ---
import pytest
from click.testing import CliRunner

# --- Local imports ---
from dev.pipeline.cli import cli


@pytest.fixture
def runner():
    """Create Click test runner."""
    return CliRunner()


# The __init__.py `from .sync import sync` shadows the module name with the
# click Command.  Retrieve the *real* module from sys.modules for patching.
_sync_mod = sys.modules["dev.pipeline.cli.sync"]

DB_MANAGER = "dev.database.manager"


@pytest.fixture
def patched_sync(monkeypatch):
    """Patch all sync helper functions and PalimpsestDB with defaults.

    Returns a dict of mock objects keyed by function name.
    """
    mocks = {}
    defaults = {
        "_run_json_import": 0,
        "_run_entries_import": 0,
        "_run_auto_prune": 0,
        "_run_metadata_import": 0,
        "_run_json_export": None,
        "_run_wiki_generate": None,
        "_run_data_commit": False,
    }
    for name, ret_val in defaults.items():
        mock = MagicMock(return_value=ret_val)
        monkeypatch.setattr(_sync_mod, name, mock)
        mocks[name] = mock

    db_mock = MagicMock()
    monkeypatch.setattr(f"{DB_MANAGER}.PalimpsestDB", db_mock)
    mocks["PalimpsestDB"] = db_mock

    return mocks


class TestSyncCommand:
    """Verify plm sync CLI invocation and option handling."""

    def test_sync_exists(self, runner):
        """plm sync should be a registered top-level command."""
        result = runner.invoke(cli, ["sync", "--help"])
        assert result.exit_code == 0

    def test_sync_help_shows_options(self, runner):
        """Help should list all sync options."""
        result = runner.invoke(cli, ["sync", "--help"])
        assert "--no-wiki" in result.output
        assert "--commit" in result.output
        assert "--dry-run" in result.output
        assert "--years" in result.output
        assert "--verbose" in result.output


class TestSyncOrchestration:
    """Verify sync runs steps in the correct order."""

    def test_full_sync_no_changes(self, runner, patched_sync):
        """When entries/metadata report 0 changes, JSON export is skipped."""
        patched_sync["_run_json_import"].return_value = 5
        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0, result.output
        assert "[OK] Sync complete" in result.output
        assert "No changes detected; skipped" in result.output
        patched_sync["_run_json_export"].assert_not_called()

    def test_metadata_changes_trigger_export(self, runner, patched_sync):
        """When metadata import finds changes, JSON export runs."""
        patched_sync["_run_metadata_import"].return_value = 3
        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0, result.output
        assert "re-exported" in result.output
        patched_sync["_run_json_export"].assert_called_once()

    def test_entry_changes_trigger_prune_and_export(self, runner, patched_sync):
        """When entries import finds changes, prune + JSON export run."""
        patched_sync["_run_entries_import"].return_value = 5
        patched_sync["_run_auto_prune"].return_value = 2
        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0, result.output
        assert "Pruning" in result.output
        assert "re-exported" in result.output
        patched_sync["_run_auto_prune"].assert_called_once()
        patched_sync["_run_json_export"].assert_called_once()


class TestSyncFlags:
    """Verify individual flags control step execution."""

    def test_no_wiki_skips_generation(self, runner, patched_sync):
        """--no-wiki prevents wiki generation."""
        patched_sync["_run_metadata_import"].return_value = 1
        result = runner.invoke(cli, ["sync", "--no-wiki"])
        assert result.exit_code == 0, result.output
        assert "--no-wiki" in result.output
        patched_sync["_run_wiki_generate"].assert_not_called()

    def test_dry_run_skips_db_writes(self, runner, patched_sync):
        """--dry-run skips JSON import, metadata import, export, wiki."""
        result = runner.invoke(cli, ["sync", "--dry-run"])
        assert result.exit_code == 0, result.output
        assert "dry-run" in result.output
        patched_sync["_run_json_import"].assert_not_called()
        patched_sync["_run_metadata_import"].assert_not_called()
        patched_sync["_run_json_export"].assert_not_called()
        patched_sync["_run_wiki_generate"].assert_not_called()

    def test_commit_triggers_data_commit(self, runner, patched_sync):
        """--commit triggers data submodule commit."""
        patched_sync["_run_metadata_import"].return_value = 1
        patched_sync["_run_data_commit"].return_value = True
        result = runner.invoke(cli, ["sync", "--commit"])
        assert result.exit_code == 0, result.output
        patched_sync["_run_data_commit"].assert_called_once()
        assert "Committed" in result.output

    def test_no_commit_by_default(self, runner, patched_sync):
        """Without --commit, data submodule commit is skipped."""
        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0, result.output
        patched_sync["_run_data_commit"].assert_not_called()
        assert "use --commit" in result.output


class TestSyncHelpers:
    """Test helper functions directly."""

    def test_parse_years_none(self):
        """None input returns None."""
        assert _sync_mod._parse_years(None) is None

    def test_parse_years_single(self):
        """Single year returns set with one element."""
        assert _sync_mod._parse_years("2024") == {"2024"}

    def test_parse_years_range(self):
        """Year range returns set of all years in range."""
        result = _sync_mod._parse_years("2021-2024")
        assert result == {"2021", "2022", "2023", "2024"}


class TestSyncConfigDefaults:
    """Verify project config provides defaults for sync flags."""

    def test_config_min_year_provides_default_years(
        self, runner, patched_sync
    ):
        """Config min_year builds year range when --years not passed."""
        cfg = {"min_year": 2022, "no_wiki": False, "auto_commit": False}
        with patch("dev.core.config.get_sync_config", return_value=cfg):
            result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0, result.output
        assert "years:" in result.output

    def test_cli_years_overrides_config(self, runner, patched_sync):
        """--years CLI flag overrides config min_year."""
        cfg = {"min_year": 2021, "no_wiki": False, "auto_commit": False}
        with patch("dev.core.config.get_sync_config", return_value=cfg):
            result = runner.invoke(cli, ["sync", "--years", "2025"])
        assert result.exit_code == 0, result.output
        assert "years: 2025" in result.output

    def test_config_no_wiki_provides_default(self, runner, patched_sync):
        """Config no_wiki=True skips wiki when --no-wiki not passed."""
        cfg = {"min_year": None, "no_wiki": True, "auto_commit": False}
        patched_sync["_run_metadata_import"].return_value = 1
        with patch("dev.core.config.get_sync_config", return_value=cfg):
            result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0, result.output
        patched_sync["_run_wiki_generate"].assert_not_called()

    def test_config_auto_commit_provides_default(self, runner, patched_sync):
        """Config auto_commit=True triggers commit when --commit not passed."""
        cfg = {"min_year": None, "no_wiki": False, "auto_commit": True}
        patched_sync["_run_metadata_import"].return_value = 1
        patched_sync["_run_data_commit"].return_value = True
        with patch("dev.core.config.get_sync_config", return_value=cfg):
            result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0, result.output
        patched_sync["_run_data_commit"].assert_called_once()
