#!/usr/bin/env python3
"""
entities.py
-----------
Entity models for the Palimpsest database.

This module contains person and metadata entity models:

Models:
    - Person: People mentioned in journal entries
    - Tag: Keyword tags for categorization
    - Theme: Thematic elements across entries

These entities are linked to entries via many-to-many relationships
and may also be linked to scenes, threads, and other analysis elements.

Design:
    - Person: alias is nullable indexed field (unique)
    - Tag: simple name field (no category hierarchy)
    - Theme: standalone entity for thematic analysis
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import unicodedata
from datetime import date
from typing import TYPE_CHECKING, List, Optional

# --- Third party imports ---
from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

# --- Local imports ---
from .associations import (
    entry_people,
    entry_tags,
    entry_themes,
    scene_people,
    thread_people,
)
from .base import Base, SoftDeleteMixin
from .enums import RelationType

if TYPE_CHECKING:
    from .analysis import Scene, Thread
    from .core import Entry
    from .manuscript import PersonCharacterMap


class Person(Base, SoftDeleteMixin):
    """
    A person mentioned in journal entries.

    Represents real people who appear in journal entries, scenes,
    and threads. Supports multiple aliases for flexible naming.

    Attributes:
        id: Primary key
        name: First/given name
        lastname: Last/family name (optional)
        disambiguator: Context tag for same-name people with unknown lastnames
        slug: Unique identifier for exports (name_lastname or name_disambiguator)
        relation_type: Type of relationship (family, friend, romantic, etc.)

    Relationships:
        aliases: O2M with PersonAlias (lookup names)
        entries: M2M with Entry (entries where person is mentioned)
        scenes: M2M with Scene (scenes where person appears)
        threads: M2M with Thread (threads involving person)
        character_mappings: O2M with PersonCharacterMap (manuscript)

    Notes:
        - slug is unique and used for wiki filenames, YAML keys, URLs
        - Format: words separated by `-`, fields separated by `_`
        - Examples: `louis_collins`, `sophie_the-accountant`, `maria-jose_castro`
    """

    __tablename__ = "people"
    __table_args__ = (
        CheckConstraint("name != ''", name="ck_person_non_empty_name"),
        Index("ix_people_name", "name"),
    )

    # --- Primary fields ---
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    lastname: Mapped[Optional[str]] = mapped_column(String(100))
    disambiguator: Mapped[Optional[str]] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    relation_type: Mapped[Optional[RelationType]] = mapped_column(
        SQLEnum(RelationType, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )

    # --- Static methods ---
    @staticmethod
    def generate_slug(
        name: str,
        lastname: Optional[str] = None,
        disambiguator: Optional[str] = None,
    ) -> str:
        """
        Generate a unique slug from name components.

        Format: words separated by `-`, fields separated by `_`
        Priority: lastname over disambiguator (lastname wins if both present)

        Args:
            name: First/given name (required)
            lastname: Last/family name (optional)
            disambiguator: Context tag (optional, used if no lastname)

        Returns:
            Slug string, e.g., 'maria-jose_castro', 'sophie_the-accountant'
        """
        def slugify(text: str) -> str:
            """Convert text to slug format (lowercase, accents removed, spaces to hyphens)."""
            text = text.lower().strip()
            # Normalize accents/diacritics
            normalized = unicodedata.normalize("NFD", text)
            without_accents = "".join(
                c for c in normalized if unicodedata.category(c)[0] != "M"
            )
            # Replace spaces with hyphens
            return without_accents.replace(" ", "-")

        name_slug = slugify(name)

        if lastname:
            return f"{name_slug}_{slugify(lastname)}"
        elif disambiguator:
            return f"{name_slug}_{slugify(disambiguator)}"
        else:
            return name_slug

    # --- Relationships ---
    aliases: Mapped[List["PersonAlias"]] = relationship(
        "PersonAlias", back_populates="person", cascade="all, delete-orphan"
    )
    entries: Mapped[List["Entry"]] = relationship(
        "Entry", secondary=entry_people, back_populates="people"
    )
    scenes: Mapped[List["Scene"]] = relationship(
        "Scene", secondary=scene_people, back_populates="people"
    )
    threads: Mapped[List["Thread"]] = relationship(
        "Thread", secondary=thread_people, back_populates="people"
    )
    character_mappings: Mapped[List["PersonCharacterMap"]] = relationship(
        "PersonCharacterMap", back_populates="person"
    )

    # --- Computed properties ---
    @property
    def display_name(self) -> str:
        """Get display name (full name or just first name)."""
        if self.lastname:
            return f"{self.name} {self.lastname}"
        return self.name

    @property
    def primary_alias(self) -> Optional[str]:
        """Get the first alias if any exist."""
        return self.aliases[0].alias if self.aliases else None

    @property
    def lookup_key(self) -> str:
        """Get the key used for lookups (the slug)."""
        return self.slug

    @property
    def entry_count(self) -> int:
        """Number of entries mentioning this person."""
        return len(self.entries)

    @property
    def scene_count(self) -> int:
        """Number of scenes where person appears."""
        return len(self.scenes)

    @property
    def first_appearance(self) -> Optional[date]:
        """Earliest entry date where person was mentioned."""
        if not self.entries:
            return None
        return min(entry.date for entry in self.entries)

    @property
    def last_appearance(self) -> Optional[date]:
        """Most recent entry date where person was mentioned."""
        if not self.entries:
            return None
        return max(entry.date for entry in self.entries)

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
        """Get privacy sensitivity level for manuscript purposes (0-5)."""
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
        known_names = [self.name.lower()]
        if self.lastname:
            known_names.append(self.lastname.lower())
            known_names.append(f"{self.name} {self.lastname}".lower())
        for alias_obj in self.aliases:
            known_names.append(alias_obj.alias.lower())
        return search_name in known_names

    def __repr__(self) -> str:
        alias_str = self.primary_alias or "none"
        return f"<Person(id={self.id}, name='{self.display_name}', alias={alias_str})>"

    def __str__(self) -> str:
        return self.display_name


class PersonAlias(Base):
    """
    An alias for a person.

    Stores alternative names/nicknames for a person, enabling lookup
    by any known name. Aliases are NOT globally unique - multiple people
    can share the same alias (e.g., "Therapist" for different therapists).

    Attributes:
        id: Primary key
        person_id: Foreign key to Person
        alias: The alias string

    Relationships:
        person: The Person this alias belongs to
    """

    __tablename__ = "person_aliases"
    __table_args__ = (
        Index("ix_person_aliases_alias", "alias"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), nullable=False)
    alias: Mapped[str] = mapped_column(String(100), nullable=False)

    # --- Relationships ---
    person: Mapped["Person"] = relationship("Person", back_populates="aliases")

    def __repr__(self) -> str:
        return f"<PersonAlias(id={self.id}, alias='{self.alias}', person_id={self.person_id})>"

    def __str__(self) -> str:
        return self.alias


class Tag(Base):
    """
    Keyword tag for categorizing entries.

    Tags are simple labels applied to journal entries for
    organization and filtering.

    Attributes:
        id: Primary key
        name: Tag name (unique)

    Relationships:
        entries: M2M with Entry (entries with this tag)
    """

    __tablename__ = "tags"
    __table_args__ = (CheckConstraint("name != ''", name="ck_tag_non_empty_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )

    # --- Relationships ---
    entries: Mapped[List["Entry"]] = relationship(
        "Entry", secondary=entry_tags, back_populates="tags"
    )

    # --- Computed properties ---
    @property
    def usage_count(self) -> int:
        """Number of entries using this tag."""
        return len(self.entries)

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

    def __repr__(self) -> str:
        return f"<Tag(id={self.id}, name='{self.name}')>"

    def __str__(self) -> str:
        return self.name


class Theme(Base):
    """
    Thematic element across entries.

    Themes represent recurring thematic patterns or concepts
    that span multiple journal entries.

    Attributes:
        id: Primary key
        name: Theme name (unique)

    Relationships:
        entries: M2M with Entry (entries containing this theme)
    """

    __tablename__ = "themes"
    __table_args__ = (CheckConstraint("name != ''", name="ck_theme_non_empty_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(200), unique=True, nullable=False, index=True
    )

    # --- Relationships ---
    entries: Mapped[List["Entry"]] = relationship(
        "Entry", secondary=entry_themes, back_populates="themes"
    )

    # --- Computed properties ---
    @property
    def usage_count(self) -> int:
        """Number of entries with this theme."""
        return len(self.entries)

    @property
    def first_used(self) -> Optional[date]:
        """Date when theme first appeared."""
        if not self.entries:
            return None
        return min(entry.date for entry in self.entries)

    @property
    def last_used(self) -> Optional[date]:
        """Date when theme last appeared."""
        if not self.entries:
            return None
        return max(entry.date for entry in self.entries)

    def __repr__(self) -> str:
        return f"<Theme(id={self.id}, name='{self.name}')>"

    def __str__(self) -> str:
        return self.name
