"""
Association Tables
-------------------

Many-to-many relationship tables for the Palimpsest database.

This module contains all association tables that connect:
- Entries with dates, cities, locations, people, events, tags
- Events with people
- Locations and people with dates
- Entries with related entries (self-referential)

These are pure association tables with no additional metadata.
"""
from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, Table

from .base import Base

# Entry associations
entry_dates = Table(
    "entry_dates",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("date_id", Integer, ForeignKey("dates.id", ondelete="CASCADE"), primary_key=True),
)

entry_cities = Table(
    "entry_cities",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("city_id", Integer, ForeignKey("cities.id", ondelete="CASCADE"), primary_key=True),
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
    Column("location_id", Integer, ForeignKey("locations.id", ondelete="CASCADE"), primary_key=True),
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
    Column("people_id", Integer, ForeignKey("people.id", ondelete="CASCADE"), primary_key=True),
)

entry_aliases = Table(
    "entry_aliases",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "alias_id",
        Integer,
        ForeignKey("aliases.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

entry_events = Table(
    "entry_events",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "event_id",
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

entry_tags = Table(
    "entry_tags",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

# Self-referential entry relationships
entry_related = Table(
    "entry_related",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "related_entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    # No self-references || duplicate pairs
    CheckConstraint("entry_id != related_entry_id", name="no_self_reference"),
)

# Event associations
event_people = Table(
    "event_people",
    Base.metadata,
    Column(
        "event_id",
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "person_id",
        Integer,
        ForeignKey("people.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# Geography and people date associations
location_dates = Table(
    "location_dates",
    Base.metadata,
    Column(
        "location_id",
        Integer,
        ForeignKey("locations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "date_id",
        Integer,
        ForeignKey("dates.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

people_dates = Table(
    "people_dates",
    Base.metadata,
    Column(
        "person_id",
        Integer,
        ForeignKey("people.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "date_id",
        Integer,
        ForeignKey("dates.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
