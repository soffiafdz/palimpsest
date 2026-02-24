#!/usr/bin/env python3
"""
metadata.py
-----------
Metadata models for the Palimpsest database.

This module contains models for controlled vocabularies and per-entry
instance metadata:

Models:
    - Motif: Controlled vocabulary of 26 motifs
    - MotifInstance: Motif as it appears in a specific entry
    - ThemeInstance: Theme as it appears in a specific entry

Motifs are recurring thematic patterns with a fixed vocabulary.
Themes are free-form named patterns with per-entry descriptions.
Each entry can have multiple motif/theme instances with descriptions.

Controlled Vocabulary (26 Motifs):
    The Anchor, The Bed, The Body, The Bottle, The Cavalry, The Chaser,
    The Death of Ivan, The Edge, The Ghost, The High-Functioning Collapse,
    The Hunger, The Institution, The Loop, The Mask, The Mirror,
    The Obsession, The Page, The Place, The Replacement, The Scroll,
    The Spiral, The Telling, The Touch, The Transformation, The Void, The Wait
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from typing import TYPE_CHECKING, List

# --- Third party imports ---
from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

# --- Local imports ---
from .base import Base

if TYPE_CHECKING:
    from .core import Entry


# The 26 controlled motifs
CONTROLLED_MOTIFS = [
    "The Anchor",
    "The Bed",
    "The Body",
    "The Bottle",
    "The Cavalry",
    "The Chaser",
    "The Death of Ivan",
    "The Edge",
    "The Ghost",
    "The High-Functioning Collapse",
    "The Hunger",
    "The Institution",
    "The Loop",
    "The Mask",
    "The Mirror",
    "The Obsession",
    "The Page",
    "The Place",
    "The Replacement",
    "The Scroll",
    "The Spiral",
    "The Telling",
    "The Touch",
    "The Transformation",
    "The Void",
    "The Wait",
]


class Motif(Base):
    """
    Controlled vocabulary motif.

    Represents one of the 26 predefined motifs. Motifs are
    recurring thematic patterns that appear across entries.

    Attributes:
        id: Primary key
        name: Motif name (unique, from controlled vocabulary)

    Relationships:
        instances: One-to-many with MotifInstance (occurrences in entries)
    """

    __tablename__ = "motifs"
    __table_args__ = (CheckConstraint("name != ''", name="ck_motif_non_empty_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )

    # --- Relationship ---
    instances: Mapped[List["MotifInstance"]] = relationship(
        "MotifInstance", back_populates="motif", cascade="all, delete-orphan"
    )

    # --- Computed properties ---
    @property
    def instance_count(self) -> int:
        """Number of entries with this motif."""
        return len(self.instances)

    @property
    def entries(self) -> List["Entry"]:
        """Get all entries with this motif."""
        return [instance.entry for instance in self.instances if instance.entry]

    def __repr__(self) -> str:
        return f"<Motif(id={self.id}, name='{self.name}')>"

    def __str__(self) -> str:
        return self.name


class MotifInstance(Base):
    """
    Motif as it appears in a specific entry.

    Tracks how a motif manifests in a particular journal entry
    with an entry-specific description.

    Attributes:
        id: Primary key
        motif_id: Foreign key to Motif
        entry_id: Foreign key to Entry
        description: Entry-specific description of how the motif appears

    Relationships:
        motif: Many-to-one with Motif
        entry: Many-to-one with Entry
    """

    __tablename__ = "motif_instances"
    __table_args__ = (
        CheckConstraint("description != ''", name="ck_motif_instance_non_empty_desc"),
        UniqueConstraint("motif_id", "entry_id", name="uq_motif_instance_motif_entry"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Foreign keys ---
    motif_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("motifs.id", ondelete="CASCADE"), nullable=False
    )
    entry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entries.id", ondelete="CASCADE"), nullable=False
    )

    # --- Relationships ---
    motif: Mapped["Motif"] = relationship("Motif", back_populates="instances")
    entry: Mapped["Entry"] = relationship("Entry", back_populates="motif_instances")

    # --- Computed properties ---
    @property
    def motif_name(self) -> str:
        """Get the name of the motif."""
        return self.motif.name if self.motif else ""

    @property
    def description_preview(self) -> str:
        """Get truncated description for display (max 100 chars)."""
        if len(self.description) <= 100:
            return self.description
        return f"{self.description[:97]}..."

    def __repr__(self) -> str:
        return f"<MotifInstance(id={self.id}, motif_id={self.motif_id}, entry_id={self.entry_id})>"

    def __str__(self) -> str:
        return f"{self.motif_name}: {self.description_preview}"


class ThemeInstance(Base):
    """
    Theme as it appears in a specific entry.

    Tracks how a free-form theme manifests in a particular journal entry
    with an entry-specific description. Themes are the middle ground
    between tags (keyword-only) and motifs (controlled vocabulary):
    free-form names with per-entry descriptions.

    Attributes:
        id: Primary key
        description: Entry-specific description of how the theme appears
        theme_id: Foreign key to Theme
        entry_id: Foreign key to Entry

    Relationships:
        theme: Many-to-one with Theme
        entry: Many-to-one with Entry
    """

    __tablename__ = "theme_instances"
    __table_args__ = (
        CheckConstraint("description != ''", name="ck_theme_instance_non_empty_desc"),
        UniqueConstraint("theme_id", "entry_id", name="uq_theme_instance_theme_entry"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Foreign keys ---
    theme_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("themes.id", ondelete="CASCADE"), nullable=False
    )
    entry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entries.id", ondelete="CASCADE"), nullable=False
    )

    # --- Relationships ---
    theme: Mapped["Theme"] = relationship("Theme", back_populates="instances")
    entry: Mapped["Entry"] = relationship("Entry", back_populates="theme_instances")

    # --- Computed properties ---
    @property
    def theme_name(self) -> str:
        """Get the name of the theme."""
        return self.theme.name if self.theme else ""

    @property
    def description_preview(self) -> str:
        """Get truncated description for display (max 100 chars)."""
        if len(self.description) <= 100:
            return self.description
        return f"{self.description[:97]}..."

    def __repr__(self) -> str:
        return f"<ThemeInstance(id={self.id}, theme_id={self.theme_id}, entry_id={self.entry_id})>"

    def __str__(self) -> str:
        return f"{self.theme_name}: {self.description_preview}"
