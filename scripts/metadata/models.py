#!/usr/bin/env python3
"""
models.py
-------------------
Defines the SQLAlchemy ORM models for the Palimpsest metadata database.

Each class represents a table in the SQLite database.
Relationships and many-to-many association tables are defined here.

Tables:
    - Entry:        journal entry metadata (from Markdown frontmatter)
    - Epigraph:     metadata of the introductory epigraphs of the entries
    - Event:        Overarching thematic arcs/phases
    - Location:     geographic placement of the entries
    - Notes:        qualitative notes for the entries
    - Person:       people mentioned in the entries
    - Reference:    dates referenced in the entries
    - Tag:          simple tags
    - Theme:        thematic tags

Notes
==============
- Each class represents a table in the SQLite DB.
- Relationships (many-to-many association tables) are defined here.
- Updates (migrations) should be handled by Alembic.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
# from datetime import datetime
from typing import List, Optional, Dict

# --- Third party ---
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    func,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    # relationship,
)


# ----- Base ORM class -----
class Base(DeclarativeBase):
    """
    Base class for all ORM models.
    Provides access to the metadata and acts as the declarative base.
    """

    pass


# ----- Association tables -----
entry_themes = Table(
    "entry_themes",
    Base.metadata,
    Column(
        "entry_id",
        Integer,
        ForeignKey("entries.id"),
        ondelete="CASCADE",
        primary_key=True,
    ),
    Column("theme_id", Integer, ForeignKey("themes.id"), primary_key=True),
)

entry_tags = Table(
    "entry_tag",
    Base.metadata,
    Column("entry_id", Integer, ForeignKey("entries.id"), primary_key=True),
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
    applied_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    description: Mapped[Optional[str]] = mapped_column(Text)


# ----- Models -----
class Entry(Base):
    """
    Journal entry metadata and relationships.

    Attributes:
        id (int):           Primary key.
        file_path (str)     Path to the Markdown file.
        date (str):         ISO-format date of the journal entry.
        word_count (int)
        reading_time (float)
        status (str):       Curation status (e.g., unreviewed, source, discard).
        excerpted (bool):   Whether content is excerpted for manuscript.
        epigraph (str):
        notes (str)
        file_hash (str):    Hash of the file content.
        created_at (datetime)
        updated_at (datetime)
        locations, people, references, events, themes, tags: relationships
    """

    __tablename__ = "entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # file_path: Mapped[int] = mapped_column(String, uniqe)
