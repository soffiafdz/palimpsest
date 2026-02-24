#!/usr/bin/env python3
"""
decorators.py
--------------------
Context manager for database operations.

Provides DatabaseOperation context manager that handles logging, timing,
and error conversion for all database operations.

Usage:
    def create_person(self, metadata):
        DataValidator.validate_required_fields(metadata, ["name"])
        with DatabaseOperation(self.logger, "create_person"):
            person = Person(name=metadata["name"])
            self.session.add(person)
            self.session.commit()
            return person
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from contextlib import contextmanager
from datetime import datetime
from typing import Generator, Optional, TYPE_CHECKING

# --- Third party imports ---
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

# --- Local imports ---
from dev.core.exceptions import DatabaseError
from dev.core.logging_manager import safe_logger

if TYPE_CHECKING:
    from dev.core.logging_manager import PalimpsestLogger


@contextmanager
def DatabaseOperation(
    logger: Optional["PalimpsestLogger"],
    operation_name: str,
    log_start: bool = False,
) -> Generator[None, None, None]:
    """
    Context manager for database operations with logging, timing, and error handling.

    Args:
        logger: Optional PalimpsestLogger instance (None-safe via safe_logger)
        operation_name: Name of the operation for logging
        log_start: If True, logs operation start (default False to reduce noise)

    Yields:
        None

    Raises:
        DatabaseError: On SQLAlchemy integrity or general errors

    Example:
        def create_person(self, metadata):
            DataValidator.validate_required_fields(metadata, ["name"])
            with DatabaseOperation(self.logger, "create_person"):
                person = Person(name=metadata["name"])
                self.session.add(person)
                return person
    """
    start_time = datetime.now()
    log = safe_logger(logger)

    if log_start:
        log.log_debug(f"Starting {operation_name}")

    try:
        yield
        duration = (datetime.now() - start_time).total_seconds()
        log.log_operation(
            f"{operation_name}_completed",
            {"duration_seconds": round(duration, 3), "success": True},
        )
    except IntegrityError as e:
        duration = (datetime.now() - start_time).total_seconds()
        log.log_error(e, {"operation": operation_name, "duration_seconds": round(duration, 3)})
        raise DatabaseError(f"Data integrity violation: {e}")
    except SQLAlchemyError as e:
        duration = (datetime.now() - start_time).total_seconds()
        log.log_error(e, {"operation": operation_name, "duration_seconds": round(duration, 3)})
        raise DatabaseError(f"Database operation failed: {e}")
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        log.log_error(e, {"operation": operation_name, "duration_seconds": round(duration, 3)})
        raise
