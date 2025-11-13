#!/usr/bin/env python3
"""
manuscript2wiki.py
------------------
Export manuscript entities to wiki pages (manuscript subwiki).

This pipeline exports only manuscript-designated content (entries, characters,
events, arcs, themes) to the manuscript subwiki at data/wiki/manuscript/.

This is separate from sql2wiki.py which exports ALL journal content to the main wiki.

Usage:
    # Export specific manuscript entity type
    python -m dev.pipeline.manuscript2wiki export entries
    python -m dev.pipeline.manuscript2wiki export characters
    python -m dev.pipeline.manuscript2wiki export arcs

    # Export all manuscript entities
    python -m dev.pipeline.manuscript2wiki export all

    # Force regeneration
    python -m dev.pipeline.manuscript2wiki export all --force
"""
from __future__ import annotations

import click
from pathlib import Path
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from dev.dataclasses.manuscript_entry import ManuscriptEntry as WikiManuscriptEntry
from dev.dataclasses.manuscript_character import Character as WikiCharacter
from dev.dataclasses.manuscript_event import ManuscriptEvent as WikiManuscriptEvent
from dev.dataclasses.manuscript_arc import Arc as WikiArc
from dev.dataclasses.manuscript_theme import Theme as WikiTheme

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
from dev.core.cli_utils import setup_logger
from dev.core.cli_stats import ConversionStats

from dev.pipeline.entity_exporter import write_if_changed


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
    stats = ConversionStats()

    if logger:
        logger.log_operation("export_characters_start", {"wiki_dir": str(wiki_dir)})

    with db.session_scope() as session:
        # Query manuscript people with relationships
        query = (
            select(DBManuscriptPerson)
            .join(DBPerson)
            .options(joinedload(DBManuscriptPerson.person))
            .order_by(DBManuscriptPerson.character)
        )

        db_characters = session.execute(query).unique().scalars().all()

        if not db_characters:
            if logger:
                logger.log_warning("No manuscript characters found in database")
            return stats

        if logger:
            logger.log_info(f"Found {len(db_characters)} manuscript characters in database")

        # Export each character
        for ms_person in db_characters:
            stats.files_processed += 1

            try:
                wiki_character = WikiCharacter.from_database(
                    ms_person.person, ms_person, wiki_dir, journal_dir
                )

                # Ensure output directory exists
                wiki_character.path.parent.mkdir(parents=True, exist_ok=True)

                # Generate wiki content
                content = "\n".join(wiki_character.to_wiki())

                # Write if changed
                status = write_if_changed(wiki_character.path, content, force)

                if status == "created":
                    stats.entries_created += 1
                elif status == "updated":
                    stats.entries_updated += 1
                elif status == "skipped":
                    stats.entries_skipped += 1

                if logger:
                    logger.log_debug(f"character {wiki_character.name}: {status}")

            except Exception as e:
                stats.errors += 1
                if logger:
                    logger.log_error(e, {
                        "operation": "export_character",
                        "entity": str(ms_person)
                    })

    return stats


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
    stats = ConversionStats()

    if logger:
        logger.log_operation("export_manuscript_events_start", {"wiki_dir": str(wiki_dir)})

    with db.session_scope() as session:
        # Query manuscript events with relationships
        query = (
            select(DBManuscriptEvent)
            .join(DBEvent)
            .options(
                joinedload(DBManuscriptEvent.event).joinedload(DBEvent.entries),
                joinedload(DBManuscriptEvent.event).joinedload(DBEvent.people).joinedload(DBPerson.manuscript),
                joinedload(DBManuscriptEvent.arc),
            )
            .order_by(DBEvent.event)
        )

        db_events = session.execute(query).unique().scalars().all()

        if not db_events:
            if logger:
                logger.log_warning("No manuscript events found in database")
            return stats

        if logger:
            logger.log_info(f"Found {len(db_events)} manuscript events in database")

        # Export each event
        for ms_event in db_events:
            stats.files_processed += 1

            try:
                wiki_event = WikiManuscriptEvent.from_database(
                    ms_event.event, ms_event, wiki_dir, journal_dir
                )

                # Ensure output directory exists
                wiki_event.path.parent.mkdir(parents=True, exist_ok=True)

                # Generate wiki content
                content = "\n".join(wiki_event.to_wiki())

                # Write if changed
                status = write_if_changed(wiki_event.path, content, force)

                if status == "created":
                    stats.entries_created += 1
                elif status == "updated":
                    stats.entries_updated += 1
                elif status == "skipped":
                    stats.entries_skipped += 1

                if logger:
                    logger.log_debug(f"manuscript event {wiki_event.name}: {status}")

            except Exception as e:
                stats.errors += 1
                if logger:
                    logger.log_error(e, {
                        "operation": "export_manuscript_event",
                        "entity": str(ms_event)
                    })

    return stats


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
    stats = ConversionStats()

    if logger:
        logger.log_operation("export_arcs_start", {"wiki_dir": str(wiki_dir)})

    with db.session_scope() as session:
        # Query arcs with relationships
        query = (
            select(DBArc)
            .options(
                joinedload(DBArc.events).joinedload(DBManuscriptEvent.event),
            )
            .order_by(DBArc.arc)
        )

        db_arcs = session.execute(query).unique().scalars().all()

        if not db_arcs:
            if logger:
                logger.log_warning("No arcs found in database")
            return stats

        if logger:
            logger.log_info(f"Found {len(db_arcs)} arcs in database")

        # Export each arc
        for arc in db_arcs:
            stats.files_processed += 1

            try:
                wiki_arc = WikiArc.from_database(arc, wiki_dir, journal_dir)

                # Ensure output directory exists
                wiki_arc.path.parent.mkdir(parents=True, exist_ok=True)

                # Generate wiki content
                content = "\n".join(wiki_arc.to_wiki())

                # Write if changed
                status = write_if_changed(wiki_arc.path, content, force)

                if status == "created":
                    stats.entries_created += 1
                elif status == "updated":
                    stats.entries_updated += 1
                elif status == "skipped":
                    stats.entries_skipped += 1

                if logger:
                    logger.log_debug(f"arc {wiki_arc.name}: {status}")

            except Exception as e:
                stats.errors += 1
                if logger:
                    logger.log_error(e, {
                        "operation": "export_arc",
                        "entity": str(arc)
                    })

    return stats


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
    stats = ConversionStats()

    if logger:
        logger.log_operation("export_manuscript_themes_start", {"wiki_dir": str(wiki_dir)})

    with db.session_scope() as session:
        # Query themes with relationships
        query = (
            select(DBTheme)
            .options(
                joinedload(DBTheme.entries).joinedload(DBManuscriptEntry.entry),
            )
            .order_by(DBTheme.theme)
        )

        db_themes = session.execute(query).unique().scalars().all()

        if not db_themes:
            if logger:
                logger.log_warning("No manuscript themes found in database")
            return stats

        if logger:
            logger.log_info(f"Found {len(db_themes)} manuscript themes in database")

        # Export each theme
        for theme in db_themes:
            stats.files_processed += 1

            try:
                wiki_theme = WikiTheme.from_database(theme, wiki_dir, journal_dir)

                # Ensure output directory exists
                wiki_theme.path.parent.mkdir(parents=True, exist_ok=True)

                # Generate wiki content
                content = "\n".join(wiki_theme.to_wiki())

                # Write if changed
                status = write_if_changed(wiki_theme.path, content, force)

                if status == "created":
                    stats.entries_created += 1
                elif status == "updated":
                    stats.entries_updated += 1
                elif status == "skipped":
                    stats.entries_skipped += 1

                if logger:
                    logger.log_debug(f"manuscript theme {wiki_theme.name}: {status}")

            except Exception as e:
                stats.errors += 1
                if logger:
                    logger.log_error(e, {
                        "operation": "export_manuscript_theme",
                        "entity": str(theme)
                    })

    return stats


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
