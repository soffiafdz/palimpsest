#!/usr/bin/env python3
"""
associations.py
---------------
Many-to-many relationship tables for the Palimpsest database.

This module contains all association tables organized by domain:

Journal Domain - Core:
    - entry_cities: Entries ↔ Cities
    - entry_locations: Entries ↔ Locations
    - entry_people: Entries ↔ People
    - narrated_dates: Dates narrated within entries

Journal Domain - Analysis:
    - scene_dates: Scenes ↔ Dates
    - scene_people: Scenes ↔ People
    - scene_locations: Scenes ↔ Locations
    - event_scenes: Events ↔ Scenes
    - event_entries: Events ↔ Entries
    - arc_entries: Arcs ↔ Entries
    - thread_people: Threads ↔ People
    - thread_locations: Threads ↔ Locations

Journal Domain - Metadata:
    - entry_tags: Entries ↔ Tags
    - motif_instances: Motifs → Entries (with description)
    - theme_instances: Themes → Entries (with description)

Manuscript Domain:
    - chapter_poems: Chapters ↔ Poems
    - chapter_characters: Chapters ↔ Characters
    - chapter_arcs: Chapters ↔ Arcs

These are pure association tables with no additional metadata (except where noted).
"""
# --- Third party imports ---
from sqlalchemy import Column, ForeignKey, Integer, Table

# --- Local imports ---
from .base import Base


# =============================================================================
# JOURNAL DOMAIN - CORE ASSOCIATIONS
# =============================================================================

entry_cities = Table(
    "entry_cities",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "city_id",
        Integer,
        ForeignKey("cities.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

entry_locations = Table(
    "entry_locations",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "location_id",
        Integer,
        ForeignKey("locations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

entry_people = Table(
    "entry_people",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "person_id",
        Integer,
        ForeignKey("people.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# =============================================================================
# JOURNAL DOMAIN - ANALYSIS ASSOCIATIONS
# =============================================================================

scene_people = Table(
    "scene_people",
    Base.metadata,
    Column(
        "scene_id",
        Integer,
        ForeignKey("scenes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "person_id",
        Integer,
        ForeignKey("people.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

scene_locations = Table(
    "scene_locations",
    Base.metadata,
    Column(
        "scene_id",
        Integer,
        ForeignKey("scenes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "location_id",
        Integer,
        ForeignKey("locations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

event_scenes = Table(
    "event_scenes",
    Base.metadata,
    Column(
        "event_id",
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "scene_id",
        Integer,
        ForeignKey("scenes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

arc_entries = Table(
    "arc_entries",
    Base.metadata,
    Column(
        "arc_id",
        Integer,
        ForeignKey("arcs.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

event_entries = Table(
    "event_entries",
    Base.metadata,
    Column(
        "event_id",
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

thread_people = Table(
    "thread_people",
    Base.metadata,
    Column(
        "thread_id",
        Integer,
        ForeignKey("threads.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "person_id",
        Integer,
        ForeignKey("people.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

thread_locations = Table(
    "thread_locations",
    Base.metadata,
    Column(
        "thread_id",
        Integer,
        ForeignKey("threads.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "location_id",
        Integer,
        ForeignKey("locations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# =============================================================================
# JOURNAL DOMAIN - METADATA ASSOCIATIONS
# =============================================================================

entry_tags = Table(
    "entry_tags",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        Integer,
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# =============================================================================
# MANUSCRIPT DOMAIN ASSOCIATIONS
# =============================================================================

chapter_poems = Table(
    "chapter_poems",
    Base.metadata,
    Column(
        "chapter_id",
        Integer,
        ForeignKey("chapters.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "poem_id",
        Integer,
        ForeignKey("poems.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

chapter_characters = Table(
    "chapter_characters",
    Base.metadata,
    Column(
        "chapter_id",
        Integer,
        ForeignKey("chapters.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "character_id",
        Integer,
        ForeignKey("characters.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

chapter_arcs = Table(
    "chapter_arcs",
    Base.metadata,
    Column(
        "chapter_id",
        Integer,
        ForeignKey("chapters.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "arc_id",
        Integer,
        ForeignKey("arcs.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
