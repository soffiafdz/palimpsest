"""
Association Tables
-------------------

Many-to-many relationship tables for the Palimpsest database.

This module contains all association tables that connect:
- Entries with moments, cities, locations, people, events, tags
- Events with people and moments
- Locations and people with moments
- Entries with related entries (self-referential)

These are pure association tables with no additional metadata.

Note: The original "dates" table was renamed to "moments" (P25) to better
reflect the semantic meaning - a moment is a point in time with context,
people, and locations, not just a date reference.
"""
# --- Third party imports ---
from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, Table

# --- Local imports ---
from .base import Base

# Entry associations
entry_moments = Table(
    "entry_moments",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("moment_id", Integer, ForeignKey("moments.id", ondelete="CASCADE"), primary_key=True),
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

# Moment associations (locations and people linked to specific moments)
moment_locations = Table(
    "moment_locations",
    Base.metadata,
    Column(
        "moment_id",
        Integer,
        ForeignKey("moments.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "location_id",
        Integer,
        ForeignKey("locations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

moment_people = Table(
    "moment_people",
    Base.metadata,
    Column(
        "moment_id",
        Integer,
        ForeignKey("moments.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "person_id",
        Integer,
        ForeignKey("people.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# NEW: Moments can belong to multiple events (M2M)
moment_events = Table(
    "moment_events",
    Base.metadata,
    Column(
        "moment_id",
        Integer,
        ForeignKey("moments.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "event_id",
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

