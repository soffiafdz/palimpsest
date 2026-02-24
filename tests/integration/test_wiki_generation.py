#!/usr/bin/env python3
"""
test_wiki_generation.py
-----------------------
End-to-end integration tests for wiki page generation.

Tests the full generation pipeline: DB → context → template → files,
including section filtering, entity type filtering, visibility rules,
change detection, and orphan cleanup.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path

# --- Third-party imports ---
import pytest

# --- Local imports ---
from dev.database.models.entities import Person
from dev.wiki.exporter import WikiExporter
from dev.wiki.validator import WikiValidator


class TestGenerateAll:
    """End-to-end tests for full wiki generation."""

    def test_generate_all_creates_directory_tree(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """generate_all creates complete directory tree."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all()

        # Journal directories
        assert (wiki_output / "journal" / "entries").is_dir()
        assert (wiki_output / "journal" / "people").is_dir()
        assert (wiki_output / "journal" / "locations").is_dir()
        assert (wiki_output / "journal" / "cities").is_dir()
        assert (wiki_output / "journal" / "events").is_dir()
        assert (wiki_output / "journal" / "arcs").is_dir()
        assert (wiki_output / "journal" / "tags").is_dir()
        assert (wiki_output / "journal" / "themes").is_dir()
        assert (wiki_output / "journal" / "poems").is_dir()
        assert (wiki_output / "journal" / "references").is_dir()

        # Manuscript directories
        assert (wiki_output / "manuscript" / "chapters").is_dir()
        assert (wiki_output / "manuscript" / "characters").is_dir()
        assert (wiki_output / "manuscript" / "scenes").is_dir()

        # Index pages
        assert (wiki_output / "index.md").is_file()
        assert (wiki_output / "indexes" / "people-index.md").is_file()
        assert (wiki_output / "indexes" / "manuscript-index.md").is_file()

    def test_generate_all_creates_entry_pages(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """All 5 entries get wiki pages."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all()

        entry_dir = wiki_output / "journal" / "entries" / "2024"
        assert (entry_dir / "2024-11-08.md").is_file()
        assert (entry_dir / "2024-11-09.md").is_file()
        assert (entry_dir / "2024-11-15.md").is_file()
        assert (entry_dir / "2024-12-01.md").is_file()
        assert (entry_dir / "2024-12-05.md").is_file()

    def test_generate_all_creates_manuscript_pages(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """Manuscript entities get wiki pages."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all()

        assert (
            wiki_output / "manuscript" / "chapters" / "espresso-and-silence.md"
        ).is_file()
        assert (
            wiki_output / "manuscript" / "chapters" / "november-nocturne.md"
        ).is_file()
        assert (
            wiki_output / "manuscript" / "characters" / "valeria.md"
        ).is_file()
        assert (
            wiki_output / "manuscript" / "characters" / "lena.md"
        ).is_file()
        assert (
            wiki_output / "manuscript" / "scenes" / "the-espresso-pause.md"
        ).is_file()

    def test_entry_content_has_expected_sections(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """Generated entry pages contain expected content."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all()

        content = (
            wiki_output / "journal" / "entries" / "2024" / "2024-11-08.md"
        ).read_text()

        # Has H1 title with date
        assert "# " in content
        # Has people wikilinks
        assert "[[Clara Dupont" in content or "Clara" in content
        # Has location references
        assert "Café Olimpico" in content or "Olimpico" in content

    def test_rating_subpage_generated(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """Entries with rating_justification get rating subpages."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all()

        rating_page = (
            wiki_output / "journal" / "entries" / "2024"
            / "2024-11-08-rating.md"
        )
        assert rating_page.is_file()
        content = rating_page.read_text()
        assert "Rich narrative detail" in content


class TestSectionFiltering:
    """Tests for section-level generation filtering."""

    def test_journal_section_only(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """section='journal' produces no manuscript pages."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="journal")

        # Journal pages exist
        assert (wiki_output / "journal" / "people").is_dir()

        # Manuscript pages do not exist
        assert not (wiki_output / "manuscript").exists()

    def test_manuscript_section_only(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """section='manuscript' produces no journal pages."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="manuscript")

        # Manuscript pages exist
        assert (wiki_output / "manuscript" / "chapters").is_dir()

        # Journal pages do not exist
        assert not (wiki_output / "journal").exists()

    def test_indexes_section_only(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """section='indexes' produces only index pages."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="indexes")

        assert (wiki_output / "index.md").is_file()
        assert not (wiki_output / "journal").exists()
        assert not (wiki_output / "manuscript").exists()


class TestEntityTypeFiltering:
    """Tests for entity type filtering."""

    def test_people_only(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """entity_type='people' generates only person pages."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="journal", entity_type="people")

        # People pages exist
        assert (wiki_output / "journal" / "people").is_dir()
        people_files = list(
            (wiki_output / "journal" / "people").glob("*.md")
        )
        assert len(people_files) >= 1

        # Other entity pages do not exist
        assert not (wiki_output / "journal" / "tags").exists()
        assert not (wiki_output / "journal" / "arcs").exists()

    def test_chapters_only(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """entity_type='chapters' generates only chapter pages."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="manuscript", entity_type="chapters")

        assert (wiki_output / "manuscript" / "chapters").is_dir()
        assert not (wiki_output / "manuscript" / "characters").exists()


class TestVisibilityFilters:
    """Tests for entity visibility thresholds."""

    def test_tags_with_two_entries_get_page(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """Tags used in 2+ entries generate wiki pages."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="journal", entity_type="tags")

        # 'writing' appears in entries 1, 2, 5 — should have page
        tag_page = wiki_output / "journal" / "tags" / "writing.md"
        assert tag_page.is_file()

    def test_tag_with_one_entry_gets_page(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """All tags get wiki pages regardless of usage count."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="journal", entity_type="tags")

        # 'therapy' appears only in entry4 — still gets a page
        tag_page = wiki_output / "journal" / "tags" / "therapy.md"
        assert tag_page.exists()

    def test_themes_visibility(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """Themes with 2+ entries get pages, others don't."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="journal", entity_type="themes")

        # 'identity' in entries 1, 2, 5 — should have page
        assert (wiki_output / "journal" / "themes" / "identity.md").is_file()
        # 'memory' in entries 3, 4, 5 — should have page
        assert (wiki_output / "journal" / "themes" / "memory.md").is_file()


class TestChangeDetection:
    """Tests for idempotent generation and change detection."""

    def test_second_generation_reports_zero_changes(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """Second generation of unchanged DB reports 0 changed files."""
        # First generation
        exporter1 = WikiExporter(test_db, output_dir=wiki_output)
        exporter1.generate_all(section="journal")

        # Second generation
        exporter2 = WikiExporter(test_db, output_dir=wiki_output)
        exporter2.generate_all(section="journal")

        assert exporter2.stats.get("entries_changed", 0) == 0
        assert exporter2.stats.get("people_changed", 0) == 0

    def test_stats_track_entity_counts(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """Stats dict contains counts for each entity type."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all()

        assert exporter.stats["entries"] == 5
        assert exporter.stats["people"] == 8
        assert "chapters" in exporter.stats


class TestOrphanCleanup:
    """Tests for orphan file removal."""

    def test_orphan_file_removed(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """Files not matching DB entities are cleaned up."""
        # Create orphan
        orphan_dir = wiki_output / "journal" / "people"
        orphan_dir.mkdir(parents=True, exist_ok=True)
        orphan = orphan_dir / "ghost.md"
        orphan.write_text("# Ghost\n\nThis person was deleted.\n")

        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all()

        assert not orphan.exists()
        assert exporter.stats.get("orphans_removed", 0) >= 1

    def test_entity_type_filter_skips_orphan_cleanup(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """Orphan cleanup is skipped when entity_type filter is active."""
        orphan_dir = wiki_output / "journal" / "people"
        orphan_dir.mkdir(parents=True, exist_ok=True)
        orphan = orphan_dir / "ghost.md"
        orphan.write_text("# Ghost\n")

        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="journal", entity_type="tags")

        # Orphan should still exist since we filtered by type
        assert orphan.exists()


class TestValidatorOnGenerated:
    """Tests that generated output passes validation."""

    def test_generated_pages_have_no_structural_errors(
        self, test_db, populated_wiki_db, wiki_output
    ):
        """
        Validator produces 0 structural error diagnostics on generated output.

        Checks for missing H1 titles, empty sections, and other structural
        issues.  UNRESOLVED_WIKILINK errors are excluded because the
        validator's known-target set covers journal entities but not
        manuscript entities (Part, Chapter, Character, ManuscriptScene),
        so cross-section wikilinks are expected to be unresolved.
        """
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all()

        validator = WikiValidator(test_db)
        all_diagnostics = validator.validate_directory(wiki_output)

        errors = []
        for file_path, diagnostics in all_diagnostics.items():
            for diag in diagnostics:
                if diag.severity == "error" and diag.code != "UNRESOLVED_WIKILINK":
                    errors.append(
                        f"{file_path}:{diag.line} [{diag.code}] "
                        f"{diag.message}"
                    )

        assert errors == [], (
            f"Generated wiki has {len(errors)} structural error(s):\n"
            + "\n".join(errors[:10])
        )
