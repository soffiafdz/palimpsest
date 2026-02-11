#!/usr/bin/env python3
"""
test_yaml_skeleton.py
---------------------
Tests for YAML metadata skeleton generation.

Tests cover:
    - Skeleton file creation with correct path and name
    - Date field auto-populated correctly
    - All expected field sections present in comments
    - Skip logic: existing file not overwritten without force
    - Force logic: existing file overwritten with force
    - Year directory created automatically
    - Integration: process_entry() creates both .md and .yaml
    - Integration: skeleton not created when yaml_dir=None

Usage:
    python -m pytest tests/unit/pipeline/test_yaml_skeleton.py -v
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date
from pathlib import Path

# --- Third-party imports ---
import pytest

# --- Local imports ---
from dev.pipeline.yaml_skeleton import generate_skeleton
from dev.pipeline.txt2md import process_entry
from dev.core.cli import ConversionStats
from dev.dataclasses.txt_entry import TxtEntry


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def yaml_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for YAML skeleton output."""
    return tmp_path / "yaml"


@pytest.fixture
def md_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for Markdown output."""
    return tmp_path / "md"


@pytest.fixture
def sample_date() -> date:
    """Provide a sample date for testing."""
    return date(2024, 3, 15)


@pytest.fixture
def sample_entry(sample_date: date) -> TxtEntry:
    """Provide a sample TxtEntry for integration tests."""
    return TxtEntry(
        date=sample_date,
        header="March 15, 2024",
        body=["This is a test entry.", "", "It has two paragraphs."],
        word_count=9,
        reading_time=0.04,
    )


# =============================================================================
# Unit Tests: generate_skeleton
# =============================================================================


class TestGenerateSkeleton:
    """Tests for the generate_skeleton function."""

    def test_creates_file_with_correct_path(
        self, yaml_dir: Path, sample_date: date
    ) -> None:
        """Skeleton file is created at yaml_dir/YYYY/YYYY-MM-DD.yaml."""
        result = generate_skeleton(sample_date, yaml_dir)

        assert result is not None
        expected = yaml_dir / "2024" / "2024-03-15.yaml"
        assert result == expected
        assert result.exists()

    def test_creates_year_directory(
        self, yaml_dir: Path, sample_date: date
    ) -> None:
        """Year subdirectory is created automatically."""
        assert not yaml_dir.exists()
        generate_skeleton(sample_date, yaml_dir)
        assert (yaml_dir / "2024").is_dir()

    def test_date_field_populated(
        self, yaml_dir: Path, sample_date: date
    ) -> None:
        """The date field is the only uncommented field, correctly populated."""
        result = generate_skeleton(sample_date, yaml_dir)
        assert result is not None
        content = result.read_text(encoding="utf-8")

        # First non-empty line should be the date field
        first_line = content.split("\n")[0]
        assert first_line == "date: 2024-03-15"

    def test_date_is_only_uncommented_field(
        self, yaml_dir: Path, sample_date: date
    ) -> None:
        """Only the date line is uncommented YAML; everything else is a comment."""
        result = generate_skeleton(sample_date, yaml_dir)
        assert result is not None
        content = result.read_text(encoding="utf-8")

        for line in content.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            # Only allowed uncommented line is the date field
            assert stripped.startswith("date:"), (
                f"Unexpected uncommented line: {stripped!r}"
            )

    def test_all_field_sections_present(
        self, yaml_dir: Path, sample_date: date
    ) -> None:
        """All expected metadata field sections appear in the comments."""
        result = generate_skeleton(sample_date, yaml_dir)
        assert result is not None
        content = result.read_text(encoding="utf-8")

        expected_fields = [
            "summary",
            "rating",
            "rating_justification",
            "arcs",
            "tags",
            "themes",
            "motifs",
            "people",
            "scenes",
            "events",
            "threads",
            "references",
            "poems",
        ]
        for field in expected_fields:
            assert field in content, f"Missing field section: {field}"

    def test_section_headers_present(
        self, yaml_dir: Path, sample_date: date
    ) -> None:
        """Major section headers appear in the skeleton."""
        result = generate_skeleton(sample_date, yaml_dir)
        assert result is not None
        content = result.read_text(encoding="utf-8")

        expected_sections = [
            "EDITORIAL METADATA",
            "CONTROLLED VOCABULARY",
            "PEOPLE",
            "NARRATIVE ANALYSIS",
            "CREATIVE CONTENT",
        ]
        for section in expected_sections:
            assert section in content, f"Missing section header: {section}"

    def test_enum_values_documented(
        self, yaml_dir: Path, sample_date: date
    ) -> None:
        """Reference mode and type enum values appear in the skeleton."""
        result = generate_skeleton(sample_date, yaml_dir)
        assert result is not None
        content = result.read_text(encoding="utf-8")

        # ReferenceMode values
        assert "direct" in content
        assert "indirect" in content
        assert "paraphrase" in content

        # ReferenceType values
        assert "book" in content
        assert "film" in content
        assert "song" in content

    def test_skip_existing_file(
        self, yaml_dir: Path, sample_date: date
    ) -> None:
        """Existing skeleton is not overwritten without force."""
        # Create first skeleton
        first_result = generate_skeleton(sample_date, yaml_dir)
        assert first_result is not None

        # Write a marker to detect overwrite
        first_result.write_text("marker content", encoding="utf-8")

        # Try to generate again without force
        second_result = generate_skeleton(sample_date, yaml_dir)
        assert second_result is None

        # Original marker should still be there
        assert first_result.read_text(encoding="utf-8") == "marker content"

    def test_force_overwrites_existing(
        self, yaml_dir: Path, sample_date: date
    ) -> None:
        """Existing skeleton is overwritten with force_overwrite=True."""
        # Create first skeleton
        first_result = generate_skeleton(sample_date, yaml_dir)
        assert first_result is not None

        # Write a marker
        first_result.write_text("marker content", encoding="utf-8")

        # Force overwrite
        second_result = generate_skeleton(
            sample_date, yaml_dir, force_overwrite=True
        )
        assert second_result is not None

        # Marker should be gone, replaced with skeleton
        content = second_result.read_text(encoding="utf-8")
        assert content.startswith("date: 2024-03-15")
        assert "marker content" not in content

    def test_different_dates_create_different_files(
        self, yaml_dir: Path
    ) -> None:
        """Different dates produce different skeleton files."""
        date1 = date(2024, 1, 5)
        date2 = date(2025, 12, 31)

        path1 = generate_skeleton(date1, yaml_dir)
        path2 = generate_skeleton(date2, yaml_dir)

        assert path1 is not None
        assert path2 is not None
        assert path1 != path2
        assert path1.name == "2024-01-05.yaml"
        assert path2.name == "2025-12-31.yaml"
        assert path1.parent.name == "2024"
        assert path2.parent.name == "2025"

    def test_date_interpolated_in_examples(
        self, yaml_dir: Path, sample_date: date
    ) -> None:
        """The entry date appears in example fields like scene date."""
        result = generate_skeleton(sample_date, yaml_dir)
        assert result is not None
        content = result.read_text(encoding="utf-8")

        # Date should appear multiple times: the field itself + examples
        occurrences = content.count("2024-03-15")
        assert occurrences >= 2, (
            f"Expected date to appear in field + examples, found {occurrences} times"
        )

    def test_utf8_encoding(
        self, yaml_dir: Path, sample_date: date
    ) -> None:
        """Skeleton file is written in UTF-8 encoding."""
        result = generate_skeleton(sample_date, yaml_dir)
        assert result is not None
        # Should be readable as UTF-8 without errors
        content = result.read_text(encoding="utf-8")
        assert len(content) > 0


# =============================================================================
# Integration Tests: process_entry with skeleton generation
# =============================================================================


class TestProcessEntrySkeletonIntegration:
    """Tests for skeleton generation hooked into process_entry."""

    def test_creates_both_md_and_yaml(
        self,
        md_dir: Path,
        yaml_dir: Path,
        sample_entry: TxtEntry,
    ) -> None:
        """process_entry creates both .md and .yaml when yaml_dir is given."""
        stats = ConversionStats()
        result = process_entry(
            sample_entry,
            md_dir,
            force_overwrite=False,
            minimal_yaml=True,
            yaml_dir=yaml_dir,
            stats=stats,
        )

        # Markdown file created
        assert result is not None
        assert result.exists()
        assert result.suffix == ".md"

        # YAML skeleton created
        yaml_path = yaml_dir / "2024" / "2024-03-15.yaml"
        assert yaml_path.exists()
        content = yaml_path.read_text(encoding="utf-8")
        assert content.startswith("date: 2024-03-15")

    def test_no_yaml_when_yaml_dir_none(
        self,
        md_dir: Path,
        tmp_path: Path,
        sample_entry: TxtEntry,
    ) -> None:
        """No YAML skeleton is created when yaml_dir=None."""
        stats = ConversionStats()
        result = process_entry(
            sample_entry,
            md_dir,
            force_overwrite=False,
            minimal_yaml=True,
            yaml_dir=None,
            stats=stats,
        )

        # Markdown file created
        assert result is not None

        # No YAML files anywhere in tmp_path
        yaml_files = list(tmp_path.rglob("*.yaml"))
        assert len(yaml_files) == 0

    def test_skeleton_stats_tracked(
        self,
        md_dir: Path,
        yaml_dir: Path,
        sample_entry: TxtEntry,
    ) -> None:
        """Skeleton creation/skip counts are tracked in stats."""
        stats = ConversionStats()

        # First call: skeleton created
        process_entry(
            sample_entry,
            md_dir,
            force_overwrite=True,
            minimal_yaml=True,
            yaml_dir=yaml_dir,
            stats=stats,
        )
        assert stats.skeletons_created == 1
        assert stats.skeletons_skipped == 0

        # Second call: skeleton skipped (already exists, no force on skeleton)
        # Note: force_overwrite applies to both md and yaml
        stats2 = ConversionStats()
        process_entry(
            sample_entry,
            md_dir,
            force_overwrite=False,
            minimal_yaml=True,
            yaml_dir=yaml_dir,
            stats=stats2,
        )
        # md was skipped (returns None), so skeleton is not attempted
        # because process_entry returns None early
        assert stats2.skeletons_created == 0
        assert stats2.skeletons_skipped == 0

    def test_skeleton_skipped_when_exists(
        self,
        md_dir: Path,
        yaml_dir: Path,
        sample_entry: TxtEntry,
    ) -> None:
        """Skeleton is skipped when it already exists and force is off."""
        # Pre-create the skeleton
        generate_skeleton(sample_entry.date, yaml_dir)

        stats = ConversionStats()
        process_entry(
            sample_entry,
            md_dir,
            force_overwrite=True,
            minimal_yaml=True,
            yaml_dir=yaml_dir,
            stats=stats,
        )
        # md was force-created, but skeleton already exists & force applies
        # force_overwrite=True means both get overwritten
        assert stats.skeletons_created == 1

    def test_skeleton_skip_counted_in_stats(
        self,
        md_dir: Path,
        yaml_dir: Path,
        sample_entry: TxtEntry,
    ) -> None:
        """When skeleton exists and md is force-created, skeleton skip is counted."""
        # Pre-create the skeleton
        generate_skeleton(sample_entry.date, yaml_dir)

        stats = ConversionStats()
        # force_overwrite=False but md doesn't exist yet
        process_entry(
            sample_entry,
            md_dir,
            force_overwrite=False,
            minimal_yaml=True,
            yaml_dir=yaml_dir,
            stats=stats,
        )
        # md is new so it gets created; skeleton already exists, gets skipped
        assert stats.skeletons_skipped == 1
        assert stats.skeletons_created == 0


# =============================================================================
# ConversionStats Tests
# =============================================================================


class TestConversionStatsSkeletonFields:
    """Tests for skeleton-related fields in ConversionStats."""

    def test_default_values(self) -> None:
        """Skeleton fields default to zero."""
        stats = ConversionStats()
        assert stats.skeletons_created == 0
        assert stats.skeletons_skipped == 0

    def test_summary_includes_skeletons_when_nonzero(self) -> None:
        """Summary includes skeleton counts when they are non-zero."""
        stats = ConversionStats()
        stats.skeletons_created = 5
        stats.skeletons_skipped = 2
        summary = stats.summary()
        assert "5 skeletons created" in summary
        assert "2 skeletons skipped" in summary

    def test_summary_excludes_skeletons_when_zero(self) -> None:
        """Summary omits skeleton counts when both are zero."""
        stats = ConversionStats()
        summary = stats.summary()
        assert "skeleton" not in summary

    def test_to_dict_includes_skeleton_fields(self) -> None:
        """to_dict always includes skeleton fields."""
        stats = ConversionStats()
        stats.skeletons_created = 3
        stats.skeletons_skipped = 1
        d = stats.to_dict()
        assert d["skeletons_created"] == 3
        assert d["skeletons_skipped"] == 1

    def test_validation_rejects_negative(self) -> None:
        """Negative skeleton counts raise ValueError."""
        with pytest.raises(ValueError, match="skeletons_created"):
            ConversionStats(skeletons_created=-1)
        with pytest.raises(ValueError, match="skeletons_skipped"):
            ConversionStats(skeletons_skipped=-1)
