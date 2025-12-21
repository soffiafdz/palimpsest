"""
Entity Models
--------------

Models for people, aliases, and tags in the journal.

Models:
    - Person: People mentioned in journal entries
    - Alias: Alternative names for people
    - TagCategory: Semantic categories for grouping tags
    - Tag: Simple keyword tags for categorizing entries

These models track who appears in the journal and how entries are categorized.
"""

# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date
from typing import TYPE_CHECKING, Any, Dict, List, Optional

# --- Third party imports ---
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

# --- Local imports ---
from .associations import (
    entry_aliases,
    entry_people,
    entry_tags,
    event_people,
    moment_people,
)
from .base import Base, SoftDeleteMixin
from .enums import RelationType

if TYPE_CHECKING:
    from .core import Entry
    from .creative import Event
    from .geography import Moment
    from ..models_manuscript import ManuscriptPerson


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
        notes: Editorial notes about this person (for wiki curation)

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
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ---- Relationships ----
    aliases: Mapped[List["Alias"]] = relationship(
        "Alias", back_populates="person", cascade="all, delete-orphan"
    )
    moments: Mapped[List["Moment"]] = relationship(
        "Moment", secondary=moment_people, back_populates="people"
    )
    events: Mapped[List["Event"]] = relationship(
        "Event", secondary=event_people, back_populates="people"
    )
    entries: Mapped[List["Entry"]] = relationship(
        "Entry", secondary=entry_people, back_populates="people"
    )
    manuscript: Mapped[Optional["ManuscriptPerson"]] = relationship(
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
        """Total number of appearances (explicit moments)."""
        return len(self.moments)

    @property
    def event_count(self) -> int:
        """Number of events this person is involved in."""
        return len(self.events)

    @property
    def first_appearance(self) -> Optional[date]:
        """Earliest date this person was mentioned."""
        moment_dates = [m.date for m in self.moments]
        return min(moment_dates) if moment_dates else None

    @property
    def last_appearance(self) -> Optional[date]:
        """Most recent date this person was mentioned."""
        moment_dates = [m.date for m in self.moments]
        return max(moment_dates) if moment_dates else None

    @property
    def mention_timeline(self) -> List[Dict[str, Any]]:
        """
        Complete timeline of mentions with context.

        Returns:
            List of dicts with keys: date, source ('entry'|'moment'), context
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

        # Add explicit moments
        for moment in self.moments:
            timeline.append(
                {
                    "date": moment.date,
                    "source": "moment",
                    "context": moment.context,
                    "moment_id": moment.id,
                }
            )

        # Sort by date
        timeline.sort(key=lambda x: x["date"])
        return timeline

    @property
    def mention_frequency(self) -> Dict[str, int]:
        """
        Calculate mention frequency by year-month.
        Uses all mentions (from moments).

        Returns:
            Dictionary mapping YYYY-MM strings to mention counts
        """
        frequency: Dict[str, int] = {}
        for moment in self.moments:
            year_month = moment.date.strftime("%Y-%m")
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
    person: Mapped["Person"] = relationship("Person", back_populates="aliases")
    entries: Mapped[List["Entry"]] = relationship(
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


class TagCategory(Base):
    """
    Semantic categories for grouping tags.

    Provides a hierarchical organization for tags based on narrative
    analysis categories. Categories are predefined based on the
    narrative analysis taxonomy.

    Attributes:
        id: Primary key
        name: Category name (unique, e.g., "Digital Surveillance", "Writing/Poetry")
        description: Optional description of what this category encompasses

    Relationships:
        tags: One-to-many with Tag (tags in this category)

    Computed Properties:
        tag_count: Number of tags in this category
        entry_count: Total entries across all tags in category

    Predefined Categories (24):
        Digital Surveillance, Photography, AI/Technology, Writing/Poetry,
        Medication, Crisis/Suicidality, Food/Diet, Academia, Sleep/Insomnia,
        Depression/Grief, Literature, Identity, Therapy, Dysphoria/Body,
        Obsession/Control, Meta-narrative, Mania/Bipolar, Music,
        Rejection/Ghosting, Intimacy, Alcohol, Messaging, Anxiety/Panic,
        Film/TV, Dating Apps, Romance/Dating, Sexual, Smoking/Drugs,
        Tarot/Divination, Transition, Relics/Objects, Physical Health,
        Isolation, Hygiene
    """

    __tablename__ = "tag_categories"
    __table_args__ = (
        CheckConstraint("name != ''", name="ck_tag_category_non_empty_name"),
    )

    # ---- Primary fields ----
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ---- Relationship ----
    tags: Mapped[List["Tag"]] = relationship("Tag", back_populates="category")

    # ---- Computed properties ----
    @property
    def tag_count(self) -> int:
        """Number of tags in this category."""
        return len(self.tags)

    @property
    def entry_count(self) -> int:
        """Total entries across all tags in this category."""
        entries = set()
        for tag in self.tags:
            entries.update(tag.entries)
        return len(entries)

    @property
    def all_tag_names(self) -> List[str]:
        """Get all tag names in this category."""
        return [tag.tag for tag in self.tags]

    def __repr__(self) -> str:
        return f"<TagCategory(id={self.id}, name='{self.name}')>"

    def __str__(self) -> str:
        return f"TagCategory '{self.name}' ({self.tag_count} tags)"


class Tag(Base):
    """
    Keyword tags for entries with optional category grouping.

    Provides a flexible tagging system for categorizing and
    searching journal entries. Tags can optionally belong to
    a semantic category for hierarchical organization.

    Attributes:
        id: Primary key
        tag: The tag text (unique)
        category_id: Optional FK to TagCategory

    Relationships:
        category: Many-to-one with TagCategory (optional)
        entries: Many-to-many with Entry
    """

    __tablename__ = "tags"
    __table_args__ = (CheckConstraint("tag != ''", name="ck_non_empty_tag"),)

    # ---- Primary fields ----
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tag: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tag_categories.id", ondelete="SET NULL"), nullable=True
    )

    # ---- Relationships ----
    category: Mapped[Optional["TagCategory"]] = relationship(
        "TagCategory", back_populates="tags"
    )
    entries: Mapped[List["Entry"]] = relationship(
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
    def chronological_entries(self) -> List["Entry"]:
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
