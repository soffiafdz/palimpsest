#!/usr/bin/env python3
"""
test_sync.py
------------
Tests for the WikiSync manuscript synchronization orchestrator.

Validates the full sync cycle (validate, ingest, regenerate) and
individual operations against a test database with real entities
and temporary wiki file structures.

Key Test Areas:
    - SyncResult data tracking and success semantics
    - Validation gate (errors block ingestion)
    - YAML-based ingestion via MetadataImporter
    - Full and partial sync cycle orchestration
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from unittest.mock import MagicMock, patch

# --- Third-party imports ---
import pytest

# --- Local imports ---
from dev.database.models.analysis import Arc
from dev.database.models.creative import Poem, ReferenceSource
from dev.database.models.enums import ReferenceType
from dev.wiki.sync import SyncResult, WikiSync


# ==================== Fixtures ====================

@pytest.fixture
def mock_logger():
    """
    Create a mock logger compatible with WikiSync.

    WikiSync calls self.logger.info() which NullLogger does not provide.
    A MagicMock auto-creates any attribute accessed on it.
    """
    return MagicMock()


@pytest.fixture
def sync_wiki_dir(tmp_path):
    """
    Create a minimal wiki directory structure for sync tests.

    Returns:
        Path to the temporary wiki directory with manuscript subdirs
    """
    wiki_dir = tmp_path / "wiki"
    manuscript_dir = wiki_dir / "manuscript"
    (manuscript_dir / "chapters").mkdir(parents=True)
    (manuscript_dir / "characters").mkdir(parents=True)
    (manuscript_dir / "scenes").mkdir(parents=True)
    return wiki_dir


@pytest.fixture
def sync_instance(test_db, sync_wiki_dir, mock_logger):
    """
    Create a WikiSync instance wired to the test database and temp wiki dir.

    Returns:
        Tuple of (WikiSync instance, wiki_dir)
    """
    sync = WikiSync(test_db, wiki_dir=sync_wiki_dir, logger=mock_logger)
    return sync, sync_wiki_dir


# ==================== TestSyncResult ====================

class TestSyncResult:
    """Tests for the SyncResult data structure."""

    def test_empty_result_success(self):
        """An empty SyncResult with no errors reports success=True."""
        result = SyncResult()
        assert result.success is True
        assert result.files_validated == 0
        assert result.files_ingested == 0
        assert result.files_generated == 0
        assert result.files_changed == 0

    def test_result_with_errors_not_success(self):
        """A SyncResult with errors reports success=False."""
        result = SyncResult()
        result.errors.append("Something went wrong")
        assert result.success is False

    def test_summary_includes_stats(self):
        """Summary includes validated, ingested, generated, and error counts."""
        result = SyncResult()
        result.files_validated = 5
        result.files_ingested = 3
        result.files_generated = 10
        result.files_changed = 2
        result.updates["chapters"] = 2
        result.updates["characters"] = 1
        result.warnings.append("minor issue")
        result.errors.append("critical issue")

        summary = result.summary()
        assert "Validated: 5 files" in summary
        assert "Ingested: 3 files" in summary
        assert "chapters: 2 updated" in summary
        assert "characters: 1 updated" in summary
        assert "Generated: 10 files (2 changed)" in summary
        assert "Warnings: 1" in summary
        assert "Errors: 1" in summary
        assert "critical issue" in summary

    def test_updates_dict_tracks_entity_types(self):
        """Updates dict has keys for chapters, characters, and scenes."""
        result = SyncResult()
        assert "chapters" in result.updates
        assert "characters" in result.updates
        assert "scenes" in result.updates
        assert all(v == 0 for v in result.updates.values())

        result.updates["chapters"] = 3
        result.updates["scenes"] = 7
        assert result.updates["chapters"] == 3
        assert result.updates["scenes"] == 7


# ==================== TestSyncValidation ====================

class TestSyncValidation:
    """Tests for the validation gate in the sync cycle."""

    def test_validation_passes_for_valid_files(
        self, test_db, db_session, tmp_path, mock_logger
    ):
        """Manuscript files with only resolvable wikilinks pass validation.

        The WikiValidator resolves wikilinks against Person, Location,
        Arc, Tag, Theme, Poem, ReferenceSource, and Entry names. It does
        not resolve Character, Chapter, or Part names. This test uses
        only entity types the validator knows about.
        """
        wiki_dir = tmp_path / "validwiki"
        manuscript_dir = wiki_dir / "manuscript" / "chapters"
        manuscript_dir.mkdir(parents=True)

        # Create DB entities the validator can resolve
        arc = Arc(name="The Long Wanting")
        poem = Poem(title="The Loop")
        ref = ReferenceSource(
            title="Nocturnes", author="Ishiguro", type=ReferenceType.BOOK,
        )
        db_session.add_all([arc, poem, ref])
        db_session.commit()

        # Write a chapter file with only resolvable wikilinks
        valid_md = (
            "# Valid Chapter\n\n"
            "**Type:** Prose · **Status:** Draft\n"
            "0 scenes\n\n"
            "---\n\n"
            "## Arcs\n\n"
            "- [[The Long Wanting]]\n\n"
            "## Poems\n\n"
            "- [[The Loop]]\n\n"
            "## References\n\n"
            "- [[Nocturnes]] *(thematic)*\n"
        )
        (manuscript_dir / "valid-chapter.md").write_text(valid_md)

        sync = WikiSync(test_db, wiki_dir=wiki_dir, logger=mock_logger)
        result = SyncResult()
        sync._validate(wiki_dir / "manuscript", result)

        assert result.success is True
        assert result.files_validated == 1

    def test_validation_fails_for_unresolved_wikilinks(
        self, test_db, tmp_path, mock_logger
    ):
        """Files with unresolved wikilinks produce validation errors."""
        wiki_dir = tmp_path / "badwiki"
        manuscript_dir = wiki_dir / "manuscript" / "chapters"
        manuscript_dir.mkdir(parents=True)

        bad_md = (
            "# Broken Chapter\n\n"
            "**Type:** Prose · **Status:** Draft\n\n"
            "## Characters\n\n"
            "- [[Nonexistent Character]]\n"
        )
        (manuscript_dir / "broken.md").write_text(bad_md)

        sync = WikiSync(test_db, wiki_dir=wiki_dir, logger=mock_logger)
        result = SyncResult()
        sync._validate(wiki_dir / "manuscript", result)

        assert result.success is False
        assert any("Nonexistent Character" in e for e in result.errors)

    def test_missing_manuscript_dir_returns_error(
        self, test_db, tmp_path, mock_logger
    ):
        """Sync with nonexistent manuscript directory returns error."""
        sync = WikiSync(test_db, wiki_dir=tmp_path, logger=mock_logger)
        result = sync.sync_manuscript()

        assert result.success is False
        assert any("Manuscript directory not found" in e for e in result.errors)


# ==================== TestSyncIngestion ====================

class TestSyncIngestion:
    """Tests for YAML metadata ingestion via MetadataImporter.

    The sync orchestrator delegates to MetadataImporter for each
    manuscript entity type. These tests verify the coordination
    logic, not the importer itself (tested in test_metadata.py).
    """

    def test_ingest_calls_importer_for_all_types(self, sync_instance):
        """Ingestion calls MetadataImporter.import_all for chapters, characters, scenes."""
        sync, wiki_dir = sync_instance
        result = SyncResult()

        mock_stats = {"imported": 2, "errors": 0}
        with patch(
            "dev.wiki.metadata.MetadataImporter"
        ) as MockImporter:
            mock_importer = MockImporter.return_value
            mock_importer.import_all.return_value = mock_stats
            sync._ingest(result)

        # Should be called once for each entity type
        calls = mock_importer.import_all.call_args_list
        assert len(calls) == 3
        called_types = [c.kwargs.get("entity_type") for c in calls]
        assert "chapters" in called_types
        assert "characters" in called_types
        assert "scenes" in called_types

    def test_ingest_accumulates_stats(self, sync_instance):
        """Ingestion accumulates file counts from importer stats."""
        sync, wiki_dir = sync_instance
        result = SyncResult()

        with patch(
            "dev.wiki.metadata.MetadataImporter"
        ) as MockImporter:
            mock_importer = MockImporter.return_value
            mock_importer.import_all.side_effect = [
                {"imported": 3, "errors": 0},  # chapters
                {"imported": 2, "errors": 0},  # characters
                {"imported": 5, "errors": 0},  # scenes
            ]
            sync._ingest(result)

        assert result.files_ingested == 10
        assert result.updates["chapters"] == 3
        assert result.updates["characters"] == 2
        assert result.updates["scenes"] == 5

    def test_ingest_reports_import_errors_as_warnings(self, sync_instance):
        """Import errors within a type are reported as warnings."""
        sync, wiki_dir = sync_instance
        result = SyncResult()

        with patch(
            "dev.wiki.metadata.MetadataImporter"
        ) as MockImporter:
            mock_importer = MockImporter.return_value
            mock_importer.import_all.side_effect = [
                {"imported": 1, "errors": 2},  # chapters with errors
                {"imported": 1, "errors": 0},  # characters
                {"imported": 1, "errors": 0},  # scenes
            ]
            sync._ingest(result)

        assert result.success is True  # warnings don't block
        assert any("chapters" in w and "2 import errors" in w for w in result.warnings)

    def test_ingest_exception_becomes_error(self, sync_instance):
        """An exception during import becomes a sync error."""
        sync, wiki_dir = sync_instance
        result = SyncResult()

        with patch(
            "dev.wiki.metadata.MetadataImporter"
        ) as MockImporter:
            mock_importer = MockImporter.return_value
            mock_importer.import_all.side_effect = [
                RuntimeError("DB connection lost"),  # chapters fails
                {"imported": 1, "errors": 0},  # characters OK
                {"imported": 1, "errors": 0},  # scenes OK
            ]
            sync._ingest(result)

        assert any("Failed to import chapters" in e for e in result.errors)
        # Other types still imported
        assert result.files_ingested == 2

    def test_ingest_clears_sync_pending_marker(self, sync_instance):
        """Successful ingest clears the .sync-pending marker file."""
        sync, wiki_dir = sync_instance
        marker = wiki_dir / ".sync-pending"
        marker.write_text("pending")
        result = SyncResult()

        with patch(
            "dev.wiki.metadata.MetadataImporter"
        ) as MockImporter:
            mock_importer = MockImporter.return_value
            mock_importer.import_all.return_value = {"imported": 0, "errors": 0}
            sync._ingest(result)

        assert not marker.exists()


# ==================== TestSyncCycle ====================

class TestSyncCycle:
    """Tests for the full and partial sync cycle orchestration."""

    def test_full_sync_runs_validate_ingest_regenerate(
        self, sync_instance
    ):
        """Full sync runs all three stages: validate, ingest, regenerate."""
        sync, wiki_dir = sync_instance

        with patch.object(
            sync.validator, "validate_directory", return_value={}
        ), patch.object(sync, "_ingest") as mock_ingest, \
             patch.object(sync, "_regenerate") as mock_regen:
            result = sync.sync_manuscript()

        assert result.files_validated == 0  # mock returns empty dict
        mock_ingest.assert_called_once()
        mock_regen.assert_called_once()

    def test_ingest_only_skips_regeneration(self, sync_instance):
        """Ingest-only mode skips the regeneration step."""
        sync, wiki_dir = sync_instance

        with patch.object(
            sync.validator, "validate_directory", return_value={}
        ), patch.object(sync, "_ingest") as mock_ingest, \
             patch.object(sync, "_regenerate") as mock_regen:
            result = sync.sync_manuscript(ingest_only=True)

        mock_ingest.assert_called_once()
        mock_regen.assert_not_called()

    def test_generate_only_skips_validation_and_ingestion(
        self, sync_instance
    ):
        """Generate-only mode skips validation and ingestion entirely."""
        sync, wiki_dir = sync_instance

        with patch.object(sync, "_validate") as mock_validate, \
             patch.object(sync, "_ingest") as mock_ingest, \
             patch.object(sync, "_regenerate") as mock_regen:
            result = sync.sync_manuscript(generate_only=True)

        mock_validate.assert_not_called()
        mock_ingest.assert_not_called()
        mock_regen.assert_called_once()

    def test_validation_errors_block_ingestion(self, sync_instance):
        """Validation errors prevent the ingestion step from running."""
        sync, wiki_dir = sync_instance

        # Write a file with an unresolved wikilink to trigger error
        bad_file = wiki_dir / "manuscript" / "chapters" / "invalid.md"
        bad_file.write_text(
            "# Invalid Chapter\n\n"
            "**Type:** Prose · **Status:** Draft\n\n"
            "## Characters\n\n"
            "- [[Ghost Person Who Does Not Exist]]\n"
        )

        with patch.object(sync, "_ingest") as mock_ingest:
            result = sync.sync_manuscript()

        assert result.success is False
        mock_ingest.assert_not_called()
