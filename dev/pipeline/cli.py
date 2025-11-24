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
    ARCHIVE_DIR,
    TXT_DIR,
    MD_DIR,
    PDF_DIR,
    LOG_DIR,
    DB_PATH,
    ALEMBIC_DIR,
    BACKUP_DIR,
    TEX_DIR,
    DATA_DIR,
    WIKI_DIR,
)
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.core.backup_manager import BackupManager
from dev.core.exceptions import BackupError
from dev.core.cli import setup_logger
from dev.database.manager import PalimpsestDB

# from dev.database.models import Entry
from dev.database.query_analytics import QueryAnalytics

from .src2txt import process_inbox
from .txt2md import convert_directory, convert_file
from .yaml2sql import process_directory
from .sql2yaml import export_entry_to_markdown
from .md2pdf import build_pdf


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
    ctx.obj["logger"] = setup_logger(Path(log_dir), "pipeline")


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
    """
    Process inbox: format and organize raw 750words exports.

    Implementation Logic:
    ---------------------
    This command is the FIRST STEP in the processing pipeline. It takes raw
    unformatted text exports from 750words.com and transforms them into
    organized, cleaned monthly text files.

    Processing Flow:
    1. Scans inbox directory for raw .txt exports
    2. Validates file naming format (expects 750words export format)
    3. Groups files by year based on content dates
    4. Invokes external format script to clean/normalize content
    5. Organizes output into year-based directory structure
    6. Archives original files (preserves raw exports)

    File Organization:
    - Input:  inbox/*.txt (raw 750words exports, any naming)
    - Output: txt/YYYY/YYYY-MM.txt (formatted, organized by year)
    - Archive: archive/*.txt (original files preserved)

    Error Handling:
    - Individual file failures don't stop batch processing
    - Validation errors logged with context
    - Statistics track errors for post-processing review

    Side Effects:
    - Creates year-based directory structure in output
    - Moves processed files to archive
    - Modifies filesystem state (output and archive dirs)

    Dependencies:
    - TxtBuilder handles actual processing logic
    - External format script for content cleaning (subprocess call)
    - Logger tracks all operations for debugging
    """
    logger: PalimpsestLogger = ctx.obj["logger"]

    click.echo("📥 Processing inbox...")

    try:
        # Call src2txt programmatic API
        stats = process_inbox(
            inbox_dir=Path(inbox),
            output_dir=Path(output),
            archive_dir=ARCHIVE_DIR,
            logger=logger,
        )

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
@click.option("--dry-run", is_flag=True, help="Preview changes without modifying files")
@click.pass_context
def convert(ctx: click.Context, input: str, output: str, force: bool, dry_run: bool) -> None:
    """
    Convert formatted text to Markdown entries.

    Implementation Logic:
    ---------------------
    This command is the SECOND STEP in the pipeline. It transforms formatted
    monthly text files into individual daily Markdown files with minimal
    YAML frontmatter (date, word_count, reading_time only).

    Processing Flow:
    1. Reads monthly text file (YYYY-MM.txt format)
    2. Parses content to identify daily entry boundaries
    3. Extracts entry date from content markers
    4. Computes metadata (word count, reading time)
    5. Generates minimal YAML frontmatter
    6. Writes individual daily .md files (YYYY-MM-DD.md)

    Parsing Strategy:
    - Uses date markers to split monthly file into daily entries
    - Handles various date format variations
    - Preserves original text content without modification
    - Computes metadata from content analysis

    File Organization:
    - Input:  txt/YYYY/YYYY-MM.txt (monthly files)
    - Output: md/YYYY/YYYY-MM-DD.md (daily files)

    YAML Frontmatter Generated:
    - date: Entry date in YYYY-MM-DD format
    - word_count: Computed word count
    - reading_time: Estimated reading time (minutes)

    Note: Complex metadata (people, locations, events) is NOT handled here.
    That's deferred to yaml2sql pipeline for human-edited metadata.

    Error Handling:
    - Accepts both file and directory paths
    - Skips existing files unless --force specified
    - Individual entry failures logged but don't stop batch
    - Statistics track created/skipped entries

    Side Effects:
    - Creates year-based directory structure
    - Writes new .md files (or overwrites if --force)
    - No database modifications (pure file conversion)

    Dependencies:
    - txt2md.convert_directory() for batch processing
    - txt2md.convert_file() for single file processing
    - TxtEntry dataclass for parsing logic
    """
    logger: PalimpsestLogger = ctx.obj["logger"]

    if dry_run:
        click.echo("📝 Converting text to Markdown (DRY RUN - no files will be modified)...")
        click.echo()
        input_path = Path(input)

        # Preview what would be processed
        if input_path.is_dir():
            txt_files = sorted(input_path.rglob("*.txt"))
            click.echo(f"Would process {len(txt_files)} .txt files:")
            for txt_file in txt_files:
                click.echo(f"  • {txt_file.relative_to(input_path)}")
        elif input_path.is_file():
            click.echo(f"Would process 1 file:")
            click.echo(f"  • {input_path.name}")

        click.echo(f"\nOutput directory: {output}")
        click.echo(f"Force overwrite: {force}")
        click.echo("\n💡 Run without --dry-run to execute conversion")
        return

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


@cli.command("sync-db")
@click.option(
    "-i",
    "--input",
    type=click.Path(),
    default=str(MD_DIR),
    help="Input directory with Markdown files",
)
@click.option("-f", "--force", is_flag=True, help="Force update all entries")
@click.option("--dry-run", is_flag=True, help="Preview changes without modifying database")
@click.pass_context
def sync_db(ctx: click.Context, input: str, force: bool, dry_run: bool) -> None:
    """
    Synchronize database with Markdown metadata.

    Implementation Logic:
    ---------------------
    This command is the THIRD STEP in the pipeline. It reads human-edited
    Markdown files with rich YAML frontmatter and populates the SQLite
    database with structured, queryable data.

    Processing Flow:
    1. Scans directory for .md files
    2. Reads YAML frontmatter from each file
    3. Parses complex metadata (people, locations, events, etc.)
    4. Creates or updates Entry records in database
    5. Manages relationships (many-to-many tables)
    6. Updates file hash for change detection

    Change Detection Strategy:
    - Computes MD5 hash of file content
    - Stores hash in Entry.file_hash field
    - Skips processing if hash unchanged (unless --force)
    - This enables incremental updates (only process changed files)

    Relationship Management:
    - People: Parses names with hyphen/alias support
    - Locations: Handles nested city→location hierarchies
    - Events: Links entries to event identifiers
    - Tags: Maintains many-to-many tag associations
    - References: Stores external citations with sources
    - Poems: Tracks poem versions with revision history
    - Manuscript: Manages editorial metadata

    Transaction Handling:
    - Each file processed in separate transaction
    - Individual failures rolled back automatically
    - Database remains consistent even if some files fail
    - Statistics track successes/failures for review

    Database Initialization:
    - Auto-backup enabled (creates backup before major operations)
    - Uses PalimpsestDB manager for connection pooling
    - Alembic tracks schema migrations
    - SQLite WAL mode for concurrent access

    Error Handling:
    - Validation errors logged with file context
    - Parsing failures don't stop batch processing
    - Orphaned records cleaned up automatically
    - Statistics report errors for manual review

    Side Effects:
    - Creates/updates database records
    - Modifies many-to-many relationship tables
    - Updates file_hash fields for change tracking
    - May create backup files (if auto-backup enabled)

    Dependencies:
    - yaml2sql.process_directory() handles file processing
    - MdEntry dataclass for YAML parsing
    - PalimpsestDB for database operations
    - SQLAlchemy ORM for relationship management
    """
    logger: PalimpsestLogger = ctx.obj["logger"]

    if dry_run:
        click.echo("🔄 Syncing database from Markdown (DRY RUN - no database changes)...")
        click.echo()
        input_path = Path(input)

        # Preview what would be synced
        md_files = sorted(input_path.rglob("*.md"))
        click.echo(f"Would process {len(md_files)} .md files:")

        # Show sample of files with progress bar
        with click.progressbar(
            md_files[:10] if len(md_files) > 10 else md_files,
            label="Scanning files",
            show_pos=True
        ) as files:
            for md_file in files:
                pass  # Just for progress visualization

        if len(md_files) > 10:
            click.echo(f"  ... and {len(md_files) - 10} more files")

        click.echo(f"\nDatabase: {DB_PATH}")
        click.echo(f"Force update: {force}")
        click.echo(f"Auto-backup: Enabled")
        click.echo("\n💡 Run without --dry-run to execute database sync")
        return

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


@cli.command("export-db")
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=str(MD_DIR),
    help="Output directory for Markdown files",
)
@click.option("-f", "--force", is_flag=True, help="Force overwrite existing files")
@click.option("--dry-run", is_flag=True, help="Preview changes without writing files")
@click.pass_context
def export_db(ctx: click.Context, output: str, force: bool, dry_run: bool) -> None:
    """
    Export database to Markdown files.

    Implementation Logic:
    ---------------------
    This command is the INVERSE of sync-db. It reads structured database
    records and generates human-editable Markdown files with complete
    YAML frontmatter. Used for database→file synchronization.

    Processing Flow:
    1. Queries all Entry records from database
    2. Loads relationships (people, locations, events, etc.)
    3. Converts database records to MdEntry dataclass
    4. Generates YAML frontmatter from metadata
    5. Preserves existing body content (or regenerates)
    6. Writes .md files with complete metadata

    Content Preservation Strategy:
    - Reads existing .md file if present
    - Extracts body content (everything after frontmatter)
    - Regenerates YAML frontmatter from database
    - Combines new frontmatter with preserved body
    - This allows database updates while preserving text

    YAML Generation:
    - All relationship data exported to YAML
    - People names formatted with hyphens/aliases
    - Locations organized by city hierarchy
    - References include sources and context
    - Manuscript metadata conditionally included
    - Dates formatted consistently (YYYY-MM-DD)

    Use Cases:
    - Restore .md files from database backup
    - Propagate database edits back to files
    - Generate initial .md files from imported data
    - Synchronize bidirectional changes

    File Handling:
    - Skips existing files unless --force specified
    - Creates year-based directory structure
    - Maintains file organization (md/YYYY/YYYY-MM-DD.md)

    Error Handling:
    - Individual export failures logged
    - Statistics track created/updated/skipped files
    - Database remains unchanged (read-only operation)

    Side Effects:
    - Writes/overwrites .md files
    - Creates year directories if needed
    - No database modifications (export-only)

    Dependencies:
    - sql2yaml.export_entry_to_markdown() for conversion
    - MdEntry dataclass for YAML generation
    - PalimpsestDB for database queries
    - YAML library for frontmatter serialization
    """
    logger: PalimpsestLogger = ctx.obj["logger"]

    if dry_run:
        click.echo("📤 Exporting database to Markdown (DRY RUN - no files will be written)...")
        click.echo()

        # Query database to show what would be exported
        try:
            db = PalimpsestDB(
                db_path=DB_PATH,
                alembic_dir=ALEMBIC_DIR,
                log_dir=LOG_DIR,
                backup_dir=BACKUP_DIR,
                enable_auto_backup=False,
            )

            with db.session_scope() as session:
                # Get count of entries
                from dev.database.models import Entry
                entry_count = session.query(Entry).count()

                click.echo(f"Would export {entry_count} database entries")
                click.echo(f"Output directory: {output}")
                click.echo(f"Force overwrite: {force}")
                click.echo(f"Preserve body content: True")

                # Show sample entries with progress bar
                sample_entries = session.query(Entry).order_by(Entry.date.desc()).limit(5).all()
                click.echo("\nSample entries that would be exported:")
                for entry in sample_entries:
                    year = entry.date.year
                    filename = f"{entry.date.isoformat()}.md"
                    click.echo(f"  • {output}/{year}/{filename}")

                click.echo(f"\n  ... and {max(0, entry_count - 5)} more entries")
                click.echo("\n💡 Run without --dry-run to execute export")
                return

        except Exception as e:
            handle_cli_error(ctx, e, "export_db_dry_run")
            return

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


@cli.command("build-pdf")
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
@click.option("--debug", is_flag=True, help="Keep temp files on error for debugging")
@click.pass_context
def build_pdf(
    ctx: click.Context,
    year: str,
    input: str,
    output: str,
    force: bool,
    debug: bool,
) -> None:
    """
    Build clean and notes PDFs for a year.

    Implementation Logic:
    ---------------------
    This command is the FINAL STEP in the pipeline. It generates professional
    typeset PDF documents from Markdown entries using Pandoc + LaTeX. Creates
    two versions: clean (reading) and notes (annotation with line numbers).

    Processing Flow:
    1. Collects all .md files for specified year
    2. Sorts entries chronologically
    3. Concatenates into single Markdown document
    4. Applies LaTeX preamble for typography
    5. Invokes Pandoc to convert MD → LaTeX → PDF
    6. Generates two PDF variants (clean and notes)

    Pandoc Integration:
    - Uses Pandoc as external subprocess
    - Passes custom LaTeX preambles for formatting
    - preamble.tex: Clean reading version
    - preamble_notes.tex: Annotation version with line numbers
    - Pandoc handles: citations, cross-refs, typography

    Temporary File Management:
    - Creates temp directory for intermediate files
    - Concatenated Markdown → temp/journal_YYYY.md
    - LaTeX intermediate → temp/journal_YYYY.tex
    - Cleanup automatic on success
    - --debug flag preserves temp files for troubleshooting

    Output Files:
    - journal_YYYY_clean.pdf: Reading/archival version
    - journal_YYYY_notes.pdf: Annotation version (line numbers)
    - Location: pdf/YYYY/

    LaTeX Typography Features:
    - Professional typography (TeX Gyre fonts)
    - Page margins optimized for reading
    - Line numbers in notes version
    - Headers/footers with metadata
    - Smart hyphenation

    Error Handling:
    - Pandoc failures captured with stderr output
    - LaTeX errors logged with context
    - Temporary files preserved on error if --debug
    - Partial builds cleaned up automatically

    Performance Considerations:
    - Large years (>365 entries) may take several minutes
    - Pandoc is CPU-intensive (LaTeX compilation)
    - Memory usage scales with year size
    - Progress feedback via logger

    Side Effects:
    - Creates PDF files in output directory
    - Creates/deletes temporary directory
    - Spawns Pandoc subprocess (external dependency)
    - May consume significant CPU/memory

    Dependencies:
    - Pandoc installed and in PATH (REQUIRED)
    - LaTeX distribution (texlive-full recommended)
    - preamble.tex and preamble_notes.tex files
    - PdfBuilder handles actual compilation
    """
    logger: PalimpsestLogger = ctx.obj["logger"]

    click.echo(f"📚 Building PDFs for {year}...")

    try:
        # Call md2pdf programmatic API
        stats = build_pdf(
            year=year,
            md_dir=Path(input),
            pdf_dir=Path(output),
            preamble=TEX_DIR / "preamble.tex",
            preamble_notes=TEX_DIR / "preamble_notes.tex",
            force_overwrite=force,
            keep_temp_on_error=debug,
            logger=logger,
        )

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


@cli.command("backup-full")
@click.option("--suffix", default=None, help="Optional backup suffix")
@click.pass_context
def backup_full(ctx: click.Context, suffix: Optional[str]) -> None:
    """
    Create full compressed backup of entire data directory.

    Implementation Logic:
    ---------------------
    Creates a timestamped, compressed archive of the complete data directory
    (journal/). Includes all files: md/, pdf/, txt/, database, etc.

    Backup Strategy:
    1. Creates temp staging directory
    2. Recursively copies entire data directory
    3. Compresses to tar.gz format
    4. Adds timestamp to filename (YYYY-MM-DD_HH-MM-SS)
    5. Saves to backup directory (outside git repo)
    6. Cleans up staging directory

    Filename Format:
    - full_backup_YYYY-MM-DD_HH-MM-SS.tar.gz
    - With suffix: full_backup_YYYY-MM-DD_HH-MM-SS_suffix.tar.gz

    Compression:
    - Uses gzip compression (level 6, balance size/speed)
    - Typical compression ratio: 40-60% for text files
    - Large archives may take several minutes

    Backup Location:
    - Saved outside journal/ directory
    - Not tracked by git (.gitignore)
    - Recommended: sync to external storage

    Use Cases:
    - Before major pipeline operations
    - Before database schema migrations
    - Regular archival (cron job)
    - Pre-deployment snapshots

    Error Handling:
    - Disk space checked before starting
    - Partial backups cleaned up on failure
    - Backup integrity verified (file count)

    Side Effects:
    - Creates large compressed file (GB range possible)
    - Temporary disk space usage during compression
    - May take significant time for large datasets

    Dependencies:
    - BackupManager handles compression
    - tar/gzip utilities (standard POSIX)
    """
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
        handle_cli_error(ctx, e, "backup_full")


@cli.command("backup-list-full")
@click.pass_context
def backup_list_full(ctx: click.Context) -> None:
    """
    List all available full data backups.

    Implementation Logic:
    ---------------------
    Scans the backup directory for full data backups and displays metadata
    for each backup file (creation date, size, age).

    Processing Flow:
    1. Checks if backup directory exists
    2. Scans for .tar.gz files
    3. Sorts by creation time
    4. Extracts metadata from filesystem
    5. Formats and displays results

    Metadata Displayed:
    - Filename: full_backup_YYYY-MM-DD_HH-MM-SS[_suffix].tar.gz
    - Creation timestamp (from file modification time)
    - File size (in MB and bytes)
    - Age (days since creation)
    - Total count and directory location

    Output Format:
    Provides human-readable list with:
    - Clear section headers
    - Indented details for each backup
    - Summary totals
    - Directory path for manual inspection

    Use Cases:
    - Before restore operations (choose backup)
    - Cleanup old backups (identify candidates)
    - Verify backup schedule compliance
    - Monitor backup storage usage

    Side Effects:
    - None (read-only operation)
    - No file modifications

    Dependencies:
    - BackupManager for directory path
    - Filesystem access for metadata
    """
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
        handle_cli_error(ctx, e, "backup_list_full")


@cli.command("run-all")
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
    """
    Run the complete processing pipeline end-to-end.

    Implementation Logic:
    ---------------------
    Orchestrates the ENTIRE journal processing pipeline in the correct order.
    This is the master command that runs all steps sequentially, ensuring
    data flows correctly from raw exports to final PDFs.

    Pipeline Sequence:
    ------------------
    1. INBOX (optional, --skip-inbox to skip)
       - Processes raw 750words exports
       - Formats and organizes into monthly text files
       - Archives original files
       - Output: txt/YYYY/YYYY-MM.txt

    2. CONVERT (always runs)
       - Transforms monthly text to daily Markdown
       - Generates minimal YAML frontmatter
       - Computes word counts and reading times
       - Output: md/YYYY/YYYY-MM-DD.md

    3. SYNC-DB (always runs)
       - Reads human-edited Markdown metadata
       - Populates database with structured data
       - Manages complex relationships
       - Output: SQLite database updated

    4. BUILD-PDF (optional, requires --year)
       - Generates yearly journal PDFs
       - Creates clean and notes versions
       - Uses Pandoc + LaTeX for typesetting
       - Output: pdf/YYYY/journal_YYYY_{clean,notes}.pdf
       - Skip with --skip-pdf flag

    5. BACKUP (optional, requires --backup flag)
       - Creates full compressed data backup
       - Includes all files and database
       - Timestamped archive outside git
       - Output: backups/full_backup_TIMESTAMP_pipeline.tar.gz

    Invocation Strategy:
    - Uses ctx.invoke() to call other commands programmatically
    - Each command runs in same Click context
    - Shared logger across all steps
    - Each step logs independently

    Error Handling:
    - Pipeline stops on first error
    - No partial rollback (completed steps remain)
    - Each command has own error handling
    - Duration tracked even on failure

    Confirmation Required:
    - Click confirmation prompt before execution
    - Prevents accidental full pipeline runs
    - Can be automated with --yes flag (future)

    Progress Feedback:
    - Visual separators between steps (=== 60 chars)
    - Each command echoes its progress
    - Total duration displayed at end
    - Celebration message on success

    Use Cases:
    - Initial data import (process all files)
    - Regular updates (periodic cron job)
    - After manual editing session
    - Pre-deployment data refresh

    Performance Considerations:
    - Full pipeline can take 10+ minutes for large datasets
    - Inbox processing: ~1-2 minutes
    - Convert: ~2-3 minutes
    - Sync-db: ~3-5 minutes (database operations)
    - Build-pdf: ~5-10 minutes (Pandoc/LaTeX)
    - Backup: ~1-2 minutes (compression)

    Side Effects:
    - Modifies entire data directory structure
    - Updates database comprehensively
    - Creates PDF files
    - May create backup archive
    - High CPU/memory usage during PDF generation

    Dependencies:
    - All pipeline commands must be functional
    - External dependencies: Pandoc, LaTeX
    - Sufficient disk space for outputs
    - Database must be initialized
    """
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
        ctx.invoke(sync_db, input=str(MD_DIR), force=False)
        click.echo()

        # Step 4: Build PDFs (if year specified)
        if not skip_pdf and year:
            click.echo("=" * 60)
            ctx.invoke(build_pdf, year=year, input=str(MD_DIR), output=str(PDF_DIR), force=False, debug=False)
            click.echo()

        # Step 5: Full backup (if requested)
        if backup:
            click.echo("=" * 60)
            ctx.invoke(backup_full, suffix="pipeline")
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


# ===== WIKI EXPORT/IMPORT COMMANDS =====


@cli.command("export-wiki")
@click.argument(
    "entity_type",
    type=click.Choice([
        "entries", "locations", "cities", "events", "timeline", "index", "stats", "analysis",
        "people", "themes", "tags", "poems", "references", "all"
    ]),
)
@click.option("-f", "--force", is_flag=True, help="Force regenerate all files")
@click.option(
    "--wiki-dir",
    type=click.Path(),
    default=str(WIKI_DIR),
    help="Vimwiki root directory",
)
@click.pass_context
def export_wiki(ctx: click.Context, entity_type: str, force: bool, wiki_dir: str) -> None:
    """Export database entities to vimwiki pages."""
    from dev.pipeline.sql2wiki import (
        export_index,
        export_stats,
        export_timeline,
        export_analysis_report,
        get_exporter,
    )

    logger: PalimpsestLogger = ctx.obj["logger"]
    wiki_path = Path(wiki_dir)
    journal_dir = MD_DIR

    db = PalimpsestDB(
        db_path=DB_PATH,
        alembic_dir=ALEMBIC_DIR,
        log_dir=LOG_DIR,
        backup_dir=BACKUP_DIR,
        enable_auto_backup=False,
    )

    try:
        if entity_type == "index":
            click.echo(f"📤 Exporting wiki homepage to {wiki_path}/index.md")
            status = export_index(db, wiki_path, journal_dir, force, logger)
            click.echo(f"\n✅ Index {status}")
        elif entity_type == "stats":
            click.echo(f"📤 Exporting statistics dashboard to {wiki_path}/stats.md")
            status = export_stats(db, wiki_path, journal_dir, force, logger)
            click.echo(f"\n✅ Statistics {status}")
        elif entity_type == "timeline":
            click.echo(f"📤 Exporting timeline to {wiki_path}/timeline.md")
            status = export_timeline(db, wiki_path, journal_dir, force, logger)
            click.echo(f"\n✅ Timeline {status}")
        elif entity_type == "analysis":
            click.echo(f"📤 Exporting analysis report to {wiki_path}/analysis.md")
            status = export_analysis_report(db, wiki_path, journal_dir, force, logger)
            click.echo(f"\n✅ Analysis report {status}")
        elif entity_type == "all":
            click.echo(f"📤 Exporting all entities to {wiki_path}/")
            all_stats = []
            for entity_name in ["entries", "locations", "cities", "events", "people", "themes", "tags", "poems", "references"]:
                exporter = get_exporter(entity_name)
                stats = exporter.export_all(db, wiki_path, journal_dir, force, logger)
                all_stats.append(stats)

            export_index(db, wiki_path, journal_dir, force, logger)
            export_stats(db, wiki_path, journal_dir, force, logger)
            export_timeline(db, wiki_path, journal_dir, force, logger)
            export_analysis_report(db, wiki_path, journal_dir, force, logger)

            total_files = sum(s.files_processed for s in all_stats)
            total_created = sum(s.entries_created for s in all_stats)
            total_updated = sum(s.entries_updated for s in all_stats)
            total_skipped = sum(s.entries_skipped for s in all_stats)
            total_errors = sum(s.errors for s in all_stats)
            total_duration = sum(s.duration() for s in all_stats)

            click.echo("\n✅ All exports complete:")
            click.echo(f"  Total files: {total_files}")
            click.echo(f"  Created: {total_created}")
            click.echo(f"  Updated: {total_updated}")
            click.echo(f"  Skipped: {total_skipped}")
            if total_errors > 0:
                click.echo(f"  ⚠️  Errors: {total_errors}")
            click.echo(f"  Duration: {total_duration:.2f}s")
        else:
            exporter = get_exporter(entity_type)
            click.echo(f"📤 Exporting {exporter.config.plural} to {wiki_path}/{exporter.config.output_subdir}/")
            stats = exporter.export_all(db, wiki_path, journal_dir, force, logger)

            click.echo(f"\n✅ {exporter.config.plural.title()} export complete:")
            click.echo(f"  Files processed: {stats.files_processed}")
            click.echo(f"  Created: {stats.entries_created}")
            click.echo(f"  Updated: {stats.entries_updated}")
            click.echo(f"  Skipped: {stats.entries_skipped}")
            if stats.errors > 0:
                click.echo(f"  ⚠️  Errors: {stats.errors}")
            click.echo(f"  Duration: {stats.duration():.2f}s")

    except Exception as e:
        handle_cli_error(ctx, e, "export_wiki", {"entity_type": entity_type})


@cli.command("import-wiki")
@click.argument(
    "entity_type",
    type=click.Choice([
        "people", "themes", "tags", "entries", "events",
        "manuscript-entries", "manuscript-characters", "manuscript-events",
        "all", "manuscript-all"
    ]),
)
@click.option(
    "--wiki-dir",
    type=click.Path(),
    default=str(WIKI_DIR),
    help="Wiki root directory",
)
@click.pass_context
def import_wiki(ctx: click.Context, entity_type: str, wiki_dir: str) -> None:
    """Import wiki edits back to database."""
    from dev.pipeline.wiki2sql import (
        import_people,
        import_themes,
        import_tags,
        import_entries,
        import_events,
        import_all,
        import_all_manuscript_entries,
        import_all_manuscript_characters,
        import_all_manuscript_events,
        ImportStats,
    )

    logger: PalimpsestLogger = ctx.obj["logger"]
    wiki_path = Path(wiki_dir)

    db = PalimpsestDB(
        db_path=DB_PATH,
        alembic_dir=ALEMBIC_DIR,
        log_dir=LOG_DIR,
        backup_dir=BACKUP_DIR,
        enable_auto_backup=False,
    )

    try:
        click.echo(f"📥 Importing {entity_type} from {wiki_path}/")

        if entity_type == "people":
            stats = import_people(wiki_path, db, logger)
        elif entity_type == "themes":
            stats = import_themes(wiki_path, db, logger)
        elif entity_type == "tags":
            stats = import_tags(wiki_path, db, logger)
        elif entity_type == "entries":
            stats = import_entries(wiki_path, db, logger)
        elif entity_type == "events":
            stats = import_events(wiki_path, db, logger)
        elif entity_type == "manuscript-entries":
            stats = import_all_manuscript_entries(db, wiki_path, logger)
        elif entity_type == "manuscript-characters":
            stats = import_all_manuscript_characters(db, wiki_path, logger)
        elif entity_type == "manuscript-events":
            stats = import_all_manuscript_events(db, wiki_path, logger)
        elif entity_type == "manuscript-all":
            combined_stats = ImportStats()
            for import_func in [
                import_all_manuscript_entries,
                import_all_manuscript_characters,
                import_all_manuscript_events,
            ]:
                s = import_func(db, wiki_path, logger)
                combined_stats.files_processed += s.files_processed
                combined_stats.records_updated += s.records_updated
                combined_stats.records_skipped += s.records_skipped
                combined_stats.errors += s.errors
            stats = combined_stats
        elif entity_type == "all":
            stats = import_all(wiki_path, db, logger)
        else:
            click.echo(f"❌ Unknown entity type: {entity_type}")
            sys.exit(1)

        click.echo(f"\n✅ Import complete:")
        click.echo(f"  Files processed: {stats.files_processed}")
        click.echo(f"  Records updated: {stats.records_updated}")
        click.echo(f"  Records skipped: {stats.records_skipped}")
        if stats.errors > 0:
            click.echo(f"  ⚠️  Errors: {stats.errors}")

    except Exception as e:
        handle_cli_error(ctx, e, "import_wiki", {"entity_type": entity_type})


if __name__ == "__main__":
    cli(obj={})
