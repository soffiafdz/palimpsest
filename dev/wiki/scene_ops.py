#!/usr/bin/env python3
"""
scene_ops.py
------------
Scene reordering operations on YAML metadata files.

Handles renumbering scenes within chapters with automatic
gap-filling and shift semantics. Order values are per-chapter:
each chapter has its own 1-based sequence.

Key Features:
    - Reorder: move a scene to a new position within its chapter
    - Remove order: clear a scene's order, close the gap
    - Insert semantics: shifting neighbors up or down as needed
    - Dry-run by default: preview changes before applying
    - Format-preserving: line-based YAML field replacement

Usage:
    from dev.wiki.scene_ops import SceneReorder

    reorder = SceneReorder(metadata_dir)
    report = reorder.reorder("Chez Ernest date", 2, dry_run=False)
    print(report.summary())
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# --- Third party imports ---
import yaml

# --- Local imports ---
from dev.wiki.chapter_ops import ChapterReorder


@dataclass
class SceneInfo:
    """
    Parsed scene metadata from a YAML file.

    Attributes:
        name: Scene name
        chapter: Chapter title or None
        order: Scene order within its chapter, or None
        filepath: Path to the YAML file
    """

    name: str
    chapter: Optional[str]
    order: Optional[int]
    filepath: Path


@dataclass
class SceneReorderChange:
    """
    A single change to a scene's order.

    Attributes:
        name: Scene name
        filepath: Path to the YAML file
        old_order: Previous order (None if unset)
        new_order: New order (None if removing)
    """

    name: str
    filepath: Path
    old_order: Optional[int] = None
    new_order: Optional[int] = None

    @property
    def changed(self) -> bool:
        """Whether the order field changed."""
        return self.old_order != self.new_order


@dataclass
class SceneReorderReport:
    """
    Result of a scene reorder operation.

    Attributes:
        operation: Description of the operation performed
        changes: List of individual scene changes
        errors: Validation errors that prevented the operation
        dry_run: Whether this was a dry-run (no files modified)
    """

    operation: str
    changes: List[SceneReorderChange] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    dry_run: bool = True

    @property
    def ok(self) -> bool:
        """Whether the operation succeeded (no errors)."""
        return len(self.errors) == 0

    def summary(self) -> str:
        """
        Human-readable summary of the operation.

        Returns:
            Formatted string with operation result and changes
        """
        lines = [self.operation]
        if self.errors:
            for err in self.errors:
                lines.append(f"  ERROR: {err}")
            return "\n".join(lines)

        if not self.changes:
            lines.append("  No changes needed.")
            return "\n".join(lines)

        prefix = "  [dry-run] " if self.dry_run else "  "
        for ch in self.changes:
            old = ch.old_order if ch.old_order is not None else "none"
            new = ch.new_order if ch.new_order is not None else "none"
            lines.append(f"{prefix}{ch.name}: #{old} → #{new}")

        return "\n".join(lines)


class SceneReorder:
    """
    Reorder scenes within chapters via YAML file manipulation.

    All ordering is per-chapter. Operations validate constraints and
    compute the minimal set of YAML file changes needed.

    Args:
        metadata_dir: Path to data/metadata/ directory
    """

    def __init__(self, metadata_dir: Path) -> None:
        """
        Initialize the reorder engine.

        Args:
            metadata_dir: Path to data/metadata/ directory
        """
        self.scenes_dir = metadata_dir / "manuscript" / "scenes"

    def _load_scenes(self) -> List[SceneInfo]:
        """
        Load all scene YAML files.

        Returns:
            List of SceneInfo with parsed metadata

        Raises:
            FileNotFoundError: If scenes directory does not exist
        """
        if not self.scenes_dir.is_dir():
            raise FileNotFoundError(
                f"Scenes directory not found: {self.scenes_dir}"
            )

        scenes = []
        for path in sorted(self.scenes_dir.glob("*.yaml")):
            with open(path) as f:
                data = yaml.safe_load(f)
            if not data or "name" not in data:
                continue
            scenes.append(SceneInfo(
                name=data["name"],
                chapter=data.get("chapter"),
                order=data.get("order"),
                filepath=path,
            ))
        return scenes

    def _find_scene(
        self, scenes: List[SceneInfo], name: str
    ) -> Optional[SceneInfo]:
        """
        Find a scene by name (case-sensitive).

        Args:
            scenes: List of loaded scenes
            name: Scene name to find

        Returns:
            SceneInfo if found, None otherwise
        """
        for s in scenes:
            if s.name == name:
                return s
        return None

    def _scenes_in_chapter(
        self, scenes: List[SceneInfo], chapter: Optional[str]
    ) -> List[SceneInfo]:
        """
        Get all ordered scenes in a chapter, sorted by order.

        Args:
            scenes: List of all scenes
            chapter: Chapter title to filter by

        Returns:
            Sorted list of ordered scenes in the chapter
        """
        return sorted(
            [s for s in scenes if s.chapter == chapter and s.order is not None],
            key=lambda s: s.order,  # type: ignore[arg-type]
        )

    def reorder(
        self,
        scene_name: str,
        new_order: int,
        dry_run: bool = True,
    ) -> SceneReorderReport:
        """
        Move a scene to a new order within its chapter.

        Shifts neighboring scenes to fill gaps and make room.

        Args:
            scene_name: Name of the scene to reorder
            new_order: Target order (1-based)
            dry_run: If True, compute changes without writing files

        Returns:
            SceneReorderReport with changes or errors
        """
        report = SceneReorderReport(
            operation=f"Reorder '{scene_name}' → #{new_order}",
            dry_run=dry_run,
        )

        scenes = self._load_scenes()
        target = self._find_scene(scenes, scene_name)

        if not target:
            report.errors.append(f"Scene not found: {scene_name}")
            return report
        if not target.chapter:
            report.errors.append(
                "Scene has no chapter. Assign a chapter before ordering."
            )
            return report
        if new_order < 1:
            report.errors.append("Order must be >= 1.")
            return report

        old_order = target.order
        if old_order == new_order:
            return report

        siblings = self._scenes_in_chapter(scenes, target.chapter)
        max_ord = max((s.order for s in siblings), default=0)  # type: ignore[arg-type]

        if old_order is None:
            # Insertion
            if new_order > max_ord + 1:
                report.errors.append(
                    f"Order {new_order} would create a gap. "
                    f"Max in '{target.chapter}' is {max_ord}."
                )
                return report

            for sib in siblings:
                if sib.order >= new_order:  # type: ignore[operator]
                    report.changes.append(SceneReorderChange(
                        name=sib.name,
                        filepath=sib.filepath,
                        old_order=sib.order,
                        new_order=sib.order + 1,  # type: ignore[operator]
                    ))

            report.changes.append(SceneReorderChange(
                name=target.name,
                filepath=target.filepath,
                old_order=None,
                new_order=new_order,
            ))
        else:
            if new_order > max_ord:
                report.errors.append(
                    f"Order {new_order} exceeds max ({max_ord}) "
                    f"in '{target.chapter}'."
                )
                return report

            if old_order < new_order:
                for sib in siblings:
                    if sib.name == target.name:
                        continue
                    if old_order < sib.order <= new_order:  # type: ignore[operator]
                        report.changes.append(SceneReorderChange(
                            name=sib.name,
                            filepath=sib.filepath,
                            old_order=sib.order,
                            new_order=sib.order - 1,  # type: ignore[operator]
                        ))
            else:
                for sib in siblings:
                    if sib.name == target.name:
                        continue
                    if new_order <= sib.order < old_order:  # type: ignore[operator]
                        report.changes.append(SceneReorderChange(
                            name=sib.name,
                            filepath=sib.filepath,
                            old_order=sib.order,
                            new_order=sib.order + 1,  # type: ignore[operator]
                        ))

            report.changes.append(SceneReorderChange(
                name=target.name,
                filepath=target.filepath,
                old_order=old_order,
                new_order=new_order,
            ))

        if not dry_run:
            self._apply_changes(report.changes)

        return report

    def remove_order(
        self,
        scene_name: str,
        dry_run: bool = True,
    ) -> SceneReorderReport:
        """
        Remove a scene's order and close the gap in its chapter.

        Args:
            scene_name: Name of the scene to unorder
            dry_run: If True, compute changes without writing files

        Returns:
            SceneReorderReport with changes or errors
        """
        report = SceneReorderReport(
            operation=f"Remove order from '{scene_name}'",
            dry_run=dry_run,
        )

        scenes = self._load_scenes()
        target = self._find_scene(scenes, scene_name)

        if not target:
            report.errors.append(f"Scene not found: {scene_name}")
            return report
        if target.order is None:
            return report

        old_order = target.order
        siblings = self._scenes_in_chapter(scenes, target.chapter)

        for sib in siblings:
            if sib.name == target.name:
                continue
            if sib.order > old_order:  # type: ignore[operator]
                report.changes.append(SceneReorderChange(
                    name=sib.name,
                    filepath=sib.filepath,
                    old_order=sib.order,
                    new_order=sib.order - 1,  # type: ignore[operator]
                ))

        report.changes.append(SceneReorderChange(
            name=target.name,
            filepath=target.filepath,
            old_order=old_order,
            new_order=None,
        ))

        if not dry_run:
            self._apply_changes(report.changes)

        return report

    def _apply_changes(self, changes: List[SceneReorderChange]) -> None:
        """
        Write changes to YAML files.

        Args:
            changes: List of changes to apply
        """
        for change in changes:
            if change.changed:
                ChapterReorder._update_yaml_field(
                    change.filepath, "order", change.new_order
                )
