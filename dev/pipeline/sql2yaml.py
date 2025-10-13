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
from datetime import date, datetime
from pathlib import Path
from sqlalchemy.orm import Session
from typing import List, Optional

from dev.database.query_analytics import QueryAnalytics
from dev.dataclasses.md_entry import MdEntry
from dev.database.models import Entry
from dev.database.query_optimizer import (
    HierarchicalBatcher,
    QueryOptimizer,
    RelationshipLoader,
)
from dev.database.manager import PalimpsestDB

from dev.core.paths import LOG_DIR, DB_PATH, ALEMBIC_DIR, BACKUP_DIR, MD_DIR
from dev.core.exceptions import Sql2YamlError
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.core.validators import DataValidator

from dev.utils import md


class ExportStats:
    """Track export statistics."""

    def __init__(self) -> None:
        self.entries_exported: int = 0
        self.entries_skipped: int = 0
        self.files_created: int = 0
        self.files_updated: int = 0
        self.errors: int = 0
        self.start_time: datetime = datetime.now()

    def duration(self) -> float:
        """Get elapsed time in seconds."""
        return (datetime.now() - self.start_time).total_seconds()

    def summary(self) -> str:
        """Get formatted summary."""
        return (
            f"{self.entries_exported} exported, "
            f"{self.files_created} created, "
            f"{self.files_updated} updated, "
            f"{self.entries_skipped} skipped, "
            f"{self.errors} errors in {self.duration():.2f}s"
        )


def setup_logger(log_dir: Path) -> PalimpsestLogger:
    """Setup logging for sql2yaml operations."""
    operations_log_dir: Path = log_dir / "operations"
    operations_log_dir.mkdir(parents=True, exist_ok=True)
    return PalimpsestLogger(operations_log_dir, component_name="sql2yaml")


def export_entry(
    entry: Entry,
    output_dir: Path,
    force_overwrite: bool = False,
    preserve_body: bool = True,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Export a single database entry to Markdown file.

    Args:
        entry: SQLAlchemy Entry ORM instance
        output_dir: Base output directory
        force_overwrite: If True, overwrite existing files
        preserve_body: If True, preserve existing body content
        logger: Optional logger

    Returns:
        Status string: "created", "updated", "skipped"

    Raises:
        Sql2YamlError: If export fails
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


def export_entries(
    session: Session,
    entries: List[Entry],
    output_dir: Path,
    force_overwrite: bool = False,
    preserve_body: bool = True,
    logger: Optional[PalimpsestLogger] = None,
) -> ExportStats:
    """
    Export multiple database entries to Markdown files.
    Uses Optimized relationship loading.

    Args:
        entries: List of Entry ORM instances
        output_dir: Base output directory
        force_overwrite: If True, overwrite existing files
        preserve_body: If True, preserve existing body content
        logger: Optional logger

    Returns:
        ExportStats with export results
    """
    stats = ExportStats()

    if logger:
        logger.log_operation(
            "export_batch_start", {"count": len(entries), "output": str(output_dir)}
        )

    RelationshipLoader.preload_for_entries(session, entries)
    if logger:
        logger.log_debug("Preloaded relationships for batch")

    for entry in entries:
        try:
            result: str = export_entry(
                entry, output_dir, force_overwrite, preserve_body, logger
            )

            stats.entries_exported += 1

            if result == "created":
                stats.files_created += 1
            elif result == "updated":
                stats.files_updated += 1
            elif result == "skipped":
                stats.entries_skipped += 1

        except Sql2YamlError as e:
            stats.errors += 1
            if logger:
                logger.log_error(
                    e, {"operation": "export_entry", "date": str(entry.date)}
                )

    if logger:
        logger.log_operation("export_batch_complete", {"stats": stats.summary()})

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
    """sql2yaml - Export database entries to Markdown with YAML"""
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
            entry = db.get_entry(session, date_obj)

            if entry is None:
                click.echo(f"❌ No entry found for {date_obj}", err=True)
                sys.exit(1)

            result: str = export_entry(
                entry, output_dir, force, not no_preserve_body, logger
            )

        if result == "created":
            click.echo("✅ File created")
        elif result == "updated":
            click.echo("✅ File updated")
        elif result == "skipped":
            click.echo("⏭️  File skipped (already exists)")

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
            analytics = QueryAnalytics(logger=logger)
            entries = analytics.get_entries_by_date_range(session, start, end)

            if not entries:
                click.echo("⚠️  No entries found in date range")
                return

            click.echo(f"Found {len(entries)} entries")

            stats: ExportStats = export_entries(
                session, entries, output_dir, force, not no_preserve_body, logger
            )

        click.echo("\n✅ Export complete:")
        click.echo(f"  Entries exported: {stats.entries_exported}")
        click.echo(f"  Files created: {stats.files_created}")
        click.echo(f"  Files updated: {stats.files_updated}")
        click.echo(f"  Entries skipped: {stats.entries_skipped}")
        if stats.errors > 0:
            click.echo(f"  ⚠️  Errors: {stats.errors}")
        click.echo(f"  Duration: {stats.duration():.2f}s")

    except (Sql2YamlError, Exception) as e:
        handle_cli_error(
            ctx,
            e,
            "export_range",
            {"start_date": start_date, "end_date": end_date},
        )


@cli.command()
@click.argument("year", type=int)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=str(MD_DIR),
    help=f"Output directory (default: {MD_DIR})",
)
@click.option("-f", "--force", is_flag=True, help="Overwrite existing files")
@click.pass_context
def export_year(ctx: click.Context, year: int, output: str, force: bool) -> None:
    """Export entries for a specific year (optimized)."""
    logger: PalimpsestLogger = ctx.obj["logger"]
    db: PalimpsestDB = ctx.obj["db"]

    try:
        output_dir: Path = Path(output)

        click.echo(f"📅 Exporting {year}")

        with db.session_scope() as session:
            # Use optimized monthly query
            entries = QueryOptimizer.for_year(session, year)

            if not entries:
                click.echo("⚠️  No entries found for this year")
                return

            click.echo(f"Found {len(entries)} entries")

            stats: ExportStats = export_entries(
                session, entries, output_dir, force, True, logger
            )

        click.echo("\n✅ Export complete:")
        click.echo(f"  Entries exported: {stats.entries_exported}")
        click.echo(f"  Files created: {stats.files_created}")
        click.echo(f"  Files updated: {stats.files_updated}")
        click.echo(f"  Entries skipped: {stats.entries_skipped}")
        if stats.errors > 0:
            click.echo(f"  ⚠️  Errors: {stats.errors}")
        click.echo(f"  Duration: {stats.duration():.2f}s")

    except (Sql2YamlError, Exception) as e:
        handle_cli_error(
            ctx,
            e,
            "export_year",
            {"year": year},
        )


@cli.command()
@click.argument("year", type=int)
@click.argument("month", type=int)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=str(MD_DIR),
    help=f"Output directory (default: {MD_DIR})",
)
@click.option("-f", "--force", is_flag=True, help="Overwrite existing files")
@click.pass_context
def export_month(
    ctx: click.Context, year: int, month: int, output: str, force: bool
) -> None:
    """Export entries for a specific month (optimized)."""
    logger: PalimpsestLogger = ctx.obj["logger"]
    db: PalimpsestDB = ctx.obj["db"]

    try:
        output_dir: Path = Path(output)

        click.echo(f"📅 Exporting {year}-{month:02d}")

        with db.session_scope() as session:
            # Use optimized monthly query
            entries = QueryOptimizer.for_month(session, year, month)

            if not entries:
                click.echo("⚠️  No entries found for this month")
                return

            click.echo(f"Found {len(entries)} entries")

            stats: ExportStats = export_entries(
                session, entries, output_dir, force, True, logger
            )

        click.echo("\n✅ Export complete:")
        click.echo(f"  Entries exported: {stats.entries_exported}")
        click.echo(f"  Files created: {stats.files_created}")
        click.echo(f"  Files updated: {stats.files_updated}")
        click.echo(f"  Entries skipped: {stats.entries_skipped}")
        if stats.errors > 0:
            click.echo(f"  ⚠️  Errors: {stats.errors}")
        click.echo(f"  Duration: {stats.duration():.2f}s")

    except (Sql2YamlError, Exception) as e:
        handle_cli_error(
            ctx,
            e,
            "export_month",
            {"year": year, "month": month},
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
            # ✨ NEW: Use HierarchicalBatcher
            batches = HierarchicalBatcher.create_batches(session, threshold=threshold)

            click.echo(f"Created {len(batches)} batches")
            total_stats = ExportStats()

            with click.progressbar(batches, label="Exporting batches") as batch_bar:
                for batch in batch_bar:
                    click.echo(
                        f"\n📦 {batch.period_label} ({batch.entry_count} entries)"
                    )

                    # All relationships already preloaded by QueryOptimizer!
                    stats = export_entries(
                        session, batch.entries, output_dir, force, True, logger
                    )

                    # Aggregate stats
                    total_stats.entries_exported += stats.entries_exported
                    total_stats.files_created += stats.files_created
                    total_stats.files_updated += stats.files_updated
                    total_stats.entries_skipped += stats.entries_skipped
                    total_stats.errors += stats.errors

                    session.expunge_all()

        click.echo("\n✅ Hierarchical export complete:")
        click.echo(f"  Total entries: {total_stats.entries_exported}")
        click.echo(f"  Files created: {total_stats.files_created}")
        click.echo(f"  Files updated: {total_stats.files_updated}")
        click.echo(f"  Entries skipped: {total_stats.entries_skipped}")
        if total_stats.errors > 0:
            click.echo(f"  ⚠️  Errors: {total_stats.errors}")
        click.echo(f"  Duration: {total_stats.duration():.2f}s")

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
@click.confirmation_option(prompt="This will export all database entries. Continue?")
@click.pass_context
def all(ctx: click.Context, output: str, force: bool, no_preserve_body: bool) -> None:
    """Export all database entries."""
    logger: PalimpsestLogger = ctx.obj["logger"]
    db: PalimpsestDB = ctx.obj["db"]

    try:
        output_dir: Path = Path(output)

        click.echo("📤 Exporting all database entries")

        # Get all entries
        with db.session_scope() as session:
            entries = session.query(Entry).order_by(Entry.date).all()

            if not entries:
                click.echo("⚠️  No entries found in database")
                return

            click.echo(f"Found {len(entries)} entries")

            stats: ExportStats = export_entries(
                session, entries, output_dir, force, not no_preserve_body, logger
            )

        click.echo("\n✅ Export complete:")
        click.echo(f"  Entries exported: {stats.entries_exported}")
        click.echo(f"  Files created: {stats.files_created}")
        click.echo(f"  Files updated: {stats.files_updated}")
        click.echo(f"  Entries skipped: {stats.entries_skipped}")
        if stats.errors > 0:
            click.echo(f"  ⚠️  Errors: {stats.errors}")
        click.echo(f"  Duration: {stats.duration():.2f}s")

    except (Sql2YamlError, Exception) as e:
        handle_cli_error(ctx, e, "export_all")


if __name__ == "__main__":
    cli(obj={})
