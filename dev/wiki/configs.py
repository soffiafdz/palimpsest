#!/usr/bin/env python3
"""
configs.py
----------
Entity export configurations for the wiki system.

Defines how to query, name, and locate each entity type for wiki export.
Each EntityConfig specifies the template, output folder, and query logic
for a single entity type.

Configs:
    - PERSON_CONFIG: People entity export
    - LOCATION_CONFIG: Location entity export
    - CITY_CONFIG: City entity export
    - ENTRY_CONFIG: Journal entry export
    - EVENT_CONFIG: Event entity export
    - TAG_CONFIG: Tag entity export
    - THEME_CONFIG: Theme entity export
    - REFERENCE_CONFIG: Reference entity export
    - POEM_CONFIG: Poem entity export
    - ARC_CONFIG: Arc entity export
    - CHAPTER_CONFIG: Chapter entity export
    - CHARACTER_CONFIG: Character entity export
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from dataclasses import dataclass
from typing import Any, Callable, List

# --- Third party imports ---
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

# --- Local imports ---
from dev.database.models import (
    Arc,
    Chapter,
    Character,
    City,
    Entry,
    Event,
    Location,
    Person,
    Poem,
    PoemVersion,
    ReferenceSource,
    Tag,
    Theme,
)
from dev.utils.wiki import slugify


@dataclass
class EntityConfig:
    """
    Configuration for exporting an entity type to wiki.

    Attributes:
        name: Singular name (person, location)
        plural: Plural name (people, locations)
        template: Template name without .jinja2 extension
        folder: Wiki subfolder for this entity type
        query: Function that takes a Session and returns list of entities
        get_name: Function that extracts display name from entity
        get_slug: Function that extracts slug for filename
    """

    name: str
    plural: str
    template: str
    folder: str
    query: Callable[[Session], List[Any]]
    get_name: Callable[[Any], str]
    get_slug: Callable[[Any], str]


# --- Query Functions ---

def _query_people(session: Session) -> List[Person]:
    """Query all non-deleted people with relationships loaded."""
    return session.scalars(
        select(Person)
        .options(
            joinedload(Person.entries),
            joinedload(Person.scenes),
            joinedload(Person.threads),
        )
        .where(Person.deleted_at.is_(None))
        .order_by(Person.name)
    ).unique().all()


def _query_locations(session: Session) -> List[Location]:
    """Query all locations with relationships loaded."""
    return session.scalars(
        select(Location)
        .options(
            joinedload(Location.city),
            joinedload(Location.entries),
            joinedload(Location.scenes),
        )
        .order_by(Location.name)
    ).unique().all()


def _query_cities(session: Session) -> List[City]:
    """Query all cities with relationships loaded."""
    return session.scalars(
        select(City)
        .options(
            joinedload(City.locations),
            joinedload(City.entries),
        )
        .order_by(City.name)
    ).unique().all()


def _query_entries(session: Session) -> List[Entry]:
    """Query all entries with relationships loaded."""
    return session.scalars(
        select(Entry)
        .options(
            joinedload(Entry.people),
            joinedload(Entry.locations),
            joinedload(Entry.tags),
            joinedload(Entry.events),
            joinedload(Entry.poems),
            joinedload(Entry.references),
            joinedload(Entry.scenes),
            joinedload(Entry.threads),
        )
        .order_by(Entry.date.desc())
    ).unique().all()


def _query_events(session: Session) -> List[Event]:
    """Query all events with relationships loaded."""
    return session.scalars(
        select(Event)
        .options(
            joinedload(Event.entries),
            joinedload(Event.scenes),
        )
        .order_by(Event.name)
    ).unique().all()


def _query_tags(session: Session) -> List[Tag]:
    """Query all tags with relationships loaded."""
    return session.scalars(
        select(Tag)
        .options(joinedload(Tag.entries))
        .order_by(Tag.name)
    ).unique().all()


def _query_themes(session: Session) -> List[Theme]:
    """Query all themes with relationships loaded."""
    return session.scalars(
        select(Theme)
        .options(joinedload(Theme.entries))
        .order_by(Theme.name)
    ).unique().all()


def _query_references(session: Session) -> List[ReferenceSource]:
    """Query all reference sources with relationships loaded."""
    return session.scalars(
        select(ReferenceSource)
        .options(joinedload(ReferenceSource.references))
        .order_by(ReferenceSource.title)
    ).unique().all()


def _query_poems(session: Session) -> List[Poem]:
    """Query all poems with versions loaded."""
    return session.scalars(
        select(Poem)
        .options(joinedload(Poem.versions).joinedload(PoemVersion.entry))
        .order_by(Poem.title)
    ).unique().all()


def _query_arcs(session: Session) -> List[Arc]:
    """Query all arcs with relationships loaded."""
    return session.scalars(
        select(Arc)
        .options(joinedload(Arc.entries))
        .order_by(Arc.name)
    ).unique().all()


def _query_chapters(session: Session) -> List[Chapter]:
    """Query all chapters with relationships loaded."""
    return session.scalars(
        select(Chapter)
        .options(
            joinedload(Chapter.part),
            joinedload(Chapter.poems),
            joinedload(Chapter.characters),
            joinedload(Chapter.arcs),
        )
        .order_by(Chapter.number, Chapter.title)
    ).unique().all()


def _query_characters(session: Session) -> List[Character]:
    """Query all characters with relationships loaded."""
    return session.scalars(
        select(Character)
        .options(
            joinedload(Character.chapters),
            joinedload(Character.person_mappings),
        )
        .order_by(Character.name)
    ).unique().all()


# --- Entity Configurations ---

PERSON_CONFIG = EntityConfig(
    name="person",
    plural="people",
    template="person",
    folder="people",
    query=_query_people,
    get_name=lambda p: p.display_name,
    get_slug=lambda p: slugify(p.display_name),
)

LOCATION_CONFIG = EntityConfig(
    name="location",
    plural="locations",
    template="location",
    folder="locations",
    query=_query_locations,
    get_name=lambda loc: loc.name,
    get_slug=lambda loc: slugify(loc.name),
)

CITY_CONFIG = EntityConfig(
    name="city",
    plural="cities",
    template="city",
    folder="cities",
    query=_query_cities,
    get_name=lambda c: c.name,
    get_slug=lambda c: slugify(c.name),
)

ENTRY_CONFIG = EntityConfig(
    name="entry",
    plural="entries",
    template="entry",
    folder="entries",
    query=_query_entries,
    get_name=lambda e: e.date.isoformat(),
    get_slug=lambda e: e.date.isoformat(),
)

EVENT_CONFIG = EntityConfig(
    name="event",
    plural="events",
    template="event",
    folder="events",
    query=_query_events,
    get_name=lambda e: e.name,
    get_slug=lambda e: slugify(e.name),
)

TAG_CONFIG = EntityConfig(
    name="tag",
    plural="tags",
    template="tag",
    folder="tags",
    query=_query_tags,
    get_name=lambda t: t.name,
    get_slug=lambda t: slugify(t.name),
)

THEME_CONFIG = EntityConfig(
    name="theme",
    plural="themes",
    template="theme",
    folder="themes",
    query=_query_themes,
    get_name=lambda t: t.name,
    get_slug=lambda t: slugify(t.name),
)

REFERENCE_CONFIG = EntityConfig(
    name="reference",
    plural="references",
    template="reference",
    folder="references",
    query=_query_references,
    get_name=lambda r: r.title,
    get_slug=lambda r: slugify(r.title),
)

POEM_CONFIG = EntityConfig(
    name="poem",
    plural="poems",
    template="poem",
    folder="poems",
    query=_query_poems,
    get_name=lambda p: p.title,
    get_slug=lambda p: slugify(p.title),
)

ARC_CONFIG = EntityConfig(
    name="arc",
    plural="arcs",
    template="arc",
    folder="narrative/arcs",
    query=_query_arcs,
    get_name=lambda a: a.name,
    get_slug=lambda a: slugify(a.name),
)

# All entity configs for batch export
ALL_CONFIGS = [
    PERSON_CONFIG,
    LOCATION_CONFIG,
    CITY_CONFIG,
    ENTRY_CONFIG,
    EVENT_CONFIG,
    TAG_CONFIG,
    THEME_CONFIG,
    REFERENCE_CONFIG,
    POEM_CONFIG,
    ARC_CONFIG,
]


# --- Manuscript Entity Configurations ---

CHAPTER_CONFIG = EntityConfig(
    name="chapter",
    plural="chapters",
    template="chapter",
    folder="manuscript/chapters",
    query=_query_chapters,
    get_name=lambda c: c.title,
    get_slug=lambda c: slugify(c.title),
)

CHARACTER_CONFIG = EntityConfig(
    name="character",
    plural="characters",
    template="character",
    folder="manuscript/characters",
    query=_query_characters,
    get_name=lambda c: c.name,
    get_slug=lambda c: slugify(c.name),
)

# All manuscript entity configs for manuscript export
MANUSCRIPT_CONFIGS = [
    CHAPTER_CONFIG,
    CHARACTER_CONFIG,
]
