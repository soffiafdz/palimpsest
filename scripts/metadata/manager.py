#!/usr/bin/env python3
"""
-------------------
Database manager for the Palimpsest medatata system.

Provides the PalimpsestDB class for interacting with the SQLite database.
Handles:
    - Initialization of the database engine and sessionmaker
    - CRUD operations for all ORM models
    - Handle queries and convenience methods
    - Relationship management for:
      locations, people, references, events, poems, themes, tags
    - Type-safe and timezone-aware handling of datetime fields
    - Backup and repopulation of the database

Notes
==============
- Migrations are handled externally via Alembic
- All datetime fields are UTC-aware
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
# import json
# import hashlib
# import warnings
import shutil

# from datetime import date, datetime, timezone
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

# --- Third party ---
# import yaml
from alembic.config import Config
from alembic import command

from alembic.runtime.migration import MigrationContext

# from alembic.operations import Operations
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

# from sqlalchemy.sql import func

# --- Local imports ---
from scripts.utils import md, fs
from scripts.metadata.models import (
    Base,
    Entry,
    MentionedDate,
    Location,
    Person,
    Alias,
    Reference,
    ReferenceType,
    Event,
    Poem,
    PoemVersion,
    Tag,
)

# from sqlalchemy import (
#     create_engine,
#     Column,
#     Integer,
#     String,
#     Text,
#     Boolean,
#     Float,
#     DateTime,
#     ForeignKey,
#     Table,
#     Index,
#     UniqueConstraint
# )
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.orm import sessionmaker, relationship, Session

# import os
# import json
# from typing import Dict, List, Any, Optional, Tuple


T = TypeVar("T", bound=Base)


# ----- Manager -----
class PalimpsestDB:
    """
    Main database manager for the Palimpsest metadata database.

    Attributes:
        - db_path (str | Path): Filesystem path to the SQLite database file.
        - alembic_dir (str | Path): Filesystem path to the Alembic directory.
        - engine (Engine): SQLAlchemy engine instance.
        - SessionLocal (sessionmaker): SQLAlchemy session factory.

    Handles:
        - Connection/session management
        - Database initialization
        - Migrations / schema versioning
        - Entry updates from Markdown files
        - Relationship management
        - Directory synchronization
        - Backups

    Usage:
        db = PalimpsestDB("~/path/to/palimpsest.db")
        with db.session() as session:
            entries = db.get_all_entries(session)
    """

    # --- Initialization ---
    def __init__(
        self, db_path: Union[str, Path], alembic_dir: Union[str, Path]
    ) -> None:
        """
        Initialize database engine and session factory.

        Args:
            db_path (str | Path): Path to the SQLite  file.
            alembic_dir (str | Path): Path to the Alembic directory.
        """
        self.db_path: Path = Path(db_path).expanduser().resolve()
        self.alembic_dir = Path(alembic_dir).expanduser().resolve()
        self.engine: Engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            future=True,
        )
        self.SessionLocal: sessionmaker = sessionmaker(
            bind=self.engine,
            autoflush=True,
            expire_on_commit=False,
            future=True,
        )

        # Initialize Alembic configuration
        self.alembic_cfg: Config = self._setup_alembic()

        # Initialize databse
        self.init_database()

    # --- Session / connection utils ---
    def get_session(self) -> Session:
        """
        Create and return a new SQLAlchemy session.

        Returns:
            Session: A new database session.
        """
        return self.SessionLocal()

    # --- Alembic ---
    def _setup_alembic(self) -> Config:
        """
        Setup Alembic configuration

        Returns:
            Config
        """
        alembic_cfg: Config = Config()

        # Set the script location (where migration files are stored)
        alembic_cfg.set_main_option("script_location", str(self.alembic_dir))

        # Set the database URL
        alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{self.db_path}")

        # Configure logging
        alembic_cfg.set_main_option(
            "file_template",
            "%%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d_%%(slug)s",
        )

        return alembic_cfg

    def init_alembic(self) -> None:
        """
        Initialize Alembic in the project directory.

        Actions:
            Creates Alembic directory with standard structure
            Updates alembic/eng.py to import Palimpsest Base metadata
            Prints instructions for first migration

        Returns:
            None
        """
        if not self.alembic_dir.is_dir():
            print(f"Initializing Alembic in {self.alembic_dir}...")
            command.init(self.alembic_cfg, str(self.alembic_dir))

            # Update the generated alembic/env.py to use models
            self._update_alembic_env()

            # TODO: This won't be here. Figure out where it goes.
            print("Alembic initialized. You can now create your first migration.")
            print("Run: python journal_db.py create_migration 'Initial schema'")
        else:
            print(f"Alembic already initialized in {self.alembic_dir}")

    def _update_alembic_env(self) -> None:
        """
        Update the generated alembic/env.py to import Palimpsest models.

        Returns:
            None
        """
        env_path: Path = self.alembic_dir / "env.py"

        if env_path.exists():
            content: str = env_path.read_text(encoding="utf-8")

            import_line = "from models import Base\n"
            target_metadata_line = "target_metadata = Base.metadata"

            # Replace the target_medatara = None line
            updated_content: str = content.replace(
                "target_metadata = None", f"{import_line}\n{target_metadata_line}"
            )

            # Write the updated file back
            env_path.write_text(updated_content, encoding="utf-8")
            print("Updated alembic/env.py to use journal models")

    # --- Migrations ---
    def create_migration(self, message: str) -> None:
        """
        Create a new Alembic migration file for the current database schema.

        Args:
            message (str): Description of the migration.

        Raises:
            Prints an error message if migration creation fails.

        Returns:
            None
        """
        try:
            command.revision(self.alembic_cfg, message=message, autogenerate=True)
            print(f"Created migration: {message}")
        except Exception as e:
            print(f"Error creating migration: {e}")

    def upgrade_database(self, revision: str = "head") -> None:
        """
        Upgrade the database schema to the specified Alembic revision.

        Args:
            revision (str, optional):
                The target revision to upgrade to.
                Defaults to 'head' (latest revision).

        Raises:
            Prints an error message if the upgrade fails.

        Returns:
            None
        """
        try:
            command.upgrade(self.alembic_cfg, revision)
            print(f"Database upgraded to {revision}")
        except Exception as e:
            print(f"Error upgrading database: {e}")

    def downgrade_database(self, revision: str) -> None:
        """
        Downgrade the database schema to a specified Alembic revision.

        Args:
            revision (str): The target revision to downgrade to.

        Raises:
            Prints an error message if the downgrade fails.

        Returns:
            None
        """
        try:
            command.downgrade(self.alembic_cfg, revision)
            print(f"Database downgraded to {revision}")
        except Exception as e:
            print(f"Error downgrading database: {e}")

    def get_migration_history(self) -> Dict[str, Optional[str]]:
        """
        Get the current migration status of the database.

        Returns:
            Dictionary with keys:
                - 'current_revision' (str | None):
                  Current Alembic revision of the database.
                - 'status' (str):
                  Either 'up_to_date' or 'needs_migration'.
                - 'error' (str, optional):
                  Present if an exception occurred.
        """
        try:
            # Get current revision
            with self.engine.connect() as conn:
                context = MigrationContext.configure(conn)
                current_rev = context.get_current_revision()

            return {
                "current_revision": current_rev,
                "status": "up_to_date" if current_rev else "needs_migration",
            }
        except Exception as e:
            return {"error": str(e)}

    # --- Init DB ---
    def init_database(self) -> None:
        """
        Initialize database - create tables if needed and run migrations.

        Actions:
            Checks if the database is fresh (no tables)
            If fresh,
                creates all tables from the ORM models
                stamps the Alembic revision to head
            If not,
                runs pending migrations to update schema

        Returns:
            None
        """
        # Check if this is a fresh database
        with self.get_session() as _:
            inspector = self.engine.dialect.get_table_names(self.engine.connect())
            is_fresh_db: bool = len(inspector) == 0

        if is_fresh_db:
            # Create all tables for fresh database
            Base.metadata.create_all(bind=self.engine)

            # Stamp with current revision (so Alembic knows the current state)
            try:
                command.stamp(self.alembic_cfg, "head")
                print("Fresh database created and stamped with current revision")
            except Exception as e:
                print(f"Note: Could not stamp database (run init_alembic first): {e}")
        else:
            # Run pending migrations
            self.upgrade_database()

    # --- Backup ---
    def backup_database(self, backup_suffix: Optional[str] = None) -> str:
        """
        Create a backup copy of the database.

        Args:
            backup_suffix (Optional[str]): Suffix to append to the backup file.

        Returns:
            str: Path to the backup database file.
        """
        if backup_suffix is None:
            backup_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")

        backup_path = f"{self.db_path}.backup_{backup_suffix}"
        shutil.copy2(self.db_path, backup_path)
        print(f"[Backup] Database backed up to: {backup_path}")
        return backup_path

    # --- Clear everything ---
    def clear_entries(self):
        """Clear all entry data."""
        with self.get_session() as session:
            try:
                session.query(Entry).delete()
                session.commit()
                print("Cleared existing entries for repopulation.")
            except Exception as e:
                session.rollback()
                print(f"Error clearing entries: {e}")

    # --- Lookup helpers ---
    def _get_lookup_item(
        self,
        session: Session,
        model_class: Type[T],
        lookup_fields: Dict[str, Any],
    ) -> Optional[T]:
        """
        Get an existing item from a lookup table.

        Args:
            session (Session): SQLAlchemy session.
            model_class (type[Base]): ORM models class to query.
            lookup_fields: Dictionary of field_name: value to filter.

        Returns:
            ORM instance of the same type of the one being queried

        Notes:
            For string-based columns, `value` should be a str
            For dates or other types, pass the appropriate Python types
        """
        query = session.query(model_class).filter_by(**lookup_fields)
        obj = query.first()
        if obj:
            return obj
        return None

    # TODO: Make this specific for simpler stuff?
    def _get_or_create_lookup_item(
        self,
        session: Session,
        model_class: Type[T],
        lookup_fields: Dict[str, Any],
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> T:
        """
        Get an existing item from a lookup table, or create it if it doesn't exist.

        Args:
            session (Session): SQLAlchemy session.
            model_class (type[Base]): ORM models class to query or create.
            lookup_fields: Dictionary of field_name: value to filter/create.
            extra_fielts: Additional fields for new object creation.

        Returns:
            ORM instance of the same type of the one being queried

        Notes:
            For string-based columns, `value` should be a str
            For dates or other types, pass the appropriate Python types
            The new object is added to the session and flushed immediately
        """
        obj: Optional[T] = self._get_lookup_item(session, model_class, lookup_fields)
        if obj:
            return obj

        # Prepare fields for creation
        fields = lookup_fields.copy()
        if extra_fields:
            fields.update(extra_fields)

        # Create object
        obj = model_class(**fields)
        session.add(obj)
        session.flush()
        return obj

    # TODO: Make this specific for simpler stuff?
    def _append_lookup(
        self,
        session: Session,
        entry_list: List[T],
        model_class: Type[T],
        lookup_fields: Dict[str, Any],
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Retrieve or create a lookup object and append it to a relationship list.

        Prevents duplicate entries in the relationship.

        Args:
            session (Session): Active SQLAlchemy session.
            entry_list (List[T]): Relationship list to append the object to.
            model_class (Type[T]): The lookup table class (e.g., Person, Theme, Tag).
            lookup_fields: Dictionary of field_name: value to filter/create.
            extra_fields: Additional fields for new object creation.

        Behaviour:
            Skips appending if:
                any value in lookup_fields is None
                an object with the same lookup_fields exists in entry_list
            Gets or creates the object and appends it
            extra_fields are only applied when creating a new object

        Returns:
            None
        """
        if any(value is None for value in lookup_fields.values()):
            return

        for obj in entry_list:
            if all(getattr(obj, k) == v for k, v in lookup_fields.items()):
                return

        if extra_fields is None:
            extra_fields = {}

        obj = self._get_or_create_lookup_item(
            session, model_class, lookup_fields, extra_fields
        )

        entry_list.append(obj)

    # --- Table creation ---
    def create_entry(self, session: Session, metadata: Dict[str, Any]) -> Entry:
        """
        Create a new Entry in the database with its associated relationships.

        This function does NOT handle file I/O or Markdown parsing. It assumes
        that `metadata` is already normalized (all dates as `datetime.date`,
        people, tags, events, etc. as strings or dicts).

        Args:
            session (Session): Active SQLAlchemy session
            metadata (Dict[str, Any]): Normalized metadata for the entry.
                Required keys:
                    - date (str | datetime.date)
                    - file_path (str)
                Optional keys:
                    - file_hash (str)
                    - word_count (int|str)
                    - reading_time (float|str)
                    - epigraph (str)
                    - notes (str)
                Relationship keys:
                    - dates (List[str|date|dict|MentionedDate], optional)
                    - locations (List[str|dict|Location], optional)
                    - people (List[str|dict|Person], optional)
                    - references (List[str|dict|Reference], optional)
                    - events (List[str|dict|Event], optional)
                    - poems (List[str|dict|Poem], optional
                    - tags (List[str|dict|Tag], optional)
        Returns:
            Entry: The newly created Entry ORM object.

        Raises:
            ValueError: if required fields are missing or invalid
        """
        # --- Required fields ---
        if "date" not in metadata or not metadata["date"]:
            raise ValueError("Entry creation requires 'date'")

        if "file_path" not in metadata or not metadata["file_path"]:
            raise ValueError("Entry creation requires 'file_path'")

        parsed_date = md.parse_date(metadata["date"])
        if not parsed_date:
            raise ValueError(f"Invalid 'date' value: {metadata['date']}")

        file_path = md.normalize_str(metadata.get("file_path"))
        if not file_path:
            raise ValueError(f"Invalid 'file_path' value: {metadata['file_path']}")

        # --- If hash doesn't exist, create it --
        file_hash = md.normalize_str(metadata.get("file_hash"))
        if not file_hash:
            file_hash = fs.get_file_hash(file_path)

        # --- Core entry data ---
        entry = Entry(
            date=parsed_date,
            file_path=file_path,
            file_hash=file_hash,
            word_count=md.safe_int(metadata.get("word_count")),
            reading_time=md.safe_float(metadata.get("reading_time")),
            epigraph=md.normalize_str(metadata.get("epigraph")),
            notes=md.normalize_str(metadata.get("notes")),
        )
        session.add(entry)
        session.flush()

        # --- Relationships ---
        self.update_entry_relationships(session, entry, metadata)

        # TODO: Remove commit??
        # --- Commit ---
        session.commit()
        return entry

    def create_location(self, session: Session, metadata: Dict[str, Any]) -> Location:
        """
        Create a new Location in the database with its associated relationships.

        This function does NOT handle file I/O or Markdown parsing. It assumes
        that `metadata` is already normalized (all dates as `datetime.date`,
        people, tags, events, etc. as strings or dicts).

        Args:
            session (Session): Active SQLAlchemy session
            metadata (Dict[str, Any]): Normalized metadata for the entry.
                Required key:
                    - name (str)
                Optional key:
                    - full_name (str)
                Relationship key:
                    - entries (List[str|date|dict|Entry], optional)

        Returns:
            Location: The newly created Location ORM object.

        Raises:
            ValueError: if required field is missing or invalid
        """
        # --- Required fields ---
        if "name" not in metadata or not metadata["name"]:
            raise ValueError("Entry creation requires 'file_path'")

        name = md.normalize_str(metadata["name"])
        if name is None:
            raise ValueError(f"Invalid 'name' value: {metadata['name']}")

        # --- Core location data ---
        loc = Location(
            name=name,
            full_name=md.normalize_str(metadata.get("full_name")),
        )
        session.add(loc)
        session.flush()

        # TODO: I think this is handled by Entry
        # --- Relationships ---
        self.update_location_relationships(session, loc, metadata)
        return loc

    def create_person(self, session: Session, metadata: Dict[str, Any]) -> Person:
        """
        Create a new Person in the database with its associated relationships.

        This function does NOT handle file I/O or Markdown parsing. It assumes
        that `metadata` is already normalized (all dates as `datetime.date`,
        people, tags, events, etc. as strings or dicts).

        Args:
            session (Session): Active SQLAlchemy session
            metadata (Dict[str, Any]): Normalized metadata for the entry.
                Required keys:
                    - name (str)
                Optional keys:
                    - full_name (str)
                    - relation_type (str)
                Relationship keys:
                    - aliases (List[str], optional)
                    - events (List[str|Event], optional)
                    - entries (List[str|date|Entry], optional)

        Returns:
            Person: The newly created Person ORM object.

        Raises:
            ValueError: if required field is missing or invalid
        """
        # --- Required fields ---
        if "name" not in metadata or not metadata["name"]:
            raise ValueError("Entry creation requires 'name'")

        name = md.normalize_str(metadata["name"])
        if name is None:
            raise ValueError(f"Invalid 'name' value: {metadata['name']}")

        # --- Core location data ---
        person = Person(
            name=name,
            full_name=md.normalize_str(metadata.get("full_name")),
            relation_type=md.normalize_str(metadata.get("relation_type")),
        )

        session.add(person)
        session.flush()

        # TODO: Move this to update_person_relationships()
        # --- Relationships ---
        for alias in metadata.get("aliases", []):
            alias_str = md.normalize_str(alias)
            if alias_str:
                alias = Alias(alias=alias_str, person=person)
                session.add(alias)

        self.update_person_relationships(session, person, metadata)
        return person

    def create_reference(self, session: Session, metadata: Dict[str, Any]) -> Reference:
        """
        Create a new Reference in the database with its associated relationships.

        This function does NOT handle file I/O or Markdown parsing. It assumes
        that `metadata` is already normalized (all dates as `datetime.date`,
        people, tags, events, etc. as strings or dicts).

        Args:
            session (Session): Active SQLAlchemy session
            metadata (Dict[str, Any]): Normalized metadata for the entry.
                Required keys:
                    - name (str)
                Optional keys:
                    - author (str)
                    - content (str)
                Relationship keys:
                    - entries (List[str|date|dict|Entry], optional)

        Returns:
            Reference: The newly created Reference ORM object.

        Raises:
            ValueError: if required field is missing or invalid
        """
        # --- Required fields ---
        if "name" not in metadata or not metadata["name"]:
            raise ValueError("Entry creation requires 'name'")

        name = md.normalize_str(metadata["name"])
        if name is None:
            raise ValueError(f"Invalid 'name' value: {metadata['name']}")

        # Handle reference type first
        ref_type: Optional[ReferenceType] = None
        if ref_type_name := metadata.get("reference_type"):
            ref_type = self._get_or_create_lookup_item(
                session, ReferenceType, {"name": ref_type_name}
            )

        # --- Core reference data ---
        ref = Reference(
            name=name,
            author=md.normalize_str(metadata.get("author")),
            content=md.normalize_str(metadata.get("content")),
            reference_type=ref_type,
        )
        session.add(ref)
        session.flush()

        # TODO: I think this is handled by Entry
        # --- Relationships ---
        self.update_reference_relationships(session, ref, metadata)
        return ref

    def create_event(self, session: Session, metadata: Dict[str, Any]) -> Event:
        """
        Create a new Event in the database with its associated relationships.

        This function does NOT handle file I/O or Markdown parsing. It assumes
        that `metadata` is already normalized (all dates as `datetime.date`,
        people, tags, events, etc. as strings or dicts).

        Args:
            session (Session): Active SQLAlchemy session
            metadata (Dict[str, Any]): Normalized metadata for the entry.
                Required keys:
                    - name (str)
                Optional keys:
                    - title (str)
                    - description (str)
                Relationship keys:
                    - entries (List[str|date|dict|Entry], optional)
                    - people (List[str|dict|Person], optional)

        Returns:
            Event: The newly created Event ORM object.

        Raises:
            ValueError: if required field is missing or invalid
        """
        # --- Required fields ---
        if "name" not in metadata or not metadata["name"]:
            raise ValueError("Entry creation requires 'name'")

        name = md.normalize_str(metadata["name"])
        if name is None:
            raise ValueError(f"Invalid 'name' value: {metadata['name']}")

        # --- Core event data ---
        event = Event(
            name=name,
            title=md.normalize_str(metadata.get("title")),
            description=md.normalize_str(metadata.get("description")),
        )
        session.add(event)
        session.flush()

        # --- Relationships ---
        self.update_event_relationships(session, event, metadata)
        return event

    def create_or_update_poem_version(
        self, session: Session, poem_data: Dict[str, Any], entry: Optional[Entry]
    ) -> PoemVersion:
        """
        Create or update a PoemVersion for a given Poem.
        Optinally link it to an Entry.

        Args:
            session (Session): Active SQLAlchemy session.
            poem_data (Dict[str, Any]): Poem metadata, expected keys:
                - 'title' (str): The title of the Poem (required)
                - 'text' (str): The text of the PoemVersion (required)
                - 'version_hash' (str, optional): Hash for version deduplication
                - 'revision_date' (date, optional)
                - 'notes' (str, optional)
            entry (Entry | None): Optional Entry to associate the version with.

        Returns:
            PoemVersion: The created or updated PoemVersion instance.

        Notes:
            - If 'entry' is None, the version will exist independently.
            - Deduplication occurs based on version_hash or text.
            - Commit is left to the caller for batch operations.
        """
        # --- Required fields ---
        if "title" not in poem_data or not poem_data["title"]:
            raise ValueError("Poem creation requires 'title'")

        if "text" not in poem_data or not poem_data["text"]:
            raise ValueError("Poem creation requires 'text'")

        poem_title: Optional[str] = md.normalize_str(poem_data.get("title"))
        if not poem_title:
            raise ValueError(f"Invalid 'poem_title' value: {poem_data['title']}")

        poem_text: Optional[str] = md.normalize_str(poem_data.get("text"))
        if not poem_text:
            raise ValueError(f"Invalid 'poem_text' value: {poem_data['text']}")

        # --- Lookup / Creation ---
        poem = self._get_lookup_item(session, Poem, {"title": poem_title})
        if not poem:
            poem = Poem(title=poem_title)
            session.add(poem)
            session.flush()

        # --- Deduplication ---
        version_hash = md.normalize_str(poem_data.get("version_hash"))
        if not version_hash:
            version_hash = md.get_text_hash(poem_text)

        existing_version = None
        for v in poem.versions:
            if version_hash and v.version_hash == version_hash:
                existing_version = v
                break
            elif v.text == poem_text:
                existing_version = v
                break

        rev_date = md.parse_date(poem_data.get("revision_date"))
        rev_notes = md.normalize_str(poem_data.get("notes"))

        if existing_version:
            # Update fields if needed
            existing_version.text = poem_text
            existing_version.revision_date = (
                rev_date if rev_date else existing_version.revision_date
            )
            existing_version.notes = rev_notes if rev_notes else existing_version.notes
            poem_version = existing_version
        else:
            # Create new PoemVersion
            poem_version = PoemVersion(
                poem=poem,
                text=poem_text,
                version_hash=version_hash,
                revision_date=rev_date,
                notes=rev_notes,
            )
            session.add(poem_version)
            session.flush()

        # --- Link to Entry ---
        if entry and poem_version not in entry.poems:
            entry.poems.append(poem_version)

        return poem_version

    def update_entry(
        self, session: Session, entry: Entry, metadata: Dict[str, Any]
    ) -> Entry:
        """
        Update an existing Entry in the database and refresh its relationships.

        Does NOT perform file parsing. Accepts pre-normalized metadata.
        Clears previous relationships before adding new ones.

        Args:
            session (Session): Active SQLAlchemy session
            entry (Entry): Existing Entry ORM object to update.
            metadata (Dict[str, Any]): Normalized metadata as in `create_entry`.

        Returns:
            Entry: Updated Entry ORM object.
        """
        with self.get_session() as session:
            # Attach the entry to the session
            entry = session.merge(entry)

            # Update core fields
            for key in [
                "date",
                "file_path",
                "file_hash",
                "word_count",
                "reading_time",
                "epigraph",
                "notes",
                # "dates",
                # "locations",
                # "people",
                # "references",
                # "events",
                # "poems",
                # "tags",
            ]:
                if key in metadata:
                    setattr(entry, key, metadata[key])

            # Clear old relationships
            entry.people.clear()
            entry.tags.clear()
            entry.locations.clear()
            entry.events.clear()
            entry.references.clear()

            # Update relationships with new metadata
            self.update_entry_relationships(session, entry, metadata)

            session.commit()
            return entry

    def update_entry_relationships(
        self, session: Session, entry: Entry, metadata: Dict[str, Any]
    ) -> None:
        """
        Update all many-to-many relationships for an Entry using normalized metadata.

        This function handles relationships only. No I/O or Markdown parsing.
        Prevents duplicates and ensures lookup tables are updated.

        Args:
            session (Session): Active SQLAlchemy session.
            entry (Entry): Entry ORM object to update relationships for.
            metadata (Dict[str, Any]): Normalized metadata containing:
                - dates (List[dates], optional)
                - locations (List[str|dict], optional)
                - people (List[str|dict], optional)
                - references (List[str|dict], optional)
                - events (List[str|dict], optional)
                - poems (List[str|dict], optional
                - tags (List[str], optional)

        Returns:
            None
        """
        # MentionedDates
        for date_obj in metadata.get("dates", []):
            parsed_date: Optional[date] = md.parse_date(date_obj)
            if parsed_date:
                self._append_lookup(
                    session, entry.dates, MentionedDate, {"date": date_obj}
                )

        # Locations
        for loc in metadata.get("locations", []):
            if isinstance(loc, str):
                col_name = "full_name" if "," in loc else "name"
                self._append_lookup(session, entry.locations, Location, {col_name: loc})
            elif isinstance(loc, dict):
                name = loc.get("name")
                full_name = loc.get("full_name")
                if name and full_name:
                    self._append_lookup(
                        session,
                        entry.locations,
                        Location,
                        {"full_name": full_name},
                        {"name": name},
                    )
                elif name:
                    self._append_lookup(
                        session, entry.locations, Location, {"name": name}
                    )
                elif full_name:
                    self._append_lookup(
                        session, entry.locations, Location, {"full_name": full_name}
                    )

        # People
        for person in metadata.get("people", []):
            if isinstance(person, str):
                person_str = md.normalize_str(person)
                if person_str:
                    col_name = "name" if len(person_str.split()) == 1 else "full_name"
                    self._append_lookup(
                        session, entry.people, Person, {col_name: person_str}
                    )
            elif isinstance(person, dict):
                col_names = ["name", "full_name", "relation_type"]
                full_name = person.get("full_name")
                name = person.get("name")
                if full_name or name:
                    if full_name:
                        col, val = "full_name", full_name
                        col_names.remove("full_name")
                    else:
                        col, val = "name", name
                        col_names.remove("name")

                    extra_fields = {
                        k: person.get(k) for k in col_names if person.get(k)
                    }

                    self._append_lookup(
                        session, entry.people, Person, {col: val}, extra_fields
                    )

        # Tags
        for tag_name in metadata.get("tags", []):
            if tag_name:
                self._append_lookup(session, entry.tags, Tag, {"name": tag_name})

        # Events
        for evt in metadata.get("events", []):
            if isinstance(evt, str):
                self._append_lookup(session, entry.events, Event, {"name": evt})
            elif isinstance(evt, dict):
                name = evt.get("name")
                if name:
                    extra_fields = {
                        k: evt.get(k) for k in ["category", "notes"] if evt.get(k)
                    }
                    self._append_lookup(
                        session, entry.events, Event, {"name": name}, extra_fields
                    )

        # References
        for ref in metadata.get("references", []):
            if isinstance(ref, str):
                self._append_lookup(session, entry.references, Reference, {"name": ref})
            elif isinstance(ref, dict):
                name = ref.get("name") or ref.get("content")
                if name:
                    extra_fields = {}
                    if ref.get("type"):
                        ref_type = self._get_or_create_lookup_item(
                            session, ReferenceType, {"name": ref["type"]}
                        )
                        extra_fields["type_id"] = ref_type.id
                    extra_fields.update(
                        {k: ref.get(k) for k in ["url", "metadata"] if ref.get(k)}
                    )
                    self._append_lookup(
                        session,
                        entry.references,
                        Reference,
                        {"name": name},
                        extra_fields,
                    )

    # def create_manuscript_entry(
    #     self,
    #     entry_id: int,
    #     status: ManuscriptStatus,
    #     edited: bool = False,
    #     themes: list[str] | None = None,
    # ):
    #     """
    #     Create a ManuscriptEntry record tied to an existing Entry.
    #
    #     Args:
    #         entry_id (int): ID of the Entry to include in manuscript.
    #         status (ManuscriptStatus): Initial manuscript status (draft, final, etc.).
    #         edited (bool): Whether the entry text has been edited for the manuscript.
    #         themes (list[str]): Optional list of themes to associate.
    #
    #     Returns:
    #         ManuscriptEntry
    #     """
    #
    # def update_manuscript_entry(
    #     self,
    #     manuscript_id: int,
    #     status: ManuscriptStatus | None = None,
    #     edited: bool | None = None,
    #     themes: list[str] | None = None,
    # ):
    #     """
    #     Update fields of a ManuscriptEntry.
    #
    #     Args:
    #         manuscript_id (int): ID of the ManuscriptEntry.
    #         status (Optional[ManuscriptStatus]): Update status.
    #         edited (Optional[bool]): Update edited flag.
    #         themes (Optional[list[str]]): Replace associated themes.
    #
    #     Returns:
    #         ManuscriptEntry
    #     """
    #
    # def get_manuscript_entry(self, entry_id: int):
    #     """
    #     Fetch the ManuscriptEntry tied to a given Entry (if it exists).
    #     """

    def update_location_relationships(
        self, session: Session, location: Location, metadata: Dict[str, Any]
    ) -> None:
        pass

    def update_person_relationships(
        self, session: Session, person: Person, metadata: Dict[str, Any]
    ) -> None:
        pass

    def update_reference_relationships(
        self, session: Session, reference: Reference, metadata: Dict[str, Any]
    ) -> None:
        pass

    def update_event_relationships(
        self, session: Session, event: Event, metadata: Dict[str, Any]
    ) -> None:
        pass

    def update_poem_relationships(
        self, session: Session, poem: Poem, metadata: Dict[str, Any]
    ) -> None:
        pass

    # --- CRUD / Query ---
    def get_entry_metadata(self, file_path: str) -> Dict[str, Any]:
        """Get metadata for a specific entry"""
        with self.get_session() as session:
            entry = session.query(Entry).filter_by(file_path=file_path).first()
            if not entry:
                return {}

            return {
                "date": entry.date,
                "word_count": entry.word_count,
                "reading_time": entry.reading_time,
                "epigraph": entry.epigraph or "",
                "notes": entry.notes or "",
                "people": [person.name for person in entry.people],
                "tags": [tag.name for tag in entry.tags],
                "location": [location.name for location in entry.locations],
                "events": [event.name for event in entry.events],
                "references": [ref.content for ref in entry.references],
            }

    def get_all_values(self, field: str) -> List[str]:
        """Get all unique values for a field (for autocomplete)"""
        model_map = {
            "people": Person,
            "tags": Tag,
            "locations": Location,
            "events": Event,
            "reference_types": ReferenceType,
        }

        if field in model_map:
            with self.get_session() as session:
                items = (
                    session.query(model_map[field])
                    .order_by(model_map[field].name)
                    .all()
                )
                return [item.name for item in items]

        return []

    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self.get_session() as session:
            stats = {}

            # Basic counts
            stats["entries"] = session.query(Entry).count()
            stats["people"] = session.query(Person).count()
            stats["tags"] = session.query(Tag).count()
            stats["locations"] = session.query(Location).count()
            stats["events"] = session.query(Event).count()
            stats["references"] = session.query(Reference).count()

            # Migration info
            migration_info = self.get_migration_history()
            stats["migration_status"] = migration_info

            # Recent activity
            from datetime import timedelta

            week_ago = datetime.now() - timedelta(days=7)
            stats["entries_updated_last_7_days"] = (
                session.query(Entry).filter(Entry.updated_at >= week_ago).count()
            )

            # # Status breakdown
            # status_counts = (
            #     session.query(Entry.status, func.count(Entry.id))
            #     .group_by(Entry.status)
            #     .all()
            # )
            # stats["status_breakdown"] = dict(status_counts)

            return stats
