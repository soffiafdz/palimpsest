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
- Sync state tracking with conflict detection
- Multi-machine synchronization support

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
import socket
from pathlib import Path
from datetime import datetime, timezone
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
from dev.database.sync_state_manager import SyncStateManager

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
from dev.core.cli import setup_logger
from dev.core.exceptions import Wiki2SqlError

from sqlalchemy import select, func

from dev.pipeline.entity_importer import EntityImporter, ImportStats
from dev.pipeline.configs.entity_import_configs import (
    PERSON_IMPORT_CONFIG,
    THEME_IMPORT_CONFIG,
    TAG_IMPORT_CONFIG,
    ENTRY_IMPORT_CONFIG,
    EVENT_IMPORT_CONFIG,
    ALL_JOURNAL_CONFIGS,
)
from dev.pipeline.configs.manuscript_entity_import_configs import (
    MANUSCRIPT_ENTRY_IMPORT_CONFIG,
    MANUSCRIPT_CHARACTER_IMPORT_CONFIG,
    MANUSCRIPT_EVENT_IMPORT_CONFIG,
    ALL_MANUSCRIPT_CONFIGS,
)


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
    importer = EntityImporter(db, wiki_dir, logger)
    return importer.import_entities(PERSON_IMPORT_CONFIG)


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
    importer = EntityImporter(db, wiki_dir, logger)
    return importer.import_entities(THEME_IMPORT_CONFIG)


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
    importer = EntityImporter(db, wiki_dir, logger)
    return importer.import_entities(TAG_IMPORT_CONFIG)


def import_entry(
    wiki_file: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger] = None
) -> str:
    """Import entry edits from wiki to database."""
    try:
        wiki_entry = WikiEntry.from_file(wiki_file)
        if not wiki_entry:
            return "skipped"

        # Compute file hash for conflict detection
        from dev.utils import fs
        file_hash = fs.get_file_hash(wiki_file)

        # Get machine ID for sync state tracking
        machine_id = socket.gethostname()

        with db.session_scope() as session:
            query = select(DBEntry).where(DBEntry.date == wiki_entry.date)
            db_entry = session.execute(query).scalar_one_or_none()

            if not db_entry:
                if logger:
                    logger.log_warning(f"Entry not found in database: {wiki_entry.date}")
                return "skipped"

            # Initialize sync state manager
            sync_mgr = SyncStateManager(session, logger)

            # Check for conflicts before updating
            if sync_mgr.check_conflict("Entry", db_entry.id, file_hash):
                if logger:
                    logger.log_warning(
                        f"Conflict detected for entry {wiki_entry.date}",
                        {
                            "file": str(wiki_file),
                            "action": "proceeding_with_update"
                        }
                    )

            # Update editable fields
            updated = False
            if wiki_entry.notes and wiki_entry.notes != db_entry.notes:
                db_entry.notes = wiki_entry.notes
                updated = True

            if updated:
                # Update sync state after successful update
                sync_mgr.update_or_create(
                    entity_type="Entry",
                    entity_id=db_entry.id,
                    last_synced_at=datetime.now(timezone.utc),
                    sync_source="wiki",
                    sync_hash=file_hash,
                    machine_id=machine_id
                )

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
    importer = EntityImporter(db, wiki_dir, logger)
    return importer.import_entities(ENTRY_IMPORT_CONFIG)


def import_event(
    wiki_file: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger] = None
) -> str:
    """Import event edits from wiki to database."""
    try:
        wiki_event = WikiEvent.from_file(wiki_file)
        if not wiki_event:
            return "skipped"

        # Compute file hash for conflict detection
        from dev.utils import fs
        file_hash = fs.get_file_hash(wiki_file)

        # Get machine ID for sync state tracking
        machine_id = socket.gethostname()

        with db.session_scope() as session:
            query = select(DBEvent).where(func.lower(DBEvent.event) == wiki_event.event.lower())
            db_event = session.execute(query).scalar_one_or_none()

            if not db_event:
                if logger:
                    logger.log_warning(f"Event not found in database: {wiki_event.event}")
                return "skipped"

            # Initialize sync state manager
            sync_mgr = SyncStateManager(session, logger)

            # Check for conflicts before updating
            if sync_mgr.check_conflict("Event", db_event.id, file_hash):
                if logger:
                    logger.log_warning(
                        f"Conflict detected for event {wiki_event.event}",
                        {
                            "file": str(wiki_file),
                            "action": "proceeding_with_update"
                        }
                    )

            # Update editable fields
            updated = False
            if wiki_event.notes and wiki_event.notes != db_event.notes:
                db_event.notes = wiki_event.notes
                updated = True

            if updated:
                # Update sync state after successful update
                sync_mgr.update_or_create(
                    entity_type="Event",
                    entity_id=db_event.id,
                    last_synced_at=datetime.now(timezone.utc),
                    sync_source="wiki",
                    sync_hash=file_hash,
                    machine_id=machine_id
                )

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
    importer = EntityImporter(db, wiki_dir, logger)
    return importer.import_entities(EVENT_IMPORT_CONFIG)


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


# ===== MANUSCRIPT IMPORT FUNCTIONS =====


def import_manuscript_entry(
    wiki_file: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger] = None
) -> str:
    """
    Import manuscript entry edits from wiki to database.

    Updates ManuscriptEntry fields: notes, character_notes, entry_type, narrative_arc.

    Args:
        wiki_file: Path to manuscript entry wiki file
        db: Database manager
        logger: Optional logger

    Returns:
        Status: "updated", "skipped", or "error"
    """
    try:
        # Import manuscript dataclasses
        from dev.dataclasses.manuscript_entry import ManuscriptEntry as WikiManuscriptEntry
        from dev.database.models_manuscript import ManuscriptEntry as DBManuscriptEntry, EntryType
        from datetime import datetime

        # Parse wiki file
        wiki_entry = WikiManuscriptEntry.from_file(wiki_file)
        if not wiki_entry:
            return "skipped"

        # Find corresponding database records
        with db.session_scope() as session:
            # Find Entry by date
            query = select(DBEntry).where(DBEntry.date == wiki_entry.date)
            db_entry = session.execute(query).scalar_one_or_none()

            if not db_entry:
                if logger:
                    logger.log_warning(f"Entry not found for date {wiki_entry.date}")
                return "skipped"

            # Find or create ManuscriptEntry
            if not db_entry.manuscript:
                if logger:
                    logger.log_warning(f"Entry {wiki_entry.date} has no manuscript record")
                return "skipped"

            ms_entry = db_entry.manuscript

            # Update editable fields
            updated = False

            if wiki_entry.notes != ms_entry.notes:
                ms_entry.notes = wiki_entry.notes
                updated = True

            if wiki_entry.character_notes != ms_entry.character_notes:
                ms_entry.character_notes = wiki_entry.character_notes
                updated = True

            if updated:
                session.commit()
                return "updated"

            return "skipped"

    except Exception as e:
        if logger:
            logger.log_error(e, {"operation": "import_manuscript_entry", "file": str(wiki_file)})
        return "error"


def import_manuscript_character(
    wiki_file: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger] = None
) -> str:
    """
    Import manuscript character edits from wiki to database.

    Updates ManuscriptPerson fields: character_description, character_arc,
    voice_notes, appearance_notes.

    Args:
        wiki_file: Path to manuscript character wiki file
        db: Database manager
        logger: Optional logger

    Returns:
        Status: "updated", "skipped", or "error"
    """
    try:
        # Import manuscript dataclasses
        from dev.dataclasses.manuscript_character import Character as WikiCharacter
        from dev.database.models_manuscript import ManuscriptPerson as DBManuscriptPerson

        # Parse wiki file
        wiki_char = WikiCharacter.from_file(wiki_file)
        if not wiki_char:
            return "skipped"

        # Find corresponding database record by character name
        with db.session_scope() as session:
            query = select(DBManuscriptPerson).where(
                DBManuscriptPerson.character == wiki_char.name
            )
            ms_person = session.execute(query).scalar_one_or_none()

            if not ms_person:
                if logger:
                    logger.log_warning(f"Character not found: {wiki_char.name}")
                return "skipped"

            # Update editable fields
            updated = False

            if wiki_char.character_description != ms_person.character_description:
                ms_person.character_description = wiki_char.character_description
                updated = True

            if wiki_char.character_arc != ms_person.character_arc:
                ms_person.character_arc = wiki_char.character_arc
                updated = True

            if wiki_char.voice_notes != ms_person.voice_notes:
                ms_person.voice_notes = wiki_char.voice_notes
                updated = True

            if wiki_char.appearance_notes != ms_person.appearance_notes:
                ms_person.appearance_notes = wiki_char.appearance_notes
                updated = True

            if updated:
                session.commit()
                return "updated"

            return "skipped"

    except Exception as e:
        if logger:
            logger.log_error(e, {"operation": "import_manuscript_character", "file": str(wiki_file)})
        return "error"


def import_manuscript_event(
    wiki_file: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger] = None
) -> str:
    """
    Import manuscript event edits from wiki to database.

    Updates ManuscriptEvent.notes field.

    Args:
        wiki_file: Path to manuscript event wiki file
        db: Database manager
        logger: Optional logger

    Returns:
        Status: "updated", "skipped", or "error"
    """
    try:
        # Import manuscript dataclasses
        from dev.dataclasses.manuscript_event import ManuscriptEvent as WikiManuscriptEvent
        from dev.database.models_manuscript import ManuscriptEvent as DBManuscriptEvent

        # Parse wiki file
        wiki_event = WikiManuscriptEvent.from_file(wiki_file)
        if not wiki_event:
            return "skipped"

        # Find corresponding database record by event name
        with db.session_scope() as session:
            # Find Event by name, then get its ManuscriptEvent
            query = select(DBEvent).where(func.lower(DBEvent.event) == wiki_event.name.lower())
            db_event = session.execute(query).scalar_one_or_none()

            if not db_event:
                if logger:
                    logger.log_warning(f"Event not found: {wiki_event.name}")
                return "skipped"

            # Find ManuscriptEvent
            ms_query = select(DBManuscriptEvent).where(
                DBManuscriptEvent.event_id == db_event.id
            )
            ms_event = session.execute(ms_query).scalar_one_or_none()

            if not ms_event:
                if logger:
                    logger.log_warning(f"Event {wiki_event.name} has no manuscript record")
                return "skipped"

            # Update editable fields
            updated = False

            if wiki_event.notes != ms_event.notes:
                ms_event.notes = wiki_event.notes
                updated = True

            if updated:
                session.commit()
                return "updated"

            return "skipped"

    except Exception as e:
        if logger:
            logger.log_error(e, {"operation": "import_manuscript_event", "file": str(wiki_file)})
        return "error"


def import_all_manuscript_entries(
    db: PalimpsestDB,
    wiki_dir: Path,
    logger: Optional[PalimpsestLogger] = None,
) -> ImportStats:
    """Import all manuscript entries from wiki."""
    importer = EntityImporter(db, wiki_dir, logger)
    return importer.import_entities(MANUSCRIPT_ENTRY_IMPORT_CONFIG)


def import_all_manuscript_characters(
    db: PalimpsestDB,
    wiki_dir: Path,
    logger: Optional[PalimpsestLogger] = None,
) -> ImportStats:
    """Import all manuscript characters from wiki."""
    importer = EntityImporter(db, wiki_dir, logger)
    return importer.import_entities(MANUSCRIPT_CHARACTER_IMPORT_CONFIG)


def import_all_manuscript_events(
    db: PalimpsestDB,
    wiki_dir: Path,
    logger: Optional[PalimpsestLogger] = None,
) -> ImportStats:
    """Import all manuscript events from wiki."""
    importer = EntityImporter(db, wiki_dir, logger)
    return importer.import_entities(MANUSCRIPT_EVENT_IMPORT_CONFIG)


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
    type=click.Choice([
        "people", "themes", "tags", "entries", "events",
        "manuscript-entries", "manuscript-characters", "manuscript-events",
        "all", "manuscript-all"
    ]),
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
        elif entity_type == "manuscript-entries":
            stats = import_all_manuscript_entries(db, wiki_dir, logger)
        elif entity_type == "manuscript-characters":
            stats = import_all_manuscript_characters(db, wiki_dir, logger)
        elif entity_type == "manuscript-events":
            stats = import_all_manuscript_events(db, wiki_dir, logger)
        elif entity_type == "manuscript-all":
            # Import all manuscript entities
            combined_stats = ImportStats()
            for import_func in [
                import_all_manuscript_entries,
                import_all_manuscript_characters,
                import_all_manuscript_events,
            ]:
                stats = import_func(db, wiki_dir, logger)
                combined_stats.files_processed += stats.files_processed
                combined_stats.records_updated += stats.records_updated
                combined_stats.records_skipped += stats.records_skipped
                combined_stats.errors += stats.errors
            stats = combined_stats
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
