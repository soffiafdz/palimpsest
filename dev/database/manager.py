#!/usr/bin/env python3
"""
manager.py
--------------------
Database manager for the Palimpsest medatata system.

Provides the PalimpsestDB class for interacting with the SQLite database.
Handles:
    - Initialization of the database engine and sessionmaker
    - CRUD operations for all ORM models
    - Handle queries and convenience methods
    - Relationship management for all model types
    - Type-safe and timezone-aware handling of datetime fields
    - Comprehensive logging system with rotation
    - Automated backup and recovery system
    - Database health monitoring and maintenance
    - Data export functionality

Notes
==============
- Migrations are handled externally via Alembic
- All datetime fields are UTC-aware
- Backup retention policies are configurable
- Logs are rotatedd automatically to prevent disk bloat
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import time
from contextlib import contextmanager
from datetime import date, datetime, timezone

from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union, List, Type, TypeVar

# --- Third party ---
from sqlalchemy import create_engine, Engine, insert
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import IntegrityError, OperationalError

from alembic.config import Config
from alembic import command
from alembic.runtime.migration import MigrationContext

# --- Local imports ---
from dev.core.backup_manager import BackupManager
from dev.core.exceptions import DatabaseError, ValidationError
from dev.core.paths import ROOT
from dev.core.validators import DataValidator
from dev.core.logging_manager import PalimpsestLogger
from dev.utils import md, fs
from .models import (
    Base,
    Entry,
    MentionedDate,
    City,
    Location,
    Person,
    Alias,
    Reference,
    ReferenceSource,
    Event,
    Poem,
    PoemVersion,
    Tag,
)
from .models_manuscript import (
    ManuscriptStatus,
    ManuscriptEntry,
    ManuscriptEvent,
    ManuscriptPerson,
    Arc,
    Theme,
)

from .decorators import (
    handle_db_errors,
    log_database_operation,
    validate_metadata,
)
from .health_monitor import HealthMonitor
from .export_manager import ExportManager
from .query_analytics import QueryAnalytics
from .relationship_manager import RelationshipManager, HasId


T = TypeVar("T", bound=HasId)


#
# ----- Main Database Manager -----
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

    # ---- Initialization ----
    def __init__(
        self,
        db_path: Union[str, Path],
        alembic_dir: Union[str, Path],
        log_dir: Optional[Union[str, Path]] = None,
        backup_dir: Optional[Union[str, Path]] = None,
        enable_auto_backup: bool = True,
    ) -> None:
        """
        Initialize database engine and session factory.

        Args:
            db_path (str | Path): Path to the SQLite  file.
            alembic_dir (str | Path): Path to the Alembic directory.
            log_dir (str | Path): Directory for log files (optional)
            backup_dir (str | Path): Directory for backups (optional)
            enable_auto_backup (bool): Whether to enable automatic backups

        """
        self.db_path = Path(db_path).expanduser().resolve()
        self.alembic_dir = Path(alembic_dir).expanduser().resolve()

        # --- Logging ---
        if log_dir:
            self.log_dir = Path(log_dir).expanduser().resolve() / "system"
            self.logger = PalimpsestLogger(
                self.log_dir,
                component_name="database",
            )
        else:
            self.logger = None

        # --- Backup system ---
        if backup_dir:
            self.backup_dir = Path(backup_dir).expanduser().resolve()
            self.backup_manager = BackupManager(
                self.db_path,
                self.backup_dir,
                logger=self.logger,
            )
            # if enable_auto_backup:
            #     self.backup_manager.auto_backup()
        else:
            self.backup_manager = None

        # Initialize service components
        self.health_monitor = HealthMonitor(self.logger)
        self.export_manager = ExportManager(self.logger)
        self.query_analytics = QueryAnalytics(self.logger)

        # Initialize database
        self._setup_engine()

        # Auto-backup if enabled
        if enable_auto_backup and self.backup_manager:
            self.backup_manager.auto_backup()

    def _setup_engine(self) -> None:
        """Initialize database engine ans session factory."""
        try:
            if self.logger:
                self.logger.log_operation(
                    "database_init_start",
                    {
                        "db_path": str(self.db_path),
                        "alembic_dir": str(self.alembic_dir),
                    },
                )

            self.engine: Engine = create_engine(
                f"sqlite:///{self.db_path}",
                echo=False,
                future=True,
                pool_pre_ping=True,
            )

            self.SessionLocal: sessionmaker = sessionmaker(
                bind=self.engine,
                autoflush=True,
                expire_on_commit=False,
                future=True,
            )

            self.alembic_cfg: Config = self._setup_alembic()
            self.initialize_schema()

            if self.logger:
                self.logger.log_operation("database_init_complete", {"success": True})

        except Exception as e:
            if self.logger:
                self.logger.log_error(e, {"operation": "database_init"})
            raise DatabaseError(f"Database initialization failed: {e}")

    # ---- Session Management ----
    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around operations with logging."""
        session = self.SessionLocal()
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        if self.logger:
            self.logger.log_debug("session_start", {"session_id": session_id})

        try:
            yield session
            if session.dirty or session.new or session.deleted:
                session.commit()
                if self.logger:
                    self.logger.log_debug("session_commit", {"session_id": session_id})

        except Exception as e:
            session.rollback()
            if self.logger:
                self.logger.log_error(
                    e, {"operation": "session_rollback", "session_id": session_id}
                )
            raise
        finally:
            session.close()
            if self.logger:
                self.logger.log_debug("session_close", {"session_id": session_id})

    def get_session(self) -> Session:
        """Create and return a new SQLAlchemy session."""
        return self.SessionLocal()

    @contextmanager
    def transaction(self):
        """Context manager for database transactions with logging."""
        with self.session_scope() as session:
            yield session

    # ---- Alembic setup ----
    def _setup_alembic(self) -> Config:
        """Setup Alembic configuration."""
        try:
            if self.logger:
                self.logger.log_debug("Setting up Alembic configuration...")

            alembic_cfg: Config = Config(str(ROOT / "alembic.ini"))
            alembic_cfg.set_main_option("script_location", str(self.alembic_dir))
            alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{self.db_path}")
            alembic_cfg.set_main_option(
                "file_template",
                "%%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d_%%(slug)s",
            )

            if self.logger:
                self.logger.log_debug("Alembic configuration setup complete")
            return alembic_cfg
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, {"operation": "setup_alembic"})
            raise DatabaseError(f"Alembic configuration failed: {e}")

    @handle_db_errors
    @log_database_operation("init_alembic")
    def init_alembic(self) -> None:
        """
        Initialize Alembic in the project directory.

        Actions:
            Creates Alembic directory with standard structure
            Updates alembic/env.py to import Palimpsest Base metadata
            Prints instructions for first migration
        """
        try:
            if not self.alembic_dir.is_dir():
                command.init(self.alembic_cfg, str(self.alembic_dir))
                self._update_alembic_env()
            else:
                if self.logger:
                    self.logger.log_debug(
                        f"Alembic already initialized in {self.alembic_dir}"
                    )
        except Exception as e:
            raise DatabaseError(f"Alembic initialization failed: {e}")

    def _update_alembic_env(self) -> None:
        """Update the generated alembic/env.py to import Palimpsest models."""
        env_path = self.alembic_dir / "env.py"

        try:
            if env_path.exists():
                content = env_path.read_text(encoding="utf-8")

                import_line = "from dev.database.models import Base\n"
                target_metadata_line = "target_metadata = Base.metadata"

                # Replace the target_metadata = None line
                if "target_metadata = None" in content:
                    updated_content = content.replace(
                        "target_metadata = None",
                        f"{import_line}\n{target_metadata_line}",
                    )
                    env_path.write_text(updated_content, encoding="utf-8")
                    if self.logger:
                        self.logger.log_operation(
                            "alembic_env_updated", {"env_path": str(env_path)}
                        )
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, {"operation": "update_alembic_env"})
            raise DatabaseError(f"Could not update Alembic environment: {e}")

    @handle_db_errors
    @log_database_operation("initialize_schema")
    def initialize_schema(self) -> None:
        """
        Initialize database - create tables if needed and run migrations.

        Actions:
            Checks if the database is fresh (no tables)
            If fresh,
                creates all tables from the ORM models
                stamps the Alembic revision to head
            If not,
                runs pending migrations to update schema
        """
        try:
            with self.engine.connect() as conn:
                inspector = self.engine.dialect.get_table_names(conn)
                is_fresh_db: bool = len(inspector) == 0

            if is_fresh_db:
                Base.metadata.create_all(bind=self.engine)
                try:
                    command.stamp(self.alembic_cfg, "head")
                    if self.logger:
                        self.logger.log_operation(
                            "fresh_database_created",
                            {"tables_created": len(Base.metadata.tables)},
                        )
                except Exception as e:
                    if self.logger:
                        self.logger.log_error(e, {"operation": "stamp_database"})
            else:
                self.upgrade_database()
                if self.logger:
                    self.logger.log_operation(
                        "existing_database_migrated",
                        {"table_count": len(inspector)},
                    )

        except Exception as e:
            raise DatabaseError(f"Could not initialize database: {e}")

    @handle_db_errors
    @log_database_operation("upgrade_database")
    def upgrade_database(self, revision: str = "head") -> None:
        """
        Upgrade the database schema to the specified Alembic revision.

        Args:
            revision (str, optional):
                The target revision to upgrade to.
                Defaults to 'head' (latest revision).
        """
        try:
            command.upgrade(self.alembic_cfg, revision)
        except Exception as e:
            raise DatabaseError(f"Database upgrade failed: {e}")

    @handle_db_errors
    @log_database_operation("create_migration")
    def create_migration(self, message: str) -> str:
        """
        Create a new Alembic migration.

        Args:
            message (str): Description of the migration.
        Returns:
            revision
        """
        try:
            result = command.revision(
                self.alembic_cfg, message=message, autogenerate=True
            )

            # Handle both single Script and List[Script] return types
            if isinstance(result, list):
                if not result or result[0] is None:
                    raise DatabaseError("Migration creation returned no scripts")
                script = result[0]
            else:
                # Single Script object
                if result is None:
                    raise DatabaseError("Migration creation returned no script")
                script = result

            # Access revision attribute
            if not hasattr(script, "revision") or script.revision is None:
                raise DatabaseError("Migration script has no revision")

            return script.revision

        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(f"Migration creation failed: {e}")

    @handle_db_errors
    @log_database_operation("downgrade_database")
    def downgrade_database(self, revision: str) -> None:
        """
        Downgrade the database schema to a specified Alembic revision.

        Args:
            revision (str): The target revision to downgrade to.
        """
        try:
            command.downgrade(self.alembic_cfg, revision)
        except Exception as e:
            raise DatabaseError(f"Database downgrade to {revision} failed: {e}")

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
            with self.engine.connect() as conn:
                context = MigrationContext.configure(conn)
                current_rev = context.get_current_revision()

            return {
                "current_revision": current_rev,
                "status": "up_to_date" if current_rev else "needs_migration",
            }
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, {"operation": "get_migration_history"})
            return {"error": str(e)}

    # ----  Helper methods ----
    def _execute_with_retry(
        self,
        operation: Callable,
        max_retries: int = 3,
        retry_delay: float = 0.1,
    ) -> Any:
        """
        Execute database operation with retry on lock.

        Args:
            session: SQLAlchemy session
            operation: Callable that performs the operation
            max_retries: Maximum number of retry attempts
            retry_delay: Base delay between retries (exponential backoff)

        Returns:
            Result of the operation

        Raises:
            OperationalError: If all retries exhausted
        """
        for attempt in range(max_retries):
            try:
                return operation()
            except OperationalError as e:
                error_msg = str(e).lower()

                if (
                    "locked" in error_msg or "busy" in error_msg
                ) and attempt < max_retries - 1:
                    wait_time = retry_delay * (2**attempt)  # Exponential backoff

                    if self.logger:
                        self.logger.log_debug(
                            f"Database locked, retrying in {wait_time}s",
                            {"attempt": attempt + 1, "max_retries": max_retries},
                        )

                    time.sleep(wait_time)
                    continue

                # Re-raise the exception if not a lock error or retries exhausted
                raise

        # This should never be reached due to the raise in the except block
        raise DatabaseError("Retry loop completed without success")

    def _resolve_object(
        self, session: Session, item: Union[T, int], model_class: Type[T]
    ) -> T:
        """Resolve an item to an ORM object."""
        return RelationshipManager._resolve_object(session, item, model_class)

    @handle_db_errors
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
        # Try to get existing first
        obj = session.query(model_class).filter_by(**lookup_fields).first()
        if obj:
            return obj

        # Create new object
        fields = lookup_fields.copy()
        if extra_fields:
            fields.update(extra_fields)

        try:
            obj = model_class(**fields)
            session.add(obj)
            session.flush()
            return obj
        except IntegrityError:
            # Handle race condition - another process might have created it
            session.rollback()
            obj = session.query(model_class).filter_by(**lookup_fields).first()
            if obj:
                return obj
            raise

    # ---- CRUD Operations for Entries ----
    @handle_db_errors
    @log_database_operation("create_entry")
    @validate_metadata(["date", "file_path"])
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
                    - cities (List[City|int])
                    - locations (List[Location|int])
                    - people (List[Person|int])
                    - references (List[Reference|int])
                    - events (List[Event|int])
                    - poems (List[Poem|int])
                    - tags (List[str])
        Returns:
            Entry: The newly created Entry ORM object.
        """
        # --- Required fields ---
        # parsed_date = md.parse_date(metadata["date"])
        parsed_date = DataValidator.normalize_date(metadata["date"])
        if not parsed_date:
            raise ValueError(f"Invalid date format: {metadata['date']}")

        # file_path = DataValidator.normalize_string(metadata.get("file_path"))
        file_path = DataValidator.normalize_string(metadata["file_path"])
        if not file_path:
            raise ValueError(f"Invalid file_path: {metadata['file_path']}")

        # --- file_path uniqueness check ---
        existing = session.query(Entry).filter_by(file_path=file_path).first()
        if existing:
            raise ValidationError(f"Entry already exists for file_path: {file_path}")

        # --- If hash doesn't exist, create it ---
        # file_hash = DataValidator.normalize_string(metadata.get("file_hash"))
        file_hash = DataValidator.normalize_string((metadata.get("file_hash")))
        if not file_hash:
            file_hash = fs.get_file_hash(file_path)

        # --- Create Entry ---
        def _do_create():
            entry = Entry(
                date=parsed_date,
                file_path=file_path,
                file_hash=file_hash,
                word_count=DataValidator.normalize_int(metadata.get("word_count")),
                reading_time=DataValidator.normalize_float(
                    metadata.get("reading_time")
                ),
                epigraph=DataValidator.normalize_string(metadata.get("epigraph")),
                notes=DataValidator.normalize_string(metadata.get("notes")),
            )
            session.add(entry)
            session.flush()
            return entry

        entry = self._execute_with_retry(_do_create)

        # --- Relationships ---
        self._update_entry_relationships(session, entry, metadata)
        return entry

    def _update_entry_relationships(
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
            person (Person): Entry ORM object to update relationships for.
            metadata (Dict[str, Any]): Normalized metadata containing:
                Expected keys (optional):
                    - dates (List[MentionedDate or id])
                    - cities (List[City or id])
                    - locations (List[Location or id])
                    - people (List[Person or id])
                    - references (List[Reference or id])
                    - events (List[Event or id])
                    - poems (List[Poem or id])
                Removal keys (optional):
                    - remove_dates (List[MentionedDate or id])
                    - remove_cities (List[City or id])
                    - remove_locations (List[Location or id])
                    - remove_people (List[Person or id])
                    - remove_references (List[Reference or id])
                    - remove_events (List[Event or id])
                    - remove_poems (List[Poem or id])

        Behavior:
            - Incremental mode:
                adds new relationships and/or removes explicitly listed items.
            - Overwrite mode:
                clears all existing relationships before adding new ones.
            - Calls session.flush() only if any changes were made
        """
        if "dates" in metadata:
            if not incremental:
                entry.dates.clear()
                session.flush()
            self._process_mentioned_dates(session, entry, metadata["dates"])

        # --- Many to many ---
        many_to_many_configs = [
            ("cities", "cities", City),
            ("locations", "locations", Location),
            ("people", "people", Person),
            ("events", "events", Event),
        ]

        for rel_name, meta_key, model_class in many_to_many_configs:
            if meta_key in metadata:
                RelationshipManager.update_many_to_many(
                    session=session,
                    parent_obj=entry,
                    relationship_name=rel_name,
                    items=metadata[meta_key],
                    model_class=model_class,
                    incremental=incremental,
                    remove_items=metadata.get(f"remove_{meta_key}", []),
                )

        # --- One to many ---
        one_to_many_configs = [
            ("references", Reference, "entry_id"),
            ("poems", PoemVersion, "entry_id"),
        ]

        for meta_key, model_class, foreign_key_attr in one_to_many_configs:
            if meta_key in metadata:
                RelationshipManager.update_one_to_many(
                    session=session,
                    parent_obj=entry,
                    items=metadata[meta_key],
                    model_class=model_class,
                    foreign_key_attr=foreign_key_attr,
                    incremental=incremental,
                    remove_items=metadata.get(f"remove_{meta_key}", []),
                )

        # --- Tags ---
        # They're strings, not objects
        if "tags" in metadata:
            self._update_entry_tags(session, entry, metadata["tags"], incremental)

        # --- Related entries ---
        # Handle related entries (uni-directional relationships)
        if "related_entries" in metadata:
            self._process_related_entries(session, entry, metadata["related_entries"])

        # --- Manuscript ---
        if "manuscript" in metadata:
            self.create_or_update_manuscript_entry(
                session, entry, metadata["manuscript"]
            )

    def _process_mentioned_dates(
        self,
        session: Session,
        entry: Entry,
        dates_data: List[Union[str, Dict[str, Any]]],
    ) -> None:
        """Process mentioned dates with optional context."""
        existing_date_ids = {d.id for d in entry.dates}

        for date_item in dates_data:
            if isinstance(date_item, str):
                # Simple date string
                date_obj = date.fromisoformat(date_item)
                mentioned_date = self._get_or_create_lookup_item(
                    session, MentionedDate, {"date": date_obj}
                )
            elif isinstance(date_item, dict) and "date" in date_item:
                # Date with context
                date_obj = date.fromisoformat(date_item["date"])
                context = date_item.get("context")
                mentioned_date = self._get_or_create_lookup_item(
                    session, MentionedDate, {"date": date_obj, "context": context}
                )
            else:
                continue

            if mentioned_date.id not in existing_date_ids:
                entry.dates.append(mentioned_date)

    def _update_entry_tags(
        self,
        session: Session,
        entry: Entry,
        tags: List[str],
        incremental: bool = True,
    ) -> None:
        """
        Update Tags for an Entry from metadata.

        Args:
            session (Session): Active SQLAlchemy session.
            entry (Entry): Entry object whose tags are to be updated.
            tags (List[str]): List of tags (strings).
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
        if entry.id is None:
            raise ValueError("Entry must be persisted before linking tags")

        # --- Normalize incoming tags --
        norm_tags = {DataValidator.normalize_string(t) for t in tags}

        if not incremental:
            entry.tags.clear()
            session.flush()

        existing_tags = {tag.tag for tag in entry.tags}

        # Add new tags
        for tag_name in norm_tags - existing_tags:
            tag_obj = self._get_or_create_lookup_item(session, Tag, {"tag": tag_name})
            entry.tags.append(tag_obj)

        if norm_tags - existing_tags:
            session.flush()

    def _process_related_entries(
        self, session: Session, entry: Entry, related_dates: List[str]
    ) -> None:
        """Process related entry connections (uni-directional)."""
        for date_str in related_dates:
            try:
                related_date = date.fromisoformat(date_str)
                related_entry = (
                    session.query(Entry).filter_by(date=related_date).first()
                )
                if related_entry and related_entry.id != entry.id:
                    entry.related_entries.append(related_entry)
            except ValueError:
                # Invalid date format, skip
                continue

    @handle_db_errors
    @log_database_operation("update_entry")
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
                      date, file_path,
                      word_count, reading_time, epigraph, notes
                    - Relationship keys:
                      dates, cities, locations, people, references, events, poems, tags

        Returns:
            Entry: The updated Entry ORM object (still attached to session).

        Notes: version_hash is automatically updated if content changes
        """
        # --- Ensure existance ---
        db_entry = session.get(Entry, entry.id)
        if db_entry is None:
            raise ValueError(f"Entry with id={entry.id} does not exist")

        # --- Attach to session ---
        entry = session.merge(db_entry)

        # --- Update scalar fields ---
        def _do_update():
            field_updates = {
                "date": DataValidator.normalize_date,
                "file_path": DataValidator.normalize_string,
                "file_hash": DataValidator.normalize_string,
                "word_count": DataValidator.normalize_int,
                "reading_time": DataValidator.normalize_float,
                "epigraph": DataValidator.normalize_string,
                "notes": DataValidator.normalize_string,
            }

            for field, normalizer in field_updates.items():
                if field not in metadata:
                    continue

                value = normalizer(metadata[field])
                if value is not None or field in ["epigraph", "notes"]:
                    if field == "file_path" and value is not None:
                        file_hash = fs.get_file_hash(value)
                        setattr(entry, "file_hash", file_hash)
                    setattr(entry, field, value)

            session.flush()
            return entry

        entry = self._execute_with_retry(_do_update)

        # --- Update relationships ---
        self._update_entry_relationships(session, entry, metadata)
        return entry

    @handle_db_errors
    @log_database_operation("get_entry")
    def get_entry(
        self, session: Session, entry_date: Union[str, date]
    ) -> Optional[Entry]:
        """Get an entry by date."""
        if isinstance(entry_date, str):
            entry_date = date.fromisoformat(entry_date)

        return session.query(Entry).filter_by(date=entry_date).first()

    @handle_db_errors
    @log_database_operation("delete_entry")
    def delete_entry(self, session: Session, entry: Entry) -> None:
        """Delete an entry and its associated data."""

        def _do_delete():
            session.delete(entry)
            session.flush()

        self._execute_with_retry(_do_delete)

    @handle_db_errors
    @log_database_operation("bulk_create_entries")
    def bulk_create_entries(
        self,
        session: Session,
        entries_metadata: List[Dict[str, Any]],
        batch_size: int = 100,
    ) -> List[int]:
        """
        Create multiple entries efficiently using bulk operations.

        Args:
            session: SQLAlchemy session
            entries_metadata: List of metadata dictionaries for entries
            batch_size: Number of entries to insert per batch

        Returns:
            List of created entry IDs
        """
        created_ids = []

        # Process in batches
        for i in range(0, len(entries_metadata), batch_size):
            batch = entries_metadata[i : i + batch_size]

            # Prepare mappings for bulk insert
            mappings = []
            for metadata in batch:
                parsed_date = DataValidator.normalize_date(metadata["date"])
                file_path = DataValidator.normalize_string(metadata["file_path"])
                file_hash = DataValidator.normalize_string(metadata.get("file_hash"))

                if file_path and not file_hash:
                    file_hash = fs.get_file_hash(file_path)

                mappings.append(
                    {
                        "date": parsed_date,
                        "file_path": file_path,
                        "file_hash": file_hash,
                        "word_count": DataValidator.normalize_int(
                            metadata.get("word_count")
                        ),
                        "reading_time": DataValidator.normalize_float(
                            metadata.get("reading_time")
                        ),
                        "epigraph": DataValidator.normalize_string(
                            metadata.get("epigraph")
                        ),
                        "notes": DataValidator.normalize_string(metadata.get("notes")),
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                )

            def _do_bulk_insert():
                # Use Core insert for bulk operations
                stmt = insert(Entry).values(mappings)
                session.execute(stmt)
                session.flush()

            self._execute_with_retry(_do_bulk_insert)

            # Get IDs of created entries
            dates = [m["date"] for m in mappings]
            created_entries = session.query(Entry).filter(Entry.date.in_(dates)).all()
            created_ids.extend([e.id for e in created_entries])

            if self.logger:
                self.logger.log_operation(
                    "bulk_create_batch",
                    {"batch_number": i // batch_size + 1, "count": len(batch)},
                )

        return created_ids

    # ---- City CRUD ----
    @handle_db_errors
    @log_database_operation("create_city")
    @validate_metadata(["city"])
    def create_city(self, session: Session, metadata: Dict[str, Any]) -> City:
        """
        Create a new City in the database with its associated relationships.

        This function does NOT handle file I/O or Markdown parsing. It assumes
        that `metadata` is already normalized (all dates as `datetime.date`,
        people, tags, events, etc. as strings or dicts).

        Args:
            session (Session): Active SQLAlchemy session
            metadata (Dict[str, Any]): Normalized metadata for the entry.
                Required keys:
                    - city (str)
                Optional keys:
                    - state_province (str)
                    - country (str)
                Relationship keys (optional):
                    - locations (List[Location|int])
                    - entries (List[Entry|int])

        Returns:
            City: The newly created City ORM object.
        """
        # --- Required fields ---
        city_name = DataValidator.normalize_string(metadata.get("city"))
        if not city_name:
            raise ValueError(f"Invalid name: {metadata['name']}")

        # --- Uniqueness check ---
        existing = session.query(City).filter_by(city=city_name).first()
        if existing:
            raise ValidationError(f"City already exists for: {city_name}")

        state = DataValidator.normalize_string(metadata.get("state_province"))
        country = DataValidator.normalize_string(metadata.get("country"))

        # --- Create Location ---
        city = City(
            city=city_name,
            state_province=state,
            country=country,
        )
        session.add(city)
        session.flush()

        # --- Relationships ---
        self._update_city_relationships(session, city, metadata)
        return city

    def _update_city_relationships(
        self,
        session: Session,
        city: City,
        metadata: Dict[str, Any],
        incremental: bool = True,
    ) -> None:
        """
        Update relationships for a City object in the database.

        Supports both incremental updates (defualt) and full overwrite.
        This function handles relationships only. No I/O or Markdown parsing.
        Prevents duplicates and ensures lookup tables are updated.

        Args:
            session (Session): Active SQLAlchemy session.
            person (Person): Entry ORM object to update relationships for.
            metadata (Dict[str, Any]): Normalized metadata containing:
                Expected keys (optional):
                    - locations (List[str]
                    - entries (List[Entry or id])
                Removal keys (optional):
                    - remove_locations (List[str])
                    - remove_entries (List[Entry or id])

        Behavior:
            - Incremental mode:
                adds new relationships and/or removes explicitly listed items.
            - Overwrite mode:
                clears all existing relationships before adding new ones.
            - Calls session.flush() only if any changes were made

        Returns:
            None
        """

        # --- Entries to many ---
        if "entries" in metadata or "remove_entries" in metadata:
            RelationshipManager.update_many_to_many(
                session=session,
                parent_obj=city,
                relationship_name="entries",
                items=metadata["entries"],
                model_class=Entry,
                incremental=incremental,
                remove_items=metadata.get("remove_entries", []),
            )

        # --- Aliases ---
        if "locations" in metadata or "remove_locations" in metadata:
            RelationshipManager.update_one_to_many(
                session=session,
                parent_obj=city,
                items=metadata["locations"],
                model_class=Location,
                foreign_key_attr="city_id",
                remove_items=metadata.get("remove_locations", []),
            )

    @handle_db_errors
    @log_database_operation("update_city")
    def update_city(
        self, session: Session, city: City, metadata: Dict[str, Any]
    ) -> City:
        """
        Update an existing City in the database and refresh its relationships.

        Does NOT perform file parsing. Accepts pre-normalized metadata.
        Clears previous relationships before adding new ones.

        Args:
            session (Session): Active SQLAlchemy session
            city (City): Existing Location ORM object to update.
            metadata (Dict[str, Any]): Normalized metadata as in `create_entry`.
                Keys may include:
                    - Core fields:
                      city, state_province, country
                Relationship keys (optional):
                    - entries (List[Entry|int])
                    - locations (List[Location|int])

        Returns:
            City: The updated City ORM object (still attached to session).
        """
        # --- Ensure existance ---
        db_city = session.get(City, city.id)
        if db_city is None:
            raise ValueError(f"Location with id={city.id} does not exist")

        # --- Attach to session ---
        location = session.merge(db_city)

        # --- Update scalar fields ---
        field_updates = {
            "city": DataValidator.normalize_string,
            "state_province": DataValidator.normalize_string,
            "country": DataValidator.normalize_string,
        }

        for field, normalizer in field_updates.items():
            if field not in metadata:
                continue

            value = normalizer(metadata[field])
            if value is not None or field != "city":
                setattr(location, field, value)

        # --- Relationships ---
        self._update_city_relationships(session, city, metadata)
        return city

    @handle_db_errors
    @log_database_operation("get_city")
    def get_city(
        self,
        session: Session,
        city_name: str,
    ) -> Optional[City]:
        """Get a city by name."""
        norm_name = DataValidator.normalize_string(city_name)
        if not norm_name:
            raise ValueError("Name must be given.")
        return session.query(City).filter_by(city=norm_name).first()

    @handle_db_errors
    @log_database_operation("delete_location")
    def delete_city(self, session: Session, city: City) -> None:
        """Delete a City and its associated data."""
        try:
            session.delete(city)
            session.flush()
        except Exception as e:
            raise DatabaseError(f"Failed to delete location: {e}")

    # ---- Location CRUD ----
    # TODO: Add _do_{task}() and _execute_with_retry() logic
    # for tasks: create_, update_, delete_
    # for Location, Person, Event, Poem, PoemVersion, Reference, ReferenceSource and Manuscript

    @handle_db_errors
    @log_database_operation("create_location")
    @validate_metadata(["name", "city"])
    def create_location(self, session: Session, metadata: Dict[str, Any]) -> Location:
        """
        Create a new Location in the database with its associated relationships.

        This function does NOT handle file I/O or Markdown parsing. It assumes
        that `metadata` is already normalized (all dates as `datetime.date`,
        people, tags, events, etc. as strings or dicts).

        Args:
            session (Session): Active SQLAlchemy session
            metadata (Dict[str, Any]): Normalized metadata for the entry.
                Required keys:
                    - name (str)
                    - city (str)

        Returns:
            Location: The newly created Location ORM object.
        """
        # --- Required fields ---
        loc_name = DataValidator.normalize_string(metadata.get("name"))
        if not loc_name:
            raise ValueError(f"Invalid name: {metadata['name']}")

        city_name = DataValidator.normalize_string((metadata.get("city")))
        city: City = self._get_or_create_lookup_item(session, City, {"city": city_name})

        # --- Create Location ---
        location = Location(name=loc_name, city=city)
        session.add(location)
        session.flush()
        return location

    @handle_db_errors
    @log_database_operation("update_location")
    def update_location(
        self, session: Session, location: Location, metadata: Dict[str, Any]
    ) -> Location:
        """
        Update an existing Location in the database and refresh its relationships.

        Does NOT perform file parsing. Accepts pre-normalized metadata.
        Clears previous relationships before adding new ones.

        Args:
            session (Session): Active SQLAlchemy session
            location (Location): Existing Location ORM object to update.
            metadata (Dict[str, Any]): Normalized metadata as in `create_entry`.
                Keys may include:
                    - Core fields:
                      name
                    - Relationship field
                      city

        Returns:
            Location: The updated Location ORM object (still attached to session).
        """
        # --- Ensure existance ---
        db_loc = session.get(Location, location.id)
        if db_loc is None:
            raise ValueError(f"Location with id={location.id} does not exist")

        # --- Attach to session ---
        location = session.merge(db_loc)

        # --- Update scalar fields ---
        name = DataValidator.normalize_string(metadata.get("name"))
        if name:
            location.name = name
        #
        # --- Parents ---
        if "city" in metadata:
            city = self._resolve_object(session, metadata["city"], City)
            if location.city_id != city.id:
                location.city = city

        return location

    @handle_db_errors
    @log_database_operation("get_location")
    def get_location(
        self,
        session: Session,
        location_name: Optional[str] = None,
    ) -> Optional[Location]:
        """Get a location by name."""
        if not location_name:
            raise ValueError("Name must be given.")
        return session.query(Location).filter_by(name=location_name).first()

    @handle_db_errors
    @log_database_operation("delete_location")
    def delete_location(self, session: Session, location: Location) -> None:
        """Delete a location and its associated data."""
        try:
            session.delete(location)
            session.flush()
        except Exception as e:
            raise DatabaseError(f"Failed to delete location: {e}")

    # ---- Person CRUD ----
    @handle_db_errors
    @log_database_operation("create_person")
    @validate_metadata(["name"])
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
                    - relation_type (Enum)
                Relationship keys (optional):
                    - aliases (List[str])
                    - events (List[Event|int])
                    - entries (List[Entry|int])

        Returns:
            Person: The newly created Location ORM object.
        """
        # --- Required fields ---
        p_name = DataValidator.normalize_string(metadata.get("name"))
        if not p_name:
            raise ValueError(f"Invalid name: {metadata['name']}")

        # --- Uniqueness check ---
        p_fname = DataValidator.normalize_string(metadata.get("full_name"))
        name_fellows = session.query(Person).filter_by(name=p_name).all()
        if name_fellows:
            if not p_fname:
                raise ValidationError(
                    f"Existing people found for name '{p_name}', "
                    "but no full_name was given."
                )
            for fellow in name_fellows:
                if fellow.full_name == p_fname:
                    raise ValidationError(
                        "Person already exists with "
                        f"'{p_name}' and full_name '{p_fname}'."
                    )

            name_fellows = [session.merge(f) for f in name_fellows]

        # --- Relationship Type ---
        relation_type = DataValidator.normalize_relation_type(
            metadata.get("relation_type")
        )

        # --- Create Person ---
        person = Person(
            name=p_name,
            full_name=p_fname,
            relation_type=relation_type,
        )

        # --- name_fellow ---
        if name_fellows:
            name_fellows.append(person)
            for fellow in name_fellows:
                setattr(fellow, "name_fellow", True)

        session.add(person)
        session.flush()

        # --- Relationships ---
        self._update_person_relationships(session, person, metadata)
        return person

    def _update_person_relationships(
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
                    - aliases (List[str]
                    - events (List[Event or id])
                    - entries (List[Entry or id])
                Removal keys (optional):
                    - remove_aliases (List[str])
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
        """

        # --- Many to many ---
        many_to_many_configs = [
            ("events", "events", Event),
            ("entries", "entries", Entry),
        ]

        for rel_name, meta_key, model_class in many_to_many_configs:
            if meta_key in metadata:
                RelationshipManager.update_many_to_many(
                    session=session,
                    parent_obj=person,
                    relationship_name=rel_name,
                    items=metadata[meta_key],
                    model_class=model_class,
                    incremental=incremental,
                    remove_items=metadata.get(f"remove_{meta_key}", []),
                )

        # --- Aliases ---
        # They're strings, not objects
        if "aliases" in metadata:
            self._update_person_aliases(
                session, person, metadata["aliases"], incremental
            )

    def _update_person_aliases(
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
            raise ValueError("Person must be persisted before linking tags")

        # --- Normalize incoming aliases --
        norm_aliases = {DataValidator.normalize_string(a) for a in aliases}

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

    @handle_db_errors
    @log_database_operation("update_person")
    def update_person(
        self, session: Session, person: Person, metadata: Dict[str, Any]
    ) -> Person:
        """
        Update an existing Person in the database and refresh its relationships.

        Does NOT perform file parsing. Accepts pre-normalized metadata.
        Clears previous relationships before adding new ones.

        Args:
            session (Session): Active SQLAlchemy session
            person (Person): Existing Person ORM object to update.
            metadata (Dict[str, Any]): Normalized metadata as in `create_entry`.
                Keys may include:
                    - Core fields:
                      name, full_name, relation_type
                    - Relationship keys:
                      aliases, events, entries

        Returns:
            Person: The updated Person ORM object (still attached to session).
        """
        # --- Ensure existance ---
        db_person = session.get(Person, person.id)
        if db_person is None:
            raise ValueError(f"Person with id={person.id} does not exist")

        # --- Attach to session ---
        person = session.merge(db_person)

        # --- Update scalar fields ---
        field_updates = {
            "relation_type": DataValidator.normalize_relation_type,
            "full_name": DataValidator.normalize_string,
            "name": DataValidator.normalize_string,
        }

        for field, normalizer in field_updates.items():
            if field not in metadata:
                continue

            value = normalizer(metadata[field])

            if field == "name" and value is not None:
                name_fellows = session.query(Person).filter_by(name=value).all()

                if name_fellows:
                    if person.full_name is None:
                        raise ValidationError(
                            f"Other name_fellows exist with name '{value}'; "
                            "this person needs a full name."
                        )

                    name_fellows.append(person)
                    for fellow in name_fellows:
                        setattr(fellow, "name_fellow", True)

            if value is not None or field in ["full_name", "relation_type"]:
                setattr(person, field, value)

        # --- Update relationships ---
        self._update_person_relationships(session, person, metadata)
        return person

    @handle_db_errors
    @log_database_operation("get_person")
    def get_person(
        self,
        session: Session,
        person_name: Optional[str] = None,
        person_full_name: Optional[str] = None,
    ) -> Optional[Person]:
        """Get a Person by name/full_name."""
        if not person_name and not person_full_name:
            raise ValueError("Either name or full_name must be given.")

        if person_full_name:
            p_fname = DataValidator.normalize_string(person_full_name)
            return session.query(Person).filter_by(full_name=p_fname).first()

        p_name = DataValidator.normalize_string(person_name)
        if session.query(Person).filter_by(name=p_name).count() < 2:
            return session.query(Person).filter_by(name=p_name).first()
        else:
            raise ValidationError(f"+1 people exist with name {p_name}. Use full_name.")

    @handle_db_errors
    @log_database_operation("delete_person")
    def delete_person(self, session: Session, person: Person) -> None:
        """Delete a person and its associated data."""
        try:
            session.delete(person)
            session.flush()
        except Exception as e:
            raise DatabaseError(f"Failed to delete person: {e}")

    # ---- Reference CRUD ----
    # Reference is created as a one-to-many relationship of Entry
    @handle_db_errors
    @log_database_operation("update_reference")
    def update_reference(
        self, session: Session, reference: Reference, metadata: Dict[str, Any]
    ) -> Reference:
        """
        Update an existing Reference in the database and refresh its relationships.

        Does NOT perform file parsing. Accepts pre-normalized metadata.
        Clears previous relationships before adding new ones.

        Args:
            session (Session): Active SQLAlchemy session
            reference (Reference): Existing Reference ORM object to update.
            metadata (Dict[str, Any]): Normalized metadata as in `create_entry`.
                Keys may include:
                    - Core fields:
                      content, speaker
                    - Relationship keys:
                        - entry (Entry or id)
                        - source (ReferenceSource or id)
                        - remove_source

        Returns:
            Reference: The updated Reference ORM object (still attached to session).
        """
        # --- Ensure existance ---
        db_ref = session.get(Reference, reference.id)
        if db_ref is None:
            raise ValueError(f"Reference with id={reference.id} does not exist")

        # --- Attach to session ---
        reference = session.merge(db_ref)

        # --- Update scalar fields ---
        field_updates = {
            "content": DataValidator.normalize_string,
            "speaker": DataValidator.normalize_string,
        }

        for field, normalizer in field_updates.items():
            if field in metadata:
                value = normalizer(metadata[field])
                if value is not None or field == "speaker":
                    setattr(reference, field, value)

        # --- Parents ---
        # -- Entry --
        if "entry" in metadata:
            entry = self._resolve_object(session, metadata["entry"], Entry)
            if reference.entry_id != entry.id:
                reference.entry = entry

        # -- ReferenceSource --
        if "source" in metadata:
            ref_source = self._resolve_object(
                session, metadata["source"], ReferenceSource
            )
            if reference.source_id != ref_source.id:
                reference.source = ref_source

        return reference

    @handle_db_errors
    @log_database_operation("create_reference_source")
    @validate_metadata(["type", "title"])
    def create_reference_source(
        self, session: Session, metadata: Dict[str, Any]
    ) -> ReferenceSource:
        """
        Create a new ReferenceSource in the database.

        This function does NOT handle file I/O or Markdown parsing.
        It assumes that `metadata` is already normalized
        (all dates as `datetime.date`,
        people, tags, events, etc. as strings or dicts).

        Args:
            session (Session): Active SQLAlchemy session
            metadata (Dict[str, Any]): Normalized metadata for the entry.
                Required keys:
                    - type (Enum)
                    - title (str)
                Optional keys:
                    - author (str)

        Returns:
            ReferenceSource: The newly created Location ORM object.
        """
        # --- Required fields ---
        ref_type = DataValidator.normalize_reference_type(metadata.get("type"))
        if not ref_type:
            raise ValueError(f"Invalid type: {metadata['type']}")

        norm_title = DataValidator.normalize_string(metadata.get("title"))
        if not norm_title:
            raise ValueError(f"Invalid title: {metadata['title']}")

        author = DataValidator.normalize_string(metadata.get("author"))
        if ref_type.requires_author and not author and self.logger:
            self.logger.log_warning(
                f"Reference type '{ref_type.display_name}' typically requires an author",
                {"title": norm_title},
            )

        # --- title uniqueness check ---
        existing = session.query(ReferenceSource).filter_by(title=norm_title).first()
        if existing:
            raise ValidationError(
                f"ReferenceSource already exists for title: {norm_title}"
            )

        # --- Create Source ---
        ref = ReferenceSource(type=ref_type, title=norm_title, author=author)
        session.add(ref)
        session.flush()
        return ref

    @handle_db_errors
    @log_database_operation("update_reference_source")
    def update_reference_source(
        self,
        session: Session,
        source: ReferenceSource,
        metadata: Dict[str, Any],
    ) -> ReferenceSource:
        """
        Update an existing ReferenceSource in the database
        and (optionally) refresh its relationships.

        Does NOT perform file parsing. Accepts pre-normalized metadata.
        Clears previous relationships before adding new ones.

        Args:
            session (Session): Active SQLAlchemy session
            entry (Entry): Existing Entry ORM object to update.
            metadata (Dict[str, Any]): Normalized metadata as in `create_entry`.
                Keys may include:
                    - Core fields:
                      type, title, author
                    - Relationship keys:
                        - references (List[Reference, int])

        Returns:
            ReferenceSource:
                The updated ReferenceSource ORM object
                (still attached to session).
        """
        # --- Ensure existance ---
        db_source = session.get(ReferenceSource, source.id)
        if db_source is None:
            raise ValueError(f"ReferenceSource with id={source.id} does not exist")

        # --- Attach to session ---
        source = session.merge(db_source)

        # --- Update scalar fields ---
        field_updates = {
            "type": DataValidator.normalize_reference_type,
            "title": DataValidator.normalize_string,
            "author": DataValidator.normalize_string,
        }

        for field, normalizer in field_updates.items():
            if field in metadata:
                value = normalizer(metadata[field])
                if value is not None or field == "author":
                    setattr(source, field, value)

        # --- Update relationships ---
        RelationshipManager.update_one_to_many(
            session=session,
            parent_obj=source,
            items=metadata["references"],
            model_class=Reference,
            foreign_key_attr="source_id",
            remove_items=metadata.get("remove_references", []),
        )

        return source

    # ---- Event CRUD ----
    @handle_db_errors
    @log_database_operation("create_event")
    @validate_metadata(["event"])
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
                    - event (str)
                Optional keys:
                    - title (str)
                    - description (str)
                Relationship keys (optional):
                    - entries (List[Entry|int])
                    - people (List[Person|int])

        Returns:
            Event: The newly created Event ORM object.
        """
        # --- Required fields ---
        event_name = DataValidator.normalize_string(metadata.get("event"))
        if not event_name:
            raise ValueError(f"Invalid event name: {metadata['event']}")

        # --- Create Location ---
        event = Event(
            event=event_name,
            title=DataValidator.normalize_string(metadata.get("title")),
            description=DataValidator.normalize_string(metadata.get("description")),
        )
        session.add(event)
        session.flush()

        # --- Relationships ---
        self._update_event_relationships(session, event, metadata)
        return event

    def _update_event_relationships(
        self,
        session: Session,
        event: Event,
        metadata: Dict[str, Any],
        incremental: bool = True,
    ) -> None:
        """
        Update relationships for an Event object in the database.

        Supports both incremental updates (defualt) and full overwrite.
        This function handles relationships only. No I/O or Markdown parsing.
        Prevents duplicates and ensures lookup tables are updated.

        Args:
            session (Session): Active SQLAlchemy session.
            event (Event): Entry ORM object to update relationships for.
            metadata (Dict[str, Any]): Normalized metadata containing:
                Expected keys (optional):
                    - entries (List[Entry|int])
                    - people (List[Person|int])
                Removal keys (optional):
                    - remove_entries (List[Entry|int])
                    - remove_people (List[Person|int])

        Behavior:
            - Incremental mode:
                adds new relationships and/or removes explicitly listed items.
            - Overwrite mode:
                clears all existing relationships before adding new ones.
            - Calls session.flush() only if any changes were made
        """
        # --- Many to many ---
        many_to_many_configs = [
            ("entries", "entries", Entry),
            ("people", "people", Person),
        ]

        for rel_name, meta_key, model_class in many_to_many_configs:
            if meta_key in metadata:
                RelationshipManager.update_many_to_many(
                    session=session,
                    parent_obj=event,
                    relationship_name=rel_name,
                    items=metadata[meta_key],
                    model_class=model_class,
                    incremental=incremental,
                    remove_items=metadata.get(f"remove_{meta_key}", []),
                )

    @handle_db_errors
    @log_database_operation("update_event")
    def update_event(
        self, session: Session, event: Event, metadata: Dict[str, Any]
    ) -> Event:
        """
        Update an existing Event in the database and refresh its relationships.

        Does NOT perform file parsing. Accepts pre-normalized metadata.
        Clears previous relationships before adding new ones.

        Args:
            session (Session): Active SQLAlchemy session
            event (Event): Existing Event ORM object to update.
            metadata (Dict[str, Any]): Normalized metadata as in `create_entry`.
                Keys may include:
                    - Core fields:
                      name, full_name, relation_type
                    - Relationship keys:
                      aliases, events, entries

        Returns:
            Event: The updated Event ORM object (still attached to session).
        """
        # --- Ensure existance ---
        db_event = session.get(Event, event.id)
        if db_event is None:
            raise ValueError(f"Event with id={event.id} does not exist")

        # --- Attach to session ---
        event = session.merge(db_event)

        # --- Update scalar fields ---
        field_updates = {
            "event": DataValidator.normalize_string,
            "title": DataValidator.normalize_string,
            "description": DataValidator.normalize_string,
        }

        for field, normalizer in field_updates.items():
            if field in metadata:
                value = normalizer(metadata[field])
                if value is not None or field in ["title", "description"]:
                    setattr(event, field, value)

        # --- Update relationships ---
        self._update_event_relationships(session, event, metadata)
        return event

    # ---- Poems CRUD ----
    @handle_db_errors
    @log_database_operation("create_poem")
    @validate_metadata(["title", "content"])
    def create_poem(self, session: Session, metadata: Dict[str, Any]) -> PoemVersion:
        """
        Create a new PoemVersion in the database with its associated Poem.

        This function does NOT handle file I/O or Markdown parsing. It assumes
        that `metadata` is already normalized (all dates as `datetime.date`,
        people, tags, events, etc. as strings or dicts).

        Args:
            session (Session): Active SQLAlchemy session
            metadata (Dict[str, Any]): Normalized metadata for the entry.
                Required keys:
                    - title (str)
                    - content (str)
                Optional keys:
                    - version_hash (str)
                    - notes (str)
                    - revision_date (str|date)
                Relationship keys (optional):
                    - entry (Entry or id)
                    - poem (Poem or id)

        Returns:
            Event: The newly created Event ORM object.
        """
        # --- Required fields ---
        title = DataValidator.normalize_string(metadata.get("title"))
        if not title:
            raise ValueError(f"Invalid poem title: {metadata['title']}")

        content = DataValidator.normalize_string(metadata.get("content"))
        if not content:
            raise ValueError(f"Invalid poem content: {metadata['content']}")

        # --- Uniqueness check ---
        existing = session.query(PoemVersion).filter_by(content=content).first()
        if existing:
            raise ValidationError("PoemVersion already exists with the same content")

        # --- Parents ---
        # -- Entry --
        entry: Optional[Entry] = None
        if "entry" in metadata:
            entry = self._resolve_object(session, metadata["entry"], Entry)

        # -- Poem --
        poem: Poem
        if "poem" in metadata:
            poem = self._resolve_object(session, metadata["poem"], Poem)
        else:
            poem = Poem(title=title)
            session.add(poem)
            session.flush()

        # --- If hash doesn't exist, create it ---
        version_hash = DataValidator.normalize_string(metadata.get("version_hash"))
        if not version_hash:
            version_hash = md.get_text_hash(content)

        # --- Determine revision date ---
        rev_date: date
        m_date = DataValidator.normalize_date(metadata.get("revision_date"))
        if m_date:
            rev_date = m_date
        elif entry:
            rev_date = entry.date
        else:
            rev_date = datetime.now(timezone.utc).date()

        # --- Create PoemVersion ---
        poem_version = PoemVersion(
            content=content,
            revision_date=rev_date,
            version_hash=version_hash,
            notes=DataValidator.normalize_string(metadata.get("notes")),
            poem=poem,
            entry=entry,
        )
        session.add(poem_version)
        session.flush()
        return poem_version

    @handle_db_errors
    @log_database_operation("update_poem")
    def update_poem(
        self, session: Session, poem: Poem, metadata: Dict[str, Any]
    ) -> Poem:
        """
        Update an existing Poem in the database and refresh its relationships.

        Args:
            session (Session): Active SQLAlchemy session
            poem (Poem): Existing Poem ORM object to update.
            metadata (Dict[str, Any]): Normalized metadata as in `create_entry`.
                Keys may include:
                    - Core field: title
                    - Relationship keys:
                      versions, remove_versions

        Returns:
            Poem: The updated Poem ORM object (still attached to session).
        """
        # --- Ensure existance ---
        db_poem = session.get(Poem, poem.id)
        if db_poem is None:
            raise ValueError(f"Poem with id={poem.id} does not exist")

        # --- Attach to session ---
        poem = session.merge(db_poem)

        # --- Update title ---
        if "title" in metadata:
            title = DataValidator.normalize_string(metadata["title"])
            if title is not None:
                setattr(poem, "title", title)

        # --- Update Versions ---
        if "versions" in metadata or "remove_versions" in metadata:
            RelationshipManager.update_one_to_many(
                session=session,
                parent_obj=poem,
                items=metadata["versions"],
                model_class=PoemVersion,
                foreign_key_attr="poem_id",
                remove_items=metadata.get("remove_versions", []),
            )

        return poem

    @handle_db_errors
    @log_database_operation("update_poem_version")
    def update_poem_version(
        self, session: Session, poem_version: PoemVersion, metadata: Dict[str, Any]
    ) -> PoemVersion:
        """
        Update an existing Poem (Version) in the database.

        Args:
            session (Session): Active SQLAlchemy session
            poem_version (PoemVersion): Existing PoemVersion ORM object to update.
            metadata (Dict[str, Any]): Normalized metadata as in `create_entry`.
                Keys may include:
                    - Core field: content, revision_date, notes
                    - Relationship keys:
                      poem, entry, remove_entry

        Returns:
            Event: The updated Event ORM object (still attached to session).

        Notes: version_hash is automatically updated if content changes
        """
        # --- Ensure existance ---
        db_poem = session.get(PoemVersion, poem_version.id)
        if db_poem is None:
            raise ValueError(f"PoemVersion with id={poem_version.id} does not exist")

        # --- Attach to session ---
        poem_version = session.merge(db_poem)

        # --- Update scalar fields ---
        field_updates = {
            "content": DataValidator.normalize_string,
            "notes": DataValidator.normalize_string,
        }

        for field, normalizer in field_updates.items():
            if field in metadata:
                value = normalizer(metadata[field])
                if value is not None or field == "notes":
                    if field == "content" and value is not None:
                        content_hash = md.get_text_hash(value)
                        setattr(poem_version, "version_hash", content_hash)
                    setattr(poem_version, field, value)

        # --- Parents ---
        # -- Entry --
        entry: Optional[Entry] = None
        if "entry" in metadata:
            entry = self._resolve_object(session, metadata["entry"], Entry)
            if poem_version.entry_id != entry.id:
                poem_version.entry = entry
                poem_version.revision_date = entry.date
        elif metadata.get("remove_entry"):
            poem_version.entry = None

        # -- Poem --
        poem_parent: Optional[Poem] = None
        if "poem" in metadata:
            poem_parent = self._resolve_object(session, metadata["poem"], Poem)
            if poem_version.poem_id != poem_parent.id:
                poem_version.poem = poem_parent

        return poem_version

    # ---- Manuscript CRUD ----
    # --- Entry ---
    @log_database_operation("create_or_update_manuscript_entry")
    def create_or_update_manuscript_entry(
        self, session: Session, entry: Entry, manuscript_data: Dict[str, Any]
    ) -> Optional[ManuscriptEntry]:
        """
        Create or update a ManuscriptEntry associated with a given Entry.

        Args:
            session (Session): Active SQLAlchemy session.
            entry (Entry): The Entry instance to link to.
            manuscript_data (Dict[str, Any]): Metadata for the ManuscriptEntry,
                keys include (optional):
                    - 'status' (str|ManuscriptStatus): Status of the Entry.
                    - 'edited' (bool): Whether the entry has been edited.
                    - 'notes' (str): Additional notes.
                    - 'themes' (List[str]): Themes (handled separately).

        Returns:
            ManuscriptEntry: The created or updated ManuscriptEntry instance.
        """
        # -- Normalize the data --
        normalized_data = {}

        # - status -
        if "status" in manuscript_data:
            status_value = manuscript_data["status"]
            if isinstance(status_value, ManuscriptStatus):
                normalized_data["status"] = status_value
            elif isinstance(status_value, str):
                try:
                    normalized_data["status"] = ManuscriptStatus[status_value.upper()]
                except KeyError:
                    # Try to match by value (case-insensitive)
                    status_found = False
                    for status_enum in ManuscriptStatus:
                        if status_enum.value.lower() == status_value.lower():
                            normalized_data["status"] = status_enum
                            status_found = True
                            break
                    if not status_found:
                        valid_values = [s.value for s in ManuscriptStatus]
                        raise ValueError(
                            f"Invalid status '{status_value}'. "
                            f"Valid values are: {valid_values}"
                        )

        # - edited -
        if "edited" in manuscript_data:
            normalized_data["edited"] = DataValidator.normalize_bool(
                manuscript_data["edited"]
            )

        # - notes -
        if "notes" in manuscript_data:
            normalized_data["notes"] = DataValidator.normalize_string(
                manuscript_data["notes"]
            )

        # -- Relationship --
        manuscript = RelationshipManager.update_one_to_one(
            session=session,
            parent_obj=entry,
            relationship_name="manuscript",
            model_class=ManuscriptEntry,
            child_data=normalized_data if normalized_data else {},
            foreign_key_attr="entry_id",
        )

        # -- Themes --
        if manuscript and "themes" in manuscript_data:
            self._update_manuscript_themes(
                session, manuscript, manuscript_data["themes"]
            )

        return manuscript

    def _update_manuscript_themes(
        self, session: Session, manuscript: ManuscriptEntry, themes_list: List[str]
    ) -> None:
        """Update themes for a ManuscriptEntry using RelationshipManager."""
        if not themes_list:
            return

        # Normalize theme names and create Theme objects as needed
        theme_objects = []
        for theme_name in themes_list:
            theme_norm = DataValidator.normalize_string(theme_name)
            if theme_norm:
                theme_obj = self._get_or_create_lookup_item(
                    session, Theme, {"theme": theme_norm}
                )
                theme_objects.append(theme_obj)

        RelationshipManager.update_many_to_many(
            session=session,
            parent_obj=manuscript,
            relationship_name="themes",
            items=theme_objects,
            model_class=Theme,
            incremental=False,  # Replace all themes
        )

    @log_database_operation("create_or_update_manuscript_person")
    def create_or_update_manuscript_person(
        self, session: Session, person: Person, manuscript_data: Dict[str, Any]
    ) -> Optional[ManuscriptPerson]:
        """
        Create or update a ManuscriptPerson associated with a given Person.

        Args:
            session (Session): Active SQLAlchemy session.
            person (Person): The Person instance to link to.
            manuscript_data (Dict[str, Any]): Metadata for the ManuscriptPerson,
                keys include:
                    - 'character' (str): Pseudonym used in the manuscript

        Returns:
            ManuscriptPerson: The created or updated ManuscriptPerson instance.
        """
        # -- Character is required --
        if "character" not in manuscript_data or not manuscript_data["character"]:
            raise ValidationError("Required field 'character' missing or empty")

        norm_character = DataValidator.normalize_string(manuscript_data["character"])
        if not norm_character:
            raise ValueError(
                f"Invalid character format: {manuscript_data['character']}"
            )

        normalized_data = {"character": norm_character}

        return RelationshipManager.update_one_to_one(
            session=session,
            parent_obj=person,
            relationship_name="manuscript",
            model_class=ManuscriptPerson,
            child_data=normalized_data,
            foreign_key_attr="person_id",
        )

    @log_database_operation("create_or_update_manuscript_event")
    def create_or_update_manuscript_event(
        self, session: Session, event: Event, manuscript_data: Dict[str, Any]
    ) -> Optional[ManuscriptEvent]:
        """
        Create or update a ManuscriptEvent associated with a given Event.

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
        normalized_data = {}

        if "notes" in manuscript_data:
            normalized_data["notes"] = DataValidator.normalize_string(
                manuscript_data["notes"]
            )

        manuscript = RelationshipManager.update_one_to_one(
            session=session,
            parent_obj=event,
            relationship_name="manuscript",
            model_class=ManuscriptEvent,
            child_data=normalized_data if normalized_data else {},
            foreign_key_attr="event_id",
        )

        # Handle arc separately (many-to-one with Arc)
        if manuscript and "arc" in manuscript_data:
            arc_name = DataValidator.normalize_string(manuscript_data["arc"])
            if arc_name:
                arc_obj = self._get_or_create_lookup_item(
                    session, Arc, {"arc": arc_name}
                )
                manuscript.arc = arc_obj
                session.flush()

        return manuscript

    # ---- Query Methods ----
    @handle_db_errors
    def get_entries_by_date_range(
        self, session: Session, start_date: Union[str, date], end_date: Union[str, date]
    ) -> List[Entry]:
        """Get entries within a date range."""
        return self.query_analytics.get_entries_by_date_range(
            session, start_date, end_date
        )

    @handle_db_errors
    def search_entries(
        self, session: Session, query: str, limit: Optional[int] = None
    ) -> List[Entry]:
        """Search entries by content in notes or epigraph."""
        return self.query_analytics.search_entries(session, query, limit)

    @handle_db_errors
    def get_entries_by_person(self, session: Session, person_name: str) -> List[Entry]:
        """Get all entries mentioning a specific person."""
        return self.query_analytics.get_entries_by_person(session, person_name)

    @handle_db_errors
    def get_entries_by_location(
        self, session: Session, location_name: str
    ) -> List[Entry]:
        """Get all entries at a specific location."""
        return self.query_analytics.get_entries_by_location(session, location_name)

    @handle_db_errors
    def get_entries_by_tag(self, session: Session, tag_name: str) -> List[Entry]:
        """Get all entries with a specific tag."""
        return self.query_analytics.get_entries_by_tag(session, tag_name)

    # ---- Statistics and Health ----
    @handle_db_errors
    def get_database_stats(self, session: Session) -> Dict[str, Any]:
        """Get comprehensive database statistics."""
        return self.query_analytics.get_database_stats(session)

    @handle_db_errors
    def health_check(self, session: Session) -> Dict[str, Any]:
        """Comprehensive database health check."""
        return self.health_monitor.health_check(session, self.db_path)

    # ----- Export Functionality (Delegated) -----
    @handle_db_errors
    # @with_temporal_cleanup
    def export_to_csv(
        self, session: Session, export_dir: Union[str, Path]
    ) -> Dict[str, Path]:
        """Export all database tables to CSV files."""
        return self.export_manager.export_to_csv(session, export_dir)

    @handle_db_errors
    # @with_temporal_cleanup
    def export_to_json(self, session: Session, export_file: Union[str, Path]) -> Path:
        """Export complete database to JSON."""
        return self.export_manager.export_to_json(session, export_file)

    # ----- Cleanup Operations -----
    @handle_db_errors
    def bulk_cleanup_unused(
        self, session: Session, cleanup_config: Dict[str, tuple]
    ) -> Dict[str, int]:
        """Perform bulk cleanup operations more efficiently."""
        return self.health_monitor.bulk_cleanup_unused(session, cleanup_config)

    @log_database_operation("cleanup_all_metadata")
    def cleanup_all_metadata(self) -> Dict[str, int]:
        """Run safe cleanup operations with proper transaction handling."""
        cleanup_config = {
            "tags": (Tag, "entries"),
            "locations": (Location, "entries"),
            "dates": (MentionedDate, "entries"),
            "themes": (Theme, "entries"),
            "references": (Reference, "entry"),
            "poem_versions": (PoemVersion, "entry"),
        }

        try:
            with self.session_scope() as session:
                return self.bulk_cleanup_unused(session, cleanup_config)
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, {"operation": "cleanup_all_metadata"})
            raise DatabaseError(f"Cleanup operation failed: {e}")

    # ----- Backup Integration -----
    def create_backup(
        self, backup_type: str = "manual", suffix: Optional[str] = None
    ) -> Optional[Path]:
        """Create a database backup using the backup manager."""
        if not self.backup_manager:
            raise DatabaseError("Backup manager not configured")

        return self.backup_manager.create_backup(backup_type, suffix)

    def list_backups(self) -> Dict[str, List[Dict[str, Any]]]:
        """List all available backups."""
        if not self.backup_manager:
            raise DatabaseError("Backup manager not configured")

        return self.backup_manager.list_backups()

    def restore_backup(self, backup_path: Union[str, Path]) -> None:
        """Restore database from backup."""
        if not self.backup_manager:
            raise DatabaseError("Backup manager not configured")

        self.backup_manager.restore_backup(Path(backup_path))

    # ---- Convenience Methods ----
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics (convenience method)."""
        try:
            with self.session_scope() as session:
                return self.get_database_stats(session)
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, {"operation": "get_stats"})
            raise DatabaseError(f"Could not retrieve database statistics: {e}")

    def check_health(self) -> Dict[str, Any]:
        """Check database health (convenience method)."""
        try:
            with self.session_scope() as session:
                return self.health_check(session)
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, {"operation": "check_health"})
            raise DatabaseError(f"Health check failed: {e}")

    # ----- Context Manager Support -----
    def __enter__(self) -> "PalimpsestDB":
        """Support for context manager usage."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Cleanup on context manager exit."""
        del exc_type, exc_val, exc_tb
        if self.backup_manager and hasattr(self, "_auto_backup_on_exit"):
            try:
                self.backup_manager.auto_backup()
            except Exception as e:
                if self.logger:
                    self.logger.log_error(e, {"operation": "exit_auto_backup"})
