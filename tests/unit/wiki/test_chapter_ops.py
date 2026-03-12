#!/usr/bin/env python3
"""
test_chapter_ops.py
-------------------
Tests for chapter reorder operations (renumber, move, remove-number).

Tests use a temporary directory with chapter YAML files to verify
correct shift semantics, gap-filling, and validation.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from dev.wiki.chapter_ops import ChapterReorder


@pytest.fixture
def chapters_dir(tmp_path: Path) -> Path:
    """Create a metadata directory with sample chapter YAMLs."""
    ch_dir = tmp_path / "manuscript" / "chapters"
    ch_dir.mkdir(parents=True)

    chapters = [
        {"title": "Alpha", "part": "Part 1", "number": 1, "type": "prose", "status": "draft"},
        {"title": "Beta", "part": "Part 1", "number": 2, "type": "prose", "status": "draft"},
        {"title": "Gamma", "part": "Part 1", "number": 3, "type": "prose", "status": "draft"},
        {"title": "Delta", "part": "Part 1", "number": 4, "type": "prose", "status": "draft"},
        {"title": "Epsilon", "part": "Part 2", "number": 1, "type": "prose", "status": "draft"},
        {"title": "Zeta", "part": "Part 2", "number": 2, "type": "prose", "status": "draft"},
        {"title": "Eta", "part": "Part 2", "number": 3, "type": "prose", "status": "draft"},
        {"title": "Floating", "type": "vignette", "status": "draft"},
    ]

    for ch in chapters:
        slug = ch["title"].lower()
        path = ch_dir / f"{slug}.yaml"
        with open(path, "w") as f:
            yaml.dump(ch, f, default_flow_style=False, sort_keys=False)

    return tmp_path


@pytest.fixture
def reorder(chapters_dir: Path) -> ChapterReorder:
    """Create a ChapterReorder pointing at the test directory."""
    return ChapterReorder(chapters_dir)


def _read_chapter(chapters_dir: Path, slug: str) -> dict:
    """Read a chapter YAML and return its data."""
    path = chapters_dir / "manuscript" / "chapters" / f"{slug}.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


# =========================================================================
# Renumber tests
# =========================================================================


class TestRenumber:
    """Tests for renumber operation."""

    def test_move_down(self, reorder: ChapterReorder, chapters_dir: Path) -> None:
        """Moving ch2→4 shifts 3,4 down by -1."""
        report = reorder.renumber("Beta", 4, dry_run=False)
        assert report.ok
        assert len(report.changes) == 3

        assert _read_chapter(chapters_dir, "beta")["number"] == 4
        assert _read_chapter(chapters_dir, "gamma")["number"] == 2
        assert _read_chapter(chapters_dir, "delta")["number"] == 3
        # Alpha unchanged
        assert _read_chapter(chapters_dir, "alpha")["number"] == 1

    def test_move_up(self, reorder: ChapterReorder, chapters_dir: Path) -> None:
        """Moving ch4→2 shifts 2,3 up by +1."""
        report = reorder.renumber("Delta", 2, dry_run=False)
        assert report.ok
        assert len(report.changes) == 3

        assert _read_chapter(chapters_dir, "delta")["number"] == 2
        assert _read_chapter(chapters_dir, "beta")["number"] == 3
        assert _read_chapter(chapters_dir, "gamma")["number"] == 4
        assert _read_chapter(chapters_dir, "alpha")["number"] == 1

    def test_no_op_same_number(self, reorder: ChapterReorder) -> None:
        """Renumbering to the same number is a no-op."""
        report = reorder.renumber("Beta", 2, dry_run=False)
        assert report.ok
        assert len(report.changes) == 0

    def test_dry_run_no_write(self, reorder: ChapterReorder, chapters_dir: Path) -> None:
        """Dry run computes changes but doesn't modify files."""
        report = reorder.renumber("Beta", 4, dry_run=True)
        assert report.ok
        assert report.dry_run
        assert len(report.changes) == 3
        # Files unchanged
        assert _read_chapter(chapters_dir, "beta")["number"] == 2

    def test_cross_part_isolation(self, reorder: ChapterReorder, chapters_dir: Path) -> None:
        """Renumbering in Part 1 doesn't affect Part 2."""
        reorder.renumber("Alpha", 4, dry_run=False)
        assert _read_chapter(chapters_dir, "epsilon")["number"] == 1
        assert _read_chapter(chapters_dir, "zeta")["number"] == 2
        assert _read_chapter(chapters_dir, "eta")["number"] == 3

    def test_error_chapter_not_found(self, reorder: ChapterReorder) -> None:
        """Error when chapter title doesn't exist."""
        report = reorder.renumber("Nonexistent", 1)
        assert not report.ok
        assert "not found" in report.errors[0]

    def test_error_no_part(self, reorder: ChapterReorder) -> None:
        """Error when chapter has no part assigned."""
        report = reorder.renumber("Floating", 1)
        assert not report.ok
        assert "no part" in report.errors[0].lower()

    def test_error_number_too_high(self, reorder: ChapterReorder) -> None:
        """Error when target number exceeds max in part."""
        report = reorder.renumber("Beta", 5)
        assert not report.ok
        assert "exceeds" in report.errors[0].lower()

    def test_error_negative_number(self, reorder: ChapterReorder) -> None:
        """Error when target number is less than 1."""
        report = reorder.renumber("Beta", 0)
        assert not report.ok

    def test_insert_unnumbered(self, reorder: ChapterReorder, chapters_dir: Path) -> None:
        """Assigning a number to a partless chapter after giving it a part."""
        # First give Floating a part by writing it manually
        path = chapters_dir / "manuscript" / "chapters" / "floating.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        data["part"] = "Part 2"
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        report = reorder.renumber("Floating", 2, dry_run=False)
        assert report.ok
        assert _read_chapter(chapters_dir, "floating")["number"] == 2
        # Zeta (was 2) → 3, Eta (was 3) → 4
        assert _read_chapter(chapters_dir, "zeta")["number"] == 3
        assert _read_chapter(chapters_dir, "eta")["number"] == 4
        # Epsilon unchanged
        assert _read_chapter(chapters_dir, "epsilon")["number"] == 1


# =========================================================================
# Remove number tests
# =========================================================================


class TestRemoveNumber:
    """Tests for remove-number operation."""

    def test_remove_middle(self, reorder: ChapterReorder, chapters_dir: Path) -> None:
        """Removing #2 shifts 3,4 down by -1."""
        report = reorder.remove_number("Beta", dry_run=False)
        assert report.ok
        assert _read_chapter(chapters_dir, "beta").get("number") is None
        assert _read_chapter(chapters_dir, "gamma")["number"] == 2
        assert _read_chapter(chapters_dir, "delta")["number"] == 3
        assert _read_chapter(chapters_dir, "alpha")["number"] == 1

    def test_remove_last(self, reorder: ChapterReorder, chapters_dir: Path) -> None:
        """Removing the last number doesn't shift anything."""
        report = reorder.remove_number("Delta", dry_run=False)
        assert report.ok
        # Only one change: Delta itself
        assert len(report.changes) == 1
        assert _read_chapter(chapters_dir, "delta").get("number") is None

    def test_remove_already_unnumbered(self, reorder: ChapterReorder) -> None:
        """Removing number from unnumbered chapter is a no-op."""
        report = reorder.remove_number("Floating", dry_run=False)
        assert report.ok
        assert len(report.changes) == 0

    def test_error_not_found(self, reorder: ChapterReorder) -> None:
        """Error when chapter doesn't exist."""
        report = reorder.remove_number("Nonexistent")
        assert not report.ok


# =========================================================================
# Move part tests
# =========================================================================


class TestMovePart:
    """Tests for move-part operation."""

    def test_move_to_end(self, reorder: ChapterReorder, chapters_dir: Path) -> None:
        """Moving chapter to another part appends at end by default."""
        report = reorder.move_part("Beta", "Part 2", dry_run=False)
        assert report.ok

        beta = _read_chapter(chapters_dir, "beta")
        assert beta["part"] == "Part 2"
        assert beta["number"] == 4  # After Epsilon(1), Zeta(2), Eta(3)

        # Gap closed in Part 1: Gamma 3→2, Delta 4→3
        assert _read_chapter(chapters_dir, "gamma")["number"] == 2
        assert _read_chapter(chapters_dir, "delta")["number"] == 3

    def test_move_at_position(self, reorder: ChapterReorder, chapters_dir: Path) -> None:
        """Moving chapter to another part at a specific position."""
        report = reorder.move_part("Beta", "Part 2", at=2, dry_run=False)
        assert report.ok

        beta = _read_chapter(chapters_dir, "beta")
        assert beta["part"] == "Part 2"
        assert beta["number"] == 2

        # Part 2 shifted: Zeta 2→3, Eta 3→4
        assert _read_chapter(chapters_dir, "zeta")["number"] == 3
        assert _read_chapter(chapters_dir, "eta")["number"] == 4

    def test_error_same_part(self, reorder: ChapterReorder) -> None:
        """Error when moving to the same part."""
        report = reorder.move_part("Beta", "Part 1")
        assert not report.ok
        assert "already" in report.errors[0].lower()

    def test_error_unknown_part(self, reorder: ChapterReorder) -> None:
        """Error when target part doesn't exist."""
        report = reorder.move_part("Beta", "Part 99")
        assert not report.ok
        assert "not found" in report.errors[0].lower()

    def test_error_position_too_high(self, reorder: ChapterReorder) -> None:
        """Error when position would create a gap."""
        report = reorder.move_part("Beta", "Part 2", at=10)
        assert not report.ok
        assert "gap" in report.errors[0].lower()

    def test_dry_run(self, reorder: ChapterReorder, chapters_dir: Path) -> None:
        """Dry run doesn't modify files."""
        report = reorder.move_part("Beta", "Part 2", dry_run=True)
        assert report.ok
        assert report.dry_run
        assert _read_chapter(chapters_dir, "beta")["part"] == "Part 1"


# =========================================================================
# Report tests
# =========================================================================


class TestReorderReport:
    """Tests for report formatting."""

    def test_summary_dry_run(self, reorder: ChapterReorder) -> None:
        """Dry-run report includes [dry-run] prefix."""
        report = reorder.renumber("Beta", 4, dry_run=True)
        summary = report.summary()
        assert "[dry-run]" in summary

    def test_summary_errors(self, reorder: ChapterReorder) -> None:
        """Error report includes ERROR prefix."""
        report = reorder.renumber("Nonexistent", 1)
        summary = report.summary()
        assert "ERROR" in summary

    def test_summary_no_changes(self, reorder: ChapterReorder) -> None:
        """No-op report says no changes."""
        report = reorder.renumber("Beta", 2)
        summary = report.summary()
        assert "No changes" in summary
