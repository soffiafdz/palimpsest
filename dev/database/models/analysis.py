#!/usr/bin/env python3
"""
analysis.py
-----------
Narrative analysis models for the Palimpsest database.

This module contains models for narrative structure analysis:

Models:
    - Scene: Granular narrative moment within an entry
    - SceneDate: Dates associated with a scene
    - Event: Groups of related scenes within an entry
    - Arc: Story arcs spanning multiple entries
    - Thread: Temporal echoes/connections between moments

These models enable rich narrative structure analysis of journal entries.

Design:
    - Scene is the core narrative unit
    - SceneDate tracks dates associated with scenes
    - Event groups scenes within an entry
    - Arc spans entries (not scenes directly)
    - Thread captures temporal connections with proximate/distant dates
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date
from typing import TYPE_CHECKING, List, Optional

# --- Third party imports ---
from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

# --- Local imports ---
from .associations import (
    arc_entries,
    event_entries,
    event_scenes,
    scene_locations,
    scene_people,
    thread_locations,
    thread_people,
)
from .base import Base

if TYPE_CHECKING:
    from .core import Entry
    from .entities import Person
    from .geography import Location


class Scene(Base):
    """
    A granular narrative moment within a journal entry.

    Scenes are the core narrative units. Each scene represents
    a distinct moment in the journal narrative with its own
    name, description, dates, people, and locations.

    Attributes:
        id: Primary key
        name: Scene name (unique within entry)
        description: Narrative description
        entry_id: Foreign key to parent Entry

    Relationships:
        entry: Many-to-one with Entry (parent entry)
        dates: One-to-many with SceneDate (dates of this scene)
        people: M2M with Person (people in this scene)
        locations: M2M with Location (locations of this scene)
        events: M2M with Event (events containing this scene)

    Notes:
        - Unique constraint on (name, entry_id)
        - A scene can span multiple dates (multi-day scenes)
    """

    __tablename__ = "scenes"
    __table_args__ = (
        CheckConstraint("name != ''", name="ck_scene_non_empty_name"),
        UniqueConstraint("name", "entry_id", name="uq_scene_name_entry"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    entry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entries.id", ondelete="CASCADE"), nullable=False
    )

    # --- Relationships ---
    entry: Mapped["Entry"] = relationship("Entry", back_populates="scenes")
    dates: Mapped[List["SceneDate"]] = relationship(
        "SceneDate", back_populates="scene", cascade="all, delete-orphan"
    )
    people: Mapped[List["Person"]] = relationship(
        "Person", secondary=scene_people, back_populates="scenes"
    )
    locations: Mapped[List["Location"]] = relationship(
        "Location", secondary=scene_locations, back_populates="scenes"
    )
    events: Mapped[List["Event"]] = relationship(
        "Event", secondary=event_scenes, back_populates="scenes"
    )

    # --- Computed properties ---
    @property
    def primary_date(self) -> Optional[str]:
        """Get the primary (first) date of this scene as string."""
        if not self.dates:
            return None
        # Sort by parsed date tuple for comparison
        return min(self.dates, key=lambda sd: sd.date_parsed[:3]).date

    @property
    def primary_date_as_date(self) -> Optional[date]:
        """Get the primary (first) date of this scene as date object."""
        if not self.dates:
            return None
        return min(sd.as_date for sd in self.dates)

    @property
    def date_range(self) -> tuple[Optional[str], Optional[str]]:
        """Get the date range (start, end) of this scene as strings."""
        if not self.dates:
            return (None, None)
        sorted_dates = sorted(self.dates, key=lambda sd: sd.date_parsed[:3])
        return (sorted_dates[0].date, sorted_dates[-1].date)

    @property
    def date_range_as_dates(self) -> tuple[Optional[date], Optional[date]]:
        """Get the date range (start, end) of this scene as date objects."""
        if not self.dates:
            return (None, None)
        dates = [sd.as_date for sd in self.dates]
        return (min(dates), max(dates))

    @property
    def is_multiday(self) -> bool:
        """Check if this scene spans multiple days."""
        start, end = self.date_range_as_dates
        return start is not None and end is not None and start != end

    @property
    def people_names(self) -> List[str]:
        """Get list of people names in this scene."""
        return [p.display_name for p in self.people]

    @property
    def location_names(self) -> List[str]:
        """Get list of location names in this scene."""
        return [loc.name for loc in self.locations]

    def __repr__(self) -> str:
        return f"<Scene(id={self.id}, name='{self.name}', entry_id={self.entry_id})>"

    def __str__(self) -> str:
        return f"{self.name} ({self.entry.date_formatted})"


class SceneDate(Base):
    """
    A date associated with a scene.

    Scenes can span multiple dates. SceneDate tracks each date
    that a scene occurs on.

    Attributes:
        id: Primary key
        date: The date of this scene (supports flexible formats)
        scene_id: Foreign key to parent Scene

    Notes:
        - date is stored as string to support flexible formats:
          - Exact dates: YYYY-MM-DD
          - Month precision: YYYY-MM
          - Year precision: YYYY
          - Approximate dates: ~YYYY, ~YYYY-MM, ~YYYY-MM-DD
    """

    __tablename__ = "scene_dates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(11), nullable=False, index=True)
    scene_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False
    )

    # --- Relationship ---
    scene: Mapped["Scene"] = relationship("Scene", back_populates="dates")

    # --- Static helpers ---
    @staticmethod
    def parse_flexible_date(date_str: str) -> tuple[int, int, int, bool]:
        """
        Parse a flexible date string into sortable components.

        Supports formats:
        - YYYY-MM-DD (exact day)
        - YYYY-MM (month precision, uses day=1)
        - YYYY (year precision, uses month=1, day=1)
        - ~YYYY-MM-DD, ~YYYY-MM, ~YYYY (approximate, same parsing)

        Args:
            date_str: Date string to parse

        Returns:
            Tuple of (year, month, day, is_approximate)
            Month and day default to 1 if not specified.
        """
        is_approximate = date_str.startswith("~")
        clean_date = date_str.lstrip("~")

        parts = clean_date.split("-")
        year = int(parts[0]) if len(parts) >= 1 else 1
        month = int(parts[1]) if len(parts) >= 2 else 1
        day = int(parts[2]) if len(parts) >= 3 else 1

        return (year, month, day, is_approximate)

    @property
    def date_parsed(self) -> tuple[int, int, int, bool]:
        """Parse date into (year, month, day, is_approximate)."""
        return self.parse_flexible_date(self.date)

    @property
    def is_approximate(self) -> bool:
        """Check if this date is approximate (~)."""
        return self.date.startswith("~")

    @property
    def as_date(self) -> date:
        """Convert to Python date object (for sorting/comparison)."""
        year, month, day, _ = self.date_parsed
        return date(year, month, day)

    def __repr__(self) -> str:
        return f"<SceneDate(date={self.date}, scene_id={self.scene_id})>"


class Event(Base):
    """
    Groups related scenes across one or more entries.

    Events provide a middle layer of organization between scenes
    and entries. They group related scenes that form a coherent
    narrative unit. An event can span multiple entries (e.g., a party
    narrated across two journal entries).

    Attributes:
        id: Primary key
        name: Event name (globally unique)

    Relationships:
        entries: M2M with Entry (entries containing this event)
        scenes: M2M with Scene (scenes in this event)

    Notes:
        - Unique constraint on name (events are shared across entries)
        - Same-named events across entries point to the same Event record
    """

    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("name != ''", name="ck_event_non_empty_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    # --- Relationships ---
    entries: Mapped[List["Entry"]] = relationship(
        "Entry", secondary=event_entries, back_populates="events"
    )
    scenes: Mapped[List["Scene"]] = relationship(
        "Scene", secondary=event_scenes, back_populates="events"
    )

    # --- Computed properties ---
    @property
    def scene_count(self) -> int:
        """Number of scenes in this event."""
        return len(self.scenes)

    @property
    def entry_count(self) -> int:
        """Number of entries containing this event."""
        return len(self.entries)

    @property
    def scene_names(self) -> List[str]:
        """Names of all scenes in this event."""
        return [scene.name for scene in self.scenes]

    @property
    def all_people(self) -> List["Person"]:
        """Get all people from all scenes in this event."""
        people_set: set = set()
        for scene in self.scenes:
            people_set.update(scene.people)
        return list(people_set)

    @property
    def all_locations(self) -> List["Location"]:
        """Get all locations from all scenes in this event."""
        locations_set: set = set()
        for scene in self.scenes:
            locations_set.update(scene.locations)
        return list(locations_set)

    def __repr__(self) -> str:
        return f"<Event(id={self.id}, name='{self.name}')>"

    def __str__(self) -> str:
        return f"{self.name} ({self.scene_count} scenes, {self.entry_count} entries)"


class Arc(Base):
    """
    A story arc spanning multiple journal entries.

    Arcs represent overarching narrative threads that span
    multiple entries. They provide high-level organization
    for thematic or character-based storylines.

    Attributes:
        id: Primary key
        name: Arc name (unique)
        description: Optional description of the arc

    Relationships:
        entries: M2M with Entry (entries in this arc)
    """

    __tablename__ = "arcs"
    __table_args__ = (CheckConstraint("name != ''", name="ck_arc_non_empty_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # --- Relationships ---
    entries: Mapped[List["Entry"]] = relationship(
        "Entry", secondary=arc_entries, back_populates="arcs"
    )

    # --- Computed properties ---
    @property
    def entry_count(self) -> int:
        """Number of entries in this arc."""
        return len(self.entries)

    @property
    def date_range(self) -> tuple[Optional[date], Optional[date]]:
        """Get the date range (start, end) of this arc."""
        if not self.entries:
            return (None, None)
        dates = [e.date for e in self.entries]
        return (min(dates), max(dates))

    @property
    def first_entry_date(self) -> Optional[date]:
        """Earliest entry date in this arc."""
        if not self.entries:
            return None
        return min(e.date for e in self.entries)

    @property
    def last_entry_date(self) -> Optional[date]:
        """Most recent entry date in this arc."""
        if not self.entries:
            return None
        return max(e.date for e in self.entries)

    def __repr__(self) -> str:
        return f"<Arc(id={self.id}, name='{self.name}')>"

    def __str__(self) -> str:
        return f"{self.name} ({self.entry_count} entries)"


class Thread(Base):
    """
    A temporal echo/connection between moments.

    Threads capture connections between moments that are narratively
    significant. They link a proximate moment (near the entry's date)
    to a distant moment (past or future).

    Attributes:
        id: Primary key
        name: Thread name (unique identifier)
        from_date: Proximate moment date (supports ~YYYY, ~YYYY-MM, YYYY-MM-DD)
        to_date: Distant moment date (supports ~YYYY, ~YYYY-MM, YYYY-MM-DD)
        referenced_entry_date: Optional date of entry narrating distant moment
        content: Description of the CONNECTION between moments
        entry_id: Foreign key to parent Entry

    Relationships:
        entry: Many-to-one with Entry (parent entry)
        people: M2M with Person (people in this thread)
        locations: M2M with Location (locations in this thread)

    Notes:
        - Both from_date and to_date are strings to support:
          - Exact dates: YYYY-MM-DD
          - Month precision: YYYY-MM
          - Year precision: YYYY
          - Approximate dates: ~YYYY, ~YYYY-MM, ~YYYY-MM-DD
        - content describes the connection, not the individual moments
    """

    __tablename__ = "threads"
    __table_args__ = (CheckConstraint("name != ''", name="ck_thread_non_empty_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    from_date: Mapped[str] = mapped_column(String(11), nullable=False)  # ~YYYY-MM-DD max
    to_date: Mapped[str] = mapped_column(String(11), nullable=False)  # ~YYYY-MM-DD max
    referenced_entry_date: Mapped[Optional[date]] = mapped_column(Date)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    entry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entries.id", ondelete="CASCADE"), nullable=False
    )

    # --- Relationships ---
    entry: Mapped["Entry"] = relationship("Entry", back_populates="threads")
    people: Mapped[List["Person"]] = relationship(
        "Person", secondary=thread_people, back_populates="threads"
    )
    locations: Mapped[List["Location"]] = relationship(
        "Location", secondary=thread_locations, back_populates="threads"
    )

    # --- Static helpers ---
    @staticmethod
    def parse_flexible_date(date_str: str) -> tuple[int, int, int, bool]:
        """
        Parse a flexible date string into sortable components.

        Supports formats:
        - YYYY-MM-DD (exact day)
        - YYYY-MM (month precision, uses day=1)
        - YYYY (year precision, uses month=1, day=1)
        - ~YYYY-MM-DD, ~YYYY-MM, ~YYYY (approximate, same parsing)

        Args:
            date_str: Date string to parse

        Returns:
            Tuple of (year, month, day, is_approximate)
            Month and day default to 1 if not specified.
        """
        is_approximate = date_str.startswith("~")
        clean_date = date_str.lstrip("~")

        parts = clean_date.split("-")
        year = int(parts[0]) if len(parts) >= 1 else 1
        month = int(parts[1]) if len(parts) >= 2 else 1
        day = int(parts[2]) if len(parts) >= 3 else 1

        return (year, month, day, is_approximate)

    # --- Computed properties ---
    @property
    def from_date_parsed(self) -> tuple[int, int, int, bool]:
        """Parse from_date into (year, month, day, is_approximate)."""
        return self.parse_flexible_date(self.from_date)

    @property
    def to_date_parsed(self) -> tuple[int, int, int, bool]:
        """Parse to_date into (year, month, day, is_approximate)."""
        return self.parse_flexible_date(self.to_date)

    @property
    def from_date_approximate(self) -> bool:
        """Check if from_date is approximate (~)."""
        return self.from_date.startswith("~")

    @property
    def to_date_approximate(self) -> bool:
        """Check if to_date is approximate (~)."""
        return self.to_date.startswith("~")

    @property
    def is_past_thread(self) -> bool:
        """Check if this thread references a past moment."""
        try:
            from_tuple = self.from_date_parsed[:3]  # (year, month, day)
            to_tuple = self.to_date_parsed[:3]
            return to_tuple < from_tuple
        except (ValueError, IndexError):
            return False

    @property
    def is_future_thread(self) -> bool:
        """Check if this thread references a future moment."""
        return not self.is_past_thread

    @property
    def people_names(self) -> List[str]:
        """Get list of people names in this thread."""
        return [p.display_name for p in self.people]

    @property
    def location_names(self) -> List[str]:
        """Get list of location names in this thread."""
        return [loc.name for loc in self.locations]

    def __repr__(self) -> str:
        return f"<Thread(id={self.id}, name='{self.name}', from={self.from_date}, to={self.to_date})>"

    def __str__(self) -> str:
        direction = "past" if self.is_past_thread else "future"
        return f"{self.name} ({self.from_date} → {self.to_date}, {direction})"
