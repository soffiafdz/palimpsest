#!/usr/bin/env python3
"""
test_sync_pending.py
--------------------
Tests for the .sync-pending marker system.

Validates that:
    - WikiExporter.generate_all() refuses when marker exists
    - WikiSync.sync_manuscript(generate_only=True) refuses when marker exists
    - WikiSync._ingest() clears the marker after commit
    - Full sync (ingest + generate) proceeds and clears marker
    - Missing or malformed markers don't cause errors

Key Test Areas:
    - Pre-generate guard in WikiExporter
    - Generate-only guard in WikiSync
    - Marker clear after successful ingest
    - Edge cases (missing files, malformed JSON)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

# --- Third-party imports ---
import pytest

# --- Local imports ---
from dev.wiki.exporter import WikiExporter
from dev.wiki.sync import WikiSync


# ==================== Fixtures ====================

@pytest.fixture
def wiki_dir(tmp_path):
    """Create a temporary wiki directory structure."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    manuscript = wiki / "manuscript"
    manuscript.mkdir()
    (manuscript / "chapters").mkdir()
    return wiki


@pytest.fixture
def mock_db():
    """Create a mock PalimpsestDB."""
    return MagicMock()


@pytest.fixture
def sync_pending_marker(wiki_dir):
    """
    Write a .sync-pending marker file.

    Returns the marker path for assertions.
    """
    marker = wiki_dir / ".sync-pending"
    data = {
        "machine": "writer-deck",
        "timestamp": "2026-02-13T14:22:00",
        "files": [
            "manuscript/chapters/the-gray-fence.md",
            "manuscript/characters/lucia.md",
        ],
    }
    marker.write_text(json.dumps(data), encoding="utf-8")
    return marker


# ==================== Exporter Guard Tests ====================

class TestExporterSyncPendingGuard:
    """Tests for WikiExporter._check_sync_pending()."""

    def test_generate_refuses_with_marker(
        self, wiki_dir, mock_db, sync_pending_marker
    ):
        """
        generate_all() raises RuntimeError when .sync-pending exists.

        The error message should include the machine name and pending files.
        """
        exporter = WikiExporter(mock_db, output_dir=wiki_dir)

        with pytest.raises(RuntimeError, match="Deck edits pending"):
            exporter.generate_all()

    def test_generate_refuses_lists_files(
        self, wiki_dir, mock_db, sync_pending_marker
    ):
        """
        RuntimeError message includes the list of pending files.
        """
        exporter = WikiExporter(mock_db, output_dir=wiki_dir)

        with pytest.raises(RuntimeError, match="the-gray-fence.md"):
            exporter.generate_all()

    def test_generate_refuses_shows_machine(
        self, wiki_dir, mock_db, sync_pending_marker
    ):
        """
        RuntimeError message includes the machine name.
        """
        exporter = WikiExporter(mock_db, output_dir=wiki_dir)

        with pytest.raises(RuntimeError, match="writer-deck"):
            exporter.generate_all()

    def test_generate_proceeds_without_marker(self, wiki_dir, mock_db):
        """
        generate_all() proceeds normally when no marker exists.

        Mocks session_scope to avoid actual DB work.
        """
        exporter = WikiExporter(mock_db, output_dir=wiki_dir)

        with patch.object(mock_db, "session_scope") as mock_scope:
            mock_scope.return_value.__enter__ = MagicMock()
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)
            # Should not raise — just verifying no RuntimeError
            try:
                exporter.generate_all()
            except RuntimeError:
                pytest.fail("generate_all raised RuntimeError without marker")
            except Exception:
                # Other errors (from mocked DB) are expected and fine
                pass

    def test_malformed_marker_still_blocks(self, wiki_dir, mock_db):
        """
        A malformed .sync-pending file still blocks generation.

        Even if the JSON can't be parsed, the marker's existence
        is enough to block.
        """
        marker = wiki_dir / ".sync-pending"
        marker.write_text("not valid json {{{", encoding="utf-8")

        exporter = WikiExporter(mock_db, output_dir=wiki_dir)

        with pytest.raises(RuntimeError, match="Deck edits pending"):
            exporter.generate_all()

    def test_empty_files_list_still_blocks(self, wiki_dir, mock_db):
        """
        A marker with empty files list still blocks generation.
        """
        marker = wiki_dir / ".sync-pending"
        data = {"machine": "deck", "timestamp": "2026-01-01T00:00:00", "files": []}
        marker.write_text(json.dumps(data), encoding="utf-8")

        exporter = WikiExporter(mock_db, output_dir=wiki_dir)

        with pytest.raises(RuntimeError, match="Deck edits pending"):
            exporter.generate_all()


# ==================== Sync Guard Tests ====================

class TestSyncGenerateOnlyGuard:
    """Tests for WikiSync generate_only guard."""

    def test_generate_only_refuses_with_marker(
        self, wiki_dir, mock_db, sync_pending_marker
    ):
        """
        sync_manuscript(generate_only=True) raises RuntimeError
        when .sync-pending exists.
        """
        sync = WikiSync(mock_db, wiki_dir=wiki_dir, logger=MagicMock())

        with pytest.raises(RuntimeError, match="Deck edits pending"):
            sync.sync_manuscript(generate_only=True)

    def test_generate_only_proceeds_without_marker(
        self, wiki_dir, mock_db
    ):
        """
        sync_manuscript(generate_only=True) proceeds when no marker.

        Mocks _regenerate to avoid actual generation.
        """
        sync = WikiSync(mock_db, wiki_dir=wiki_dir, logger=MagicMock())

        with patch.object(sync, "_regenerate") as mock_regen:
            result = sync.sync_manuscript(generate_only=True)
            mock_regen.assert_called_once()
            assert result.success


# ==================== Marker Clear Tests ====================

class TestMarkerClearAfterIngest:
    """Tests for .sync-pending marker removal after ingest."""

    def test_ingest_clears_marker(
        self, wiki_dir, mock_db, sync_pending_marker
    ):
        """
        _ingest() removes .sync-pending after successful commit.
        """
        sync = WikiSync(mock_db, wiki_dir=wiki_dir, logger=MagicMock())

        # Mock session_scope to simulate successful commit
        mock_session = MagicMock()
        mock_db.session_scope.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_db.session_scope.return_value.__exit__ = MagicMock(
            return_value=False
        )

        from dev.wiki.sync import SyncResult
        result = SyncResult()
        manuscript_dir = wiki_dir / "manuscript"

        sync._ingest(manuscript_dir, result)

        assert not sync_pending_marker.exists()

    def test_ingest_without_marker_no_error(self, wiki_dir, mock_db):
        """
        _ingest() works fine when no .sync-pending exists.
        """
        sync = WikiSync(mock_db, wiki_dir=wiki_dir, logger=MagicMock())

        mock_session = MagicMock()
        mock_db.session_scope.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_db.session_scope.return_value.__exit__ = MagicMock(
            return_value=False
        )

        from dev.wiki.sync import SyncResult
        result = SyncResult()
        manuscript_dir = wiki_dir / "manuscript"

        # Should not raise
        sync._ingest(manuscript_dir, result)

    def test_full_sync_clears_marker(
        self, wiki_dir, mock_db, sync_pending_marker
    ):
        """
        Full sync (ingest + generate) clears marker via ingest step.
        """
        sync = WikiSync(mock_db, wiki_dir=wiki_dir, logger=MagicMock())

        # Mock validator to pass, session for ingest, and regenerate
        with patch.object(sync, "_validate") as mock_validate, \
             patch.object(sync, "_regenerate"), \
             patch.object(sync.parser, "clear_cache"):

            mock_session = MagicMock()
            mock_db.session_scope.return_value.__enter__ = MagicMock(
                return_value=mock_session
            )
            mock_db.session_scope.return_value.__exit__ = MagicMock(
                return_value=False
            )

            sync.sync_manuscript()

        assert not sync_pending_marker.exists()

    def test_ingest_only_clears_marker(
        self, wiki_dir, mock_db, sync_pending_marker
    ):
        """
        sync_manuscript(ingest_only=True) clears the marker.
        """
        sync = WikiSync(mock_db, wiki_dir=wiki_dir, logger=MagicMock())

        with patch.object(sync, "_validate"):
            mock_session = MagicMock()
            mock_db.session_scope.return_value.__enter__ = MagicMock(
                return_value=mock_session
            )
            mock_db.session_scope.return_value.__exit__ = MagicMock(
                return_value=False
            )

            sync.sync_manuscript(ingest_only=True)

        assert not sync_pending_marker.exists()
