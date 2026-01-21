#!/usr/bin/env python3
"""
yaml2sql.py
-----------
Parse YAML frontmatter from Markdown files and populate database.

This pipeline converts human-edited Markdown entries with rich YAML metadata
into structured database records. It handles the complete conversion from
MdEntry → Database ORM models with comprehensive relationship management.

Features:
    - Parse YAML frontmatter with progressive complexity
    - Intelligent name/location parsing (hyphens, quotes, hierarchy)
    - Create or update database entries with relationships
    - Handle manuscript metadata
    - Batch processing with error recovery
    - Comprehensive logging and statistics
    - Hash-based change detection
    - Incremental and full synchronization modes
    - Tombstone tracking for reliable deletion propagation
    - Sync state tracking with conflict detection
    - Soft delete support for removed entries
    - Multi-machine synchronization support

Supported Metadata Fields:
    Core Fields:
        - date (required): Entry date in YYYY-MM-DD format
        - word_count: Word count (computed if missing)
        - reading_time: Estimated reading time in minutes
        - epigraph: Opening quote
        - epigraph_attribution: Attribution for epigraph
        - notes: Editorial notes

    Geographic Fields:
        - city: Single city or list of cities
        - locations: Flat list or nested dict by city

    Relationship Fields:
        - people: Names with hyphen/alias/full_name support
        - events: Event identifiers
        - tags: Keyword tags
        - dates: Mentioned dates with optional context
        - related_entries: Date strings of related entries

    Content Fields:
        - references: External citations with sources
        - poems: Poem versions with revision tracking

    Manuscript Fields:
        - manuscript: Status, themes, and editorial notes

Processing Modes:
    Single File Update:
        - Process individual Markdown file
        - Create or update based on file hash
        - Skip unchanged files (unless forced)

    Batch Processing:
        - Process directory of Markdown files
        - Parallel-safe with transaction isolation
        - Error recovery for individual failures

    Full Synchronization:
        - Update all entries in directory
        - Optional deletion of missing entries
        - Comprehensive validation

Programmatic API:
    from dev.pipeline.yaml2sql import process_entry_file, process_directory
    from dev.database.manager import PalimpsestDB

    # Process single file
    stats = process_entry_file(file_path, db, force_update=False, logger=logger)

    # Process directory
    stats = process_directory(input_dir, db, force_update=False, logger=logger)

Error Handling:
    - Validation errors logged with context
    - Parsing failures don't stop batch processing
    - Transaction rollback on database errors
    - Comprehensive error statistics

Notes:
    - All datetime fields stored as UTC
    - File paths must be absolute or relative to working directory
    - Hash-based change detection prevents redundant updates
    - Supports incremental relationship updates
    - Manuscript metadata optional but validated if present
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from dev.dataclasses.md_entry import MdEntry
from dev.database.manager import PalimpsestDB
from dev.database.models import Entry
from dev.database.sync_state_manager import SyncStateManager
from dev.core.exceptions import Yaml2SqlError
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.core.cli import ConversionStats
from dev.utils import fs
import socket


def process_entry_file(
    file_path: Path,
    db: PalimpsestDB,
    force_update: bool = False,
    logger: Optional[PalimpsestLogger] = None,
    raise_on_error: bool = True,
) -> str:
    """
    Process a single Markdown file and update database with parsed YAML metadata.

    Implementation Logic:
    ---------------------
    Core function for yaml2sql pipeline. Reads a Markdown file with YAML
    frontmatter, parses complex metadata, and creates/updates database records
    with full relationship management.

    Processing Flow:
    1. Parse Markdown file to MdEntry dataclass
    2. Validate required fields and data types
    3. Convert to database metadata format
    4. Check for existing entry by date
    5. Compare file hash for change detection
    6. Create new entry OR update existing entry
    7. Return status for statistics tracking

    Change Detection Strategy:
    - Computes MD5 hash of file content
    - Compares with Entry.file_hash in database
    - If hash matches and not force_update: skip processing
    - This enables incremental updates (only changed files)
    - Prevents redundant database writes

    YAML Parsing Complexity:
    - Handles nested structures (locations by city)
    - Parses name variations (hyphens, aliases, full_name)
    - Validates date formats and field types
    - Extracts references with sources
    - Processes poem versions with revisions
    - Manages manuscript editorial metadata

    Database Operations:
    - Uses session_scope() for transaction management
    - Create: db.entries.create() handles ORM object creation
    - Update: db.entries.update() manages relationship changes
    - Automatic rollback on exception
    - File hash stored in Entry.file_hash field

    Relationship Management:
    - People: Many-to-many via entry_people table
    - Locations: Hierarchical (city → location)
    - Events: Many-to-many via entry_events table
    - Tags: Many-to-many via entry_tags table
    - References: One-to-many from Entry
    - Poems: One-to-many from Entry with versions
    - Manuscript: One-to-one via ManuscriptEntry

    Error Handling Modes:
    - raise_on_error=True: Raises Yaml2SqlError (stops batch)
    - raise_on_error=False: Returns "error" status (continues batch)
    - Allows flexible error handling in batch vs single-file contexts

    Status Return Values:
    - "created": New entry added to database
    - "updated": Existing entry modified
    - "skipped": File unchanged (hash match)
    - "error": Processing failed (raise_on_error=False only)

    Validation:
    - Required fields: date
    - Optional fields validated if present
    - Type checking for dates, numbers, lists
    - Validation errors collected and logged

    Args:
        file_path: Path to .md file with YAML frontmatter
        db: PalimpsestDB manager for database operations
        force_update: If True, update even if file hash unchanged
        logger: Optional logger for operation tracking
        raise_on_error: If True, raise on errors; if False, return "error"

    Returns:
        Status string: "created", "updated", "skipped", or "error"

    Raises:
        Yaml2SqlError: If processing fails and raise_on_error=True
    """
    try:
        safe_logger(logger).log_debug(f"Processing {file_path.name}")

        # Parse markdown entry
        try:
            md_entry: MdEntry = MdEntry.from_file(file_path, verbose=False)
        except Exception as e:
            safe_logger(logger).log_error(e, {"operation": "parse_file", "file": str(file_path)})
            raise Yaml2SqlError(f"Failed to parse {file_path}: {e}") from e

        # Validate entry
        validation_errors: List[str] = md_entry.validate()
        if validation_errors:
            error_msg: str = f"Validation failed: {', '.join(validation_errors)}"
            safe_logger(logger).log_warning(error_msg, {"file": str(file_path)})
            raise Yaml2SqlError(error_msg)

        # Convert to database format
        db_metadata: Dict[str, Any] = md_entry.to_database_metadata()

        # Compute file hash for conflict detection
        file_hash = fs.get_file_hash(file_path)

        # Get machine ID for sync state tracking
        machine_id = socket.gethostname()

        # Check if entry exists
        with db.session_scope() as session:
            existing = db.entries.get(entry_date=md_entry.date)

            # Initialize sync state manager
            sync_mgr = SyncStateManager(session, logger)

            if existing:
                # Check for conflicts before updating
                if sync_mgr.check_conflict("Entry", existing.id, file_hash):
                    safe_logger(logger).log_warning(
                        f"Conflict detected for entry {md_entry.date}",
                        {
                            "file": str(file_path),
                            "action": "proceeding_with_update"
                        }
                    )
                    # Continue with update - conflict logged for user review

                if fs.should_skip_file(file_path, existing.file_hash, force_update):
                    safe_logger(logger).log_debug(f"Entry {md_entry.date} unchanged, skipping")
                    return "skipped"

                # Update existing entry
                try:
                    db.entries.update(
                        existing,
                        db_metadata,
                        sync_source="yaml",
                        removed_by="yaml2sql"
                    )

                    # Update sync state after successful update
                    sync_mgr.update_or_create(
                        entity_type="Entry",
                        entity_id=existing.id,
                        last_synced_at=datetime.now(timezone.utc),
                        sync_source="yaml",
                        sync_hash=file_hash,
                        machine_id=machine_id
                    )

                    safe_logger(logger).log_operation(
                        "entry_updated",
                        {"date": str(md_entry.date), "file": str(file_path)},
                    )
                    return "updated"
                except Exception as e:
                    safe_logger(logger).log_error(
                        e, {"operation": "update_entry", "date": str(md_entry.date)}
                    )
                    raise Yaml2SqlError(f"Failed to update entry: {e}") from e
            else:
                # Create new entry
                try:
                    entry = db.entries.create(
                        db_metadata,
                        sync_source="yaml",
                        removed_by="yaml2sql"
                    )

                    # Create initial sync state for new entry
                    sync_mgr.update_or_create(
                        entity_type="Entry",
                        entity_id=entry.id,
                        last_synced_at=datetime.now(timezone.utc),
                        sync_source="yaml",
                        sync_hash=file_hash,
                        machine_id=machine_id
                    )

                    safe_logger(logger).log_operation(
                        "entry_created",
                        {"date": str(md_entry.date), "file": str(file_path)},
                    )
                    return "created"
                except Exception as e:
                    safe_logger(logger).log_error(
                        e, {"operation": "create_entry", "date": str(md_entry.date)}
                    )
                    raise Yaml2SqlError(f"Failed to create entry: {e}") from e
    except Exception as e:
        safe_logger(logger).log_error(e, {"operation": "parse_file", "file": str(file_path)})

        if raise_on_error:
            raise Yaml2SqlError(f"Failed to parse {file_path}: {e}") from e
        else:
            return "error"


def process_directory(
    input_dir: Path,
    db: PalimpsestDB,
    pattern: str = "**/*.md",
    force_update: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> ConversionStats:
    """
    Process all Markdown files in a directory.

    Args:
        input_dir: Directory containing .md files
        db: Database manager instance
        pattern: Glob pattern for matching files
        force_update: If True, update all files regardless of hash
        logger: Optional logger

    Returns:
        ConversionStats with processing results
    """
    stats = ConversionStats()

    if not input_dir.exists():
        raise Yaml2SqlError(f"Directory not found: {input_dir}")

    # Find all matching files
    md_files: List[Path] = fs.find_markdown_files(input_dir, pattern)

    if not md_files:
        safe_logger(logger).log_info(f"No .md files found in {input_dir}")
        return stats

    safe_logger(logger).log_operation(
        "batch_start", {"input": str(input_dir), "files_found": len(md_files)}
    )

    # Process each file
    for md_file in md_files:
        stats.files_processed += 1

        try:
            result: str = process_entry_file(
                md_file,
                db,
                force_update,
                logger,
                False,
            )

            if result == "created":
                stats.entries_created += 1
            elif result == "updated":
                stats.entries_updated += 1
            elif result == "skipped":
                stats.entries_skipped += 1

        except Yaml2SqlError as e:
            stats.errors += 1
            safe_logger(logger).log_error(e, {"operation": "process_file", "file": str(md_file)})

    safe_logger(logger).log_operation("batch_complete", {"stats": stats.summary()})

    return stats


def sync_directory(
    input_dir: Path,
    db: PalimpsestDB,
    pattern: str = "**/*.md",
    delete_missing: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> ConversionStats:
    """
    Synchronize database with directory contents.

    Updates all entries and optionally removes entries for missing files.

    Args:
        input_dir: Directory containing .md files
        db: Database manager instance
        pattern: Glob pattern for matching files
        delete_missing: If True, delete entries with missing files
        logger: Optional logger

    Returns:
        ConversionStats with sync results
    """
    stats = ConversionStats()

    safe_logger(logger).log_operation(
        "sync_start", {"input": str(input_dir), "delete_missing": delete_missing}
    )

    # Process all files (force update)
    batch_stats: ConversionStats = process_directory(
        input_dir, db, pattern, force_update=True, logger=logger
    )

    stats.files_processed = batch_stats.files_processed
    stats.entries_created = batch_stats.entries_created
    stats.entries_updated = batch_stats.entries_updated
    stats.errors = batch_stats.errors

    # Handle missing files
    if delete_missing:
        md_files: List[Path] = fs.find_markdown_files(input_dir, pattern)
        file_paths: set[str] = {str(f.resolve()) for f in md_files}

        with db.session_scope() as session:
            all_entries = session.query(Entry).all()

            for entry in all_entries:
                if entry.file_path and entry.file_path not in file_paths:
                    try:
                        db.entries.delete(
                            entry,
                            deleted_by="yaml2sql",
                            reason="removed_from_source"
                        )
                        stats.entries_skipped += 1  # Reuse as "deleted" counter
                        safe_logger(logger).log_operation(
                            "entry_soft_deleted",
                            {"date": str(entry.date), "file": entry.file_path},
                        )
                    except Exception as e:
                        stats.errors += 1
                        safe_logger(logger).log_error(
                            e,
                            {"operation": "delete_entry", "date": str(entry.date)},
                        )

    safe_logger(logger).log_operation("sync_complete", {"stats": stats.summary()})

    return stats


# --- CLI ---
