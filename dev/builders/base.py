#!/usr/bin/env python3
"""
base.py
-------------------
Base classes for builders in the Palimpsest project.

Provides:
- BuilderStats: Abstract base class for tracking build statistics
- BaseBuilder: Abstract base class for builder implementations

These classes establish common interfaces and shared functionality
for all builder types (PDF, text, etc.).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from dev.core.logging_manager import PalimpsestLogger, safe_logger


class BuilderStats(ABC):
    """
    Abstract base class for tracking builder statistics.

    Provides common functionality for measuring execution time and
    formatting summary output. Subclasses should add specific metrics.

    Attributes:
        start_time: Timestamp when processing started
    """

    def __init__(self) -> None:
        """Initialize stats with current timestamp."""
        self.start_time: datetime = datetime.now()

    def duration(self) -> float:
        """
        Get elapsed time since initialization.

        Returns:
            Elapsed time in seconds as float
        """
        return (datetime.now() - self.start_time).total_seconds()

    @abstractmethod
    def summary(self) -> str:
        """
        Get formatted summary of build statistics.

        Returns:
            Human-readable summary string

        Note:
            Subclasses must implement this to provide builder-specific summaries
        """
        pass


class BaseBuilder(ABC):
    """
    Abstract base class for builder implementations.

    Provides common interface and optional logger integration for all
    builders. Subclasses implement the build() method with specific logic.

    Attributes:
        logger: Optional logger for operation tracking
    """

    def __init__(self, logger: Optional[PalimpsestLogger] = None):
        """
        Initialize builder with optional logger.

        Args:
            logger: Optional logger for operation tracking
        """
        self.logger = logger

    @abstractmethod
    def build(self) -> BuilderStats:
        """
        Execute the build process.

        Returns:
            BuilderStats subclass instance with build results

        Raises:
            Appropriate exception on build failure (subclass-specific)

        Note:
            Subclasses must implement this with their specific build logic
        """
        pass

    def _log_operation(
        self, operation: str, details: Optional[dict] = None
    ) -> None:
        """
        Log an operation if logger is available.

        Helper method for consistent operation logging across builders.

        Args:
            operation: Operation identifier string
            details: Optional dictionary of operation details
        """
        safe_logger(self.logger).log_operation(operation, details or {})

    def _log_debug(self, message: str) -> None:
        """
        Log a debug message if logger is available.

        Args:
            message: Debug message string
        """
        safe_logger(self.logger).log_debug(message)

    def _log_info(self, message: str) -> None:
        """
        Log an info message if logger is available.

        Args:
            message: Info message string
        """
        safe_logger(self.logger).log_info(message)

    def _log_warning(self, message: str) -> None:
        """
        Log a warning message if logger is available.

        Args:
            message: Warning message string
        """
        safe_logger(self.logger).log_warning(message)

    def _log_error(self, error: Exception, context: Optional[dict] = None) -> None:
        """
        Log an error if logger is available.

        Args:
            error: Exception that occurred
            context: Optional dictionary with error context
        """
        safe_logger(self.logger).log_error(error, context or {})
