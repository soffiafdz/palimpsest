#!/usr/bin/env python3
"""
yaml2sql.py
-----------
Parse YAML frontmatter from Markdown files and populate database.

This pipeline converts human-edited Markdown entries with rich YAML metadata
into structured database records. It handles the complete conversion from
MdEntry → Database ORM models.

Features:
- Parse YAML frontmatter with progressive complexity
- Intelligent name/location parsing (hyphens, quotes, hierarchy)
- Create or update database entries with relationships
- Handle manuscript metadata
- Batch processing with error recovery
- Comprehensive logging and statistics

Usage:
    # Single file
    python -m dev.pipeline.yaml2sql update path/to/entry.md

    # Batch directory
    python -m dev.pipeline.yaml2sql batch path/to/entries/

    # Full sync
    python -m dev.pipeline.yaml2sql sync path/to/entries/
"""
from __future__ import annotations

import sys
import click
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from dev.dataclasses.md_entry import MdEntry
from dev.database.manager import PalimpsestDB
from dev.database.models import Entry
from dev.core.exceptions import Yaml2SqlError
from dev.core.paths import LOG_DIR, DB_PATH, ALEMBIC_DIR, BACKUP_DIR
from dev.core.logging_manager import PalimpsestLogger
from dev.utils import fs


class ConversionStats:
    """Track conversion statistics."""

    def __init__(self) -> None:
        self.files_processed: int = 0
        self.entries_created: int = 0
        self.entries_updated: int = 0
        self.entries_skipped: int = 0
        self.errors: int = 0
        self.start_time: datetime = datetime.now()

    def duration(self) -> float:
        """Get elapsed time in seconds."""
        return (datetime.now() - self.start_time).total_seconds()

    def summary(self) -> str:
        """Get formatted summary."""
        return (
            f"{self.files_processed} files, "
            f"{self.entries_created} created, "
            f"{self.entries_updated} updated, "
            f"{self.entries_skipped} skipped, "
            f"{self.errors} errors in {self.duration():.2f}s"
        )


def setup_logger(log_dir: Path) -> PalimpsestLogger:
    """Setup logging for yaml2sql operations."""
    operations_log_dir: Path = log_dir / "operations"
    operations_log_dir.mkdir(parents=True, exist_ok=True)
    return PalimpsestLogger(operations_log_dir, component_name="yaml2sql")


def process_entry_file(
    file_path: Path,
    db: PalimpsestDB,
    force_update: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Process a single Markdown file and update database.

    Args:
        file_path: Path to .md file
        db: Database manager instance
        force_update: If True, update even if file hash unchanged
        logger: Optional logger

    Returns:
        Status string: "created", "updated", "skipped", or "error"

    Raises:
        Yaml2SqlError: If processing fails
    """
    if logger:
        logger.log_debug(f"Processing {file_path.name}")

    # Parse markdown entry
    try:
        md_entry: MdEntry = MdEntry.from_file(file_path, verbose=False)
    except Exception as e:
        if logger:
            logger.log_error(e, {"operation": "parse_file", "file": str(file_path)})
        raise Yaml2SqlError(f"Failed to parse {file_path}: {e}") from e

    # Validate entry
    validation_errors: List[str] = md_entry.validate()
    if validation_errors:
        error_msg: str = f"Validation failed: {', '.join(validation_errors)}"
        if logger:
            logger.log_warning(error_msg, {"file": str(file_path)})
        raise Yaml2SqlError(error_msg)

    # Convert to database format
    db_metadata: Dict[str, Any] = md_entry.to_database_metadata()

    # Check if entry exists
    with db.session_scope() as session:
        existing = db.get_entry(session, md_entry.date)

        if existing:
            if fs.should_skip_file(file_path, existing.file_hash, force_update):
                if logger:
                    logger.log_debug(f"Entry {md_entry.date} unchanged, skipping")
                return "skipped"

            # Update existing entry
            try:
                db.update_entry(session, existing, db_metadata)
                if logger:
                    logger.log_operation(
                        "entry_updated",
                        {"date": str(md_entry.date), "file": str(file_path)},
                    )
                return "updated"
            except Exception as e:
                if logger:
                    logger.log_error(
                        e, {"operation": "update_entry", "date": str(md_entry.date)}
                    )
                raise Yaml2SqlError(f"Failed to update entry: {e}") from e
        else:
            # Create new entry
            try:
                db.create_entry(session, db_metadata)
                if logger:
                    logger.log_operation(
                        "entry_created",
                        {"date": str(md_entry.date), "file": str(file_path)},
                    )
                return "created"
            except Exception as e:
                if logger:
                    logger.log_error(
                        e, {"operation": "create_entry", "date": str(md_entry.date)}
                    )
                raise Yaml2SqlError(f"Failed to create entry: {e}") from e


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
        if logger:
            logger.log_info(f"No .md files found in {input_dir}")
        return stats

    if logger:
        logger.log_operation(
            "batch_start", {"input": str(input_dir), "files_found": len(md_files)}
        )

    # Process each file
    for md_file in md_files:
        stats.files_processed += 1

        try:
            result: str = process_entry_file(md_file, db, force_update, logger)

            if result == "created":
                stats.entries_created += 1
            elif result == "updated":
                stats.entries_updated += 1
            elif result == "skipped":
                stats.entries_skipped += 1

        except Yaml2SqlError as e:
            stats.errors += 1
            if logger:
                logger.log_error(e, {"operation": "process_file", "file": str(md_file)})

    if logger:
        logger.log_operation("batch_complete", {"stats": stats.summary()})

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

    if logger:
        logger.log_operation(
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
                        db.delete_entry(session, entry)
                        stats.entries_skipped += 1  # Reuse as "deleted" counter
                        if logger:
                            logger.log_operation(
                                "entry_deleted",
                                {"date": str(entry.date), "file": entry.file_path},
                            )
                    except Exception as e:
                        stats.errors += 1
                        if logger:
                            logger.log_error(
                                e,
                                {"operation": "delete_entry", "date": str(entry.date)},
                            )

    if logger:
        logger.log_operation("sync_complete", {"stats": stats.summary()})

    return stats


# ----- CLI -----
@click.group()
@click.option(
    "--db-path",
    type=click.Path(),
    default=str(DB_PATH),
    help="Path to database file",
)
@click.option(
    "--log-dir",
    type=click.Path(),
    default=str(LOG_DIR),
    help="Directory for log files",
)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
@click.pass_context
def cli(ctx: click.Context, db_path: str, log_dir: str, verbose: bool) -> None:
    """yaml2sql - Parse YAML frontmatter and populate database"""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = Path(db_path)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["verbose"] = verbose
    ctx.obj["logger"] = setup_logger(Path(log_dir))

    # Initialize database
    ctx.obj["db"] = PalimpsestDB(
        db_path=Path(db_path),
        alembic_dir=ALEMBIC_DIR,
        log_dir=Path(log_dir),
        backup_dir=BACKUP_DIR,
        enable_auto_backup=False,
    )


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("-f", "--force", is_flag=True, help="Force update even if unchanged")
@click.pass_context
def update(ctx: click.Context, input_file: str, force: bool) -> None:
    """Update database from a single Markdown file."""
    logger: PalimpsestLogger = ctx.obj["logger"]
    db: PalimpsestDB = ctx.obj["db"]

    try:
        file_path: Path = Path(input_file)

        click.echo(f"📄 Processing {file_path.name}")

        result: str = process_entry_file(file_path, db, force, logger)

        if result == "created":
            click.echo("✅ Entry created")
        elif result == "updated":
            click.echo("✅ Entry updated")
        elif result == "skipped":
            click.echo("⏭️  Entry skipped (unchanged)")

    except Yaml2SqlError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        if ctx.obj["verbose"]:
            import traceback

            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.argument("input_dir", type=click.Path(exists=True))
@click.option(
    "-p",
    "--pattern",
    default="**/*.md",
    help="File pattern to match (default: **/*.md)",
)
@click.option("-f", "--force", is_flag=True, help="Force update all files")
@click.pass_context
def batch(ctx: click.Context, input_dir: str, pattern: str, force: bool) -> None:
    """Process all Markdown files in a directory."""
    logger: PalimpsestLogger = ctx.obj["logger"]
    db: PalimpsestDB = ctx.obj["db"]

    try:
        dir_path: Path = Path(input_dir)

        click.echo(f"📁 Processing directory: {dir_path}")

        stats: ConversionStats = process_directory(dir_path, db, pattern, force, logger)

        click.echo("\n✅ Batch processing complete:")
        click.echo(f"  Files processed: {stats.files_processed}")
        click.echo(f"  Entries created: {stats.entries_created}")
        click.echo(f"  Entries updated: {stats.entries_updated}")
        click.echo(f"  Entries skipped: {stats.entries_skipped}")
        if stats.errors > 0:
            click.echo(f"  ⚠️  Errors: {stats.errors}")
        click.echo(f"  Duration: {stats.duration():.2f}s")

    except Yaml2SqlError as e:
        click.echo(f"❌ Batch processing failed: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        if ctx.obj["verbose"]:
            import traceback

            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.argument("input_dir", type=click.Path(exists=True))
@click.option(
    "-p",
    "--pattern",
    default="**/*.md",
    help="File pattern to match (default: **/*.md)",
)
@click.option(
    "--delete-missing", is_flag=True, help="Delete database entries for missing files"
)
@click.confirmation_option(
    prompt="This will update all entries and optionally delete missing. Continue?"
)
@click.pass_context
def sync(
    ctx: click.Context, input_dir: str, pattern: str, delete_missing: bool
) -> None:
    """Synchronize database with directory contents."""
    logger: PalimpsestLogger = ctx.obj["logger"]
    db: PalimpsestDB = ctx.obj["db"]

    try:
        dir_path: Path = Path(input_dir)

        click.echo(f"🔄 Synchronizing database with: {dir_path}")

        stats: ConversionStats = sync_directory(
            dir_path, db, pattern, delete_missing, logger
        )

        click.echo("\n✅ Synchronization complete:")
        click.echo(f"  Files processed: {stats.files_processed}")
        click.echo(f"  Entries created: {stats.entries_created}")
        click.echo(f"  Entries updated: {stats.entries_updated}")
        if delete_missing:
            click.echo(f"  Entries deleted: {stats.entries_skipped}")
        if stats.errors > 0:
            click.echo(f"  ⚠️  Errors: {stats.errors}")
        click.echo(f"  Duration: {stats.duration():.2f}s")

    except Yaml2SqlError as e:
        click.echo(f"❌ Sync failed: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        if ctx.obj["verbose"]:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    cli(obj={})
