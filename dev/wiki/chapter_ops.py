#!/usr/bin/env python3
"""
chapter_ops.py
--------------
Chapter reordering operations on YAML metadata files.

Handles renumbering chapters within parts and moving chapters
between parts, with automatic gap-filling and shift semantics.
Numbers are per-part: each part has its own 1-based sequence.

Key Features:
    - Renumber: move a chapter to a new position within its part
    - Move: reassign a chapter to a different part
    - Remove number: clear a chapter's number, close the gap
    - Insert semantics: shifting neighbors up or down as needed
    - Dry-run by default: preview changes before applying
    - Format-preserving: line-based YAML field replacement

Usage:
    from dev.wiki.chapter_ops import ChapterReorder

    reorder = ChapterReorder(metadata_dir)
    report = reorder.renumber("Noche de muertos", 3, dry_run=False)
    print(report.summary())

    report = reorder.move_part("Cigarro", "Part 2", at=5, dry_run=False)
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


@dataclass
class ChapterInfo:
    """
    Parsed chapter metadata from a YAML file.

    Attributes:
        title: Chapter title
        part: Part display name (e.g. "Part 1") or None
        number: Chapter number within its part, or None
        filepath: Path to the YAML file
    """

    title: str
    part: Optional[str]
    number: Optional[int]
    filepath: Path


@dataclass
class ReorderChange:
    """
    A single change to a chapter's number or part.

    Attributes:
        title: Chapter title
        filepath: Path to the YAML file
        old_number: Previous number (None if unset)
        new_number: New number (None if removing)
        old_part: Previous part name (None if unset)
        new_part: New part name (None if unchanged)
    """

    title: str
    filepath: Path
    old_number: Optional[int] = None
    new_number: Optional[int] = None
    old_part: Optional[str] = None
    new_part: Optional[str] = None

    @property
    def number_changed(self) -> bool:
        """Whether the number field changed."""
        return self.old_number != self.new_number

    @property
    def part_changed(self) -> bool:
        """Whether the part field changed."""
        return self.old_part != self.new_part


@dataclass
class ReorderReport:
    """
    Result of a reorder operation.

    Attributes:
        operation: Description of the operation performed
        changes: List of individual chapter changes
        errors: Validation errors that prevented the operation
        dry_run: Whether this was a dry-run (no files modified)
    """

    operation: str
    changes: List[ReorderChange] = field(default_factory=list)
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
            parts = [f"{prefix}{ch.title}:"]
            if ch.number_changed:
                old = ch.old_number if ch.old_number is not None else "none"
                new = ch.new_number if ch.new_number is not None else "none"
                parts.append(f"#{old} → #{new}")
            if ch.part_changed:
                old = ch.old_part or "none"
                new = ch.new_part or "none"
                parts.append(f"({old} → {new})")
            lines.append(" ".join(parts))

        return "\n".join(lines)


class ChapterReorder:
    """
    Reorder chapters within and across parts via YAML file manipulation.

    All numbering is per-part. Operations validate constraints and
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
        self.chapters_dir = metadata_dir / "manuscript" / "chapters"

    def _load_chapters(self) -> List[ChapterInfo]:
        """
        Load all chapter YAML files.

        Returns:
            List of ChapterInfo with parsed metadata

        Raises:
            FileNotFoundError: If chapters directory does not exist
        """
        if not self.chapters_dir.is_dir():
            raise FileNotFoundError(
                f"Chapters directory not found: {self.chapters_dir}"
            )

        chapters = []
        for path in sorted(self.chapters_dir.glob("*.yaml")):
            with open(path) as f:
                data = yaml.safe_load(f)
            if not data or "title" not in data:
                continue
            chapters.append(ChapterInfo(
                title=data["title"],
                part=data.get("part"),
                number=data.get("number"),
                filepath=path,
            ))
        return chapters

    def _find_chapter(
        self, chapters: List[ChapterInfo], title: str
    ) -> Optional[ChapterInfo]:
        """
        Find a chapter by title (case-sensitive).

        Args:
            chapters: List of loaded chapters
            title: Chapter title to find

        Returns:
            ChapterInfo if found, None otherwise
        """
        for ch in chapters:
            if ch.title == title:
                return ch
        return None

    def _chapters_in_part(
        self, chapters: List[ChapterInfo], part: Optional[str]
    ) -> List[ChapterInfo]:
        """
        Get all numbered chapters in a part, sorted by number.

        Args:
            chapters: List of all chapters
            part: Part display name to filter by

        Returns:
            Sorted list of numbered chapters in the part
        """
        return sorted(
            [c for c in chapters if c.part == part and c.number is not None],
            key=lambda c: c.number,  # type: ignore[arg-type]
        )

    @staticmethod
    def _update_yaml_field(
        filepath: Path, field_name: str, new_value: object
    ) -> None:
        """
        Update a single field in a YAML file using line-based replacement.

        Preserves formatting and comments for other fields.

        Args:
            filepath: Path to the YAML file
            field_name: YAML key to update (e.g. "number", "part")
            new_value: New value (None removes the field value, keeps key)
        """
        lines = filepath.read_text().splitlines(keepends=True)
        found = False
        for i, line in enumerate(lines):
            stripped = line.rstrip("\n\r")
            # Match field at start of line (not nested)
            if stripped.startswith(f"{field_name}:"):
                if new_value is None:
                    lines[i] = f"{field_name}:\n"
                else:
                    lines[i] = f"{field_name}: {new_value}\n"
                found = True
                break

        if not found and new_value is not None:
            # Append the field if it doesn't exist
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(f"{field_name}: {new_value}\n")

        filepath.write_text("".join(lines))

    def renumber(
        self,
        chapter_title: str,
        new_number: int,
        dry_run: bool = True,
    ) -> ReorderReport:
        """
        Move a chapter to a new number within its current part.

        Shifts neighboring chapters to fill gaps and make room.
        Moving down (2→5): chapters 3,4,5 shift -1.
        Moving up (5→2): chapters 2,3,4 shift +1.

        Args:
            chapter_title: Title of the chapter to renumber
            new_number: Target number (1-based)
            dry_run: If True, compute changes without writing files

        Returns:
            ReorderReport with changes or errors
        """
        report = ReorderReport(
            operation=f"Renumber '{chapter_title}' → #{new_number}",
            dry_run=dry_run,
        )

        chapters = self._load_chapters()
        target = self._find_chapter(chapters, chapter_title)

        # --- Validation ---
        if not target:
            report.errors.append(f"Chapter not found: {chapter_title}")
            return report
        if not target.part:
            report.errors.append(
                "Chapter has no part. Assign a part before numbering."
            )
            return report
        if new_number < 1:
            report.errors.append("Number must be >= 1.")
            return report

        old_number = target.number
        if old_number == new_number:
            return report  # No-op

        siblings = self._chapters_in_part(chapters, target.part)
        max_num = max((c.number for c in siblings), default=0)  # type: ignore[arg-type]

        # If target has no number yet, treat as insertion
        if old_number is None:
            if new_number > max_num + 1:
                report.errors.append(
                    f"Number {new_number} would create a gap. "
                    f"Max in {target.part} is {max_num}."
                )
                return report

            # Shift siblings >= new_number up by +1
            for sib in siblings:
                if sib.number >= new_number:  # type: ignore[operator]
                    change = ReorderChange(
                        title=sib.title,
                        filepath=sib.filepath,
                        old_number=sib.number,
                        new_number=sib.number + 1,  # type: ignore[operator]
                    )
                    report.changes.append(change)

            report.changes.append(ReorderChange(
                title=target.title,
                filepath=target.filepath,
                old_number=None,
                new_number=new_number,
            ))

        else:
            # Moving within existing numbered sequence
            if new_number > max_num:
                report.errors.append(
                    f"Number {new_number} exceeds max ({max_num}) "
                    f"in {target.part}."
                )
                return report

            if old_number < new_number:
                # Moving down: shift range (old+1..new) by -1
                for sib in siblings:
                    if sib.title == target.title:
                        continue
                    if old_number < sib.number <= new_number:  # type: ignore[operator]
                        report.changes.append(ReorderChange(
                            title=sib.title,
                            filepath=sib.filepath,
                            old_number=sib.number,
                            new_number=sib.number - 1,  # type: ignore[operator]
                        ))
            else:
                # Moving up: shift range (new..old-1) by +1
                for sib in siblings:
                    if sib.title == target.title:
                        continue
                    if new_number <= sib.number < old_number:  # type: ignore[operator]
                        report.changes.append(ReorderChange(
                            title=sib.title,
                            filepath=sib.filepath,
                            old_number=sib.number,
                            new_number=sib.number + 1,  # type: ignore[operator]
                        ))

            report.changes.append(ReorderChange(
                title=target.title,
                filepath=target.filepath,
                old_number=old_number,
                new_number=new_number,
            ))

        if not dry_run:
            self._apply_changes(report.changes)

        return report

    def remove_number(
        self,
        chapter_title: str,
        dry_run: bool = True,
    ) -> ReorderReport:
        """
        Remove a chapter's number and close the gap in its part.

        Args:
            chapter_title: Title of the chapter to unnumber
            dry_run: If True, compute changes without writing files

        Returns:
            ReorderReport with changes or errors
        """
        report = ReorderReport(
            operation=f"Remove number from '{chapter_title}'",
            dry_run=dry_run,
        )

        chapters = self._load_chapters()
        target = self._find_chapter(chapters, chapter_title)

        if not target:
            report.errors.append(f"Chapter not found: {chapter_title}")
            return report
        if target.number is None:
            return report  # Already unnumbered, no-op

        old_number = target.number
        siblings = self._chapters_in_part(chapters, target.part)

        # Close gap: shift siblings > old_number by -1
        for sib in siblings:
            if sib.title == target.title:
                continue
            if sib.number > old_number:  # type: ignore[operator]
                report.changes.append(ReorderChange(
                    title=sib.title,
                    filepath=sib.filepath,
                    old_number=sib.number,
                    new_number=sib.number - 1,  # type: ignore[operator]
                ))

        report.changes.append(ReorderChange(
            title=target.title,
            filepath=target.filepath,
            old_number=old_number,
            new_number=None,
        ))

        if not dry_run:
            self._apply_changes(report.changes)

        return report

    def move_part(
        self,
        chapter_title: str,
        new_part: str,
        at: Optional[int] = None,
        dry_run: bool = True,
    ) -> ReorderReport:
        """
        Move a chapter to a different part.

        Closes the gap in the old part and inserts at the given
        position (or end) in the new part.

        Args:
            chapter_title: Title of the chapter to move
            new_part: Target part display name (e.g. "Part 2")
            at: Position in the new part (1-based). None = append at end.
            dry_run: If True, compute changes without writing files

        Returns:
            ReorderReport with changes or errors
        """
        report = ReorderReport(
            operation=f"Move '{chapter_title}' → {new_part}"
            + (f" at #{at}" if at else ""),
            dry_run=dry_run,
        )

        chapters = self._load_chapters()
        target = self._find_chapter(chapters, chapter_title)

        if not target:
            report.errors.append(f"Chapter not found: {chapter_title}")
            return report

        # Validate target part exists (at least one chapter references it)
        known_parts = {c.part for c in chapters if c.part}
        if new_part not in known_parts:
            report.errors.append(
                f"Part not found: {new_part}. "
                f"Known parts: {', '.join(sorted(known_parts))}"
            )
            return report

        if target.part == new_part:
            report.errors.append(
                f"Chapter is already in {new_part}. "
                "Use renumber to change position within a part."
            )
            return report

        old_part = target.part
        old_number = target.number

        # --- Close gap in old part ---
        if old_number is not None and old_part is not None:
            old_siblings = self._chapters_in_part(chapters, old_part)
            for sib in old_siblings:
                if sib.title == target.title:
                    continue
                if sib.number > old_number:  # type: ignore[operator]
                    report.changes.append(ReorderChange(
                        title=sib.title,
                        filepath=sib.filepath,
                        old_number=sib.number,
                        new_number=sib.number - 1,  # type: ignore[operator]
                    ))

        # --- Insert into new part ---
        new_siblings = self._chapters_in_part(chapters, new_part)
        max_new = max(
            (c.number for c in new_siblings), default=0  # type: ignore[arg-type]
        )

        if at is None:
            new_number = max_new + 1
        else:
            if at < 1:
                report.errors.append("Position must be >= 1.")
                return report
            if at > max_new + 1:
                report.errors.append(
                    f"Position {at} would create a gap. "
                    f"Max in {new_part} is {max_new}."
                )
                return report
            new_number = at

            # Shift new siblings >= at by +1
            for sib in new_siblings:
                if sib.number >= at:  # type: ignore[operator]
                    report.changes.append(ReorderChange(
                        title=sib.title,
                        filepath=sib.filepath,
                        old_number=sib.number,
                        new_number=sib.number + 1,  # type: ignore[operator]
                    ))

        report.changes.append(ReorderChange(
            title=target.title,
            filepath=target.filepath,
            old_number=old_number,
            new_number=new_number,
            old_part=old_part,
            new_part=new_part,
        ))

        if not dry_run:
            self._apply_changes(report.changes)

        return report

    def _apply_changes(self, changes: List[ReorderChange]) -> None:
        """
        Write changes to YAML files.

        Applies number changes first (shifted siblings), then
        the target chapter's number and part changes.

        Args:
            changes: List of changes to apply
        """
        for change in changes:
            if change.number_changed:
                self._update_yaml_field(
                    change.filepath, "number", change.new_number
                )
            if change.part_changed:
                self._update_yaml_field(
                    change.filepath, "part", change.new_part
                )
