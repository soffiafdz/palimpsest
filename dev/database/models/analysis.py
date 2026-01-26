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
    def primary_date(self) -> Optional[date]:
        """Get the primary (first) date of this scene."""
        if not self.dates:
            return None
        return min(sd.date for sd in self.dates)

    @property
    def date_range(self) -> tuple[Optional[date], Optional[date]]:
        """Get the date range (start, end) of this scene."""
        if not self.dates:
            return (None, None)
        dates = [sd.date for sd in self.dates]
        return (min(dates), max(dates))

    @property
    def is_multiday(self) -> bool:
        """Check if this scene spans multiple days."""
        start, end = self.date_range
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
        date: The date of this scene
        scene_id: Foreign key to parent Scene
    """

    __tablename__ = "scene_dates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scene_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False
    )

    # --- Relationship ---
    scene: Mapped["Scene"] = relationship("Scene", back_populates="dates")

    def __repr__(self) -> str:
        return f"<SceneDate(date={self.date}, scene_id={self.scene_id})>"


class Event(Base):
    """
    Groups related scenes within an entry.

    Events provide a middle layer of organization between scenes
    and entries. They group related scenes that form a coherent
    narrative unit.

    Attributes:
        id: Primary key
        name: Event name (unique within entry)
        entry_id: Foreign key to parent Entry

    Relationships:
        entry: Many-to-one with Entry (parent entry)
        scenes: M2M with Scene (scenes in this event)

    Notes:
        - Unique constraint on (name, entry_id)
        - Events only contain 'name' and 'scenes' fields
    """

    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("name != ''", name="ck_event_non_empty_name"),
        UniqueConstraint("name", "entry_id", name="uq_event_name_entry"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entries.id", ondelete="CASCADE"), nullable=False
    )

    # --- Relationships ---
    entry: Mapped["Entry"] = relationship("Entry", back_populates="events")
    scenes: Mapped[List["Scene"]] = relationship(
        "Scene", secondary=event_scenes, back_populates="events"
    )

    # --- Computed properties ---
    @property
    def scene_count(self) -> int:
        """Number of scenes in this event."""
        return len(self.scenes)

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
        return f"<Event(id={self.id}, name='{self.name}', entry_id={self.entry_id})>"

    def __str__(self) -> str:
        return f"{self.name} ({self.scene_count} scenes)"


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
        from_date: Proximate moment date (YYYY-MM-DD)
        to_date: Distant moment date (YYYY, YYYY-MM, or YYYY-MM-DD)
        referenced_entry_date: Optional date of entry narrating distant moment
        content: Description of the CONNECTION between moments
        entry_id: Foreign key to parent Entry

    Relationships:
        entry: Many-to-one with Entry (parent entry)
        people: M2M with Person (people in this thread)
        locations: M2M with Location (locations in this thread)

    Notes:
        - to_date is stored as string to allow approximate dates
        - content describes the connection, not the individual moments
    """

    __tablename__ = "threads"
    __table_args__ = (CheckConstraint("name != ''", name="ck_thread_non_empty_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY, YYYY-MM, or YYYY-MM-DD
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
        "Location", secondary=thread_locations, back_populates="locations"
    )

    # --- Computed properties ---
    @property
    def is_past_thread(self) -> bool:
        """Check if this thread references a past moment."""
        # Simple heuristic: if to_date string is before from_date, it's past
        try:
            if len(self.to_date) == 4:  # YYYY
                return int(self.to_date) < self.from_date.year
            elif len(self.to_date) == 7:  # YYYY-MM
                year, month = self.to_date.split("-")
                return (int(year), int(month)) < (self.from_date.year, self.from_date.month)
            else:  # YYYY-MM-DD
                to_parts = self.to_date.split("-")
                to_tuple = (int(to_parts[0]), int(to_parts[1]), int(to_parts[2]))
                from_tuple = (self.from_date.year, self.from_date.month, self.from_date.day)
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
