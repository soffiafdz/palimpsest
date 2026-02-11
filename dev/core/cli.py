#!/usr/bin/env python3
"""
cli.py
------
Shared CLI utilities and statistics for Palimpsest commands.

Consolidates CLI helper functions and statistics tracking classes used across
all CLI scripts to reduce duplication and ensure consistency.

Functions:
    setup_logger: Initialize PalimpsestLogger for CLI operations

Classes:
    OperationStats: Base class for all statistics
    ConversionStats: For conversion operations (txt2md, yaml2sql)
    ExportStats: For export operations (sql2yaml)
    BuildStats: For build operations (md2pdf, src2txt)

Usage:
    from dev.core.cli import setup_logger, ConversionStats

    logger = setup_logger(log_dir, "my_component")
    stats = ConversionStats()
    stats.files_processed += 1
    print(stats.summary())
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional

# --- Local imports ---
from dev.core.logging_manager import PalimpsestLogger


# ═══════════════════════════════════════════════════════════════════════════
# LOGGER SETUP
# ═══════════════════════════════════════════════════════════════════════════

def setup_logger(log_dir: Path, component_name: str) -> PalimpsestLogger:
    """
    Setup logging for CLI operations.

    Creates the operations log directory if it doesn't exist and initializes
    a PalimpsestLogger instance for the specified component.

    Args:
        log_dir: Base log directory (typically from paths.LOG_DIR)
        component_name: Component identifier for logging (e.g., 'txt2md', 'yaml2sql')

    Returns:
        Configured PalimpsestLogger instance

    Examples:
        >>> from pathlib import Path
        >>> from dev.core.paths import LOG_DIR
        >>> logger = setup_logger(LOG_DIR, "txt2md")
        >>> logger.log_info("Starting conversion...")
    """
    operations_log_dir = log_dir / "operations"
    operations_log_dir.mkdir(parents=True, exist_ok=True)
    return PalimpsestLogger(operations_log_dir, component_name=component_name)


# ═══════════════════════════════════════════════════════════════════════════
# STATISTICS CLASSES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class OperationStats:
    """
    Base class for CLI operation statistics.

    Tracks basic metrics common to all operations: files processed, errors,
    and elapsed time.

    Attributes:
        files_processed: Number of files successfully processed
        errors: Number of errors encountered
        start_time: Operation start timestamp
    """
    files_processed: int = 0
    errors: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    _duration_cached: Optional[float] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        """Validate statistics on initialization."""
        if self.files_processed < 0:
            raise ValueError(f"files_processed must be non-negative, got {self.files_processed}")
        if self.errors < 0:
            raise ValueError(f"errors must be non-negative, got {self.errors}")

    def duration(self) -> float:
        """
        Get elapsed time in seconds (cached after first call).

        Returns:
            Seconds elapsed since start_time
        """
        if self._duration_cached is None:
            self._duration_cached = (datetime.now() - self.start_time).total_seconds()
        return self._duration_cached

    def summary(self) -> str:
        """
        Get formatted summary string.

        Returns:
            Human-readable summary of operation statistics
        """
        return (
            f"{self.files_processed} files processed, "
            f"{self.errors} errors, "
            f"{self.duration():.2f}s"
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON output.

        Returns:
            Dictionary with all metrics and computed duration
        """
        return {
            "files_processed": self.files_processed,
            "errors": self.errors,
            "duration": self.duration(),
        }


@dataclass
class ConversionStats(OperationStats):
    """
    Statistics for conversion operations (txt2md, yaml2sql).

    Extends OperationStats with entry-specific metrics for tracking
    creation, updates, and skips during conversion.

    Attributes:
        entries_created: Number of new entries created
        entries_updated: Number of existing entries updated
        entries_skipped: Number of entries skipped (unchanged)
        skeletons_created: Number of YAML skeleton files created
        skeletons_skipped: Number of YAML skeletons skipped (already exist)
    """
    entries_created: int = 0
    entries_updated: int = 0
    entries_skipped: int = 0
    skeletons_created: int = 0
    skeletons_skipped: int = 0

    def __post_init__(self) -> None:
        """Validate statistics on initialization."""
        super().__post_init__()
        if self.entries_created < 0:
            raise ValueError(f"entries_created must be non-negative, got {self.entries_created}")
        if self.entries_updated < 0:
            raise ValueError(f"entries_updated must be non-negative, got {self.entries_updated}")
        if self.entries_skipped < 0:
            raise ValueError(f"entries_skipped must be non-negative, got {self.entries_skipped}")
        if self.skeletons_created < 0:
            raise ValueError(f"skeletons_created must be non-negative, got {self.skeletons_created}")
        if self.skeletons_skipped < 0:
            raise ValueError(f"skeletons_skipped must be non-negative, got {self.skeletons_skipped}")

    def summary(self) -> str:
        """Get formatted summary with entry metrics."""
        parts = [
            f"{self.files_processed} files processed",
            f"{self.entries_created} created",
            f"{self.entries_updated} updated",
            f"{self.entries_skipped} skipped",
        ]
        if self.skeletons_created or self.skeletons_skipped:
            parts.append(f"{self.skeletons_created} skeletons created")
            parts.append(f"{self.skeletons_skipped} skeletons skipped")
        parts.append(f"{self.errors} errors")
        parts.append(f"{self.duration():.2f}s")
        return ", ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with entry metrics."""
        d = super().to_dict()
        d.update({
            "entries_created": self.entries_created,
            "entries_updated": self.entries_updated,
            "entries_skipped": self.entries_skipped,
            "skeletons_created": self.skeletons_created,
            "skeletons_skipped": self.skeletons_skipped,
        })
        return d


@dataclass
class ExportStats(OperationStats):
    """
    Statistics for export operations (sql2yaml).

    Tracks export-specific metrics including entries exported and files
    created/updated during the export process.

    Attributes:
        entries_exported: Number of entries exported
        files_created: Number of new files created
        files_updated: Number of existing files updated
    """
    entries_exported: int = 0
    files_created: int = 0
    files_updated: int = 0

    def __post_init__(self) -> None:
        """Validate statistics on initialization."""
        super().__post_init__()
        if self.entries_exported < 0:
            raise ValueError(f"entries_exported must be non-negative, got {self.entries_exported}")
        if self.files_created < 0:
            raise ValueError(f"files_created must be non-negative, got {self.files_created}")
        if self.files_updated < 0:
            raise ValueError(f"files_updated must be non-negative, got {self.files_updated}")

    def summary(self) -> str:
        """Get formatted summary with export metrics."""
        return (
            f"{self.entries_exported} entries exported, "
            f"{self.files_created} files created, "
            f"{self.files_updated} files updated, "
            f"{self.errors} errors, "
            f"{self.duration():.2f}s"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with export metrics."""
        d = super().to_dict()
        d.update({
            "entries_exported": self.entries_exported,
            "files_created": self.files_created,
            "files_updated": self.files_updated,
        })
        return d


@dataclass
class BuildStats(OperationStats):
    """
    Statistics for build operations (md2pdf, src2txt).

    Tracks build-specific metrics including artifact generation during
    the build process.

    Attributes:
        artifacts_created: Number of artifacts (PDFs, text files) created
        pdfs_created: Number of PDF files created (md2pdf specific)
    """
    artifacts_created: int = 0
    pdfs_created: int = 0

    def __post_init__(self) -> None:
        """Validate statistics on initialization."""
        super().__post_init__()
        if self.artifacts_created < 0:
            raise ValueError(f"artifacts_created must be non-negative, got {self.artifacts_created}")
        if self.pdfs_created < 0:
            raise ValueError(f"pdfs_created must be non-negative, got {self.pdfs_created}")

    def summary(self) -> str:
        """Get formatted summary with build metrics."""
        if self.pdfs_created > 0:
            return (
                f"{self.files_processed} files processed, "
                f"{self.pdfs_created} PDFs created, "
                f"{self.errors} errors, "
                f"{self.duration():.2f}s"
            )
        return (
            f"{self.files_processed} files processed, "
            f"{self.artifacts_created} artifacts created, "
            f"{self.errors} errors, "
            f"{self.duration():.2f}s"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with build metrics."""
        d = super().to_dict()
        d.update({
            "artifacts_created": self.artifacts_created,
            "pdfs_created": self.pdfs_created,
        })
        return d
