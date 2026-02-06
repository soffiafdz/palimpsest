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
    Arc,
    Event,
    Location,
    Person,
    Poem,
    PoemVersion,
    Reference,
    ReferenceSource,
    Scene,
    Tag,
    Theme,
    Thread,
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
        "lastname": person.lastname,
        "slug": person.slug,
        "relation_type": person.relation_type.value if person.relation_type else None,
        "entry_count": len(person.entries),
    }


def _serialize_location(location: Location) -> Dict[str, Any]:
    """Serialize Location entity."""
    return {
        "id": location.id,
        "name": location.name,
        "city_id": location.city_id,
        "city_name": location.city.name if location.city else None,
    }


def _serialize_scene(scene: Scene) -> Dict[str, Any]:
    """Serialize Scene entity."""
    return {
        "id": scene.id,
        "name": scene.name,
        "description": scene.description,
        "entry_id": scene.entry_id,
        "date_count": len(scene.dates),
        "people_count": len(scene.people),
        "location_count": len(scene.locations),
    }


def _serialize_event(event: Event) -> Dict[str, Any]:
    """Serialize Event entity."""
    return {
        "id": event.id,
        "name": event.name,
        "scene_count": len(event.scenes),
        "entry_count": len(event.entries),
    }


def _serialize_arc(arc: Arc) -> Dict[str, Any]:
    """Serialize Arc entity."""
    return {
        "id": arc.id,
        "name": arc.name,
        "description": arc.description,
        "entry_count": len(arc.entries),
    }


def _serialize_thread(thread: Thread) -> Dict[str, Any]:
    """Serialize Thread entity."""
    return {
        "id": thread.id,
        "name": thread.name,
        "from_date": thread.from_date,
        "to_date": thread.to_date,
        "referenced_entry_date": (
            thread.referenced_entry_date.isoformat()
            if thread.referenced_entry_date else None
        ),
        "content": thread.content,
        "entry_id": thread.entry_id,
    }


def _serialize_tag(tag: Tag) -> Dict[str, Any]:
    """Serialize Tag entity."""
    return {
        "id": tag.id,
        "name": tag.name,
        "entry_count": len(tag.entries),
    }


def _serialize_theme(theme: Theme) -> Dict[str, Any]:
    """Serialize Theme entity."""
    return {
        "id": theme.id,
        "name": theme.name,
        "entry_count": len(theme.entries),
    }


def _serialize_reference_source(source: ReferenceSource) -> Dict[str, Any]:
    """Serialize ReferenceSource entity."""
    return {
        "id": source.id,
        "title": source.title,
        "author": source.author,
        "type": source.type.value if source.type else None,
        "url": source.url,
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
    }


# ========================================
# Export Configurations
# ========================================

# Core entity configurations (in order they appear in JSON output)
EXPORT_CONFIGS = [
    EntityExportConfig("people", Person, _serialize_person),
    EntityExportConfig("locations", Location, _serialize_location),
    EntityExportConfig("scenes", Scene, _serialize_scene),
    EntityExportConfig("events", Event, _serialize_event),
    EntityExportConfig("arcs", Arc, _serialize_arc),
    EntityExportConfig("threads", Thread, _serialize_thread),
    EntityExportConfig("tags", Tag, _serialize_tag),
    EntityExportConfig("themes", Theme, _serialize_theme),
    EntityExportConfig("reference_sources", ReferenceSource, _serialize_reference_source),
    EntityExportConfig("references", Reference, _serialize_reference),
    EntityExportConfig("poems", Poem, _serialize_poem),
    EntityExportConfig("poem_versions", PoemVersion, _serialize_poem_version),
]
