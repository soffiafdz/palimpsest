#!/usr/bin/env python3
"""
test_wiki_sync_roundtrip.py
---------------------------
Integration tests for the wiki sync round-trip cycle.

Tests the full workflow: generate → user edits wiki → sync → verify DB.
Covers validation gates, partial operations, and error propagation.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import re

# --- Third-party imports ---
import pytest

# --- Local imports ---
from dev.database.models.enums import ChapterStatus, ChapterType
from dev.database.models.manuscript import Chapter
from dev.wiki.exporter import WikiExporter
from dev.wiki.sync import WikiSync


class TestSyncRoundTrip:
    """Full generate → edit → sync → verify cycle."""

    def test_modify_chapter_type_roundtrip(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """
        Generate chapter page → change type in wiki → sync → verify DB.

        Steps:
            1. Generate wiki with exporter
            2. Read generated chapter file
            3. Replace type from 'Prose' to 'Vignette'
            4. Run sync
            5. Verify DB chapter type updated
        """
        # Step 1: Generate
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="manuscript")

        # Step 2: Read chapter file
        chapter_file = (
            wiki_output / "manuscript" / "chapters" / "espresso-and-silence.md"
        )
        assert chapter_file.is_file()
        content = chapter_file.read_text()

        # Step 3: Modify type from Prose to Vignette
        modified = content.replace(
            "**Type:** Prose",
            "**Type:** Vignette",
        )
        assert modified != content, "Expected to find **Type:** Prose in file"
        chapter_file.write_text(modified)

        # Step 4: Sync
        sync = WikiSync(test_db, wiki_dir=wiki_output)
        result = sync.sync_manuscript()

        assert result.success, f"Sync failed: {result.errors}"

        # Step 5: Verify DB
        with test_db.session_scope() as session:
            chapter = session.query(Chapter).filter(
                Chapter.title == "Espresso and Silence"
            ).first()
            assert chapter is not None
            assert chapter.type == ChapterType.VIGNETTE

    def test_modify_chapter_status_roundtrip(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """
        Modify chapter status and verify sync updates DB.
        """
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="manuscript")

        # Modify the revised chapter to final
        chapter_file = (
            wiki_output / "manuscript" / "chapters" / "november-nocturne.md"
        )
        content = chapter_file.read_text()
        modified = content.replace(
            "**Status:** Revised",
            "**Status:** Final",
        )
        chapter_file.write_text(modified)

        sync = WikiSync(test_db, wiki_dir=wiki_output)
        result = sync.sync_manuscript()
        assert result.success

        with test_db.session_scope() as session:
            chapter = session.query(Chapter).filter(
                Chapter.title == "November Nocturne"
            ).first()
            assert chapter.status == ChapterStatus.FINAL


class TestValidationGate:
    """Tests that validation blocks sync on errors."""

    def test_broken_wikilink_blocks_sync(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """
        Sync is blocked when a manuscript page has an unresolved wikilink.
        """
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="manuscript")

        # Inject a broken wikilink into a chapter file
        chapter_file = (
            wiki_output / "manuscript" / "chapters" / "espresso-and-silence.md"
        )
        content = chapter_file.read_text()
        content += "\n\nSee also [[Nonexistent Entity]]\n"
        chapter_file.write_text(content)

        sync = WikiSync(test_db, wiki_dir=wiki_output)
        result = sync.sync_manuscript()

        assert not result.success
        assert any("UNRESOLVED_WIKILINK" in err for err in result.errors)

    def test_warnings_do_not_block_sync(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """
        Warnings (like empty sections) should not block sync.
        """
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="manuscript")

        # Sync should succeed even if there are warnings
        sync = WikiSync(test_db, wiki_dir=wiki_output)
        result = sync.sync_manuscript()

        # Should succeed regardless of warnings
        assert result.success


class TestPartialOperations:
    """Tests for ingest_only and generate_only flags."""

    def test_ingest_only_skips_regeneration(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """ingest_only=True parses wiki → DB without regenerating."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="manuscript")

        sync = WikiSync(test_db, wiki_dir=wiki_output)
        result = sync.sync_manuscript(ingest_only=True)

        assert result.success
        assert result.files_ingested > 0
        assert result.files_generated == 0

    def test_generate_only_skips_ingestion(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """generate_only=True regenerates without parsing wiki files."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="manuscript")

        sync = WikiSync(test_db, wiki_dir=wiki_output)
        result = sync.sync_manuscript(generate_only=True)

        assert result.success
        assert result.files_ingested == 0

    def test_missing_manuscript_dir_returns_error(
        self, test_db, wiki_output
    ):
        """Sync returns error when manuscript directory doesn't exist."""
        sync = WikiSync(test_db, wiki_dir=wiki_output)
        result = sync.sync_manuscript()

        assert not result.success
        assert any("not found" in err for err in result.errors)


class TestSyncResult:
    """Tests for SyncResult reporting."""

    def test_sync_result_summary(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """SyncResult.summary() produces readable text."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="manuscript")

        sync = WikiSync(test_db, wiki_dir=wiki_output)
        result = sync.sync_manuscript()

        summary = result.summary()
        assert isinstance(summary, str)
        assert "Validated" in summary

    def test_sync_tracks_updates(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """Sync result tracks per-entity-type update counts."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="manuscript")

        sync = WikiSync(test_db, wiki_dir=wiki_output)
        result = sync.sync_manuscript()

        assert result.success
        assert "chapters" in result.updates
        assert "characters" in result.updates
        assert "scenes" in result.updates
