#!/usr/bin/env python3
"""
manuscript.py
-------------
Manuscript domain models for the Palimpsest database.

This module contains models for manuscript structure and source tracking:

Structure Models:
    - Part: Book sections (optional)
    - Chapter: Discrete units of the manuscript (prose, vignette, poem)
    - Character: Fictional characters in the manuscript
    - PersonCharacterMap: Real person → fictional character mapping

Source Tracking Models:
    - ManuscriptScene: A narrative unit in the manuscript
    - ManuscriptSource: Links manuscript scene to source material
    - ManuscriptReference: How a chapter uses a referenced work

Design:
    - Manuscript structure is separate from journal analysis
    - Source tracking links manuscript to journal scenes/entries/threads
    - Characters map to real people with contribution types
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from typing import TYPE_CHECKING, List, Optional

# --- Third party imports ---
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

# --- Local imports ---
from .associations import chapter_arcs, chapter_characters, chapter_poems
from .base import Base
from .enums import (
    ChapterStatus,
    ChapterType,
    ContributionType,
    ReferenceMode,
    SceneOrigin,
    SceneStatus,
    SourceType,
)

if TYPE_CHECKING:
    from .analysis import Arc, Scene, Thread
    from .core import Entry
    from .creative import Poem, ReferenceSource
    from .entities import Person


class Part(Base):
    """
    Book section (optional).

    Parts are optional organizational units that group chapters.

    Attributes:
        id: Primary key
        number: Part number (nullable until ordered)
        title: Part title (optional)

    Relationships:
        chapters: One-to-many with Chapter
    """

    __tablename__ = "parts"
    __table_args__ = (
        UniqueConstraint("number", name="uq_part_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    number: Mapped[Optional[int]] = mapped_column(Integer)
    title: Mapped[Optional[str]] = mapped_column(String(255))

    # --- Relationship ---
    chapters: Mapped[List["Chapter"]] = relationship(
        "Chapter", back_populates="part"
    )

    # --- Computed properties ---
    @property
    def chapter_count(self) -> int:
        """Number of chapters in this part."""
        return len(self.chapters)

    @property
    def display_name(self) -> str:
        """Get display name for this part."""
        if self.title:
            if self.number:
                return f"Part {self.number}: {self.title}"
            return self.title
        if self.number:
            return f"Part {self.number}"
        return f"Part (id={self.id})"

    def __repr__(self) -> str:
        return f"<Part(id={self.id}, number={self.number}, title='{self.title}')>"

    def __str__(self) -> str:
        return self.display_name


class Chapter(Base):
    """
    A discrete unit of the manuscript.

    Chapters can be prose, vignettes, or poems. Each chapter
    has a type and status, and can optionally belong to a part.

    Attributes:
        id: Primary key
        title: Chapter title
        number: Chapter number (nullable until ordered, editable)
        part_id: Foreign key to Part (optional)
        type: Chapter type (prose, vignette, poem)
        status: Chapter status (draft, revised, final)
        content: Content for short pieces (poems, vignettes)
        draft_path: Path to draft file for longer prose

    Relationships:
        part: Many-to-one with Part (optional)
        poems: M2M with Poem (poems included/referenced)
        characters: M2M with Character
        arcs: M2M with Arc
        scenes: One-to-many with ManuscriptScene (source material)
        references: One-to-many with ManuscriptReference
    """

    __tablename__ = "chapters"
    __table_args__ = (
        CheckConstraint("title != ''", name="ck_chapter_non_empty_title"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    number: Mapped[Optional[int]] = mapped_column(Integer)
    part_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("parts.id", ondelete="SET NULL")
    )
    type: Mapped[ChapterType] = mapped_column(
        SQLEnum(ChapterType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ChapterType.PROSE,
        index=True,
    )
    status: Mapped[ChapterStatus] = mapped_column(
        SQLEnum(ChapterStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ChapterStatus.DRAFT,
        index=True,
    )
    content: Mapped[Optional[str]] = mapped_column(Text)
    draft_path: Mapped[Optional[str]] = mapped_column(String(500))

    # --- Relationships ---
    part: Mapped[Optional["Part"]] = relationship("Part", back_populates="chapters")
    poems: Mapped[List["Poem"]] = relationship(
        "Poem", secondary=chapter_poems, backref="chapters"
    )
    characters: Mapped[List["Character"]] = relationship(
        "Character", secondary=chapter_characters, back_populates="chapters"
    )
    arcs: Mapped[List["Arc"]] = relationship(
        "Arc", secondary=chapter_arcs, backref="chapters"
    )
    scenes: Mapped[List["ManuscriptScene"]] = relationship(
        "ManuscriptScene", back_populates="chapter"
    )
    references: Mapped[List["ManuscriptReference"]] = relationship(
        "ManuscriptReference", back_populates="chapter", cascade="all, delete-orphan"
    )

    # --- Computed properties ---
    @property
    def type_display(self) -> str:
        """Get human-readable type name."""
        return self.type.display_name if self.type else "Unknown"

    @property
    def status_display(self) -> str:
        """Get human-readable status name."""
        return self.status.display_name if self.status else "Unknown"

    @property
    def scene_count(self) -> int:
        """Number of manuscript scenes in this chapter."""
        return len(self.scenes)

    @property
    def character_names(self) -> List[str]:
        """Get list of character names in this chapter."""
        return [c.name for c in self.characters]

    @property
    def has_content(self) -> bool:
        """Check if chapter has inline content."""
        return bool(self.content)

    @property
    def has_draft(self) -> bool:
        """Check if chapter has a draft file."""
        return bool(self.draft_path)

    def __repr__(self) -> str:
        return f"<Chapter(id={self.id}, title='{self.title}', type={self.type.value})>"

    def __str__(self) -> str:
        return self.title


class Character(Base):
    """
    A fictional character in the manuscript.

    Characters are fictional representations that may be based
    on real people. They track the manuscript's cast.

    Attributes:
        id: Primary key
        name: Character name
        description: Character description (optional)
        role: Character role (protagonist, love interest, etc.)
        is_narrator: Whether this character is the narrator

    Relationships:
        chapters: M2M with Chapter
        person_mappings: One-to-many with PersonCharacterMap
    """

    __tablename__ = "characters"
    __table_args__ = (
        CheckConstraint("name != ''", name="ck_character_non_empty_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    role: Mapped[Optional[str]] = mapped_column(String(100))
    is_narrator: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- Relationships ---
    chapters: Mapped[List["Chapter"]] = relationship(
        "Chapter", secondary=chapter_characters, back_populates="characters"
    )
    person_mappings: Mapped[List["PersonCharacterMap"]] = relationship(
        "PersonCharacterMap", back_populates="character", cascade="all, delete-orphan"
    )

    # --- Computed properties ---
    @property
    def chapter_count(self) -> int:
        """Number of chapters featuring this character."""
        return len(self.chapters)

    @property
    def based_on(self) -> List["Person"]:
        """Get all people this character is based on."""
        return [mapping.person for mapping in self.person_mappings if mapping.person]

    @property
    def primary_person(self) -> Optional["Person"]:
        """Get the primary person this character is based on."""
        for mapping in self.person_mappings:
            if mapping.contribution == ContributionType.PRIMARY:
                return mapping.person
        return None

    def __repr__(self) -> str:
        return f"<Character(id={self.id}, name='{self.name}')>"

    def __str__(self) -> str:
        return self.name


class PersonCharacterMap(Base):
    """
    Maps real people to fictional characters.

    Tracks how real people contribute to fictional characters
    with contribution type metadata.

    Attributes:
        id: Primary key
        person_id: Foreign key to Person
        character_id: Foreign key to Character
        contribution: Type of contribution (primary, composite, inspiration)
        notes: Additional notes (optional)

    Relationships:
        person: Many-to-one with Person
        character: Many-to-one with Character
    """

    __tablename__ = "person_character_map"
    __table_args__ = (
        UniqueConstraint("person_id", "character_id", name="uq_person_character_map"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False
    )
    character_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    contribution: Mapped[ContributionType] = mapped_column(
        SQLEnum(ContributionType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ContributionType.PRIMARY,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # --- Relationships ---
    person: Mapped["Person"] = relationship(
        "Person", back_populates="character_mappings"
    )
    character: Mapped["Character"] = relationship(
        "Character", back_populates="person_mappings"
    )

    # --- Computed properties ---
    @property
    def contribution_display(self) -> str:
        """Get human-readable contribution type."""
        return self.contribution.display_name if self.contribution else "Unknown"

    def __repr__(self) -> str:
        return f"<PersonCharacterMap(person_id={self.person_id}, character_id={self.character_id})>"

    def __str__(self) -> str:
        return f"{self.person.display_name} → {self.character.name} ({self.contribution_display})"


class ManuscriptScene(Base):
    """
    A narrative unit in the manuscript.

    Represents a scene in the manuscript that may be sourced
    from journal scenes, entries, threads, or external material.

    Attributes:
        id: Primary key
        name: Scene name
        description: Scene description (optional)
        chapter_id: Foreign key to Chapter (nullable = unassigned fragment)
        origin: How the scene was created (journaled, inferred, invented, composite)
        status: Inclusion status (fragment, draft, included, cut)
        notes: Additional notes (optional)

    Relationships:
        chapter: Many-to-one with Chapter (nullable)
        sources: One-to-many with ManuscriptSource
    """

    __tablename__ = "manuscript_scenes"
    __table_args__ = (
        CheckConstraint("name != ''", name="ck_ms_scene_non_empty_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    chapter_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("chapters.id", ondelete="SET NULL")
    )
    origin: Mapped[SceneOrigin] = mapped_column(
        SQLEnum(SceneOrigin, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SceneOrigin.JOURNALED,
        index=True,
    )
    status: Mapped[SceneStatus] = mapped_column(
        SQLEnum(SceneStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SceneStatus.FRAGMENT,
        index=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # --- Relationships ---
    chapter: Mapped[Optional["Chapter"]] = relationship(
        "Chapter", back_populates="scenes"
    )
    sources: Mapped[List["ManuscriptSource"]] = relationship(
        "ManuscriptSource", back_populates="manuscript_scene", cascade="all, delete-orphan"
    )

    # --- Computed properties ---
    @property
    def origin_display(self) -> str:
        """Get human-readable origin type."""
        return self.origin.display_name if self.origin else "Unknown"

    @property
    def status_display(self) -> str:
        """Get human-readable status."""
        return self.status.display_name if self.status else "Unknown"

    @property
    def is_assigned(self) -> bool:
        """Check if scene is assigned to a chapter."""
        return self.chapter_id is not None

    @property
    def source_count(self) -> int:
        """Number of sources for this scene."""
        return len(self.sources)

    def __repr__(self) -> str:
        return f"<ManuscriptScene(id={self.id}, name='{self.name}')>"

    def __str__(self) -> str:
        return self.name


class ManuscriptSource(Base):
    """
    Links manuscript scene to source material.

    Tracks where manuscript content comes from, supporting
    multiple source types (scene, entry, thread, external).

    Attributes:
        id: Primary key
        manuscript_scene_id: Foreign key to ManuscriptScene
        source_type: Type of source (scene, entry, thread, external)
        scene_id: Foreign key to Scene (if source_type=scene)
        entry_id: Foreign key to Entry (if source_type=entry)
        thread_id: Foreign key to Thread (if source_type=thread)
        external_note: External source description (if source_type=external)
        notes: Additional notes (optional)

    Relationships:
        manuscript_scene: Many-to-one with ManuscriptScene
        scene: Many-to-one with Scene (optional)
        entry: Many-to-one with Entry (optional)
        thread: Many-to-one with Thread (optional)
    """

    __tablename__ = "manuscript_sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    manuscript_scene_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("manuscript_scenes.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[SourceType] = mapped_column(
        SQLEnum(SourceType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )

    # Nullable FKs - only one populated based on source_type
    scene_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("scenes.id", ondelete="SET NULL")
    )
    entry_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("entries.id", ondelete="SET NULL")
    )
    thread_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("threads.id", ondelete="SET NULL")
    )
    external_note: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # --- Relationships ---
    manuscript_scene: Mapped["ManuscriptScene"] = relationship(
        "ManuscriptScene", back_populates="sources"
    )
    scene: Mapped[Optional["Scene"]] = relationship("Scene")
    entry: Mapped[Optional["Entry"]] = relationship("Entry")
    thread: Mapped[Optional["Thread"]] = relationship("Thread")

    # --- Computed properties ---
    @property
    def source_type_display(self) -> str:
        """Get human-readable source type."""
        return self.source_type.display_name if self.source_type else "Unknown"

    @property
    def source_reference(self) -> str:
        """Get reference string for the source."""
        if self.source_type == SourceType.SCENE and self.scene:
            return f"Scene: {self.scene.name}"
        elif self.source_type == SourceType.ENTRY and self.entry:
            return f"Entry: {self.entry.date_formatted}"
        elif self.source_type == SourceType.THREAD and self.thread:
            return f"Thread: {self.thread.name}"
        elif self.source_type == SourceType.EXTERNAL:
            return f"External: {self.external_note or 'N/A'}"
        return "Unknown source"

    def __repr__(self) -> str:
        return f"<ManuscriptSource(id={self.id}, type={self.source_type.value})>"

    def __str__(self) -> str:
        return self.source_reference


class ManuscriptReference(Base):
    """
    How a chapter uses a referenced work.

    Tracks intertextual references in manuscript chapters,
    linking to external sources.

    Attributes:
        id: Primary key
        chapter_id: Foreign key to Chapter
        source_id: Foreign key to ReferenceSource
        mode: How the reference is used (direct, indirect, thematic, etc.)
        content: Quote if direct reference (optional)
        notes: Additional notes (optional)

    Relationships:
        chapter: Many-to-one with Chapter
        source: Many-to-one with ReferenceSource
    """

    __tablename__ = "manuscript_references"
    __table_args__ = (
        UniqueConstraint("chapter_id", "source_id", name="uq_manuscript_reference_chapter_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reference_sources.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[ReferenceMode] = mapped_column(
        SQLEnum(ReferenceMode, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ReferenceMode.THEMATIC,
        index=True,
    )
    content: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # --- Relationships ---
    chapter: Mapped["Chapter"] = relationship("Chapter", back_populates="references")
    source: Mapped["ReferenceSource"] = relationship("ReferenceSource")

    # --- Computed properties ---
    @property
    def mode_display(self) -> str:
        """Get human-readable mode name."""
        return self.mode.display_name if self.mode else "Unknown"

    @property
    def content_preview(self) -> Optional[str]:
        """Get truncated content for display (max 100 chars)."""
        if self.content:
            if len(self.content) <= 100:
                return self.content
            return f"{self.content[:97]}..."
        return None

    def __repr__(self) -> str:
        return f"<ManuscriptReference(chapter_id={self.chapter_id}, source_id={self.source_id})>"

    def __str__(self) -> str:
        return f"{self.source.title} ({self.mode_display})"
