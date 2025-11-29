"""
YAML→SQL Pipeline Commands
---------------------------

Commands for syncing YAML/Markdown data into the SQL database.

Commands:
    - inbox: Process inbox files (raw exports → formatted text)
    - convert: Convert text to Markdown (txt → md with metadata)
    - sync-db: Sync Markdown metadata into database (yaml → SQL)

This is the primary data ingestion pathway.
"""
from __future__ import annotations

import click
from pathlib import Path

from dev.core.paths import (
    INBOX_DIR,
    ARCHIVE_DIR,
    TXT_DIR,
    MD_DIR,
    DB_PATH,
    ALEMBIC_DIR,
    LOG_DIR,
    BACKUP_DIR,
)
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.database.manager import PalimpsestDB
from dev.pipeline.src2txt import process_inbox
from dev.pipeline.txt2md import convert_directory, convert_file
from dev.pipeline.yaml2sql import process_directory


@click.command()
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

    This is STEP 1 of the pipeline - transforms raw text exports into
    organized monthly text files.
    """
    logger: PalimpsestLogger = ctx.obj["logger"]

    click.echo("📥 Processing inbox...")

    try:
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


@click.command()
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

    This is STEP 2 of the pipeline - transforms monthly text files into
    individual daily Markdown files with minimal YAML frontmatter.
    """
    logger: PalimpsestLogger = ctx.obj["logger"]

    if dry_run:
        click.echo("📝 Converting text to Markdown (DRY RUN - no files will be modified)...")
        click.echo()
        input_path = Path(input)

        if input_path.is_dir():
            txt_files = sorted(input_path.rglob("*.txt"))
            click.echo(f"Would process {len(txt_files)} .txt files:")
            for txt_file in txt_files:
                click.echo(f"  • {txt_file.relative_to(input_path)}")
        elif input_path.is_file():
            click.echo("Would process 1 file:")
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


@click.command("sync-db")
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

    This is STEP 3 of the pipeline - reads human-edited Markdown files
    with rich YAML frontmatter and populates the database.
    """
    logger: PalimpsestLogger = ctx.obj["logger"]

    if dry_run:
        click.echo("🔄 Syncing database from Markdown (DRY RUN - no database changes)...")
        click.echo()
        input_path = Path(input)

        md_files = sorted(input_path.rglob("*.md"))
        click.echo(f"Would process {len(md_files)} .md files:")

        with click.progressbar(
            md_files[:10] if len(md_files) > 10 else md_files,
            label="Scanning files",
            show_pos=True
        ) as files:
            for _md_file in files:
                pass  # Progress visualization

        if len(md_files) > 10:
            click.echo(f"  ... and {len(md_files) - 10} more files")

        click.echo(f"\nDatabase: {DB_PATH}")
        click.echo(f"Force update: {force}")
        click.echo("Auto-backup: Enabled")
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
