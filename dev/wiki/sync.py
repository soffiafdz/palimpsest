#!/usr/bin/env python3
"""
sync.py
-------
Bidirectional manuscript wiki sync orchestrator.

Manages the validate → ingest → regenerate cycle for manuscript
wiki pages. User edits wiki files in Neovim, sync validates them,
parses changes into the database, and regenerates all manuscript
pages with computed data.

Key Features:
    - Pre-sync validation gate (errors block sync)
    - Per-file transaction during ingestion
    - Change detection during regeneration (only overwrites if different)
    - Supports partial operations (ingest-only, generate-only)

Sync Cycle:
    1. Validate: Run validator on all manuscript wiki files
    2. Ingest: Parse validated wiki → update DB entities
    3. Regenerate: Render all manuscript pages from DB

Usage:
    from dev.wiki.sync import WikiSync

    sync = WikiSync(db)
    sync.sync_manuscript()                    # Full cycle
    sync.sync_manuscript(ingest_only=True)    # Wiki → DB only
    sync.sync_manuscript(generate_only=True)  # DB → Wiki only

Dependencies:
    - WikiParser for markdown → dataclass conversion
    - WikiValidator for pre-sync validation
    - WikiExporter for DB → wiki generation
    - PalimpsestDB for database operations
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- Local imports ---
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.core.paths import WIKI_DIR
from dev.database.manager import PalimpsestDB
from dev.database.models import Arc, Entry, Person, Poem, ReferenceSource
from dev.database.models.enums import (
    ChapterStatus,
    ChapterType,
    ContributionType,
    ReferenceMode,
    SceneOrigin,
    SceneStatus,
    SourceType,
)
from dev.database.models.manuscript import (
    Chapter,
    Character,
    ManuscriptReference,
    ManuscriptScene,
    ManuscriptSource,
    PersonCharacterMap,
)
from dev.wiki.parser import (
    ChapterData,
    CharacterData,
    ManuscriptSceneData,
    WikiParser,
)
from dev.wiki.validator import WikiValidator


# ==================== Sync Result ====================

class SyncResult:
    """
    Result of a sync operation.

    Tracks files processed, entities updated, errors encountered,
    and warnings produced during sync.

    Attributes:
        files_validated: Number of files that passed validation
        files_ingested: Number of files parsed into DB
        files_generated: Number of files regenerated
        files_changed: Number of files that actually changed on disk
        errors: List of error messages
        warnings: List of warning messages
        updates: Dict of entity type → count of updates
    """

    def __init__(self) -> None:
        """Initialize an empty sync result."""
        self.files_validated: int = 0
        self.files_ingested: int = 0
        self.files_generated: int = 0
        self.files_changed: int = 0
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.updates: Dict[str, int] = {
            "chapters": 0,
            "characters": 0,
            "scenes": 0,
        }

    @property
    def success(self) -> bool:
        """Check if sync completed without errors."""
        return len(self.errors) == 0

    def summary(self) -> str:
        """
        Format a human-readable summary of the sync result.

        Returns:
            Multi-line summary string
        """
        lines = []
        if self.files_validated:
            lines.append(f"Validated: {self.files_validated} files")
        if self.files_ingested:
            lines.append(f"Ingested: {self.files_ingested} files")
            for entity_type, count in self.updates.items():
                if count:
                    lines.append(f"  {entity_type}: {count} updated")
        if self.files_generated:
            lines.append(
                f"Generated: {self.files_generated} files "
                f"({self.files_changed} changed)"
            )
        if self.warnings:
            lines.append(f"Warnings: {len(self.warnings)}")
        if self.errors:
            lines.append(f"Errors: {len(self.errors)}")
            for err in self.errors:
                lines.append(f"  - {err}")
        return "\n".join(lines)


# ==================== WikiSync ====================

class WikiSync:
    """
    Orchestrates bidirectional manuscript wiki synchronization.

    Coordinates validation, parsing, database ingestion, and
    wiki regeneration for manuscript pages (chapters, characters,
    manuscript scenes).

    Attributes:
        db: PalimpsestDB instance
        wiki_dir: Root wiki directory
        parser: WikiParser for markdown → data extraction
        validator: WikiValidator for pre-sync checks
        logger: Optional logger instance
    """

    def __init__(
        self,
        db: PalimpsestDB,
        wiki_dir: Optional[Path] = None,
        logger: Optional[PalimpsestLogger] = None,
    ) -> None:
        """
        Initialize the wiki sync manager.

        Args:
            db: PalimpsestDB instance
            wiki_dir: Wiki root directory (defaults to WIKI_DIR)
            logger: Optional logger for progress reporting
        """
        self.db = db
        self.wiki_dir = wiki_dir or WIKI_DIR
        self.parser = WikiParser(db)
        self.validator = WikiValidator(db)
        self.logger = safe_logger(logger)

    def _check_sync_pending(self) -> None:
        """
        Check for deck sync-pending marker and refuse generation.

        When generate_only=True, edits haven't been ingested yet, so
        generation would overwrite deck changes. This guard ensures
        the user runs a full sync (or ingest) first.

        Raises:
            RuntimeError: If .sync-pending marker exists
        """
        from dev.wiki.exporter import WikiExporter

        exporter = WikiExporter(self.db, output_dir=self.wiki_dir)
        exporter._check_sync_pending()

    def sync_manuscript(
        self,
        ingest_only: bool = False,
        generate_only: bool = False,
    ) -> SyncResult:
        """
        Run the manuscript sync cycle.

        By default runs the full cycle: validate → ingest → regenerate.
        Use flags to run partial operations.

        Args:
            ingest_only: Only parse wiki → DB (skip regeneration)
            generate_only: Only regenerate DB → wiki (skip ingestion)

        Returns:
            SyncResult with operation statistics
        """
        result = SyncResult()
        manuscript_dir = self.wiki_dir / "manuscript"

        if not manuscript_dir.exists():
            result.errors.append(
                f"Manuscript directory not found: {manuscript_dir}"
            )
            return result

        if generate_only:
            self._check_sync_pending()
            self._regenerate(result)
            return result

        # Step 1: Validate
        self._validate(manuscript_dir, result)
        if not result.success:
            return result

        # Step 2: Ingest
        self._ingest(manuscript_dir, result)
        if not result.success:
            return result

        # Step 3: Regenerate (unless ingest-only)
        if not ingest_only:
            self.parser.clear_cache()
            self._regenerate(result)

        return result

    def _validate(
        self, manuscript_dir: Path, result: SyncResult
    ) -> None:
        """
        Run validation on all manuscript wiki files.

        Error-level diagnostics block sync. Warnings are recorded
        but do not block.

        Args:
            manuscript_dir: Path to manuscript wiki directory
            result: SyncResult to accumulate findings
        """
        self.logger.info("Validating manuscript pages...")
        all_diagnostics = self.validator.validate_directory(manuscript_dir)

        file_count = 0
        error_count = 0
        warning_count = 0

        for file_path, diagnostics in all_diagnostics.items():
            file_count += 1
            for diag in diagnostics:
                if diag.severity == "error":
                    error_count += 1
                    result.errors.append(
                        f"{file_path}:{diag.line} [{diag.code}] "
                        f"{diag.message}"
                    )
                elif diag.severity == "warning":
                    warning_count += 1
                    result.warnings.append(
                        f"{file_path}:{diag.line} [{diag.code}] "
                        f"{diag.message}"
                    )

        result.files_validated = file_count
        self.logger.info(
            f"Validation: {file_count} files, "
            f"{error_count} errors, {warning_count} warnings"
        )

    def _ingest(
        self, manuscript_dir: Path, result: SyncResult
    ) -> None:
        """
        Parse manuscript wiki files and update database.

        Processes each file type (chapters, characters, scenes)
        with per-file error handling. A parse error for one file
        does not block other files.

        Args:
            manuscript_dir: Path to manuscript wiki directory
            result: SyncResult to accumulate statistics
        """
        self.logger.info("Ingesting manuscript changes...")

        chapters_dir = manuscript_dir / "chapters"
        characters_dir = manuscript_dir / "characters"
        scenes_dir = manuscript_dir / "scenes"

        with self.db.session_scope() as session:
            # Ingest chapters
            if chapters_dir.exists():
                for md_file in sorted(chapters_dir.glob("*.md")):
                    try:
                        data = self.parser.parse_chapter(md_file)
                        self._ingest_chapter(session, data)
                        result.files_ingested += 1
                        result.updates["chapters"] += 1
                    except Exception as e:
                        result.errors.append(
                            f"Failed to ingest {md_file.name}: {e}"
                        )

            # Ingest characters
            if characters_dir.exists():
                for md_file in sorted(characters_dir.glob("*.md")):
                    try:
                        data = self.parser.parse_character(md_file)
                        self._ingest_character(session, data)
                        result.files_ingested += 1
                        result.updates["characters"] += 1
                    except Exception as e:
                        result.errors.append(
                            f"Failed to ingest {md_file.name}: {e}"
                        )

            # Ingest manuscript scenes
            if scenes_dir.exists():
                for md_file in sorted(scenes_dir.glob("*.md")):
                    try:
                        data = self.parser.parse_manuscript_scene(md_file)
                        self._ingest_manuscript_scene(session, data)
                        result.files_ingested += 1
                        result.updates["scenes"] += 1
                    except Exception as e:
                        result.errors.append(
                            f"Failed to ingest {md_file.name}: {e}"
                        )

            session.commit()

            # Clear deck sync-pending marker after successful ingest
            marker = self.wiki_dir / ".sync-pending"
            if marker.exists():
                marker.unlink()
                self.logger.info(
                    "Cleared .sync-pending marker — deck edits ingested"
                )

        self.logger.info(
            f"Ingested {result.files_ingested} files"
        )

    def _ingest_chapter(
        self, session: Any, data: ChapterData
    ) -> None:
        """
        Update a chapter entity from parsed wiki data.

        Resolves wikilinks to entity IDs and updates scalar fields
        and M2M relationships.

        Args:
            session: SQLAlchemy session
            data: Parsed chapter data

        Raises:
            ValueError: If chapter not found in database
        """
        chapter = session.query(Chapter).filter(
            Chapter.title == data.title
        ).first()

        if not chapter:
            raise ValueError(f"Chapter not found: {data.title}")

        # Update scalar fields
        chapter.type = ChapterType(data.chapter_type)
        chapter.status = ChapterStatus(data.status)

        # Resolve part
        if data.part_name:
            part_id = self.parser.resolve_part(session, data.part_name)
            chapter.part_id = part_id
        else:
            chapter.part_id = None

        # Update characters M2M
        chapter.characters.clear()
        for char_name, _ in data.characters:
            char = session.query(Character).filter(
                Character.name == char_name
            ).first()
            if char:
                chapter.characters.append(char)

        # Update arcs M2M
        chapter.arcs.clear()
        for arc_name in data.arcs:
            arc = session.query(Arc).filter(Arc.name == arc_name).first()
            if arc:
                chapter.arcs.append(arc)

        # Update poems M2M
        chapter.poems.clear()
        for poem_title in data.poems:
            poem = session.query(Poem).filter(
                Poem.title == poem_title
            ).first()
            if poem:
                chapter.poems.append(poem)

        # Update references
        for ref in chapter.references[:]:
            session.delete(ref)
        session.flush()

        for ref_data in data.references:
            source = session.query(ReferenceSource).filter(
                ReferenceSource.title == ref_data.source_title
            ).first()
            if source:
                mode = ReferenceMode(ref_data.mode)
                manuscript_ref = ManuscriptReference(
                    chapter_id=chapter.id,
                    source_id=source.id,
                    mode=mode,
                    content=ref_data.content,
                )
                session.add(manuscript_ref)

    def _ingest_character(
        self, session: Any, data: CharacterData
    ) -> None:
        """
        Update a character entity from parsed wiki data.

        Updates scalar fields and person-character mappings.

        Args:
            session: SQLAlchemy session
            data: Parsed character data

        Raises:
            ValueError: If character not found in database
        """
        character = session.query(Character).filter(
            Character.name == data.name
        ).first()

        if not character:
            raise ValueError(f"Character not found: {data.name}")

        # Update scalar fields
        character.role = data.role
        character.is_narrator = data.is_narrator
        character.description = data.description

        # Update person mappings
        for mapping in character.person_mappings[:]:
            session.delete(mapping)
        session.flush()

        for pm_data in data.based_on:
            person = session.query(Person).filter(
                Person.display_name == pm_data.person_name
            ).first()
            if person:
                contribution = ContributionType(pm_data.contribution)
                mapping = PersonCharacterMap(
                    person_id=person.id,
                    character_id=character.id,
                    contribution=contribution,
                )
                session.add(mapping)

    def _ingest_manuscript_scene(
        self, session: Any, data: ManuscriptSceneData
    ) -> None:
        """
        Update a manuscript scene entity from parsed wiki data.

        Updates scalar fields, chapter assignment, and source links.

        Args:
            session: SQLAlchemy session
            data: Parsed manuscript scene data

        Raises:
            ValueError: If manuscript scene not found in database
        """
        ms_scene = session.query(ManuscriptScene).filter(
            ManuscriptScene.name == data.name
        ).first()

        if not ms_scene:
            raise ValueError(f"ManuscriptScene not found: {data.name}")

        # Update scalar fields
        ms_scene.origin = SceneOrigin(data.origin)
        ms_scene.status = SceneStatus(data.status)
        ms_scene.description = data.description

        # Resolve chapter
        if data.chapter_name:
            chapter = session.query(Chapter).filter(
                Chapter.title == data.chapter_name
            ).first()
            ms_scene.chapter_id = chapter.id if chapter else None
        else:
            ms_scene.chapter_id = None

        # Update sources
        for source in ms_scene.sources[:]:
            session.delete(source)
        session.flush()

        for src_data in data.sources:
            source_type_str = src_data.source_type.lower()
            try:
                source_type = SourceType(source_type_str)
            except ValueError:
                continue

            new_source = ManuscriptSource(
                manuscript_scene_id=ms_scene.id,
                source_type=source_type,
            )

            if source_type == SourceType.EXTERNAL:
                new_source.external_note = src_data.reference
            elif src_data.entry_date:
                entry = session.query(Entry).filter(
                    Entry.date == src_data.entry_date
                ).first()
                if entry:
                    new_source.entry_id = entry.id

            session.add(new_source)

    def _regenerate(self, result: SyncResult) -> None:
        """
        Regenerate all manuscript wiki pages from database.

        Uses WikiExporter with change detection to avoid
        overwriting files that haven't changed.

        Args:
            result: SyncResult to accumulate statistics
        """
        from dev.wiki.exporter import WikiExporter

        self.logger.info("Regenerating manuscript pages...")

        exporter = WikiExporter(
            self.db,
            output_dir=self.wiki_dir,
            logger=self.logger,
        )
        exporter.generate_all(section="manuscript")

        result.files_generated = exporter.stats.get("files_written", 0)
        result.files_changed = exporter.stats.get("files_changed", 0)

        self.logger.info(
            f"Regenerated {result.files_generated} files "
            f"({result.files_changed} changed)"
        )
