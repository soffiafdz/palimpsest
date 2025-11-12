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

# Modular entity managers (Phase 2 & Phase 3)
from .managers import (
    TagManager,
    PersonManager,
    EventManager,
    DateManager,
    LocationManager,
    ReferenceManager,
    PoemManager,
    ManuscriptManager,
    EntryManager,
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
        self._entry_manager = EntryManager(session, self.logger)

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

    @property
    def entries(self) -> EntryManager:
        """
        Access EntryManager for entry operations.

        Recommended usage:
            with db.session_scope() as session:
                entry = db.entries.create({"date": "2024-01-15", "file_path": "/path.md"})
                entry = db.entries.get(entry_date="2024-01-15")
                db.entries.update(entry, {"notes": "Updated notes"})

        Raises:
            DatabaseError: If accessed outside of session_scope context
        """
        if self._entry_manager is None:
            raise DatabaseError(
                "EntryManager requires active session. "
                "Use within session_scope."
            )
        return self._entry_manager

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

    # -------------------------------------------------------------------------
    # Entry Operations - Delegated to EntryManager (Phase 3)
    # -------------------------------------------------------------------------
    # All Entry CRUD and relationship operations are now handled by EntryManager.
    #
    # New recommended usage:
    #   with db.session_scope() as session:
    #       entry = db.entries.create({"date": "2024-01-15", "file_path": "/path.md"})
    #       entry = db.entries.get(entry_date="2024-01-15")
    #       db.entries.update(entry, {"notes": "Updated"})
    #       db.entries.delete(entry)
    #
    # Legacy methods below delegate to EntryManager for backward compatibility:
    # -------------------------------------------------------------------------

    @handle_db_errors
    @log_database_operation("create_entry")
    @validate_metadata(["date", "file_path"])
    def create_entry(self, session: Session, metadata: Dict[str, Any]) -> Entry:
        """Create entry - delegates to EntryManager."""
        return self.entries.create(metadata)

    @handle_db_errors
    @log_database_operation("update_entry")
    def update_entry(
        self, session: Session, entry: Entry, metadata: Dict[str, Any]
    ) -> Entry:
        """Update entry - delegates to EntryManager."""
        return self.entries.update(entry, metadata)

    @handle_db_errors
    @log_database_operation("get_entry")
    def get_entry(
        self, session: Session, entry_date: Union[str, date]
    ) -> Optional[Entry]:
        """Get entry - delegates to EntryManager."""
        return self.entries.get(entry_date=entry_date)

    @handle_db_errors
    @log_database_operation("delete_entry")
    def delete_entry(self, session: Session, entry: Entry) -> None:
        """Delete entry - delegates to EntryManager."""
        self.entries.delete(entry)

    @handle_db_errors
    @log_database_operation("get_entry_for_display")
    def get_entry_for_display(
        self, session: Session, entry_date: Union[str, date]
    ) -> Optional[Entry]:
        """Get entry for display - delegates to EntryManager."""
        return self.entries.get_for_display(entry_date)

    @handle_db_errors
    @log_database_operation("bulk_create_entries")
    def bulk_create_entries(
        self,
        session: Session,
        entries_metadata: List[Dict[str, Any]],
        batch_size: int = 100,
    ) -> List[int]:
        """Bulk create entries - delegates to EntryManager."""
        return self.entries.bulk_create(entries_metadata, batch_size)

    # ---- Mentioned Date Helper Methods ----
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

    # ---- Missing Helper Methods (Phase 2 Integration) ----

    def get_person(
        self,
        session: Session,
        person_name: Optional[str] = None,
        person_full_name: Optional[str] = None,
    ) -> Optional[Person]:
        """
        Get person by name or full_name - delegates to PersonManager.

        This method exists for backward compatibility with existing code.
        """
        return self.people.get(person_name=person_name, full_name=person_full_name)

    def _update_entry_locations(
        self,
        session: Session,
        entry: Entry,
        locations_data: List[Any],
        incremental: bool = True,
    ) -> None:
        """
        Update entry locations using LocationManager.

        Args:
            session: SQLAlchemy session
            entry: Entry to update
            locations_data: List of location specs (strings, dicts, or Location objects)
            incremental: If True, add to existing. If False, replace all.
        """
        if entry.id is None:
            raise ValueError("Entry must be persisted before linking locations")

        if not incremental:
            entry.locations.clear()
            session.flush()

        existing_location_ids = {loc.id for loc in entry.locations}

        for loc_spec in locations_data:
            # Handle different input formats
            if isinstance(loc_spec, dict):
                location_name = DataValidator.normalize_string(loc_spec.get("name"))
                city_name = DataValidator.normalize_string(loc_spec.get("city"))

                if not location_name or not city_name:
                    continue

                # Get or create location via manager
                city = self.locations.get_or_create_city(city_name)
                location = self.locations.get_or_create_location(location_name, city)

            elif isinstance(loc_spec, str):
                # Just a location name - need city context
                location_name = DataValidator.normalize_string(loc_spec)
                if not location_name:
                    continue
                # Try to find existing location by name only
                location = self.locations.get(location_name=location_name)
                if not location:
                    if self.logger:
                        self.logger.log_warning(
                            f"Location '{location_name}' not found, skipping"
                        )
                    continue
            elif isinstance(loc_spec, Location):
                location = loc_spec
            else:
                if self.logger:
                    self.logger.log_warning(
                        f"Invalid location spec type: {type(loc_spec)}"
                    )
                continue

            if location and location.id not in existing_location_ids:
                entry.locations.append(location)

        session.flush()

    def _process_references(
        self,
        session: Session,
        entry: Entry,
        references_data: List[Dict[str, Any]],
    ) -> None:
        """
        Process references for an entry using ReferenceManager.

        References are one-to-many children of Entry (cascade delete).
        """
        if entry.id is None:
            raise ValueError("Entry must be persisted before adding references")

        for ref_data in references_data:
            content = DataValidator.normalize_string(ref_data.get("content"))
            description = DataValidator.normalize_string(ref_data.get("description"))

            if not content and not description:
                if self.logger:
                    self.logger.log_warning("Reference missing content/description, skipping")
                continue

            # Process source if provided
            source = None
            if "source" in ref_data and ref_data["source"]:
                source_data = ref_data["source"]
                if isinstance(source_data, dict):
                    title = DataValidator.normalize_string(source_data.get("title"))
                    if title:
                        # Get or create source via manager
                        source = self.references.get_or_create_source({
                            "title": title,
                            "type": source_data.get("type"),
                            "author": source_data.get("author"),
                            "publication_date": source_data.get("publication_date"),
                        })

            # Create reference via manager
            self.references.create({
                "content": content,
                "description": description,
                "mode": ref_data.get("mode", "direct"),
                "type": ref_data.get("type"),
                "speaker": ref_data.get("speaker"),
                "entry_id": entry.id,
                "source_id": source.id if source else None,
            })

    def _process_poems(
        self,
        session: Session,
        entry: Entry,
        poems_data: List[Dict[str, Any]],
    ) -> None:
        """
        Process poems for an entry using PoemManager.

        Poems are one-to-many children of Entry (cascade delete).
        """
        if entry.id is None:
            raise ValueError("Entry must be persisted before adding poems")

        for poem_data in poems_data:
            title = DataValidator.normalize_string(poem_data.get("title"))
            text = DataValidator.normalize_string(poem_data.get("text"))

            if not title or not text:
                if self.logger:
                    self.logger.log_warning("Poem missing title/text, skipping")
                continue

            # Parse revision date (default to entry date)
            revision_date = DataValidator.normalize_date(
                poem_data.get("revision_date") or entry.date
            )

            # Create poem version via manager
            self.poems.create_version({
                "title": title,
                "text": text,
                "revision_date": revision_date,
                "notes": poem_data.get("notes"),
                "entry_id": entry.id,
            })

    def create_or_update_manuscript_entry(
        self,
        session: Session,
        entry: Entry,
        manuscript_data: Dict[str, Any],
    ) -> None:
        """
        Create or update manuscript metadata for an entry using ManuscriptManager.
        """
        if entry.id is None:
            raise ValueError("Entry must be persisted before adding manuscript data")

        # Delegate to ManuscriptManager
        self.manuscripts.create_or_update_entry(entry, manuscript_data)

    # ---- Static Helper Methods for EntryManager ----
    # These allow EntryManager to call back to modular managers without circular dependencies

    @staticmethod
    def _get_person_static(
        session: Session,
        person_name: Optional[str] = None,
        person_full_name: Optional[str] = None,
    ) -> Optional[Person]:
        """Static method for PersonManager access from EntryManager."""
        from .managers import PersonManager
        person_mgr = PersonManager(session, None)
        return person_mgr.get(person_name=person_name, full_name=person_full_name)

    @staticmethod
    def _update_entry_locations_static(
        session: Session,
        entry: Entry,
        locations_data: List[Any],
        incremental: bool = True,
    ) -> None:
        """Static method for location processing from EntryManager."""
        from .managers import LocationManager
        location_mgr = LocationManager(session, None)

        if entry.id is None:
            raise ValueError("Entry must be persisted before linking locations")

        if not incremental:
            entry.locations.clear()
            session.flush()

        existing_location_ids = {loc.id for loc in entry.locations}

        for loc_spec in locations_data:
            # Handle different input formats
            if isinstance(loc_spec, dict):
                location_name = DataValidator.normalize_string(loc_spec.get("name"))
                city_name = DataValidator.normalize_string(loc_spec.get("city"))

                if not location_name or not city_name:
                    continue

                # Get or create location via manager
                city = location_mgr.get_or_create_city(city_name)
                location = location_mgr.get_or_create_location(location_name, city)

            elif isinstance(loc_spec, str):
                # Just a location name - need city context
                location_name = DataValidator.normalize_string(loc_spec)
                if not location_name:
                    continue
                # Try to find existing location by name only
                location = location_mgr.get(location_name=location_name)
                if not location:
                    continue
            elif isinstance(loc_spec, Location):
                location = loc_spec
            else:
                continue

            if location and location.id not in existing_location_ids:
                entry.locations.append(location)

        session.flush()

    @staticmethod
    def _process_references_static(
        session: Session,
        entry: Entry,
        references_data: List[Dict[str, Any]],
    ) -> None:
        """Static method for reference processing from EntryManager."""
        from .managers import ReferenceManager
        reference_mgr = ReferenceManager(session, None)

        if entry.id is None:
            raise ValueError("Entry must be persisted before adding references")

        for ref_data in references_data:
            content = DataValidator.normalize_string(ref_data.get("content"))
            description = DataValidator.normalize_string(ref_data.get("description"))

            if not content and not description:
                continue

            # Process source if provided
            source = None
            if "source" in ref_data and ref_data["source"]:
                source_data = ref_data["source"]
                if isinstance(source_data, dict):
                    title = DataValidator.normalize_string(source_data.get("title"))
                    if title:
                        # Get or create source via manager
                        source = reference_mgr.get_or_create_source({
                            "title": title,
                            "type": source_data.get("type"),
                            "author": source_data.get("author"),
                            "publication_date": source_data.get("publication_date"),
                        })

            # Create reference via manager
            reference_mgr.create({
                "content": content,
                "description": description,
                "mode": ref_data.get("mode", "direct"),
                "type": ref_data.get("type"),
                "speaker": ref_data.get("speaker"),
                "entry_id": entry.id,
                "source_id": source.id if source else None,
            })

    @staticmethod
    def _process_poems_static(
        session: Session,
        entry: Entry,
        poems_data: List[Dict[str, Any]],
    ) -> None:
        """Static method for poem processing from EntryManager."""
        from .managers import PoemManager
        poem_mgr = PoemManager(session, None)

        if entry.id is None:
            raise ValueError("Entry must be persisted before adding poems")

        for poem_data in poems_data:
            title = DataValidator.normalize_string(poem_data.get("title"))
            text = DataValidator.normalize_string(poem_data.get("text"))

            if not title or not text:
                continue

            # Parse revision date (default to entry date)
            revision_date = DataValidator.normalize_date(
                poem_data.get("revision_date") or entry.date
            )

            # Create poem version via manager
            poem_mgr.create_version({
                "title": title,
                "text": text,
                "revision_date": revision_date,
                "notes": poem_data.get("notes"),
                "entry_id": entry.id,
            })

    @staticmethod
    def _create_or_update_manuscript_entry_static(
        session: Session,
        entry: Entry,
        manuscript_data: Dict[str, Any],
    ) -> None:
        """Static method for manuscript processing from EntryManager."""
        from .managers import ManuscriptManager
        manuscript_mgr = ManuscriptManager(session, None)

        if entry.id is None:
            raise ValueError("Entry must be persisted before adding manuscript data")

        # Delegate to ManuscriptManager
        manuscript_mgr.create_or_update_entry(entry, manuscript_data)

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
