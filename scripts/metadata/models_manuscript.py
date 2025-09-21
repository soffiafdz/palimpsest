#!/usr/bin/env python3
"""
models_manuscript.py
-------------------
Defines the SQLAlchemy ORM models specific to the auto-fiction manuscript.

Each class represents a table in the SQLite database.
Relationships and many-to-many association tables are defined here.

Tables:
    - Entry
    - ...
    - Theme:        thematic tags

Notes
==============
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from typing import List, Optional
from enum import Enum

# --- Third party ---
from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

# --- Local ---
from scripts.metadata.models import Base, Entry, Event, Person


# ----- Association tables -----
entry_themes = Table(
    "entry_themes",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
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


# ----- Models -----
class ManuscriptEntry(Base):
    """Represents an Entry excerpted to be incl/ref in the manuscript."""

    __tablename__ = "manuscript_entry"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("entry.id"), unique=True)
    status: Mapped[ManuscriptStatus] = mapped_column(
        String, default=ManuscriptStatus.UNSPECIFIED.value, index=True
    )
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    themes: Mapped[List[Theme]] = relationship("Theme", secondary=entry_themes)

    # Relationships
    entry: Mapped[Entry] = relationship("Entry", back_populates="manuscript")

    # Call
    def __repr__(self):
        return f"<ManuscriptEntry(entry='{self.entry}', status='{self.status}')>"


class ManuscriptPerson(Base):
    """Represents a Person from whom a character will be based."""

    __tablename__ = "manuscript_person"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), unique=True)
    character: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # Relationships
    person: Mapped[Person] = relationship("Person", back_populates="manuscript")

    # Call
    def __repr__(self):
        return (
            f"<ManuscriptPerson(person='{self.person}', character='{self.character}')>"
        )


class ManuscriptEvent(Base):
    """Represents an Event from the journal adapted to the manuscript."""

    __tablename__ = "manuscript_event"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), unique=True)
    arc_id: Mapped[Optional[int]] = mapped_column(ForeignKey("arcs.id"))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    event: Mapped[Event] = relationship("Event", back_populates="manuscript")
    arc: Mapped[Optional[Arc]] = relationship("Arc", back_populates="events")

    # Call
    def __repr__(self):
        return f"<ManuscriptEvent(event='{self.event}')>"


class Arc(Base):
    __tablename__ = "arcs"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    arc: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    # Relationships
    events: Mapped[List["ManuscriptEvent"]] = relationship(
        "ManuscriptEvent", back_populates="arc"
    )

    # Call
    def __repr__(self):
        return f"<Arc(arc='{self.arc}')>"


class Theme(Base):
    """Represents a theme/tag associated with entries."""

    __tablename__ = "themes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    theme: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    # Relationships
    entries: Mapped[List[ManuscriptEntry]] = relationship(
        "ManuscriptEntry", secondary=entry_themes, back_populates="themes"
    )

    # Call
    def __repr__(self):
        return f"<Theme(name='{self.theme}')>"
