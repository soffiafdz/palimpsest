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
import warnings
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
from sqlalchemy.sql import func

# --- Local imports ---
from scripts.metadata.models import (
    Base,
    Entry,
    # MentionedDate,
    Location,
    Person,
    Reference,
    ReferenceType,
    Event,
    # Poem,
    # PoemVersion,
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

    # --- Lookup helpers ---
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
        query = session.query(model_class).filter_by(**lookup_fields)
        obj = query.first()
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

    # --- Entry Management ---
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
                    - file_hash (str)
                Optional keys:
                    - word_count (int | str)
                    - reading_time (float | str)
                    - epigraph (str)
                    - notes (str)
                Relationship keys:
                    - dates (List[dates], optional)
                    - people (List[str], optional)
                    - tags (List[str], optional)
                    - locations (List[str or dict], optional)
                    - events (List[str or dict], optional)
                    - references (List[str or dict], optional)

        Returns:
            Entry: The newly created Entry ORM object.

        Raises:
            ValueError: if required fields are missing or invalid
        """
        entry = Entry(
            date=self._parse_date(metadata.get("date")),
            file_path=metadata["file_path"],
            file_hash=metadata["file_hash"],
            word_count=self._safe_int(metadata.get("word_count")),
            reading_time=self._safe_float(metadata.get("reading_time")),
            epigraph=self._normalize_str(metadata.get("epigraph")),
            notes=self._normalize_str(metadata.get("notes")),
        )
        # --- Required fields ---
        if "file_path" not in metadata or not metadata["file_path"]:
            raise ValueError("Entry creation requires 'file_path'")

        if "file_hash" not in metadata or not metadata["file_hash"]:
            raise ValueError("Entry creation requires 'file_hash'")

        if "date" not in metadata or not metadata["date"]:
            raise ValueError("Entry creation requires 'date'")

        parsed_date = self._parse_date(metadata["date"])
        if parsed_date is None:
            raise ValueError(f"Invalid 'date' value: {metadata['date']}")

        # --- Core entry data ---
        entry = Entry(
            date=parsed_date,
            file_path=metadata["file_path"],
            file_hash=metadata["file_hash"],
            word_count=self._safe_int(metadata.get("word_count")),
            reading_time=self._safe_float(metadata.get("reading_time")),
            epigraph=self._normalize_str(metadata.get("epigraph")),
            notes=self._normalize_str(metadata.get("notes")),
        )
        session.add(entry)

        # --- Relationships ---
        self.update_entry_relationships(session, entry, metadata)

        # --- Commit ---
        session.commit()
        return entry

        with self.get_session() as session:
            entry_data = {
                "date": metadata["date"],
                "word_count": metadata.get("word_count", 0),
                "reading_time": metadata.get("reading_time", 0.0),
                "status": metadata.get("status", "unreviewed"),
                "excerpted": metadata.get("excerpted", False),
                "epigraph": metadata.get("epigraph"),
                "notes": metadata.get("notes"),
                "file_hash": file_hash,
            }
            entry = Entry(**entry_data)
            session.add(entry)
            session.flush()  # assign ID for relationships

            # Add relationships
            self.update_entry_relationships(session, entry, metadata)
            session.commit()
            return entry

    def update_entry(
        self, entry: Entry, metadata: Dict[str, Any], file_hash: str
    ) -> Entry:
        """
        Update an existing Entry in the database and refresh its relationships.

        Does NOT perform file parsing. Accepts pre-normalized metadata.
        Clears previous relationships before adding new ones.

        Args:
            entry (Entry): Existing Entry ORM object to update.
            metadata (Dict[str, Any]): Normalized metadata as in `create_entry`.
            file_hash (str): Updated hash of the source file.

        Returns:
            Entry: Updated Entry ORM object.
        """
        with self.get_session() as session:
            # Attach the entry to the session
            entry = session.merge(entry)

            # Update core fields
            for key in [
                "date",
                "word_count",
                "reading_time",
                "status",
                "excerpted",
                "epigraph",
                "notes",
            ]:
                if key in metadata:
                    setattr(entry, key, metadata[key])
            entry.file_hash = file_hash

            # Clear old relationships
            entry.people.clear()
            entry.tags.clear()
            entry.locations.clear()
            entry.events.clear()
            entry.references.clear()
            if hasattr(entry, "themes"):
                entry.themes.clear()

            # Update relationships with new metadata
            self.update_entry_relationships(session, entry, metadata)

            session.commit()
            return entry

    def update_entry_relationships(
        self, session: Session, entry: Entry, normalized_metadata: Dict[str, Any]
    ) -> None:
        """
        Update all many-to-many relationships for an Entry using normalized metadata.

        This function handles relationships only. No I/O or Markdown parsing.
        Prevents duplicates and ensures lookup tables are updated.

        Args:
            session (Session): Active SQLAlchemy session.
            entry (Entry): Entry ORM object to update relationships for.
            normalized_metadata (Dict[str, Any]): Normalized metadata containing:
                - people (List[str])
                - tags (List[str])
                - locations (List[str or dict])
                - events (List[str or dict])
                - references (List[str or dict])
                - themes (List[str])  # optional, manuscript-specific

        Returns:
            None
        """
        # People
        for person_name in normalized_metadata.get("people", []):
            if person_name:
                self._append_lookup(
                    session, entry.people, Person, {"name": person_name}
                )

        # Tags
        for tag_name in normalized_metadata.get("tags", []):
            if tag_name:
                self._append_lookup(session, entry.tags, Tag, {"name": tag_name})

        # Locations
        for loc in normalized_metadata.get("locations", []):
            if isinstance(loc, str):
                self._append_lookup(session, entry.locations, Location, {"name": loc})
            elif isinstance(loc, dict):
                name = loc.get("name")
                if name:
                    extra_fields = {
                        k: loc.get(k)
                        for k in [
                            "full_name",
                            "coordinates",
                            "parent_location",
                            "location_type",
                        ]
                        if loc.get(k)
                    }
                    self._append_lookup(
                        session, entry.locations, Location, {"name": name}, extra_fields
                    )

        # Events
        for evt in normalized_metadata.get("events", []):
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
        for ref in normalized_metadata.get("references", []):
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

        def create_manuscript_entry(
            self,
            entry_id: int,
            status: ManuscriptStatus,
            edited: bool = False,
            themes: list[str] | None = None,
        ):
            """
            Create a ManuscriptEntry record tied to an existing Entry.

            Args:
                entry_id (int): ID of the Entry to include in manuscript.
                status (ManuscriptStatus): Initial manuscript status (draft, final, etc.).
                edited (bool): Whether the entry text has been edited for the manuscript.
                themes (list[str]): Optional list of themes to associate.

            Returns:
                ManuscriptEntry
            """

        def update_manuscript_entry(
            self,
            manuscript_id: int,
            status: ManuscriptStatus | None = None,
            edited: bool | None = None,
            themes: list[str] | None = None,
        ):
            """
            Update fields of a ManuscriptEntry.

            Args:
                manuscript_id (int): ID of the ManuscriptEntry.
                status (Optional[ManuscriptStatus]): Update status.
                edited (Optional[bool]): Update edited flag.
                themes (Optional[list[str]]): Replace associated themes.

            Returns:
                ManuscriptEntry
            """

        def get_manuscript_entry(self, entry_id: int):
            """
            Fetch the ManuscriptEntry tied to a given Entry (if it exists).
            """

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
                "excerpted": entry.excerpted,
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
