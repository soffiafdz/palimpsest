#!/usr/bin/env python3
"""
models.py
---------
Data models for the curation module.

This module defines dataclasses used throughout the curation workflow
to track statistics, validation results, and operation outcomes.

Models:
    - ExtractionStats: Statistics from entity extraction
    - ValidationResult: Results from curation file validation
    - ConsolidationResult: Results from merging curation files
    - ImportStats: Statistics from database import
    - FailedImport: Record of a failed import attempt
    - SummaryData: Aggregated entity summary data

All models are immutable dataclasses designed for consistent result
reporting across the curation CLI.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set


# =============================================================================
# Extraction Models
# =============================================================================

@dataclass
class ExtractionStats:
    """
    Statistics from entity extraction.

    Tracks counts of files scanned and entities extracted during
    the extraction phase.

    Attributes:
        files_scanned_md: Number of MD files scanned
        files_scanned_yaml: Number of narrative_analysis YAML files scanned
        years_found: Set of years with data
        people_count: Total unique people names extracted
        locations_count: Total unique location names extracted
        people_by_year: Count of people per year
        locations_by_year: Count of locations per year
    """
    files_scanned_md: int = 0
    files_scanned_yaml: int = 0
    years_found: Set[str] = field(default_factory=set)
    people_count: int = 0
    locations_count: int = 0
    people_by_year: Dict[str, int] = field(default_factory=dict)
    locations_by_year: Dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        """
        Get human-readable summary.

        Returns:
            Formatted summary string
        """
        return (
            f"Scanned {self.files_scanned_md} MD files, "
            f"{self.files_scanned_yaml} YAML files. "
            f"Found {self.people_count} people, "
            f"{self.locations_count} locations across {len(self.years_found)} years."
        )


# =============================================================================
# Validation Models
# =============================================================================

@dataclass
class ValidationResult:
    """
    Results from curation file validation.

    Tracks errors and warnings found during validation, along with
    the validity status.

    Attributes:
        file_path: Path to the validated file
        errors: List of error messages (blocking issues)
        warnings: List of warning messages (non-blocking issues)
        is_valid: True if no errors were found
    """
    file_path: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    is_valid: bool = True

    def __post_init__(self) -> None:
        """Update is_valid based on errors."""
        self.is_valid = len(self.errors) == 0

    def add_error(self, message: str) -> None:
        """
        Add an error message and mark as invalid.

        Args:
            message: Error message to add
        """
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        """
        Add a warning message (doesn't affect validity).

        Args:
            message: Warning message to add
        """
        self.warnings.append(message)

    def summary(self) -> str:
        """
        Get human-readable summary.

        Returns:
            Formatted summary string
        """
        if self.is_valid:
            if self.warnings:
                return f"Valid (with {len(self.warnings)} warnings)"
            return "Valid"
        return f"Invalid: {len(self.errors)} errors, {len(self.warnings)} warnings"


@dataclass
class ConsistencyResult:
    """
    Results from cross-year consistency check.

    Tracks conflicts (same key with different canonicals) and
    suggestions (similar names that may need linking).

    Attributes:
        entity_type: 'people' or 'locations'
        conflicts: List of conflict descriptions (must resolve before import)
        suggestions: List of suggestions for potential merges
    """
    entity_type: str = ""
    conflicts: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        """Check if there are any conflicts."""
        return len(self.conflicts) > 0

    def summary(self) -> str:
        """
        Get human-readable summary.

        Returns:
            Formatted summary string
        """
        if not self.conflicts and not self.suggestions:
            return f"{self.entity_type}: No conflicts or suggestions"
        return (
            f"{self.entity_type}: {len(self.conflicts)} conflicts, "
            f"{len(self.suggestions)} suggestions"
        )


# =============================================================================
# Consolidation Models
# =============================================================================

@dataclass
class ConsolidationResult:
    """
    Results from merging curation files.

    Tracks the outcomes of consolidating multiple per-year curation
    files into a single merged file.

    Attributes:
        years_processed: List of years that were consolidated
        merged_count: Number of entities successfully merged
        skipped_count: Number of entries skipped
        self_count: Number of self (author) references
        conflicts: List of conflict descriptions
        output_path: Path to the output file
    """
    years_processed: List[str] = field(default_factory=list)
    merged_count: int = 0
    skipped_count: int = 0
    self_count: int = 0
    conflicts: List[str] = field(default_factory=list)
    output_path: str = ""

    @property
    def has_conflicts(self) -> bool:
        """Check if there are any conflicts."""
        return len(self.conflicts) > 0

    def summary(self) -> str:
        """
        Get human-readable summary.

        Returns:
            Formatted summary string
        """
        parts = [
            f"Years: {', '.join(self.years_processed)}",
            f"Merged: {self.merged_count}",
            f"Skipped: {self.skipped_count}",
            f"Self: {self.self_count}",
        ]
        if self.conflicts:
            parts.append(f"Conflicts: {len(self.conflicts)}")
        return " | ".join(parts)


# =============================================================================
# Import Models
# =============================================================================

@dataclass
class ImportStats:
    """
    Statistics for the database import process.

    Tracks file processing progress, entity creation counts, and
    failure thresholds.

    Attributes:
        total_files: Total number of files to process
        processed: Number of files processed so far
        succeeded: Number of files successfully imported
        failed: Number of files that failed to import
        skipped: Number of files skipped (already exist or not in retry list)
        consecutive_failures: Count of failures in a row (for threshold)

    Entity counts:
        entries_created: Number of Entry records created
        scenes_created: Number of Scene records created
        events_created: Number of Event records created
        threads_created: Number of Thread records created
        people_created: Number of Person records created
        locations_created: Number of Location records created
        cities_created: Number of City records created
        arcs_created: Number of Arc records created
        tags_created: Number of Tag records created
        themes_created: Number of Theme records created
        motifs_created: Number of Motif records created
        references_created: Number of Reference records created
        poems_created: Number of Poem records created
    """
    # Processing counts
    total_files: int = 0
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    consecutive_failures: int = 0

    # Entity counts
    entries_created: int = 0
    scenes_created: int = 0
    events_created: int = 0
    threads_created: int = 0
    people_created: int = 0
    locations_created: int = 0
    cities_created: int = 0
    arcs_created: int = 0
    tags_created: int = 0
    themes_created: int = 0
    motifs_created: int = 0
    references_created: int = 0
    poems_created: int = 0

    # Thresholds (class-level constants)
    MAX_CONSECUTIVE_FAILURES: int = field(default=5, repr=False)
    MAX_FAILURE_RATE: float = field(default=0.05, repr=False)

    @property
    def failure_rate(self) -> float:
        """
        Calculate current failure rate.

        Returns:
            Failure rate as a decimal (0.0 to 1.0)
        """
        if self.processed == 0:
            return 0.0
        return self.failed / self.processed

    def should_stop(self) -> bool:
        """
        Check if import should stop due to failure thresholds.

        Returns:
            True if thresholds exceeded, False otherwise
        """
        if self.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
            return True
        if self.processed >= 20 and self.failure_rate >= self.MAX_FAILURE_RATE:
            return True
        return False

    def summary(self) -> str:
        """
        Get human-readable summary.

        Returns:
            Formatted summary string
        """
        return (
            f"Processed: {self.processed}/{self.total_files} | "
            f"Succeeded: {self.succeeded} | "
            f"Failed: {self.failed} | "
            f"Skipped: {self.skipped}"
        )

    def entity_summary(self) -> str:
        """
        Get summary of entity creation counts.

        Returns:
            Formatted summary string with entity counts
        """
        return (
            f"Entries: {self.entries_created} | "
            f"Scenes: {self.scenes_created} | "
            f"Events: {self.events_created} | "
            f"Threads: {self.threads_created} | "
            f"People: {self.people_created} | "
            f"Locations: {self.locations_created}"
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.

        Returns:
            Dictionary with all statistics
        """
        return {
            "processing": {
                "total_files": self.total_files,
                "processed": self.processed,
                "succeeded": self.succeeded,
                "failed": self.failed,
                "skipped": self.skipped,
                "failure_rate": self.failure_rate,
            },
            "entities": {
                "entries": self.entries_created,
                "scenes": self.scenes_created,
                "events": self.events_created,
                "threads": self.threads_created,
                "people": self.people_created,
                "locations": self.locations_created,
                "cities": self.cities_created,
                "arcs": self.arcs_created,
                "tags": self.tags_created,
                "themes": self.themes_created,
                "motifs": self.motifs_created,
                "references": self.references_created,
                "poems": self.poems_created,
            },
        }


@dataclass
class FailedImport:
    """
    Record of a failed import attempt.

    Stores information about a file that failed to import for
    later retry or debugging.

    Attributes:
        file_path: Path to the failed file
        error_type: Type of exception that occurred
        error_message: Error message text
        timestamp: When the failure occurred
    """
    file_path: str
    error_type: str
    error_message: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, str]:
        """
        Convert to dictionary for JSON serialization.

        Returns:
            Dictionary with failure details
        """
        return {
            "file_path": self.file_path,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "timestamp": self.timestamp,
        }


# =============================================================================
# Summary Models
# =============================================================================

@dataclass
class SummaryData:
    """
    Aggregated entity summary data.

    Holds aggregated counts for entities across all years.

    Attributes:
        entity_type: 'people' or 'locations'
        total_unique: Total unique entity names
        by_name: Mapping of name -> {year: count}
        by_city: For locations only: city -> name -> {year: count}
    """
    entity_type: str = ""
    total_unique: int = 0
    by_name: Dict[str, Dict[str, int]] = field(default_factory=dict)
    by_city: Optional[Dict[str, Dict[str, Dict[str, int]]]] = None

    def summary(self) -> str:
        """
        Get human-readable summary.

        Returns:
            Formatted summary string
        """
        if self.by_city:
            city_count = len(self.by_city)
            return f"{self.entity_type}: {self.total_unique} unique across {city_count} cities"
        return f"{self.entity_type}: {self.total_unique} unique names"
