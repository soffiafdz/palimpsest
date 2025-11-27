#!/usr/bin/env python3
"""
entity_importer.py
------------------

Generic entity import framework to eliminate code duplication in wiki2sql.py.

This module provides a configuration-driven approach for importing wiki edits
back to the database, replacing 600+ lines of duplicated import functions.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Type

from dev.core.logging_manager import PalimpsestLogger
from dev.database.manager import PalimpsestDB


@dataclass
class ImportStats:
    """Statistics from import operation."""

    files_processed: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    errors: int = 0


@dataclass
class EntityImportConfig:
    """
    Configuration for entity import operations.

    This dataclass defines how to import a specific entity type from wiki
    pages back to the database, eliminating the need for separate import functions.

    Attributes:
        entity_name: Singular name (e.g., "person", "entry")
        entity_plural: Plural name (e.g., "people", "entries")
        wiki_class: WikiEntity class with from_file() method
        wiki_subdir: Subdirectory within wiki (e.g., "people", "entries")
        file_pattern: Glob pattern for finding wiki files (default: "*.md")
        recursive: If True, use rglob() instead of glob() (default: False)
        entity_updater: Optional function that takes (wiki_entity, wiki_file, db, logger)
            and returns status ("updated", "skipped", "error").
            If None, uses default behavior (always skip - for metadata-only entities)
    """
    entity_name: str
    entity_plural: str
    wiki_class: Type
    wiki_subdir: str
    file_pattern: str = "*.md"
    recursive: bool = False
    entity_updater: Optional[Callable[[Any, Path, PalimpsestDB, Optional[PalimpsestLogger]], str]] = None


class EntityImporter:
    """
    Generic entity importer that handles wiki-to-database sync.

    This class eliminates code duplication by providing a single implementation
    that works with any entity type via configuration objects.

    Example:
        >>> from dev.pipeline.entity_import_configs import PERSON_IMPORT_CONFIG
        >>> importer = EntityImporter(db, wiki_dir, logger)
        >>> stats = importer.import_entities(PERSON_IMPORT_CONFIG)
    """

    def __init__(
        self,
        db: PalimpsestDB,
        wiki_dir: Path,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize the entity importer.

        Args:
            db: Database manager instance
            wiki_dir: Root wiki directory
            logger: Optional logger for operation tracking
        """
        self.db = db
        self.wiki_dir = wiki_dir
        self.logger = logger

    def import_entities(
        self,
        config: EntityImportConfig,
    ) -> ImportStats:
        """
        Import entity edits from wiki pages using the provided configuration.

        This single method replaces all the duplicated import_* functions
        in wiki2sql.py by using configuration objects to specify behavior.

        Args:
            config: Import configuration specifying entity type and behavior

        Returns:
            ImportStats with counts of updated/skipped/error files

        Example:
            >>> config = EntityImportConfig(
            ...     entity_name="person",
            ...     entity_plural="people",
            ...     wiki_class=WikiPerson,
            ...     wiki_subdir="people",
            ... )
            >>> stats = importer.import_entities(config)
        """
        stats = ImportStats()

        self._log_start(config)

        # Find wiki files
        wiki_files = self._find_wiki_files(config)
        stats.files_processed = len(wiki_files)

        if not wiki_files:
            self._log_no_files(config)
            return stats

        # Process each wiki file
        for wiki_file in wiki_files:
            status = self._import_single_entity(wiki_file, config)
            self._update_stats(stats, status)

        self._log_completion(config, stats)
        return stats

    def _find_wiki_files(self, config: EntityImportConfig) -> list[Path]:
        """
        Find all wiki files for the entity type.

        Args:
            config: Import configuration

        Returns:
            List of wiki file paths
        """
        entity_dir = self.wiki_dir / config.wiki_subdir

        if not entity_dir.exists():
            if self.logger:
                self.logger.log_warning(
                    f"{config.entity_plural.title()} directory not found: {entity_dir}"
                )
            return []

        if config.recursive:
            return list(entity_dir.rglob(config.file_pattern))
        else:
            return list(entity_dir.glob(config.file_pattern))

    def _import_single_entity(
        self,
        wiki_file: Path,
        config: EntityImportConfig,
    ) -> str:
        """
        Import a single entity from wiki file.

        Args:
            wiki_file: Path to wiki markdown file
            config: Import configuration

        Returns:
            Status: "updated", "skipped", or "error"
        """
        try:
            # Parse wiki file
            wiki_entity = config.wiki_class.from_file(wiki_file)
            if not wiki_entity:
                return "skipped"

            # Update database using custom updater or default behavior
            if config.entity_updater:
                # Custom updater can optionally take wiki_file for hash calculation
                return config.entity_updater(wiki_entity, wiki_file, self.db, self.logger)
            else:
                # Default: metadata-only entities (no database fields to update)
                return "skipped"

        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Error importing {wiki_file}: {e}")
            return "error"

    def _update_stats(self, stats: ImportStats, status: str) -> None:
        """Update statistics based on import status."""
        if status == "updated":
            stats.records_updated += 1
        elif status == "skipped":
            stats.records_skipped += 1
        elif status == "error":
            stats.errors += 1

    # Logging methods (null-safe, no conditional checks needed)

    def _log_start(self, config: EntityImportConfig) -> None:
        """Log import operation start."""
        if self.logger:
            self.logger.log_operation(
                f"import_{config.entity_plural}_start",
                {"wiki_dir": str(self.wiki_dir)}
            )

    def _log_completion(self, config: EntityImportConfig, stats: ImportStats) -> None:
        """Log import operation completion."""
        if self.logger:
            self.logger.log_operation(
                f"import_{config.entity_plural}_complete",
                {
                    "processed": stats.files_processed,
                    "updated": stats.records_updated,
                    "skipped": stats.records_skipped,
                    "errors": stats.errors,
                }
            )

    def _log_no_files(self, config: EntityImportConfig) -> None:
        """Log warning when no files found."""
        if self.logger:
            self.logger.log_warning(
                f"No {config.entity_plural} wiki files found"
            )


def import_entities_batch(
    db: PalimpsestDB,
    wiki_dir: Path,
    configs: list[EntityImportConfig],
    logger: Optional[PalimpsestLogger] = None,
) -> dict[str, ImportStats]:
    """
    Import multiple entity types in batch.

    Convenience function for importing multiple entity types in a single call.

    Args:
        db: Database manager
        wiki_dir: Wiki root directory
        configs: List of entity import configurations
        logger: Optional logger

    Returns:
        Dictionary mapping entity_plural to ImportStats

    Example:
        >>> from dev.pipeline.entity_import_configs import ALL_JOURNAL_CONFIGS
        >>> results = import_entities_batch(db, wiki_dir, ALL_JOURNAL_CONFIGS)
        >>> print(f"People: {results['people'].records_updated} updated")
    """
    importer = EntityImporter(db, wiki_dir, logger)
    results = {}

    for config in configs:
        stats = importer.import_entities(config)
        results[config.entity_plural] = stats

    return results
