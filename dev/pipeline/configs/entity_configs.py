#!/usr/bin/env python3
"""
entity_configs.py
-----------------

Entity export configurations for the generic EntityExporter framework.

This module defines configuration objects for all exportable entity types,
replacing the need for separate export functions in ms2wiki.py.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from dev.database.models_manuscript import (
    ManuscriptEntry as DBManuscriptEntry,
    ManuscriptPerson as DBManuscriptPerson,
    ManuscriptEvent as DBManuscriptEvent,
    Theme as DBTheme,
)
from dev.database.models import Event as DBEvent, Person as DBPerson
from dev.dataclasses.manuscript_character import Character as WikiCharacter
from dev.dataclasses.manuscript_entry import ManuscriptEntry as WikiManuscriptEntry
from dev.dataclasses.manuscript_event import ManuscriptEvent as WikiManuscriptEvent
from dev.dataclasses.wiki_event import Event as WikiEvent
from dev.dataclasses.wiki_theme import Theme as WikiTheme
from dev.pipeline.entity_exporter import EntityExportConfig


# ========================================
# Manuscript Entity Configurations
# ========================================

def _build_character_query(session: Session):
    """Build query for manuscript characters."""
    return (
        select(DBManuscriptPerson)
        .join(DBPerson)
        .options(
            joinedload(DBManuscriptPerson.person).joinedload(DBPerson.entries),
            joinedload(DBManuscriptPerson.person).joinedload(DBPerson.aliases),
        )
    )


def _build_manuscript_entry_query(session: Session):
    """Build query for manuscript entries."""
    return (
        select(DBManuscriptEntry)
        .join(DBManuscriptEntry.entry)
        .options(
            joinedload(DBManuscriptEntry.entry),
            joinedload(DBManuscriptEntry.themes),
        )
    )


def _build_manuscript_event_query(session: Session):
    """Build query for manuscript events."""
    return (
        select(DBManuscriptEvent)
        .join(DBEvent)
        .options(
            joinedload(DBManuscriptEvent.event).joinedload(DBEvent.entries),
            joinedload(DBManuscriptEvent.themes),
        )
    )


def _build_event_query(session: Session):
    """Build query for journal events."""
    return (
        select(DBEvent)
        .options(
            joinedload(DBEvent.entries),
            joinedload(DBEvent.people),
        )
    )


def _build_theme_query(session: Session):
    """Build query for themes."""
    return (
        select(DBTheme)
        .options(joinedload(DBTheme.entries))
    )


# Configuration for manuscript characters
CHARACTER_EXPORT_CONFIG = EntityExportConfig(
    entity_name="character",
    entity_plural="characters",
    db_model=DBManuscriptPerson,
    wiki_class=WikiCharacter,
    query_builder=_build_character_query,
    name_extractor=lambda ms_person: ms_person.person.display_name,
    output_subdir="manuscript",
)

# Configuration for manuscript entries
MANUSCRIPT_ENTRY_EXPORT_CONFIG = EntityExportConfig(
    entity_name="manuscript_entry",
    entity_plural="manuscript_entries",
    db_model=DBManuscriptEntry,
    wiki_class=WikiManuscriptEntry,
    query_builder=_build_manuscript_entry_query,
    name_extractor=lambda ms_entry: str(ms_entry.entry.date),
    output_subdir="manuscript",
)

# Configuration for manuscript events
MANUSCRIPT_EVENT_EXPORT_CONFIG = EntityExportConfig(
    entity_name="manuscript_event",
    entity_plural="manuscript_events",
    db_model=DBManuscriptEvent,
    wiki_class=WikiManuscriptEvent,
    query_builder=_build_manuscript_event_query,
    name_extractor=lambda ms_event: ms_event.event.event,
    output_subdir="manuscript",
)

# Configuration for journal events
EVENT_EXPORT_CONFIG = EntityExportConfig(
    entity_name="event",
    entity_plural="events",
    db_model=DBEvent,
    wiki_class=WikiEvent,
    query_builder=_build_event_query,
    name_extractor=lambda event: event.event,
    output_subdir=None,
)

# Configuration for themes
THEME_EXPORT_CONFIG = EntityExportConfig(
    entity_name="theme",
    entity_plural="themes",
    db_model=DBTheme,
    wiki_class=WikiTheme,
    query_builder=_build_theme_query,
    name_extractor=lambda theme: theme.theme,
    output_subdir=None,
)

# Grouped configurations for batch operations
ALL_MANUSCRIPT_CONFIGS = [
    MANUSCRIPT_ENTRY_EXPORT_CONFIG,
    CHARACTER_EXPORT_CONFIG,
    MANUSCRIPT_EVENT_EXPORT_CONFIG,
]

ALL_JOURNAL_CONFIGS = [
    EVENT_EXPORT_CONFIG,
    THEME_EXPORT_CONFIG,
]

ALL_ENTITY_CONFIGS = ALL_MANUSCRIPT_CONFIGS + ALL_JOURNAL_CONFIGS
