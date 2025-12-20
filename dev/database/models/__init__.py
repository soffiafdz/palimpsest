"""
Database Models Package
------------------------

SQLAlchemy ORM models for the Palimpsest metadata database.

This package provides a modular organization of database models:
- base: Base class and mixins
- associations: Many-to-many relationship tables
- enums: Enumeration types
- core: Entry model and schema info
- entities: Person, Alias, Tag
- geography: Moment, City, Location
- creative: Poem, Reference, Event
- sync: Tombstone, SyncState, EntitySnapshot

Note: MentionedDate was renamed to Moment (P25 schema enhancement).

Usage:
    from dev.database.models import Entry, Person, Tag, Moment
"""
# Base classes
from .base import Base, SoftDeleteMixin

# Enumerations
from .enums import ReferenceMode, ReferenceType, RelationType

# Association tables (for direct usage if needed)
from .associations import (
    entry_aliases,
    entry_cities,
    entry_events,
    entry_locations,
    entry_moments,
    entry_people,
    entry_related,
    entry_tags,
    event_people,
    moment_events,
    moment_locations,
    moment_people,
)

# Core models
from .core import Entry, SchemaInfo

# Geography models
from .geography import City, Location, Moment

# Entity models
from .entities import Alias, Person, Tag

# Creative works
from .creative import Event, Poem, PoemVersion, Reference, ReferenceSource

# Sync models
from .sync import AssociationTombstone, EntitySnapshot, SyncState

__all__ = [
    # Base
    "Base",
    "SoftDeleteMixin",
    # Enums
    "ReferenceMode",
    "ReferenceType",
    "RelationType",
    # Association tables
    "entry_aliases",
    "entry_cities",
    "entry_events",
    "entry_locations",
    "entry_moments",
    "entry_people",
    "entry_related",
    "entry_tags",
    "event_people",
    "moment_events",
    "moment_locations",
    "moment_people",
    # Core
    "SchemaInfo",
    "Entry",
    # Geography
    "Moment",
    "City",
    "Location",
    # People
    "Person",
    "Alias",
    # Creative
    "Reference",
    "ReferenceSource",
    "Event",
    "Poem",
    "PoemVersion",
    # Tags
    "Tag",
    # Sync
    "AssociationTombstone",
    "SyncState",
    "EntitySnapshot",
]
