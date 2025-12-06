#!/usr/bin/env python3
"""
sql2wiki.py
-----------
Export database entities to Vimwiki pages.

This pipeline orchestrates the export of structured database records into
human-readable vimwiki entity pages (people, themes, tags, entries, locations,
cities, events) and special pages (index, stats, timeline, analysis).

Uses builders from dev/builders/:
- wiki.py: GenericEntityExporter for entity export
- wiki_indexes.py: Custom index builders
- wiki_pages.py: Special page exports

Usage:
    # Export specific entity type
    python -m dev.pipeline.sql2wiki export people
    python -m dev.pipeline.sql2wiki export entries

    # Export all entities
    python -m dev.pipeline.sql2wiki export all

    # Export special pages
    python -m dev.pipeline.sql2wiki export index
    python -m dev.pipeline.sql2wiki export stats

    # Force regeneration
    python -m dev.pipeline.sql2wiki export all --force
"""
from __future__ import annotations

from pathlib import Path

# Builder imports
from dev.builders.wiki import (
    EntityConfig,
        register_entity,
    get_exporter,
)
from dev.builders.wiki_indexes import (
    build_people_index,
    build_entries_index,
    build_locations_index,
    build_cities_index,
    build_events_index,
)
from dev.builders.wiki_pages import (
    export_entries_with_navigation,
    export_index,
    export_stats,
    export_timeline,
    export_analysis_report,
)

# Dataclass imports
from dev.dataclasses.wiki_person import Person as WikiPerson
from dev.dataclasses.wiki_theme import Theme as WikiTheme
from dev.dataclasses.wiki_tag import Tag as WikiTag
from dev.dataclasses.wiki_poem import Poem as WikiPoem
from dev.dataclasses.wiki_reference import Reference as WikiReference
from dev.dataclasses.wiki_entry import Entry as WikiEntry
from dev.dataclasses.wiki_location import Location as WikiLocation
from dev.dataclasses.wiki_city import City as WikiCity
from dev.dataclasses.wiki_event import Event as WikiEvent

# Database model imports
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

# Core imports
from dev.database.manager import PalimpsestDB
from dev.core.paths import LOG_DIR, DB_PATH, WIKI_DIR, MD_DIR, ALEMBIC_DIR, BACKUP_DIR
from dev.core.exceptions import Sql2WikiError
from dev.core.logging_manager import PalimpsestLogger



def register_all_entities():
    """Register all entity configurations."""

    # People (custom index builder)
    register_entity("people", EntityConfig(
        name="person",
        plural="people",
        db_model=DBPerson,
        wiki_class=WikiPerson,
        output_subdir="people",
        index_filename="people.md",
        eager_loads=["entries", "manuscript"],
        index_builder=build_people_index,  # Custom
        sort_by="name",
        order_by="name",  # Use database column, not property
    ))

    # Themes (default index)
    register_entity("themes", EntityConfig(
        name="theme",
        plural="themes",
        db_model=DBTheme,
        wiki_class=WikiTheme,
        output_subdir="themes",
        index_filename="themes.md",
        eager_loads=["entries"],
        index_builder=None,  # Use default
        sort_by="name",
        order_by="theme",
    ))

    # Tags (default index)
    register_entity("tags", EntityConfig(
        name="tag",
        plural="tags",
        db_model=DBTag,
        wiki_class=WikiTag,
        output_subdir="tags",
        index_filename="tags.md",
        eager_loads=["entries"],
        index_builder=None,  # Use default
        sort_by="name",
        order_by="tag",
    ))

    # Poems (default index)
    register_entity("poems", EntityConfig(
        name="poem",
        plural="poems",
        db_model=DBPoem,
        wiki_class=WikiPoem,
        output_subdir="poems",
        index_filename="poems.md",
        eager_loads=["versions"],
        index_builder=None,  # Use default
        sort_by="title",
        order_by="title",
    ))

    # References (default index)
    register_entity("references", EntityConfig(
        name="reference",
        plural="references",
        db_model=DBReferenceSource,
        wiki_class=WikiReference,
        output_subdir="references",
        index_filename="references.md",
        eager_loads=["references"],
        index_builder=None,  # Use default
        sort_by="title",
        order_by="title",
    ))

    # Entries (custom index builder)
    register_entity("entries", EntityConfig(
        name="entry",
        plural="entries",
        db_model=DBEntry,
        wiki_class=WikiEntry,
        output_subdir="entries",
        index_filename="entries.md",
        eager_loads=[
            "dates",
            "cities",
            "locations.city",  # Nested load
            "people",
            "events",
            "tags",
            "poems",
            "references",
            "manuscript",
            "related_entries",
        ],
        index_builder=build_entries_index,  # Custom
        custom_export_all=export_entries_with_navigation,  # Custom export with prev/next navigation
        sort_by="date",
        order_by="date",
    ))

    # Locations (custom index builder)
    register_entity("locations", EntityConfig(
        name="location",
        plural="locations",
        db_model=DBLocation,
        wiki_class=WikiLocation,
        output_subdir="locations",
        index_filename="locations.md",
        eager_loads=[
            "city",
            "entries.people",  # Nested load
            "dates",
        ],
        index_builder=build_locations_index,  # Custom
        sort_by="name",
        order_by="name",
    ))

    # Cities (custom index builder)
    register_entity("cities", EntityConfig(
        name="city",
        plural="cities",
        db_model=DBCity,
        wiki_class=WikiCity,
        output_subdir="cities",
        index_filename="cities.md",
        eager_loads=[
            "entries",
            "locations",
        ],
        index_builder=build_cities_index,  # Custom
        sort_by="name",
        order_by="city",
    ))

    # Events (custom index builder)
    register_entity("events", EntityConfig(
        name="event",
        plural="events",
        db_model=DBEvent,
        wiki_class=WikiEvent,
        output_subdir="events",
        index_filename="events.md",
        eager_loads=[
            "entries",
            "people",
            "manuscript",
        ],
        index_builder=build_events_index,  # Custom
        sort_by="display_name",
        order_by="event",
    ))


# Register all entities on module import
register_all_entities()


# ===== CLI =====


