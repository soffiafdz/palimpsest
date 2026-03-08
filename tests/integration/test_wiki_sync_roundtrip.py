#!/usr/bin/env python3
"""
test_wiki_sync_roundtrip.py
---------------------------
Integration tests for the wiki sync round-trip cycle.

Tests the full workflow: YAML export → user edits YAML → import → verify DB.
Covers validation gates, partial operations, and error propagation.
"""
# --- Annotations ---
from __future__ import annotations

# --- Third-party imports ---
import pytest

# --- Local imports ---
from dev.database.models.enums import ChapterStatus, ChapterType
from dev.database.models.manuscript import Chapter
from dev.wiki.exporter import WikiExporter
from dev.wiki.metadata import MetadataExporter, MetadataImporter
from dev.wiki.sync import WikiSync


class TestSyncRoundTrip:
    """Full YAML export → edit → import → verify cycle."""

    def test_modify_chapter_type_roundtrip(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """
        Export chapter YAML → change type → import → verify DB.

        Steps:
            1. Export chapter YAML with MetadataExporter
            2. Read and modify type from 'prose' to 'vignette'
            3. Import modified YAML with MetadataImporter
            4. Verify DB chapter type updated
        """
        yaml_dir = wiki_output / "metadata"

        # Step 1: Export chapter YAML
        exporter = MetadataExporter(test_db, output_dir=yaml_dir)
        exporter.export_all(entity_type="chapters")

        # Step 2: Find and edit the chapter YAML
        chapter_yaml = (
            yaml_dir / "manuscript" / "chapters" / "espresso-and-silence.yaml"
        )
        assert chapter_yaml.is_file()
        content = chapter_yaml.read_text()

        # Step 3: Modify type from prose to vignette
        modified = content.replace("type: prose", "type: vignette")
        assert modified != content, "Expected to find 'type: prose' in YAML"
        chapter_yaml.write_text(modified)

        # Step 4: Import
        importer = MetadataImporter(test_db, input_dir=yaml_dir)
        importer.import_all(entity_type="chapters")

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
        Modify chapter status via YAML and verify import updates DB.
        """
        yaml_dir = wiki_output / "metadata"

        exporter = MetadataExporter(test_db, output_dir=yaml_dir)
        exporter.export_all(entity_type="chapters")

        chapter_yaml = (
            yaml_dir / "manuscript" / "chapters" / "november-nocturne.yaml"
        )
        content = chapter_yaml.read_text()
        modified = content.replace("status: revised", "status: final")
        assert modified != content, "Expected to find 'status: revised' in YAML"
        chapter_yaml.write_text(modified)

        importer = MetadataImporter(test_db, input_dir=yaml_dir)
        importer.import_all(entity_type="chapters")

        with test_db.session_scope() as session:
            chapter = session.query(Chapter).filter(
                Chapter.title == "November Nocturne"
            ).first()
            assert chapter is not None
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
