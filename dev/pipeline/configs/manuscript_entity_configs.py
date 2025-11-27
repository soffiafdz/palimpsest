#!/usr/bin/env python3
"""
manuscript_entity_configs.py
-----------------------------

Entity export configurations for manuscript-designated entities.

This module defines configuration objects for manuscript entity types
(entries, characters, events, arcs, themes), used by the EntityExporter
framework to export manuscript-designated content to data/wiki/manuscript/.

Note: This is separate from entity_configs.py which handles general journal
export. Manuscript export uses specialized models (models_manuscript) and
dataclasses (dataclasses.manuscript_*).
"""
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

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

from dev.dataclasses.manuscript_entry import ManuscriptEntry as WikiManuscriptEntry
from dev.dataclasses.manuscript_character import Character as WikiCharacter
from dev.dataclasses.manuscript_event import ManuscriptEvent as WikiManuscriptEvent
from dev.dataclasses.manuscript_arc import Arc as WikiArc
from dev.dataclasses.manuscript_theme import Theme as WikiTheme

from dev.pipeline.entity_exporter import EntityExportConfig


# ========================================
# Query Builders
# ========================================

def _build_character_query(session: Session):
    """Build query for manuscript characters."""
    return (
        select(DBManuscriptPerson)
        .join(DBPerson)
        .options(joinedload(DBManuscriptPerson.person))
        .order_by(DBManuscriptPerson.character)
    )


def _build_event_query(session: Session):
    """Build query for manuscript events."""
    return (
        select(DBManuscriptEvent)
        .join(DBEvent)
        .options(
            joinedload(DBManuscriptEvent.event).joinedload(DBEvent.entries),
            joinedload(DBManuscriptEvent.event).joinedload(DBEvent.people).joinedload(DBPerson.manuscript),
            joinedload(DBManuscriptEvent.arc),
        )
        .order_by(DBEvent.event)
    )


def _build_arc_query(session: Session):
    """Build query for story arcs."""
    return (
        select(DBArc)
        .options(
            joinedload(DBArc.events).joinedload(DBManuscriptEvent.event),
        )
        .order_by(DBArc.arc)
    )


def _build_theme_query(session: Session):
    """Build query for manuscript themes."""
    return (
        select(DBTheme)
        .options(
            joinedload(DBTheme.entries).joinedload(DBManuscriptEntry.entry),
        )
        .order_by(DBTheme.theme)
    )


# ========================================
# Custom Converters
# ========================================

def _convert_character(ms_person, wiki_dir, journal_dir):
    """Convert ManuscriptPerson to WikiCharacter."""
    return WikiCharacter.from_database(
        ms_person.person,  # Base Person object
        ms_person,          # ManuscriptPerson object
        wiki_dir,
        journal_dir,
    )


def _convert_manuscript_event(ms_event, wiki_dir, journal_dir):
    """Convert ManuscriptEvent to WikiManuscriptEvent."""
    return WikiManuscriptEvent.from_database(
        ms_event.event,  # Base Event object
        ms_event,        # ManuscriptEvent object
        wiki_dir,
        journal_dir,
    )


def _convert_arc(arc, wiki_dir, journal_dir):
    """Convert Arc to WikiArc."""
    return WikiArc.from_database(arc, wiki_dir, journal_dir)


def _convert_theme(theme, wiki_dir, journal_dir):
    """Convert Theme to WikiTheme."""
    return WikiTheme.from_database(theme, wiki_dir, journal_dir)


# ========================================
# Entity Configurations
# ========================================

# Configuration for manuscript characters
CHARACTER_EXPORT_CONFIG = EntityExportConfig(
    entity_name="character",
    entity_plural="characters",
    db_model=DBManuscriptPerson,
    wiki_class=WikiCharacter,
    query_builder=_build_character_query,
    name_extractor=lambda ms_person: ms_person.character,
    output_subdir="manuscript",
    entity_converter=_convert_character,
)

# Configuration for manuscript events
MANUSCRIPT_EVENT_EXPORT_CONFIG = EntityExportConfig(
    entity_name="manuscript_event",
    entity_plural="manuscript_events",
    db_model=DBManuscriptEvent,
    wiki_class=WikiManuscriptEvent,
    query_builder=_build_event_query,
    name_extractor=lambda ms_event: ms_event.event.event,
    output_subdir="manuscript",
    entity_converter=_convert_manuscript_event,
)

# Configuration for story arcs
ARC_EXPORT_CONFIG = EntityExportConfig(
    entity_name="arc",
    entity_plural="arcs",
    db_model=DBArc,
    wiki_class=WikiArc,
    query_builder=_build_arc_query,
    name_extractor=lambda arc: arc.arc,
    output_subdir="manuscript",
    entity_converter=_convert_arc,
)

# Configuration for manuscript themes
MANUSCRIPT_THEME_EXPORT_CONFIG = EntityExportConfig(
    entity_name="manuscript_theme",
    entity_plural="manuscript_themes",
    db_model=DBTheme,
    wiki_class=WikiTheme,
    query_builder=_build_theme_query,
    name_extractor=lambda theme: theme.theme,
    output_subdir="manuscript",
    entity_converter=_convert_theme,
)

# Grouped configurations for batch operations
ALL_MANUSCRIPT_CONFIGS = [
    CHARACTER_EXPORT_CONFIG,
    MANUSCRIPT_EVENT_EXPORT_CONFIG,
    ARC_EXPORT_CONFIG,
    MANUSCRIPT_THEME_EXPORT_CONFIG,
]
