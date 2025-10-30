#!/usr/bin/env python3
"""
logging_manager.py
--------------------
Centralized logging system for all palimpsest operations.

Provides structured logging with rotation for database operations,
conversion pipelines, and any process requiring comprehensive logging.
"""
import json
import logging
import traceback
import sys

from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import click


class PalimpsestLogger:
    """
    Centralized logging system for project operations.

    Creates structured logging with rotation for all activities.
    Logs are organized by severity and written to appropriate files.

    Attributes:
        log_dir: Directory for log files
        component_name: Name of the component using this logger
        main_logger: Main logger for all operations
        error_logger: Dedicated logger for errors only
    """

    def __init__(self, log_dir: Path, component_name: str = "palimpsest") -> None:
        """
        Initialize database logging system.

        Args:
            log_dir: Directory for log files
            component_name: Name for the component logger
                (e.g. 'database', 'txt2md', etc.)
        """
        self.log_dir = Path(log_dir)
        self.component_name = component_name
        self._setup_loggers()

    def _setup_loggers(self) -> None:
        """Initialize logging system with database-specific handlers."""
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Main database logger (handles all database activity)
        self.main_logger = logging.getLogger(f"{self.component_name}.operations")
        self.main_logger.setLevel(logging.DEBUG)

        # Error logger (errors only, for quick scanning)
        self.error_logger = logging.getLogger(f"{self.component_name}.errors")
        self.error_logger.setLevel(logging.ERROR)

        # Clear existing handlers to avoid duplicates
        for logger in [self.main_logger, self.error_logger]:
            logger.handlers.clear()

        # Create handlers - only database.log and errors.log
        self._create_file_handler(
            self.main_logger,
            self.log_dir / f"{self.component_name}.log",
            logging.DEBUG,
        )
        self._create_file_handler(
            self.error_logger,
            self.log_dir / "errors.log",
            logging.ERROR,
        )

        # Console handler for development
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
        )
        console_handler.setFormatter(console_formatter)

        self.main_logger.addHandler(console_handler)

    def _create_file_handler(
        self, logger: logging.Logger, file_path: Path, level: int
    ) -> None:
        """
        Create a rotating file handler for a logger.

        Args:
            logger: Logger instance to add handler to
            file_path: Path for log file
            level: Logging level for the handler
        """
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

    def log_operation(
        self, operation: str, details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a database operation - goes to main database.log.

        Args:
            operation: Name of the operation
            details: Optional operation details dictionary
        """
        details = details or {}
        self.main_logger.info(
            f"OPERATION - {operation}: {json.dumps(details, default=str)}"
        )

    def log_error(
        self, error: Exception, context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an error with context and traceback.

        Args:
            error: Exception that occurred
            context: Optional context information dictionary
        """
        context = context or {}
        error_type = type(error).__name__
        error_message = str(error)

        self.main_logger.error(f"ERROR - {error_type}: {error_message}")
        self.error_logger.error(f"ERROR - {error_type}: {error_message}")

        if context:
            context_str = ", ".join(f"{k}={v}" for k, v in context.items())
            self.main_logger.error(f"Context: {context_str}")
            self.error_logger.error(f"Context: {context_str}")

        # Log traceback
        self.main_logger.error(f"Traceback:\n{traceback.format_exc()}")
        self.error_logger.error(f"Traceback:\n{traceback.format_exc()}")

    def log_debug(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Log debug information.

        Args:
            message: Debug message
            details: Optional details dictionary
        """
        if details:
            self.main_logger.debug(
                f"DEBUG - {message}: {json.dumps(details, default=str)}"
            )
        else:
            self.main_logger.debug(f"DEBUG - {message}")

    def log_info(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Log general information.

        Args:
            message: Info message
            details: Optional details dictionary
        """
        if details:
            self.main_logger.info(
                f"INFO - {message}: {json.dumps(details, default=str)}"
            )
        else:
            self.main_logger.info(f"INFO - {message}")

    def log_warning(
        self, message: str, details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a warning.

        Args:
            message: Warning message
            details: Optional details dictionary
        """
        if details:
            self.main_logger.warning(
                f"WARNING - {message}: {json.dumps(details, default=str)}"
            )
        else:
            self.main_logger.warning(f"WARNING - {message}")

    def log_cli_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        show_traceback: bool = False,
    ) -> str:
        """
        Format error for CLI display and log full details to file.

        This method:
        1. Logs complete error details (JSON format) to log files
        2. Returns a clean, human-readable error message for CLI output

        Args:
            error: Exception to log
            context: Optional context information about where error occurred
            show_traceback: If True, include full traceback in CLI output

        Returns:
            Formatted error message suitable for CLI display

        Examples:
            >>> logger.log_cli_error(DatabaseError("Connection failed"))
            '❌ DatabaseError: Connection failed'

            >>> logger.log_cli_error(error, {"operation": "init"}, show_traceback=True)
            '❌ DatabaseError: Connection failed\\n\\nTraceback (most recent call last)...'
        """
        # Log full details to file (JSON format for machine parsing)
        self.log_error(error, context or {"source": "cli"})

        # Build clean CLI message
        error_type = type(error).__name__
        error_msg = str(error)

        if show_traceback:
            tb = traceback.format_exc()
            return f"❌ {error_type}: {error_msg}\n\n{tb}"
        else:
            return f"❌ {error_type}: {error_msg}"


def handle_cli_error(
    ctx: "click.Context",
    error: Exception,
    operation: str,
    additional_context: Optional[Dict[str, Any]] = None,
    exit_code: int = 1,
) -> None:
    """
    Standardized error handling for all CLI commands.

    This function:
    1. Retrieves logger from Click context
    2. Logs complete error details (JSON format) to log files
    3. Displays clean, human-readable error message in terminal
    4. Exits with specified error code

    Args:
        ctx: Click context object containing logger and verbose flag
        error: Exception that occurred
        operation: Name of the operation that failed (e.g., 'build_pdf', 'sync_db')
        additional_context: Optional extra context (year, file path, etc.)
        exit_code: Exit code for sys.exit() (default: 1)

    Note:
        This function never returns - it always calls sys.exit()
    """
    logger: Optional[PalimpsestLogger] = ctx.obj.get("logger")
    verbose: bool = ctx.obj.get("verbose", False)

    # Build context dictionary
    context = {"operation": operation}
    if additional_context:
        context.update(additional_context)

    # Format error message
    if logger:
        error_msg = logger.log_cli_error(error, context, show_traceback=verbose)
    else:
        # Fallback if logger not available
        error_type = type(error).__name__
        error_msg = (
            f"❌ {operation.replace('_', ' ').title()} failed: {error_type}: {error}"
        )
        if verbose:
            error_msg += f"\n\n{traceback.format_exc()}"

    # Display and exit
    import click  # Import here to avoid hard dependency at module level

    click.echo(error_msg, err=True)
    sys.exit(exit_code)
