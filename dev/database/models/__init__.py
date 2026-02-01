#!/usr/bin/env python3
"""
Database Models Package
-----------------------

SQLAlchemy ORM models for the Palimpsest metadata database.

This package provides a modular organization of database models:

Base:
    - base: Base class and SoftDeleteMixin

Enumerations:
    - enums: All enumeration types (ReferenceMode, ChapterType, etc.)

Association Tables:
    - associations: Many-to-many relationship tables

Journal Domain - Core:
    - core: Entry, NarratedDate, SchemaInfo

Journal Domain - Geography:
    - geography: City, Location

Journal Domain - Entities:
    - entities: Person, Tag, Theme

Journal Domain - Analysis:
    - analysis: Scene, SceneDate, Event, Arc, Thread

Journal Domain - Creative:
    - creative: ReferenceSource, Reference, Poem, PoemVersion

Journal Domain - Metadata:
    - metadata: Motif, MotifInstance

Manuscript Domain:
    - manuscript: Part, Chapter, Character, PersonCharacterMap,
                  ManuscriptScene, ManuscriptSource, ManuscriptReference

Usage:
    from dev.database.models import Entry, Scene, Person, Chapter
"""
# --- Base classes ---
from .base import Base, SoftDeleteMixin

# --- Enumerations ---
from .enums import (
    ChapterStatus,
    ChapterType,
    ContributionType,
    ReferenceMode,
    ReferenceType,
    RelationType,
    SceneOrigin,
    SceneStatus,
    SourceType,
)

# --- Association tables ---
from .associations import (
    arc_entries,
    chapter_arcs,
    chapter_characters,
    chapter_poems,
    entry_cities,
    entry_locations,
    entry_people,
    entry_tags,
    entry_themes,
    event_entries,
    event_scenes,
    scene_locations,
    scene_people,
    thread_locations,
    thread_people,
)

# --- Core models ---
from .core import Entry, NarratedDate, SchemaInfo

# --- Geography models ---
from .geography import City, Location

# --- Entity models ---
from .entities import Person, PersonAlias, Tag, Theme

# --- Analysis models ---
from .analysis import Arc, Event, Scene, SceneDate, Thread

# --- Creative models ---
from .creative import Poem, PoemVersion, Reference, ReferenceSource

# --- Metadata models ---
from .metadata import CONTROLLED_MOTIFS, Motif, MotifInstance

# --- Manuscript models ---
from .manuscript import (
    Chapter,
    Character,
    ManuscriptReference,
    ManuscriptScene,
    ManuscriptSource,
    Part,
    PersonCharacterMap,
)

__all__ = [
    # Base
    "Base",
    "SoftDeleteMixin",
    # Enums
    "ChapterStatus",
    "ChapterType",
    "ContributionType",
    "ReferenceMode",
    "ReferenceType",
    "RelationType",
    "SceneOrigin",
    "SceneStatus",
    "SourceType",
    # Association tables
    "arc_entries",
    "chapter_arcs",
    "chapter_characters",
    "chapter_poems",
    "entry_cities",
    "entry_locations",
    "entry_people",
    "entry_tags",
    "entry_themes",
    "event_entries",
    "event_scenes",
    "scene_locations",
    "scene_people",
    "thread_locations",
    "thread_people",
    # Core
    "Entry",
    "NarratedDate",
    "SchemaInfo",
    # Geography
    "City",
    "Location",
    # Entities
    "Person",
    "PersonAlias",
    "Tag",
    "Theme",
    # Analysis
    "Arc",
    "Event",
    "Scene",
    "SceneDate",
    "Thread",
    # Creative
    "Poem",
    "PoemVersion",
    "Reference",
    "ReferenceSource",
    # Metadata
    "CONTROLLED_MOTIFS",
    "Motif",
    "MotifInstance",
    # Manuscript
    "Chapter",
    "Character",
    "ManuscriptReference",
    "ManuscriptScene",
    "ManuscriptSource",
    "Part",
    "PersonCharacterMap",
]
