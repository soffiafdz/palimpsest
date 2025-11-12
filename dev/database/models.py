#!/usr/bin/env python3
"""
models.py
--------------------
SQLAlchemy ORM models for the Palimpsest metadata database.

This module defines the core database schema for journal entry metadata,
including relationships between entries, people, locations, events, and
other metadata elements.

Tables:
    - SchemaInfo: Schema version control for migrations
    - Entry: Journal entry metadata from Markdown frontmatter
    - MentionedDate: Dates referenced within entries
    - Location: Geographic locations mentioned in entries
    - Person: People mentioned in entries with soft delete support
    - Alias: Alternative names for people
    - Reference: External references cited in entries
    - ReferenceSource: Sources of references (books, articles, etc.)
    - Event: Thematic events spanning multiple entries
    - Poem: Poetry written in the journal
    - PoemVersion: Specific versions of poems linked to entries
    - Tag: Simple keyword tags for entries

Association Tables:
    - entry_dates: Links entries to mentioned dates
    - entry_locations: Links entries to locations
    - entry_people: Links entries to people
    - entry_events: Links entries to events
    - event_people: Links events to people
    - entry_aliases: Links entries to alias
    - entry_related: Self-referential entry relationships
    - entry_tags: Links entries to tags

Notes
==============
    - All datetime fields are timezone-aware (UTC)
    - Soft delete functionality available via SoftDeleteMixin
    - Extensive use of properties for computed fields
    - Check constraints ensure data integrity
    - Cascade deletes configured appropriately for each relationship
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from enum import Enum
from datetime import date, datetime, timezone
from typing import Any, List, Optional, Dict, TYPE_CHECKING

# --- Third party ---
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import (
    Boolean,
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
    UniqueConstraint,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

# --- Local ---
if TYPE_CHECKING:
    from .models_manuscript import (
        ManuscriptEntry,
        ManuscriptPerson,
        ManuscriptEvent,
    )


# ----- Base ORM class -----
class Base(DeclarativeBase):
    """
    Base class for all ORM models.

    Serves as the declarative base for SQLAlchemy models and provides
    access to the metadata object for table creation and migrations.
    """

    pass


# ----- Soft Delete -----
class SoftDeleteMixin:
    """
    Mixin providing soft delete functionality for models.

    Soft delete allows records to be marked as deleted without actually
    removing them from the database, preserving historical data and
    enabling recovery if needed.

    Attributes:
        deleted_at: Timestamp when the record was soft deleted
        deleted_by: Identifier of who deleted the record
        deletion_reason: Optional explanation for the deletion
    """

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="Timestamp of soft deletion"
    )
    deleted_by: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, doc="User or process that deleted the record"
    )
    deletion_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, doc="Reason for deletion"
    )

    @property
    def is_deleted(self) -> bool:
        """Check if the record is soft deleted."""
        return self.deleted_at is not None

    def soft_delete(
        self, deleted_by: Optional[str] = None, reason: Optional[str] = None
    ) -> None:
        """
        Mark record as soft deleted.

        Args:
            deleted_by: Identifier of who is deleting the record
            reason: Explanation for the deletion
        """
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = deleted_by
        self.deletion_reason = reason

    def restore(self) -> None:
        """Restore a soft deleted record."""
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
    Column("date_id", Integer, ForeignKey("dates.id", ondelete="CASCADE"), primary_key=True),
)

entry_cities = Table(
    "entry_cities",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("city_id", Integer, ForeignKey("cities.id", ondelete="CASCADE"), primary_key=True),
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
    Column("location_id", Integer, ForeignKey("locations.id", ondelete="CASCADE"), primary_key=True),
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
    Column("people_id", Integer, ForeignKey("people.id", ondelete="CASCADE"), primary_key=True),
)

entry_aliases = Table(
    "entry_aliases",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "alias_id",
        Integer,
        ForeignKey("aliases.id", ondelete="CASCADE"),
        primary_key=True,
    ),
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
    Column(
        "person_id",
        Integer,
        ForeignKey("people.id", ondelete="CASCADE"),  # Fixed: was SET NULL on primary key!
        primary_key=True,
    ),
)

entry_related = Table(
    "entry_related",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "related_entry_id",
        Integer,
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    # No self-references || duplicate pairs
    CheckConstraint("entry_id != related_entry_id", name="no_self_reference"),
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
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

location_dates = Table(
    "location_dates",
    Base.metadata,
    Column(
        "location_id",
        Integer,
        ForeignKey("locations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "date_id",
        Integer,
        ForeignKey("dates.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

people_dates = Table(
    "people_dates",
    Base.metadata,
    Column(
        "person_id",
        Integer,
        ForeignKey("people.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "date_id",
        Integer,
        ForeignKey("dates.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# ----- Schema Versioning -----
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


# ----- Enum -----
class ReferenceMode(str, Enum):
    """
    Enumeration of reference modes.
    - DIRECT: Direct quotation
    - INDIRECT: Indirect reference or allusion
    - PARAPHRASE: Paraphrased content
    - VISUAL: Visual/image reference
    """

    DIRECT = "direct"
    INDIRECT = "indirect"
    PARAPHRASE = "paraphrase"
    VISUAL = "visual"

    @classmethod
    def choices(cls) -> List[str]:
        """Get all available reference mode choices."""
        return [ref_mode.value for ref_mode in cls]

    @property
    def display_name(self) -> str:
        """Get human-readable display name."""
        display_map = {
            self.DIRECT: "Direct",
            self.INDIRECT: "Indirect",
            self.PARAPHRASE: "Paraphrase",
            self.VISUAL: "Visual",
        }
        return display_map.get(self, self.value.title())


class ReferenceType(str, Enum):
    """
    Enumeration of reference source types.

    Categories of sources that can be referenced in journal entries:
    - BOOK: Published books
    - POEM: Poem
    - ARTICLE: Articles, essays, papers
    - FILM: Movies and documentaries
    - SONG: Music and songs
    - PODCAST: Podcast episodes
    - INTERVIEW: Interviews
    - SPEECH: Speeches and talks
    - TV_SHOW: Television programs
    - VIDEO: Online videos, YouTube content
    - OTHER: Miscellaneous sources
    """

    BOOK = "book"
    POEM = "poem"
    ARTICLE = "article"
    FILM = "film"
    SONG = "song"
    PODCAST = "podcast"
    INTERVIEW = "interview"
    SPEECH = "speech"
    TV_SHOW = "tv_show"
    VIDEO = "video"
    OTHER = "other"

    @classmethod
    def choices(cls) -> List[str]:
        """Get all available reference type choices."""
        return [ref_type.value for ref_type in cls]

    @classmethod
    def written_types(cls) -> List["ReferenceType"]:
        """Get types that are primarily written/text-based."""
        return [cls.BOOK, cls.POEM, cls.ARTICLE]

    @classmethod
    def audiovisual_types(cls) -> List["ReferenceType"]:
        """Get types that are audiovisual media."""
        return [cls.FILM, cls.PODCAST, cls.TV_SHOW, cls.VIDEO]

    @classmethod
    def performance_types(cls) -> List["ReferenceType"]:
        """Get types that are performances or spoken word."""
        return [cls.SONG, cls.INTERVIEW, cls.SPEECH]

    @property
    def is_written(self) -> bool:
        """Check if this is a written/text-based source."""
        return self in self.written_types()

    @property
    def is_audiovisual(self) -> bool:
        """Check if this is an audiovisual source."""
        return self in self.audiovisual_types()

    @property
    def requires_author(self) -> bool:
        """Check if this source type typically has an author field."""
        return self in [self.BOOK, self.ARTICLE]

    @property
    def display_name(self) -> str:
        """Get human-readable display name."""
        display_map = {
            self.BOOK: "Book",
            self.ARTICLE: "Article",
            self.FILM: "Film",
            self.SONG: "Song",
            self.PODCAST: "Podcast",
            self.INTERVIEW: "Interview",
            self.SPEECH: "Speech",
            self.TV_SHOW: "TV Show",
            self.VIDEO: "Video",
            self.OTHER: "Other",
        }
        return display_map.get(self, self.value.title())


class RelationType(str, Enum):
    """
    Enumeration of personal relationship types.

    Categories of relationships with people mentioned in journal:
    - FAMILY: Family members
    - FRIEND: Friends
    - ROMANTIC: Romantic partners
    - COLLEAGUE: Work colleagues
    - ACQUAINTANCE: Casual acquaintances
    - PROFESSIONAL: Professional relationships (therapist, doctor, etc.)
    - PUBLIC: Public figures, celebrities
    - OTHER: Uncategorized relationships
    """

    FAMILY = "family"
    FRIEND = "friend"
    ROMANTIC = "romantic"
    COLLEAGUE = "colleague"
    ACQUAINTANCE = "acquaintance"
    PROFESSIONAL = "professional"
    PUBLIC = "public"
    OTHER = "other"

    @classmethod
    def choices(cls) -> List[str]:
        """Get all available relation type choices."""
        return [rel_type.value for rel_type in cls]

    @classmethod
    def personal_types(cls) -> List["RelationType"]:
        """Get types that represent personal relationships."""
        return [cls.FAMILY, cls.FRIEND, cls.ROMANTIC]

    @classmethod
    def professional_types(cls) -> List["RelationType"]:
        """Get types that represent professional relationships."""
        return [cls.COLLEAGUE, cls.PROFESSIONAL]

    @property
    def is_personal(self) -> bool:
        """Check if this is a personal relationship."""
        return self in self.personal_types()

    @property
    def is_professional(self) -> bool:
        """Check if this is a professional relationship."""
        return self in self.professional_types()

    @property
    def is_close(self) -> bool:
        """Check if this typically represents a close relationship."""
        return self in [self.FAMILY, self.FRIEND, self.ROMANTIC]

    @property
    def privacy_level(self) -> int:
        """
        Get privacy sensitivity level (higher = more sensitive).

        Used for manuscript adaptation decisions:
        - 5: Romantic (highest privacy)
        - 4: Family
        - 3: Friend
        - 2: Professional, Colleague
        - 1: Acquaintance, Public (lowest privacy)
        """
        privacy_map = {
            self.ROMANTIC: 5,
            self.FAMILY: 4,
            self.FRIEND: 3,
            self.PROFESSIONAL: 2,
            self.COLLEAGUE: 2,
            self.ACQUAINTANCE: 1,
            self.PUBLIC: 1,
            self.OTHER: 2,
        }
        return privacy_map.get(self, 0)

    @property
    def display_name(self) -> str:
        """Get human-readable display name."""
        return self.value.title()


# ----- Models -----
class Entry(Base):
    """
    Central model representing a journal entry's metadata.

       Each Entry corresponds to a single Markdown file in the journal,
       with metadata extracted from the frontmatter and relationships
       to various entities mentioned in the entry.

       Attributes:
           id: Primary key
           date: Date of the journal entry (unique)
           file_path: Path to the Markdown file (unique)
           file_hash: Hash of file content for change detection
           word_count: Number of words in the entry
           reading_time: Estimated reading time in minutes
           epigraph: Opening quote or epigraph
           epigraph_attribution: Attribution for epigraph (author, source)
           notes: Additional notes or metadata
           created_at: When this database record was created
           updated_at: When this database record was last updated

       Relationships:
           dates: Many-to-many with MentionedDate (dates referenced in entry)
           cities: Many-to-many with City (cities where entry took place)
           locations: Many-to-many with Location (specific venues mentioned)
           people: Many-to-many with Person (people mentioned)
           events: Many-to-many with Event (thematic events entry belongs to)
           tags: Many-to-many with Tag (keyword tags)
           related_entries: Many-to-many self-referential (related entries)
           references: One-to-many with Reference (external citations)
           poems: One-to-many with PoemVersion (poems written in entry)
           manuscript: One-to-one with ManuscriptEntry (manuscript metadata)
    """

    __tablename__ = "entries"
    __table_args__ = (
        CheckConstraint("file_path != ''", name="ck_entry_non_empty_file_path"),
        CheckConstraint("word_count >= 0", name="positive_entry_word_count"),
        CheckConstraint("reading_time >= 0.0", name="positive_entry_reading_time"),
    )

    # ---- Primary fields ----
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    file_hash: Mapped[Optional[str]] = mapped_column(String)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    reading_time: Mapped[float] = mapped_column(Float, default=0.0)
    epigraph: Mapped[Optional[str]] = mapped_column(Text)
    epigraph_attribution: Mapped[Optional[str]] = mapped_column(String(255))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # ---- Timestamps ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ---- Many-to-many Relationships ----
    dates: Mapped[List[MentionedDate]] = relationship(
        "MentionedDate", secondary=entry_dates, back_populates="entries"
    )
    related_entries: Mapped[List[Entry]] = relationship(
        "Entry",
        secondary=entry_related,
        primaryjoin="Entry.id == entry_related.c.entry_id",
        secondaryjoin="Entry.id == entry_related.c.related_entry_id",
        back_populates=None,
        overlaps="related_entries",
    )
    cities: Mapped[List[City]] = relationship(
        "City", secondary=entry_cities, back_populates="entries"
    )
    locations: Mapped[List[Location]] = relationship(
        "Location", secondary=entry_locations, back_populates="entries"
    )
    people: Mapped[List[Person]] = relationship(
        "Person", secondary=entry_people, back_populates="entries"
    )
    aliases_used: Mapped[List[Alias]] = relationship(
        "Alias", secondary=entry_aliases, back_populates="entries"
    )
    events: Mapped[List[Event]] = relationship(
        "Event", secondary=entry_events, back_populates="entries"
    )
    tags: Mapped[List[Tag]] = relationship(
        "Tag", secondary=entry_tags, back_populates="entries"
    )

    # ---- One-to-many Relationships ----
    references: Mapped[List[Reference]] = relationship(
        "Reference", back_populates="entry", cascade="all, delete-orphan"
    )
    poems: Mapped[List[PoemVersion]] = relationship(
        "PoemVersion", back_populates="entry", cascade="all, delete-orphan"
    )

    # ---- One-to-one Relationship ----
    manuscript: Mapped[Optional[ManuscriptEntry]] = relationship(
        "ManuscriptEntry", uselist=False, back_populates="entry"
    )

    # ---- Computed properties ----
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
        """Get date in YYYY-MM-DD format"""
        return self.date.isoformat()

    @property
    def date_range(self) -> Optional[Dict[str, Any]]:
        """
        Calculate statistics about mentioned dates in this entry.

        Returns:
            Dictionary with count, min_date, max_date, and duration,
            or None if no dates are mentioned
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
            or (person.full_name and search_name in person.full_name.lower())
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
        return any(tag.tag.lower() == search_tag for tag in self.tags)

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


class MentionedDate(Base):
    """
    Represents dates referenced within journal entries.

    Tracks specific dates mentioned in entries, allowing for temporal
    analysis and cross-referencing of events. Dates can optionally include
    context about why they were mentioned. They can, but not necessarily
    be the date of the entry.

    Attributes:
        id: Primary key
        date: The mentioned date
        context: Optional context about why this date was mentioned

    Relationships:
        entries: Many-to-many with Entry (entries that mention this date)
        locations: Many-to-many with Location (locations visited on this date)
        people: Many-to-many with People (people interacted with on this date)

    Computed Properties:
        date_formatted: ISO format string (YYYY-MM-DD)
        entry_count: Number of entries referencing this date
        first_mention_date: When this date was first mentioned in the journal
        last_mention_date: Most recent mention of this date

    Examples:
        # Simple date mention
        MentionedDate(date=date(2020, 3, 15))

        # Date with context
        MentionedDate(date=date(2020, 3, 15), context="thesis defense")
    """

    __tablename__ = "dates"

    # ---- Primary fields ----
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    context: Mapped[Optional[str]] = mapped_column(Text)

    # ---- Relationship ----
    entries: Mapped[List[Entry]] = relationship(
        "Entry", secondary=entry_dates, back_populates="dates"
    )
    locations: Mapped[List[Location]] = relationship(
        "Location", secondary=location_dates, back_populates="dates"
    )
    people: Mapped[List[Person]] = relationship(
        "Person", secondary=people_dates, back_populates="dates"
    )

    # ---- Computed properties ----
    @property
    def date_formatted(self) -> str:
        """Get date in YYYY-MM-DD format"""
        return self.date.isoformat()

    @property
    def entry_count(self) -> int:
        """Count of entries referencing this date."""
        return len(self.entries) if self.entries else 0

    @property
    def location_count(self) -> int:
        """Count of locations visited on this date."""
        return len(self.locations) if self.locations else 0

    @property
    def locations_visited(self) -> List[str]:
        """Names of locations visited on this date."""
        return [loc.name for loc in self.locations] if self.locations else []

    @property
    def people_count(self) -> int:
        """Count of people present on this date."""
        return len(self.people) if self.people else 0

    @property
    def people_present(self) -> List[str]:
        """Names of people present on this date."""
        return [person.display_name for person in self.people] if self.people else []

    @property
    def first_mention_date(self) -> Optional[date]:
        """Date when this was first menioned."""
        if not self.entries:
            return None
        return min(entry.date for entry in self.entries)

    @property
    def last_mention_date(self) -> Optional[date]:
        """Date when this was most recently mentioned."""
        if not self.entries:
            return None
        return max(entry.date for entry in self.entries)

    def __repr__(self) -> str:
        return f"<MentionedDate(id={self.id}, date={self.date})>"

    def __str__(self) -> str:
        count = self.entry_count
        if count == 0:
            return f"Date {self.date_formatted} (no entries)"
        elif count == 1:
            return f"Date {self.date_formatted} (1 entry)"
        else:
            return f"Date {self.date_formatted} ({count} entries)"


class City(Base):
    """
    Represents Cities mentioned in entries.

    Tracks cities referenced in journal entries for geographic analysis
    and location-based queries. Cities are parent entities for Locations.

    Attributes:
        id: Primary key
        city: Name of the city (unique)
        state_province: State or province (optional)
        country: Country (optional)

    Relationships:
        locations: One-to-many with Location (specific venues in this city)
        entries: Many-to-many with Entry (entries that took place in this city)
    """

    __tablename__ = "cities"
    __table_args__ = (CheckConstraint("city != ''", name="ck_city_non_empty_name"),)

    # ---- Primary fields ----
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    city: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    state_province: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    country: Mapped[Optional[str]] = mapped_column(String(255), index=True)

    # ---- Relationship ----
    locations: Mapped[List[Location]] = relationship("Location", back_populates="city")
    entries: Mapped[List[Entry]] = relationship(
        "Entry", secondary=entry_cities, back_populates="cities"
    )

    # ---- Computed properties ----
    @property
    def entry_count(self) -> int:
        """Number of entries mentioning this location."""
        return len(self.entries)

    @property
    def visit_frequency(self) -> Dict[str, int]:
        """
        Calculate visit frequency by year-month.

        Returns:
            Dictionary mapping YYYY-MM strings to visit counts
        """
        frequency: Dict[str, int] = {}
        for entry in self.entries:
            year_month = entry.date.strftime("%Y-%m")
            frequency[year_month] = frequency.get(year_month, 0) + 1
        return frequency

    # Call
    def __repr__(self) -> str:
        return f"<City(id={self.id}, city={self.city})>"

    def __str__(self) -> str:
        # Build display name with available context
        parts = [self.city]

        if self.state_province:
            parts.append(self.state_province)

        if self.country:
            parts.append(self.country)

        location_str = ", ".join(parts)

        # Add entry count
        count = self.entry_count
        if count == 0:
            return f"City: {location_str} (no entries)"
        elif count == 1:
            return f"City: {location_str} (1 entry)"
        else:
            return f"City: {location_str} ({count} entries)"


class Location(Base):
    """
    Represents specific venues or places mentioned in entries.

    Tracks venues referenced in journal entries for geographic analysis
    and location-based queries. Each location belongs to a parent City.

    Attributes:
        id: Primary key
        name: Name of the location/venue (unique)
        city_id: Foreign key to parent City
        city: Relationship to parent City

    Relationships:
        city: Many-to-one with City (parent city)
        entries: Many-to-many with Entry (entries mentioning this location)
        dates: Many-to-many with MentionedDate (dates related to this location)

    Computed Properties:
        entry_count: Number of entries mentioning this location
        visit_frequency: Monthly visit frequency statistics
        visit_span_days: Days between first and last visit
    """

    __tablename__ = "locations"
    __table_args__ = (
        CheckConstraint("name != ''", name="ck_location_non_empty_name"),
        UniqueConstraint("name", "city_id", name="uq_location_name_city"),
    )

    # ---- Primary fields ----
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True  # Removed unique=True (now composite)
    )

    # ---- Geographical location ----
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    city: Mapped[City] = relationship(back_populates="locations")

    # ---- Relationship ----
    entries: Mapped[List[Entry]] = relationship(
        "Entry", secondary=entry_locations, back_populates="locations"
    )
    dates: Mapped[List[MentionedDate]] = relationship(
        "MentionedDate", secondary=location_dates, back_populates="locations"
    )

    # ---- Computed properties ----
    @property
    def entry_count(self) -> int:
        """Number of entries mentioning this location."""
        return len(self.entries)

    @property
    def visit_count(self) -> int:
        """Total number of recorded visits (explicit dates)."""
        return len(self.dates)

    @property
    def first_visit_date(self) -> Optional[date]:
        """Earliest date this location was visited."""
        dates = [md.date for md in self.dates]
        return min(dates) if dates else None

    @property
    def last_visit_date(self) -> Optional[date]:
        """Most recent date this location was visited."""
        dates = [md.date for md in self.dates]
        return max(dates) if dates else None

    @property
    def visit_timeline(self) -> List[Dict[str, Any]]:
        """
        Complete timeline of visits with context.

        Returns:
            List of dicts with keys: date, source ('entry'|'mentioned'), context
        """
        timeline = []

        # Add entry dates
        for entry in self.entries:
            timeline.append(
                {
                    "date": entry.date,
                    "source": "entry",
                    "entry_id": entry.id,
                    "context": None,
                }
            )

        # Add explicit mentioned dates
        for md in self.dates:
            timeline.append(
                {
                    "date": md.date,
                    "source": "mentioned",
                    "context": md.context,
                    "mentioned_date_id": md.id,
                }
            )

        # Sort by date
        timeline.sort(key=lambda x: x["date"])
        return timeline

    @property
    def visit_frequency(self) -> Dict[str, int]:
        """
        Calculate visit frequency by year-month.
        Uses all recorded visits (entries + mentioned dates).

        Returns:
            Dictionary mapping YYYY-MM strings to visit counts
        """
        frequency: Dict[str, int] = {}
        # Count from mentioned dates
        for md in self.dates:
            year_month = md.date.strftime("%Y-%m")
            frequency[year_month] = frequency.get(year_month, 0) + 1
        return frequency

    @property
    def visit_span_days(self) -> int:
        """Days between first and last visit."""
        first = self.first_visit_date
        last = self.last_visit_date
        if not first or not last or first == last:
            return 0
        return (last - first).days

    # Call
    def __repr__(self) -> str:
        return f"<Location(id={self.id}, name={self.name})>"

    def __str__(self) -> str:
        loc_name = f"{self.name} ({self.city.city})"
        count = self.visit_count
        if count == 0:
            return f"Location {loc_name} (no visits)"
        elif count == 1:
            return f"Location {loc_name} (1 visit)"
        else:
            return f"Location {loc_name} ({count} visits)"


class Person(Base, SoftDeleteMixin):
    """
    Represents a person mentioned in journal entries.

    Tracks individuals referenced across entries with support for:
    - Multiple names (name vs full_name)
    - Name disambiguation (name_fellow flag)
    - Relationship categorization
    - Aliases
    - Soft deletion

    Attributes:
        id: Primary key
        name: Primary name (usually first name or nickname)
        full_name: Full legal name (unique, optional)
        name_fellow: Flag indicating multiple people share this name
        relation_type: Category of relationship (enum)

    Relationships:
        aliases: One-to-many with Alias (alternative names)
        events: Many-to-many with Event (events person is involved in)
        entries: Many-to-many with Entry (entries mentioning person)
        manuscript: One-to-one with ManuscriptPerson (manuscript character mapping)

    Computed Properties:
        display_name: Best name for display (full_name or name)
        all_names: List of all names including aliases
        entry_count: Number of entries mentioning person
        event_count: Number of events person is involved in
        first_appearance: Date of first journal mention
        last_appearance: Date of most recent mention
        relationship_display: Human-readable relationship type
        is_close_relationship: Whether relationship is close (family/friend/romantic)
        privacy_sensitivity: Privacy level for manuscript adaptation (0-5)
        mention_frequency: Monthly mention frequency statistics
    """

    __tablename__ = "people"
    __table_args__ = (CheckConstraint("name != ''", name="ck_person_non_empty_name"),)

    # ---- Primary fields ----
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, index=True
    )
    name_fellow: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    relation_type: Mapped[Optional[RelationType]] = mapped_column(
        SQLEnum(RelationType, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
        index=True,
    )

    # ---- Relationships ----
    aliases: Mapped[List[Alias]] = relationship(
        "Alias", back_populates="person", cascade="all, delete-orphan"
    )
    dates: Mapped[List[MentionedDate]] = relationship(
        "MentionedDate", secondary=people_dates, back_populates="people"
    )
    events: Mapped[List[Event]] = relationship(
        "Event", secondary=event_people, back_populates="people"
    )
    entries: Mapped[List[Entry]] = relationship(
        "Entry", secondary=entry_people, back_populates="people"
    )
    manuscript: Mapped[Optional[ManuscriptPerson]] = relationship(
        "ManuscriptPerson", uselist=False, back_populates="person"
    )

    # ---- Computed properties ----
    @property
    def display_name(self) -> str:
        """Get the best display name for this person."""
        return self.full_name if self.full_name else self.name

    @property
    def all_names(self) -> List[str]:
        """Get all names and aliases for this person."""
        names = [self.name]
        if self.full_name:
            names.append(self.full_name)
        names.extend([alias.alias for alias in self.aliases])
        return list(set(names))  # Remove duplicates

    @property
    def entry_count(self) -> int:
        """Number of entries mentioning this person."""
        return len(self.entries)

    @property
    def appearances_count(self) -> int:
        """Total number of appearances (explicit dates)."""
        return len(self.dates)

    @property
    def event_count(self) -> int:
        """Number of events this person is involved in."""
        return len(self.events)

    @property
    def first_appearance_date(self) -> Optional[date]:
        """Earliest date this person was mentioned."""
        dates = [md.date for md in self.dates]
        return min(dates) if dates else None

    @property
    def last_appearance_date(self) -> Optional[date]:
        """Most recent date this person was mentioned."""
        dates = [md.date for md in self.dates]
        return max(dates) if dates else None

    @property
    def mention_timeline(self) -> List[Dict[str, Any]]:
        """
        Complete timeline of mentions with context.

        Returns:
            List of dicts with keys: date, source ('entry'|'mentioned'), context
        """
        timeline = []

        # Add entry dates
        for entry in self.entries:
            timeline.append(
                {
                    "date": entry.date,
                    "source": "entry",
                    "entry_id": entry.id,
                    "context": None,
                }
            )

        # Add explicit mentioned dates
        for md in self.dates:
            timeline.append(
                {
                    "date": md.date,
                    "source": "date",
                    "context": md.context,
                    "mentioned_date_id": md.id,
                }
            )

        # Sort by date
        timeline.sort(key=lambda x: x["date"])
        return timeline

    @property
    def mention_frequency(self) -> Dict[str, int]:
        """
        Calculate mention frequency by year-month.
        Uses all mentions (entries + mentioned dates).

        Returns:
            Dictionary mapping YYYY-MM strings to mention counts
        """
        frequency: Dict[str, int] = {}
        for md in self.dates:
            year_month = md.date.strftime("%Y-%m")
            frequency[year_month] = frequency.get(year_month, 0) + 1
        return frequency

    @property
    def relationship_display(self) -> str:
        """Get human-readable relationship type."""
        if self.relation_type:
            return self.relation_type.display_name
        return "Unknown"

    @property
    def is_close_relationship(self) -> bool:
        """Check if this person has a close relationship."""
        return self.relation_type.is_close if self.relation_type else False

    @property
    def privacy_sensitivity(self) -> int:
        """Get privacy sensitivity level for manuscript purposes."""
        return self.relation_type.privacy_level if self.relation_type else 0

    def is_known_as(self, name: str) -> bool:
        """
        Check if person is known by this name or alias.

        Args:
            name: Name to check (case-insensitive)

        Returns:
            True if this is a known name for the person
        """
        search_name = name.lower()
        return search_name in [n.lower() for n in self.all_names]

    def __repr__(self) -> str:
        return f"<Person(id={self.id}, name='{self.name}')>"

    def __str__(self) -> str:
        return f"Person {self.display_name} ({self.appearances_count} mentions)"


class Alias(Base):
    """Represents the multiple aliases for people."""

    __tablename__ = "aliases"
    __table_args__ = (CheckConstraint("alias != ''", name="ck_non_empty_alias"),)

    # ---- Primary fields ----
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    alias: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # ---- Foreign key ----
    person_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("people.id", ondelete="CASCADE")
    )

    # ---- Relationship ----
    person: Mapped[Person] = relationship("Person", back_populates="aliases")
    entries: Mapped[List[Entry]] = relationship(
        "Entry", secondary=entry_aliases, back_populates="aliases_used"
    )

    # ---- Computed properties ----
    @property
    def first_used(self) -> Optional[date]:
        """Date when alias was first used."""
        if not self.entries:
            return None
        return min(entry.date for entry in self.entries)

    @property
    def last_used(self) -> Optional[date]:
        """Date when alias was last used."""
        if not self.entries:
            return None
        return max(entry.date for entry in self.entries)

    @property
    def usage_count(self) -> int:
        """Number of entries using this alias."""
        return len(self.entries)

    def __repr__(self) -> str:
        return f"<Alias(id={self.id}, alias={self.alias})>"

    def __str__(self) -> str:
        count = self.usage_count
        if count == 0:
            return f"Alias '{self.alias}' for {self.person.display_name} (unused)"
        elif count == 1:
            return f"Alias '{self.alias}' for {self.person.display_name} (1 entry)"
        else:
            return (
                f"Alias '{self.alias}' for {self.person.display_name} ({count} entries)"
            )


class Reference(Base):
    """
    External references cited in entries.

    Tracks quotes, citations, and references to external sources
    mentioned in journal entries. References can be direct quotes,
    paraphrases, or visual references.

    Attributes:
        id: Primary key
        content: The quoted or referenced content (optional)
        description: Brief description of reference (optional, but content or description required)
        speaker: Who said/wrote this (optional)
        mode: Type of reference (direct/indirect/paraphrase/visual)
        entry_id: Which entry contains this reference (required)
        source_id: Source of the reference (book, article, etc., optional)

    Relationships:
        entry: Many-to-one with Entry (parent entry)
        source: Many-to-one with ReferenceSource (optional source details)

    Computed Properties:
        content_preview: Truncated content for display (max 100 chars)

    Note:
        Either content or description must be provided.
    """

    __tablename__ = "references"
    __table_args__ = (
        CheckConstraint(
            "content IS NOT NULL OR description IS NOT NULL",
            name="ck_reference_has_content_or_description",
        ),
    )

    # ---- Primary fields ----
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(String(255))
    speaker: Mapped[Optional[str]] = mapped_column(String(255))
    mode: Mapped[ReferenceMode] = mapped_column(
        SQLEnum(ReferenceMode, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ReferenceMode.DIRECT.value,
        index=True,
    )

    # ---- Foreign keys ----
    entry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entries.id"), nullable=False
    )
    source_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("reference_sources.id")
    )

    # ---- Relationships ----
    entry: Mapped[Entry] = relationship("Entry", back_populates="references")
    source: Mapped[Optional[ReferenceSource]] = relationship(
        "ReferenceSource", back_populates="references"
    )

    # ---- Computed property ----
    @property
    def content_preview(self) -> str | None:
        """Get truncated content for display (max 100 chars)."""
        if self.content:
            if len(self.content) <= 100:
                return self.content
            return f"{self.content[:97]}..."
        return None

    def __repr__(self) -> str:
        return f"<Reference(id={self.id}, entry_id={self.entry_id})>"

    def __str__(self) -> str:
        source_info = f" from {self.source.title}" if self.source else ""
        ref = self.content_preview if self.content else self.description
        return f"Reference '{ref}'{source_info}"


class ReferenceSource(Base):
    """
    Sources of references (books, articles, movies, etc).

    Centralizes information about sources that are referenced
    multiple times across different entries. Supports various
    media types with type-specific validation.

    Attributes:
        id: Primary key
        type: Type of source (book/article/film/poem/song/etc.)
        title: Title of the source (unique)
        author: Author or creator of the source (optional)

    Relationships:
        references: One-to-many with Reference (references from this source)

    Computed Properties:
        display_name: Formatted name with type and author
        requires_author_validation: Whether this source type should have an author
        reference_count: Number of references from this source

    Note:
        Some source types (book, article) typically require an author field.
    """

    __tablename__ = "reference_sources"
    __table_args__ = (
        CheckConstraint("title != ''", name="ck_ref_source_non_empty_title"),
    )

    # ---- Primary fields ----
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    type: Mapped[ReferenceType] = mapped_column(
        SQLEnum(ReferenceType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    author: Mapped[Optional[str]] = mapped_column(String(255), index=True)

    # ---- Relationship ----
    references: Mapped[List[Reference]] = relationship(
        "Reference", back_populates="source", cascade="all, delete-orphan"
    )

    # ---- Computed property ----
    @property
    def display_name(self) -> str:
        """Get formatted display name with type."""
        if self.author:
            return f"{self.title} by {self.author} ({self.type.display_name})"
        return f"{self.title} ({self.type.display_name})"

    @property
    def requires_author_validation(self) -> bool:
        """Check if this source type should have an author."""
        return self.type.requires_author and not self.author

    @property
    def reference_count(self) -> int:
        """Number of references from this source."""
        return len(self.references)

    def __repr__(self) -> str:
        return f"<ReferenceSource(id={self.id}, title={self.title})>"

    def __str__(self) -> str:
        author_info = f" by {self.author}" if self.author else ""
        count = self.reference_count
        ref_str = "reference" if count == 1 else "references"
        return (
            f"{self.type.display_name}: {self.title}{author_info} ({count} {ref_str})"
        )


class Event(Base, SoftDeleteMixin):
    """
    Narrative events spanning multiple entries.

    Represents significant events or periods that are referenced
    across multiple journal entries.

    Attributes:
        id: Primary key
        event: Short identifier for the event (unique)
        title: Full title of the event
        description: Detailed description
    """

    __tablename__ = "events"
    __table_args__ = (CheckConstraint("event != ''", name="ck_non_empty_event"),)

    # ---- Primary fields ----
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # ---- Relationships ----
    entries: Mapped[List[Entry]] = relationship(
        "Entry", secondary=entry_events, back_populates="events"
    )
    people: Mapped[List[Person]] = relationship(
        "Person", secondary=event_people, back_populates="events"
    )
    manuscript: Mapped[Optional[ManuscriptEvent]] = relationship(
        "ManuscriptEvent", uselist=False, back_populates="event"
    )

    # ---- Computed properties ----
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
    def chronological_entries(self) -> List[Entry]:
        """Get entries for this event in chronological order."""
        if not self.entries:
            return []
        return sorted(self.entries, key=lambda e: e.date)

    @property
    def start_date(self) -> Optional[date]:
        """Start date of the event."""
        if not self.entries:
            return None
        dates = [entry.date for entry in self.entries if entry.date]
        return min(dates) if dates else None

    @property
    def end_date(self) -> Optional[date]:
        """End date of the event."""
        if not self.entries:
            return None
        dates = [entry.date for entry in self.entries if entry.date]
        return max(dates) if dates else None

    def __repr__(self) -> str:
        return f"<Event(id={self.id}, event={self.event})>"

    def __str__(self) -> str:
        return f"Event {self.display_name} ({len(self.entries)} entries)"


class Poem(Base):
    """
    Parent entity for poem tracking.

    Represents a poem title that may have multiple versions/revisions
    across different entries. The Poem entity groups related PoemVersions.

    Attributes:
        id: Primary key
        title: Title of the poem (not unique - multiple versions allowed)

    Relationships:
        versions: One-to-many with PoemVersion (all versions of this poem)

    Computed Properties:
        version_count: Number of versions of this poem
        latest_version: Most recent version by revision_date

    Note:
        Poems are not unique by title - the same title can have multiple
        poem records if they represent different works. Version deduplication
        is handled at the PoemVersion level via version_hash.
    """

    __tablename__ = "poems"
    __table_args__ = (CheckConstraint("title != ''", name="ck_poem_non_empty_title"),)

    # ---- Primary fields ----
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # ---- Relationship ----
    versions: Mapped[List[PoemVersion]] = relationship(
        "PoemVersion", back_populates="poem", cascade="all, delete-orphan"
    )

    # ---- Computed properties ----
    @property
    def version_count(self) -> int:
        """Number of versions of this poem."""
        return len(self.versions)

    @property
    def latest_version(self) -> Optional[PoemVersion]:
        """Get the most recent version of this poem."""
        if not self.versions:
            return None
        return max(self.versions, key=lambda v: v.revision_date)

    def __repr__(self) -> str:
        return f"<Poem(id={self.id}, title={self.title})>"

    def __str__(self) -> str:
        count = self.version_count
        version_str = "version" if count == 1 else "versions"
        return f"Poem: {self.title} ({count} {version_str})"


class PoemVersion(Base):
    """
    Specific versions of poems linked to entries.

    Tracks different versions of poems as they evolve over time,
    with each version potentially linked to a specific journal entry.

    Attributes:
        id: Primary key
        poem_id: Foreign key to parent Poem
        entry_id: Foreign key to Entry (optional)
        content: The poem text for this version
        revision_date: When this version was created
        version_hash: Hash of content for deduplication
        notes: Notes about this version
    """

    __tablename__ = "poem_versions"
    __table_args__ = (
        CheckConstraint("content != ''", name="ck_poem_version_non_empty_content"),
    )

    # ---- Primary fields ----
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    revision_date: Mapped[date] = mapped_column(Date, index=True)
    version_hash: Mapped[Optional[str]] = mapped_column(String)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # ---- Foreign keys ----
    poem_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("poems.id"), nullable=False
    )
    entry_id: Mapped[int] = mapped_column(Integer, ForeignKey("entries.id"))

    # ---- Relationships ----
    poem: Mapped[Poem] = relationship("Poem", back_populates="versions")
    entry: Mapped[Optional[Entry]] = relationship("Entry", back_populates="poems")

    # ---- Computed properties ----
    @property
    def content_preview(self) -> str:
        """Get truncated content for display (max 100 chars)."""
        if len(self.content) <= 100:
            return self.content
        return f"{self.content[:97]}..."

    @property
    def line_count(self) -> int:
        """Count the number of lines in the poem."""
        return len(self.content.splitlines())

    def __repr__(self) -> str:
        return f"<PoemVersion(id={self.id}, poem_id={self.poem_id})>"

    def __str__(self) -> str:
        date_str = self.revision_date.isoformat()
        return f"Version of '{self.poem.title}' ({date_str})"


class Tag(Base):
    """
    Simple keyword tags for entries.

    Provides a flexible tagging system for categorizing and
    searching journal entries.

    Attributes:
        id: Primary key
        tag: The tag text (unique)
    """

    __tablename__ = "tags"
    __table_args__ = (CheckConstraint("tag != ''", name="ck_non_empty_tag"),)

    # ---- Primary fields ----
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tag: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )

    # ---- Relationship ----
    entries: Mapped[List[Entry]] = relationship(
        "Entry", secondary=entry_tags, back_populates="tags"
    )

    # ---- Computed properties ----
    @property
    def usage_count(self) -> int:
        """Number of entries using this tag."""
        return len(self.entries)

    @property
    def usage_span_days(self) -> int:
        """Number of days between first and last use."""
        if not self.entries or len(self.entries) < 2:
            return 0
        dates = [entry.date for entry in self.entries]
        return (max(dates) - min(dates)).days

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

    @property
    def chronological_entries(self) -> List[Entry]:
        """Get entries for this tag in chronological order."""
        return sorted(self.entries, key=lambda e: e.date)

    # Call
    def __repr__(self) -> str:
        return f"<Tag(id={self.id}, tag={self.tag})>"

    def __str__(self) -> str:
        count = self.usage_count
        if count == 0:
            return f"Tag '{self.tag}' (no entries)"
        elif count == 1:
            return f"Tag '{self.tag}' (1 entry)"
        else:
            return f"Tag '{self.tag}' ({count} entries)"
