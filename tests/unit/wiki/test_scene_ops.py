#!/usr/bin/env python3
"""
test_scene_ops.py
-----------------
Tests for scene reorder operations (reorder, remove-order).

Tests use a temporary directory with scene YAML files to verify
correct shift semantics, gap-filling, and validation.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from dev.wiki.scene_ops import SceneReorder


@pytest.fixture
def scenes_dir(tmp_path: Path) -> Path:
    """Create a metadata directory with sample scene YAMLs."""
    sc_dir = tmp_path / "manuscript" / "scenes"
    sc_dir.mkdir(parents=True)

    scenes = [
        {"name": "Arrival", "chapter": "Alpha", "order": 1},
        {"name": "Breakfast", "chapter": "Alpha", "order": 2},
        {"name": "Conflict", "chapter": "Alpha", "order": 3},
        {"name": "Departure", "chapter": "Alpha", "order": 4},
        {"name": "Encounter", "chapter": "Beta", "order": 1},
        {"name": "Farewell", "chapter": "Beta", "order": 2},
        {"name": "Flashback", "chapter": "Beta", "order": 3},
        {"name": "Unassigned", "chapter": "Alpha"},
        {"name": "Orphan"},
    ]

    for sc in scenes:
        slug = sc["name"].lower()
        path = sc_dir / f"{slug}.yaml"
        with open(path, "w") as f:
            yaml.dump(sc, f, default_flow_style=False, sort_keys=False)

    return tmp_path


@pytest.fixture
def reorder(scenes_dir: Path) -> SceneReorder:
    """Create a SceneReorder pointing at the test directory."""
    return SceneReorder(scenes_dir)


def _read_scene(scenes_dir: Path, slug: str) -> dict:
    """Read a scene YAML and return its data."""
    path = scenes_dir / "manuscript" / "scenes" / f"{slug}.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


# =========================================================================
# Reorder tests
# =========================================================================


class TestReorder:
    """Tests for reorder operation."""

    def test_move_down(self, reorder: SceneReorder, scenes_dir: Path) -> None:
        """Moving scene #2→4 shifts 3,4 down by -1."""
        report = reorder.reorder("Breakfast", 4, dry_run=False)
        assert report.ok
        assert len(report.changes) == 3

        assert _read_scene(scenes_dir, "breakfast")["order"] == 4
        assert _read_scene(scenes_dir, "conflict")["order"] == 2
        assert _read_scene(scenes_dir, "departure")["order"] == 3
        assert _read_scene(scenes_dir, "arrival")["order"] == 1

    def test_move_up(self, reorder: SceneReorder, scenes_dir: Path) -> None:
        """Moving scene #4→2 shifts 2,3 up by +1."""
        report = reorder.reorder("Departure", 2, dry_run=False)
        assert report.ok
        assert len(report.changes) == 3

        assert _read_scene(scenes_dir, "departure")["order"] == 2
        assert _read_scene(scenes_dir, "breakfast")["order"] == 3
        assert _read_scene(scenes_dir, "conflict")["order"] == 4
        assert _read_scene(scenes_dir, "arrival")["order"] == 1

    def test_no_op_same_order(self, reorder: SceneReorder) -> None:
        """Reordering to same position is a no-op."""
        report = reorder.reorder("Breakfast", 2, dry_run=False)
        assert report.ok
        assert len(report.changes) == 0

    def test_dry_run_no_write(self, reorder: SceneReorder, scenes_dir: Path) -> None:
        """Dry run computes changes but doesn't modify files."""
        report = reorder.reorder("Breakfast", 4, dry_run=True)
        assert report.ok
        assert report.dry_run
        assert len(report.changes) == 3
        assert _read_scene(scenes_dir, "breakfast")["order"] == 2

    def test_cross_chapter_isolation(self, reorder: SceneReorder, scenes_dir: Path) -> None:
        """Reordering in Alpha doesn't affect Beta."""
        reorder.reorder("Arrival", 4, dry_run=False)
        assert _read_scene(scenes_dir, "encounter")["order"] == 1
        assert _read_scene(scenes_dir, "farewell")["order"] == 2
        assert _read_scene(scenes_dir, "flashback")["order"] == 3

    def test_insert_unordered(self, reorder: SceneReorder, scenes_dir: Path) -> None:
        """Inserting an unordered scene shifts siblings up."""
        report = reorder.reorder("Unassigned", 2, dry_run=False)
        assert report.ok
        assert _read_scene(scenes_dir, "unassigned")["order"] == 2
        assert _read_scene(scenes_dir, "breakfast")["order"] == 3
        assert _read_scene(scenes_dir, "conflict")["order"] == 4
        assert _read_scene(scenes_dir, "departure")["order"] == 5
        assert _read_scene(scenes_dir, "arrival")["order"] == 1

    def test_insert_at_end(self, reorder: SceneReorder, scenes_dir: Path) -> None:
        """Inserting at max+1 appends without shifting."""
        report = reorder.reorder("Unassigned", 5, dry_run=False)
        assert report.ok
        assert len(report.changes) == 1
        assert _read_scene(scenes_dir, "unassigned")["order"] == 5

    def test_error_scene_not_found(self, reorder: SceneReorder) -> None:
        """Error when scene name doesn't exist."""
        report = reorder.reorder("Nonexistent", 1)
        assert not report.ok
        assert "not found" in report.errors[0]

    def test_error_no_chapter(self, reorder: SceneReorder) -> None:
        """Error when scene has no chapter assigned."""
        report = reorder.reorder("Orphan", 1)
        assert not report.ok
        assert "no chapter" in report.errors[0].lower()

    def test_error_order_too_high(self, reorder: SceneReorder) -> None:
        """Error when target order exceeds max for ordered scene."""
        report = reorder.reorder("Breakfast", 5)
        assert not report.ok
        assert "exceeds" in report.errors[0].lower()

    def test_error_insert_gap(self, reorder: SceneReorder) -> None:
        """Error when inserting unordered scene would create a gap."""
        report = reorder.reorder("Unassigned", 10)
        assert not report.ok
        assert "gap" in report.errors[0].lower()

    def test_error_negative_order(self, reorder: SceneReorder) -> None:
        """Error when target order is less than 1."""
        report = reorder.reorder("Breakfast", 0)
        assert not report.ok


# =========================================================================
# Remove order tests
# =========================================================================


class TestRemoveOrder:
    """Tests for remove-order operation."""

    def test_remove_middle(self, reorder: SceneReorder, scenes_dir: Path) -> None:
        """Removing #2 shifts 3,4 down by -1."""
        report = reorder.remove_order("Breakfast", dry_run=False)
        assert report.ok
        assert _read_scene(scenes_dir, "breakfast").get("order") is None
        assert _read_scene(scenes_dir, "conflict")["order"] == 2
        assert _read_scene(scenes_dir, "departure")["order"] == 3
        assert _read_scene(scenes_dir, "arrival")["order"] == 1

    def test_remove_last(self, reorder: SceneReorder, scenes_dir: Path) -> None:
        """Removing the last order doesn't shift anything."""
        report = reorder.remove_order("Departure", dry_run=False)
        assert report.ok
        assert len(report.changes) == 1
        assert _read_scene(scenes_dir, "departure").get("order") is None

    def test_remove_already_unordered(self, reorder: SceneReorder) -> None:
        """Removing order from unordered scene is a no-op."""
        report = reorder.remove_order("Unassigned", dry_run=False)
        assert report.ok
        assert len(report.changes) == 0

    def test_error_not_found(self, reorder: SceneReorder) -> None:
        """Error when scene doesn't exist."""
        report = reorder.remove_order("Nonexistent")
        assert not report.ok


# =========================================================================
# Report tests
# =========================================================================


class TestSceneReorderReport:
    """Tests for report formatting."""

    def test_summary_dry_run(self, reorder: SceneReorder) -> None:
        """Dry-run report includes [dry-run] prefix."""
        report = reorder.reorder("Breakfast", 4, dry_run=True)
        summary = report.summary()
        assert "[dry-run]" in summary

    def test_summary_errors(self, reorder: SceneReorder) -> None:
        """Error report includes ERROR prefix."""
        report = reorder.reorder("Nonexistent", 1)
        summary = report.summary()
        assert "ERROR" in summary

    def test_summary_no_changes(self, reorder: SceneReorder) -> None:
        """No-op report says no changes."""
        report = reorder.reorder("Breakfast", 2)
        summary = report.summary()
        assert "No changes" in summary
