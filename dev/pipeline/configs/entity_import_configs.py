#!/usr/bin/env python3
"""
entity_import_configs.py
-------------------------

Entity import configurations for the generic EntityImporter framework.

This module defines configuration objects for all importable entity types,
replacing the need for separate import functions in wiki2sql.py.
"""
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select, or_, func

from dev.database.manager import PalimpsestDB
from dev.database.models import (
    Person as DBPerson,
    Entry as DBEntry,
    Event as DBEvent,
    Tag as DBTag,
    Poem as DBPoem,
    ReferenceSource as DBReferenceSource,
    Location as DBLocation,
    City as DBCity,
)
from dev.database.models_manuscript import Theme as DBTheme
from dev.database.sync_state_manager import SyncStateManager
from dev.core.logging_manager import PalimpsestLogger

from dev.dataclasses.wiki_person import Person as WikiPerson
from dev.dataclasses.wiki_theme import Theme as WikiTheme
from dev.dataclasses.wiki_tag import Tag as WikiTag
from dev.dataclasses.wiki_poem import Poem as WikiPoem
from dev.dataclasses.wiki_reference import Reference as WikiReference
from dev.dataclasses.wiki_entry import Entry as WikiEntry
from dev.dataclasses.wiki_location import Location as WikiLocation
from dev.dataclasses.wiki_city import City as WikiCity
from dev.dataclasses.wiki_event import Event as WikiEvent

from dev.pipeline.entity_importer import EntityImportConfig


# ========================================
# Custom Updater Functions
# ========================================

def _update_entry(wiki_entry: WikiEntry, wiki_file: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger]) -> str:
    """Update entry from wiki edits."""
    try:
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
            logger.log_error(e, {"operation": "update_entry_edits", "file": str(wiki_file)})
        return "error"


def _update_event(wiki_event: WikiEvent, wiki_file: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger]) -> str:
    """Update event from wiki edits."""
    try:
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
            logger.log_error(e, {"operation": "update_event_edits", "file": str(wiki_file)})
        return "error"


# ========================================
# Entity Configurations
# ========================================

# Metadata-only entities (no database updates needed)
# These have wiki-only metadata (notes, vignettes) preserved during export

PERSON_IMPORT_CONFIG = EntityImportConfig(
    entity_name="person",
    entity_plural="people",
    wiki_class=WikiPerson,
    wiki_subdir="people",
    # No updater = always skip (wiki-only metadata)
)

THEME_IMPORT_CONFIG = EntityImportConfig(
    entity_name="theme",
    entity_plural="themes",
    wiki_class=WikiTheme,
    wiki_subdir="themes",
    # No updater = always skip (wiki-only metadata)
)

TAG_IMPORT_CONFIG = EntityImportConfig(
    entity_name="tag",
    entity_plural="tags",
    wiki_class=WikiTag,
    wiki_subdir="tags",
    # No updater = always skip (wiki-only metadata)
)

POEM_IMPORT_CONFIG = EntityImportConfig(
    entity_name="poem",
    entity_plural="poems",
    wiki_class=WikiPoem,
    wiki_subdir="poems",
    # No updater = always skip (wiki-only metadata)
)

REFERENCE_IMPORT_CONFIG = EntityImportConfig(
    entity_name="reference",
    entity_plural="references",
    wiki_class=WikiReference,
    wiki_subdir="references",
    # No updater = always skip (wiki-only metadata)
)

LOCATION_IMPORT_CONFIG = EntityImportConfig(
    entity_name="location",
    entity_plural="locations",
    wiki_class=WikiLocation,
    wiki_subdir="locations",
    # No updater = always skip (wiki-only metadata)
)

CITY_IMPORT_CONFIG = EntityImportConfig(
    entity_name="city",
    entity_plural="cities",
    wiki_class=WikiCity,
    wiki_subdir="cities",
    # No updater = always skip (wiki-only metadata)
)

# Entities with updatable database fields

ENTRY_IMPORT_CONFIG = EntityImportConfig(
    entity_name="entry",
    entity_plural="entries",
    wiki_class=WikiEntry,
    wiki_subdir="entries",
    recursive=True,  # Entries are in year subdirectories
    entity_updater=_update_entry,
)

EVENT_IMPORT_CONFIG = EntityImportConfig(
    entity_name="event",
    entity_plural="events",
    wiki_class=WikiEvent,
    wiki_subdir="events",
    entity_updater=_update_event,
)

# Grouped configurations for batch operations

ALL_JOURNAL_CONFIGS = [
    PERSON_IMPORT_CONFIG,
    THEME_IMPORT_CONFIG,
    TAG_IMPORT_CONFIG,
    POEM_IMPORT_CONFIG,
    REFERENCE_IMPORT_CONFIG,
    LOCATION_IMPORT_CONFIG,
    CITY_IMPORT_CONFIG,
    ENTRY_IMPORT_CONFIG,
    EVENT_IMPORT_CONFIG,
]
