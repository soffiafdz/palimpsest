#!/usr/bin/env python3
"""
manuscript_entity_import_configs.py
------------------------------------

Entity import configurations for manuscript-designated entities.

This module defines configuration objects for manuscript entity types,
used by the EntityImporter framework to import manuscript wiki edits.
"""
from pathlib import Path
from typing import Optional

from sqlalchemy import select, func

from dev.database.manager import PalimpsestDB
from dev.database.models import Entry as DBEntry
from dev.database.models_manuscript import (
    
    ManuscriptPerson as DBManuscriptPerson,
    ManuscriptEvent as DBManuscriptEvent,
)
from dev.core.logging_manager import PalimpsestLogger

from dev.dataclasses.manuscript_entry import ManuscriptEntry as WikiManuscriptEntry
from dev.dataclasses.manuscript_character import Character as WikiCharacter
from dev.dataclasses.manuscript_event import ManuscriptEvent as WikiManuscriptEvent

from dev.pipeline.entity_importer import EntityImportConfig


# ========================================
# Custom Updater Functions
# ========================================

def _update_manuscript_entry(
    wiki_entry: WikiManuscriptEntry,
    wiki_file: Path,
    db: PalimpsestDB,
    logger: Optional[PalimpsestLogger]
) -> str:
    """
    Update manuscript entry from wiki edits.

    Updates ManuscriptEntry fields: notes, character_notes, entry_type, narrative_arc.
    """
    try:
        with db.session_scope() as session:
            # Find Entry by date
            query = select(DBEntry).where(DBEntry.date == wiki_entry.date)
            db_entry = session.execute(query).scalar_one_or_none()

            if not db_entry:
                if logger:
                    logger.log_warning(f"Entry not found for date {wiki_entry.date}")
                return "skipped"

            # Check ManuscriptEntry exists
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
                if logger:
                    logger.log_info(f"Updated manuscript entry: {wiki_entry.date}")
                return "updated"

            return "skipped"

    except Exception as e:
        if logger:
            logger.log_error(e, {"operation": "import_manuscript_entry", "file": str(wiki_file)})
        return "error"


def _update_manuscript_character(
    wiki_char: WikiCharacter,
    wiki_file: Path,
    db: PalimpsestDB,
    logger: Optional[PalimpsestLogger]
) -> str:
    """
    Update manuscript character from wiki edits.

    Updates ManuscriptPerson fields: character_description, character_arc,
    voice_notes, appearance_notes.
    """
    try:
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
                if logger:
                    logger.log_info(f"Updated manuscript character: {wiki_char.name}")
                return "updated"

            return "skipped"

    except Exception as e:
        if logger:
            logger.log_error(e, {"operation": "import_manuscript_character", "file": str(wiki_file)})
        return "error"


def _update_manuscript_event(
    wiki_event: WikiManuscriptEvent,
    wiki_file: Path,
    db: PalimpsestDB,
    logger: Optional[PalimpsestLogger]
) -> str:
    """
    Update manuscript event from wiki edits.

    Updates ManuscriptEvent fields: notes.
    """
    try:
        with db.session_scope() as session:
            # Find ManuscriptEvent by event name (requires joining with Event)
            from dev.database.models import Event as DBEvent
            query = (
                select(DBManuscriptEvent)
                .join(DBEvent)
                .where(func.lower(DBEvent.event) == wiki_event.name.lower())
            )
            ms_event = session.execute(query).scalar_one_or_none()

            if not ms_event:
                if logger:
                    logger.log_warning(f"Manuscript event not found: {wiki_event.name}")
                return "skipped"

            # Update editable fields
            updated = False

            if wiki_event.notes and wiki_event.notes != ms_event.notes:
                ms_event.notes = wiki_event.notes
                updated = True

            if updated:
                session.commit()
                if logger:
                    logger.log_info(f"Updated manuscript event: {wiki_event.name}")
                return "updated"

            return "skipped"

    except Exception as e:
        if logger:
            logger.log_error(e, {"operation": "import_manuscript_event", "file": str(wiki_file)})
        return "error"


# ========================================
# Entity Configurations
# ========================================

MANUSCRIPT_ENTRY_IMPORT_CONFIG = EntityImportConfig(
    entity_name="manuscript_entry",
    entity_plural="manuscript_entries",
    wiki_class=WikiManuscriptEntry,
    wiki_subdir="manuscript/entries",
    recursive=True,  # Entries are in year subdirectories
    entity_updater=_update_manuscript_entry,
)

MANUSCRIPT_CHARACTER_IMPORT_CONFIG = EntityImportConfig(
    entity_name="manuscript_character",
    entity_plural="manuscript_characters",
    wiki_class=WikiCharacter,
    wiki_subdir="manuscript/characters",
    entity_updater=_update_manuscript_character,
)

MANUSCRIPT_EVENT_IMPORT_CONFIG = EntityImportConfig(
    entity_name="manuscript_event",
    entity_plural="manuscript_events",
    wiki_class=WikiManuscriptEvent,
    wiki_subdir="manuscript/events",
    entity_updater=_update_manuscript_event,
)

# Grouped configuration for batch operations
ALL_MANUSCRIPT_CONFIGS = [
    MANUSCRIPT_ENTRY_IMPORT_CONFIG,
    MANUSCRIPT_CHARACTER_IMPORT_CONFIG,
    MANUSCRIPT_EVENT_IMPORT_CONFIG,
]
