#!/usr/bin/env python3
"""
entity_exporter.py
------------------

Generic entity export framework to eliminate code duplication in ms2wiki.py.

This module provides a configuration-driven approach for exporting database
entities to wiki pages, replacing 400+ lines of duplicated export functions.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Type

from sqlalchemy import Select
from sqlalchemy.orm import Session

from dev.core.logging_manager import PalimpsestLogger
from dev.core.cli import ConversionStats
from dev.database.manager import PalimpsestDB
from dev.builders.wiki import write_if_changed


@dataclass
class EntityExportConfig:
    """
    Configuration for entity export operations.

    This dataclass defines how to export a specific entity type from the
    database to wiki pages, eliminating the need for separate export functions.

    Attributes:
        entity_name: Singular name (e.g., "character", "event")
        entity_plural: Plural name (e.g., "characters", "events")
        db_model: SQLAlchemy ORM model class
        wiki_class: WikiEntity subclass for serialization
        query_builder: Function that constructs the SQLAlchemy query
        name_extractor: Function to extract entity name for logging
        output_subdir: Optional subdirectory within wiki (e.g., "manuscript")
        entity_converter: Optional custom converter function that takes
            (db_entity, wiki_dir, journal_dir) and returns wiki_entity.
            If None, uses default: wiki_class.from_database(db_entity, wiki_dir, journal_dir)
    """
    entity_name: str
    entity_plural: str
    db_model: Type
    wiki_class: Type
    query_builder: Callable[[Session], Select]
    name_extractor: Callable[[Any], str]
    output_subdir: Optional[str] = None
    entity_converter: Optional[Callable[[Any, Path, Path], Any]] = None


class EntityExporter:
    """
    Generic entity exporter that handles database-to-wiki conversion.

    This class eliminates code duplication by providing a single implementation
    that works with any entity type via configuration objects.

    Example:
        >>> from dev.pipeline.entity_configs import CHARACTER_EXPORT_CONFIG
        >>> exporter = EntityExporter(db, wiki_dir, journal_dir, logger)
        >>> stats = exporter.export_entities(CHARACTER_EXPORT_CONFIG, force=False)
    """

    def __init__(
        self,
        db: PalimpsestDB,
        wiki_dir: Path,
        journal_dir: Path,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize the entity exporter.

        Args:
            db: Database manager instance
            wiki_dir: Root wiki directory
            journal_dir: Journal markdown directory
            logger: Optional logger for operation tracking
        """
        self.db = db
        self.wiki_dir = wiki_dir
        self.journal_dir = journal_dir
        self.logger = logger

    def export_entities(
        self,
        config: EntityExportConfig,
        force: bool = False,
    ) -> ConversionStats:
        """
        Export entities to wiki pages using the provided configuration.

        This single method replaces all the duplicated export_* functions
        in ms2wiki.py by using configuration objects to specify behavior.

        Args:
            config: Export configuration specifying entity type and behavior
            force: If True, regenerate all files even if unchanged

        Returns:
            ConversionStats with counts of created/updated/skipped files

        Example:
            >>> config = EntityExportConfig(
            ...     entity_name="character",
            ...     entity_plural="characters",
            ...     db_model=DBManuscriptPerson,
            ...     wiki_class=WikiCharacter,
            ...     query_builder=lambda s: select(DBManuscriptPerson)...,
            ...     name_extractor=lambda e: e.person.display_name,
            ... )
            >>> stats = exporter.export_entities(config)
        """
        stats = ConversionStats()

        self._log_start(config)

        with self.db.session_scope() as session:
            # Execute configured query
            entities = self._fetch_entities(session, config)

            if not entities:
                self._log_no_entities(config)
                return stats

            # Process each entity
            for entity in entities:
                self._process_entity(entity, config, force, stats)

        self._log_completion(config, stats)
        return stats

    def _fetch_entities(
        self,
        session: Session,
        config: EntityExportConfig,
    ) -> list[Any]:
        """
        Fetch entities from database using configured query.

        Args:
            session: Active database session
            config: Export configuration

        Returns:
            List of ORM entity instances
        """
        query = config.query_builder(session)
        return session.execute(query).unique().scalars().all()

    def _process_entity(
        self,
        db_entity: Any,
        config: EntityExportConfig,
        force: bool,
        stats: ConversionStats,
    ) -> None:
        """
        Process a single entity: convert to wiki and write to file.

        Args:
            db_entity: Database ORM instance
            config: Export configuration
            force: Force regeneration flag
            stats: Statistics tracker (updated in place)
        """
        stats.files_processed += 1

        try:
            # Convert database entity to wiki entity
            if config.entity_converter:
                # Use custom converter if provided
                wiki_entity = config.entity_converter(
                    db_entity,
                    self.wiki_dir,
                    self.journal_dir,
                )
            else:
                # Use default conversion
                wiki_entity = config.wiki_class.from_database(
                    db_entity,
                    self.wiki_dir,
                    self.journal_dir,
                )

            # Write to file and track status
            status = self._write_wiki_file(wiki_entity, force)
            self._update_stats(stats, status)

            # Log individual entity processing
            entity_name = config.name_extractor(db_entity)
            self._log_entity_status(config, entity_name, status)

        except Exception as e:
            stats.errors += 1
            self._log_entity_error(config, db_entity, e)

    def _write_wiki_file(
        self,
        wiki_entity: Any,
        force: bool,
    ) -> str:
        """
        Write wiki entity to markdown file.

        Args:
            wiki_entity: WikiEntity instance with path and to_wiki() method
            force: If True, write even if content unchanged

        Returns:
            Status string: "created", "updated", or "skipped"
        """
        # Ensure parent directory exists
        wiki_entity.path.parent.mkdir(parents=True, exist_ok=True)

        # Generate markdown content
        content = "\n".join(wiki_entity.to_wiki())

        # Write file (only if changed, unless force=True)
        return write_if_changed(wiki_entity.path, content, force)

    def _update_stats(self, stats: ConversionStats, status: str) -> None:
        """Update statistics based on write status."""
        if status == "created":
            stats.entries_created += 1
        elif status == "updated":
            stats.entries_updated += 1
        elif status == "skipped":
            stats.entries_skipped += 1

    # Logging methods (null-safe, no conditional checks needed)

    def _log_start(self, config: EntityExportConfig) -> None:
        """Log export operation start."""
        if self.logger:
            self.logger.log_operation(
                f"export_{config.entity_plural}_start",
                {"wiki_dir": str(self.wiki_dir)}
            )

    def _log_completion(self, config: EntityExportConfig, stats: ConversionStats) -> None:
        """Log export operation completion."""
        if self.logger:
            self.logger.log_operation(
                f"export_{config.entity_plural}_complete",
                {
                    "processed": stats.files_processed,
                    "created": stats.entries_created,
                    "updated": stats.entries_updated,
                    "skipped": stats.entries_skipped,
                    "errors": stats.errors,
                }
            )

    def _log_no_entities(self, config: EntityExportConfig) -> None:
        """Log warning when no entities found."""
        if self.logger:
            self.logger.log_warning(
                f"No {config.entity_plural} found in database"
            )

    def _log_entity_status(
        self,
        config: EntityExportConfig,
        entity_name: str,
        status: str,
    ) -> None:
        """Log individual entity processing status."""
        if self.logger:
            self.logger.log_debug(
                f"{config.entity_name} {entity_name}: {status}"
            )

    def _log_entity_error(
        self,
        config: EntityExportConfig,
        db_entity: Any,
        error: Exception,
    ) -> None:
        """Log entity processing error."""
        if self.logger:
            try:
                entity_name = config.name_extractor(db_entity)
            except Exception:
                entity_name = "unknown"

            self.logger.log_error(
                error,
                {
                    "operation": f"export_{config.entity_name}",
                    "entity": entity_name,
                }
            )


def export_entities_batch(
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    configs: list[EntityExportConfig],
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> dict[str, ConversionStats]:
    """
    Export multiple entity types in batch.

    Convenience function for exporting multiple entity types in a single call.

    Args:
        db: Database manager
        wiki_dir: Wiki root directory
        journal_dir: Journal directory
        configs: List of entity export configurations
        force: Force regeneration flag
        logger: Optional logger

    Returns:
        Dictionary mapping entity_plural to ConversionStats

    Example:
        >>> from dev.pipeline.entity_configs import ALL_MANUSCRIPT_CONFIGS
        >>> results = export_entities_batch(
        ...     db, wiki_dir, journal_dir, ALL_MANUSCRIPT_CONFIGS
        ... )
        >>> print(f"Characters: {results['characters'].entries_created} created")
    """
    exporter = EntityExporter(db, wiki_dir, journal_dir, logger)
    results = {}

    for config in configs:
        stats = exporter.export_entities(config, force)
        results[config.entity_plural] = stats

    return results
