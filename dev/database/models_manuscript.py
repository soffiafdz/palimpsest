#!/usr/bin/env python3
"""
models_manuscript.py
-------------------
SQLAlchemy ORM models for manuscript-specific data.

This module extends the core journal models with manuscript-specific
tables for tracking which journal content will be adapted into the
auto-fiction manuscript.

Tables:
    - ManuscriptEntry: Entries selected for manuscript inclusion
    - ManuscriptPerson: People who become characters in the manuscript
    - ManuscriptEvent: Events adapted for the manuscript narrative
    - Arc: Story arcs encompassing multiple events
    - Theme: Thematic elements in manuscript entries

Association Tables:
    - entry_themes: Links manuscript entries to themes

Notes
==============
    - Uses ManuscriptStatus enum for categorizing entry usage
    - Soft delete support for manuscript data via SoftDeleteMixin
    - Maintains relationships with core journal models
    - Provides computed properties for manuscript analytics
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date
from typing import Any, Dict, List, Optional
from enum import Enum

# --- Third party ---
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

# --- Local ---
from .models import Base, Entry, Event, Person, SoftDeleteMixin


# ----- Association table -----
entry_themes = Table(
    "entry_themes",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("manuscript_entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("theme_id", Integer, ForeignKey("themes.id"), primary_key=True),
)


# ----- Status Enum -----
class ManuscriptStatus(str, Enum):
    """
    Enumeration of manuscript entry statuses.

    Defines how journal entries are used in the manuscript:
    - UNSPECIFIED: Status not yet determined
    - REFERENCE: Entry is referenced but not included
    - QUOTE: Direct quotes will be used
    - FRAGMENTS: Partial content will be adapted
    - SOURCE: Full entry serves as source material
    """

    UNSPECIFIED = "unspecified"
    REFERENCE = "reference"
    QUOTE = "quote"
    FRAGMENTS = "fragments"
    SOURCE = "source"

    @classmethod
    def choices(cls) -> List[str]:
        """Get all available status choices."""
        return [status.value for status in cls]

    @classmethod
    def content_statuses(cls) -> List["ManuscriptStatus"]:
        """Get statuses that indicate actual manuscript content."""
        return [cls.SOURCE, cls.QUOTE, cls.FRAGMENTS]

    @classmethod
    def non_content_statuses(cls) -> List["ManuscriptStatus"]:
        """Get statuses that don't represent manuscript content."""
        return [cls.UNSPECIFIED, cls.REFERENCE]

    @property
    def is_content(self) -> bool:
        """Check if this status represents actual manuscript content."""
        return self in self.content_statuses()

    @property
    def priority(self) -> int:
        """Get priority level for sorting (higher = more important)."""
        priority_map = {
            self.SOURCE: 5,
            self.FRAGMENTS: 4,
            self.QUOTE: 3,
            self.REFERENCE: 2,
            self.UNSPECIFIED: 1,
        }
        return priority_map.get(self, 0)


# ----- Models -----
class ManuscriptEntry(Base):
    """
    Tracks journal entries selected for manuscript inclusion.

    Links journal entries to the manuscript with metadata about
    how the entry will be used (status) and whether it has been
    edited for inclusion.

    Attributes:
        id: Primary key
        entry_id: Foreign key to Entry (unique - one-to-one)
        status: How this entry is used in the manuscript
        edited: Whether the entry has been edited for manuscript
        notes: Editorial notes about this entry's usage
    """

    __tablename__ = "manuscript_entries"

    # ---- Primary fields ----
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    status: Mapped[ManuscriptStatus] = mapped_column(
        SQLEnum(ManuscriptStatus, values_callable=lambda x: [e.value for e in x]),
        default=ManuscriptStatus.UNSPECIFIED,
        index=True,
        nullable=False,
    )
    edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ---- Foreign key ----
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("entries.id"),
        unique=True,
        nullable=False,
    )

    # ---- Relationships ----
    themes: Mapped[List[Theme]] = relationship(
        "Theme", secondary=entry_themes, back_populates="entries"
    )
    entry: Mapped[Entry] = relationship("Entry", back_populates="manuscript")

    # ---- Computed property ----
    @property
    def is_ready_for_manuscript(self) -> bool:
        """Check if entry is ready for manuscript inclusion."""
        return self.edited and self.status.is_content

    @property
    def theme_names(self) -> List[str]:
        """Get list of theme names for this entry."""
        return [theme.theme for theme in self.themes]

    @property
    def theme_count(self) -> int:
        """Number of themes associated with this entry."""
        return len(self.themes)

    def has_theme(self, theme_name: str) -> bool:
        """
        Check if entry has a specific theme.

        Args:
            theme_name: Theme to check for (case-insensitive)

        Returns:
            True if the theme is present
        """
        search_theme = theme_name.lower()
        return any(theme.theme.lower() == search_theme for theme in self.themes)

    @property
    def word_count(self) -> int:
        """Get word count from associated entry."""
        return self.entry.word_count if self.entry else 0

    @property
    def date(self) -> Optional[date]:
        """Get date from associated entry."""
        return self.entry.date if self.entry else None

    @property
    def date_formatted(self) -> str:
        """Get formatted date string."""
        return self.date.isoformat() if self.date else "No date"

    def __repr__(self) -> str:
        return (
            f"<ManuscriptEntry(id={self.id}, entry_id={self.entry_id}, "
            f"status={self.status.value})>"
        )

    def __str__(self) -> str:
        status_str = self.status.value
        edited_str = " (edited)" if self.edited else ""
        return f"Manuscript Entry {self.date_formatted} [{status_str}]{edited_str}"


class ManuscriptPerson(Base, SoftDeleteMixin):
    """
    Maps real people to fictional characters in the manuscript.

    Tracks which people from the journal will become characters
    in the auto-fiction manuscript, with their character names.

    Attributes:
        id: Primary key
        person_id: Foreign key to Person (unique - one-to-one)
        character: Name of the fictional character
    """

    __tablename__ = "manuscript_people"
    __table_args__ = (
        CheckConstraint(
            "character != ''", name="ck_manuscript_person_non_empty_character"
        ),
    )

    # ---- Primary fields ----
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    character: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # ---- Foreign key ----
    person_id: Mapped[int] = mapped_column(
        ForeignKey("people.id"),
        unique=True,
        nullable=False,
    )

    # ---- Relationship ----
    person: Mapped[Person] = relationship("Person", back_populates="manuscript")

    # ---- Computed property ----
    @property
    def real_name(self) -> str:
        """Get the real person's display name."""
        return self.person.display_name if self.person else "Unknown"

    @property
    def entry_count(self) -> int:
        """Number of entries this person/character appears in."""
        return self.person.entry_count if self.person else 0

    @property
    def event_count(self) -> int:
        """Number of events this person/character is involved in."""
        return len(self.person.events) if self.person else 0

    @property
    def first_appearance(self) -> Optional[date]:
        """Date of first appearance in the journal."""
        return self.person.first_appearance if self.person else None

    @property
    def last_appearance(self) -> Optional[date]:
        """Date of last appearance in the journal."""
        return self.person.last_appearance if self.person else None

    def __repr__(self) -> str:
        return (
            f"<ManuscriptPerson(id={self.id}, person_id={self.person_id}, "
            f"character={self.character})>"
        )

    def __str__(self) -> str:
        return f"Character: {self.character} (based on {self.real_name})"


class ManuscriptEvent(Base, SoftDeleteMixin):
    """
    Tracks events adapted for the manuscript narrative.

    Links journal events to story arcs in the manuscript,
    with notes about how the event is adapted.

    Attributes:
        id: Primary key
        event_id: Foreign key to Event (unique - one-to-one)
        arc_id: Foreign key to Arc (optional)
        notes: Notes about how this event is adapted
    """

    __tablename__ = "manuscript_events"

    # ---- Primary fields ----
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ---- Foreign keys ----
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id"),
        unique=True,
        nullable=False,
    )
    arc_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("arcs.id"),
        nullable=True,
    )

    # ---- Relationships ----
    event: Mapped[Event] = relationship("Event", back_populates="manuscript")
    arc: Mapped[Optional[Arc]] = relationship("Arc", back_populates="events")

    # ---- Computed property ----
    @property
    def display_name(self) -> str:
        """Get event display name."""
        return self.event.display_name if self.event else "Unknown Event"

    @property
    def entry_count(self) -> int:
        """Number of entries in this event."""
        return len(self.event.entries) if self.event else 0

    @property
    def duration_days(self) -> Optional[int]:
        """Get event duration."""
        return self.event.duration_days if self.event else None

    @property
    def arc_name(self) -> Optional[str]:
        """Get arc name."""
        return self.arc.arc if self.arc else None

    @property
    def people_involved(self) -> List[str]:
        """List of people involved in this event."""
        if not self.event:
            return []
        return [person.display_name for person in self.event.people]

    @property
    def start_date(self) -> Optional[date]:
        """Start date of the event."""
        return self.event.start_date if self.event else None

    @property
    def end_date(self) -> Optional[date]:
        """End date of the event."""
        return self.event.end_date if self.event else None

    def __repr__(self):
        return f"<ManuscriptEvent(id={self.id}, event_id={self.event_id})>"

    def __str__(self) -> str:
        arc_info = f" in {self.arc_name}" if self.arc_name else ""
        return f"Manuscript Event: {self.display_name}{arc_info}"


class Arc(Base, SoftDeleteMixin):
    """
    Story arcs that group related events in the manuscript.

    Represents major narrative arcs that span multiple events,
    providing structure to the manuscript narrative.

    Attributes:
        id: Primary key
        arc: Name/identifier of the arc (unique)
    """

    __tablename__ = "arcs"
    __table_args__ = (
        CheckConstraint("arc != ''", name="ck_manuscript_arc_non_empty_arc"),
    )

    # ---- Primary fields ----
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    arc: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)

    # ---- Relationship ----
    events: Mapped[List["ManuscriptEvent"]] = relationship(
        "ManuscriptEvent", back_populates="arc"
    )

    # Utilities
    @property
    def event_count(self) -> int:
        """Number of events in this arc."""
        return len(self.events)

    @property
    def total_entry_count(self) -> int:
        """Total entries across all events in arc."""
        return sum(event.entry_count for event in self.events)

    @property
    def date_range(self) -> Optional[Dict[str, Any]]:
        """
        Calculate date range across all events in arc.

        Returns:
            Dictionary with start_date, end_date, and duration_days,
            or None if arc has no events with dates
        """
        if not self.events:
            return None

        all_dates: List[date] = []
        for manuscript_event in self.events:
            if manuscript_event.event and manuscript_event.event.entries:
                all_dates.extend(
                    [entry.date for entry in manuscript_event.event.entries]
                )

        if not all_dates:
            return None

        min_date = min(all_dates)
        max_date = max(all_dates)
        return {
            "start_date": min_date,
            "end_date": max_date,
            "duration_days": (max_date - min_date).days + 1,
            "total_entries": len(all_dates),
        }

    @property
    def chronological_events(self) -> List[ManuscriptEvent]:
        """Get events in this arc in chronological order."""
        return sorted(self.events, key=lambda e: e.start_date or date.min)

    def __repr__(self):
        return f"<Arc(id={self.id}, arc={self.arc})>"

    def __str__(self) -> str:
        return (
            f"Arc {self.arc} ({self.event_count} events, "
            f"{self.total_entry_count} entries)"
        )


class Theme(Base, SoftDeleteMixin):
    """
    Thematic elements tracked in manuscript entries.

    Provides a thematic tagging system specifically for manuscript
    content, separate from general journal tags.

    Attributes:
        id: Primary key
        theme: Name of the theme (unique)
    """

    __tablename__ = "themes"
    __table_args__ = (
        CheckConstraint("theme != ''", name="ck_manuscript_non_empty_theme"),
    )

    # ---- Primary fields ----
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    theme: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)

    # ---- Relationship ----
    entries: Mapped[List[ManuscriptEntry]] = relationship(
        "ManuscriptEntry", secondary=entry_themes, back_populates="themes"
    )

    # ---- Computed property ----
    @property
    def usage_count(self) -> int:
        """Number of manuscript entries using this theme."""
        return len(self.entries)

    @property
    def word_count_total(self) -> int:
        """Total word count across all entries with this theme."""
        return sum(entry.word_count for entry in self.entries)

    @property
    def average_word_count(self) -> float:
        """Average word count for entries with this theme."""
        if not self.entries:
            return 0.0
        return self.word_count_total / len(self.entries)

    @property
    def first_used(self) -> Optional[date]:
        """Date when theme was first used."""
        if not self.entries:
            return None
        dates = [entry.date for entry in self.entries if entry.date]
        return min(dates) if dates else None

    @property
    def last_used(self) -> Optional[date]:
        """Date when theme was last used."""
        if not self.entries:
            return None
        dates = [entry.date for entry in self.entries if entry.date]
        return max(dates) if dates else None

    @property
    def usage_span_days(self) -> int:
        """Days between first and last use of this theme."""
        first = self.first_used
        last = self.last_used
        if not first or not last or first == last:
            return 0
        return (last - first).days

    def __repr__(self):
        return f"<Theme(id={self.id}, theme={self.theme})>"

    def __str__(self) -> str:
        count = self.usage_count
        if count == 0:
            return f"Theme '{self.theme}' (unused)"
        elif count == 1:
            return f"Theme '{self.theme}' (1 entry)"
        else:
            return f"Theme '{self.theme}' ({count} entries)"
