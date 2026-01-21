#!/usr/bin/env python3
"""
wiki2sql.py
-----------
Import wiki edits back to database (wiki→database sync).

Parses wiki markdown files for editable fields (notes, vignettes, etc.)
and updates the corresponding database records.

Features:
    - Import editable fields from wiki files
    - Update database records while preserving computed fields
    - Batch import with statistics
    - Sync state tracking with conflict detection

Usage:
    # Import via CLI
    palimpsest import-wiki people
    palimpsest import-wiki entries
    palimpsest import-wiki all
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# --- Third party imports ---
from sqlalchemy import select, func

# --- Local imports ---
from dev.database.manager import PalimpsestDB
from dev.database.models import Entry, Event, Person, Tag
from dev.database.models_manuscript import Theme, ManuscriptPerson, ManuscriptEvent
from dev.database.sync_state_manager import SyncStateManager

from dev.wiki.parser import (
    parse_entry_file,
    parse_event_file,
    parse_person_file,
    parse_tag_file,
    parse_theme_file,
    parse_manuscript_entry_file,
    parse_manuscript_character_file,
    parse_manuscript_event_file,
)

from dev.core.logging_manager import PalimpsestLogger
from dev.utils import fs


class ImportStats:
    """Statistics for wiki import operations."""

    def __init__(self):
        self.files_processed: int = 0
        self.records_updated: int = 0
        self.records_skipped: int = 0
        self.errors: int = 0


def import_people(
    wiki_dir: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger] = None
) -> ImportStats:
    """Import all people notes from wiki."""
    stats = ImportStats()
    people_dir = wiki_dir / "people"

    if not people_dir.exists():
        return stats

    for wiki_file in people_dir.glob("*.md"):
        stats.files_processed += 1
        data = parse_person_file(wiki_file)
        if not data:
            stats.records_skipped += 1
            continue

        with db.session_scope() as session:
            person = session.execute(
                select(Person).where(func.lower(Person.name) == data["name"].lower())
            ).scalar_one_or_none()

            if not person:
                stats.records_skipped += 1
                continue

            updated = False
            if data["notes"] and data["notes"] != person.notes:
                person.notes = data["notes"]
                updated = True

            if updated:
                session.commit()
                stats.records_updated += 1
            else:
                stats.records_skipped += 1

    return stats


def import_entries(
    wiki_dir: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger] = None
) -> ImportStats:
    """Import all entry notes from wiki."""
    stats = ImportStats()
    entries_dir = wiki_dir / "entries"

    if not entries_dir.exists():
        return stats

    # Entries are in year subdirectories
    for year_dir in entries_dir.iterdir():
        if not year_dir.is_dir():
            continue
        for wiki_file in year_dir.glob("*.md"):
            stats.files_processed += 1
            data = parse_entry_file(wiki_file)
            if not data:
                stats.records_skipped += 1
                continue

            file_hash = fs.get_file_hash(wiki_file)
            machine_id = socket.gethostname()

            with db.session_scope() as session:
                entry = session.execute(
                    select(Entry).where(Entry.date == data["date"])
                ).scalar_one_or_none()

                if not entry:
                    stats.records_skipped += 1
                    continue

                sync_mgr = SyncStateManager(session, logger)

                updated = False
                if data["notes"] and data["notes"] != entry.notes:
                    entry.notes = data["notes"]
                    updated = True

                if updated:
                    sync_mgr.update_or_create(
                        entity_type="Entry",
                        entity_id=entry.id,
                        last_synced_at=datetime.now(timezone.utc),
                        sync_source="wiki",
                        sync_hash=file_hash,
                        machine_id=machine_id,
                    )
                    session.commit()
                    stats.records_updated += 1
                else:
                    stats.records_skipped += 1

    return stats


def import_events(
    wiki_dir: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger] = None
) -> ImportStats:
    """Import all event notes from wiki."""
    stats = ImportStats()
    events_dir = wiki_dir / "events"

    if not events_dir.exists():
        return stats

    for wiki_file in events_dir.glob("*.md"):
        stats.files_processed += 1
        data = parse_event_file(wiki_file)
        if not data:
            stats.records_skipped += 1
            continue

        file_hash = fs.get_file_hash(wiki_file)
        machine_id = socket.gethostname()

        with db.session_scope() as session:
            event = session.execute(
                select(Event).where(func.lower(Event.event) == data["event"].lower())
            ).scalar_one_or_none()

            if not event:
                stats.records_skipped += 1
                continue

            sync_mgr = SyncStateManager(session, logger)

            updated = False
            if data["notes"] and data["notes"] != event.notes:
                event.notes = data["notes"]
                updated = True

            if updated:
                sync_mgr.update_or_create(
                    entity_type="Event",
                    entity_id=event.id,
                    last_synced_at=datetime.now(timezone.utc),
                    sync_source="wiki",
                    sync_hash=file_hash,
                    machine_id=machine_id,
                )
                session.commit()
                stats.records_updated += 1
            else:
                stats.records_skipped += 1

    return stats


def import_tags(
    wiki_dir: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger] = None
) -> ImportStats:
    """Import all tag notes from wiki."""
    stats = ImportStats()
    tags_dir = wiki_dir / "tags"

    if not tags_dir.exists():
        return stats

    for wiki_file in tags_dir.glob("*.md"):
        stats.files_processed += 1
        data = parse_tag_file(wiki_file)
        if not data:
            stats.records_skipped += 1
            continue

        with db.session_scope() as session:
            tag = session.execute(
                select(Tag).where(func.lower(Tag.tag) == data["tag"].lower())
            ).scalar_one_or_none()

            if not tag:
                stats.records_skipped += 1
                continue

            updated = False
            if data["notes"] and data["notes"] != tag.notes:
                tag.notes = data["notes"]
                updated = True

            if updated:
                session.commit()
                stats.records_updated += 1
            else:
                stats.records_skipped += 1

    return stats


def import_themes(
    wiki_dir: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger] = None
) -> ImportStats:
    """Import all theme notes from wiki."""
    stats = ImportStats()
    themes_dir = wiki_dir / "themes"

    if not themes_dir.exists():
        return stats

    for wiki_file in themes_dir.glob("*.md"):
        stats.files_processed += 1
        data = parse_theme_file(wiki_file)
        if not data:
            stats.records_skipped += 1
            continue

        with db.session_scope() as session:
            theme = session.execute(
                select(Theme).where(func.lower(Theme.theme) == data["theme"].lower())
            ).scalar_one_or_none()

            if not theme:
                stats.records_skipped += 1
                continue

            updated = False
            if data["notes"] and data["notes"] != theme.notes:
                theme.notes = data["notes"]
                updated = True

            if updated:
                session.commit()
                stats.records_updated += 1
            else:
                stats.records_skipped += 1

    return stats


def import_all(
    wiki_dir: Path, db: PalimpsestDB, logger: Optional[PalimpsestLogger] = None
) -> ImportStats:
    """Import all entity types from wiki."""
    combined = ImportStats()

    for import_func in [import_people, import_entries, import_events, import_tags, import_themes]:
        stats = import_func(wiki_dir, db, logger)
        combined.files_processed += stats.files_processed
        combined.records_updated += stats.records_updated
        combined.records_skipped += stats.records_skipped
        combined.errors += stats.errors

    return combined


# --- Manuscript Import Functions ---


def import_all_manuscript_entries(
    db: PalimpsestDB, wiki_dir: Path, logger: Optional[PalimpsestLogger] = None
) -> ImportStats:
    """Import all manuscript entry notes from wiki."""
    stats = ImportStats()
    entries_dir = wiki_dir / "manuscript" / "entries"

    if not entries_dir.exists():
        return stats

    for year_dir in entries_dir.iterdir():
        if not year_dir.is_dir():
            continue
        for wiki_file in year_dir.glob("*.md"):
            stats.files_processed += 1
            data = parse_manuscript_entry_file(wiki_file)
            if not data:
                stats.records_skipped += 1
                continue

            with db.session_scope() as session:
                entry = session.execute(
                    select(Entry).where(Entry.date == data["date"])
                ).scalar_one_or_none()

                if not entry or not entry.manuscript:
                    stats.records_skipped += 1
                    continue

                ms_entry = entry.manuscript
                updated = False

                if data["notes"] and data["notes"] != ms_entry.notes:
                    ms_entry.notes = data["notes"]
                    updated = True

                if data["character_notes"] and data["character_notes"] != ms_entry.character_notes:
                    ms_entry.character_notes = data["character_notes"]
                    updated = True

                if updated:
                    session.commit()
                    stats.records_updated += 1
                else:
                    stats.records_skipped += 1

    return stats


def import_all_manuscript_characters(
    db: PalimpsestDB, wiki_dir: Path, logger: Optional[PalimpsestLogger] = None
) -> ImportStats:
    """Import all manuscript character notes from wiki."""
    stats = ImportStats()
    chars_dir = wiki_dir / "manuscript" / "characters"

    if not chars_dir.exists():
        return stats

    for wiki_file in chars_dir.glob("*.md"):
        stats.files_processed += 1
        data = parse_manuscript_character_file(wiki_file)
        if not data:
            stats.records_skipped += 1
            continue

        with db.session_scope() as session:
            ms_person = session.execute(
                select(ManuscriptPerson).where(ManuscriptPerson.character == data["name"])
            ).scalar_one_or_none()

            if not ms_person:
                stats.records_skipped += 1
                continue

            updated = False
            for field in ["character_description", "character_arc", "voice_notes", "appearance_notes"]:
                if data[field] and data[field] != getattr(ms_person, field):
                    setattr(ms_person, field, data[field])
                    updated = True

            if updated:
                session.commit()
                stats.records_updated += 1
            else:
                stats.records_skipped += 1

    return stats


def import_all_manuscript_events(
    db: PalimpsestDB, wiki_dir: Path, logger: Optional[PalimpsestLogger] = None
) -> ImportStats:
    """Import all manuscript event notes from wiki."""
    stats = ImportStats()
    events_dir = wiki_dir / "manuscript" / "events"

    if not events_dir.exists():
        return stats

    for wiki_file in events_dir.glob("*.md"):
        stats.files_processed += 1
        data = parse_manuscript_event_file(wiki_file)
        if not data:
            stats.records_skipped += 1
            continue

        with db.session_scope() as session:
            event = session.execute(
                select(Event).where(func.lower(Event.event) == data["name"].lower())
            ).scalar_one_or_none()

            if not event:
                stats.records_skipped += 1
                continue

            ms_event = session.execute(
                select(ManuscriptEvent).where(ManuscriptEvent.event_id == event.id)
            ).scalar_one_or_none()

            if not ms_event:
                stats.records_skipped += 1
                continue

            updated = False
            if data["notes"] and data["notes"] != ms_event.notes:
                ms_event.notes = data["notes"]
                updated = True

            if updated:
                session.commit()
                stats.records_updated += 1
            else:
                stats.records_skipped += 1

    return stats
