"""
Entry Export with Navigation
-----------------------------

Custom export function for journal entries that includes chronological
navigation links (prev/next).

Functions:
    - export_entries_with_navigation: Export all entries with navigation
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from dev.database.manager import PalimpsestDB
from dev.database.models import Entry as DBEntry
from dev.core.logging_manager import PalimpsestLogger
from dev.core.cli import ConversionStats
from dev.dataclasses.wiki_entry import Entry as WikiEntry
from dev.builders.wiki import write_if_changed

if TYPE_CHECKING:
    from dev.builders.wiki import GenericEntityExporter


def export_entries_with_navigation(
    exporter: GenericEntityExporter,
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> ConversionStats:
    """
    Custom export function for entries that includes prev/next navigation.

    This function exports all entries with chronological navigation links,
    allowing readers to navigate between entries sequentially.

    Args:
        exporter: The GenericEntityExporter instance
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
        logger.log_operation("export_entries_start", {"wiki_dir": str(wiki_dir)})

    with db.session_scope() as session:
        # Query all entries sorted by date
        query = select(DBEntry)

        # Add eager loads
        for load_path in exporter.config.eager_loads:
            if "." in load_path:
                parts = load_path.split(".")
                attr = getattr(DBEntry, parts[0])
                load = joinedload(attr)
                for part in parts[1:]:
                    load = load.joinedload(getattr(attr.property.mapper.class_, part))
                query = query.options(load)
            else:
                query = query.options(joinedload(getattr(DBEntry, load_path)))

        # Order by date
        query = query.order_by(DBEntry.date)

        # Execute query
        db_entries = session.execute(query).scalars().unique().all()

        if not db_entries:
            if logger:
                logger.log_warning("No entries found in database")
            return stats

        if logger:
            logger.log_info(f"Found {len(db_entries)} entries in database")

        # Export each entry with prev/next navigation
        wiki_entities = []
        for i, db_entry in enumerate(db_entries):
            stats.files_processed += 1

            try:
                # Get prev/next entries
                prev_entry = db_entries[i - 1] if i > 0 else None
                next_entry = db_entries[i + 1] if i < len(db_entries) - 1 else None

                # Convert to wiki entity with navigation
                wiki_entry = WikiEntry.from_database(
                    db_entry, wiki_dir, journal_dir, prev_entry, next_entry
                )

                # Ensure output directory exists
                wiki_entry.path.parent.mkdir(parents=True, exist_ok=True)

                # Generate wiki content
                content = "\n".join(wiki_entry.to_wiki())

                # Write if changed
                status = write_if_changed(wiki_entry.path, content, force)

                if status == "created":
                    stats.entries_created += 1
                elif status == "updated":
                    stats.entries_updated += 1
                elif status == "skipped":
                    stats.entries_skipped += 1

                if logger:
                    logger.log_debug(f"entry {wiki_entry.date}: {status}")

                wiki_entities.append(wiki_entry)

            except Exception as e:
                stats.errors += 1
                if logger:
                    logger.log_error(e, {
                        "operation": "export_entry",
                        "entity": str(db_entry)
                    })

        # Build index
        if exporter.config.index_builder:
            exporter.config.index_builder(
                wiki_entities, wiki_dir, force, logger
            )
        else:
            exporter.build_index(
                wiki_entities, wiki_dir, force, logger
            )

    return stats
