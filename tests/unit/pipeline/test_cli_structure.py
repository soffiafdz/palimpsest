#!/usr/bin/env python3
"""
test_cli_structure.py
---------------------
Smoke tests for CLI command structure.

Verifies that all command groups and subcommands are properly registered
and accessible through the ``plm`` entry point. These tests catch
import errors, missing registrations, and naming issues without
requiring database access.

Key Features:
    - Validates all top-level commands exist
    - Validates all subcommand groups and their children
    - Verifies removed commands no longer exist
    - Tests --help output for each group

Usage:
    pytest tests/unit/pipeline/test_cli_structure.py -v
"""
# --- Annotations ---
from __future__ import annotations

# --- Third-party imports ---
import pytest
from click.testing import CliRunner

# --- Local imports ---
from dev.pipeline.cli import cli


@pytest.fixture
def runner():
    """Create Click test runner."""
    return CliRunner()


class TestTopLevelCommands:
    """Verify top-level commands are registered."""

    @pytest.mark.parametrize("command", [
        "inbox", "convert", "status", "sync", "export",
    ])
    def test_top_level_commands_exist(self, runner, command):
        """Top-level commands should be accessible."""
        result = runner.invoke(cli, [command, "--help"])
        assert result.exit_code == 0, f"{command}: {result.output}"

    @pytest.mark.parametrize("group", [
        "build", "pipeline", "db",
        "validate", "wiki", "metadata",
    ])
    def test_command_groups_exist(self, runner, group):
        """Command groups should be accessible."""
        result = runner.invoke(cli, [group, "--help"])
        assert result.exit_code == 0, f"{group}: {result.output}"


class TestBuildGroup:
    """Verify build subcommands."""

    @pytest.mark.parametrize("command", ["pdf", "metadata"])
    def test_build_subcommands(self, runner, command):
        """plm build pdf/metadata should exist."""
        result = runner.invoke(cli, ["build", command, "--help"])
        assert result.exit_code == 0


class TestPipelineGroup:
    """Verify pipeline subcommands."""

    def test_pipeline_run(self, runner):
        """plm pipeline run should exist."""
        result = runner.invoke(cli, ["pipeline", "run", "--help"])
        assert result.exit_code == 0


class TestDbGroup:
    """Verify db subcommands."""

    @pytest.mark.parametrize("command", [
        "init", "reset", "backup", "backups", "restore",
        "stats", "health", "optimize", "analyze", "prune",
        "create", "upgrade", "downgrade", "migration-status", "history",
        "show", "years", "months", "batches",
    ])
    def test_db_subcommands(self, runner, command):
        """All DB subcommands should be accessible."""
        result = runner.invoke(cli, ["db", command, "--help"])
        assert result.exit_code == 0, f"db {command}: {result.output}"


class TestMetadataGroup:
    """Verify metadata subcommands."""

    @pytest.mark.parametrize("command", [
        "export", "import", "validate", "list", "rename",
    ])
    def test_metadata_subcommands(self, runner, command):
        """All metadata subcommands should be accessible."""
        result = runner.invoke(cli, ["metadata", command, "--help"])
        assert result.exit_code == 0, f"metadata {command}: {result.output}"


class TestRemovedCommands:
    """Verify old commands no longer exist."""

    @pytest.mark.parametrize("command", [
        "import-metadata",
        "export-json",
        "import-json",
        "build-pdf",
        "build-metadata-pdf",
        "run-all",
        "backup-full",
        "backup-list-full",
        "prune-orphans",
    ])
    def test_old_commands_removed(self, runner, command):
        """Old dashed commands should not be accessible."""
        result = runner.invoke(cli, [command])
        assert result.exit_code != 0

    def test_list_entities_renamed(self, runner):
        """plm metadata list-entities should not exist (renamed to list)."""
        result = runner.invoke(cli, ["metadata", "list-entities"])
        assert result.exit_code != 0

    def test_entries_group_removed(self, runner):
        """plm entries should not exist (subsumed by sync)."""
        result = runner.invoke(cli, ["entries", "import"])
        assert result.exit_code != 0

    def test_json_group_removed(self, runner):
        """plm json should not exist (subsumed by sync + top-level export)."""
        result = runner.invoke(cli, ["json", "export"])
        assert result.exit_code != 0
