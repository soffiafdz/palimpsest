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
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from dataclasses import dataclass
from typing import Any, Callable, List, Type

# --- Third party imports ---
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

# --- Local imports ---
from dev.database.models import (
    Person,
    Location,
    City,
    Entry,
    Event,
    Tag,
    Poem,
    PoemVersion,
    ReferenceSource,
)
from dev.database.models_manuscript import Theme
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
            joinedload(Person.moments),
            joinedload(Person.aliases),
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
            joinedload(Location.moments),
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
        .order_by(City.city)
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
        )
        .order_by(Entry.date.desc())
    ).unique().all()


def _query_events(session: Session) -> List[Event]:
    """Query all non-deleted events with relationships loaded."""
    return session.scalars(
        select(Event)
        .options(
            joinedload(Event.entries),
            joinedload(Event.moments),
        )
        .where(Event.deleted_at.is_(None))
        .order_by(Event.event)
    ).unique().all()


def _query_tags(session: Session) -> List[Tag]:
    """Query all non-deleted tags with relationships loaded."""
    return session.scalars(
        select(Tag)
        .options(joinedload(Tag.entries))
        .where(Tag.deleted_at.is_(None))
        .order_by(Tag.tag)
    ).unique().all()


def _query_themes(session: Session) -> List[Theme]:
    """Query all themes with relationships loaded."""
    return session.scalars(
        select(Theme)
        .options(joinedload(Theme.entries))
        .where(Theme.deleted_at.is_(None))
        .order_by(Theme.theme)
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
    get_name=lambda l: l.name,
    get_slug=lambda l: slugify(l.name),
)

CITY_CONFIG = EntityConfig(
    name="city",
    plural="cities",
    template="city",
    folder="cities",
    query=_query_cities,
    get_name=lambda c: c.city,
    get_slug=lambda c: slugify(c.city),
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
    get_name=lambda e: e.event,
    get_slug=lambda e: slugify(e.event),
)

TAG_CONFIG = EntityConfig(
    name="tag",
    plural="tags",
    template="tag",
    folder="tags",
    query=_query_tags,
    get_name=lambda t: t.tag,
    get_slug=lambda t: slugify(t.tag),
)

THEME_CONFIG = EntityConfig(
    name="theme",
    plural="themes",
    template="theme",
    folder="themes",
    query=_query_themes,
    get_name=lambda t: t.theme,
    get_slug=lambda t: slugify(t.theme),
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
]
