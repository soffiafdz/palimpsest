#!/usr/bin/env python3
"""
sync.py
-------
Manuscript wiki sync orchestrator.

Manages the validate → YAML import → regenerate cycle for manuscript
wiki pages. Manuscript metadata is edited via YAML files (floating
window in nvim), and wiki pages are regenerated from DB state.

Key Features:
    - Pre-sync validation gate (errors block sync)
    - YAML metadata import (via MetadataImporter)
    - Change detection during regeneration (only overwrites if different)
    - Supports partial operations (ingest-only, generate-only)

Sync Cycle:
    1. Validate: Run validator on all manuscript wiki files
    2. Ingest: Import YAML metadata → update DB entities
    3. Regenerate: Render all manuscript pages from DB

Usage:
    from dev.wiki.sync import WikiSync

    sync = WikiSync(db)
    sync.sync_manuscript()                    # Full cycle
    sync.sync_manuscript(ingest_only=True)    # YAML → DB only
    sync.sync_manuscript(generate_only=True)  # DB → Wiki only

Dependencies:
    - MetadataImporter for YAML → DB ingestion
    - WikiValidator for pre-sync validation
    - WikiExporter for DB → wiki generation
    - PalimpsestDB for database operations
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from typing import Dict, List, Optional

# --- Local imports ---
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.core.paths import WIKI_DIR
from dev.database.manager import PalimpsestDB
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
    Orchestrates manuscript wiki synchronization.

    Coordinates validation, YAML metadata import, and wiki regeneration
    for manuscript pages (chapters, characters, manuscript scenes).

    Attributes:
        db: PalimpsestDB instance
        wiki_dir: Root wiki directory
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
        self.validator = WikiValidator(db)
        self.logger = safe_logger(logger)

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
            ingest_only: Only import YAML → DB (skip regeneration)
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
            self._regenerate(result)
            return result

        # Step 1: Validate
        self._validate(manuscript_dir, result)
        if not result.success:
            return result

        # Step 2: Ingest via YAML metadata import
        self._ingest(result)
        if not result.success:
            return result

        # Step 3: Regenerate (unless ingest-only)
        if not ingest_only:
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

    def _ingest(self, result: SyncResult) -> None:
        """
        Import manuscript YAML metadata files into the database.

        Uses MetadataImporter for chapters, characters, and scenes.
        Each entity type is imported separately with error tracking.

        Args:
            result: SyncResult to accumulate statistics
        """
        from dev.wiki.metadata import MetadataImporter

        self.logger.info("Ingesting manuscript YAML metadata...")

        importer = MetadataImporter(self.db, logger=self.logger)

        for entity_type in ("chapters", "characters", "scenes"):
            try:
                stats = importer.import_all(entity_type=entity_type)
                count = stats.get("imported", 0)
                result.files_ingested += count
                result.updates[entity_type] = count
                if stats.get("errors", 0) > 0:
                    result.warnings.append(
                        f"{entity_type}: {stats['errors']} import errors"
                    )
            except Exception as e:
                result.errors.append(
                    f"Failed to import {entity_type}: {e}"
                )

        self.logger.info(
            f"Ingested {result.files_ingested} files"
        )

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
