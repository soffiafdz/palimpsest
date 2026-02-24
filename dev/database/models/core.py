#!/usr/bin/env python3
"""
core.py
-------
Core models for the Palimpsest database.

This module contains the central Entry model and schema versioning:

Models:
    - SchemaInfo: Schema version tracking for migrations
    - Entry: Journal entry - the source text (core of journal domain)
    - NarratedDate: Dates narrated within an entry

The Entry model is the heart of the journal system, representing a single
journal entry with its metadata and relationships to all other entities.

Design:
    - Entry stores minimal metadata (file reference, computed stats)
    - Analysis metadata (scenes, events, threads) lives in separate tables
    - People/locations can be linked directly to Entry or via Scenes
    - Soft delete support for recovery and sync
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, List, Optional

# --- Third party imports ---
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

# --- Local imports ---
from .associations import (
    arc_entries,
    entry_cities,
    entry_locations,
    entry_people,
    entry_tags,
    event_entries,
)
from .base import Base, SoftDeleteMixin

if TYPE_CHECKING:
    from .analysis import Arc, Event, Scene, Thread
    from .creative import PoemVersion, Reference
    from .entities import Person, Tag
    from .geography import City, Location
    from .metadata import MotifInstance, ThemeInstance


class SchemaInfo(Base):
    """
    Tracks schema versions for migration management.

    Used by Alembic or manual migration scripts to track which schema
    changes have been applied to the database.

    Attributes:
        version: Schema version number (primary key)
        applied_at: When this version was applied
        description: Human-readable description of changes
    """

    __tablename__ = "schema_info"

    version: Mapped[int] = mapped_column(
        Integer, primary_key=True, doc="Schema version number"
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        doc="Timestamp when migration was applied",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, doc="Description of schema changes in this version"
    )


class Entry(Base, SoftDeleteMixin):
    """
    Central model representing a journal entry's metadata.

    Each Entry corresponds to a single Markdown file in the journal.
    This is the source text - the ground truth for journal prose.

    Design:
        - Minimal metadata on Entry itself
        - People/locations can be linked directly or derived from Scenes
        - Analysis data in Scene/Event/Thread tables
        - Tags and Themes linked directly

    Attributes:
        id: Primary key
        date: Date of the journal entry (unique)
        file_path: Path to the Markdown file (unique)
        file_hash: Hash of MD file content for change detection
        metadata_hash: Hash of metadata YAML file for change detection
        word_count: Number of words in the entry
        reading_time: Estimated reading time in minutes
        summary: Narrative summary (from analysis)
        rating: Narrative quality rating 1-5 (from analysis)
        rating_justification: Explanation for rating
        created_at: When this database record was created
        updated_at: When this database record was last updated

    Relationships:
        cities: M2M with City (cities where entry took place)
        locations: M2M with Location (specific venues mentioned)
        people: M2M with Person (people mentioned)
        tags: M2M with Tag (keyword tags)
        arcs: M2M with Arc (story arcs this entry belongs to)
        scenes: One-to-many with Scene (granular narrative moments)
        events: One-to-many with Event (scene groupings)
        threads: One-to-many with Thread (temporal connections)
        narrated_dates: One-to-many with NarratedDate (dates narrated)
        references: One-to-many with Reference (external citations)
        poems: One-to-many with PoemVersion (poems in entry)
    """

    __tablename__ = "entries"
    __table_args__ = (
        CheckConstraint("file_path != ''", name="ck_entry_non_empty_file_path"),
        CheckConstraint("word_count >= 0", name="ck_entry_positive_word_count"),
        CheckConstraint("reading_time >= 0.0", name="ck_entry_positive_reading_time"),
        CheckConstraint(
            "rating IS NULL OR (rating >= 1 AND rating <= 5)",
            name="ck_entry_rating_range",
        ),
    )

    # --- Primary fields ---
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64))
    metadata_hash: Mapped[Optional[str]] = mapped_column(String(64))
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    reading_time: Mapped[float] = mapped_column(Float, default=0.0)

    # --- Analysis fields (from narrative analysis) ---
    summary: Mapped[Optional[str]] = mapped_column(Text)
    rating: Mapped[Optional[float]] = mapped_column(Float)
    rating_justification: Mapped[Optional[str]] = mapped_column(Text)

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # --- M2M Relationships (metadata) ---
    cities: Mapped[List["City"]] = relationship(
        "City", secondary=entry_cities, back_populates="entries"
    )
    locations: Mapped[List["Location"]] = relationship(
        "Location", secondary=entry_locations, back_populates="entries"
    )
    people: Mapped[List["Person"]] = relationship(
        "Person", secondary=entry_people, back_populates="entries"
    )
    tags: Mapped[List["Tag"]] = relationship(
        "Tag", secondary=entry_tags, back_populates="entries"
    )
    arcs: Mapped[List["Arc"]] = relationship(
        "Arc", secondary=arc_entries, back_populates="entries"
    )

    # --- One-to-many Relationships (analysis) ---
    scenes: Mapped[List["Scene"]] = relationship(
        "Scene", back_populates="entry", cascade="all, delete-orphan"
    )
    events: Mapped[List["Event"]] = relationship(
        "Event", secondary=event_entries, back_populates="entries"
    )
    threads: Mapped[List["Thread"]] = relationship(
        "Thread", back_populates="entry", cascade="all, delete-orphan"
    )
    narrated_dates: Mapped[List["NarratedDate"]] = relationship(
        "NarratedDate", back_populates="entry", cascade="all, delete-orphan"
    )

    # --- One-to-many Relationships (creative) ---
    references: Mapped[List["Reference"]] = relationship(
        "Reference", back_populates="entry", cascade="all, delete-orphan"
    )
    poems: Mapped[List["PoemVersion"]] = relationship(
        "PoemVersion", back_populates="entry", cascade="all, delete-orphan"
    )

    # --- One-to-many Relationships (metadata instances) ---
    motif_instances: Mapped[List["MotifInstance"]] = relationship(
        "MotifInstance", back_populates="entry", cascade="all, delete-orphan"
    )
    theme_instances: Mapped[List["ThemeInstance"]] = relationship(
        "ThemeInstance", back_populates="entry", cascade="all, delete-orphan"
    )

    # --- Computed properties ---
    @property
    def age_in_days(self) -> int:
        """Get the age of the entry in days."""
        return (date.today() - self.date).days

    @property
    def age_display(self) -> str:
        """Get human-readable entry age."""
        days = self.age_in_days
        if days == 0:
            return "Today"
        elif days == 1:
            return "Yesterday"
        elif days < 7:
            return f"{days} days ago"
        elif days < 30:
            weeks = days // 7
            return f"{weeks} week{'s' if weeks > 1 else ''} ago"
        elif days < 365:
            months = days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        else:
            years = days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"

    @property
    def date_formatted(self) -> str:
        """Get date in YYYY-MM-DD format."""
        return self.date.isoformat()

    @property
    def reading_time_display(self) -> str:
        """Get human-readable reading time."""
        minutes = max(1, round(self.reading_time))
        if minutes == 1:
            return "1 min read"
        elif minutes < 60:
            return f"{minutes} min read"
        else:
            hours = minutes // 60
            remaining = minutes % 60
            if remaining == 0:
                return f"{hours}h read"
            return f"{hours}h {remaining}m read"

    @property
    def scene_count(self) -> int:
        """Number of scenes in this entry."""
        return len(self.scenes)

    @property
    def event_count(self) -> int:
        """Number of events in this entry."""
        return len(self.events)

    @property
    def thread_count(self) -> int:
        """Number of threads in this entry."""
        return len(self.threads)

    @property
    def all_scene_people(self) -> List["Person"]:
        """Get all people from all scenes in this entry."""
        people_set: set = set()
        for scene in self.scenes:
            people_set.update(scene.people)
        return list(people_set)

    @property
    def all_scene_locations(self) -> List["Location"]:
        """Get all locations from all scenes in this entry."""
        locations_set: set = set()
        for scene in self.scenes:
            locations_set.update(scene.locations)
        return list(locations_set)

    def has_person(self, person_name: str) -> bool:
        """
        Check if a specific person is mentioned in this entry.

        Args:
            person_name: Name to search for (case-insensitive)

        Returns:
            True if the person is mentioned
        """
        search_name = person_name.lower()
        return any(
            search_name in person.name.lower()
            or (person.lastname and search_name in person.lastname.lower())
            for person in self.people
        )

    def has_tag(self, tag_name: str) -> bool:
        """
        Check if entry has a specific tag.

        Args:
            tag_name: Tag to search for (case-insensitive)

        Returns:
            True if the tag is present
        """
        search_tag = tag_name.lower()
        return any(tag.name.lower() == search_tag for tag in self.tags)

    def needs_update(self, current_hash: str) -> bool:
        """
        Check if the file has changed since last processing.

        Args:
            current_hash: Hash of the current file content

        Returns:
            True if the file has changed
        """
        return self.file_hash != current_hash

    def __repr__(self) -> str:
        return f"<Entry(id={self.id}, date={self.date}, file_path={self.file_path})>"

    def __str__(self) -> str:
        return f"Entry {self.date_formatted} ({self.word_count} words)"


class NarratedDate(Base):
    """
    Dates narrated within an entry.

    Tracks which dates are described/narrated within a journal entry.
    This is derived from scene dates and used for the MD frontmatter.

    Attributes:
        id: Primary key
        date: The narrated date
        entry_id: Foreign key to parent Entry
    """

    __tablename__ = "narrated_dates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    entry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entries.id", ondelete="CASCADE"), nullable=False
    )

    # --- Relationship ---
    entry: Mapped["Entry"] = relationship("Entry", back_populates="narrated_dates")

    def __repr__(self) -> str:
        return f"<NarratedDate(date={self.date}, entry_id={self.entry_id})>"
