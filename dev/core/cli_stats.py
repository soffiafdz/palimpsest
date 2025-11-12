#!/usr/bin/env python3
"""
cli_stats.py
-------------------
Statistics tracking for CLI operations.

Provides base and specialized stats classes for tracking operation metrics
across different CLI commands. All stats classes include timing and basic
metrics, with specialized subclasses for different operation types.

Classes:
    OperationStats: Base class for all statistics
    ConversionStats: For conversion operations (txt2md, yaml2sql)
    ExportStats: For export operations (sql2yaml)
    BuildStats: For build operations (md2pdf, src2txt)

Usage:
    from dev.core.cli_stats import ConversionStats

    stats = ConversionStats()
    stats.files_processed += 1
    stats.entries_created += 1
    print(stats.summary())
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any


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

    def duration(self) -> float:
        """
        Get elapsed time in seconds.

        Returns:
            Seconds elapsed since start_time
        """
        return (datetime.now() - self.start_time).total_seconds()

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
    """
    entries_created: int = 0
    entries_updated: int = 0
    entries_skipped: int = 0

    def summary(self) -> str:
        """Get formatted summary with entry metrics."""
        return (
            f"{self.files_processed} files processed, "
            f"{self.entries_created} created, "
            f"{self.entries_updated} updated, "
            f"{self.entries_skipped} skipped, "
            f"{self.errors} errors, "
            f"{self.duration():.2f}s"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with entry metrics."""
        d = super().to_dict()
        d.update({
            "entries_created": self.entries_created,
            "entries_updated": self.entries_updated,
            "entries_skipped": self.entries_skipped,
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
