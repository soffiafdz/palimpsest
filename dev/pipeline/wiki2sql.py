#!/usr/bin/env python3
"""
wiki2sql.py
-----------
Import wiki edits back to database (Phase 3: wiki→database sync).

This pipeline parses wiki markdown files for editable fields (notes, vignettes, etc.)
and updates the corresponding database records, completing the bidirectional sync loop.

Features:
- Import editable fields from wiki files
- Update database records while preserving computed fields
- Batch import with statistics
- CLI interface for selective imports

Usage:
    # Import specific entity type
    python -m dev.pipeline.wiki2sql import people
    python -m dev.pipeline.wiki2sql import entries

    # Import all entities
    python -m dev.pipeline.wiki2sql import all
"""
from __future__ import annotations

import sys
import click
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

from dev.database.manager import PalimpsestDB
from dev.database.models import (
    Person as DBPerson,
    Entry as DBEntry,
    Tag as DBTag,
    Poem as DBPoem,
    ReferenceSource as DBReferenceSource,
    Location as DBLocation,
    City as DBCity,
    Event as DBEvent,
)
from dev.database.models_manuscript import Theme as DBTheme

from dev.dataclasses.wiki_person import Person as WikiPerson
from dev.dataclasses.wiki_theme import Theme as WikiTheme
from dev.dataclasses.wiki_tag import Tag as WikiTag
from dev.dataclasses.wiki_poem import Poem as WikiPoem
from dev.dataclasses.wiki_reference import Reference as WikiReference
from dev.dataclasses.wiki_entry import Entry as WikiEntry
from dev.dataclasses.wiki_location import Location as WikiLocation
from dev.dataclasses.wiki_city import City as WikiCity
from dev.dataclasses.wiki_event import Event as WikiEvent

from dev.core.paths import LOG_DIR, DB_PATH, WIKI_DIR, ALEMBIC_DIR, BACKUP_DIR
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.core.cli_utils import setup_logger
from dev.core.exceptions import Wiki2SqlError

from sqlalchemy import select


@dataclass
class ImportStats:
    """Statistics from import operation."""

    files_processed: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    errors: int = 0


# ===== IMPORT FUNCTIONS =====


def import_person(
    wiki_file: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger] = None
) -> str:
    """
    Import person edits from wiki to database.

    Args:
        wiki_file: Path to person wiki file
        db: Database manager
        logger: Optional logger

    Returns:
        Status: "updated", "skipped", or "error"
    """
    try:
        # Parse wiki file
        wiki_person = WikiPerson.from_file(wiki_file)
        if not wiki_person:
            return "skipped"

        # Find corresponding database record by name or full_name
        # Wiki exports display_name (full_name if exists, else name)
        with db.session_scope() as session:
            from sqlalchemy import or_
            query = select(DBPerson).where(
                or_(
                    DBPerson.name == wiki_person.name,
                    DBPerson.full_name == wiki_person.name
                )
            )
            db_person = session.execute(query).scalar_one_or_none()

            if not db_person:
                if logger:
                    logger.log_warning(f"Person not found in database: {wiki_person.name}")
                return "skipped"

            # Note: Person notes and vignettes are wiki-only metadata, not stored in database
            # They are preserved during export by reading existing wiki files
            # No database fields to update, so always skip
            return "skipped"

    except Exception as e:
        if logger:
            logger.log_error(f"Error importing {wiki_file}: {e}")
        return "error"


def import_people(
    wiki_dir: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger] = None
) -> ImportStats:
    """
    Batch import all people from wiki.

    Args:
        wiki_dir: Wiki root directory
        db: Database manager
        logger: Optional logger

    Returns:
        ImportStats with summary
    """
    stats = ImportStats()
    people_dir = wiki_dir / "people"

    if not people_dir.exists():
        if logger:
            logger.log_warning(f"People directory not found: {people_dir}")
        return stats

    # Find all person wiki files
    wiki_files = list(people_dir.glob("*.md"))
    stats.files_processed = len(wiki_files)

    for wiki_file in wiki_files:
        status = import_person(wiki_file, db, logger)
        if status == "updated":
            stats.records_updated += 1
        elif status == "skipped":
            stats.records_skipped += 1
        elif status == "error":
            stats.errors += 1

    return stats


def import_theme(
    wiki_file: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger] = None
) -> str:
    """Import theme edits from wiki to database."""
    try:
        wiki_theme = WikiTheme.from_file(wiki_file)
        if not wiki_theme:
            return "skipped"

        with db.session_scope() as session:
            query = select(DBTheme).where(DBTheme.theme == wiki_theme.name)
            db_theme = session.execute(query).scalar_one_or_none()

            if not db_theme:
                if logger:
                    logger.log_warning(f"Theme not found in database: {wiki_theme.name}")
                return "skipped"

            # Note: Theme notes and description are wiki-only metadata, not stored in database
            # They are preserved during export by reading existing wiki files
            # No database fields to update, so always skip
            return "skipped"

    except Exception as e:
        if logger:
            logger.log_error(f"Error importing {wiki_file}: {e}")
        return "error"


def import_themes(
    wiki_dir: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger] = None
) -> ImportStats:
    """Batch import all themes from wiki."""
    stats = ImportStats()
    themes_dir = wiki_dir / "themes"

    if not themes_dir.exists():
        return stats

    wiki_files = list(themes_dir.glob("*.md"))
    stats.files_processed = len(wiki_files)

    for wiki_file in wiki_files:
        status = import_theme(wiki_file, db, logger)
        if status == "updated":
            stats.records_updated += 1
        elif status == "skipped":
            stats.records_skipped += 1
        elif status == "error":
            stats.errors += 1

    return stats


def import_tag(
    wiki_file: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger] = None
) -> str:
    """Import tag edits from wiki to database."""
    try:
        wiki_tag = WikiTag.from_file(wiki_file)
        if not wiki_tag:
            return "skipped"

        with db.session_scope() as session:
            query = select(DBTag).where(DBTag.tag == wiki_tag.name)
            db_tag = session.execute(query).scalar_one_or_none()

            if not db_tag:
                if logger:
                    logger.log_warning(f"Tag not found in database: {wiki_tag.name}")
                return "skipped"

            # Note: Tag notes are wiki-only metadata, not stored in database
            # They are preserved during export by reading existing wiki files
            # No database fields to update, so always skip
            return "skipped"

    except Exception as e:
        if logger:
            logger.log_error(f"Error importing {wiki_file}: {e}")
        return "error"


def import_tags(
    wiki_dir: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger] = None
) -> ImportStats:
    """Batch import all tags from wiki."""
    stats = ImportStats()
    tags_dir = wiki_dir / "tags"

    if not tags_dir.exists():
        return stats

    wiki_files = list(tags_dir.glob("*.md"))
    stats.files_processed = len(wiki_files)

    for wiki_file in wiki_files:
        status = import_tag(wiki_file, db, logger)
        if status == "updated":
            stats.records_updated += 1
        elif status == "skipped":
            stats.records_skipped += 1
        elif status == "error":
            stats.errors += 1

    return stats


def import_entry(
    wiki_file: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger] = None
) -> str:
    """Import entry edits from wiki to database."""
    try:
        wiki_entry = WikiEntry.from_file(wiki_file)
        if not wiki_entry:
            return "skipped"

        with db.session_scope() as session:
            query = select(DBEntry).where(DBEntry.date == wiki_entry.date)
            db_entry = session.execute(query).scalar_one_or_none()

            if not db_entry:
                if logger:
                    logger.log_warning(f"Entry not found in database: {wiki_entry.date}")
                return "skipped"

            # Update editable fields
            updated = False
            if wiki_entry.notes and wiki_entry.notes != db_entry.manuscript.notes if db_entry.manuscript else True:
                if not db_entry.manuscript:
                    from dev.database.models_manuscript import ManuscriptEntry

                    db_entry.manuscript = ManuscriptEntry(entry=db_entry)
                    session.add(db_entry.manuscript)

                db_entry.manuscript.notes = wiki_entry.notes
                updated = True

            if updated:
                session.commit()
                if logger:
                    logger.log_info(f"Updated entry: {wiki_entry.date}")
                return "updated"
            else:
                return "skipped"

    except Exception as e:
        if logger:
            logger.log_error(f"Error importing {wiki_file}: {e}")
        return "error"


def import_entries(
    wiki_dir: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger] = None
) -> ImportStats:
    """Batch import all entries from wiki."""
    stats = ImportStats()
    entries_dir = wiki_dir / "entries"

    if not entries_dir.exists():
        return stats

    # Find all entry wiki files (recursively in year subdirs)
    wiki_files = list(entries_dir.rglob("*.md"))
    stats.files_processed = len(wiki_files)

    for wiki_file in wiki_files:
        status = import_entry(wiki_file, db, logger)
        if status == "updated":
            stats.records_updated += 1
        elif status == "skipped":
            stats.records_skipped += 1
        elif status == "error":
            stats.errors += 1

    return stats


def import_event(
    wiki_file: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger] = None
) -> str:
    """Import event edits from wiki to database."""
    try:
        wiki_event = WikiEvent.from_file(wiki_file)
        if not wiki_event:
            return "skipped"

        with db.session_scope() as session:
            query = select(DBEvent).where(DBEvent.event == wiki_event.event)
            db_event = session.execute(query).scalar_one_or_none()

            if not db_event:
                if logger:
                    logger.log_warning(f"Event not found in database: {wiki_event.event}")
                return "skipped"

            # Update editable fields
            updated = False
            if wiki_event.notes and wiki_event.notes != db_event.manuscript.notes if db_event.manuscript else True:
                if not db_event.manuscript:
                    from dev.database.models_manuscript import ManuscriptEvent

                    db_event.manuscript = ManuscriptEvent(event=db_event)
                    session.add(db_event.manuscript)

                db_event.manuscript.notes = wiki_event.notes
                updated = True

            if updated:
                session.commit()
                if logger:
                    logger.log_info(f"Updated event: {wiki_event.event}")
                return "updated"
            else:
                return "skipped"

    except Exception as e:
        if logger:
            logger.log_error(f"Error importing {wiki_file}: {e}")
        return "error"


def import_events(
    wiki_dir: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger] = None
) -> ImportStats:
    """Batch import all events from wiki."""
    stats = ImportStats()
    events_dir = wiki_dir / "events"

    if not events_dir.exists():
        return stats

    wiki_files = list(events_dir.glob("*.md"))
    stats.files_processed = len(wiki_files)

    for wiki_file in wiki_files:
        status = import_event(wiki_file, db, logger)
        if status == "updated":
            stats.records_updated += 1
        elif status == "skipped":
            stats.records_skipped += 1
        elif status == "error":
            stats.errors += 1

    return stats


# Note: Poems, References, Locations, and Cities have no database-stored notes fields.
# They either have wiki-only metadata or no notes at all.
# Import functions for these would always skip, so they're not implemented.


def import_all(
    wiki_dir: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger] = None
) -> ImportStats:
    """
    Import all entity types from wiki.

    Args:
        wiki_dir: Wiki root directory
        db: Database manager
        logger: Optional logger

    Returns:
        Combined ImportStats
    """
    combined_stats = ImportStats()

    # Import each entity type
    for import_func in [import_people, import_themes, import_tags, import_entries, import_events]:
        stats = import_func(wiki_dir, db, logger)
        combined_stats.files_processed += stats.files_processed
        combined_stats.records_updated += stats.records_updated
        combined_stats.records_skipped += stats.records_skipped
        combined_stats.errors += stats.errors

    return combined_stats


# ===== CLI =====


@click.group()
@click.option(
    "--db-path",
    type=click.Path(),
    default=str(DB_PATH),
    help="Path to database file",
)
@click.option(
    "--wiki-dir",
    type=click.Path(),
    default=str(WIKI_DIR),
    help="Wiki root directory",
)
@click.option(
    "--log-dir",
    type=click.Path(),
    default=str(LOG_DIR),
    help="Logging directory",
)
@click.pass_context
def cli(ctx: click.Context, db_path: str, wiki_dir: str, log_dir: str) -> None:
    """Import wiki edits back to database."""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = Path(db_path)
    ctx.obj["wiki_dir"] = Path(wiki_dir)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["logger"] = setup_logger(Path(log_dir), "wiki2sql")

    # Initialize database
    ctx.obj["db"] = PalimpsestDB(
        db_path=Path(db_path),
        alembic_dir=ALEMBIC_DIR,
        log_dir=Path(log_dir),
        backup_dir=BACKUP_DIR,
        enable_auto_backup=False,
    )


@cli.command()
@click.argument(
    "entity_type",
    type=click.Choice(["people", "themes", "tags", "entries", "events", "all"]),
)
@click.pass_context
def import_cmd(ctx: click.Context, entity_type: str) -> None:
    """Import wiki edits to database."""
    logger: PalimpsestLogger = ctx.obj["logger"]
    db: PalimpsestDB = ctx.obj["db"]
    wiki_dir: Path = ctx.obj["wiki_dir"]

    try:
        click.echo(f"📥 Importing {entity_type} from {wiki_dir}/")

        # Run appropriate import function
        if entity_type == "people":
            stats = import_people(wiki_dir, db, logger)
        elif entity_type == "themes":
            stats = import_themes(wiki_dir, db, logger)
        elif entity_type == "tags":
            stats = import_tags(wiki_dir, db, logger)
        elif entity_type == "entries":
            stats = import_entries(wiki_dir, db, logger)
        elif entity_type == "events":
            stats = import_events(wiki_dir, db, logger)
        elif entity_type == "all":
            stats = import_all(wiki_dir, db, logger)
        else:
            click.echo(f"❌ Unknown entity type: {entity_type}")
            sys.exit(1)

        # Print summary
        click.echo(f"\n✅ Import complete:")
        click.echo(f"  Files processed: {stats.files_processed}")
        click.echo(f"  Records updated: {stats.records_updated}")
        click.echo(f"  Records skipped: {stats.records_skipped}")
        if stats.errors > 0:
            click.echo(f"  ⚠️  Errors: {stats.errors}")

    except (Wiki2SqlError, Exception) as e:
        handle_cli_error(ctx, e, "import", {"entity_type": entity_type})


# Register import command with proper name
cli.add_command(import_cmd, name="import")


if __name__ == "__main__":
    cli(obj={})
