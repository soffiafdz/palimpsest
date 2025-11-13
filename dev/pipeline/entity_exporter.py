"""
entity_exporter.py
------------------
Generic entity exporter for wiki pages.

This module provides a generic, configuration-driven approach to exporting
database entities to vimwiki pages. Instead of duplicating export logic for
each entity type, all entities are exported through a single GenericEntityExporter
configured with entity-specific metadata.

Architecture:
- EntityConfig: Metadata describing how to export an entity type
- GenericEntityExporter: Generic exporter that works with any EntityConfig
- ENTITY_REGISTRY: Registry of all entity configurations

This reduces sql2wiki.py from ~2,600 lines to ~800 lines by eliminating
repetitive export functions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Callable, Type, Dict
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from dev.database.manager import PalimpsestDB
from dev.core.logging_manager import PalimpsestLogger
from dev.core.cli_stats import ConversionStats
from dev.utils.wiki import relative_link


@dataclass
class EntityConfig:
    """
    Configuration for exporting an entity type.

    Defines all metadata needed to export a database entity type to wiki pages:
    - Identity (name, plural form)
    - Database model and wiki dataclass
    - File paths and organization
    - Eager loading requirements
    - Custom index builder (if needed)
    - Sorting preferences
    """

    # Entity identification
    name: str                               # Singular: "person", "theme", "entry"
    plural: str                             # Plural: "people", "themes", "entries"

    # Database model
    db_model: Type                          # DBPerson, DBTheme, DBEntry

    # Wiki dataclass
    wiki_class: Type                        # WikiPerson, WikiTheme, WikiEntry

    # Paths
    output_subdir: str                      # "people", "themes", "entries"
    index_filename: str                     # "people.md", "themes.md"

    # Eager loading (list of relationship names)
    eager_loads: List[str]                  # ["entries", "manuscript"]

    # Index building
    index_builder: Optional[Callable] = None  # Custom builder or None for default

    # Sorting
    sort_by: str = "name"                   # Field to sort wiki entities by
    order_by: str = "name"                  # Field to order database query by


def write_if_changed(path: Path, content: str, force: bool = False) -> str:
    """
    Write file only if content has changed.

    Args:
        path: File path to write
        content: New content
        force: Force write even if unchanged

    Returns:
        Status: "created", "updated", or "skipped"
    """
    file_existed = path.exists()

    if file_existed and not force:
        # Check if content changed
        existing_content = path.read_text(encoding="utf-8")
        if existing_content == content:
            return "skipped"

    # Write file
    path.write_text(content, encoding="utf-8")

    return "updated" if file_existed else "created"


class GenericEntityExporter:
    """
    Generic exporter for any wiki entity type.

    This class provides a unified export interface that works with any entity
    type. The behavior is controlled by the EntityConfig, which specifies:
    - Which database model to query
    - Which wiki dataclass to create
    - How to build indexes
    - What relationships to eager load

    Usage:
        config = ENTITY_REGISTRY["people"]
        exporter = GenericEntityExporter(config)
        stats = exporter.export_all(db, wiki_dir, journal_dir)
    """

    def __init__(self, config: EntityConfig):
        """Initialize with entity configuration."""
        self.config = config

    def export_single(
        self,
        db_entity: Any,
        wiki_dir: Path,
        journal_dir: Path,
        force: bool = False,
        logger: Optional[PalimpsestLogger] = None,
    ) -> str:
        """
        Export a single entity to wiki page.

        Works for ANY entity type by using the wiki_class.from_database()
        and to_wiki() methods defined in each WikiEntity dataclass.

        Args:
            db_entity: Database entity (DBPerson, DBTheme, etc.)
            wiki_dir: Vimwiki root directory
            journal_dir: Journal entries directory
            force: Force write even if unchanged
            logger: Optional logger

        Returns:
            Status: "created", "updated", or "skipped"
        """
        # Convert database entity to wiki entity
        wiki_entity = self.config.wiki_class.from_database(
            db_entity, wiki_dir, journal_dir
        )

        # Ensure output directory exists
        wiki_entity.path.parent.mkdir(parents=True, exist_ok=True)

        # Generate wiki content
        content = "\n".join(wiki_entity.to_wiki())

        # Write if changed
        status = write_if_changed(wiki_entity.path, content, force)

        if logger:
            entity_name = getattr(wiki_entity, "name", str(wiki_entity.path.stem))
            logger.log_debug(f"{self.config.name} {entity_name}: {status}")

        return status

    def build_index(
        self,
        entities: List[Any],
        wiki_dir: Path,
        force: bool = False,
        logger: Optional[PalimpsestLogger] = None,
    ) -> str:
        """
        Build index page for all entities.

        Uses custom builder if specified in config, otherwise uses default
        simple alphabetical index.

        Args:
            entities: List of wiki entities (WikiPerson, WikiTheme, etc.)
            wiki_dir: Vimwiki root directory
            force: Force write even if unchanged
            logger: Optional logger

        Returns:
            Status: "created", "updated", or "skipped"
        """
        if self.config.index_builder:
            # Use custom index builder
            return self.config.index_builder(entities, wiki_dir, force, logger)
        else:
            # Use default index builder
            return self._build_default_index(entities, wiki_dir, force, logger)

    def _build_default_index(
        self,
        entities: List[Any],
        wiki_dir: Path,
        force: bool = False,
        logger: Optional[PalimpsestLogger] = None,
    ) -> str:
        """
        Build default simple alphabetical index.

        Creates a basic index with:
        - Title
        - Alphabetical list of all entities
        - Statistics

        Args:
            entities: List of wiki entities
            wiki_dir: Vimwiki root directory
            force: Force write even if unchanged
            logger: Optional logger

        Returns:
            Status: "created", "updated", or "skipped"
        """
        index_path = wiki_dir / self.config.index_filename

        lines = [
            f"# Palimpsest — {self.config.plural.title()}",
            "",
            f"Index of all {self.config.plural}.",
            "",
        ]

        # Sort entities
        sorted_entities = sorted(
            entities,
            key=lambda e: getattr(e, self.config.sort_by, "").lower()
        )

        # List all entities with links
        for entity in sorted_entities:
            link = relative_link(index_path, entity.path)
            name = getattr(entity, "name", entity.path.stem)
            lines.append(f"- [[{link}|{name}]]")

        lines.extend([
            "",
            "---",
            "",
            "## Statistics",
            "",
            f"- Total {self.config.plural}: {len(entities)}",
            "",
        ])

        # Write
        content = "\n".join(lines)
        status = write_if_changed(index_path, content, force)

        if logger:
            if status in ("created", "updated"):
                logger.log_info(f"{self.config.plural} index {status}")
            else:
                logger.log_debug(f"{self.config.plural} index unchanged")

        return status

    def export_all(
        self,
        db: PalimpsestDB,
        wiki_dir: Path,
        journal_dir: Path,
        force: bool = False,
        logger: Optional[PalimpsestLogger] = None,
    ) -> ConversionStats:
        """
        Export all entities of this type from database.

        This is the main entry point for batch export. It:
        1. Queries database with eager loading
        2. Exports each entity individually
        3. Builds the index page
        4. Returns statistics

        Args:
            db: Database manager
            wiki_dir: Vimwiki root directory
            journal_dir: Journal entries directory
            force: Force write all files
            logger: Optional logger

        Returns:
            ConversionStats with results
        """
        stats = ConversionStats()

        if logger:
            logger.log_operation(
                f"export_{self.config.plural}_start",
                {"wiki_dir": str(wiki_dir)}
            )

        with db.session_scope() as session:
            # Build query with eager loading
            query = select(self.config.db_model)

            # Add eager loads for relationships
            for load_path in self.config.eager_loads:
                # Handle nested loads (e.g., "locations.city")
                if "." in load_path:
                    parts = load_path.split(".")
                    attr = getattr(self.config.db_model, parts[0])
                    load = joinedload(attr)
                    for part in parts[1:]:
                        # Get the related model's attribute
                        load = load.joinedload(getattr(attr.property.mapper.class_, part))
                    query = query.options(load)
                else:
                    query = query.options(
                        joinedload(getattr(self.config.db_model, load_path))
                    )

            # Add ordering
            query = query.order_by(getattr(self.config.db_model, self.config.order_by))

            # Execute query
            db_entities = session.execute(query).scalars().unique().all()

            if not db_entities:
                if logger:
                    logger.log_warning(f"No {self.config.plural} found in database")
                return stats

            if logger:
                logger.log_info(f"Found {len(db_entities)} {self.config.plural} in database")

            # Export each entity
            wiki_entities = []
            for db_entity in db_entities:
                stats.files_processed += 1

                try:
                    status = self.export_single(
                        db_entity, wiki_dir, journal_dir, force, logger
                    )

                    if status == "created":
                        stats.entries_created += 1
                    elif status == "updated":
                        stats.entries_updated += 1
                    elif status == "skipped":
                        stats.entries_skipped += 1

                    # Create wiki entity for index building
                    wiki_entity = self.config.wiki_class.from_database(
                        db_entity, wiki_dir, journal_dir
                    )
                    wiki_entities.append(wiki_entity)

                except Exception as e:
                    stats.errors += 1
                    if logger:
                        logger.log_error(e, {
                            "operation": f"export_{self.config.name}",
                            "entity": str(db_entity)
                        })

            # Build index
            try:
                self.build_index(wiki_entities, wiki_dir, force, logger)
            except Exception as e:
                stats.errors += 1
                if logger:
                    logger.log_error(e, {
                        "operation": f"build_{self.config.plural}_index"
                    })

        if logger:
            logger.log_operation(
                f"export_{self.config.plural}_complete",
                {"stats": stats.summary()}
            )

        return stats


# Global registry - will be populated by sql2wiki.py with actual models/classes
ENTITY_REGISTRY: Dict[str, EntityConfig] = {}


def register_entity(key: str, config: EntityConfig) -> None:
    """Register an entity configuration."""
    ENTITY_REGISTRY[key] = config


def get_exporter(entity_type: str) -> GenericEntityExporter:
    """
    Get exporter for entity type.

    Args:
        entity_type: Entity type key (e.g., "people", "themes")

    Returns:
        GenericEntityExporter configured for that entity type

    Raises:
        KeyError: If entity type not registered
    """
    if entity_type not in ENTITY_REGISTRY:
        raise KeyError(f"Unknown entity type: {entity_type}")

    config = ENTITY_REGISTRY[entity_type]
    return GenericEntityExporter(config)
