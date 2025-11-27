#!/usr/bin/env python3
"""
ms2wiki.py
----------
Export manuscript entities to wiki pages (manuscript subwiki).

This pipeline exports only manuscript-designated content (entries, characters,
events, arcs, themes) to the manuscript subwiki at data/wiki/manuscript/.

This is separate from sql2wiki.py which exports ALL journal content to the main wiki.

Usage:
    # Export specific manuscript entity type
    python -m dev.pipeline.ms2wiki export entries
    python -m dev.pipeline.ms2wiki export characters
    python -m dev.pipeline.ms2wiki export arcs

    # Export all manuscript entities
    python -m dev.pipeline.ms2wiki export all

    # Force regeneration
    python -m dev.pipeline.ms2wiki export all --force
"""
from __future__ import annotations

import click
from pathlib import Path
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import joinedload

# Only needed for export_manuscript_entries_with_navigation (special case with nav)
from dev.dataclasses.manuscript_entry import ManuscriptEntry as WikiManuscriptEntry

# Only needed for index/CLI functions
from dev.database.models import Entry as DBEntry
from dev.database.models import Person as DBPerson
from dev.database.models import Event as DBEvent
from dev.database.models_manuscript import (
    ManuscriptEntry as DBManuscriptEntry,
    ManuscriptPerson as DBManuscriptPerson,
    ManuscriptEvent as DBManuscriptEvent,
    Arc as DBArc,
    Theme as DBTheme,
)

from dev.database.manager import PalimpsestDB
from dev.core.paths import LOG_DIR, DB_PATH, WIKI_DIR, MD_DIR, ALEMBIC_DIR
from dev.core.logging_manager import PalimpsestLogger
from dev.core.cli import setup_logger
from dev.core.cli import ConversionStats

from dev.builders.wiki import write_if_changed
from dev.pipeline.entity_exporter import EntityExporter
from dev.pipeline.configs.manuscript_entity_configs import (
    CHARACTER_EXPORT_CONFIG,
    MANUSCRIPT_EVENT_EXPORT_CONFIG,
    ARC_EXPORT_CONFIG,
    MANUSCRIPT_THEME_EXPORT_CONFIG,
)


def export_manuscript_entries_with_navigation(
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> ConversionStats:
    """
    Export manuscript entries with prev/next navigation.

    Only exports entries that have ManuscriptEntry records.

    Args:
        db: Database manager
        wiki_dir: Wiki root directory
        journal_dir: Journal directory
        force: Force write all files
        logger: Optional logger

    Returns:
        ConversionStats with results
    """
    stats = ConversionStats()

    if logger:
        logger.log_operation("export_manuscript_entries_start", {"wiki_dir": str(wiki_dir)})

    with db.session_scope() as session:
        # Query entries with manuscript metadata, sorted by date
        query = (
            select(DBEntry)
            .join(DBManuscriptEntry)
            .options(
                joinedload(DBEntry.people).joinedload(DBPerson.manuscript),
                joinedload(DBEntry.manuscript).joinedload(DBManuscriptEntry.themes),
            )
            .order_by(DBEntry.date)
        )

        db_entries = session.execute(query).unique().scalars().all()

        if not db_entries:
            if logger:
                logger.log_warning("No manuscript entries found in database")
            return stats

        if logger:
            logger.log_info(f"Found {len(db_entries)} manuscript entries in database")

        # Export each entry with prev/next navigation
        wiki_entities = []
        for i, db_entry in enumerate(db_entries):
            stats.files_processed += 1

            try:
                # Get prev/next entries
                prev_entry = db_entries[i - 1] if i > 0 else None
                next_entry = db_entries[i + 1] if i < len(db_entries) - 1 else None

                # Convert to wiki entity with navigation
                wiki_entry = WikiManuscriptEntry.from_database(
                    db_entry, db_entry.manuscript, wiki_dir, journal_dir, prev_entry, next_entry
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
                    logger.log_debug(f"manuscript entry {wiki_entry.date}: {status}")

                wiki_entities.append(wiki_entry)

            except Exception as e:
                stats.errors += 1
                if logger:
                    logger.log_error(e, {
                        "operation": "export_manuscript_entry",
                        "entity": str(db_entry)
                    })

    return stats


def export_characters(
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> ConversionStats:
    """
    Export manuscript characters.

    Args:
        db: Database manager
        wiki_dir: Wiki root directory
        journal_dir: Journal directory
        force: Force write all files
        logger: Optional logger

    Returns:
        ConversionStats with results
    """
    exporter = EntityExporter(db, wiki_dir, journal_dir, logger)
    return exporter.export_entities(CHARACTER_EXPORT_CONFIG, force)


def export_events(
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> ConversionStats:
    """
    Export manuscript events.

    Args:
        db: Database manager
        wiki_dir: Wiki root directory
        journal_dir: Journal directory
        force: Force write all files
        logger: Optional logger

    Returns:
        ConversionStats with results
    """
    exporter = EntityExporter(db, wiki_dir, journal_dir, logger)
    return exporter.export_entities(MANUSCRIPT_EVENT_EXPORT_CONFIG, force)


def export_arcs(
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> ConversionStats:
    """
    Export story arcs.

    Args:
        db: Database manager
        wiki_dir: Wiki root directory
        journal_dir: Journal directory
        force: Force write all files
        logger: Optional logger

    Returns:
        ConversionStats with results
    """
    exporter = EntityExporter(db, wiki_dir, journal_dir, logger)
    return exporter.export_entities(ARC_EXPORT_CONFIG, force)


def export_themes(
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> ConversionStats:
    """
    Export manuscript themes.

    Args:
        db: Database manager
        wiki_dir: Wiki root directory
        journal_dir: Journal directory
        force: Force write all files
        logger: Optional logger

    Returns:
        ConversionStats with results
    """
    exporter = EntityExporter(db, wiki_dir, journal_dir, logger)
    return exporter.export_entities(MANUSCRIPT_THEME_EXPORT_CONFIG, force)


def export_manuscript_index(
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Export manuscript homepage (index.md).

    Args:
        db: Database manager
        wiki_dir: Wiki root directory
        journal_dir: Journal directory (unused)
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    path = wiki_dir / "manuscript" / "index.md"

    if logger:
        logger.log_operation("export_manuscript_index_start", {"path": str(path)})

    with db.session_scope() as session:
        # Count manuscript entities
        entry_count = session.execute(
            select(DBManuscriptEntry)
        ).scalars().all()

        character_count = session.execute(
            select(DBManuscriptPerson)
        ).scalars().all()

        event_count = session.execute(
            select(DBManuscriptEvent)
        ).scalars().all()

        arc_count = session.execute(
            select(DBArc)
        ).scalars().all()

        theme_count = session.execute(
            select(DBTheme)
        ).scalars().all()

        # Get recent entries
        recent_entries = session.execute(
            select(DBEntry)
            .join(DBManuscriptEntry)
            .order_by(DBEntry.date.desc())
            .limit(5)
        ).scalars().all()

        # Build content
        lines = [
            "# Palimpsest — Manuscript",
            "",
            "*[[../index.md|Home]] > Manuscript*",
            "",
            "## Manuscript Workspace",
            "",
            "This is the manuscript adaptation workspace, separate from the main journal wiki.",
            "Here you plan and track the adaptation of journal content into auto-fiction.",
            "",
            "## Quick Navigation",
            "",
            f"- [[entries.md|Entries]] — {len(entry_count)} manuscript entries",
            f"- [[characters.md|Characters]] — {len(character_count)} fictional characters",
            f"- [[events.md|Events]] — {len(event_count)} adapted events",
            f"- [[arcs.md|Arcs]] — {len(arc_count)} story arcs",
            f"- [[themes.md|Themes]] — {len(theme_count)} manuscript themes",
            "",
            "## Statistics",
            "",
            f"- **Total Manuscript Entries**: {len(entry_count)}",
            f"- **Characters Developed**: {len(character_count)}",
            f"- **Narrative Arcs**: {len(arc_count)}",
            f"- **Thematic Elements**: {len(theme_count)}",
            "",
        ]

        # Recent manuscript entries
        if recent_entries:
            lines.extend([
                "## Recent Manuscript Entries",
                "",
            ])
            for entry in recent_entries:
                year = entry.date.year
                entry_link = f"entries/{year}/{entry.date.isoformat()}.md"
                status = entry.manuscript.status.value if entry.manuscript else "unknown"
                lines.append(f"- [[{entry_link}|{entry.date.isoformat()}]] — Status: {status}")
            lines.append("")

        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write content
        content = "\n".join(lines)
        status = write_if_changed(path, content, force)

        if logger:
            if status in ("created", "updated"):
                logger.log_info(f"Manuscript index {status}")
            else:
                logger.log_debug("Manuscript index unchanged")

    return status


def build_entity_index(
    entity_name: str,
    entity_plural: str,
    items: List[Dict[str, str]],
    wiki_dir: Path,
    force: bool = False,
) -> str:
    """
    Build a generic entity index page.

    Args:
        entity_name: Entity name (singular)
        entity_plural: Entity name (plural)
        items: List of items with 'name', 'link', and optional 'info'
        wiki_dir: Wiki root directory
        force: Force write even if unchanged

    Returns:
        Status: "created", "updated", or "skipped"
    """
    path = wiki_dir / "manuscript" / f"{entity_plural.lower()}.md"

    lines = [
        f"# Palimpsest — Manuscript {entity_plural.title()}",
        "",
        f"*[[../index.md|Home]] > [[index.md|Manuscript]] > {entity_plural.title()}*",
        "",
        f"## All {entity_plural.title()}",
        "",
    ]

    if items:
        for item in items:
            info = f" — {item['info']}" if item.get('info') else ""
            lines.append(f"- [[{item['link']}|{item['name']}]]{info}")
    else:
        lines.append(f"No {entity_plural} found.")

    lines.append("")

    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write content
    content = "\n".join(lines)
    return write_if_changed(path, content, force)


# ===== CLI =====


@click.group()
def cli():
    """Manuscript subwiki export pipeline."""
    pass


@cli.command()
@click.argument(
    "entity_type",
    type=click.Choice([
        "entries", "characters", "events", "arcs", "themes", "all"
    ]),
)
@click.option("--force", is_flag=True, help="Force regenerate all files")
@click.option("--verbose", is_flag=True, help="Enable verbose logging")
def export(entity_type: str, force: bool, verbose: bool):
    """Export manuscript entities to wiki."""
    logger = setup_logger(LOG_DIR, "manuscript2wiki")

    try:
        db = PalimpsestDB(DB_PATH, ALEMBIC_DIR)
        wiki_dir = WIKI_DIR
        journal_dir = MD_DIR

        if entity_type == "all":
            # Export all manuscript entities
            click.echo(f"📤 Exporting all manuscript entities to {wiki_dir}/manuscript/")

            all_stats = []

            # Export in logical order
            stats = export_manuscript_entries_with_navigation(db, wiki_dir, journal_dir, force, logger)
            all_stats.append(("entries", stats))

            stats = export_characters(db, wiki_dir, journal_dir, force, logger)
            all_stats.append(("characters", stats))

            stats = export_events(db, wiki_dir, journal_dir, force, logger)
            all_stats.append(("events", stats))

            stats = export_arcs(db, wiki_dir, journal_dir, force, logger)
            all_stats.append(("arcs", stats))

            stats = export_themes(db, wiki_dir, journal_dir, force, logger)
            all_stats.append(("themes", stats))

            # Export manuscript homepage
            export_manuscript_index(db, wiki_dir, journal_dir, force, logger)

            # Build entity indexes
            # Note: We could build these from the wiki entities collected during export,
            # but for simplicity we'll query the database again
            with db.session_scope() as session:
                # Entries index
                entries = session.execute(
                    select(DBEntry).join(DBManuscriptEntry).order_by(DBEntry.date.desc())
                ).scalars().all()
                entry_items = []
                for entry in entries:
                    year = entry.date.year
                    entry_items.append({
                        "name": entry.date.isoformat(),
                        "link": f"entries/{year}/{entry.date.isoformat()}.md",
                        "info": f"Status: {entry.manuscript.status.value}"
                    })
                build_entity_index("entry", "entries", entry_items, wiki_dir, force)

                # Characters index
                characters = session.execute(
                    select(DBManuscriptPerson).join(DBPerson).order_by(DBManuscriptPerson.character)
                ).scalars().all()
                char_items = []
                for char in characters:
                    char_slug = char.character.lower().replace(" ", "_")
                    char_items.append({
                        "name": char.character,
                        "link": f"characters/{char_slug}.md",
                        "info": f"based on {char.person.display_name}"
                    })
                build_entity_index("character", "characters", char_items, wiki_dir, force)

                # Events index
                events = session.execute(
                    select(DBManuscriptEvent).join(DBEvent).order_by(DBEvent.event)
                ).scalars().all()
                event_items = []
                for event in events:
                    event_slug = event.event.event.lower().replace(" ", "_")
                    arc_info = f"Arc: {event.arc.arc}" if event.arc else "No arc"
                    event_items.append({
                        "name": event.event.event,
                        "link": f"events/{event_slug}.md",
                        "info": arc_info
                    })
                build_entity_index("event", "events", event_items, wiki_dir, force)

                # Arcs index
                arcs = session.execute(
                    select(DBArc).order_by(DBArc.arc)
                ).scalars().all()
                arc_items = []
                for arc in arcs:
                    arc_slug = arc.arc.lower().replace(" ", "_")
                    arc_items.append({
                        "name": arc.arc,
                        "link": f"arcs/{arc_slug}.md",
                        "info": f"{len(arc.events)} events"
                    })
                build_entity_index("arc", "arcs", arc_items, wiki_dir, force)

                # Themes index
                themes = session.execute(
                    select(DBTheme).order_by(DBTheme.theme)
                ).scalars().all()
                theme_items = []
                for theme in themes:
                    theme_slug = theme.theme.lower().replace(" ", "_")
                    theme_items.append({
                        "name": theme.theme,
                        "link": f"themes/{theme_slug}.md",
                        "info": f"{len(theme.entries)} entries"
                    })
                build_entity_index("theme", "themes", theme_items, wiki_dir, force)

            # Summary
            total_files = sum(s[1].files_processed for s in all_stats)
            total_created = sum(s[1].entries_created for s in all_stats)
            total_updated = sum(s[1].entries_updated for s in all_stats)
            total_skipped = sum(s[1].entries_skipped for s in all_stats)
            total_errors = sum(s[1].errors for s in all_stats)

            click.echo("\n✅ Manuscript export complete:")
            for entity_name, stat in all_stats:
                click.echo(f"  {entity_name}: {stat.files_processed} files")
            click.echo(f"  Total: {total_files} files processed")
            click.echo(f"  Created: {total_created}")
            click.echo(f"  Updated: {total_updated}")
            click.echo(f"  Skipped: {total_skipped}")
            if total_errors > 0:
                click.echo(f"  Errors: {total_errors}", err=True)

        else:
            # Export specific entity type
            click.echo(f"📤 Exporting manuscript {entity_type} to {wiki_dir}/manuscript/{entity_type}/")

            if entity_type == "entries":
                stats = export_manuscript_entries_with_navigation(db, wiki_dir, journal_dir, force, logger)
            elif entity_type == "characters":
                stats = export_characters(db, wiki_dir, journal_dir, force, logger)
            elif entity_type == "events":
                stats = export_events(db, wiki_dir, journal_dir, force, logger)
            elif entity_type == "arcs":
                stats = export_arcs(db, wiki_dir, journal_dir, force, logger)
            elif entity_type == "themes":
                stats = export_themes(db, wiki_dir, journal_dir, force, logger)

            click.echo(f"\n✅ Manuscript {entity_type} export complete:")
            click.echo(f"  Files processed: {stats.files_processed}")
            click.echo(f"  Created: {stats.entries_created}")
            click.echo(f"  Updated: {stats.entries_updated}")
            click.echo(f"  Skipped: {stats.entries_skipped}")
            if stats.errors > 0:
                click.echo(f"  Errors: {stats.errors}", err=True)

    except Exception as e:
        logger.log_error(e, {"operation": f"export_{entity_type}"})
        click.echo(f"❌ {type(e).__name__}: {e}", err=True)
        raise


if __name__ == "__main__":
    cli()
