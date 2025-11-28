#!/usr/bin/env python3
"""
json_export_configs.py
----------------------

Configuration-driven JSON export for database entities.

This module defines export configurations for all database entity types,
eliminating duplication in export_manager.py's export_to_json method.
"""
from dataclasses import dataclass
from typing import Any, Callable, Dict, Type

from ..models import (
    Person,
    Location,
    Event,
    Tag,
    ReferenceSource,
    Reference,
    MentionedDate,
    Poem,
    PoemVersion,
    Alias,
)
from ..models_manuscript import (
    ManuscriptEntry,
    ManuscriptPerson,
    ManuscriptEvent,
    Theme,
    Arc,
)


@dataclass
class EntityExportConfig:
    """
    Configuration for exporting an entity type to JSON.

    Attributes:
        json_key: Key name in the JSON output (e.g., "people", "locations")
        model: SQLAlchemy model class to query
        serializer: Function that takes an entity instance and returns a dict
    """
    json_key: str
    model: Type
    serializer: Callable[[Any], Dict[str, Any]]


# ========================================
# Serializer Functions
# ========================================

def _serialize_person(person: Person) -> Dict[str, Any]:
    """Serialize Person entity."""
    return {
        "id": person.id,
        "name": person.name,
        "full_name": person.full_name,
        "entry_count": len(person.entries),
    }


def _serialize_location(location: Location) -> Dict[str, Any]:
    """Serialize Location entity."""
    return {
        "id": location.id,
        "name": location.name,
    }


def _serialize_event(event: Event) -> Dict[str, Any]:
    """Serialize Event entity."""
    return {
        "id": event.id,
        "event": event.event,
        "title": event.title,
        "description": event.description,
    }


def _serialize_tag(tag: Tag) -> Dict[str, Any]:
    """Serialize Tag entity."""
    return {
        "id": tag.id,
        "tag": tag.tag,
        "entry_count": len(tag.entries),
    }


def _serialize_reference_source(source: ReferenceSource) -> Dict[str, Any]:
    """Serialize ReferenceSource entity."""
    return {
        "id": source.id,
        "title": source.title,
        "type": source.type.value if source.type else None,
        "author": source.author,
    }


def _serialize_reference(ref: Reference) -> Dict[str, Any]:
    """Serialize Reference entity."""
    return {
        "id": ref.id,
        "entry_id": ref.entry_id,
        "source_id": ref.source_id,
        "content": ref.content,
        "description": ref.description,
        "mode": ref.mode.value if ref.mode else "direct",
        "speaker": ref.speaker,
    }


def _serialize_mentioned_date(md: MentionedDate) -> Dict[str, Any]:
    """Serialize MentionedDate entity."""
    return {
        "id": md.id,
        "entry_ids": [e.id for e in md.entries] if md.entries else [],
        "date": md.date.isoformat() if md.date else None,
        "context": md.context,
    }


def _serialize_poem(poem: Poem) -> Dict[str, Any]:
    """Serialize Poem entity."""
    return {
        "id": poem.id,
        "title": poem.title,
        "version_count": len(poem.versions),
    }


def _serialize_poem_version(pv: PoemVersion) -> Dict[str, Any]:
    """Serialize PoemVersion entity."""
    return {
        "id": pv.id,
        "poem_id": pv.poem_id,
        "entry_id": pv.entry_id,
        "content": pv.content,
        "notes": pv.notes,
        "revision_date": pv.revision_date.isoformat() if pv.revision_date else None,
    }


def _serialize_alias(alias: Alias) -> Dict[str, Any]:
    """Serialize Alias entity."""
    return {
        "id": alias.id,
        "person_id": alias.person_id,
        "alias": alias.alias,
    }


def _serialize_manuscript_entry(me: ManuscriptEntry) -> Dict[str, Any]:
    """Serialize ManuscriptEntry entity."""
    return {
        "id": me.id,
        "entry_id": me.entry_id,
        "status": me.status.value if me.status else None,
        "edited": me.edited,
        "notes": me.notes,
    }


def _serialize_manuscript_person(mp: ManuscriptPerson) -> Dict[str, Any]:
    """Serialize ManuscriptPerson entity."""
    return {
        "id": mp.id,
        "person_id": mp.person_id,
        "character": mp.character,
        "character_description": mp.character_description,
        "character_arc": mp.character_arc,
    }


def _serialize_manuscript_event(me: ManuscriptEvent) -> Dict[str, Any]:
    """Serialize ManuscriptEvent entity."""
    return {
        "id": me.id,
        "event_id": me.event_id,
        "arc_id": me.arc_id,
        "notes": me.notes,
    }


def _serialize_manuscript_theme(mt: Theme) -> Dict[str, Any]:
    """Serialize Theme entity."""
    return {
        "id": mt.id,
        "theme": mt.theme,
        "entry_count": len(mt.entries),
    }


def _serialize_arc(arc: Arc) -> Dict[str, Any]:
    """Serialize Arc entity."""
    return {
        "id": arc.id,
        "arc": arc.arc,
        "event_count": len(arc.events),
    }


# ========================================
# Export Configurations
# ========================================

# Core entity configurations (in order they appear in JSON output)
EXPORT_CONFIGS = [
    EntityExportConfig("people", Person, _serialize_person),
    EntityExportConfig("locations", Location, _serialize_location),
    EntityExportConfig("events", Event, _serialize_event),
    EntityExportConfig("tags", Tag, _serialize_tag),
    EntityExportConfig("reference_sources", ReferenceSource, _serialize_reference_source),
    EntityExportConfig("references", Reference, _serialize_reference),
    EntityExportConfig("mentioned_dates", MentionedDate, _serialize_mentioned_date),
    EntityExportConfig("poems", Poem, _serialize_poem),
    EntityExportConfig("poem_versions", PoemVersion, _serialize_poem_version),
    EntityExportConfig("aliases", Alias, _serialize_alias),
    EntityExportConfig("manuscript_entries", ManuscriptEntry, _serialize_manuscript_entry),
    EntityExportConfig("manuscript_people", ManuscriptPerson, _serialize_manuscript_person),
    EntityExportConfig("manuscript_events", ManuscriptEvent, _serialize_manuscript_event),
    EntityExportConfig("manuscript_themes", Theme, _serialize_manuscript_theme),
    EntityExportConfig("arcs", Arc, _serialize_arc),
]
