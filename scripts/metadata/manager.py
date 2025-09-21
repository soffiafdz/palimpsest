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
import shutil

# from datetime import date, datetime, timezone
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type, TypeVar, Union

# --- Third party ---
# import yaml
from alembic.config import Config
from alembic import command

from alembic.runtime.migration import MigrationContext

# from alembic.operations import Operations
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

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
from scripts.metadata.models_manuscript import (
    ManuscriptStatus,
    ManuscriptEntry,
    ManuscriptEvent,
    ManuscriptPerson,
    Arc,
    Theme,
)

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
                "target_metadata = None",
                f"{import_line}\n{target_metadata_line}",
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
                print(
                    "Note: Could not stamp database ", f"(run init_alembic first): {e}"
                )
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

    def _get_or_create_lookup_item(
        self,
        session: Session,
        model_class: Type[T],
        lookup_fields: Dict[str, Any],
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> T:
        """
        Get an existing item from a lookup table,
        or create it if it doesn't exist.

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

    def _remove_lookup_item(
        self,
        session: Session,
        model_class: Type[T],
        obj: Optional[T] = None,
        id: Optional[int] = None,
        lookup_fields: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Remove an item from a lookup table.

        Args:
            session (Session): Active SQLAlchemy session.
            model_class (Type[Base]): ORM model class.
            obj (Optional[T]): The ORM object to remove.
                If provided, removal uses this directly.
            id (Optional[int]): Primary key ID of the object to remove.
                Used if `obj` not provided.
            lookup_fields (Optional[Dict[str, Any]]):
                Dictionary of field_name: value to locate the object.

        Returns:
            bool: True if an object was found and removed, False otherwise.

        Behavior:
            - Requires at least one of obj, id, or lookup_fields.
            - If multiple identifiers are provided,
              obj takes precedence, then id, then lookup_fields.
            - Flushes the session immediately after removal.
        """
        if obj is None:
            if id is not None:
                obj = session.get(model_class, id)
            elif lookup_fields:
                obj = self._get_lookup_item(session, model_class, lookup_fields)
            else:
                raise ValueError("Must provide obj, id, or lookup_fields to remove.")

        if obj:
            session.delete(obj)
            session.flush()
            return True

        return False

    # --- Tables creation ---
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
                Relationship keys (optional):
                    - dates (List[MentionedDate|int])
                    - locations (List[Location|int])
                    - people (List[Person|int])
                    - references (List[Reference|int])
                    - events (List[Event|int])
                    - poems (List[Poem|int])
                    - tags (List[str])
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

        # --- Tags ---
        tags = metadata.get("tags")
        if tags:
            self.update_entry_tags(session, entry, tags)

        # --- Relationships ---
        self.update_entry_relationships(session, entry, metadata)
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
        return loc

    def create_person(self, session: Session, metadata: Dict[str, Any]) -> Person:
        """
        Create a new Person in the db with its associated relationships.

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

        # --- Aliases ---
        aliases = metadata.get("aliases")
        if aliases:
            self.update_person_aliases(session, person, aliases, incremental=False)

        # --- Relationships ---
        self.update_person_relationships(session, person, metadata)
        return person

    def create_reference(self, session: Session, metadata: Dict[str, Any]) -> Reference:
        """
        Create a new Reference in the db with its associated relationships.

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
        return ref

    def create_event(self, session: Session, metadata: Dict[str, Any]) -> Event:
        """
        Create a new Event in the db with its associated relationships.

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
        self,
        session: Session,
        poem_data: Dict[str, Any],
        entry: Optional[Entry],
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
        poem: Poem = self._get_or_create_lookup_item(
            session, Poem, {"title": poem_title}
        )

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
            session.flush()

        return poem_version

    # --- Tables updates ---
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
                Keys may include:
                    - Core fields:
                      date, file_path, file_hash,
                      word_count, reading_time, epigraph, notes
                    - Relationship keys:
                      dates, locations, people, references, events, poems, tags

        Returns:
            Entry: The updated Entry ORM object (still attached to session).
        """
        # --- Failsafe ---
        db_entry = session.get(Entry, entry.id)
        if db_entry is None:
            raise ValueError(
                f"Entry with id={entry.id} does not exist in the database."
            )

        # --- Attach to session ---
        entry = session.merge(db_entry)

        # --- Check & update fields ---
        # -- date --
        if "date" in metadata:
            entry_date: Optional[date] = md.parse_date(metadata["date"])
            if entry_date is None:
                raise ValueError(
                    "Expected str|date for Entry.date, ",
                    f"got {type(metadata['date'])}",
                )
            entry.date = entry_date

        # -- file_path --
        if "file_path" in metadata:
            file_path: Optional[str] = md.normalize_str(metadata["file_path"])
            if file_path is None:
                raise ValueError(
                    "Expected str for Entry.file_path,",
                    f"got {type(metadata['file_path'])}",
                )
            entry.file_path = file_path

        # -- word_count --
        if "word_count" in metadata:
            word_count: Optional[int] = md.safe_int(metadata["word_count"])
            if word_count is None:
                raise ValueError(
                    "Expected int for Entry.word_count, ",
                    f"got {type(metadata['word_count'])}",
                )
            entry.word_count = word_count

        # -- reading_time --
        if "reading_time" in metadata:
            reading_time: Optional[float] = md.safe_float(metadata["reading_time"])
            if reading_time is None:
                raise ValueError(
                    "Expected float for Entry.reading_time, ",
                    f"got {type(metadata['reading_time'])}",
                )
            entry.reading_time = reading_time

        # -- file_hash, epigraph, notes (str) --
        for key in ["file_hash", "epigraph", "notes"]:
            if key in metadata:
                setattr(entry, key, md.normalize_str(metadata[key]))

        # --- Tags ---
        if "tags" in metadata:
            self.update_entry_tags(session, entry, metadata["tags"])

        # --- Relationships ---
        self.update_entry_relationships(session, entry, metadata)
        return entry

    def update_location(
        self, session: Session, loc: Location, metadata: Dict[str, Any]
    ) -> Location:
        """
        Update an existing Location in the db and refresh its relationships.

        Does NOT perform file parsing. Accepts pre-normalized metadata.
        Clears previous relationships before adding new ones.

        Args:
            session (Session): Active SQLAlchemy session
            loc (Location): Existing Entry ORM object to update.
            metadata (Dict[str, Any]): Normalized metadata as in `create_entry`.
                Keys may include:
                    - Core fields: name, full_name

        Returns:
            Location: The updated Entry ORM object (still attached to session).
        """
        # --- Failsafe ---
        db_loc = session.get(Location, loc.id)
        if db_loc is None:
            raise ValueError(
                f"Location with id={loc.id} does not exist in the database."
            )

        # --- Attach to session ---
        loc = session.merge(db_loc)

        # --- Check & update fields ---
        # -- name --
        if "name" in metadata:
            loc_name: Optional[str] = md.normalize_str(metadata["name"])
            if loc_name is None:
                raise ValueError(
                    f"Expected str for Location.name, got {type(metadata['name'])}"
                )
            loc.name = loc_name

        # -- full_name --
        if "full_name" in metadata:
            loc.full_name = md.normalize_str(metadata["full_name"])

        return loc

    def update_person(
        self, session: Session, person: Person, metadata: Dict[str, Any]
    ) -> Person:
        """
        Update an existing Person in the database and refresh its relationships.

        Does NOT perform file parsing. Accepts pre-normalized metadata.
        Clears previous relationships before adding new ones.

        Args:
            session (Session): Active SQLAlchemy session
            person (Person): Existing Entry ORM object to update.
            metadata (Dict[str, Any]): Normalized metadata as in `create_entry`.
                Keys may include:
                    - Core fields: name, full_name, relation_type
                    - Relationship keys: aliases, events, entries

        Returns:
            Person: The updated Entry ORM object (still attached to session).
        """
        # --- Failsafe ---
        db_person = session.get(Person, person.id)
        if db_person is None:
            raise ValueError(
                f"Person with id={person.id} does not exist in the database."
            )

        # --- Attach to session ---
        person = session.merge(db_person)

        # --- Check & update fields ---
        # -- name --
        if "name" in metadata:
            person_name: Optional[str] = md.normalize_str(metadata["name"])
            if person_name is None:
                raise ValueError(
                    f"Expected str for Person.name, got {type(metadata['name'])}"
                )
            person.name = person_name

        # -- full_name, relation_type (str) --
        for key in ["full_name", "relation_type"]:
            if key in metadata:
                setattr(person, key, md.normalize_str(metadata[key]))

        # --- Aliases ---
        if "aliases" in metadata:
            self.update_person_aliases(session, person, metadata["aliases"])

        # --- Relationships ---
        self.update_person_relationships(session, person, metadata)
        return person

    def update_reference(
        self, session: Session, ref: Reference, metadata: Dict[str, Any]
    ) -> Reference:
        """
        Update an existing Reference in the db and refresh its relationships.

        Does NOT perform file parsing. Accepts pre-normalized metadata.
        Clears previous relationships before adding new ones.

        Args:
            session (Session): Active SQLAlchemy session
            ref (Reference): Existing Entry ORM object to update.
            metadata (Dict[str, Any]): Normalized metadata as in `create_entry`.
                Keys may include:
                    - Core fields: name, author, content
                    - Relationship keys: reference_type

        Returns:
            Reference: The updated Entry ORM object (still attached to session).
        """
        # --- Failsafe ---
        db_ref = session.get(Reference, ref.id)
        if db_ref is None:
            raise ValueError(
                f"Reference with id={ref.id} does not exist in the database."
            )

        # --- Attach to session ---
        ref = session.merge(db_ref)

        # --- Check & update fields ---
        # -- name --
        if "name" in metadata:
            ref_name: Optional[str] = md.normalize_str(metadata["name"])
            if ref_name is None:
                raise ValueError(
                    f"Expected str for Reference.name, got {type(metadata['name'])}"
                )
            ref.name = ref_name

        # -- author, content (str) --
        for key in ["author", "content"]:
            if key in metadata:
                setattr(ref, key, md.normalize_str(metadata[key]))

        # -- reference type --
        ref_type: Optional[ReferenceType] = None
        if ref_type_name := metadata.get("reference_type"):
            ref_type = self._get_or_create_lookup_item(
                session, ReferenceType, {"name": ref_type_name}
            )
            ref.reference_type = ref_type

        session.flush()
        return ref

    def update_event(
        self, session: Session, event: Event, metadata: Dict[str, Any]
    ) -> Event:
        """
        Update an existing Event in the database and refresh its relationships.

        Does NOT perform file parsing. Accepts pre-normalized metadata.
        Clears previous relationships before adding new ones.

        Args:
            session (Session): Active SQLAlchemy session
            event (Event): Existing Entry ORM object to update.
            metadata (Dict[str, Any]): Normalized metadata as in `create_entry`.
                Keys may include:
                    - Core fields: name, title, description
                    - Relationship keys: entries, people

        Returns:
            Event: The updated Entry ORM object (still attached to session).
        """
        # --- Failsafe ---
        db_event = session.get(Event, event.id)
        if db_event is None:
            raise ValueError(
                f"Event with id={event.id} does not exist in the database."
            )

        # --- Attach to session ---
        event = session.merge(db_event)

        # --- Check & update fields ---
        # -- name --
        if "name" in metadata:
            event_name: Optional[str] = md.normalize_str(metadata["name"])
            if event_name is None:
                raise ValueError(
                    f"Expected str for Event.name, got {type(metadata['name'])}"
                )
            event.name = event_name

        # -- title, description (str) --
        for key in ["title", "description"]:
            if key in metadata:
                setattr(event, key, md.normalize_str(metadata[key]))

        # --- Relationships ---
        self.update_event_relationships(session, event, metadata)
        return event

    # --- Relationship updating ---
    def update_entry_tags(
        self, session: Session, entry: Entry, tags: List[str]
    ) -> None:
        """
        Update (fully) Tags for an Entry from metadata.

        This clears all existing tags and recreates the relationships.

        Args:
            session (Session): Active SQLAlchemy session.
            entry (Entry): Entry object whose tags are to be updated.
            tags (List[str]): List of tags (strings).

        Returns:
            None
        """
        # --- Failsafe ---
        if entry.id is None:
            raise ValueError(
                "Entry instance has no ID; must be persisted before linking."
            )

        # --- Clear existing ---
        entry.tags.clear()
        session.flush()

        # --- Add new ones --
        for tag in tags:
            tag_normalized = md.normalize_str(tag)
            if not tag_normalized:
                raise ValueError(f"Invalid tag value: {tag}")

            tag = self._get_or_create_lookup_item(session, Tag, {"tag": tag_normalized})

            entry.tags.append(tag)

        session.flush()

    def update_entry_relationships(
        self,
        session: Session,
        entry: Entry,
        metadata: Dict[str, Any],
        incremental: bool = True,
    ) -> None:
        """
        Update relationships for an Entry object in the database.

        Supports both incremental updates (defualt) and full overwrite.
        This function handles relationships only. No I/O or Markdown parsing.
        Prevents duplicates and ensures lookup tables are updated.

        Args:
            session (Session): Active SQLAlchemy session.
            entry (Entry): Entry ORM object to update relationships for.
            metadata (Dict[str, Any]): Normalized metadata containing:
                Expected keys (optional):
                    - dates (List[MentionedDate|int])
                    - locations (List[Location|int])
                    - people (List[Person|int])
                    - references (List[Reference|int])
                    - events (List[Event|int])
                    - poems (List[PoemVersion|int]
                Removal keys (optional):
                    - remove_dates (List[MentionedDate|int])
                    - remove_locations (List[Location|int])
                    - remove_people (List[Person|int])
                    - remove_references (List[Reference|int])
                    - remove_events (List[Event|int])
                    - remove_poems (List[PoemVersion|int]
            incremental (bool): Whether incremental/overwrite mode.

        Behavior:
            - Incremental mode:
                adds new relationships and/or removes explicitly listed items.
            - Overwrite mode:
                clears all existing relationships before adding new ones.
            - Calls session.flush() only if any changes were made

        Returns:
            None

        Raises:
            TypeError: if values of metadata are not ORM objects nor int.
            ValueError: ORM instance is non-existent
        """
        # --- Failsafe ---
        if entry.id is None:
            raise ValueError(
                "Entry instance has no ID; must be persisted before linking."
            )

        # --- Relationship management ---
        changed: bool = False

        # -- MentionedDate --
        existing_dates: Set[int] = {d.id for d in entry.dates}

        if not incremental:
            entry.dates.clear()
            changed = True

        # - Appending -
        for d_meta in metadata.get("dates", []):
            if isinstance(d_meta, MentionedDate):
                date_obj = d_meta
                if date_obj.id is None:
                    raise ValueError(
                        "MentionedDate instance has no ID; ",
                        "must be persisted before linking.",
                    )
            elif isinstance(d_meta, int):
                date_obj = session.get(MentionedDate, d_meta)
                if date_obj is None:
                    raise ValueError(f"No MentionedDate found with id:{d_meta}")
            else:
                raise TypeError(
                    "Expected MentionedDate instance or int, ", f"got {type(d_meta)}"
                )

            if date_obj.id not in existing_dates:
                entry.dates.append(date_obj)
                changed = True

        # - Removal -
        if incremental:
            for d_meta in metadata.get("remove_dates", []):
                if isinstance(d_meta, MentionedDate):
                    date_obj = d_meta
                    if date_obj.id is None:
                        raise ValueError(
                            "MentionedDate instance has no ID; ",
                            "must be persisted before linking.",
                        )
                elif isinstance(d_meta, int):
                    date_obj = session.get(MentionedDate, d_meta)
                    if date_obj is None:
                        raise ValueError(f"No MentionedDate found with id:{d_meta}")
                else:
                    raise TypeError(
                        "Expected MentionedDate instance or int, ",
                        f"got {type(d_meta)}",
                    )

                if date_obj.id in existing_dates:
                    entry.dates.remove(date_obj)
                    changed = True

        # -- Location --
        existing_locs: Set[int] = {loc.id for loc in entry.locations}

        if not incremental:
            entry.locations.clear()
            changed = True

        # - Appending -
        for l_meta in metadata.get("locations", []):
            if isinstance(l_meta, Location):
                loc_obj = l_meta
                if loc_obj.id is None:
                    raise ValueError(
                        "Location instance has no ID; ",
                        "must be persisted before linking.",
                    )
            elif isinstance(l_meta, int):
                loc_obj = session.get(Location, l_meta)
                if loc_obj is None:
                    raise ValueError(f"No Location found with id:{l_meta}")
            else:
                raise TypeError(
                    "Expected Location instance or int, ", f"got {type(l_meta)}"
                )

            if loc_obj.id not in existing_locs:
                entry.locations.append(loc_obj)
                changed = True

        # - Removal -
        if incremental:
            for l_meta in metadata.get("remove_locations", []):
                if isinstance(l_meta, Location):
                    loc_obj = l_meta
                    if loc_obj.id is None:
                        raise ValueError(
                            "Location instance has no ID; ",
                            "must be persisted before linking.",
                        )
                elif isinstance(l_meta, int):
                    loc_obj = session.get(Location, l_meta)
                    if loc_obj is None:
                        raise ValueError(f"No Location found with id:{l_meta}")
                else:
                    raise TypeError(
                        "Expected Location instance or int, ", f"got {type(l_meta)}"
                    )

                if loc_obj.id in existing_locs:
                    entry.locations.remove(loc_obj)
                    changed = True

        # -- Reference --
        existing_refs: Set[int] = {r.id for r in entry.references}

        if not incremental:
            entry.references.clear()
            changed = True

        # - Appending -
        for r_meta in metadata.get("references", []):
            if isinstance(r_meta, Reference):
                ref_obj = r_meta
                if ref_obj.id is None:
                    raise ValueError(
                        "Reference instance has no ID; ",
                        "must be persisted before linking.",
                    )
            elif isinstance(r_meta, int):
                ref_obj = session.get(Reference, r_meta)
                if ref_obj is None:
                    raise ValueError(f"No Reference found with id:{r_meta}")
            else:
                raise TypeError(
                    "Expected Reference instance or int, ", f"got {type(r_meta)}"
                )

            if ref_obj.id not in existing_refs:
                entry.references.append(ref_obj)
                changed = True

        # - Removal -
        if incremental:
            for r_meta in metadata.get("remove_references", []):
                if isinstance(r_meta, Reference):
                    ref_obj = r_meta
                    if ref_obj.id is None:
                        raise ValueError(
                            "Reference instance has no ID; ",
                            "must be persisted before linking.",
                        )
                elif isinstance(r_meta, int):
                    ref_obj = session.get(Reference, r_meta)
                    if ref_obj is None:
                        raise ValueError(f"No Reference found with id:{r_meta}")
                else:
                    raise TypeError(
                        "Expected Reference instance or int, ", f"got {type(r_meta)}"
                    )

                if ref_obj.id in existing_refs:
                    entry.references.remove(ref_obj)
                    changed = True

        # -- Event --
        existing_events: Set[int] = {e.id for e in entry.events}

        if not incremental:
            entry.events.clear()
            changed = True

        # - Appending -
        for e_meta in metadata.get("events", []):
            if isinstance(e_meta, Event):
                event_obj = e_meta
                if event_obj.id is None:
                    raise ValueError(
                        "Event instance has no ID; ",
                        "must be persisted before linking.",
                    )
            elif isinstance(e_meta, int):
                event_obj = session.get(Event, e_meta)
                if event_obj is None:
                    raise ValueError(f"No Event found with id:{e_meta}")
            else:
                raise TypeError(
                    "Expected Event instance or int, ", f"got {type(e_meta)}"
                )

            if event_obj.id not in existing_events:
                entry.events.append(event_obj)
                changed = True

        # - Removal -
        if incremental:
            for e_meta in metadata.get("remove_events", []):
                if isinstance(e_meta, Event):
                    event_obj = e_meta
                    if event_obj.id is None:
                        raise ValueError(
                            "Event instance has no ID; ",
                            "must be persisted before linking.",
                        )
                elif isinstance(e_meta, int):
                    event_obj = session.get(Event, e_meta)
                    if event_obj is None:
                        raise ValueError(f"No Event found with id:{e_meta}")
                else:
                    raise TypeError(
                        "Expected Event instance or int, ", f"got {type(e_meta)}"
                    )

                if event_obj.id in existing_events:
                    entry.events.remove(event_obj)
                    changed = True

        # -- Poem --
        existing_poems: Set[int] = {p.id for p in entry.poems}

        if not incremental:
            entry.poems.clear()
            changed = True

        # - Appending -
        for p_meta in metadata.get("poems", []):
            if isinstance(p_meta, PoemVersion):
                poem_obj = p_meta
                if poem_obj.id is None:
                    raise ValueError(
                        "PoemVersion instance has no ID; ",
                        "must be persisted before linking.",
                    )
            elif isinstance(p_meta, int):
                poem_obj = session.get(PoemVersion, p_meta)
                if poem_obj is None:
                    raise ValueError(f"No PoemVersion found with id:{p_meta}")
            else:
                raise TypeError(
                    "Expected PoemVersion instance or int, ", f"got {type(p_meta)}"
                )

            if poem_obj.id not in existing_poems:
                entry.poems.append(poem_obj)
                changed = True

        # - Removal -
        if incremental:
            for p_meta in metadata.get("remove_poems", []):
                if isinstance(p_meta, PoemVersion):
                    poem_obj = p_meta
                    if poem_obj.id is None:
                        raise ValueError(
                            "PoemVersion instance has no ID; ",
                            "must be persisted before linking.",
                        )
                elif isinstance(p_meta, int):
                    poem_obj = session.get(PoemVersion, p_meta)
                    if poem_obj is None:
                        raise ValueError(f"No PoemVersion found with id:{p_meta}")
                else:
                    raise TypeError(
                        "Expected PoemVersion instance or int, ", f"got {type(p_meta)}"
                    )

                if poem_obj.id in existing_poems:
                    entry.poems.remove(poem_obj)
                    changed = True

        # --- Session flush ---
        if changed:
            session.flush()

    def update_person_aliases(
        self,
        session: Session,
        person: Person,
        aliases: List[str],
        incremental: bool = True,
    ) -> None:
        """
        Update Aliases for a Person from metadata.

        Args:
            session (Session): Active SQLAlchemy session.
            person (Person): Person object whose aliases are to be updated.
            aliases (List[str]): List of aliases (strings).
            incremental (bool): Whether incremental/overwrite mode.

        Behavior:
            - Incremental mode:
                adds new relationships and/or removes explicitly listed items.
            - Overwrite mode:
                clears all existing relationships before adding new ones.
            - Calls session.flush() only if any changes were made

        Returns:
            None
        """
        # --- Failsafe ---
        if person.id is None:
            raise ValueError(
                "Person instance has no ID; must be persisted before linking."
            )

        # --- Normalize incoming aliases --
        norm_aliases = {md.normalize_str(a) for a in aliases if md.normalize_str(a)}

        if not incremental:
            for a in person.aliases:
                session.delete(a)
            for alias_norm in norm_aliases:
                session.add(Alias(alias=alias_norm, person=person))
            session.flush()
            return

        # Incremental: only add aliases that don't exist yet
        existing = {a.alias for a in person.aliases}
        for alias_norm in norm_aliases - existing:
            session.add(Alias(alias=alias_norm, person=person))

        if norm_aliases - existing:
            session.flush()

    def update_person_relationships(
        self,
        session: Session,
        person: Person,
        metadata: Dict[str, Any],
        incremental: bool = True,
    ) -> None:
        """
        Update relationships for a Person object in the database.

        Supports both incremental updates (defualt) and full overwrite.
        This function handles relationships only. No I/O or Markdown parsing.
        Prevents duplicates and ensures lookup tables are updated.

        Args:
            session (Session): Active SQLAlchemy session.
            person (Person): Entry ORM object to update relationships for.
            metadata (Dict[str, Any]): Normalized metadata containing:
                Expected keys (optional):
                    - events (List[Event or id])
                    - entries (List[Entry or id])
                Removal keys (optional):
                    - remove_events (List[Event or id])
                    - remove_entries (List[Entry or id])

        Behavior:
            - Incremental mode:
                adds new relationships and/or removes explicitly listed items.
            - Overwrite mode:
                clears all existing relationships before adding new ones.
            - Calls session.flush() only if any changes were made

        Returns:
            None

        Raises:
            TypeError: if values of metadata are not ORM objects nor int.
            ValueError: ORM instance is non-existent
        """
        # --- Failsafe ---
        if person.id is None:
            raise ValueError(
                "Person instance has no ID; must be persisted before linking."
            )

        # --- Relationship management ---
        changed: bool = False

        # -- Event --
        existing_events: Set[int] = {e.id for e in person.events}

        if not incremental:
            person.events.clear()
            changed = True

        # - Appending -
        for e_meta in metadata.get("events", []):
            if isinstance(e_meta, Event):
                event_obj = e_meta
                if event_obj.id is None:
                    raise ValueError(
                        "Event instance has no ID; ",
                        "must be persisted before linking.",
                    )
            elif isinstance(e_meta, int):
                event_obj = session.get(Event, e_meta)
                if event_obj is None:
                    raise ValueError(f"No Event found with id:{e_meta}")
            else:
                raise TypeError(
                    "Expected Event instance or int, ", f"got {type(e_meta)}"
                )

            if event_obj.id not in existing_events:
                person.events.append(event_obj)
                changed = True

        # - Removal -
        if incremental:
            for e_meta in metadata.get("remove_events", []):
                if isinstance(e_meta, Event):
                    event_obj = e_meta
                    if event_obj.id is None:
                        raise ValueError(
                            "Event instance has no ID; ",
                            "must be persisted before linking.",
                        )
                elif isinstance(e_meta, int):
                    event_obj = session.get(Event, e_meta)
                    if event_obj is None:
                        raise ValueError(f"No Event found with id:{e_meta}")
                else:
                    raise TypeError(
                        "Expected Event instance or int, ", f"got {type(e_meta)}"
                    )

                if event_obj.id in existing_events:
                    person.events.remove(event_obj)
                    changed = True

        # -- Entry --
        existing_entries: Set[int] = {e.id for e in person.entries}

        if not incremental:
            person.entries.clear()
            changed = True

        # - Appending -
        for e_meta in metadata.get("entries", []):
            if isinstance(e_meta, Entry):
                entry_obj = e_meta
                if entry_obj.id is None:
                    raise ValueError(
                        "Entry instance has no ID; ",
                        "must be persisted before linking.",
                    )
            elif isinstance(e_meta, int):
                entry_obj = session.get(Entry, e_meta)
                if entry_obj is None:
                    raise ValueError(f"No Entry found with id:{e_meta}")
            else:
                raise TypeError(
                    "Expected Entry instance or int, ", f"got {type(e_meta)}"
                )

            if entry_obj.id not in existing_entries:
                person.entries.append(entry_obj)
                changed = True

        # - Removal -
        if incremental:
            for e_meta in metadata.get("remove_entries", []):
                if isinstance(e_meta, Entry):
                    entry_obj = e_meta
                    if entry_obj.id is None:
                        raise ValueError(
                            "Entry instance has no ID; ",
                            "must be persisted before linking.",
                        )
                elif isinstance(e_meta, int):
                    entry_obj = session.get(Entry, e_meta)
                    if entry_obj is None:
                        raise ValueError(f"No Entry found with id:{e_meta}")
                else:
                    raise TypeError(
                        "Expected Entry instance or int, ", f"got {type(e_meta)}"
                    )

                if entry_obj.id in existing_entries:
                    person.entries.remove(entry_obj)
                    changed = True

        if changed:
            session.flush()

    def update_event_relationships(
        self,
        session: Session,
        event: Event,
        metadata: Dict[str, Any],
        incremental: bool = True,
    ) -> None:
        """
        Update relationships for a Event object in the database.

        Supports both incremental updates (defualt) and full overwrite.
        This function handles relationships only. No I/O or Markdown parsing.
        Prevents duplicates and ensures lookup tables are updated.

        Args:
            session (Session): Active SQLAlchemy session.
            event (Event): Entry ORM object to update relationships for.
            metadata (Dict[str, Any]): Normalized metadata containing:
                Expected keys (optional):
                    - entries (List[Entry or id])
                    - people (List[Person or id])
                Removal keys (optional):
                    - remove_entries (List[Entry or id])
                    - remove_people (List[People or id])

        Behavior:
            - Incremental mode:
                adds new relationships and/or removes explicitly listed items.
            - Overwrite mode:
                clears all existing relationships before adding new ones.
            - Calls session.flush() only if any changes were made

        Returns:
            None

        Raises:
            TypeError: if values of metadata are not ORM objects nor int.
            ValueError: ORM instance is non-existent
        """
        # --- Failsafe ---
        if event.id is None:
            raise ValueError(
                "Event instance has no ID; must be persisted before linking."
            )

        # --- Relationship management ---
        changed: bool = False

        # -- Entry --
        existing_entries: Set[int] = {e.id for e in event.entries}

        if not incremental:
            event.entries.clear()
            changed = True

        # - Appending -
        for e_meta in metadata.get("entries", []):
            if isinstance(e_meta, Entry):
                entry_obj = e_meta
                if entry_obj.id is None:
                    raise ValueError(
                        "Entry instance has no ID; ",
                        "must be persisted before linking.",
                    )
            elif isinstance(e_meta, int):
                entry_obj = session.get(Entry, e_meta)
                if entry_obj is None:
                    raise ValueError(f"No Entry found with id:{e_meta}")
            else:
                raise TypeError(
                    "Expected Entry instance or int, ", f"got {type(e_meta)}"
                )

            if entry_obj.id not in existing_entries:
                event.entries.append(entry_obj)
                changed = True

        # - Removal -
        if incremental:
            for e_meta in metadata.get("remove_entries", []):
                if isinstance(e_meta, Entry):
                    entry_obj = e_meta
                    if entry_obj.id is None:
                        raise ValueError(
                            "Entry instance has no ID; ",
                            "must be persisted before linking.",
                        )
                elif isinstance(e_meta, int):
                    entry_obj = session.get(Entry, e_meta)
                    if entry_obj is None:
                        raise ValueError(f"No Entry found with id:{e_meta}")
                else:
                    raise TypeError(
                        "Expected Entry instance or int, ", f"got {type(e_meta)}"
                    )

                if entry_obj.id in existing_entries:
                    event.entries.remove(entry_obj)
                    changed = True

        # -- Person --
        existing_people: Set[int] = {p.id for p in event.people}

        if not incremental:
            event.people.clear()
            changed = True

        # - Appending -
        for p_meta in metadata.get("people", []):
            if isinstance(p_meta, Person):
                person_obj = p_meta
                if person_obj.id is None:
                    raise ValueError(
                        "Person instance has no ID; ",
                        "must be persisted before linking.",
                    )
            elif isinstance(p_meta, int):
                person_obj = session.get(Person, p_meta)
                if person_obj is None:
                    raise ValueError(f"No Person found with id:{p_meta}")
            else:
                raise TypeError(
                    "Expected Person instance or int, ", f"got {type(p_meta)}"
                )

            if person_obj.id not in existing_people:
                event.people.append(person_obj)
                changed = True

        # - Removal -
        if incremental:
            for p_meta in metadata.get("remove_people", []):
                if isinstance(p_meta, Person):
                    person_obj = p_meta
                    if person_obj.id is None:
                        raise ValueError(
                            "Person instance has no ID; ",
                            "must be persisted before linking.",
                        )
                elif isinstance(p_meta, int):
                    person_obj = session.get(Person, p_meta)
                    if person_obj is None:
                        raise ValueError(f"No Person found with id:{p_meta}")
                else:
                    raise TypeError(
                        "Expected Person instance or int, ", f"got {type(p_meta)}"
                    )

                if person_obj.id in existing_people:
                    event.people.remove(person_obj)
                    changed = True

        if changed:
            session.flush()

    # --- Manuscript ---
    def create_or_update_manuscript_entry(
        self, session: Session, entry: Entry, manuscript_data: Dict[str, Any]
    ) -> None:
        """
        Create or update a ManuscriptEntry associated with a given Entry.

        This function handles the one-to-one relationship between Entry and
        ManuscriptEntry. If a ManuscriptEntry already exists for the Entry,
        it will update its fields. Otherwise, it will create a new row.

        Args:
            session (Session): Active SQLAlchemy session.
            entry (Entry): The Entry instance to link to.
            manuscript_data (Dict[str, Any]): Metadata for the ManuscriptEntry,
                 keys include (optional):
                    - 'status' (ManuscriptStatus): Status of the Entry.
                    - 'edited' (bool): Whether the entry has been edited.
                    - 'themes' (str): Themes (relationship).

        Returns:
            None
        """
        manuscript: Optional[ManuscriptEntry] = entry.manuscript
        status: Optional[ManuscriptStatus] = manuscript_data.get("status")
        edited: Optional[bool] = manuscript_data.get("edited")
        notes: Optional[str] = md.normalize_str(manuscript_data.get("notes"))
        themes_list: List[str] = manuscript_data.get("themes", [])

        if manuscript:
            # -- Status --
            if status is not None:
                manuscript.status = status
            # -- Edited --
            if edited is not None:
                manuscript.edited = edited
            # -- Notes --
            if notes is not None:
                manuscript.notes = notes
        else:
            manuscript = ManuscriptEntry(
                entry=entry,
                status=status,
                edited=edited,
                notes=notes,
            )
            session.add(manuscript)
        session.flush()

        # -- Themes --
        if themes_list:
            norm_themes = {
                md.normalize_str(t) for t in themes_list if md.normalize_str(t)
            }

            # --- Overwrite mode (replace all) ---
            manuscript.themes.clear()
            session.flush()  # optional, but keeps DB in sync

            for theme_name in norm_themes:
                # Either get existing Theme or create a new one
                theme_obj = self._get_or_create_lookup_item(
                    session, Theme, {"theme": theme_name}
                )
                manuscript.themes.append(theme_obj)

            session.flush()

    def create_or_update_manuscript_person(
        self, session: Session, person: Person, manuscript_data: Dict[str, Any]
    ):
        """
        Create or update a ManuscriptPerson associated with a given Person.

        This function handles the one-to-one relationship between Person and
        ManuscriptPerson. If a ManuscriptPerson already exists for the Person,
        it will update its fields. Otherwise, it will create a new row.

        Args:
            session (Session): Active SQLAlchemy session.
            person (Person): The Person instance to link to.
            manuscript_data (Dict[str, Any]): Metadata for the ManuscriptPerson,
                 keys include (optional):
                    - 'character' (str): Pseudonym used in the manuscript

        Returns:
            ManuscriptPerson: The created or updated ManuscriptPerson instance.
        """
        manuscript = person.manuscript
        character: Optional[str] = md.normalize_str(manuscript_data.get("character"))
        if manuscript:
            # -- Character --
            if character is not None:
                manuscript.character = character
        else:
            manuscript = ManuscriptPerson(
                person=person,
                character=character,
            )
            session.add(manuscript)
        session.flush()

    def create_or_update_manuscript_event(
        self, session: Session, event: Event, manuscript_data: Dict[str, Any]
    ):
        """
        Create or update a ManuscriptEvent associated with a given Event.

        This function handles the one-to-one relationship between Event and
        ManuscriptEvent. If a ManuscriptEvent already exists for the Event,
        it will update its fields. Otherwise, it will create a new row.

        Args:
            session (Session): Active SQLAlchemy session.
            event (Event): The Event instance to link to.
            manuscript_data (Dict[str, Any]): Metadata for the ManuscriptEvent,
                 keys include (optional):
                    - 'arc' (str): Name of the arc
                    - 'notes' (str): Qualitative notes regarding the event

        Returns:
            ManuscriptEvent: The created or updated ManuscriptEvent instance.
        """
        manuscript = event.manuscript
        arc: Optional[str] = md.normalize_str(manuscript_data.get("arc"))
        notes: Optional[str] = md.normalize_str(manuscript_data.get("notes"))

        if manuscript:
            # -- Character --
            if notes is not None:
                manuscript.notes = notes
        else:
            manuscript = ManuscriptEvent(
                event=event,
                notes=notes,
            )
            session.add(manuscript)
        session.flush()

        # -- Arc --
        if arc:
            arc_obj = self._get_or_create_lookup_item(session, Arc, {"arc": arc})
            manuscript.arc = arc_obj

        session.flush()

    # --- Cleanup ---
    def _cleanup_unused(
        self, session: Session, model_class: Type[Base], relationship_attr: str
    ) -> int:
        """
        Generic helper to delete unused objects from a lookup table.

        Args:
            session (Session): Active SQLAlchemy session
            model_class (Type[Base]): ORM model to query
            relationship_attr (str): Name of relationship attribute to check

        Returns:
            int: Number of rows deleted
        """
        unused = (
            session.query(model_class)
            .filter(~getattr(model_class, relationship_attr).any())
            .all()
        )
        count = len(unused)
        for obj in unused:
            session.delete(obj)

        session.flush()
        return count

    # -- Specific cleanup functions --
    def cleanup_unused_tags(self, session: Session) -> int:
        return self._cleanup_unused(session, Tag, "entries")

    def cleanup_unused_locations(self, session: Session) -> int:
        return self._cleanup_unused(session, Location, "entries")

    def cleanup_unused_dates(self, session: Session) -> int:
        return self._cleanup_unused(session, MentionedDate, "entries")

    def cleanup_unused_reference_types(self, session: Session) -> int:
        return self._cleanup_unused(session, ReferenceType, "references")

    def cleanup_unused_themes(self, session: Session) -> int:
        return self._cleanup_unused(session, Theme, "entries")

    # -- Content cleanup (explicit opt-in) --
    def cleanup_orphan_references(self, session: Session) -> int:
        return self._cleanup_unused(session, Reference, "entries")

    def cleanup_orphan_events(self, session: Session) -> int:
        # Events are special: they can be linked to entries OR people
        unused = (
            session.query(Event).filter(~Event.entries.any(), ~Event.people.any()).all()
        )
        count = len(unused)
        for obj in unused:
            session.delete(obj)
        session.flush()
        return count

    def cleanup_orphan_arcs(self, session: Session) -> int:
        return self._cleanup_unused(session, Arc, "events")

    # -- Convenience wrapper --
    def cleanup_all_metadata(self, session: Session) -> dict[str, int]:
        """
        Run safe cleanup passes (tags, locations, dates, reference types).
        Returns counts of deleted objects.
        """
        return {
            "dates": self.cleanup_unused_dates(session),
            "locations": self.cleanup_unused_locations(session),
            "tags": self.cleanup_unused_tags(session),
            "reference_types": self.cleanup_unused_reference_types(session),
        }

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
                "tags": [tag.tag for tag in entry.tags],
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

            return stats
