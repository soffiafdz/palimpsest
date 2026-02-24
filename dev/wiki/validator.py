#!/usr/bin/env python3
"""
validator.py
------------
Wiki page validator and linter.

Validates wiki markdown files against structural rules and database
consistency. Produces diagnostics in a format compatible with
vim.diagnostic and common editor integrations.

Key Features:
    - Wikilink resolution (checks all [[links]] exist in DB)
    - Required section validation (H1 title, HR separator)
    - Empty section detection
    - Severity levels: error, warning, info
    - JSON-serializable output for editor integration

Usage:
    from dev.wiki.validator import WikiValidator

    validator = WikiValidator(db)
    diagnostics = validator.validate_file(Path("wiki/journal/people/clara.md"))

Dependencies:
    - PalimpsestDB for wikilink resolution
    - re for markdown pattern matching
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# --- Local imports ---
from dev.database.manager import PalimpsestDB
from dev.database.models import (
    Arc,
    City,
    Entry,
    Event,
    Location,
    Motif,
    Person,
    Poem,
    ReferenceSource,
    Tag,
    Theme,
)
from dev.database.models.manuscript import (
    Chapter,
    Character,
    ManuscriptScene,
    Part,
)
from dev.utils.slugify import slugify


# ==================== Constants ====================

WIKILINK_PATTERN = re.compile(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]')
WIKILINK1_PATTERN = re.compile(r'\[([^\]]*)\]\[([^\]]*)\]')
H1_PATTERN = re.compile(r'^# .+', re.MULTILINE)
HEADING_PATTERN = re.compile(r'^(#{1,6}) (.+)', re.MULTILINE)


# ==================== Diagnostic ====================

@dataclass
class Diagnostic:
    """
    A single diagnostic finding from wiki validation.

    Represents a structural issue, broken link, or style violation
    found in a wiki markdown file. Designed for JSON serialization
    and compatibility with vim.diagnostic.

    Attributes:
        file: Path to the file containing the diagnostic
        line: 1-based line number where the issue starts
        col: 1-based column number where the issue starts
        end_line: 1-based end line (same as line for single-line issues)
        end_col: 1-based end column
        severity: Diagnostic severity: "error", "warning", or "info"
        code: Machine-readable diagnostic code (e.g., UNRESOLVED_WIKILINK)
        message: Human-readable description of the issue
        source: Diagnostic source identifier, always "palimpsest"
    """

    file: str
    line: int
    col: int
    end_line: int
    end_col: int
    severity: str
    code: str
    message: str
    source: str = "palimpsest"

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize diagnostic to dict for JSON output.

        Returns:
            Dict with all diagnostic fields, suitable for
            json.dumps() and vim.diagnostic integration
        """
        return {
            "file": self.file,
            "line": self.line,
            "col": self.col,
            "end_line": self.end_line,
            "end_col": self.end_col,
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "source": self.source,
        }


# ==================== WikiValidator ====================

class WikiValidator:
    """
    Validates wiki markdown files for structural and semantic issues.

    Checks structural rules (H1 title, non-empty sections) and
    resolves wikilinks against the database to find broken references.
    All valid wikilink targets are loaded once and cached for the
    lifetime of the validator instance.

    Attributes:
        db: PalimpsestDB instance for entity resolution
        _known_targets: Cached set of valid lowercase wikilink targets
    """

    def __init__(self, db: PalimpsestDB) -> None:
        """
        Initialize the wiki validator.

        Args:
            db: PalimpsestDB instance for querying wikilink targets
        """
        self.db = db
        self._known_targets: Optional[Set[str]] = None

    def validate_file(self, file_path: Path) -> List[Diagnostic]:
        """
        Validate a single wiki markdown file.

        Runs all structural checks and wikilink resolution against
        the file content. Returns a list of diagnostics sorted by
        line number.

        Args:
            file_path: Path to the markdown file to validate

        Returns:
            List of Diagnostic instances found in the file,
            sorted by line number
        """
        content = file_path.read_text(encoding="utf-8")
        file_str = str(file_path)

        diagnostics: List[Diagnostic] = []
        diagnostics.extend(self._check_title(content, file_str))
        diagnostics.extend(self._check_empty_sections(content, file_str))
        diagnostics.extend(self._check_wikilinks(content, file_str))

        diagnostics.sort(key=lambda d: (d.line, d.col))
        return diagnostics

    def validate_directory(self, dir_path: Path) -> Dict[str, List[Diagnostic]]:
        """
        Validate all markdown files in a directory tree.

        Recursively walks the directory and validates every .md file.
        Returns results keyed by file path string.

        Args:
            dir_path: Root directory to scan for .md files

        Returns:
            Dict mapping file path strings to their diagnostic lists.
            All files are included, even those with no diagnostics.
        """
        results: Dict[str, List[Diagnostic]] = {}

        for md_file in sorted(dir_path.rglob("*.md")):
            diagnostics = self.validate_file(md_file)
            results[str(md_file)] = diagnostics

        return results

    def _load_known_targets(self) -> Set[str]:
        """
        Load all valid wikilink targets from the database.

        Queries every entity type that can be a wikilink target and
        collects their names/identifiers into a single set of
        lowercased strings. Results are cached after first load.

        Returns:
            Set of lowercase strings representing valid wikilink targets
        """
        if self._known_targets is not None:
            return self._known_targets

        targets: Set[str] = set()

        with self.db.session_scope() as session:
            # People: by display_name + absolute path
            for person in session.query(Person).all():
                targets.add(person.display_name.lower())
                targets.add(f"/journal/people/{person.slug}")

            # Locations: by name + absolute path
            for location in session.query(Location).all():
                targets.add(location.name.lower())
                city_slug = slugify(location.city.name)
                loc_slug = slugify(location.name)
                targets.add(f"/journal/locations/{city_slug}/{loc_slug}")

            # Cities: by name + absolute path
            for city in session.query(City).all():
                targets.add(city.name.lower())
                targets.add(f"/journal/cities/{slugify(city.name)}")

            # Events: by name + absolute path
            for event in session.query(Event).all():
                targets.add(event.name.lower())
                targets.add(f"/journal/events/{slugify(event.name)}")

            # Arcs: by name + absolute path
            for arc in session.query(Arc).all():
                targets.add(arc.name.lower())
                targets.add(f"/journal/arcs/{slugify(arc.name)}")

            # Tags: by name + absolute path
            for tag in session.query(Tag).all():
                targets.add(tag.name.lower())
                targets.add(f"/journal/tags/{slugify(tag.name)}")

            # Themes: by name + absolute path
            for theme in session.query(Theme).all():
                targets.add(theme.name.lower())
                targets.add(f"/journal/themes/{slugify(theme.name)}")

            # Poems: by title + absolute path
            for poem in session.query(Poem).all():
                targets.add(poem.title.lower())
                targets.add(f"/journal/poems/{slugify(poem.title)}")

            # Reference sources: by title + absolute path
            for source in session.query(ReferenceSource).all():
                targets.add(source.title.lower())
                targets.add(f"/journal/references/{slugify(source.title)}")

            # Motifs: by name + absolute path
            for motif in session.query(Motif).all():
                targets.add(motif.name.lower())
                targets.add(f"/journal/motifs/{slugify(motif.name)}")

            # Entries: by date + absolute path + per-year index pages
            entry_years: set = set()
            for entry in session.query(Entry).all():
                date_str = entry.date.isoformat()
                year = entry.date.strftime("%Y")
                targets.add(date_str.lower())
                targets.add(f"/journal/entries/{year}/{date_str}")
                entry_years.add(year)

            for year in entry_years:
                targets.add(f"/indexes/entries-{year}")
            targets.add("/indexes/entry-index")

            # Manuscript: Chapters by title + absolute path
            for chapter in session.query(Chapter).all():
                targets.add(chapter.title.lower())
                targets.add(
                    f"/manuscript/chapters/{slugify(chapter.title)}"
                )

            # Manuscript: Characters by name + absolute path
            for character in session.query(Character).all():
                targets.add(character.name.lower())
                targets.add(
                    f"/manuscript/characters/{slugify(character.name)}"
                )

            # Manuscript: Scenes by name + absolute path
            for ms_scene in session.query(ManuscriptScene).all():
                targets.add(ms_scene.name.lower())
                targets.add(
                    f"/manuscript/scenes/{slugify(ms_scene.name)}"
                )

            # Manuscript: Parts by display_name + absolute path
            for part in session.query(Part).all():
                title = part.title or ""
                targets.add(f"part {part.number}: {title}".lower())
                stem = slugify(part.title) if part.title else f"part-{part.number}"
                targets.add(f"/manuscript/parts/{stem}")

        self._known_targets = targets
        return self._known_targets

    def _check_wikilinks(
        self, content: str, file_path: str
    ) -> List[Diagnostic]:
        """
        Check all wikilinks in the content resolve to known targets.

        Recognizes both WikiLink0 (``[[target]]``, ``[[target|display]]``)
        and WikiLink1 (``[display][target]``, ``[target][]``) formats.

        Args:
            content: File content as string
            file_path: File path for diagnostic reporting

        Returns:
            List of UNRESOLVED_WIKILINK diagnostics for broken links
        """
        known = self._load_known_targets()
        diagnostics: List[Diagnostic] = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines, start=1):
            # WikiLink0: [[target]] or [[target|display]]
            for match in WIKILINK_PATTERN.finditer(line):
                target = match.group(1).strip()
                if target.lower() not in known:
                    col = match.start() + 1
                    end_col = match.end() + 1
                    diagnostics.append(Diagnostic(
                        file=file_path,
                        line=line_num,
                        col=col,
                        end_line=line_num,
                        end_col=end_col,
                        severity="error",
                        code="UNRESOLVED_WIKILINK",
                        message=f"Wikilink target not found: [[{target}]]",
                    ))

            # WikiLink1: [display][target] or [target][]
            for match in WIKILINK1_PATTERN.finditer(line):
                display = match.group(1).strip()
                target = match.group(2).strip()
                # [target][] → target is in group 1, group 2 is empty
                resolved = target if target else display
                if resolved.lower() not in known:
                    col = match.start() + 1
                    end_col = match.end() + 1
                    diagnostics.append(Diagnostic(
                        file=file_path,
                        line=line_num,
                        col=col,
                        end_line=line_num,
                        end_col=end_col,
                        severity="error",
                        code="UNRESOLVED_WIKILINK",
                        message=(
                            f"Wikilink target not found: "
                            f"[{display}][{target}]"
                        ),
                    ))

        return diagnostics

    def _check_title(
        self, content: str, file_path: str
    ) -> List[Diagnostic]:
        """
        Check that the file contains an H1 heading.

        Every wiki page must have exactly one H1 title line
        (``# Title``). Files without one receive an error diagnostic.

        Args:
            content: File content as string
            file_path: File path for diagnostic reporting

        Returns:
            List containing one MISSING_TITLE diagnostic if no H1 found,
            or empty list if H1 exists
        """
        if H1_PATTERN.search(content):
            return []

        return [Diagnostic(
            file=file_path,
            line=1,
            col=1,
            end_line=1,
            end_col=1,
            severity="error",
            code="MISSING_TITLE",
            message="No H1 heading found in file",
        )]

    def _check_empty_sections(
        self, content: str, file_path: str
    ) -> List[Diagnostic]:
        """
        Check for empty sections (headings with no content before next heading).

        A section is considered empty if there is no non-whitespace content
        between its heading and the next heading (or end of file for the
        last section). Only checks H2+ headings; H1 title is excluded.

        Args:
            content: File content as string
            file_path: File path for diagnostic reporting

        Returns:
            List of EMPTY_SECTION diagnostics for headings with no content
        """
        diagnostics: List[Diagnostic] = []
        lines = content.split("\n")

        # Collect heading positions (line_num, level, title)
        headings: List[tuple] = []
        for line_num, line in enumerate(lines, start=1):
            match = HEADING_PATTERN.match(line)
            if match:
                level = len(match.group(1))
                title = match.group(2)
                headings.append((line_num, level, title))

        # Check each H2+ heading for content before the next heading
        for i, (line_num, level, title) in enumerate(headings):
            if level < 2:
                continue

            # Determine the range to check for content
            start_line = line_num  # heading line (1-based)
            if i + 1 < len(headings):
                end_line = headings[i + 1][0]
            else:
                end_line = len(lines) + 1

            # Check for non-whitespace content between heading and next heading
            has_content = False
            for check_line in range(start_line, end_line - 1):
                # check_line is 1-based index, lines[] is 0-based
                line_content = lines[check_line]  # line after heading
                if line_content.strip():
                    has_content = True
                    break

            if not has_content:
                diagnostics.append(Diagnostic(
                    file=file_path,
                    line=line_num,
                    col=1,
                    end_line=line_num,
                    end_col=len(lines[line_num - 1]) + 1,
                    severity="warning",
                    code="EMPTY_SECTION",
                    message=f"Empty section: {title}",
                ))

        return diagnostics
