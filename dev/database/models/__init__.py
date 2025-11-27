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
- geography: MentionedDate, City, Location
- creative: Poem, Reference, Event
- sync: Tombstone, SyncState, EntitySnapshot

For backward compatibility, all models are re-exported from the root package.

Usage:
    from dev.database.models import Entry, Person, Tag
    # All imports work as before
"""
# Base classes
from .base import Base, SoftDeleteMixin

# Enumerations
from .enums import ReferenceMode, ReferenceType, RelationType

# Association tables (for direct usage if needed)
from .associations import (
    entry_aliases,
    entry_cities,
    entry_dates,
    entry_events,
    entry_locations,
    entry_people,
    entry_related,
    entry_tags,
    event_people,
    location_dates,
    people_dates,
)

# Core models
from .core import Entry, SchemaInfo

# Geography models
from .geography import City, Location, MentionedDate

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
    "entry_dates",
    "entry_events",
    "entry_locations",
    "entry_people",
    "entry_related",
    "entry_tags",
    "event_people",
    "location_dates",
    "people_dates",
    # Core
    "SchemaInfo",
    "Entry",
    # Geography
    "MentionedDate",
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
