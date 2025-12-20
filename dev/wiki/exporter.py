#!/usr/bin/env python3
"""
exporter.py
-----------
Export database entities to wiki markdown files.

Provides a unified exporter that handles all entity types using
configuration objects and Jinja2 templates. This replaces the
individual wiki dataclass exporters with a single, clean interface.

Usage:
    exporter = WikiExporter(db, wiki_dir, logger)
    stats = exporter.export_entity_type(PERSON_CONFIG)
    stats = exporter.export_all()
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from typing import Optional

# --- Local imports ---
from dev.core.logging_manager import PalimpsestLogger
from dev.core.cli import ConversionStats
from dev.database.manager import PalimpsestDB

from .renderer import WikiRenderer
from .configs import EntityConfig, ALL_CONFIGS


def write_if_changed(path: Path, content: str) -> str:
    """
    Write content to file only if it differs from existing content.

    Args:
        path: Target file path
        content: Content to write

    Returns:
        Status string: "created", "updated", or "unchanged"
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return "unchanged"
        path.write_text(content, encoding="utf-8")
        return "updated"
    else:
        path.write_text(content, encoding="utf-8")
        return "created"


class WikiExporter:
    """
    Export database entities to wiki markdown using Jinja2 templates.

    This class provides a unified interface for exporting all entity types,
    replacing the individual wiki dataclass exporters with a single
    configuration-driven implementation.

    Attributes:
        db: Database manager instance
        wiki_dir: Root wiki directory
        renderer: Jinja2 wiki renderer
        logger: Optional logger for operation tracking
    """

    def __init__(
        self,
        db: PalimpsestDB,
        wiki_dir: Path,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize the wiki exporter.

        Args:
            db: Database manager instance
            wiki_dir: Root wiki directory for output
            logger: Optional logger for operation tracking
        """
        self.db = db
        self.wiki_dir = wiki_dir
        self.renderer = WikiRenderer(wiki_dir)
        self.logger = logger

    def export_entity_type(
        self,
        config: EntityConfig,
        force: bool = False,
    ) -> ConversionStats:
        """
        Export all entities of a given type to wiki pages.

        Args:
            config: Entity configuration defining query and template
            force: If True, regenerate files even if unchanged

        Returns:
            Statistics with counts of created/updated/skipped files
        """
        stats = ConversionStats()

        if self.logger:
            self.logger.log_info(f"Exporting {config.plural}...")

        with self.db.session_scope() as session:
            entities = config.query(session)

            if not entities:
                if self.logger:
                    self.logger.log_info(f"No {config.plural} to export")
                return stats

            for entity in entities:
                self._export_entity(entity, config, force, stats)

        if self.logger:
            self.logger.log_info(
                f"Exported {config.plural}: "
                f"{stats.created} created, {stats.updated} updated, "
                f"{stats.skipped} unchanged"
            )

        return stats

    def _export_entity(
        self,
        entity,
        config: EntityConfig,
        force: bool,
        stats: ConversionStats,
    ) -> None:
        """
        Export a single entity to its wiki page.

        Args:
            entity: Database entity to export
            config: Entity configuration
            force: If True, regenerate even if unchanged
            stats: Statistics object to update
        """
        # Determine output path
        slug = config.get_slug(entity)
        output_path = self.wiki_dir / config.folder / f"{slug}.md"

        # Render template
        content = self.renderer.render(
            config.template,
            output_path=output_path,
            entity=entity,
            config=config,
        )

        # Write file
        if force:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
            stats.updated += 1
        else:
            status = write_if_changed(output_path, content)
            if status == "created":
                stats.created += 1
            elif status == "updated":
                stats.updated += 1
            else:
                stats.skipped += 1

    def export_all(self, force: bool = False) -> ConversionStats:
        """
        Export all entity types to wiki.

        Args:
            force: If True, regenerate all files

        Returns:
            Combined statistics for all entity types
        """
        total_stats = ConversionStats()

        for config in ALL_CONFIGS:
            stats = self.export_entity_type(config, force)
            total_stats.created += stats.created
            total_stats.updated += stats.updated
            total_stats.skipped += stats.skipped

        if self.logger:
            self.logger.log_info(
                f"Wiki export complete: "
                f"{total_stats.created} created, {total_stats.updated} updated, "
                f"{total_stats.skipped} unchanged"
            )

        return total_stats

    def export_indexes(self, force: bool = False) -> ConversionStats:
        """
        Export index pages for all entity types.

        Args:
            force: If True, regenerate all indexes

        Returns:
            Statistics for index generation
        """
        stats = ConversionStats()

        # Index generation will use index templates
        # Each index queries grouped entities and renders indexes/{type}.jinja2

        return stats
