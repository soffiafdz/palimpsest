#!/usr/bin/env python3
"""
sql2yaml.py
-----------
Export database entries to Markdown files with rich YAML frontmatter.

This pipeline converts structured database records into human-editable
Markdown files with comprehensive YAML metadata. It's the inverse of
yaml2sql, enabling bidirectional data flow.

Features:
- Export entries with complete relationship metadata
- Generate human-readable YAML frontmatter
- Preserve existing body content (or regenerate from database)
- Handle manuscript metadata
- Batch export with filtering
- Update existing files or create new ones

Usage:
    # Export single entry
    python -m dev.pipeline.sql2yaml export 2024-01-15 -o output/

    # Export date range
    python -m dev.pipeline.sql2yaml range 2024-01-01 2024-01-31 -o output/

    # Export all entries
    python -m dev.pipeline.sql2yaml all -o output/
"""
from __future__ import annotations

import sys
import click
from datetime import date
from pathlib import Path
from typing import List, Optional

from dev.dataclasses.md_entry import MdEntry
from dev.database.models import Entry
from dev.database.manager import PalimpsestDB

from dev.core.paths import LOG_DIR, DB_PATH, ALEMBIC_DIR, BACKUP_DIR, MD_DIR
from dev.core.exceptions import Sql2YamlError
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.core.validators import DataValidator
from dev.core.cli import setup_logger

from dev.utils import md


def export_entry_to_markdown(
    entry: Entry,
    output_dir: Path,
    force_overwrite: bool = False,
    preserve_body: bool = True,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Export a single database entry to Markdown file with complete YAML frontmatter.

    Implementation Logic:
    ---------------------
    Core function for sql2yaml pipeline. Reads a database Entry ORM object,
    converts all relationships to YAML frontmatter, and generates a human-editable
    Markdown file. Handles content preservation to avoid losing text.

    Processing Flow:
    1. Determine output file path (output_dir/YYYY/YYYY-MM-DD.md)
    2. Check for existing file (skip if exists unless force_overwrite)
    3. Retrieve/preserve body content (three strategies)
    4. Convert database Entry to MdEntry dataclass
    5. Generate complete Markdown with YAML frontmatter
    6. Write to file with UTF-8 encoding
    7. Return status for statistics tracking

    Content Preservation Strategies:
    Three strategies in priority order:

    1. preserve_body=True + file exists:
       - Reads existing .md file
       - Extracts body content (everything after frontmatter)
       - Combines with NEW frontmatter from database
       - Use case: Database edits while preserving text

    2. entry.file_path exists:
       - Reads body from original source file
       - Uses entry.file_path from database
       - Use case: Initial export from database

    3. No existing content:
       - Generates placeholder body with date
       - Minimal fallback for missing content
       - Use case: New entries without source files

    YAML Generation from Database:
    - Loads all relationships via SQLAlchemy ORM
    - People: Formats names with hyphens/aliases
    - Locations: Organizes by city hierarchy
    - Events: List of event identifiers
    - Tags: List of tag names
    - References: Includes sources and context
    - Poems: Includes versions and revisions
    - Manuscript: Editorial metadata if present

    File Organization:
    - Creates year-based directories automatically
    - Filename format: YYYY-MM-DD.md
    - Example: md/2024/2024-01-15.md

    Status Return Values:
    - "created": New file written (didn't exist)
    - "updated": Existing file overwritten
    - "skipped": File exists and not force_overwrite

    Database Read Operations:
    - Entry loaded with all relationships (eager loading)
    - No database modifications (export is read-only)
    - Relationship data accessed via ORM navigation
    - Example: entry.people, entry.locations, entry.tags

    Error Handling:
    - MdEntry creation failures logged with context
    - Markdown generation failures logged with context
    - File write failures logged with context
    - All failures raise Sql2YamlError with original exception

    Use Cases:
    - Restore .md files from database backup
    - Propagate database edits back to files
    - Generate fresh Markdown from imported data
    - Bidirectional synchronization with yaml2sql

    Args:
        entry: SQLAlchemy Entry ORM instance with relationships loaded
        output_dir: Base output directory (typically MD_DIR)
        force_overwrite: If True, overwrite existing files
        preserve_body: If True, preserve existing body content
        logger: Optional logger for operation tracking

    Returns:
        Status string: "created", "updated", or "skipped"

    Raises:
        Sql2YamlError: If export fails (MdEntry creation, markdown generation, file write)
    """
    if logger:
        logger.log_debug(f"Exporting entry {entry.date}")

    # Determine output path
    year_dir: Path = output_dir / str(entry.date.year)
    year_dir.mkdir(parents=True, exist_ok=True)

    filename: str = f"{entry.date.isoformat()}.md"
    output_path: Path = year_dir / filename

    # Check if file exists
    file_existed: bool = output_path.exists()

    if file_existed and not force_overwrite:
        if logger:
            logger.log_debug(f"File exists, skipping: {output_path.name}")
        return "skipped"

    # Get body content
    body_lines: List[str]
    if preserve_body and file_existed:
        # Preserve existing body
        body_lines = md.read_entry_body(output_path)
        if logger:
            logger.log_debug(f"Preserved body: {len(body_lines)} lines")
    elif entry.file_path and Path(entry.file_path).exists():
        # Read from original file
        body_lines = md.read_entry_body(Path(entry.file_path))
        if logger:
            logger.log_debug(f"Loaded body from: {entry.file_path}")
    else:
        body_lines = md.generate_placeholder_body(entry.date)
        if logger:
            logger.log_debug("Generated placeholder body")

    # Create MdEntry from database
    try:
        md_entry: MdEntry = MdEntry.from_database(entry, body_lines, output_path)
    except Exception as e:
        if logger:
            logger.log_error(
                e, {"operation": "create_mdentry", "date": str(entry.date)}
            )
        raise Sql2YamlError(f"Failed to create MdEntry: {e}") from e

    # Generate markdown
    try:
        markdown_content: str = md_entry.to_markdown()
    except Exception as e:
        if logger:
            logger.log_error(
                e, {"operation": "generate_markdown", "date": str(entry.date)}
            )
        raise Sql2YamlError(f"Failed to generate markdown: {e}") from e

    # Write file
    try:
        output_path.write_text(markdown_content, encoding="utf-8")

        if logger:
            action: str = "updated" if file_existed else "created"
            logger.log_operation(
                f"entry_{action}", {"date": str(entry.date), "file": str(output_path)}
            )

        return "updated" if file_existed else "created"

    except Exception as e:
        if logger:
            logger.log_error(e, {"operation": "write_file", "file": str(output_path)})
        raise Sql2YamlError(f"Failed to write file: {e}") from e


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
    """sql2yaml - Export database entries to Markdown with YAML"""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = Path(db_path)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["verbose"] = verbose
    ctx.obj["logger"] = setup_logger(Path(log_dir), "sql2yaml")

    # Initialize database
    ctx.obj["db"] = PalimpsestDB(
        db_path=Path(db_path),
        alembic_dir=ALEMBIC_DIR,
        log_dir=Path(log_dir),
        backup_dir=BACKUP_DIR,
        enable_auto_backup=False,
    )


@cli.command()
@click.argument("entry_date")
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=str(MD_DIR),
    help=f"Output directory (default: {MD_DIR})",
)
@click.option("-f", "--force", is_flag=True, help="Overwrite existing file")
@click.option(
    "--no-preserve-body", is_flag=True, help="Don't preserve existing body content"
)
@click.pass_context
def export(
    ctx: click.Context,
    entry_date: str,
    output: str,
    force: bool,
    no_preserve_body: bool,
) -> None:
    """Export a single entry by date (YYYY-MM-DD)."""
    logger: PalimpsestLogger = ctx.obj["logger"]
    db: PalimpsestDB = ctx.obj["db"]

    try:
        # Parse date
        date_obj: Optional[date] = DataValidator.normalize_date(entry_date)
        if date_obj is None:
            raise Sql2YamlError(f"Invalid date format: {entry_date}")

        output_dir: Path = Path(output)
        click.echo(f"📤 Exporting entry for {date_obj}")

        # Get entry from database
        with db.session_scope() as session:
            entry = db.entries.get(entry_date=date_obj)

            if entry is None:
                click.echo(f"❌ No entry found for {date_obj}", err=True)
                sys.exit(1)

            stats = db.export_manager.export_entries_optimized(
                session,
                [entry.id],
                export_entry_to_markdown,
                output_dir=output_dir,
                force_overwrite=force,
                preserve_body=not no_preserve_body,
                logger=logger,
            )

        if stats["errors"] > 0:
            click.echo("❌ Export failed")
            sys.exit(1)
        else:
            click.echo("✅ Export complete")

    except (Sql2YamlError, Exception) as e:
        handle_cli_error(ctx, e, "export", {"entry_date": entry_date})


@cli.command()
@click.argument("start_date")
@click.argument("end_date")
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=str(MD_DIR),
    help=f"Output directory (default: {MD_DIR})",
)
@click.option("-f", "--force", is_flag=True, help="Overwrite existing files")
@click.option(
    "--no-preserve-body", is_flag=True, help="Don't preserve existing body content"
)
@click.pass_context
def range(
    ctx: click.Context,
    start_date: str,
    end_date: str,
    output: str,
    force: bool,
    no_preserve_body: bool,
) -> None:
    """Export entries in date range (YYYY-MM-DD YYYY-MM-DD)."""
    logger: PalimpsestLogger = ctx.obj["logger"]
    db: PalimpsestDB = ctx.obj["db"]

    try:
        # Parse dates
        start: Optional[date] = DataValidator.normalize_date(start_date)
        end: Optional[date] = DataValidator.normalize_date(end_date)

        if start is None or end is None:
            raise Sql2YamlError("Invalid date format")

        output_dir: Path = Path(output)
        click.echo(f"📤 Exporting entries from {start} to {end}")

        # Get entries from database
        with db.session_scope() as session:
            entries = db.query_analytics.get_entries_by_date_range(session, start, end)

            if not entries:
                click.echo("⚠️  No entries found in date range")
                return

            click.echo(f"Found {len(entries)} entries")

            entry_ids = [e.id for e in entries]
            stats = db.export_manager.export_entries_optimized(
                session,
                entry_ids,
                export_entry_to_markdown,
                output_dir=output_dir,
                force_overwrite=force,
                preserve_body=not no_preserve_body,
                logger=logger,
            )

        click.echo("\n✅ Export complete:")
        click.echo(f"  Entries processed: {stats['processed']}")
        if stats["errors"] > 0:
            click.echo(f"  ⚠️  Errors: {stats['errors']}")
        click.echo(f"  Duration: {stats['duration']:.2f}s")

    except (Sql2YamlError, Exception) as e:
        handle_cli_error(
            ctx,
            e,
            "export_range",
            {"start_date": start_date, "end_date": end_date},
        )


@cli.command()
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=str(MD_DIR),
    help=f"Output directory (default: {MD_DIR})",
)
@click.option("-f", "--force", is_flag=True, help="Overwrite existing files")
@click.option(
    "--threshold",
    type=int,
    default=500,
    help="Batch size threshold for year splitting (default: 500)",
)
@click.pass_context
def export_hierarchical(
    ctx: click.Context, output: str, force: bool, threshold: int
) -> None:
    """
    Export all entries using hierarchical batching for optimal performance.

    Automatically batches by year or month based on entry volume.
    """
    logger: PalimpsestLogger = ctx.obj["logger"]
    db: PalimpsestDB = ctx.obj["db"]

    try:
        output_dir: Path = Path(output)
        click.echo("📤 Starting hierarchical export")

        with db.session_scope() as session:
            stats = db.export_manager.export_hierarchical(
                session,
                export_entry_to_markdown,
                threshold=threshold,
                output_dir=output_dir,
                force_overwrite=force,
                preserve_body=True,
                logger=logger,
            )

        click.echo("\n✅ Hierarchical export complete:")
        click.echo(f"  Total batches: {stats['total_batches']}")
        click.echo(f"  Total entries: {stats['total_entries']}")
        click.echo(f"  Processed: {stats['processed']}")
        if stats["errors"] > 0:
            click.echo(f"  ⚠️  Errors: {stats['errors']}")
        click.echo(f"  Duration: {stats['duration']:.2f}s")

    except (Sql2YamlError, Exception) as e:
        handle_cli_error(
            ctx,
            e,
            "export_hierarchical",
            {"threshold": threshold},
        )


@cli.command()
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=str(MD_DIR),
    help=f"Output directory (default: {MD_DIR})",
)
@click.option("-f", "--force", is_flag=True, help="Overwrite existing files")
@click.option(
    "--no-preserve-body", is_flag=True, help="Don't preserve existing body content"
)
@click.option(
    "--threshold",
    type=int,
    default=500,
    help="Batch size threshold (default: 500)",
)
@click.confirmation_option(prompt="This will export all database entries. Continue?")
@click.pass_context
def all(
    ctx: click.Context,
    output: str,
    force: bool,
    no_preserve_body: bool,
    threshold: int,
) -> None:
    """Export all database entries."""
    logger: PalimpsestLogger = ctx.obj["logger"]
    db: PalimpsestDB = ctx.obj["db"]

    try:
        output_dir: Path = Path(output)

        click.echo("📤 Exporting all database entries")

        # Get all entries
        with db.session_scope() as session:
            stats = db.export_manager.export_hierarchical(
                session,
                export_entry_to_markdown,
                threshold=threshold,
                output_dir=output_dir,
                force_overwrite=force,
                preserve_body=not no_preserve_body,
                logger=logger,
            )

        click.echo("\n✅ Export complete:")
        click.echo(f"  Total batches: {stats['total_batches']}")
        click.echo(f"  Total entries: {stats['total_entries']}")
        click.echo(f"  Processed: {stats['processed']}")
        if stats["errors"] > 0:
            click.echo(f"  ⚠️  Errors: {stats['errors']}")
        click.echo(f"  Duration: {stats['duration']:.2f}s")

    except (Sql2YamlError, Exception) as e:
        handle_cli_error(ctx, e, "export_all")


if __name__ == "__main__":
    cli(obj={})
