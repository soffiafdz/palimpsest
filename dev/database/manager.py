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
from contextlib import contextmanager
from datetime import datetime

from pathlib import Path
from typing import Any, Dict, Optional, Union, List, Type, TypeVar, Protocol

# --- Third party ---
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker, Mapped

from alembic.config import Config
from alembic import command
from alembic.runtime.migration import MigrationContext

# --- Local imports ---
from dev.core.backup_manager import BackupManager
from dev.core.exceptions import DatabaseError
from dev.core.paths import ROOT
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from .models import (
    Base,
    Location,
    Reference,
    PoemVersion,
    Tag,
    Theme,
    Scene,
)

from .decorators import DatabaseOperation
from .health_monitor import HealthMonitor
from .query_analytics import QueryAnalytics

# Modular entity managers
from .managers import (
    SimpleManager,
    TagManager,
    EventManager,
    PersonManager,
    LocationManager,
    ReferenceManager,
    PoemManager,
    EntryManager,
)


class HasId(Protocol):
    """Protocol for objects that have an id attribute."""

    id: Mapped[int]


T = TypeVar("T", bound=HasId)


class ManagerProperty:
    """
    Descriptor for lazy manager properties with automatic session validation.

    This eliminates boilerplate property definitions by automatically checking
    if the manager is None and raising appropriate errors.

    Usage:
        class MyDB:
            tags = ManagerProperty("_tag_manager", "TagManager")

            def __init__(self):
                self._tag_manager = None
    """

    def __init__(self, attr_name: str, manager_name: str):
        """
        Initialize the descriptor.

        Args:
            attr_name: Name of the private attribute (e.g., "_tag_manager")
            manager_name: Display name for error messages (e.g., "TagManager")
        """
        self.attr_name = attr_name
        self.manager_name = manager_name

    def __get__(self, obj: Any, objtype: Optional[Type] = None) -> Any:
        """Get the manager or raise an error if accessed outside session."""
        if obj is None:
            return self

        manager = getattr(obj, self.attr_name)
        if manager is None:
            raise DatabaseError(
                f"{self.manager_name} requires active session. "
                "Use within session_scope: "
                f"with db.session_scope() as session: db.{self.attr_name[1:]}.create(...)"
            )
        return manager

    def __set__(self, obj: Any, value: Any) -> None:
        """Set the manager value."""
        setattr(obj, self.attr_name, value)


# --- Main Database Manager ---
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

    # Manager descriptors - automatically validate session context
    tags = ManagerProperty("_tag_manager", "TagManager")
    events = ManagerProperty("_event_manager", "EventManager")
    people = ManagerProperty("_person_manager", "PersonManager")
    locations = ManagerProperty("_location_manager", "LocationManager")
    references = ManagerProperty("_reference_manager", "ReferenceManager")
    poems = ManagerProperty("_poem_manager", "PoemManager")
    entries = ManagerProperty("_entry_manager", "EntryManager")

    # --- Initialization ---
    def __init__(
        self,
        db_path: Union[str, Path],
        alembic_dir: Optional[Union[str, Path]] = None,
        log_dir: Optional[Union[str, Path]] = None,
        backup_dir: Optional[Union[str, Path]] = None,
        enable_auto_backup: bool = True,
    ) -> None:
        """
        Initialize database engine and session factory.

        Args:
            db_path (str | Path): Path to the SQLite  file.
            alembic_dir (str | Path): Path to the Alembic directory (optional, None for tests).
            log_dir (str | Path): Directory for log files (optional)
            backup_dir (str | Path): Directory for backups (optional)
            enable_auto_backup (bool): Whether to enable automatic backups

        """
        self.db_path = Path(db_path).expanduser().resolve()
        self.alembic_dir = Path(alembic_dir).expanduser().resolve() if alembic_dir else None

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
        self.query_analytics = QueryAnalytics(self.logger)

        # Initialize modular entity managers (lazy-loaded in session_scope)
        # Note: TagManager/EventManager are factories that return SimpleManager
        self._tag_manager: Optional[SimpleManager] = None
        self._event_manager: Optional[SimpleManager] = None
        self._person_manager: Optional[PersonManager] = None
        self._location_manager: Optional[LocationManager] = None
        self._reference_manager: Optional[ReferenceManager] = None
        self._poem_manager: Optional[PoemManager] = None
        self._entry_manager: Optional[EntryManager] = None

        # Initialize database
        self._setup_engine()

        # Auto-backup if enabled
        if enable_auto_backup and self.backup_manager:
            self.backup_manager.auto_backup()

    def _setup_engine(self) -> None:
        """Initialize database engine and session factory."""
        try:
            safe_logger(self.logger).log_operation(
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

            safe_logger(self.logger).log_operation("database_init_complete", {"success": True})

        except Exception as e:
            safe_logger(self.logger).log_error(e, {"operation": "database_init"})
            raise DatabaseError(f"Database initialization failed: {e}")

    # --- Session Management ---
    @contextmanager
    def session_scope(self):
        """
        Provide a transactional scope around operations with logging.

        Also initializes modular entity managers for use within the session.
        Managers are available via properties (db.people, db.tags, etc.)

        Usage (both syntaxes supported):
            with db.session_scope() as session:
                # Direct manager access (recommended for new code)
                person = db.people.create({"name": "Alice"})
                tag = db.tags.get_or_create("python")

                # Facade API (stable, used by yaml2sql/sql2yaml)
                entry = db.create_entry(session, metadata)
        """
        session = self.SessionLocal()
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        # Initialize modular managers for this session
        self._tag_manager = TagManager(session, self.logger)
        self._event_manager = EventManager(session, self.logger)
        self._person_manager = PersonManager(session, self.logger)
        self._location_manager = LocationManager(session, self.logger)
        self._reference_manager = ReferenceManager(session, self.logger)
        self._poem_manager = PoemManager(session, self.logger)
        self._entry_manager = EntryManager(session, self.logger)

        safe_logger(self.logger).log_debug("session_start", {"session_id": session_id})

        try:
            yield session
            session.commit()
            safe_logger(self.logger).log_debug("session_commit", {"session_id": session_id})

        except Exception as e:
            session.rollback()
            safe_logger(self.logger).log_error(
                e, {"operation": "session_rollback", "session_id": session_id}
            )
            raise
        finally:
            # Clean up managers
            self._tag_manager = None
            self._event_manager = None
            self._person_manager = None
            self._location_manager = None
            self._reference_manager = None
            self._poem_manager = None
            self._entry_manager = None

            session.close()
            safe_logger(self.logger).log_debug("session_close", {"session_id": session_id})

    def get_session(self) -> Session:
        """Create and return a new SQLAlchemy session."""
        return self.SessionLocal()

    @contextmanager
    def transaction(self):
        """Context manager for database transactions with logging."""
        with self.session_scope() as session:
            yield session

    # -------------------------------------------------------------------------

    # --- Alembic setup ---
    def _setup_alembic(self) -> Config:
        """Setup Alembic configuration."""
        try:
            safe_logger(self.logger).log_debug("Setting up Alembic configuration...")

            alembic_cfg: Config = Config(str(ROOT / "alembic.ini"))
            alembic_cfg.set_main_option("script_location", str(self.alembic_dir))
            alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{self.db_path}")
            alembic_cfg.set_main_option(
                "file_template",
                "%%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d_%%(slug)s",
            )

            safe_logger(self.logger).log_debug("Alembic configuration setup complete")
            return alembic_cfg
        except Exception as e:
            safe_logger(self.logger).log_error(e, {"operation": "setup_alembic"})
            raise DatabaseError(f"Alembic configuration failed: {e}")

    def init_alembic(self) -> None:
        """
        Initialize Alembic in the project directory.

        Actions:
            Creates Alembic directory with standard structure
            Updates alembic/env.py to import Palimpsest Base metadata
            Prints instructions for first migration
        """
        with DatabaseOperation(self.logger, "init_alembic"):
            try:
                if self.alembic_dir is not None and not self.alembic_dir.is_dir():
                    command.init(self.alembic_cfg, str(self.alembic_dir))
                    self._update_alembic_env()
                else:
                    safe_logger(self.logger).log_debug(
                        f"Alembic already initialized in {self.alembic_dir}"
                    )
            except Exception as e:
                raise DatabaseError(f"Alembic initialization failed: {e}")

    def _update_alembic_env(self) -> None:
        """Update the generated alembic/env.py to import Palimpsest models."""
        if self.alembic_dir is None:
            raise DatabaseError("Alembic directory not configured")
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
                    safe_logger(self.logger).log_operation(
                        "alembic_env_updated", {"env_path": str(env_path)}
                    )
        except Exception as e:
            safe_logger(self.logger).log_error(e, {"operation": "update_alembic_env"})
            raise DatabaseError(f"Could not update Alembic environment: {e}")

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
        with DatabaseOperation(self.logger, "initialize_schema"):
            try:
                with self.engine.connect() as conn:
                    inspector = self.engine.dialect.get_table_names(conn)
                    is_fresh_db: bool = len(inspector) == 0

                if is_fresh_db:
                    Base.metadata.create_all(bind=self.engine)
                    try:
                        command.stamp(self.alembic_cfg, "head")
                        safe_logger(self.logger).log_operation(
                            "fresh_database_created",
                            {"tables_created": len(Base.metadata.tables)},
                        )
                    except Exception as e:
                        safe_logger(self.logger).log_error(e, {"operation": "stamp_database"})
                else:
                    self.upgrade_database()
                    safe_logger(self.logger).log_operation(
                        "existing_database_migrated",
                        {"table_count": len(inspector)},
                    )

            except Exception as e:
                raise DatabaseError(f"Could not initialize database: {e}")

    def upgrade_database(self, revision: str = "head") -> None:
        """
        Upgrade the database schema to the specified Alembic revision.

        Args:
            revision (str, optional):
                The target revision to upgrade to.
                Defaults to 'head' (latest revision).
        """
        with DatabaseOperation(self.logger, "upgrade_database"):
            try:
                command.upgrade(self.alembic_cfg, revision)
            except Exception as e:
                raise DatabaseError(f"Database upgrade failed: {e}")

    def create_migration(self, message: str) -> str:
        """
        Create a new Alembic migration.

        Args:
            message (str): Description of the migration.
        Returns:
            revision
        """
        with DatabaseOperation(self.logger, "create_migration"):
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

    def downgrade_database(self, revision: str) -> None:
        """
        Downgrade the database schema to a specified Alembic revision.

        Args:
            revision (str): The target revision to downgrade to.
        """
        with DatabaseOperation(self.logger, "downgrade_database"):
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
            safe_logger(self.logger).log_error(e, {"operation": "get_migration_history"})
            return {"error": str(e)}

    # -------------------------------------------------------------------------
    # Entity operations use modular managers via properties:
    #   db.entries, db.people, db.events, db.locations, db.references,
    #   db.poems, db.tags
    #
    # Example:
    #   with db.session_scope() as session:
    #       entry = db.entries.create({"date": "2024-01-15", "file_path": "/path.md"})
    #       person = db.people.create({"name": "Alice"})
    # -------------------------------------------------------------------------

    # --- Cleanup Operations ---
    def bulk_cleanup_unused(
        self, session: Session, cleanup_config: Dict[str, tuple]
    ) -> Dict[str, int]:
        """Perform bulk cleanup operations more efficiently."""
        with DatabaseOperation(self.logger, "bulk_cleanup_unused"):
            return self.health_monitor.bulk_cleanup_unused(session, cleanup_config)

    def cleanup_all_metadata(self) -> Dict[str, int]:
        """Run safe cleanup operations with proper transaction handling."""
        with DatabaseOperation(self.logger, "cleanup_all_metadata"):
            cleanup_config = {
                "tags": (Tag, "entries"),
                "locations": (Location, "entries"),
                "scenes": (Scene, "entry"),
                "themes": (Theme, "entries"),
                "references": (Reference, "entry"),
                "poem_versions": (PoemVersion, "entry"),
            }

            try:
                with self.session_scope() as session:
                    return self.bulk_cleanup_unused(session, cleanup_config)
            except Exception as e:
                safe_logger(self.logger).log_error(e, {"operation": "cleanup_all_metadata"})
                raise DatabaseError(f"Cleanup operation failed: {e}")

    # --- Backup Integration ---
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

    # --- Context Manager Support ---
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
                safe_logger(self.logger).log_error(e, {"operation": "exit_auto_backup"})
