#!/usr/bin/env python3
"""
models_manuscript.py
-------------------
Defines the SQLAlchemy ORM models specific to the auto-fiction manuscript.

Each class represents a table in the SQLite database.
Relationships and many-to-many association tables are defined here.

Tables:
    - ManuscriptEntry
    - ManuscriptPerson
    - ManuscriptEvent
    - Arc
    - Theme

Notes
==============
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
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

# --- Local ---
from code.metadata.models import Base, Entry, Event, Person, SoftDeleteMixin


# ----- Association tables -----
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
    UNSPECIFIED = "unspecified"
    REFERENCE = "reference"
    QUOTE = "quote"
    FRAGMENTS = "fragments"
    SOURCE = "source"

    @classmethod
    def choices(cls):
        return [status.value for status in cls]

    @classmethod
    def content_statuses(cls):
        """Statuses that indicate actual manuscript content."""
        return [cls.SOURCE, cls.QUOTE, cls.FRAGMENTS]

    @classmethod
    def non_content_statuses(cls):
        """Statuses that are not manuscript content."""
        return [cls.UNSPECIFIED, cls.REFERENCE]

    @property
    def is_content(self) -> bool:
        """Check if this status represents actual manuscript content."""
        return self in self.content_statuses()


# ----- Models -----
class ManuscriptEntry(Base):
    """Represents an Entry excerpted to be incl/ref in the manuscript."""

    __tablename__ = "manuscript_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("entries.id"), unique=True)
    status: Mapped[ManuscriptStatus] = mapped_column(
        SQLEnum(ManuscriptStatus, values_callable=lambda x: [e.value for e in x]),
        default=ManuscriptStatus.UNSPECIFIED,
        index=True,
    )
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    themes: Mapped[List[Theme]] = relationship(
        "Theme", secondary=entry_themes, back_populates="entries"
    )
    entry: Mapped[Entry] = relationship("Entry", back_populates="manuscript")

    # Utilities
    @property
    def is_ready_for_manuscript(self) -> bool:
        """Check if entry is ready for manuscript inclusion."""
        return self.edited and self.status in [
            ManuscriptStatus.SOURCE,
            ManuscriptStatus.QUOTE,
            ManuscriptStatus.FRAGMENTS,
        ]

    @property
    def theme_names(self) -> List[str]:
        """Get list of theme names."""
        return [theme.theme for theme in self.themes]

    def has_theme(self, theme_name: str) -> bool:
        """Check if entry has a specific theme."""
        return any(theme.theme.lower() == theme_name.lower() for theme in self.themes)

    @property
    def word_count(self) -> int:
        """Get word count from associated entry."""
        return self.entry.word_count if self.entry else 0

    @property
    def date(self) -> Optional[date]:
        """Get date from associated entry."""
        return self.entry.date if self.entry else None

    # Call
    def __repr__(self):
        return f"<ManuscriptEntry(entry={self.entry}, status={self.status})>"

    def __str__(self) -> str:
        entry_date = self.entry.date_formatted if self.entry else "No entry"
        return f"ManuscriptEntry {entry_date} ({self.status.value})"


class ManuscriptPerson(Base, SoftDeleteMixin):
    """Represents a Person from whom a character will be based."""

    __tablename__ = "manuscript_people"
    __table_args__ = (
        CheckConstraint(
            "character != ''", name="ck_manuscript_person_non_empty_character"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), unique=True)
    character: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # Relationships
    person: Mapped[Person] = relationship("Person", back_populates="manuscript")

    # Utilities
    @property
    def entry_count(self) -> int:
        """Number of entries this person appears in."""
        return self.person.entry_count if self.person else 0

    @property
    def display_name(self) -> str:
        """Get person's display name."""
        return self.person.display_name if self.person else "Unknown"

    # Call
    def __repr__(self):
        return f"<ManuscriptPerson(person={self.person}, character={self.character})>"

    def __str__(self) -> str:
        person_name = self.display_name
        return f"ManuscriptPerson {person_name} -> {self.character}"


class ManuscriptEvent(Base, SoftDeleteMixin):
    """Represents an Event from the journal adapted to the manuscript."""

    __tablename__ = "manuscript_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), unique=True)
    arc_id: Mapped[Optional[int]] = mapped_column(ForeignKey("arcs.id"))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    event: Mapped[Event] = relationship("Event", back_populates="manuscript")
    arc: Mapped[Optional[Arc]] = relationship("Arc", back_populates="events")

    # Utilities
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

    # Call
    def __repr__(self):
        return f"<ManuscriptEvent(event={self.event})>"

    def __str__(self) -> str:
        event_name = self.display_name
        arc_info = f" (Arc: {self.arc_name})" if self.arc else ""
        return f"ManuscriptEvent {event_name}{arc_info}"


class Arc(Base, SoftDeleteMixin):
    """Represents an Arc encompassing several narrative manuscriptEvents."""

    __tablename__ = "arcs"
    __table_args__ = (
        CheckConstraint("arc != ''", name="ck_manuscript_arc_non_empty_arc"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    arc: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)

    # Relationships
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
        """Get date range across all events in arc."""
        if not self.events:
            return None

        all_dates = []
        for event in self.events:
            if event.event and event.event.entries:
                all_dates.extend([entry.date for entry in event.event.entries])

        if not all_dates:
            return None

        return {
            "count": len(all_dates),
            "start_date": min(all_dates),
            "end_date": max(all_dates),
            "duration_days": (max(all_dates) - min(all_dates)).days + 1,
        }

    # Call
    def __repr__(self):
        return f"<Arc(arc='{self.arc}')>"

    def __str__(self) -> str:
        return (
            f"Arc {self.arc} ({self.event_count} events, "
            f"{self.total_entry_count} entries)"
        )


class Theme(Base, SoftDeleteMixin):
    """Represents a theme/tag associated with entries."""

    __tablename__ = "themes"
    __table_args__ = (
        CheckConstraint("theme != ''", name="ck_manuscript_non_empty_theme"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    theme: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)

    # Relationships
    entries: Mapped[List[ManuscriptEntry]] = relationship(
        "ManuscriptEntry", secondary=entry_themes, back_populates="themes"
    )

    # Utilities
    @property
    def usage_count(self) -> int:
        """Number of manuscript entries using this theme."""
        return len(self.entries)

    @property
    def word_count_total(self) -> int:
        """Total word count across all entries with this theme."""
        return sum(entry.word_count for entry in self.entries)

    @property
    def first_used(self) -> Optional[date]:
        """Date when theme was first used."""
        if not self.entries or not any(entry.entry for entry in self.entries):
            return None

        dates: list[date] = [
            d for entry in self.entries if (d := entry.date) is not None
        ]
        return min(dates) if dates else None

    @property
    def last_used(self) -> Optional[date]:
        """Date when theme was last used."""
        if not self.entries or not any(entry.entry for entry in self.entries):
            return None

        dates: list[date] = [
            d for entry in self.entries if (d := entry.date) is not None
        ]
        return max(dates) if dates else None

    # Call
    def __repr__(self):
        return f"<Theme(name={self.theme})>"

    def __str__(self) -> str:
        return f"Theme {self.theme} ({self.usage_count} entries)"
