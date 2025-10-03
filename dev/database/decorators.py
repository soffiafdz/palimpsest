#!/usr/bin/env python3
"""
decorators.py
--------------------
Shared decorators for database operations.
"""
# import inspect
from functools import wraps
from typing import Callable, List
from datetime import datetime

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from dev.core.validators import DataValidator

from .exceptions import DatabaseError


def log_database_operation(operation_name: str):
    """
    Decorator to log database operations with timing and context.

    Args:
        operation_name: Name of the operation being logged

    Returns:
        Decorator function
    """

    def decorator(function: Callable) -> Callable:
        @wraps(function)
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
                result = function(self, *args, **kwargs)

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
    """
    Decorator to validate metadata dictionaries before processing.

    Args:
        required_fields: List of required field names

    Returns:
        Decorator function
    """

    def decorator(function: Callable) -> Callable:
        @wraps(function)
        def wrapper(self, session: Session, *args, **kwargs):
            # Find metadata as last positional arg or in kwargs
            metadata = args[-1] if args else kwargs.get("metadata", {})

            DataValidator.validate_required_fields(metadata, required_fields)

            return function(self, session, *args, **kwargs)

        return wrapper

    return decorator


def handle_db_errors(function: Callable) -> Callable:
    """
    Decorator to handle common database errors.

    Args:
        function: Function to wrap

    Returns:
        Wrapped function with error handling
    """

    @wraps(function)
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except IntegrityError as e:
            raise DatabaseError(f"Data integrity violation: {e}")
        except SQLAlchemyError as e:
            raise DatabaseError(f"Database operation failed: {e}")
        except Exception:
            raise

    return wrapper
