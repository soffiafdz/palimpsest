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
    - Migration management via Alembic

Key Features:
    - Transaction management with automatic rollback
    - Retry logic for database lock handling
    - Optimized relationship loading
    - Validation and normalization of inputs
    - Comprehensive error handling and logging
    - Support for manuscript metadata

Core Operations:
    Entry Management:
        - create_entry: Create new entries with relationships
        - update_entry: Update existing entries
        - get_entry: Retrieve entries by date
        - delete_entry: Remove entries
        - bulk_create_entries: Efficient batch creation

    People Management:
        - create_person: Create person records with aliases
        - update_person: Update person details
        - get_person: Retrieve by name or full_name

    Location Management:
        - update_city: Manage city records
        - update_location: Manage venue records

    Reference Management:
        - update_reference: Manage reference records
        - create_reference_source: Create source records
        - update_reference_source: Update source details

    Event & Poem Management:
        - create_event: Create event records
        - update_event: Update event details
        - create_poem: Create poem versions
        - update_poem: Update poem details
        - update_poem_version: Update specific versions

    Manuscript Management:
        - create_or_update_manuscript_entry: Link entries to manuscript
        - create_or_update_manuscript_person: Map people to characters
        - create_or_update_manuscript_event: Track manuscript events

    Database Maintenance:
        - cleanup_all_metadata: Remove orphaned records
        - health_monitor: Check database integrity
        - export_manager: Export data to various formats
        - query_analytics: Generate statistics and reports

Notes
==============
- Migrations are handled externally via Alembic
- All datetime fields are UTC-aware
- Backup retention policies are configurable
- Logs are rotated automatically to prevent disk bloat
- Retry logic handles SQLite lock contention
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import time
from contextlib import contextmanager
from datetime import date, datetime, timezone

from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union, List, Type, TypeVar, Sequence

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
    ReferenceMode,
    ReferenceType,
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
from .query_optimizer import QueryOptimizer
from .relationship_manager import RelationshipManager, HasId

# Modular entity managers (Phase 2)
from .managers import (
    TagManager,
    PersonManager,
    EventManager,
    DateManager,
    LocationManager,
    ReferenceManager,
    PoemManager,
    ManuscriptManager,
)


T = TypeVar("T", bound=HasId)


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
        else:
            self.backup_manager = None

        # Initialize service components
        self.health_monitor = HealthMonitor(self.logger)
        self.export_manager = ExportManager(self.logger)
        self.query_analytics = QueryAnalytics(self.logger)

        # Initialize modular entity managers (lazy-loaded in session_scope)
        self._tag_manager: Optional[TagManager] = None
        self._person_manager: Optional[PersonManager] = None
        self._event_manager: Optional[EventManager] = None
        self._date_manager: Optional[DateManager] = None
        self._location_manager: Optional[LocationManager] = None
        self._reference_manager: Optional[ReferenceManager] = None
        self._poem_manager: Optional[PoemManager] = None
        self._manuscript_manager: Optional[ManuscriptManager] = None

        # Initialize database
        self._setup_engine()

        # Auto-backup if enabled
        if enable_auto_backup and self.backup_manager:
            self.backup_manager.auto_backup()

    def _setup_engine(self) -> None:
        """Initialize database engine and session factory."""
        try:
            if self.logger:
                self.logger.log_operation(
                    "database_init_start",
                    {
                        "db_path": str(self.db_path),
                        "alembic_dir": str(self.alembic_dir),
                    },
                )

            self.db_path.parent.mkdir(parents=True, exist_ok=True)

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

            if not self.db_path.exists():
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
        """
        Provide a transactional scope around operations with logging.

        Also initializes modular entity managers for use within the session.
        Managers are available via properties (db.people, db.tags, etc.)

        Usage:
            with db.session_scope() as session:
                # New pattern (recommended)
                person = db.people.create({"name": "Alice"})
                tag = db.tags.get_or_create("python")

                # Old pattern (still works, deprecated)
                entry = db.create_entry(session, metadata)
        """
        session = self.SessionLocal()
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        # Initialize modular managers for this session
        self._tag_manager = TagManager(session, self.logger)
        self._person_manager = PersonManager(session, self.logger)
        self._event_manager = EventManager(session, self.logger)
        self._date_manager = DateManager(session, self.logger)
        self._location_manager = LocationManager(session, self.logger)
        self._reference_manager = ReferenceManager(session, self.logger)
        self._poem_manager = PoemManager(session, self.logger)
        self._manuscript_manager = ManuscriptManager(session, self.logger)

        if self.logger:
            self.logger.log_debug("session_start", {"session_id": session_id})

        try:
            yield session
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
            # Clean up managers
            self._tag_manager = None
            self._person_manager = None
            self._event_manager = None
            self._date_manager = None
            self._location_manager = None
            self._reference_manager = None
            self._poem_manager = None
            self._manuscript_manager = None

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

    # -------------------------------------------------------------------------
    # Modular Entity Manager Properties (Phase 2)
    # -------------------------------------------------------------------------

    @property
    def tags(self) -> TagManager:
        """
        Access TagManager for tag operations.

        Recommended usage:
            with db.session_scope() as session:
                tag = db.tags.get_or_create("python")
                db.tags.link_to_entry(entry, "coding")

        Raises:
            DatabaseError: If accessed outside of session_scope context
        """
        if self._tag_manager is None:
            raise DatabaseError(
                "TagManager requires active session. "
                "Use within session_scope: "
                "with db.session_scope() as session: db.tags.create(...)"
            )
        return self._tag_manager

    @property
    def people(self) -> PersonManager:
        """
        Access PersonManager for person operations.

        Recommended usage:
            with db.session_scope() as session:
                person = db.people.create({"name": "Alice", "relation_type": "friend"})
                alice = db.people.get(person_name="Alice")

        Raises:
            DatabaseError: If accessed outside of session_scope context
        """
        if self._person_manager is None:
            raise DatabaseError(
                "PersonManager requires active session. "
                "Use within session_scope."
            )
        return self._person_manager

    @property
    def events(self) -> EventManager:
        """
        Access EventManager for event operations.

        Recommended usage:
            with db.session_scope() as session:
                event = db.events.create({"name": "PyCon 2024"})

        Raises:
            DatabaseError: If accessed outside of session_scope context
        """
        if self._event_manager is None:
            raise DatabaseError(
                "EventManager requires active session. "
                "Use within session_scope."
            )
        return self._event_manager

    @property
    def dates(self) -> DateManager:
        """
        Access DateManager for mentioned date operations.

        Recommended usage:
            with db.session_scope() as session:
                date = db.dates.get_or_create("2024-01-15")

        Raises:
            DatabaseError: If accessed outside of session_scope context
        """
        if self._date_manager is None:
            raise DatabaseError(
                "DateManager requires active session. "
                "Use within session_scope."
            )
        return self._date_manager

    @property
    def locations(self) -> LocationManager:
        """
        Access LocationManager for location operations.

        Recommended usage:
            with db.session_scope() as session:
                location = db.locations.create({"name": "Central Park", "city": "NYC"})

        Raises:
            DatabaseError: If accessed outside of session_scope context
        """
        if self._location_manager is None:
            raise DatabaseError(
                "LocationManager requires active session. "
                "Use within session_scope."
            )
        return self._location_manager

    @property
    def references(self) -> ReferenceManager:
        """
        Access ReferenceManager for reference operations.

        Recommended usage:
            with db.session_scope() as session:
                ref = db.references.create({"title": "Book Title", "author": "Author"})

        Raises:
            DatabaseError: If accessed outside of session_scope context
        """
        if self._reference_manager is None:
            raise DatabaseError(
                "ReferenceManager requires active session. "
                "Use within session_scope."
            )
        return self._reference_manager

    @property
    def poems(self) -> PoemManager:
        """
        Access PoemManager for poem operations.

        Recommended usage:
            with db.session_scope() as session:
                poem = db.poems.create({"title": "Poem Title", "text": "..."})

        Raises:
            DatabaseError: If accessed outside of session_scope context
        """
        if self._poem_manager is None:
            raise DatabaseError(
                "PoemManager requires active session. "
                "Use within session_scope."
            )
        return self._poem_manager

    @property
    def manuscripts(self) -> ManuscriptManager:
        """
        Access ManuscriptManager for manuscript operations.

        Recommended usage:
            with db.session_scope() as session:
                ms = db.manuscripts.create_entry(entry, {"status": "draft"})

        Raises:
            DatabaseError: If accessed outside of session_scope context
        """
        if self._manuscript_manager is None:
            raise DatabaseError(
                "ManuscriptManager requires active session. "
                "Use within session_scope."
            )
        return self._manuscript_manager

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
        file_hash = DataValidator.normalize_string((metadata.get("file_hash")))
        if not file_hash and file_path:
            file_path_obj = Path(file_path)
            if file_path_obj.exists():
                file_hash = fs.get_file_hash(file_path)
            else:
                if self.logger:
                    self.logger.log_warning(
                        f"File path does not exist, cannot calculate hash: {file_path}"
                    )

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
                epigraph_attribution=DataValidator.normalize_string(
                    metadata.get("epigraph_attribution")
                ),
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
                    - dates (List[MentionedDate|int|str|Dict]) - Mentioned dates with optional context
                    - cities (List[City|int|str]) - Cities where entry took place
                    - locations (List[Dict]) - Locations with city context: {"name": str, "city": str}
                    - people (List[Person|int|str]) - People mentioned
                    - events (List[Event|int|str]) - Events entry belongs to
                    - tags (List[str]) - Keyword tags
                    - related_entries (List[str]) - Date strings of related entries
                    - references (List[Dict]) - External references with sources
                    - poems (List[Dict]) - Poem versions
                    - manuscript (Dict) - Manuscript metadata
                Removal keys (optional):
                    - remove_dates (List[MentionedDate|int])
                    - remove_cities (List[City|int])
                    - remove_people (List[Person|int])
                    - remove_events (List[Event|int])
                    - remove_locations (List[Location|int])
            incremental (bool): If True, add/remove specified items.
                                If False, replace all relationships.

        Behavior:
            - Incremental mode:
                adds new relationships and/or removes explicitly listed items.
            - Overwrite mode:
                clears all existing relationships before adding new ones.
            - Calls session.flush() only if any changes were made

        Special Handling:
            - dates: Supports both simple date strings and dicts with context
            - locations: Requires city context in dict format
            - references: Creates ReferenceSource records as needed
            - poems: Creates Poem parent records as needed
            - tags: Simple string list (not ORM objects)
            - related_entries: Uni-directional relationships by date string
        """
        try:
            # --- Many to many ---
            many_to_many_configs = [
                ("cities", "cities", City),
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

            # --- Aliases ---
            if "alias" in metadata:
                self._process_entry_aliases(session, entry, metadata["alias"])

            # --- Locations ---
            if "locations" in metadata:
                self._update_entry_locations(
                    session, entry, metadata["locations"], incremental
                )

            # --- Dates ---
            if "dates" in metadata:
                if not incremental:
                    entry.dates.clear()
                    session.flush()
                self._process_mentioned_dates(session, entry, metadata["dates"])

            # --- References ---
            # References need special handling because they involve ReferenceSource creation
            if "references" in metadata:
                self._process_references(session, entry, metadata["references"])

            # --- Poems ---
            if "poems" in metadata:
                self._process_poems(session, entry, metadata["poems"])

            # --- Related entries ---
            # Handle related entries (uni-directional relationships)
            if "related_entries" in metadata:
                self._process_related_entries(
                    session, entry, metadata["related_entries"]
                )

            # --- Tags ---
            # They're strings, not objects
            if "tags" in metadata:
                self._update_entry_tags(session, entry, metadata["tags"], incremental)

            # --- Manuscript ---
            if "manuscript" in metadata:
                self.create_or_update_manuscript_entry(
                    session, entry, metadata["manuscript"]
                )

            session.flush()

        except Exception as e:
            # Log error with context
            if self.logger:
                self.logger.log_error(
                    e,
                    {
                        "operation": "update_entry_relationships",
                        "entry_id": entry.id,
                        "entry_date": str(entry.date),
                    },
                )
            # Re-raise for higher-level handling
            raise

    def _process_entry_aliases(
        self,
        session: Session,
        entry: Entry,
        alias_data: Sequence[str | Sequence[str] | Dict[str, Any]],
    ):
        """
        Process aliases with optional person context and link to entry.

        Args:
            session: SQLAlchemy session
            entry: Entry to link aliases to
            alias_data: List of alias specifications:
                - str: single alias
                - List[str]: multiple aliases for same person
                - Dict: {"alias": str|List[str], "name": str, "full_name": str}

        Raises:
            ValueError: If entry not persisted or invalid alias data
        """
        if entry.id is None:
            raise ValueError("Entry must be persisted before linking aliases")

        alias_orms = []

        for alias_obj in alias_data:
            person: Optional[Person] = None
            aliases: List[str] = []
            name: Optional[str] = None
            full_name: Optional[str] = None

            # Parse input format
            if isinstance(alias_obj, dict):
                # Dict format: {"alias": [...], "name": "...", "full_name": "..."}
                alias_raw = alias_obj.get("alias", [])
                if isinstance(alias_raw, str):
                    alias_raw = [alias_raw]

                aliases_raw = [
                    DataValidator.normalize_string(a) for a in alias_raw if a
                ]
                aliases = [a for a in aliases_raw if a]

                name = DataValidator.normalize_string(alias_obj.get("name"))
                full_name = DataValidator.normalize_string(alias_obj.get("full_name"))

            elif isinstance(alias_obj, list):
                # List format: ["alias1", "alias2"]
                aliases_raw = [DataValidator.normalize_string(a) for a in alias_obj]
                aliases = [a for a in aliases_raw if a]

            elif isinstance(alias_obj, str):
                # String format: "alias"
                normalized = DataValidator.normalize_string(alias_obj)
                if normalized:
                    aliases = [normalized]

            else:
                if self.logger:
                    self.logger.log_warning(
                        f"Invalid alias format: {type(alias_obj).__name__}",
                        {"entry_id": entry.id, "alias_data": str(alias_obj)[:100]},
                    )
                continue

            if not aliases:
                if self.logger:
                    self.logger.log_warning(
                        "Empty alias list after normalization",
                        {"entry_id": entry.id, "raw_data": str(alias_obj)[:100]},
                    )
                continue

            # Try to resolve person from existing aliases
            unresolved_aliases = aliases.copy()
            alias_fellows = []
            for alias in aliases:
                existing_aliases = session.query(Alias).filter_by(alias=alias).all()

                if len(existing_aliases) == 1:
                    # Unique alias found - use it
                    alias_orms.append(existing_aliases[0])
                    person = existing_aliases[0].person
                    unresolved_aliases.remove(alias)

                elif len(existing_aliases) > 1:
                    # Ambiguous - multiple people have this alias
                    alias_fellows.append(alias)
                    unresolved_aliases.remove(alias)

            if unresolved_aliases or alias_fellows:
                if not person:
                    if name or full_name:
                        try:
                            person = self.get_person(session, name, full_name)
                        except ValidationError as e:
                            if self.logger:
                                self.logger.log_warning(
                                    f"Could not resolve person for aliases: {e}",
                                    {
                                        "entry_id": entry.id,
                                        "entry_date": str(entry.date),
                                        "alias": [
                                            *unresolved_aliases,
                                            *alias_fellows,
                                        ],
                                        "name": name,
                                        "full_name": full_name,
                                    },
                                )
                            continue

                        if person is None:
                            if self.logger:
                                person_id = full_name if full_name else name
                                self.logger.log_warning(
                                    f"Person '{person_id}' not found for alias",
                                    {
                                        "entry_id": entry.id,
                                        "entry_date": str(entry.date),
                                        "alias": [
                                            *unresolved_aliases,
                                            *alias_fellows,
                                        ],
                                        "name": name,
                                        "full_name": full_name,
                                    },
                                )
                            continue
                    else:
                        # No person context provided
                        if self.logger:
                            self.logger.log_warning(
                                "Cannot resolve alias without person context",
                                {
                                    "entry_id": entry.id,
                                    "entry_date": str(entry.date),
                                    "alias": [*unresolved_aliases, *alias_fellows],
                                    "hint": "Provide 'name' or 'full_name' in alias dict",
                                },
                            )
                        continue

                if alias_fellows:
                    # Resolve ambiguous alias
                    resolved_fellows = []
                    for alias in alias_fellows:
                        existing_aliases = (
                            session.query(Alias)
                            .filter_by(alias=alias, person_id=person.id)
                            .all()
                        )

                        if len(existing_aliases) == 1:
                            # Unique alias found - use it
                            alias_orms.append(existing_aliases[0])
                            resolved_fellows.append(alias)

                    alias_fellows = [
                        a for a in alias_fellows if a not in resolved_fellows
                    ]
                    # This shouldn't happen due to Tables limitation, leave here anyway
                    if alias_fellows:
                        if self.logger:
                            self.logger.log_warning(
                                f"Ambiguous alias(es) '{alias_fellows}' match multiple people",
                                {
                                    "entry_id": entry.id,
                                    "entry_date": str(entry.date),
                                    "alias": alias_fellows,
                                },
                            )

                # Create new alias records for this person
                for alias in unresolved_aliases:
                    try:
                        alias_orm = self._get_or_create_lookup_item(
                            session,
                            Alias,
                            lookup_fields={"alias": alias, "person_id": person.id},
                        )
                        alias_orms.append(alias_orm)

                        if self.logger:
                            self.logger.log_debug(
                                f"Created alias '{alias}' for {person.display_name}",
                                {
                                    "entry_id": entry.id,
                                    "person_id": person.id,
                                    "alias": alias,
                                },
                            )
                    except Exception as e:
                        if self.logger:
                            self.logger.log_error(
                                e,
                                {
                                    "operation": "create_alias",
                                    "entry_id": entry.id,
                                    "person_id": person.id,
                                    "alias": alias,
                                },
                            )
                        # Continue processing other aliases
                        continue

        # Link all collected aliases to entry
        if alias_orms:
            try:
                RelationshipManager.update_many_to_many(
                    session=session,
                    parent_obj=entry,
                    relationship_name="aliases_used",
                    items=alias_orms,
                    model_class=Alias,
                    incremental=True,
                )

                if self.logger:
                    self.logger.log_debug(
                        f"Linked {len(alias_orms)} aliases to entry",
                        {
                            "entry_id": entry.id,
                            "entry_date": str(entry.date),
                            "alias_count": len(alias_orms),
                        },
                    )
            except Exception as e:
                if self.logger:
                    self.logger.log_error(
                        e,
                        {
                            "operation": "link_aliases_to_entry",
                            "entry_id": entry.id,
                            "entry_date": str(entry.date),
                            "alias_count": len(alias_orms),
                        },
                    )
                raise
        elif self.logger:
            # No aliases were successfully processed
            self.logger.log_debug(
                "No alias linked to entry",
                {
                    "entry_id": entry.id,
                    "entry_date": str(entry.date),
                    "input_count": len(alias_data),
                },
            )

    def _process_mentioned_dates(
        self,
        session: Session,
        entry: Entry,
        dates_data: List[Union[str, Dict[str, Any]]],
    ) -> None:
        """
        Process mentioned dates with optional context, locations, and people.

        Each date can have:
        - date: ISO format date string (required)
        - context: Optional text context
        - locations: List of location names (creates relationships)
        - people: List of person specs (creates relationships)

        Args:
            session: SQLAlchemy session
            entry: Entry to attach dates to
            dates_data: List of date specifications
        """
        existing_date_ids = {d.id for d in entry.dates}

        for date_item in dates_data:
            mentioned_date = None

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

                if "locations" in date_item and date_item["locations"]:
                    self._update_mentioned_date_locations(
                        session, mentioned_date, date_item["locations"]
                    )

                if "people" in date_item and date_item["people"]:
                    self._update_mentioned_date_people(
                        session, mentioned_date, date_item["people"]
                    )
            else:
                continue

            if mentioned_date and mentioned_date.id not in existing_date_ids:
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
                "epigraph_attribution": DataValidator.normalize_string,
                "notes": DataValidator.normalize_string,
            }

            for field, normalizer in field_updates.items():
                if field not in metadata:
                    continue

                value = normalizer(metadata[field])
                if value is not None or field in ["epigraph", "epigraph_attribution", "notes"]:
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
    @log_database_operation("get_entry_for_display")
    def get_entry_for_display(
        self, session: Session, entry_date: Union[str, date]
    ) -> Optional[Entry]:
        """
        Get single entry optimized for display operations.

        Loads basic metadata without heavy relationships like references/poems.

        Args:
            session: SQLAlchemy session
            entry_date: Date to query

        Returns:
            Entry with display relationships preloaded
        """
        if isinstance(entry_date, str):
            entry_date = date.fromisoformat(entry_date)

        entry = session.query(Entry).filter_by(date=entry_date).first()

        if entry:
            # Use optimized display query
            return QueryOptimizer.for_display(session, entry.id)

        return None

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
                        "epigraph_attribution": DataValidator.normalize_string(
                            metadata.get("epigraph_attribution")
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
    def _update_mentioned_date_relationships(
        self,
        session: Session,
        mentioned_date: MentionedDate,
        metadata: Dict[str, Any],
        incremental: bool = True,
    ) -> None:
        """
        Update relationships for a MentionedDate object.

        Args:
            session: SQLAlchemy session
            mentioned_date: MentionedDate to update
            metadata: Relationship data with keys:
                - entries: List of Entry objects/IDs
                - locations: List of location names
                - people: List of person specs
                - remove_entries: Entries to unlink
                - remove_locations: Locations to unlink
                - remove_people: People to unlink
            incremental: If True, add/remove specified items.
                        If False, replace all relationships.
        """
        # --- Entries many-to-many ---
        if "entries" in metadata or "remove_entries" in metadata:
            RelationshipManager.update_many_to_many(
                session=session,
                parent_obj=mentioned_date,
                relationship_name="entries",
                items=metadata.get("entries", []),
                model_class=Entry,
                incremental=incremental,
                remove_items=metadata.get("remove_entries", []),
            )

        # --- Locations many-to-many ---
        if "locations" in metadata:
            if not incremental:
                mentioned_date.locations.clear()
                session.flush()

            # Process location names
            self._update_mentioned_date_locations(
                session, mentioned_date, metadata["locations"]
            )

        # Handle location removal
        if "remove_locations" in metadata:
            remove_names = [
                DataValidator.normalize_string(loc)
                for loc in metadata["remove_locations"]
            ]
            remove_names = [n for n in remove_names if n]

            for loc in list(mentioned_date.locations):
                if loc.name in remove_names:
                    mentioned_date.locations.remove(loc)

            if remove_names:
                session.flush()

        # --- People many-to-many ---
        if "people" in metadata:
            if not incremental:
                mentioned_date.people.clear()
                session.flush()

            # Process people specs
            self._update_mentioned_date_people(
                session, mentioned_date, metadata["people"]
            )

        # Handle people removal
        if "remove_people" in metadata:
            people_to_remove = []

            for person_spec in metadata["remove_people"]:
                if isinstance(person_spec, Person):
                    people_to_remove.append(person_spec)
                elif isinstance(person_spec, int):
                    person = session.get(Person, person_spec)
                    if person:
                        people_to_remove.append(person)
                elif isinstance(person_spec, str):
                    try:
                        person = self.get_person(session, person_name=person_spec)
                        if person:
                            people_to_remove.append(person)
                    except ValidationError:
                        continue
                elif isinstance(person_spec, dict):
                    try:
                        person = self.get_person(
                            session,
                            person_name=person_spec.get("name"),
                            person_full_name=person_spec.get("full_name"),
                        )
                        if person:
                            people_to_remove.append(person)
                    except ValidationError:
                        continue

            for person in people_to_remove:
                if person in mentioned_date.people:
                    mentioned_date.people.remove(person)

            if people_to_remove:
                session.flush()

    def _update_mentioned_date_locations(
        self,
        session: Session,
        mentioned_date: MentionedDate,
        locations_data: List[str],
    ) -> None:
        """
        Update locations associated with a mentioned date.

        Args:
            session: SQLAlchemy session
            mentioned_date: MentionedDate to update
            locations_data: List of location names
        """
        if mentioned_date.id is None:
            raise ValueError("MentionedDate must be persisted before linking locations")

        # Get existing location IDs to avoid duplicates
        existing_location_ids = {loc.id for loc in mentioned_date.locations}

        for loc_name in locations_data:
            # Normalize location name
            norm_name = DataValidator.normalize_string(loc_name)
            if not norm_name:
                continue

            # Find location by name
            location = session.query(Location).filter_by(name=norm_name).first()

            if not location:
                if self.logger:
                    self.logger.log_warning(
                        f"Location '{norm_name}' not found for date {mentioned_date.date}",
                        {
                            "date_id": mentioned_date.id,
                            "date": str(mentioned_date.date),
                            "location": norm_name,
                        },
                    )
                continue

            # Link if not already linked
            if location.id not in existing_location_ids:
                mentioned_date.locations.append(location)

        if locations_data:
            session.flush()

    def _update_mentioned_date_people(
        self,
        session: Session,
        mentioned_date: MentionedDate,
        people_data: List[Union[str, Dict[str, Any]]],
    ) -> None:
        """
        Update people associated with a mentioned date.

        Supports both simple names and full person specifications:
        - String: "John" (looks up by name)
        - Dict: {"name": "John"} or {"full_name": "John Smith"}
        - Dict with alias:
            {"alias": "Bobby", "name": "Bob"} or
            {"alias": ["Bobby", "Rob"], "full_name": "Robert Smith"}

        Args:
            session: SQLAlchemy session
            mentioned_date: MentionedDate to update
            people_data: List of person specifications
        """
        if mentioned_date.id is None:
            raise ValueError("MentionedDate must be persisted before linking people")

        # Get existing person IDs to avoid duplicates
        existing_person_ids = {p.id for p in mentioned_date.people}

        for person_spec in people_data:
            person = None

            if isinstance(person_spec, str):
                # Simple name lookup
                norm_name = DataValidator.normalize_string(person_spec)
                if not norm_name:
                    continue

                try:
                    person = self.get_person(session, person_name=norm_name)
                except ValidationError as e:
                    if self.logger:
                        self.logger.log_warning(
                            f"Could not resolve person '{norm_name}' for date: {e}",
                            {
                                "date_id": mentioned_date.id,
                                "date": str(mentioned_date.date),
                                "person_spec": norm_name,
                            },
                        )
                    continue

            elif isinstance(person_spec, dict):
                # Dict with name or full_name
                name = DataValidator.normalize_string(person_spec.get("name"))
                full_name = DataValidator.normalize_string(person_spec.get("full_name"))
                alias = person_spec.get("alias")

                # Try to resolve by name/full_name first
                if name or full_name:
                    try:
                        person = self.get_person(
                            session, person_name=name, person_full_name=full_name
                        )
                    except ValidationError as e:
                        if self.logger:
                            self.logger.log_warning(
                                f"Could not resolve person for date: {e}",
                                {
                                    "date_id": mentioned_date.id,
                                    "date": str(mentioned_date.date),
                                    "person_spec": person_spec,
                                },
                            )

                if not person and alias:
                    # Normalize alias (could be string or list)
                    alias_list = alias if isinstance(alias, list) else [alias]

                    for alias_str in alias_list:
                        norm_alias = DataValidator.normalize_string(alias_str)
                        if not norm_alias:
                            continue

                        # Look up alias in database
                        alias_obj = (
                            session.query(Alias).filter_by(alias=norm_alias).first()
                        )

                        if alias_obj:
                            person = alias_obj.person
                            if self.logger:
                                self.logger.log_debug(
                                    f"Resolved person via alias '{norm_alias}' for date",
                                    {
                                        "date_id": mentioned_date.id,
                                        "date": str(mentioned_date.date),
                                        "person_id": person.id,
                                        "person_name": person.display_name,
                                    },
                                )
                            break
                        else:
                            if self.logger:
                                self.logger.log_warning(
                                    f"Alias '{norm_alias}' not found in database for date",
                                    {
                                        "date_id": mentioned_date.id,
                                        "date": str(mentioned_date.date),
                                        "alias": norm_alias,
                                    },
                                )

                # If still not resolved, log warning
                if not person:
                    if self.logger:
                        self.logger.log_warning(
                            f"Could not resolve person spec for date {mentioned_date.date}",
                            {
                                "date_id": mentioned_date.id,
                                "person_spec": person_spec,
                            },
                        )
                    continue

            else:
                if self.logger:
                    self.logger.log_warning(
                        f"Invalid person spec format for date {mentioned_date.date}",
                        {
                            "date_id": mentioned_date.id,
                            "spec_type": type(person_spec).__name__,
                        },
                    )
                continue

            # Link if person found and not already linked
            if person and person.id not in existing_person_ids:
                mentioned_date.people.append(person)

        if people_data:
            session.flush()


    # -------------------------------------------------------------------------
    # Entity Operations Delegated to Modular Managers
    # -------------------------------------------------------------------------
    # All entity-specific CRUD operations are now handled by specialized managers.
    #
    # Use the manager properties within session_scope:
    #   - db.people: PersonManager
    #   - db.events: EventManager
    #   - db.locations: LocationManager
    #   - db.references: ReferenceManager
    #   - db.poems: PoemManager
    #   - db.manuscripts: ManuscriptManager
    #   - db.tags: TagManager
    #   - db.dates: DateManager
    #
    # Example:
    #   with db.session_scope() as session:
    #       person = db.people.create({"name": "Alice"})
    #       event = db.events.create({"name": "PyCon 2024"})
    # -------------------------------------------------------------------------

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
