#!/usr/bin/env python3
"""
test_sync_state.py
------------------
Unit tests for git-based sync state tracking.

Verifies commit hash storage/retrieval, git diff change detection,
and file filtering for incremental sync.

Usage:
    pytest tests/unit/pipeline/test_sync_state.py -v
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from unittest.mock import MagicMock, patch

# --- Local imports ---
from dev.pipeline.sync_state import (
    get_data_head,
    get_stored_sync_hash,
    store_sync_hash,
    get_changed_files,
    filter_json_export_files,
    filter_metadata_files,
)


SYNC_STATE_MOD = "dev.pipeline.sync_state"


class TestGetDataHead:
    """Tests for get_data_head()."""

    def test_returns_commit_hash(self):
        """Returns stripped commit hash from git rev-parse."""
        mock_result = MagicMock(stdout="abc123def456\n")
        with patch(f"{SYNC_STATE_MOD}.subprocess.run", return_value=mock_result):
            assert get_data_head() == "abc123def456"

    def test_returns_none_on_failure(self):
        """Returns None when git command fails."""
        import subprocess
        with patch(
            f"{SYNC_STATE_MOD}.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "git"),
        ):
            assert get_data_head() is None

    def test_returns_none_when_git_missing(self):
        """Returns None when git is not installed."""
        with patch(
            f"{SYNC_STATE_MOD}.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            assert get_data_head() is None


class TestStoredSyncHash:
    """Tests for get/store sync hash."""

    def test_returns_none_when_missing(self, tmp_path):
        """Returns None when state file does not exist."""
        with patch(f"{SYNC_STATE_MOD}.SYNC_STATE_PATH", tmp_path / ".sync_state"):
            assert get_stored_sync_hash() is None

    def test_returns_stored_hash(self, tmp_path):
        """Returns the hash from the state file."""
        state_file = tmp_path / ".sync_state"
        state_file.write_text("abc123\n")
        with patch(f"{SYNC_STATE_MOD}.SYNC_STATE_PATH", state_file):
            assert get_stored_sync_hash() == "abc123"

    def test_returns_none_for_empty_file(self, tmp_path):
        """Returns None for empty state file."""
        state_file = tmp_path / ".sync_state"
        state_file.write_text("")
        with patch(f"{SYNC_STATE_MOD}.SYNC_STATE_PATH", state_file):
            assert get_stored_sync_hash() is None

    def test_store_writes_hash(self, tmp_path):
        """store_sync_hash writes hash to state file."""
        state_file = tmp_path / ".sync_state"
        with patch(f"{SYNC_STATE_MOD}.SYNC_STATE_PATH", state_file):
            store_sync_hash("abc123def")
        assert state_file.read_text() == "abc123def\n"

    def test_store_overwrites_existing(self, tmp_path):
        """store_sync_hash overwrites previous hash."""
        state_file = tmp_path / ".sync_state"
        state_file.write_text("old_hash\n")
        with patch(f"{SYNC_STATE_MOD}.SYNC_STATE_PATH", state_file):
            store_sync_hash("new_hash")
        assert state_file.read_text() == "new_hash\n"


class TestGetChangedFiles:
    """Tests for get_changed_files()."""

    def test_returns_existing_changed_files(self, tmp_path):
        """Returns absolute paths for changed files that exist."""
        (tmp_path / "file1.json").touch()
        (tmp_path / "file2.json").touch()
        mock_result = MagicMock(stdout="file1.json\nfile2.json\ndeleted.json\n")
        with patch(f"{SYNC_STATE_MOD}.subprocess.run", return_value=mock_result), \
             patch(f"{SYNC_STATE_MOD}.DATA_DIR", tmp_path):
            result = get_changed_files("old", "new")
        assert result == {tmp_path / "file1.json", tmp_path / "file2.json"}

    def test_filters_deleted_files(self, tmp_path):
        """Excludes files that no longer exist on disk."""
        mock_result = MagicMock(stdout="deleted.json\n")
        with patch(f"{SYNC_STATE_MOD}.subprocess.run", return_value=mock_result), \
             patch(f"{SYNC_STATE_MOD}.DATA_DIR", tmp_path):
            result = get_changed_files("old", "new")
        assert result == set()

    def test_returns_empty_on_failure(self, tmp_path):
        """Returns empty set when git command fails."""
        import subprocess
        with patch(
            f"{SYNC_STATE_MOD}.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "git"),
        ):
            assert get_changed_files("old", "new") == set()

    def test_handles_empty_output(self, tmp_path):
        """Returns empty set for empty git diff output."""
        mock_result = MagicMock(stdout="")
        with patch(f"{SYNC_STATE_MOD}.subprocess.run", return_value=mock_result), \
             patch(f"{SYNC_STATE_MOD}.DATA_DIR", tmp_path):
            result = get_changed_files("old", "new")
        assert result == set()


class TestFilterFunctions:
    """Tests for filter_json_export_files and filter_metadata_files."""

    def test_filter_json_exports(self, tmp_path):
        """Filters to only JSON files under exports/journal/."""
        data_dir = tmp_path / "data"
        exports = data_dir / "exports" / "journal"
        meta = data_dir / "metadata" / "people"
        exports.mkdir(parents=True)
        meta.mkdir(parents=True)

        json_file = exports / "entries" / "2025" / "2025-01-01.json"
        json_file.parent.mkdir(parents=True)
        yaml_file = meta / "bob.yaml"

        changed = {json_file, yaml_file}
        with patch(f"{SYNC_STATE_MOD}.DATA_DIR", data_dir):
            result = filter_json_export_files(changed)
        assert result == {json_file}

    def test_filter_metadata_excludes_journal(self, tmp_path):
        """Filters metadata YAML but excludes metadata/journal/."""
        data_dir = tmp_path / "data"
        meta_people = data_dir / "metadata" / "people"
        meta_journal = data_dir / "metadata" / "journal" / "2025"
        meta_people.mkdir(parents=True)
        meta_journal.mkdir(parents=True)

        people_yaml = meta_people / "bob.yaml"
        entry_yaml = meta_journal / "2025-01-01.yaml"

        changed = {people_yaml, entry_yaml}
        with patch(f"{SYNC_STATE_MOD}.DATA_DIR", data_dir):
            result = filter_metadata_files(changed)
        assert result == {people_yaml}

    def test_filter_metadata_includes_manuscript(self, tmp_path):
        """Includes manuscript metadata YAML files."""
        data_dir = tmp_path / "data"
        ms_chapters = data_dir / "metadata" / "manuscript" / "chapters"
        ms_chapters.mkdir(parents=True)

        chapter_yaml = ms_chapters / "chapter-one.yaml"
        changed = {chapter_yaml}
        with patch(f"{SYNC_STATE_MOD}.DATA_DIR", data_dir):
            result = filter_metadata_files(changed)
        assert result == {chapter_yaml}
