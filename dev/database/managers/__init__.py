#!/usr/bin/env python3
"""
managers package
--------------------
Modular entity managers for the Palimpsest database.

Each manager handles CRUD operations for a specific entity type,
following the Single Responsibility Principle and inheriting from BaseManager.

Available Managers:
    BaseManager: Abstract base class with common utilities
    TagManager: Manages Tag entities and their relationships
    EventManager: Manages Event entities
    DateManager: Manages MentionedDate entities
    LocationManager: Manages City and Location entities
    ReferenceManager: Manages ReferenceSource and Reference entities
    PoemManager: Manages Poem and PoemVersion entities
    PersonManager: Manages Person and Alias entities
    ManuscriptManager: Manages manuscript-related entities
    EntryManager: Manages Entry entities (most complex)

Usage:
    from dev.database.managers import PersonManager, EntryManager

    person_mgr = PersonManager(session, logger)
    person = person_mgr.create({"name": "John Doe"})
"""
from .base_manager import BaseManager
from .tag_manager import TagManager
from .event_manager import EventManager
from .date_manager import DateManager
from .location_manager import LocationManager
from .reference_manager import ReferenceManager
from .poem_manager import PoemManager

__all__ = [
    "BaseManager",
    "TagManager",
    "EventManager",
    "DateManager",
    "LocationManager",
    "ReferenceManager",
    "PoemManager",
]

# Additional managers will be added as they are implemented:
# See REFACTORING_GUIDE.md for implementation templates
# from .person_manager import PersonManager
# from .manuscript_manager import ManuscriptManager
# from .entry_manager import EntryManager
# from .entry_relationship_handler import EntryRelationshipHandler
