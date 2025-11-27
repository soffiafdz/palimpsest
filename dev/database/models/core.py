"""
Core Models
------------

Central models for the Palimpsest database.

Models:
    - SchemaInfo: Schema version tracking for migrations
    - Entry: Journal entry metadata (the primary model)

The Entry model is the heart of the system, containing metadata extracted from
Markdown frontmatter and relationships to all other entities.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import CheckConstraint, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .associations import (
    entry_aliases,
    entry_cities,
    entry_dates,
    entry_events,
    entry_locations,
    entry_people,
    entry_related,
    entry_tags,
)
from .base import Base, SoftDeleteMixin

if TYPE_CHECKING:
    from .creative import Event, PoemVersion, Reference
    from .entities import Alias, Person, Tag
    from .geography import City, Location, MentionedDate
    from ..models_manuscript import ManuscriptEntry


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


# ----- Entry Model -----
class Entry(Base, SoftDeleteMixin):
    """
    Central model representing a journal entry's metadata.

       Each Entry corresponds to a single Markdown file in the journal,
       with metadata extracted from the frontmatter and relationships
       to various entities mentioned in the entry.

       Soft Delete Support:
           Entries support soft deletion (marked as deleted without removing
           from database) to enable recovery and multi-machine synchronization.
           Inherited from SoftDeleteMixin.

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
           deleted_at: When this entry was soft deleted (from SoftDeleteMixin)
           deleted_by: Who/what deleted this entry (from SoftDeleteMixin)
           deletion_reason: Why this entry was deleted (from SoftDeleteMixin)

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
    dates: Mapped[List["MentionedDate"]] = relationship(
        "MentionedDate", secondary=entry_dates, back_populates="entries"
    )
    related_entries: Mapped[List["Entry"]] = relationship(
        "Entry",
        secondary=entry_related,
        primaryjoin="Entry.id == entry_related.c.entry_id",
        secondaryjoin="Entry.id == entry_related.c.related_entry_id",
        back_populates=None,
        overlaps="related_entries",
    )
    cities: Mapped[List["City"]] = relationship(
        "City", secondary=entry_cities, back_populates="entries"
    )
    locations: Mapped[List["Location"]] = relationship(
        "Location", secondary=entry_locations, back_populates="entries"
    )
    people: Mapped[List["Person"]] = relationship(
        "Person", secondary=entry_people, back_populates="entries"
    )
    aliases_used: Mapped[List["Alias"]] = relationship(
        "Alias", secondary=entry_aliases, back_populates="entries"
    )
    events: Mapped[List["Event"]] = relationship(
        "Event", secondary=entry_events, back_populates="entries"
    )
    tags: Mapped[List["Tag"]] = relationship(
        "Tag", secondary=entry_tags, back_populates="entries"
    )

    # ---- One-to-many Relationships ----
    references: Mapped[List["Reference"]] = relationship(
        "Reference", back_populates="entry", cascade="all, delete-orphan"
    )
    poems: Mapped[List["PoemVersion"]] = relationship(
        "PoemVersion", back_populates="entry", cascade="all, delete-orphan"
    )

    # ---- One-to-one Relationship ----
    manuscript: Mapped[Optional["ManuscriptEntry"]] = relationship(
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
