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
from typing import List, Optional, Dict, TYPE_CHECKING

# --- Third party ---
from sqlalchemy import (
    CheckConstraint,
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


# ----- Soft Delete -----
class SoftDeleteMixin:
    """Basic soft delete functionality - keep in models for ORM integration."""

    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[Optional[str]] = mapped_column(String)
    deletion_reason: Mapped[Optional[str]] = mapped_column(Text)

    @property
    def is_deleted(self) -> bool:
        """Simple property check."""
        return self.deleted_at is not None

    def soft_delete(
        self, deleted_by: Optional[str] = None, reason: Optional[str] = None
    ) -> None:
        """Basic soft delete - no business logic here."""
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = deleted_by
        self.deletion_reason = reason

    def restore(self) -> None:
        """Basic restore - no business logic here."""
        self.deleted_at = None
        self.deleted_by = None
        self.deletion_reason = None


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
        file_hash (str):    Hash of the file content.
        word_count (int)
        reading_time (float)
        epigraph (str):
        notes (str)
        created_at (datetime)
        updated_at (datetime)

    Relationships:
        dates, locations, people, references, events, poems, themes, tags
    """

    __tablename__ = "entries"
    __table_args__ = (
        CheckConstraint("word_count >= 0", name="positive_entry_word_count"),
        CheckConstraint("reading_time >= 0.0", name="positive_entry_reading_time"),
        CheckConstraint("file_path != ''", name="ck_entry_non_empty_file_path"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    file_hash: Mapped[Optional[str]] = mapped_column(String)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    reading_time: Mapped[float] = mapped_column(Float, default=0.0)
    epigraph: Mapped[Optional[str]] = mapped_column(String)
    notes: Mapped[Optional[str]] = mapped_column(Text)
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
        "Reference", back_populates="entry", cascade="all, delete-orphan"
    )
    events: Mapped[List[Event]] = relationship(
        "Event", secondary=entry_events, back_populates="entries"
    )
    poems: Mapped[List[PoemVersion]] = relationship(
        "PoemVersion", back_populates="entry", cascade="all, delete-orphan"
    )
    tags: Mapped[List[Tag]] = relationship(
        "Tag", secondary=entry_tags, back_populates="entries"
    )

    # Manuscript
    manuscript: Mapped[Optional[ManuscriptEntry]] = relationship(
        "ManuscriptEntry", uselist=False, back_populates="entry"
    )

    # Utilities
    @property
    def is_recent(self, days: int = 30) -> bool:
        """Check if entry is from the last N days."""
        return (date.today() - self.date).days <= days

    @property
    def age_in_days(self) -> int:
        """Get the age of the entry in days."""
        return (date.today() - self.date).days

    @property
    def age_display(self) -> str:
        """Get human-readable entry age."""
        days = self.age_in_days
        if days < 30:
            return f"{days} days old"
        elif days < 365:
            months = days // 30
            remaining_days = days % 30
            if remaining_days == 0:
                return f"{months} months old"
            return f"{months} months, {remaining_days} days old"
        else:
            years = days // 365
            remaining_days = days % 365
            if remaining_days == 0:
                return f"{years} years old"
            months = remaining_days // 30
            remaining_days = remaining_days % 30
            if remaining_days == 0:
                return f"{years} years, {months} months old"
            return f"{years} years, {months} months, {remaining_days} days old"

    @property
    def date_formatted(self) -> str:
        """Get date in YYYY-MM-DD format"""
        return self.date.strftime("%Y-%m-%d")

    @property
    def date_range(self) -> Optional[Dict[str, int | date]]:
        """
        Return a Tuple containing:
            number of days, min_date, max_date, range in days.
        """
        if not self.dates:
            return None

        date_vals = [d.date for d in self.dates if d.date is not None]

        if not date_vals:
            return None

        min_date, max_date = (min(date_vals), max(date_vals))
        return {
            "count": len(date_vals),
            "min_date": min_date,
            "max_date": max_date,
            "duration": (max_date - min_date).days,
        }

    @property
    def reading_time_minutes(self) -> int:
        """Get reading time rounded to nearest minute."""
        return max(1, round(self.reading_time))

    @property
    def reading_time_display(self) -> str:
        """Get human-readable reading time."""
        minutes = self.reading_time_minutes
        if minutes < 60:
            return f"{minutes} min read"
        else:
            hours = minutes // 60
            remaining_minutes = minutes % 60
            if remaining_minutes == 0:
                return f"{hours}h read"
            return f"{hours}h {remaining_minutes}m read"

    @property
    def people_count(self) -> int:
        """Number of people mentioned in this entry."""
        return len(self.people)

    @property
    def people_names(self) -> List[str]:
        """Get list of people mentioned."""
        return [p.display_name for p in self.people]

    def has_person(self, person_name: str) -> bool:
        """Check if a specific person is mentioned."""
        return any(
            person_name.lower()
            in (person.name.lower(), (person.full_name or "").lower())
            for person in self.people
        )

    @property
    def location_names(self) -> List[str]:
        """Get list of location names mentioned."""
        return [loc.display_name for loc in self.locations]

    @property
    def references_count(self) -> int:
        """Number of references in this entry."""
        return len(self.references)

    @property
    def has_references(self) -> bool:
        """Check if entry has any references."""
        return len(self.references) > 0

    @property
    def has_poems(self) -> bool:
        """Check if entry contains any poems."""
        return len(self.poems) > 0

    @property
    def tag_names(self) -> List[str]:
        """Get list of tags."""
        return [tag.tag for tag in self.tags]

    def has_tag(self, tag_name: str) -> bool:
        """Check if entry has a specific tag."""
        return any(tag.tag.lower() == tag_name.lower() for tag in self.tags)

    @property
    def has_manuscript_version(self) -> bool:
        """Check if this entry has been added to manuscript consideration."""
        return self.manuscript is not None

    @property
    def manuscript_status(self) -> Optional[str]:
        """Get manuscript status if it exists."""
        return self.manuscript.status.value if self.manuscript else None

    def needs_update(self, current_hash: str) -> bool:
        """Check if file has changed since last processing."""
        return self.file_hash != current_hash

    def __repr__(self) -> str:
        return f"<Entry(id={self.id}, date={self.date}, file_path={self.file_path})>"

    def __str__(self) -> str:
        return f"Entry {self.date_formatted} ({self.word_count} words)"


class MentionedDate(Base):
    """Represents the set of dates referenced in entries."""

    __tablename__ = "dates"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Relationships
    entries: Mapped[List[Entry]] = relationship(
        "Entry", secondary=entry_dates, back_populates="dates"
    )

    # Utilities
    @property
    def date_formatted(self) -> str:
        """Get date in YYYY-MM-DD format"""
        return self.date.strftime("%Y-%m-%d")

    @property
    def entry_count(self) -> int:
        """Number of entries referencing this date."""
        if not self.entries:
            return 0
        return len(self.entries)

    @property
    def first_mention_date(self) -> Optional[date]:
        """Get oldest reference."""
        if not self.entries:
            return None
        return min(entry.date for entry in self.entries)

    @property
    def last_mention_date(self) -> Optional[date]:
        """Get most recent reference."""
        if not self.entries:
            return None
        return max(entry.date for entry in self.entries)

    def __repr__(self) -> str:
        return f"<MentionedDate(id={self.id}, date={self.date})>"

    def __str__(self) -> str:
        if self.entry_count == 0:
            return f"MentionedDate {self.date_formatted}, (orphan)"

        if self.entry_count == 1:
            return (
                f"MentionedDate {self.date_formatted} "
                f"({self.entries[0].date_formatted} entry)"
            )

        return f"MentionedDate {self.date_formatted} ({self.entry_count} entries)"


class Location(Base):
    """Represents a location associated with entries."""

    __tablename__ = "locations"
    __table_args__ = CheckConstraint("name != ''", name="ck_location_non_empty_name")

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String, index=True)

    # Relationships
    entries: Mapped[List[Entry]] = relationship(
        "Entry", secondary=entry_locations, back_populates="locations"
    )

    # Utilities
    @property
    def display_name(self) -> str:
        """Get the best display name for this location."""
        return self.full_name or self.name

    @property
    def entry_count(self) -> int:
        """Number of entries at this location."""
        return len(self.entries)

    @property
    def visit_frequency(self) -> Dict[str, int]:
        """Get visit frequency by year/month."""
        frequency = {}
        for entry in self.entries:
            year_month = entry.date.strftime("%Y-%m")
            frequency[year_month] = frequency.get(year_month, 0) + 1
        return frequency

    @property
    def visit_span_days(self) -> int:
        """Number of days between first and last visit."""
        if not self.entries or len(self.entries) < 2:
            return 0
        first = self.first_mention_date
        last = self.last_mention_date
        return (last - first).days if first and last else 0

    @property
    def first_mention_date(self) -> Optional[date]:
        """Get oldest visit."""
        if not self.entries:
            return None
        return min(entry.date for entry in self.entries)

    @property
    def last_mention_date(self) -> Optional[date]:
        """Get most recent visit."""
        if not self.entries:
            return None
        return max(entry.date for entry in self.entries)

    # Call
    def __repr__(self):
        return f"<Location(id={self.id}, name={self.name})>"

    def __str__(self) -> str:
        if self.entry_count == 0:
            return f"Location {self.display_name}, (orphan)"

        if self.entry_count == 1:
            return (
                f"Location {self.display_name} "
                f"({self.entries[0].date_formatted} entry)"
            )

        return f"Location {self.display_name} ({self.entry_count} entries)"


class Person(Base, SoftDeleteMixin):
    """Represents a person mentioned in journal entries."""

    __tablename__ = "people"
    __table_args__ = CheckConstraint("name != ''", name="ck_person_non_empty_name")

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True)
    relation_type: Mapped[Optional[str]] = mapped_column(String)

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
    manuscript: Mapped[Optional[ManuscriptPerson]] = relationship(
        "ManuscriptPerson", uselist=False, back_populates="person"
    )

    # Utilities
    @property
    def display_name(self) -> str:
        """Get the best display name for this person."""
        return self.full_name or self.name

    @property
    def has_aliases(self) -> bool:
        """Check if person has any aliases."""
        return len(self.aliases) > 0

    @property
    def all_names(self) -> List[str]:
        """Get all names and aliases for this person."""
        names = [self.name]
        if self.full_name:
            names.append(self.full_name)
        names.extend([alias.alias for alias in self.aliases])
        return list(set(names))  # Remove duplicates

    @property
    def relation_display(self) -> str:
        """Get relation type or 'Unknown' if not set."""
        return self.relation_type or "Unknown"

    @property
    def entry_count(self) -> int:
        """Number of entries this person appears in."""
        return len(self.entries)

    @property
    def mention_span_days(self) -> int:
        """Number of days between first and last mention."""
        if not self.entries or len(self.entries) < 2:
            return 0
        first = self.first_mention_date
        last = self.last_mention_date
        return (last - first).days if first and last else 0

    @property
    def first_mention_date(self) -> Optional[date]:
        """Date of first mention in journal."""
        if not self.entries:
            return None
        return min(entry.date for entry in self.entries)

    @property
    def last_mention_date(self) -> Optional[date]:
        """Date of most recent mention."""
        if not self.entries:
            return None
        return max(entry.date for entry in self.entries)

    @property
    def mention_frequency(self) -> Dict[str, int]:
        """Get mention frequency by year/month."""
        frequency = {}
        for entry in self.entries:
            year_month = entry.date.strftime("%Y-%m")
            frequency[year_month] = frequency.get(year_month, 0) + 1
        return frequency

    def add_alias(self, alias_name: str) -> Alias:
        """Add a new alias for this person."""
        alias = Alias(alias=alias_name, person=self)
        self.aliases.append(alias)
        return alias

    def is_known_as(self, name: str) -> bool:
        """Check if person is known by this name/alias."""
        return name.lower() in [n.lower() for n in self.all_names]

    # Call
    def __repr__(self):
        return f"<Person(name='{self.name}')>"

    def __str__(self) -> str:
        return f"Person {self.display_name} ({self.entry_count} entries)"


class Alias(Base):
    """Represents the multiple aliases for people."""

    __tablename__ = "aliases"
    __table_args__ = CheckConstraint("alias != ''", name="ck_non_empty_alias")

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    alias: Mapped[str] = mapped_column(String, nullable=False, index=True)
    person_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("people.id", ondelete="CASCADE")
    )

    # Relationships
    person: Mapped[Person] = relationship("Person", back_populates="aliases")

    # Call
    def __repr__(self):
        return f"<Alias(alias={self.alias})>"

    def __str__(self) -> str:
        return f"Alias {self.alias} (for {self.person.display_name})"


class Reference(Base):
    """Represents an (external) reference associated with entries."""

    __tablename__ = "references"
    __table_args__ = CheckConstraint(
        "content != ''", name="check_reference_non_empty_content"
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    speaker: Mapped[Optional[str]] = mapped_column(String)

    # Relationships
    entry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entries.id"), nullable=False
    )
    entry: Mapped[Entry] = relationship("Entry", back_populates="references")
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reference_sources.id"), nullable=False
    )
    source: Mapped[ReferenceSource] = relationship(
        "ReferenceSource", back_populates="references"
    )

    # Utilities
    @property
    def type(self) -> str:
        """Get the type of the Source material"""
        return self.source.type

    @property
    def title(self) -> str:
        """Get the title of the Source material"""
        return self.source.title

    @property
    def author(self) -> Optional[str]:
        """Get the author of the Source material"""
        return self.source.author

    @property
    def content_preview(self) -> str:
        """Get truncated content for display."""
        return self.content[:100] + "..." if len(self.content) > 100 else self.content

    # Call
    def __repr__(self):
        return f"<Reference(id={self.id}, content={self.content})>"

    def __str__(self) -> str:
        return (
            f"Reference '{self.content_preview}' "
            f"({self.title}, {self.type}; {self.entry.date_formatted})"
        )


class ReferenceSource(Base):
    """Defines the source of a reference (book, article, movie, etc.)."""

    __tablename__ = "reference_sources"
    __table_args__ = (
        CheckConstraint("title != ''", name="ck_ref_source_non_empty_title"),
        CheckConstraint("type != ''", name="ck_ref_source_non_empty_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    author: Mapped[Optional[str]] = mapped_column(String, index=True)

    # Relationships
    references: Mapped[List[Reference]] = relationship(
        "Reference", back_populates="source", cascade="all, delete-orphan"
    )

    # Utilities
    @property
    def reference_count(self) -> int:
        """Number of references from this source."""
        return len(self.references)

    @property
    def author_display(self) -> str:
        """Get author or 'Unknown' if not set."""
        return self.author or "Unknown"

    def add_reference_instance(
        self,
        entry: Entry,
        content: str,
        speaker: Optional[str] = None,
    ) -> Reference:
        """Add a new Reference instance for this source."""
        ref = Reference(content=content, entry=entry, speaker=speaker)
        self.references.append(ref)
        return ref

    # Call
    def __repr__(self):
        return "<ReferenceSource(id={self.id}, title={self.title}, type={self.type})>"

    def __str__(self) -> str:
        return (
            f"ReferenceSource {self.title} "
            f"({self.type}, {len(self.references)} references)"
        )


class Event(Base, SoftDeleteMixin):
    """
    Represents a main narrative event related to one or more entries.
    """

    __tablename__ = "events"
    __table_args__ = CheckConstraint("event != ''", name="ck_non_empty_event")

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    entries: Mapped[List[Entry]] = relationship(
        "Entry", secondary=entry_events, back_populates="events"
    )
    people: Mapped[List[Person]] = relationship(
        "Person", secondary=event_people, back_populates="events"
    )

    # Manuscript
    manuscript: Mapped[Optional[ManuscriptEvent]] = relationship(
        "ManuscriptEvent", uselist=False, back_populates="entry"
    )

    # Utilities
    @property
    def display_name(self) -> str:
        """Get the best display name for this Event."""
        return self.title or self.event

    @property
    def duration_days(self) -> Optional[int]:
        """Calculate event duration based on entry dates."""
        if not self.entries:
            return None

        dates = [entry.date for entry in self.entries]
        return (max(dates) - min(dates)).days + 1

    @property
    def start_date(self) -> Optional[date]:
        """First entry date for this event."""
        if not self.entries:
            return None
        return min(entry.date for entry in self.entries)

    @property
    def end_date(self) -> Optional[date]:
        """Last entry date for this event."""
        if not self.entries:
            return None
        return max(entry.date for entry in self.entries)

    @property
    def people_count(self) -> int:
        """Number of people involved in this event."""
        return len(self.people)

    @property
    def average_words_per_entry(self) -> float:
        """Average word count per entry for this event."""
        if not self.entries:
            return 0.0
        return self.total_word_count / len(self.entries)

    @property
    def total_word_count(self) -> int:
        """Total words written about this event."""
        return sum(entry.word_count for entry in self.entries)

    @property
    def involved_people_names(self) -> List[str]:
        """Names of all people involved in this event."""
        return [person.display_name for person in self.people]

    @property
    def has_manuscript_version(self) -> bool:
        """Check if this event has been added to manuscript."""
        return self.manuscript is not None

    @property
    def get_chronological_entries(self) -> List[Entry]:
        """Get entries for this event in chronological order."""
        return sorted(self.entries, key=lambda e: e.date)

    # Call
    def __repr__(self):
        return f"<Event(event={self.event})>"

    def __str__(self) -> str:
        return f"Event {self.display_name} ({len(self.entries)} entries)"


class Poem(Base):
    __tablename__ = "poems"
    __table_args__ = CheckConstraint("title != ''", name="ck_poem_non_empty_title")

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # Relationships
    versions: Mapped[List[PoemVersion]] = relationship(
        "PoemVersion", back_populates="poem", cascade="all, delete-orphan"
    )

    # Call
    def __repr__(self):
        return f"<Poem(title='{self.title}')>"

    def __str__(self) -> str:
        return f"Poem {self.title} ({len(self.versions)} versions)"


class PoemVersion(Base):
    __tablename__ = "poem_versions"
    __table_args__ = CheckConstraint(
        "text != ''", name="ck_poem_version_non_empty_text"
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    poem_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("poems.id"), nullable=False
    )
    entry_id: Mapped[int] = mapped_column(Integer, ForeignKey("entries.id"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    version_hash: Mapped[Optional[str]] = mapped_column(String)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    poem: Mapped[Poem] = relationship("Poem", back_populates="versions")
    entry: Mapped[Entry] = relationship("Entry", back_populates="poems")

    # Utilities
    @property
    def content_preview(self) -> str:
        """Get truncated content for display."""
        return self.content[:100] + "..." if len(self.content) > 100 else self.content

    # Call
    def __repr__(self):
        return f"<PoemVersion(content={self.content})>"

    def __str__(self) -> str:
        return f"PoemVersion ({self.poem.title}, {self.entry.date_formatted})"


class Tag(Base):
    """Represents a keyword/tag associated with entries."""

    __tablename__ = "tags"
    __table_args__ = CheckConstraint("tag != ''", name="ck_non_empty_tag")

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tag: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)

    # Relationships
    entries: Mapped[List[Entry]] = relationship(
        "Entry", secondary=entry_tags, back_populates="tags"
    )

    # Utilities
    @property
    def usage_count(self) -> int:
        """Number of entries using this tag."""
        return len(self.entries)

    @property
    def usage_span_days(self) -> int:
        """Number of days between first and last use."""
        if not self.entries or len(self.entries) < 2:
            return 0
        first = self.first_used
        last = self.last_used
        return (last - first).days if first and last else 0

    @property
    def first_used(self) -> Optional[date]:
        """Date when tag was first used."""
        if not self.entries:
            return None
        return min(entry.date for entry in self.entries)

    @property
    def last_used(self) -> Optional[date]:
        """Date when tag was last used."""
        if not self.entries:
            return None
        return max(entry.date for entry in self.entries)

    # Call
    def __repr__(self):
        return f"<Tag(name='{self.tag}')>"

    def __str__(self) -> str:
        return f"Tag {self.tag} ({self.usage_count} entries)"
