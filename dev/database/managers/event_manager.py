#!/usr/bin/env python3
"""
event_manager.py
----------------
STUB: Minimal EventManager to satisfy imports.

Event is currently a one-to-many relationship from Entry, not a standalone
managed entity. This stub exists only to prevent import errors until Event
processing is properly implemented.

Note: Event handling in entry_manager.py treats Event as M2M which is incorrect.
The Event model has entry_id FK making it one-to-many from Entry.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from dev.core.logging_manager import PalimpsestLogger
from .base_manager import BaseManager


class EventManager(BaseManager):
    """
    Stub EventManager - not fully implemented.

    Event is one-to-many from Entry and should not be managed separately.
    This class exists only to prevent import errors.
    """

    def __init__(self, session: Session, logger: Optional[PalimpsestLogger] = None):
        """Initialize EventManager stub."""
        super().__init__(session, logger)

    def get_or_create(self, name: str) -> None:
        """
        Stub method - not implemented.

        Events are tied to entries and should be created through entry_manager.
        """
        raise NotImplementedError(
            "Event get_or_create not implemented - Event is one-to-many from Entry"
        )
