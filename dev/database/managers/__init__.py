#!/usr/bin/env python3
"""
managers package
--------------------
Modular entity managers for the Palimpsest database.

Each manager handles CRUD operations for a specific entity type,
following the Single Responsibility Principle and inheriting from BaseManager.

Available Managers:
    BaseManager: Abstract base class with common utilities
    SimpleManager: Config-driven manager for Tag, MentionedDate, Event
    TagManager: Factory for Tag SimpleManager (alias)
    EventManager: Factory for Event SimpleManager (alias)
    DateManager: Factory for MentionedDate SimpleManager (alias)
    LocationManager: Manages City and Location entities
    ReferenceManager: Manages ReferenceSource and Reference entities
    PoemManager: Manages Poem and PoemVersion entities
    PersonManager: Manages Person and Alias entities
    ManuscriptManager: Manages manuscript-related entities
    EntryManager: Manages Entry entities (most complex)

Usage:
    from dev.database.managers import PersonManager, TagManager

    person_mgr = PersonManager(session, logger)
    tag_mgr = TagManager(session, logger)  # Returns SimpleManager
"""
from .base_manager import BaseManager
from .simple_manager import SimpleManager, TagManager, DateManager, EventManager
from .location_manager import LocationManager
from .reference_manager import ReferenceManager
from .poem_manager import PoemManager
from .person_manager import PersonManager
from .manuscript_manager import ManuscriptManager
from .entry_manager import EntryManager

__all__ = [
    "BaseManager",
    "SimpleManager",
    "TagManager",
    "EventManager",
    "DateManager",
    "LocationManager",
    "ReferenceManager",
    "PoemManager",
    "PersonManager",
    "ManuscriptManager",
    "EntryManager",
]
