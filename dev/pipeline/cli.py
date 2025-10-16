#!/usr/bin/env python3
"""
cli.py
-------------------
Unified command-line interface for the complete journal processing pipeline.

Orchestrates the full workflow:
1. Process inbox → Format raw exports
2. txt2md → Convert formatted text to Markdown
3. yaml2sql → Populate database from Markdown metadata
4. sql2yaml → Export database to Markdown (optional)
5. md2pdf → Generate yearly PDFs

Can run individual steps or the complete pipeline end-to-end.

Usage:
    # Run complete pipeline
    python -m dev.pipeline.pipeline run-all

    # Individual steps
    python -m dev.pipeline.cli inbox
    python -m dev.pipeline.cli convert
    python -m dev.pipeline.cli sync-db
    python -m dev.pipeline.cli export-db
    python -m dev.pipeline.cli build-pdf 2025

    # Backups
    python -m dev.pipeline.cli backup-data
    python -m dev.pipeline.cli backup-list

    # Status and validation
    python -m dev.pipeline.cli status
    python -m dev.pipeline.cli validate
"""
from __future__ import annotations

import sys
import click
from pathlib import Path
from datetime import datetime
from typing import Optional

from dev.core.paths import (
    INBOX_DIR,
    TXT_DIR,
    MD_DIR,
    PDF_DIR,
    LOG_DIR,
    DB_PATH,
    ALEMBIC_DIR,
    BACKUP_DIR,
    TEX_DIR,
    DATA_DIR,
)
from dev.builders.txtbuilder import TxtBuilder
from dev.builders.pdfbuilder import PdfBuilder
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.core.backup_manager import BackupManager
from dev.core.exceptions import BackupError
from dev.database.manager import PalimpsestDB
from dev.database.models import Entry
from dev.database.query_analytics import QueryAnalytics

from .txt2md import convert_directory, convert_file
from .yaml2sql import process_directory
from .sql2yaml import export_entry_to_markdown


def setup_logger(log_dir: Path) -> PalimpsestLogger:
    """Setup logging for pipeline operations."""
    operations_log_dir = log_dir / "operations"
    operations_log_dir.mkdir(parents=True, exist_ok=True)
    return PalimpsestLogger(operations_log_dir, component_name="pipeline")


@click.group()
@click.option(
    "--log-dir",
    type=click.Path(),
    default=str(LOG_DIR),
    help="Directory for log files",
)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
@click.pass_context
def cli(ctx: click.Context, log_dir: str, verbose: bool) -> None:
    """Palimpsest Journal Processing Pipeline"""
    ctx.ensure_object(dict)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["verbose"] = verbose
    ctx.obj["logger"] = setup_logger(Path(log_dir))


@cli.command()
@click.option(
    "--inbox",
    type=click.Path(),
    default=str(INBOX_DIR),
    help="Inbox directory with raw exports",
)
@click.option(
    "--output",
    type=click.Path(),
    default=str(TXT_DIR),
    help="Output directory for formatted text",
)
@click.pass_context
def inbox(ctx: click.Context, inbox: str, output: str) -> None:
    """Process inbox: format and organize raw 750words exports."""
    logger: PalimpsestLogger = ctx.obj["logger"]

    click.echo("📥 Processing inbox...")

    try:
        builder = TxtBuilder(
            inbox_dir=Path(inbox), output_dir=Path(output), logger=logger
        )

        stats = builder.build()

        click.echo("\n✅ Inbox processing complete:")
        click.echo(f"  Files found: {stats.files_found}")
        click.echo(f"  Files processed: {stats.files_processed}")
        if stats.files_skipped > 0:
            click.echo(f"  Files skipped: {stats.files_skipped}")
        click.echo(f"  Years updated: {stats.years_updated}")
        if stats.errors > 0:
            click.echo(f"  ⚠️  Errors: {stats.errors}")
        click.echo(f"  Duration: {stats.duration():.2f}s")

    except Exception as e:
        handle_cli_error(ctx, e, "inbox")


@cli.command()
@click.option(
    "-i",
    "--input",
    type=click.Path(),
    default=str(TXT_DIR),
    help="Input directory with formatted text files",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=str(MD_DIR),
    help="Output directory for Markdown files",
)
@click.option("-f", "--force", is_flag=True, help="Force overwrite existing files")
@click.pass_context
def convert(ctx: click.Context, input: str, output: str, force: bool) -> None:
    """Convert formatted text to Markdown entries."""
    logger: PalimpsestLogger = ctx.obj["logger"]

    click.echo("📝 Converting text to Markdown...")

    try:
        stats = None
        input_path = Path(input)
        if input_path.is_dir():
            stats = convert_directory(
                input_dir=input_path,
                output_dir=Path(output),
                force_overwrite=force,
                logger=logger,
            )

        if input_path.is_file():
            stats = convert_file(
                input_path=input_path,
                output_dir=Path(output),
                force_overwrite=force,
                logger=logger,
            )

        if stats:
            click.echo("\n✅ Conversion complete:")
            click.echo(f"  Files processed: {stats.files_processed}")
            click.echo(f"  Entries created: {stats.entries_created}")
            click.echo(f"  Duration: {stats.duration():.2f}s")

    except Exception as e:
        handle_cli_error(
            ctx,
            e,
            "convert",
            additional_context={"input": input, "output": output},
        )


@cli.command()
@click.option(
    "-i",
    "--input",
    type=click.Path(),
    default=str(MD_DIR),
    help="Input directory with Markdown files",
)
@click.option("-f", "--force", is_flag=True, help="Force update all entries")
@click.pass_context
def sync_db(ctx: click.Context, input: str, force: bool) -> None:
    """Synchronize database with Markdown metadata."""
    logger: PalimpsestLogger = ctx.obj["logger"]

    click.echo("🔄 Syncing database from Markdown...")

    try:
        db = PalimpsestDB(
            db_path=DB_PATH,
            alembic_dir=ALEMBIC_DIR,
            log_dir=LOG_DIR,
            backup_dir=BACKUP_DIR,
            enable_auto_backup=True,
        )

        stats = process_directory(
            input_dir=Path(input), db=db, force_update=force, logger=logger
        )

        click.echo("\n✅ Database sync complete:")
        click.echo(f"  Files processed: {stats.files_processed}")
        click.echo(f"  Entries created: {stats.entries_created}")
        click.echo(f"  Entries updated: {stats.entries_updated}")
        click.echo(f"  Duration: {stats.duration():.2f}s")

    except Exception as e:
        handle_cli_error(
            ctx,
            e,
            "sync_db",
            additional_context={"input": input},
        )


@cli.command()
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=str(MD_DIR),
    help="Output directory for Markdown files",
)
@click.option("-f", "--force", is_flag=True, help="Force overwrite existing files")
@click.pass_context
def export_db(ctx: click.Context, output: str, force: bool) -> None:
    """Export database to Markdown files."""
    logger: PalimpsestLogger = ctx.obj["logger"]

    click.echo("📤 Exporting database to Markdown...")

    try:
        db = PalimpsestDB(
            db_path=DB_PATH,
            alembic_dir=ALEMBIC_DIR,
            log_dir=LOG_DIR,
            backup_dir=BACKUP_DIR,
            enable_auto_backup=False,
        )

        with db.session_scope() as session:
            stats = db.export_manager.export_hierarchical(
                session,
                export_entry_to_markdown,
                threshold=500,
                output_dir=Path(output),
                force_overwrite=force,
                preserve_body=True,
                logger=logger,
            )

        click.echo("\n✅ Export complete:")
        click.echo(f"  Total entries: {stats['total_entries']}")
        click.echo(f"  Processed: {stats['processed']}")
        if stats.get("errors", 0) > 0:
            click.echo(f"  Errors: {stats['errors']}")
        click.echo(f"  Duration: {stats['duration']:.2f}s")

    except Exception as e:
        handle_cli_error(
            ctx,
            e,
            "export_db",
            additional_context={"output": output},
        )


@cli.command()
@click.argument("year")
@click.option(
    "-i",
    "--input",
    type=click.Path(),
    default=str(MD_DIR),
    help="Input directory with Markdown files",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=str(PDF_DIR),
    help="Output directory for PDFs",
)
@click.option("-f", "--force", is_flag=True, help="Force overwrite existing PDFs")
@click.pass_context
def build_pdf(
    ctx: click.Context, year: str, input: str, output: str, force: bool
) -> None:
    """Build clean and notes PDFs for a year."""
    logger: PalimpsestLogger = ctx.obj["logger"]

    click.echo(f"📚 Building PDFs for {year}...")

    try:
        builder = PdfBuilder(
            year=year,
            md_dir=Path(input),
            pdf_dir=Path(output),
            preamble=TEX_DIR / "preamble.tex",
            preamble_notes=TEX_DIR / "preamble_notes.tex",
            force_overwrite=force,
            logger=logger,
        )

        stats = builder.build()

        click.echo("\n✅ PDF build complete:")
        click.echo(f"  Markdown entries: {stats.files_processed}")
        click.echo(f"  PDFs created: {stats.pdfs_created}")
        click.echo(f"  Duration: {stats.duration():.2f}s")

    except Exception as e:
        handle_cli_error(
            ctx,
            e,
            "build_pdf",
            additional_context={"year": year},
        )


@cli.command()
@click.option("--suffix", default=None, help="Optional backup suffix")
@click.pass_context
def backup_data(ctx: click.Context, suffix: Optional[str]) -> None:
    """Create full compressed backup of entire data directory."""
    logger: PalimpsestLogger = ctx.obj["logger"]

    click.echo("📦 Creating full data backup...")
    click.echo("   (This may take a while for large archives)")

    try:
        backup_mgr = BackupManager(
            db_path=DB_PATH,
            backup_dir=BACKUP_DIR,
            data_dir=DATA_DIR,
            logger=logger,
        )

        backup_path = backup_mgr.create_full_backup(suffix=suffix)
        backup_size = backup_path.stat().st_size
        backup_size_mb = backup_size / (1024 * 1024)

        click.echo("\n✅ Full backup created:")
        click.echo(f"  Location: {backup_path}")
        click.echo(f"  Size: {backup_size_mb:.2f} MB ({backup_size:,} bytes)")
        click.echo("\n💡 Backup saved outside git repository")

    except BackupError as e:
        handle_cli_error(ctx, e, "build_pdf")


@cli.command()
@click.pass_context
def backup_list(ctx: click.Context) -> None:
    """List all available full data backups."""
    logger: PalimpsestLogger = ctx.obj["logger"]

    try:
        backup_mgr = BackupManager(
            db_path=DB_PATH,
            backup_dir=BACKUP_DIR,
            data_dir=DATA_DIR,
            logger=logger,
        )

        if (
            not hasattr(backup_mgr, "full_backup_dir")
            or not backup_mgr.full_backup_dir.exists()
        ):
            click.echo("📦 No full backups directory found")
            return

        backups = sorted(backup_mgr.full_backup_dir.glob("*.tar.gz"))

        if not backups:
            click.echo("📦 No full backups found")
            return

        click.echo("\n📦 Full Data Backups")
        click.echo("=" * 70)

        for backup in backups:
            stat = backup.stat()
            size_mb = stat.st_size / (1024 * 1024)
            created = datetime.fromtimestamp(stat.st_mtime)
            age_days = (datetime.now() - created).days

            click.echo(f"\n  • {backup.name}")
            click.echo(f"    Created: {created.strftime('%Y-%m-%d %H:%M:%S')}")
            click.echo(f"    Size: {size_mb:.2f} MB ({stat.st_size:,} bytes)")
            click.echo(f"    Age: {age_days} days")

        click.echo(f"\nTotal backups: {len(backups)}")
        click.echo(f"Location: {backup_mgr.full_backup_dir}")

    except Exception as e:
        handle_cli_error(ctx, e, "backup_list")


@cli.command()
@click.option("--year", help="Specific year to process (optional)")
@click.option("--skip-inbox", is_flag=True, help="Skip inbox processing")
@click.option("--skip-pdf", is_flag=True, help="Skip PDF generation")
@click.option("--backup", is_flag=True, help="Create full data backup after completion")
@click.confirmation_option(prompt="Run complete pipeline?")
@click.pass_context
def run_all(
    ctx: click.Context,
    year: Optional[str],
    skip_inbox: bool,
    skip_pdf: bool,
    backup: bool,
) -> None:
    """Run the complete processing pipeline end-to-end."""
    click.echo("🚀 Starting complete pipeline...\n")

    start_time = datetime.now()

    try:
        # Step 1: Process inbox
        if not skip_inbox:
            click.echo("=" * 60)
            ctx.invoke(inbox)
            click.echo()

        # Step 2: Convert to Markdown
        click.echo("=" * 60)
        ctx.invoke(convert, force=False)
        click.echo()

        # Step 3: Sync database
        click.echo("=" * 60)
        ctx.invoke(sync_db, force=False)
        click.echo()

        # Step 4: Build PDFs (if year specified)
        if not skip_pdf and year:
            click.echo("=" * 60)
            ctx.invoke(build_pdf, year=year, force=False)
            click.echo()

        # Step 5: Full backup (if requested)
        if backup:
            click.echo("=" * 60)
            ctx.invoke(backup_data, suffix="pipeline")
            click.echo()

        duration = (datetime.now() - start_time).total_seconds()

        click.echo("=" * 60)
        click.echo(f"\n✅ Pipeline complete! ({duration:.2f}s)")

    except Exception as e:
        handle_cli_error(ctx, e, "run_all")


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show pipeline status and statistics."""
    logger: PalimpsestLogger = ctx.obj["logger"]
    click.echo("📊 Pipeline Status\n")

    # Check directories
    click.echo("Directories:")
    for name, path in [
        ("Inbox", INBOX_DIR),
        ("Text", TXT_DIR),
        ("Markdown", MD_DIR),
        ("PDF", PDF_DIR),
    ]:
        exists = "✓" if path.exists() else "✗"
        click.echo(f"  {exists} {name}: {path}")

    click.echo()

    # Database stats
    try:
        db = PalimpsestDB(
            db_path=DB_PATH,
            alembic_dir=ALEMBIC_DIR,
            log_dir=LOG_DIR,
            backup_dir=BACKUP_DIR,
            enable_auto_backup=False,
        )

        with db.session_scope() as session:
            analytics = QueryAnalytics(logger)
            stats = analytics.get_database_stats(session)

        click.echo("Database:")
        click.echo(f"  Entries: {stats.get('entries', 0)}")
        click.echo(f"  People: {stats.get('people', 0)}")
        click.echo(f"  Locations: {stats.get('locations', 0)}")
        click.echo(f"  Total words: {stats.get('total_words', 0):,}")

    except Exception as e:
        handle_cli_error(ctx, e, "status")


@cli.command()
def validate() -> None:
    """Validate pipeline integrity."""

    click.echo("🔍 Validating pipeline...\n")

    issues = []

    # Check required directories
    for name, path in [
        ("Inbox", INBOX_DIR),
        ("Markdown", MD_DIR),
    ]:
        if not path.exists():
            issues.append(f"Missing directory: {name} ({path})")

    # Check database
    if not DB_PATH.exists():
        issues.append(f"Database not found: {DB_PATH}")

    # Check preambles
    for name, path in [
        ("Clean preamble", TEX_DIR / "preamble.tex"),
        ("Notes preamble", TEX_DIR / "preamble_notes.tex"),
    ]:
        if not path.exists():
            issues.append(f"Missing preamble: {name} ({path})")

    if issues:
        click.echo("⚠️  Issues found:")
        for issue in issues:
            click.echo(f"  • {issue}")
        sys.exit(1)
    else:
        click.echo("✅ Pipeline validation passed!")


if __name__ == "__main__":
    cli(obj={})
