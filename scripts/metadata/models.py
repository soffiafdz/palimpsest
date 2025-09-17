#!/usr/bin/env python3
"""
models.py
-------------------
Defines the SQLAlchemy ORM models for the Palimpsest metadata database.

Each class represents a table in the SQLite database.
Relationships and many-to-many association tables are defined here.

Tables:
    - SchemaInfo    schema version control
    - Entry:        journal entry metadata (from Markdown frontmatter)
    - Location:     geographic placement of the entries
    - Person:       people mentioned in the entries
    - Reference:    dates referenced in the entries
    - Event:        overarching thematic arcs/phases
    - Poem:         poems written in the journal
    - Tag:          simple tags

Notes
==============
- Each class represents a table in the SQLite DB.
- Relationships (many-to-many association tables) are defined here.
- Updates (migrations) should be handled by Alembic.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date, datetime, timezone
from typing import List, Optional, TYPE_CHECKING

# --- Third party ---
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

# --- Local ---
if TYPE_CHECKING:
    from scripts.metadata.models_manuscript import (
        ManuscriptEntry,
        ManuscriptPerson,
        ManuscriptEvent,
    )


# ----- Base ORM class -----
class Base(DeclarativeBase):
    """
    Base class for all ORM models.
    Provides access to the metadata and acts as the declarative base.
    """

    pass


# ----- Association tables -----
entry_dates = Table(
    "entry_dates",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("date_id", Integer, ForeignKey("dates.id"), primary_key=True),
)

entry_locations = Table(
    "entry_locations",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("location_id", Integer, ForeignKey("locations.id"), primary_key=True),
)

entry_people = Table(
    "entry_people",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("people_id", Integer, ForeignKey("people.id"), primary_key=True),
)

entry_references = Table(
    "entry_references",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("reference_id", Integer, ForeignKey("references.id"), primary_key=True),
)

entry_events = Table(
    "entry_events",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "event_id",
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

event_people = Table(
    "event_people",
    Base.metadata,
    Column(
        "event_id",
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    # Note: SET NULL on person deletion
    # keeps the occurrence but removes the link
    Column(
        "person_id",
        Integer,
        ForeignKey("people.id", ondelete="SET NULL"),
        primary_key=True,
    ),
)

entry_tags = Table(
    "entry_tags",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)

entry_poem_versions = Table(
    "entry_poem_versions",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "poem_version_id",
        Integer,
        ForeignKey("poem_versions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# ----- Schema Versioning -----
class SchemaInfo(Base):
    """
    Tracks schema versions for migration purposes.

    Attributes:
        version (int): Schema version number.
        applied_at (datetime): Timestamp when migration/version was applied.
        description (str): Description of the schema changes.
    """

    __tablename__ = "schema_info"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    description: Mapped[Optional[str]] = mapped_column(Text)


# ----- Models -----
class Entry(Base):
    """
    Journal entry metadata and relationships.

    Attributes:
        id (int):           Primary key.
        date (date):        Date of the journal entry.
        file_path (str)     Path to the Markdown file.
        word_count (int)
        reading_time (float)
        epigraph (str):
        notes (str)
        file_hash (str):    Hash of the file content.
        created_at (datetime)
        updated_at (datetime)

    Relationships:
        dates, locations, people, references, events, poems, themes, tags
    """

    __tablename__ = "entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    reading_time: Mapped[float] = mapped_column(Float, default=0.0)
    excerpted: Mapped[bool] = mapped_column(Boolean, default=False)
    epigraph: Mapped[Optional[str]] = mapped_column(String)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    file_hash: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    dates: Mapped[List[MentionedDate]] = relationship(
        "MentionedDate", secondary=entry_dates, back_populates="entries"
    )
    locations: Mapped[List[Location]] = relationship(
        "Location", secondary=entry_locations, back_populates="entries"
    )
    people: Mapped[List[Person]] = relationship(
        "Person", secondary=entry_people, back_populates="entries"
    )
    references: Mapped[List[Reference]] = relationship(
        "Reference", secondary=entry_references, back_populates="entries"
    )
    events: Mapped[List[Event]] = relationship(
        "Event", secondary=entry_events, back_populates="entries"
    )
    poems: Mapped[List[PoemVersion]] = relationship(
        "Poem", secondary=entry_poem_versions, back_populates="entries"
    )
    tags: Mapped[List[Tag]] = relationship(
        "Tag", secondary=entry_tags, back_populates="entries"
    )

    # Manuscript
    manuscript: Mapped[Optional["ManuscriptEntry"]] = relationship(
        "ManuscriptEntry", uselist=False, back_populates="entry"
    )

    # Call
    def __repr__(self):
        return f"<Entry(date='{self.date}', file_path='{self.file_path}')>"


class MentionedDate(Base):
    """Represents the set of dates referenced in entries."""

    __tablename__ = "dates"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Relationships
    entries: Mapped[List[Entry]] = relationship(
        "Entry", secondary=entry_dates, back_populates="dates"
    )


class Location(Base):
    """Represents a location associated with entries."""

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String, index=True)

    # Relationships
    entries: Mapped[List[Entry]] = relationship(
        "Entry", secondary=entry_locations, back_populates="locations"
    )

    # Call
    def __repr__(self):
        return f"<Location(full_name='{self.full_name}')>"


class Person(Base):
    """Represents a person mentioned in journal entries."""

    __tablename__ = "people"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True)
    type_relationship: Mapped[Optional[str]] = mapped_column(String)
    pseudonym: Mapped[Optional[str]] = mapped_column(String)

    # Relationships
    aliases: Mapped[List[Alias]] = relationship(
        "Alias", back_populates="person", cascade="all, delete-orphan"
    )
    events: Mapped[List[Event]] = relationship(
        "Event", secondary=event_people, back_populates="people"
    )
    entries: Mapped[List[Entry]] = relationship(
        "Entry", secondary=entry_people, back_populates="people"
    )

    # Manuscript
    manuscript: Mapped[Optional["ManuscriptPerson"]] = relationship(
        "ManuscriptPerson", uselist=False, back_populates="entry"
    )

    # Call
    def __repr__(self):
        return f"<Person(name='{self.name}')>"


class Alias(Base):
    """Represents the multiple aliases for people."""

    __tablename__ = "aliases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    alias: Mapped[str] = mapped_column(String, nullable=False)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))

    # Relationships
    person: Mapped["Person"] = relationship("Person", back_populates="aliases")

    # Call
    def __repr__(self):
        return f"<Alias(alias='{self.alias}')>"


class Reference(Base):
    """Represents an (external) reference associated with entries."""

    __tablename__ = "references"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    type_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("reference_types.id")
    )

    # Relationships
    reference_type: Mapped[Optional[ReferenceType]] = relationship(
        "ReferenceType", back_populates="references"
    )
    entries: Mapped[List[Entry]] = relationship(
        "Entry", secondary=entry_references, back_populates="references"
    )

    # Call
    def __repr__(self):
        return f"<Reference(name='{self.name}')>"


class ReferenceType(Base):
    """Defines types of references (book, article, movie, etc.)."""

    __tablename__ = "reference_types"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    # Relationships
    references: Mapped[List[Reference]] = relationship(
        "Reference", back_populates="reference_type"
    )

    # Call
    def __repr__(self):
        return f"<ReferenceType(name='{self.name}')>"


class Event(Base):
    """
    Represents a main narrative event related to one or more entries.
    """

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    entries: Mapped[List[Entry]] = relationship(
        "Entry", secondary=entry_events, back_populates="events"
    )
    people: Mapped[List[Person]] = relationship(
        "Person", secondary=event_people, back_populates="events"
    )

    # Manuscript
    manuscript: Mapped[Optional["ManuscriptEvent"]] = relationship(
        "ManuscriptEvent", uselist=False, back_populates="entry"
    )

    # Call
    def __repr__(self):
        return f"<Event(name='{self.name}')>"


class Poem(Base):
    __tablename__ = "poems"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # Relationships
    versions: Mapped[List["PoemVersion"]] = relationship(
        "PoemVersion", back_populates="poem", cascade="all, delete-orphan"
    )

    # Call
    def __repr__(self):
        return f"<Poem(title='{self.title}')>"


class PoemVersion(Base):
    __tablename__ = "poem_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    poem_id: Mapped[int] = mapped_column(ForeignKey("poems.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    revision_date: Mapped[Optional[date]] = mapped_column(Date)  # optional
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    poem: Mapped[Poem] = relationship("Poem", back_populates="versions")
    entries: Mapped[List[Entry]] = relationship(
        secondary=entry_poem_versions, back_populates="poems"
    )

    # Call
    def __repr__(self):
        return f"<PoemVersion(text='{self.text[:50]}...')>"


class Tag(Base):
    """Represents a keyword/tag associated with entries."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    # Relationships
    entries: Mapped[List[Entry]] = relationship(
        "Entry", secondary=entry_tags, back_populates="tags"
    )

    # Call
    def __repr__(self):
        return f"<Tag(name='{self.name}')>"
