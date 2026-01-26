#!/usr/bin/env python3
"""
creative.py
-----------
Creative works models for the Palimpsest database.

This module contains models for references and poems:

Models:
    - ReferenceSource: Sources of references (books, articles, films, etc.)
    - Reference: Reference instances in journal entries
    - Poem: Parent entity for poem tracking
    - PoemVersion: Specific version of a poem in an entry

These models track creative works and cultural references in the journal.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date
from typing import TYPE_CHECKING, List, Optional

# --- Third party imports ---
from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

# --- Local imports ---
from .base import Base
from .enums import ReferenceMode, ReferenceType

if TYPE_CHECKING:
    from .core import Entry


class ReferenceSource(Base):
    """
    External work that can be referenced (book, film, song, etc.).

    Centralizes information about sources that are referenced
    across different entries. Supports various media types.

    Attributes:
        id: Primary key
        title: Title of the source (unique)
        author: Author or creator of the source (optional)
        type: Type of source (book, article, film, etc.)
        url: URL of the source (optional)

    Relationships:
        references: One-to-many with Reference (references from this source)
    """

    __tablename__ = "reference_sources"
    __table_args__ = (
        CheckConstraint("title != ''", name="ck_ref_source_non_empty_title"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    author: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    type: Mapped[ReferenceType] = mapped_column(
        SQLEnum(ReferenceType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    url: Mapped[Optional[str]] = mapped_column(String(500))

    # --- Relationship ---
    references: Mapped[List["Reference"]] = relationship(
        "Reference", back_populates="source", cascade="all, delete-orphan"
    )

    # --- Computed properties ---
    @property
    def display_name(self) -> str:
        """Get formatted display name with author."""
        if self.author:
            return f"{self.title} by {self.author}"
        return self.title

    @property
    def type_display(self) -> str:
        """Get human-readable type name."""
        return self.type.display_name if self.type else "Unknown"

    @property
    def reference_count(self) -> int:
        """Number of references from this source."""
        return len(self.references)

    @property
    def first_referenced(self) -> Optional[date]:
        """Earliest date this source was referenced."""
        if not self.references:
            return None
        return min(ref.entry.date for ref in self.references if ref.entry)

    @property
    def last_referenced(self) -> Optional[date]:
        """Most recent date this source was referenced."""
        if not self.references:
            return None
        return max(ref.entry.date for ref in self.references if ref.entry)

    def __repr__(self) -> str:
        return f"<ReferenceSource(id={self.id}, title='{self.title}')>"

    def __str__(self) -> str:
        return self.display_name


class Reference(Base):
    """
    A reference instance in a journal entry.

    Tracks how an external source is used in a specific entry.
    Can be a direct quote, paraphrase, or thematic reference.

    Attributes:
        id: Primary key
        entry_id: Foreign key to Entry
        source_id: Foreign key to ReferenceSource
        content: Quote if direct reference (optional)
        description: Brief description (optional)
        mode: How the reference is used (direct, indirect, paraphrase, visual)

    Relationships:
        entry: Many-to-one with Entry
        source: Many-to-one with ReferenceSource

    Notes:
        - Either content or description should be provided
    """

    __tablename__ = "references"
    __table_args__ = (
        CheckConstraint(
            "content IS NOT NULL OR description IS NOT NULL",
            name="ck_reference_has_content_or_description",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    mode: Mapped[ReferenceMode] = mapped_column(
        SQLEnum(ReferenceMode, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ReferenceMode.DIRECT,
        index=True,
    )

    # --- Foreign keys ---
    entry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entries.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reference_sources.id", ondelete="CASCADE"), nullable=False
    )

    # --- Relationships ---
    entry: Mapped["Entry"] = relationship("Entry", back_populates="references")
    source: Mapped["ReferenceSource"] = relationship(
        "ReferenceSource", back_populates="references"
    )

    # --- Computed properties ---
    @property
    def content_preview(self) -> Optional[str]:
        """Get truncated content for display (max 100 chars)."""
        if self.content:
            if len(self.content) <= 100:
                return self.content
            return f"{self.content[:97]}..."
        return None

    @property
    def mode_display(self) -> str:
        """Get human-readable mode name."""
        return self.mode.display_name if self.mode else "Unknown"

    @property
    def display_text(self) -> str:
        """Get display text (content preview or description)."""
        if self.content:
            return self.content_preview or ""
        return self.description or ""

    def __repr__(self) -> str:
        return f"<Reference(id={self.id}, entry_id={self.entry_id}, source_id={self.source_id})>"

    def __str__(self) -> str:
        return f"Reference to '{self.source.title}' ({self.mode_display})"


class Poem(Base):
    """
    Parent entity for poem tracking.

    Represents a poem that may have multiple versions across
    different journal entries.

    Attributes:
        id: Primary key
        title: Title of the poem

    Relationships:
        versions: One-to-many with PoemVersion
    """

    __tablename__ = "poems"
    __table_args__ = (CheckConstraint("title != ''", name="ck_poem_non_empty_title"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # --- Relationship ---
    versions: Mapped[List["PoemVersion"]] = relationship(
        "PoemVersion", back_populates="poem", cascade="all, delete-orphan"
    )

    # --- Computed properties ---
    @property
    def version_count(self) -> int:
        """Number of versions of this poem."""
        return len(self.versions)

    @property
    def latest_version(self) -> Optional["PoemVersion"]:
        """Get the most recent version of this poem."""
        if not self.versions:
            return None
        # Sort by entry date, with None dates last
        def sort_key(v: "PoemVersion") -> date:
            if v.entry:
                return v.entry.date
            return date.min
        return max(self.versions, key=sort_key)

    @property
    def first_appearance(self) -> Optional[date]:
        """Earliest date this poem appeared."""
        dates = [v.entry.date for v in self.versions if v.entry]
        return min(dates) if dates else None

    @property
    def last_appearance(self) -> Optional[date]:
        """Most recent date this poem appeared."""
        dates = [v.entry.date for v in self.versions if v.entry]
        return max(dates) if dates else None

    def __repr__(self) -> str:
        return f"<Poem(id={self.id}, title='{self.title}')>"

    def __str__(self) -> str:
        return self.title


class PoemVersion(Base):
    """
    Specific version of a poem in an entry.

    Tracks the content of a poem as it appears in a specific
    journal entry.

    Attributes:
        id: Primary key
        content: The poem text
        poem_id: Foreign key to Poem
        entry_id: Foreign key to Entry

    Relationships:
        poem: Many-to-one with Poem
        entry: Many-to-one with Entry
    """

    __tablename__ = "poem_versions"
    __table_args__ = (
        CheckConstraint("content != ''", name="ck_poem_version_non_empty_content"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Foreign keys ---
    poem_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("poems.id", ondelete="CASCADE"), nullable=False
    )
    entry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entries.id", ondelete="CASCADE"), nullable=False
    )

    # --- Relationships ---
    poem: Mapped["Poem"] = relationship("Poem", back_populates="versions")
    entry: Mapped["Entry"] = relationship("Entry", back_populates="poems")

    # --- Computed properties ---
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

    @property
    def word_count(self) -> int:
        """Count the number of words in the poem."""
        return len(self.content.split())

    def __repr__(self) -> str:
        return f"<PoemVersion(id={self.id}, poem_id={self.poem_id}, entry_id={self.entry_id})>"

    def __str__(self) -> str:
        entry_date = self.entry.date_formatted if self.entry else "unknown"
        return f"'{self.poem.title}' ({entry_date})"
