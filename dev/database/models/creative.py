"""
Creative Works Models
----------------------

Models for references, events, and poems in the journal.

Models:
    - Reference: External citations and quotes
    - ReferenceSource: Sources of references (books, articles, films, etc.)
    - Event: Narrative events spanning multiple entries
    - Poem: Poems written in the journal
    - PoemVersion: Specific versions of poems

These models track creative works and cultural references in the journal.
"""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .associations import entry_events, event_people
from .base import Base, SoftDeleteMixin
from .enums import ReferenceMode, ReferenceType

if TYPE_CHECKING:
    from .core import Entry
    from .entities import Person
    from ..models_manuscript import ManuscriptEvent


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
    entry: Mapped["Entry"] = relationship("Entry", back_populates="references")
    source: Mapped[Optional["ReferenceSource"]] = relationship(
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
    references: Mapped[List["Reference"]] = relationship(
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
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ---- Relationships ----
    entries: Mapped[List["Entry"]] = relationship(
        "Entry", secondary=entry_events, back_populates="events"
    )
    people: Mapped[List["Person"]] = relationship(
        "Person", secondary=event_people, back_populates="events"
    )
    manuscript: Mapped[Optional["ManuscriptEvent"]] = relationship(
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
    def chronological_entries(self) -> List["Entry"]:
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
    versions: Mapped[List["PoemVersion"]] = relationship(
        "PoemVersion", back_populates="poem", cascade="all, delete-orphan"
    )

    # ---- Computed properties ----
    @property
    def version_count(self) -> int:
        """Number of versions of this poem."""
        return len(self.versions)

    @property
    def latest_version(self) -> Optional["PoemVersion"]:
        """Get the most recent version of this poem."""
        if not self.versions:
            return None
        return max(self.versions, key=lambda v: v.revision_date or date.min)

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
    revision_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    version_hash: Mapped[Optional[str]] = mapped_column(String)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # ---- Foreign keys ----
    poem_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("poems.id"), nullable=False
    )
    entry_id: Mapped[int] = mapped_column(Integer, ForeignKey("entries.id"))

    # ---- Relationships ----
    poem: Mapped["Poem"] = relationship("Poem", back_populates="versions")
    entry: Mapped[Optional["Entry"]] = relationship("Entry", back_populates="poems")

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
