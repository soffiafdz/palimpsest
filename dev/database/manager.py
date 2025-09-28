#!/usr/bin/env python3
"""
manager.py
-------------------
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
import csv
import json
import logging
import os
import shutil
import tempfile
import traceback

from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import ExceptHookArgs
from typing import (
    Any,
    Callable,
    Dict,
    IO,
    List,
    Optional,
    Protocol,
    runtime_checkable,
    Tuple,
    Type,
    TypeVar,
    Union,
)

# --- Third party ---
# import yaml
from alembic.config import Config
from alembic import command
from alembic.runtime.migration import MigrationContext

from sqlalchemy import create_engine, Engine, text, and_, or_, func
from sqlalchemy import exc
from sqlalchemy.orm import Mapped, Session, sessionmaker
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

# --- Local imports ---
from dev.paths import ROOT
from dev.utils import md, fs
from dev.database.models import (
    Base,
    Entry,
    # entry_related,
    MentionedDate,
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
from dev.database.models_manuscript import (
    ManuscriptStatus,
    ManuscriptEntry,
    ManuscriptEvent,
    ManuscriptPerson,
    Arc,
    Theme,
)


@runtime_checkable
class HasId(Protocol):
    id: Mapped[int]


T = TypeVar("T", bound=HasId)
C = TypeVar("C", bound=HasId)


# ----- Errors -----
class DatabaseError(Exception):
    """Custom exception for database-related errors."""

    pass


class ValidationError(Exception):
    """Custom exception for validation errors."""

    pass


class BackupError(Exception):
    """Custom exception for backup-related errors."""

    pass


class TemporalFileError(Exception):
    """Custom exception for temporal file operations."""

    pass


# ----- Temporal File Manager -----
class TemporalFileManager:
    """Manages temporal files with automatic cleanup."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir else Path(tempfile.gettempdir())
        self.active_files: List[Path] = []
        self.active_dirs: List[Path] = []
        self._temp_file_handles: List[IO[Any]] = []

    def create_temp_file(
        self, suffix: str = "", prefix: str = "palimpsest_", delete: bool = False
    ) -> Path:
        """Create a temporary file and track it for cleanup."""
        try:
            temp_file_obj = tempfile.NamedTemporaryFile(
                suffix=suffix, prefix=prefix, dir=self.base_dir, delete=delete
            )

            temp_path = Path(temp_file_obj.name)

            if delete:
                # Keep reference to prevente premature deletion
                self._temp_file_handles.append(temp_file_obj)
            else:
                # Close the file handle but keep the file
                temp_file_obj.close()
                self.active_files.append(temp_path)

            return temp_path

        except Exception as e:
            raise TemporalFileError(f"Failed to create temporary file: {e}")

    def create_temp_dir(self, prefix: str = "palimpsest_") -> Path:
        """Create a temporary directory and track it for cleanup."""
        try:
            temp_dir = Path(tempfile.mkdtemp(prefix=prefix, dir=self.base_dir))
            self.active_dirs.append(temp_dir)
            return temp_dir
        except Exception as e:
            raise TemporalFileError(f"Failed to create temporary directory: {e}")

    def create_secure_temp_file(
        self,
        suffix: str = "",
        prefix: str = "palimpsest_",
    ) -> Tuple[int, Path]:
        """
        Create a secure temporary file using mkstemp.

        Returns:
            Tuple of (file_descriptor, file_path)
            Note: Caller is responsible for closing the file descriptor
        """
        try:
            fd, temp_path = tempfile.mkstemp(
                suffix=suffix, prefix=prefix, dir=self.base_dir
            )
            path_obj = Path(temp_path)
            self.active_files.append(path_obj)
            return fd, path_obj
        except Exception as e:
            raise TemporalFileError(f"Failed to create secure temporary file: {e}")

    def cleanup(self) -> Dict[str, int]:
        """Clean up all tracked temporary files and directories."""
        cleanup_stats = {"files_removed": 0, "dirs_removed": 0, "errors": 0}

        # Clean up temporary file handles
        for temp_handle in self._temp_file_handles[:]:
            try:
                temp_handle.close()
                self._temp_file_handles.remove(temp_handle)
            except Exception:
                cleanup_stats["errors"] += 1

        # Clean up tracked filfes
        for temp_file in self.active_files[:]:
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    cleanup_stats["files_removed"] += 1
                self.active_files.remove(temp_file)
            except Exception:
                cleanup_stats["errors"] += 1

        # Clean up directories
        for temp_dir in self.active_dirs[:]:
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                    cleanup_stats["dirs_removed"] += 1
                self.active_dirs.remove(temp_dir)
            except Exception:
                cleanup_stats["errors"] += 1

        return cleanup_stats

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        del exc_type, exc_val, exc_tb
        self.cleanup()


# ----- Logging System -----
class DatabaseLogger:
    """Centralized logging system for database operations."""

    def __init__(self, log_dir: Path, db_name: str = "palimpsest"):
        self.log_dir = Path(log_dir)
        self.db_name = db_name
        self._setup_loggers()

    def _setup_loggers(self) -> None:
        """Initialize logging system with multiple handlers."""
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Main database logger
        self.db_logger = logging.getLogger(f"{self.db_name}.database")
        self.db_logger.setLevel(logging.DEBUG)

        # Error logger (Error and above)
        self.error_logger = logging.getLogger(f"{self.db_name}.errors")
        self.error_logger.setLevel(logging.ERROR)

        # Clear existing handlers to avoid duplicates
        for logger in [self.db_logger, self.error_logger]:
            logger.handlers.clear()

        # Create handlers
        self._create_file_handler(
            self.db_logger, self.log_dir / "database.log", logging.DEBUG
        )
        self._create_file_handler(
            self.error_logger, self.log_dir / "errors.log", logging.ERROR
        )

        # Console handler for development
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
        )
        console_handler.setFormatter(console_formatter)

        self.db_logger.addHandler(console_handler)

    def _create_file_handler(
        self, logger: logging.Logger, file_path: Path, level: int
    ) -> None:
        """Create a rotating file handler for a logger."""

        handler = RotatingFileHandler(
            file_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        handler.setLevel(level)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    def log_operation(self, operation: str, details: Dict[str, Any]) -> None:
        """Log a database operation with context."""
        self.db_logger.info(
            f"OPERATION - {operation}: {json.dumps(details, default=str)}"
        )

    def log_error(self, error: Exception, context: Dict[str, Any]) -> None:
        """Log an error with full context."""
        error_info = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            "traceback": traceback.format_exc(),
        }
        error_msg = f"ERROR - {json.dumps(error_info, default=str)}"

        # Log to both database.log (via db_logger) and errors.log (via error_logger)
        self.db_logger.error(error_msg)
        self.error_logger.error(error_msg)

    def log_debug(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log debug information - goes sto main database.log."""
        if details:
            self.db_logger.debug(
                f"DEBUG - {message}: {json.dumps(details, default=str)}"
            )
        else:
            self.db_logger.debug(f"DEBUG - {message}")

    def log_info(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log general information - goes to main database.log."""
        if details:
            self.db_logger.info(f"INFO - {message}: {json.dumps(details, default=str)}")
        else:
            self.db_logger.info(f"INFO - {message}")


# ----- Backup System -----
class BackupManager:
    """Handles database backup and recovery operations."""

    def __init__(
        self,
        db_path: Path,
        backup_dir: Path,
        retention_days: int = 30,
        logger: Optional[DatabaseLogger] = None,
    ):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.retention_days = retention_days
        self.logger = logger

        # Create backup directories
        (self.backup_dir / "daily").mkdir(parents=True, exist_ok=True)
        (self.backup_dir / "weekly").mkdir(parents=True, exist_ok=True)
        (self.backup_dir / "manual").mkdir(parents=True, exist_ok=True)

    def create_backup(
        self,
        backup_type: str = "manual",
        suffix: Optional[str] = None,
    ) -> Path:
        """Create a timestamped database backup."""
        if not self.db_path.exists():
            raise BackupError(f"Database file not found: {self.db_path}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if suffix:
            backup_name = f"{self.db_path.stem}_{timestamp}_{suffix}.db"
        else:
            backup_name = f"{self.db_path.stem}_{timestamp}.db"

        backup_path = self.backup_dir / backup_type / backup_name

        try:
            shutil.copy2(self.db_path, backup_path)

            if self.logger:
                self.logger.log_operation(
                    "backup_created",
                    {
                        "backup_type": backup_type,
                        "backup_path": str(backup_path),
                        "original_size": self.db_path.stat().st_size,
                        "backup_size": backup_path.stat().st_size,
                    },
                )

            return backup_path

        except Exception as e:
            if self.logger:
                self.logger.log_error(
                    e,
                    {
                        "operation": "create_backup",
                        "backup_type": backup_type,
                        "target_path": str(backup_path),
                    },
                )
            raise BackupError(f"Failed to create backup: {e}")

    def auto_backup(self) -> Optional[Path]:
        """Create automatic daily backup with cleanup."""
        try:
            # Create daily backup
            backup_path = self.create_backup("daily", "auto")

            # Cleanup old backups
            self._cleanup_old_backups()

            return backup_path

        except Exception as e:
            if self.logger:
                self.logger.log_error(e, {"operation": "auto_backup"})
            return None

    def create_weekly_backup(self) -> Path:
        """Create weekly backup (typically called on Sundays)."""
        return self.create_backup("weekly", f"week_{datetime.now().strftime('%U')}")

    def _cleanup_old_backups(self) -> None:
        """Remove backups older than retention period."""
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)

        for backup_type in ["daily", "weekly"]:
            backup_dir = self.backup_dir / backup_type
            if not backup_dir.exists():
                continue

            removed_count = 0
            for backup_file in backup_dir.glob("*.db"):
                try:
                    file_mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
                    if file_mtime < cutoff_date:
                        backup_file.unlink()
                        removed_count += 1
                except Exception as e:
                    if self.logger:
                        self.logger.log_error(
                            e, {"operation": "cleanup_backup", "file": str(backup_file)}
                        )

            if removed_count > 0 and self.logger:
                self.logger.log_operation(
                    "backup_cleanup",
                    {
                        "backup_type": backup_type,
                        "removed_count": removed_count,
                        "retention_days": self.retention_days,
                    },
                )

    def restore_backup(self, backup_path: Path) -> None:
        """Restore database from backup."""
        if not backup_path.exists():
            raise BackupError(f"Backup file not found: {backup_path}")

        # Create current backup before restore
        current_backup = self.create_backup("manual", "pre_restore")

        try:
            shutil.copy2(backup_path, self.db_path)

            if self.logger:
                self.logger.log_operation(
                    "restore_backup",
                    {
                        "restored_from": str(backup_path),
                        "pre_restore_backup": str(current_backup),
                    },
                )

        except Exception as e:
            if self.logger:
                self.logger.log_error(
                    e, {"operation": "restore_backup", "backup_path": str(backup_path)}
                )
            raise BackupError(f"Failed to restore backup: {e}")

    def list_backups(self) -> Dict[str, List[Dict[str, Any]]]:
        """List all available backups with metadata."""
        backups = {"daily": [], "weekly": [], "manual": []}

        for backup_type in backups.keys():
            backup_dir = self.backup_dir / backup_type
            if not backup_dir.exists():
                continue

            for backup_file in sorted(backup_dir.glob("*.db")):
                stat = backup_file.stat()
                backups[backup_type].append(
                    {
                        "name": backup_file.name,
                        "path": str(backup_file),
                        "size": stat.st_size,
                        "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "age_days": (
                            datetime.now() - datetime.fromtimestamp(stat.st_mtime)
                        ).days,
                    }
                )

        return backups


# ----- Operation Decorators -----
def log_database_operation(operation_name: str):
    """Decorator to log database operations."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            start_time = datetime.now()
            operation_id = f"{operation_name}_{start_time.strftime('%Y%m%d_%H%M%S_%f')}"

            if hasattr(self, "logger") and self.logger:
                self.logger.log_debug(
                    f"Starting {operation_name}",
                    {
                        "operation_id": operation_id,
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys()),
                    },
                )

            try:
                result = func(self, *args, **kwargs)

                duration = (datetime.now() - start_time).total_seconds()
                if hasattr(self, "logger") and self.logger:
                    self.logger.log_operation(
                        f"{operation_name}_completed",
                        {
                            "operation_id": operation_id,
                            "duration_seconds": duration,
                            "success": True,
                        },
                    )

                return result

            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                if hasattr(self, "logger") and self.logger:
                    self.logger.log_error(
                        e,
                        {
                            "operation": operation_name,
                            "operation_id": operation_id,
                            "duration_seconds": duration,
                        },
                    )
                raise

        return wrapper

    return decorator


def validate_metadata(required_fields: List[str]):
    """Decorator to validate metadata dictionaries before processing."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, session: Session, *args, **kwargs):
            # Assume metadata is the last positional arg or in kwargs
            metadata = args[-1] if args else kwargs.get("metadata", {})

            if not isinstance(metadata, dict):
                raise ValidationError(f"Expected metadata dict, got {type(metadata)}")

            for field in required_fields:
                if field not in metadata or not metadata[field]:
                    raise ValidationError(f"Required field '{field}' missing or empty")

            return func(self, session, *args, **kwargs)

        return wrapper

    return decorator


def handle_db_errors(func: Callable) -> Callable:
    """Decorator to handle common database errors."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except IntegrityError as e:
            raise DatabaseError(f"Data integrity violation: {e}")
        except SQLAlchemyError as e:
            raise DatabaseError(f"Database operation failed: {e}")
        except Exception:
            raise

    return wrapper


# ----- Relationships -----
class RelationshipManager:
    """Handles generic relationship updates: one-to-one, one-to-many and many-to-many."""

    @staticmethod
    def update_one_to_one(
        session: Session,
        parent_obj: HasId,
        relationship_name: str,
        model_class: Type[C],
        foreign_key_attr: str,
        child_data: Dict[str, Any] = {},
        delete: bool = False,
    ) -> Optional[C]:
        """
        Update a one-to-one relationship.

        Args:
            session: a SQLAlchemy session
            parent_obj: The parent object (e.g., Entry)
            relationship_name: name of the relationship column.
            model_class: The child model class (e.g., ManuscriptEntry)
            child_data: Data to update/create the child object
            foreign_key_attr: Foreign key attribute name on child (e.g., 'entry_id')
            delete: Whether to delete an existing relationship

        Returns:
            The child object or None if deleted/not created
        """
        if parent_obj.id is None:
            raise ValueError(
                f"{parent_obj.__class__.__name__} must be persisted before linking"
            )

        existing_child: Optional[C] = getattr(parent_obj, relationship_name, None)

        if existing_child:
            # -- Deletion request --
            if delete:
                session.delete(existing_child)
                session.flush()
                return None
            # -- Update --
            if child_data:
                for key, value in child_data.items():
                    if hasattr(existing_child, key):
                        setattr(existing_child, key, value)
                session.flush()
            return existing_child

        # -- Create --
        child_data[foreign_key_attr] = parent_obj.id
        child_obj = model_class(**child_data)
        session.add(child_obj)
        session.flush()
        return child_obj

    @staticmethod
    def update_one_to_many(
        session: Session,
        parent_obj: HasId,
        items: List[Union[C, int, Dict[str, Any]]],
        model_class: Type[C],
        foreign_key_attr: str,
        incremental: bool = True,
        remove_items: Optional[List[Union[T, int]]] = None,
    ) -> bool:
        """
        Generic one-to-many relationship updater.

        For one-to-many relationships where the child objects belong to only one parent.
        This updates the foreign key on the child objects rather than using collections.

        Args:
            session: a SQLAlchemy session
            parent_obj: The parent object (e.g., Entry)
            items: List of child objects, IDs, or creation data
            model_class: The child model class (e.g., Poem, Reference)
            foreign_key_attr: The foreign key attribute name on the child (e.g., 'entry_id')
            incremental: If False, removes all existing children first
            remove_items: Items to explicitly remove (incremental mode only)

        Returns:
            bool: True if any changes were made
        """
        if parent_obj.id is None:
            raise ValueError(
                f"{parent_obj.__class__.__name__} must be persisted before linking"
            )

        changed = False

        # Get existing children
        existing_children = (
            session.query(model_class)
            .filter(getattr(model_class, foreign_key_attr) == parent_obj.id)
            .all()
        )
        existing_ids = {child.id for child in existing_children}

        # Clear all existing if not incremental
        if not incremental:
            for child in existing_children:
                setattr(child, foreign_key_attr, None)
                changed = True

        # Process new items
        for item in items:
            if isinstance(item, dict):
                # Create new object from metadata
                child_obj = model_class(**item)
                session.add(child_obj)
                session.flush()  # Get the ID
                setattr(child_obj, foreign_key_attr, parent_obj.id)
                changed = True
            else:
                # Resolve existing object
                child_obj = RelationshipManager._resolve_object(
                    session, item, model_class
                )
                current_parent_id = getattr(child_obj, foreign_key_attr)

                if current_parent_id != parent_obj.id:
                    setattr(child_obj, foreign_key_attr, parent_obj.id)
                    changed = True

        # Remove specified items (incremental mode only)
        if incremental and remove_items:
            for item in remove_items:
                child_obj = RelationshipManager._resolve_object(
                    session, item, model_class
                )
                if child_obj.id in existing_ids:
                    setattr(child_obj, foreign_key_attr, None)
                    changed = True

        if changed:
            session.flush()

        return changed

    @staticmethod
    def update_many_to_many(
        session: Session,
        parent_obj: HasId,
        relationship_name: str,
        items: List[Union[C, int]],
        model_class: Type[C],
        incremental: bool = True,
        remove_items: Optional[List[Union[C, int]]] = None,
    ) -> bool:
        """
        Generic many-to-many relationship updater.

        Args:
            session: a SQLAlchemy session
            parent_obj: The parent object (e.g., Entry)
            relationship_name: name of the relationship column.
            items: List of child objects, IDs, or creation data
            model_class: The child model class (e.g., Poem, Reference)
            incremental: If False, removes all existing children first
            remove_items: Items to explicitly remove (incremental mode only)

        Returns:
            bool: True if any changes were made
        """
        if parent_obj.id is None:
            raise ValueError(
                f"{parent_obj.__class__.__name__} must be persisted before linking"
            )

        relationship = getattr(parent_obj, relationship_name)
        existing_ids = {obj.id for obj in relationship}
        changed = False

        # Clear all if not incremental
        if not incremental:
            relationship.clear()
            changed = True

        # Add new items
        for item in items:
            obj = RelationshipManager._resolve_object(session, item, model_class)
            if obj.id not in existing_ids:
                relationship.append(obj)
                changed = True

        # Remove specified items (incremental mode only)
        if incremental and remove_items:
            for item in remove_items:
                obj = RelationshipManager._resolve_object(session, item, model_class)
                if obj.id in existing_ids:
                    relationship.remove(obj)
                    changed = True

        if changed:
            session.flush()

        return changed

    @staticmethod
    def _resolve_object(
        session: Session, item: Union[T, int], model_class: Type[T]
    ) -> T:
        """Resolve an item to an ORM object."""
        if isinstance(item, model_class):
            if item.id is None:
                raise ValueError(f"{model_class.__name__} instance must be persisted")
            return item
        elif isinstance(item, int):
            obj = session.get(model_class, item)
            if obj is None:
                raise ValueError(f"No {model_class.__name__} found with id: {item}")
            return obj
        else:
            raise TypeError(
                f"Expected {model_class.__name__} instance or int, got {type(item)}"
            )


# ----- Database Manager -----
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
            self.log_dir = Path(log_dir).expanduser().resolve()
            self.logger = DatabaseLogger(self.log_dir)
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

            if enable_auto_backup:
                self.backup_manager.auto_backup()
        else:
            self.backup_manager = None

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
                f"sqlite:///{self.db_path}", echo=False, future=True, pool_pre_ping=True
            )

            self.SessionLocal: sessionmaker = sessionmaker(
                bind=self.engine,
                autoflush=True,
                expire_on_commit=False,
                future=True,
            )

            self.alembic_cfg: Config = self._setup_alembic()
            self.init_database()

            if self.logger:
                self.logger.log_operation("database_init_complete", {"success": True})

        except Exception as e:
            if self.logger:
                self.logger.log_error(e, {"operation": "database_init"})
            raise DatabaseError(f"Database initialization failed: {e}")

    # ---- Session Management ----
    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around operations."""
        session = self.SessionLocal()
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

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
            session.close()
            if self.logger:
                self.logger.log_debug("session_close", {"session_id": session_id})

    def get_session(self) -> Session:
        """Create and return a new SQLAlchemy session."""
        return self.SessionLocal()

    # ---- Alembic setup ----
    def _setup_alembic(self) -> Config:
        """Setup Alembic configuration with error handling."""
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
                if self.logger:
                    self.logger.log_operation(
                        "init_alembic_start", {"alembic_dir": str(self.alembic_dir)}
                    )

                command.init(self.alembic_cfg, str(self.alembic_dir))
                self._update_alembic_env()

                if self.logger:
                    self.logger.log_operation(
                        "init_alembic_complete", {"success": True}
                    )

            else:
                if self.logger:
                    self.logger.log_debug(
                        f"Alembic already initialized in {self.alembic_dir}"
                    )
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, {"operation": "init_alembic"})
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
                if "target_metadata = None" not in content:
                    if self.logger:
                        self.logger.log_debug(
                            "No 'target_metadata = None' "
                            "line found in env.py, skipping update"
                        )
                else:
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
            if self.logger:
                self.logger.log_error(e, {"operation": "init_database"})
            raise DatabaseError(f"Could not initialize database: {e}")

    # ----  Helper methods ----
    @staticmethod
    def _resolve_object(
        session: Session, item: Union[T, int], model_class: Type[T]
    ) -> T:
        """Resolve an item to an ORM object."""
        if isinstance(item, model_class):
            if item.id is None:
                raise ValueError(f"{model_class.__name__} instance must be persisted")
            return item
        elif isinstance(item, int):
            obj = session.get(model_class, item)
            if obj is None:
                raise ValueError(f"No {model_class.__name__} found with id: {item}")
            return obj
        else:
            raise TypeError(
                f"Expected {model_class.__name__} instance or int, got {type(item)}"
            )

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

    # ---- Entry ----
    @validate_metadata(["date", "file_path"])
    @handle_db_errors
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
        """
        # --- Required fields ---
        parsed_date = md.parse_date(metadata["date"])
        if not parsed_date:
            raise ValueError(f"Invalid date format: {metadata['date']}")

        file_path = md.normalize_str(metadata.get("file_path"))
        if not file_path:
            raise ValueError(f"Invalid file_path: {metadata['file_path']}")

        # --- file_path uniqueness check ---
        existing = session.query(Entry).filter_by(file_path=file_path).first()
        if existing:
            raise ValidationError(f"Entry already exists for file_path: {file_path}")

        # --- If hash doesn't exist, create it ---
        file_hash = md.normalize_str(metadata.get("file_hash"))
        if not file_hash:
            file_hash = fs.get_file_hash(file_path)

        # --- Create Entry ---
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
        Update relationships for a Entry object in the database.

        Supports both incremental updates (defualt) and full overwrite.
        This function handles relationships only. No I/O or Markdown parsing.
        Prevents duplicates and ensures lookup tables are updated.

        Args:
            session (Session): Active SQLAlchemy session.
            person (Person): Entry ORM object to update relationships for.
            metadata (Dict[str, Any]): Normalized metadata containing:
                Expected keys (optional):
                    - dates (List[MentionedDate or id])
                    - locations (List[Location or id])
                    - people (List[Person or id])
                    - references (List[Reference or id])
                    - events (List[Event or id])
                    - poems (List[Poem or id])
                Removal keys (optional):
                    - remove_dates (List[MentionedDate or id])
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

        Returns:
            None
        """

        # --- Many to many ---
        many_to_many_configs = [
            ("dates", "dates", MentionedDate),
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
        norm_tags = {md.normalize_str(t) for t in tags if md.normalize_str(t)}

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

    @handle_db_errors
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
                      dates, locations, people, references, events, poems, tags

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
        field_updates = {
            "date": lambda x: md.parse_date(x),
            "file_path": lambda x: md.normalize_str(x),
            "file_hash": lambda x: md.normalize_str(x),
            "word_count": lambda x: md.safe_int(x),
            "reading_time": lambda x: md.safe_float(x),
            "epigraph": lambda x: md.normalize_str(x),
            "notes": lambda x: md.normalize_str(x),
        }

        for field, parser in field_updates.items():
            if field in metadata:
                value = parser(metadata[field])
                if value is not None or field in ["epigraph", "notes"]:
                    if field == "file_path" and value is not None:
                        file_hash = fs.get_file_hash(value)
                        setattr(entry, "file_hash", file_hash)
                    setattr(entry, field, value)

        # --- Update relationships ---
        self._update_entry_relationships(session, entry, metadata)
        return entry

    # ---- Location ----
    @validate_metadata(["name"])
    @handle_db_errors
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
                Optional keys:
                    - full_name (str)

        Returns:
            Location: The newly created Location ORM object.
        """
        # --- Required fields ---
        loc_name = md.normalize_str(metadata.get("name"))
        if not loc_name:
            raise ValueError(f"Invalid name: {metadata['name']}")

        # --- Create Location ---
        location = Location(
            name=loc_name,
            full_name=md.normalize_str(metadata.get("full_name")),
        )
        session.add(location)
        session.flush()
        return location

    @handle_db_errors
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
                      name, full_name

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
        field_updates = {
            "name": lambda x: md.normalize_str(x),
            "full_name": lambda x: md.normalize_str(x),
        }

        for field, parser in field_updates.items():
            if field in metadata:
                value = parser(metadata[field])
                if value is not None or field == "full_name":
                    setattr(location, field, value)

        return location

    # ---- Person ----
    @validate_metadata(["name"])
    @handle_db_errors
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
                Relationship keys (optional):
                    - aliases (List[str])
                    - events (List[Event|int])
                    - entries (List[Entry|int])

        Returns:
            Person: The newly created Location ORM object.
        """
        # --- Required fields ---
        p_name = md.normalize_str(metadata.get("name"))
        if not p_name:
            raise ValueError(f"Invalid name: {metadata['name']}")

        # --- Uniqueness check ---
        p_fname = md.normalize_str(metadata.get("full_name"))
        existing = session.query(Person).filter_by(name=p_name).first()
        if existing:
            if not p_fname:
                raise ValidationError(
                    f"Person already exists for name: {p_name} "
                    "and no full_name was given"
                )
            if existing.full_name == p_fname:
                raise ValidationError(
                    "Person already exists for name: "
                    f"{p_name} and full_name: {p_fname}"
                )

        # --- Create Person ---
        person = Person(
            name=p_name,
            full_name=p_fname,
            relation_type=md.normalize_str(metadata.get("relation_type")),
        )
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

    @handle_db_errors
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
            "name": lambda x: md.normalize_str(x),
            "full_name": lambda x: md.normalize_str(x),
            "relation_type": lambda x: md.normalize_str(x),
        }

        for field, parser in field_updates.items():
            if field in metadata:
                value = parser(metadata[field])
                if value is not None or field in ["full_name", "relation_type"]:
                    setattr(person, field, value)

        # --- Update relationships ---
        self._update_person_relationships(session, person, metadata)
        return person

    # ---- Reference ----
    # Reference is created as a one-to-many relationship of Entry
    @handle_db_errors
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
            "content": lambda x: md.normalize_str(x),
            "speaker": lambda x: md.normalize_str(x),
        }

        for field, parser in field_updates.items():
            if field in metadata:
                value = parser(metadata[field])
                if value is not None or field == "speaker":
                    setattr(reference, field, value)

        # --- Parents ---
        # -- Entry --
        entry: Optional[Entry] = None
        if (m_entry := metadata.get("entry")) is not None:
            entry = self._resolve_object(session, m_entry, Entry)
            if reference.entry_id != entry.id:
                reference.entry = entry
        #
        # -- ReferenceSource --
        ref_source: Optional[ReferenceSource] = None
        if (m_source := metadata.get("source")) is not None:
            ref_source = self._resolve_object(session, m_source, ReferenceSource)
            if reference.source_id != ref_source.id:
                reference.source = ref_source

        return reference

    @validate_metadata(["type", "title"])
    @handle_db_errors
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
                    - type (str)
                    - title (str)
                Optional keys:
                    - author (str)

        Returns:
            ReferenceSource: The newly created Location ORM object.
        """
        # --- Required fields ---
        norm_type = md.normalize_str(metadata.get("type"))
        if not norm_type:
            raise ValueError(f"Invalid type: {metadata['type']}")

        norm_title = md.normalize_str(metadata.get("title"))
        if not norm_title:
            raise ValueError(f"Invalid title: {metadata['title']}")

        # --- title uniqueness check ---
        existing = session.query(ReferenceSource).filter_by(title=norm_title).first()

        if existing:
            raise ValidationError(
                f"ReferenceSource already exists for title: {norm_title}"
            )

        # --- Create Source ---
        ref = ReferenceSource(
            type=norm_type,
            title=norm_title,
            author=md.normalize_str(metadata.get("author")),
        )
        session.add(ref)
        session.flush()
        return ref

    @handle_db_errors
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
            "type": lambda x: md.normalize_str(x),
            "title": lambda x: md.normalize_str(x),
            "author": lambda x: md.normalize_str(x),
        }

        for field, parser in field_updates.items():
            if field in metadata:
                value = parser(metadata[field])
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

    # ---- Event ----
    @validate_metadata(["name"])
    @handle_db_errors
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
        event_name = md.normalize_str(metadata.get("event"))
        if not event_name:
            raise ValueError(f"Invalid event name: {metadata['event']}")

        # --- Create Location ---
        event = Event(
            event=event_name,
            title=md.normalize_str(metadata.get("title")),
            description=md.normalize_str(metadata.get("description")),
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
        Update relationships for a Event object in the database.

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

        Returns:
            None
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
            "event": lambda x: md.normalize_str(x),
            "title": lambda x: md.normalize_str(x),
            "description": lambda x: md.normalize_str(x),
        }

        for field, parser in field_updates.items():
            if field in metadata:
                value = parser(metadata[field])
                if value is not None or field in ["title", "description"]:
                    setattr(event, field, value)

        # --- Update relationships ---
        self._update_event_relationships(session, event, metadata)
        return event

    # ---- Poems ----
    @validate_metadata(["title", "content"])
    @handle_db_errors
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
                    - poem (Person or id)

        Returns:
            Event: The newly created Event ORM object.
        """
        # --- Required fields ---
        title = md.normalize_str(metadata.get("title"))
        if not title:
            raise ValueError(f"Invalid poem title: {metadata['title']}")

        content = md.normalize_str(metadata.get("content"))
        if not content:
            raise ValueError(f"Invalid poem content: {metadata['content']}")

        # --- Uniqueness check ---
        existing = session.query(PoemVersion).filter_by(content=content).first()
        if existing:
            raise ValidationError("PoemVersion already exists with the same content")

        # --- Parents ---
        # -- Entry --
        entry: Optional[Entry] = None
        if (m_entry := metadata.get("entry")) is not None:
            entry = self._resolve_object(session, m_entry, Entry)

        # -- Poem --
        poem: Poem
        if (m_poem := metadata.get("poem")) is not None:
            poem = self._resolve_object(session, m_poem, Poem)
        else:
            poem = Poem(title=title)
            session.add(poem)
            session.flush()

        # --- If hash doesn't exist, create it ---
        version_hash = md.normalize_str(metadata.get("version_hash"))
        if not version_hash:
            version_hash = md.get_text_hash(content)

        # --- Use metadata, or entry date or now
        rev_date: date
        m_date = md.parse_date(metadata.get("revision_date"))
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
            notes=md.normalize_str(metadata.get("notes")),
            poem=poem,
            entry=entry,
        )
        session.add(poem_version)
        session.flush()
        return poem_version

    @handle_db_errors
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
            Event: The updated Event ORM object (still attached to session).
        """
        # --- Ensure existance ---
        db_poem = session.get(Poem, poem.id)
        if db_poem is None:
            raise ValueError(f"Poem with id={poem.id} does not exist")

        # --- Attach to session ---
        poem = session.merge(db_poem)

        # --- Update title ---
        if "title" in metadata:
            title = md.normalize_str(metadata["title"])
            if title is not None:
                setattr(poem, "title", title)

        # --- Update Versions ---
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
    def update_poem_version(
        self, session: Session, poem: PoemVersion, metadata: Dict[str, Any]
    ) -> PoemVersion:
        """
        Update an existing Poem (Version) in the database.

        Args:
            session (Session): Active SQLAlchemy session
            poem (PoemVersion): Existing Poem ORM object to update.
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
        db_poem = session.get(PoemVersion, poem.id)
        if db_poem is None:
            raise ValueError(f"PoemVersion with id={poem.id} does not exist")

        # --- Attach to session ---
        poem = session.merge(db_poem)

        # --- Update scalar fields ---
        field_updates = {
            "content": lambda x: md.normalize_str(x),
            "notes": lambda x: md.normalize_str(x),
        }

        for field, parser in field_updates.items():
            if field in metadata:
                value = parser(metadata[field])
                if value is not None or field in ["revision_date", "notes"]:
                    if field == "content" and value is not None:
                        content_hash = md.get_text_hash(value)
                        setattr(poem, "version_hash", content_hash)
                    setattr(poem, field, value)

        # --- Parents ---
        # -- Entry --
        entry: Optional[Entry] = None
        if (m_entry := metadata.get("entry")) is not None:
            entry = self._resolve_object(session, m_entry, Entry)
            if poem.entry_id != entry.id:
                poem.entry = entry
                poem.revision_date = entry.date
        elif metadata.get("remove_entry"):
            poem.entry = None

        # -- Poem --
        poem_parent: Optional[Poem] = None
        if (m_poem := metadata.get("poem")) is not None:
            poem_parent = self._resolve_object(session, m_poem, Poem)
            if poem.poem_id != poem_parent.id:
                poem.poem = poem_parent

        return poem

    # ---- Manuscript ----
    # --- Entry ---
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
            elif status_value is not None:
                raise ValueError(
                    "Status must be string or ManuscriptStatus enum, "
                    f"got {type(status_value)}"
                )

        # - edited -
        if "edited" in manuscript_data:
            edited_value = manuscript_data["edited"]
            if isinstance(edited_value, bool):
                normalized_data["edited"] = edited_value
            elif isinstance(edited_value, str):
                # Handle string representations of boolean
                if edited_value.lower() in ("true", "1", "yes", "on"):
                    normalized_data["edited"] = True
                elif edited_value.lower() in ("false", "0", "no", "off"):
                    normalized_data["edited"] = False
                else:
                    raise ValueError(f"Cannot convert '{edited_value}' to boolean")
            elif edited_value is not None:
                # Try to convert other types to bool
                normalized_data["edited"] = bool(edited_value)

        # - notes -
        if "notes" in manuscript_data:
            normalized_data["notes"] = md.normalize_str(manuscript_data["notes"])

        # -- Relationship --
        manuscript = RelationshipManager.update_one_to_one(
            session=session,
            parent_obj=entry,
            relationship_name="manuscript",
            model_class=ManuscriptEntry,
            child_data=normalized_data if normalized_data else {},
            foreign_key_attr="entry_id",
        )

        # -- Theemes --
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
            theme_norm = md.normalize_str(theme_name)
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
        # -- Character is required
        if "character" not in manuscript_data or not manuscript_data["character"]:
            raise ValidationError("Required field 'character' missing or empty")

        norm_character = md.normalize_str(manuscript_data["character"])
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
            normalized_data["notes"] = md.normalize_str(manuscript_data["notes"])

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
            arc_name = md.normalize_str(manuscript_data["arc"])
            if arc_name:
                arc_obj = self._get_or_create_lookup_item(
                    session, Arc, {"arc": arc_name}
                )
                manuscript.arc = arc_obj
                session.flush()

        return manuscript

    # ---- Cleanup ----
    @handle_db_errors
    def bulk_cleanup_unused(
        self, session: Session, cleanup_config: Dict[str, tuple]
    ) -> Dict[str, int]:
        """
        Perform bulk cleanup operations more efficiently.

        Args:
            cleanup_config: Dict mapping table names to (model_class, relationship_attr) tuples
        """
        results = {}

        for table_name, (model_class, relationship_attr) in cleanup_config.items():
            # Use bulk delete for better performance
            subquery = (
                session.query(model_class.id)
                .filter(~getattr(model_class, relationship_attr).any())
                .subquery()
            )

            deleted_count = (
                session.query(model_class)
                .filter(model_class.id.in_(subquery.select()))
                .delete(synchronize_session=False)
            )

            results[table_name] = deleted_count
            logger.info(f"Cleaned up {deleted_count} unused {table_name}")

        session.flush()
        return results

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
            logger.error(f"Cleanup failed: {e}")
            raise DatabaseError(f"Cleanup operation failed: {e}")

    # ---- Migrations ----
    @handle_db_errors
    def create_migration(self, message: str) -> None:
        """
        Create a new Alembic migration file for the current database schema.

        Args:
            message (str): Description of the migration.
        Returns:
            None
        """
        try:
            command.revision(self.alembic_cfg, message=message, autogenerate=True)
            logger.info(f"Created migration: {message}")
        except Exception as e:
            logger.error(f"Failed to create migration '{message}': {e}")
            raise DatabaseError(f"Migration creation failed: {e}")

    @handle_db_errors
    def downgrade_database(self, revision: str) -> None:
        """
        Downgrade the database schema to a specified Alembic revision.

        Args:
            revision (str): The target revision to downgrade to.

        Returns:
            None
        """
        try:
            command.downgrade(self.alembic_cfg, revision)
            logger.info(f"Database downgraded to {revision}")
        except Exception as e:
            logger.error(f"Database downgrade to {revision} failed: {e}")
            raise DatabaseError(f"Could not downgrade database to {revision}: {e}")

    @handle_db_errors
    def upgrade_database(self, revision: str = "head") -> None:
        """
        Upgrade the database schema to the specified Alembic revision.

        Args:
            revision (str, optional):
                The target revision to upgrade to.
                Defaults to 'head' (latest revision).

        Returns:
            None
        """
        try:
            command.upgrade(self.alembic_cfg, revision)
            logger.info(f"Database upgraded to {revision}")
        except Exception as e:
            logger.error(f"Database upgrade failed: {e}")
            raise DatabaseError(f"Could not upgrade database to {revision}: {e}")

    def backup_database(self, backup_suffix: Optional[str] = None) -> str:
        """
        Create database backup.

        Args:
            backup_suffix (Optional[str]): Suffix to append to the backup file.

        Returns:
            str: Path to the backup database file.
        """
        try:
            if backup_suffix is None:
                backup_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")

            backup_path = f"{self.db_path}.backup_{backup_suffix}"
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Database backed up to: {backup_path}")
            return backup_path

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            raise DatabaseError(f"Could not create backup: {e}")

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
            logger.error(f"Failed to get migration history: {e}")
            return {"error": str(e)}

    # ---- Stats ----
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            with self.session_scope() as session:
                stats = {
                    "entries": session.query(Entry).count(),
                    "mentioned_dates": session.query(MentionedDate).count(),
                    "locations": session.query(Location).count(),
                    "people": session.query(Person).count(),
                    "aliases": session.query(Alias).count(),
                    "references": session.query(Reference).count(),
                    "references_sources": session.query(ReferenceSource).count(),
                    "events": session.query(Event).count(),
                    "poems": session.query(Poem).count(),
                    "poemVersion": session.query(PoemVersion).count(),
                    "tags": session.query(Tag).count(),
                    "manuscript_entries": session.query(ManuscriptEntry).count(),
                    "manuscript_events": session.query(ManuscriptEvent).count(),
                    "manuscript_people": session.query(ManuscriptPerson).count(),
                    "arcs": session.query(Arc).count(),
                    "themes": session.query(Theme).count(),
                    "migration_status": self.get_migration_history(),
                }

                # -- Recent activity --
                week_ago = datetime.now() - timedelta(days=7)
                stats["entries_updated_last_7_days"] = (
                    session.query(Entry).filter(Entry.updated_at >= week_ago).count()
                )

                return stats
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            raise DatabaseError(f"Could not retrieve database statistics: {e}")

    ## --- CRUD / Query ---
    # def get_entry_metadata(self, file_path: str) -> Dict[str, Any]:
    #     """Get metadata for a specific entry"""
    #     with self.get_session() as session:
    #         entry = session.query(Entry).filter_by(file_path=file_path).first()
    #         if not entry:
    #             return {}
    #
    #         return {
    #             "date": entry.date,
    #             "word_count": entry.word_count,
    #             "reading_time": entry.reading_time,
    #             "epigraph": entry.epigraph or "",
    #             "notes": entry.notes or "",
    #             "people": [person.display_name for person in entry.people],
    #             "tags": [tag.tag for tag in entry.tags],
    #             "location": [location.display_name for location in entry.locations],
    #             "events": [event.display_name for event in entry.events],
    #             "references": [ref.content_preview for ref in entry.references],
    #         }
    #
    # def get_all_values(self, field: str) -> List[str]:
    #     """Get all unique values for a field (for autocomplete)"""
    #     model_map = {
    #         "people": Person,
    #         "tags": Tag,
    #         "locations": Location,
    #         "events": Event,
    #         "reference": Reference,
    #     }
    #
    #     if field in model_map:
    #         with self.get_session() as session:
    #             items = (
    #                 session.query(model_map[field])
    #                 .order_by(model_map[field].name)
    #                 .all()
    #             )
    #             return [item.name for item in items]
    #
    #     return []
    #
    ## Usage example demonstrating both relationship types
    # def example_usage(self):
    #     """Example showing how to handle mixed relationship types."""
    #
    #     # Example metadata with both many-to-many and one-to-many relationships
    #     entry_metadata = {
    #         'date': '2024-01-15',
    #         'file_path': '/path/to/entry.md',
    #
    #         # Many-to-many relationships (these objects can be shared across entries)
    #         'people': [1, 2],  # Person IDs that can appear in multiple entries
    #         'locations': ['New York', 'Paris'],  # Locations that can be referenced by multiple entries
    #         'events': [{'name': 'Birthday Party', 'description': 'Annual celebration'}],
    #         'tags': ['personal', 'reflection'],
    #
    #         # One-to-many relationships (these objects belong exclusively to this entry)
    #         'references': [
    #             {
    #                 'name': 'The Great Gatsby',
    #                 'author': 'F. Scott Fitzgerald',
    #                 'reference_type': 'book'
    #             }
    #         ],
    #         'poems': [
    #             {
    #                 'title': 'Morning Reflection',
    #                 'text': 'The sun rises...',
    #                 'revision_date': '2024-01-15'
    #             }
    #         ]
    #     }
    #
    #     try:
    #         with self.session_scope() as session:
    #             # Create entry - this will handle all relationships appropriately
    #             entry = self.create_entry(session, entry_metadata)
    #
    #             # The RelationshipManager automatically handles:
    #             # - Many-to-many: Updates junction tables for people, locations, events, tags
    #             # - One-to-many: Sets foreign keys on references and poems to point to this entry
    #
    #             logger.info(f"Created entry {entry.id} with mixed relationship types")
    #
    #     except (DatabaseError, ValidationError) as e:
    #         logger.error(f"Failed to create entry: {e}")
    #         raise
