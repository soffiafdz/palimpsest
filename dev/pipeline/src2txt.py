#!/usr/bin/env python3
"""
src2txt.py
-------------------
Process raw 750words exports into formatted text files.

Converts raw journal exports from inbox directory into organized,
formatted monthly text files ready for markdown conversion.

Pipeline position: FIRST STEP
    src2txt → txt2md → yaml2sql → sql2yaml → md2pdf

Features:
- Validates and renames files to standard format
- Groups files by year
- Runs format script to clean content
- Archives processed originals

Usage:
    # Process inbox directory
    python -m dev.pipeline.src2txt process

    # Process with custom paths
    python -m dev.pipeline.src2txt process -i inbox/ -o txt/

    # Validate inbox files
    python -m dev.pipeline.src2txt validate
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import sys
import click
from pathlib import Path
from typing import Optional

# --- Local imports ---
from dev.core.paths import ARCHIVE_DIR, INBOX_DIR, TXT_DIR, LOG_DIR, FORMATTING_SCRIPT
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.core.exceptions import TxtBuildError
from dev.core.cli import setup_logger
from dev.builders.txtbuilder import TxtBuilder, ProcessingStats


# --- Programmatic API ---
def process_inbox(
    inbox_dir: Path,
    output_dir: Path,
    archive_dir: Optional[Path] = None,
    format_script: Optional[Path] = None,
    logger: Optional[PalimpsestLogger] = None,
) -> ProcessingStats:
    """
    Process inbox: format and organize raw 750words exports.

    This is the programmatic API for src2txt processing, used by:
    - The pipeline CLI (python -m dev.pipeline.cli pipeline)
    - The standalone CLI (python -m dev.pipeline.src2txt process)

    Args:
        inbox_dir: Directory containing raw exports
        output_dir: Base output directory for formatted files
        archive_dir: Archive directory (defaults to ARCHIVE_DIR)
        format_script: Format script path (defaults to FORMATTING_SCRIPT)
        logger: Optional logger instance

    Returns:
        ProcessingStats with files_found, files_processed, etc.

    Raises:
        TxtBuildError: If processing fails
    """
    # Apply defaults
    if archive_dir is None:
        archive_dir = ARCHIVE_DIR
    if format_script is None:
        format_script = FORMATTING_SCRIPT

    # Create builder
    builder = TxtBuilder(
        inbox_dir=inbox_dir,
        output_dir=output_dir,
        archive_dir=archive_dir,
        format_script=format_script,
        logger=logger,
    )

    # Execute build
    stats: ProcessingStats = builder.build()

    return stats


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
    """src2txt - Process raw 750words exports to formatted text"""
    ctx.ensure_object(dict)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["verbose"] = verbose
    ctx.obj["logger"] = setup_logger(Path(log_dir), "src2txt")


@cli.command()
@click.option(
    "-i",
    "--inbox",
    type=click.Path(),
    default=str(INBOX_DIR),
    help=f"Inbox directory (default: {INBOX_DIR})",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=str(TXT_DIR),
    help=f"Output directory (default: {TXT_DIR})",
)
@click.option(
    "--archive",
    type=click.Path(),
    default=str(ARCHIVE_DIR),
    help=f"Archive directory (default: {ARCHIVE_DIR})",
)
@click.option(
    "--format-script",
    type=click.Path(exists=True),
    default=None,
    help="Format script path (default: dev/bin/init_format)",
)
@click.pass_context
def process(
    ctx: click.Context,
    inbox: str,
    output: str,
    archive: str,
    format_script: str,
) -> None:
    """Process inbox: format and organize raw exports."""
    logger: PalimpsestLogger = ctx.obj["logger"]

    try:
        inbox_dir = Path(inbox)
        output_dir = Path(output)
        archive_dir = Path(archive) if archive else None
        script_path = Path(format_script) if format_script else None

        click.echo(f"📥 Processing inbox: {inbox_dir}")

        # Call programmatic API
        stats = process_inbox(
            inbox_dir=inbox_dir,
            output_dir=output_dir,
            archive_dir=archive_dir,
            format_script=script_path,
            logger=logger,
        )

        # Report results
        click.echo("\n✅ Inbox processing complete:")
        click.echo(f"  Files found: {stats.files_found}")
        click.echo(f"  Files processed: {stats.files_processed}")
        if stats.files_skipped > 0:
            click.echo(f"  Files skipped: {stats.files_skipped}")
        click.echo(f"  Years updated: {stats.years_updated}")
        if stats.errors > 0:
            click.echo(f"  ⚠️  Errors: {stats.errors}")
        click.echo(f"  Duration: {stats.duration():.2f}s")

    except (TxtBuildError, Exception) as e:
        handle_cli_error(ctx, e, "process", {"inbox": inbox})


@cli.command()
@click.option(
    "-i",
    "--inbox",
    type=click.Path(),
    default=str(INBOX_DIR),
    help=f"Inbox directory (default: {INBOX_DIR})",
)
@click.pass_context
def validate(ctx: click.Context, inbox: str) -> None:
    """Validate inbox files without processing."""
    try:
        inbox_dir = Path(inbox)

        click.echo(f"🔍 Validating inbox: {inbox_dir}")

        if not inbox_dir.exists():
            click.echo(f"❌ Directory not found: {inbox_dir}", err=True)
            sys.exit(1)

        # Find all text files
        txt_files = list(inbox_dir.glob("*.txt"))

        if not txt_files:
            click.echo("⚠️  No .txt files found in inbox")
            return

        click.echo(f"Found {len(txt_files)} files")

        # Use builder's parser
        builder = TxtBuilder(inbox_dir=inbox_dir, output_dir=Path("/tmp"))

        # Validate each file
        valid = []
        invalid = []

        for file_path in txt_files:
            parsed = builder.parse_filename(file_path.name)
            if parsed:
                year, month = parsed
                valid.append((file_path.name, year, month))
            else:
                invalid.append(file_path.name)

        if valid:
            click.echo(f"\n✅ Valid files ({len(valid)}):")
            for filename, year, month in sorted(valid):
                click.echo(f"  • {filename} → {year}-{month}")

        if invalid:
            click.echo(f"\n⚠️  Invalid files ({len(invalid)}):")
            for filename in sorted(invalid):
                click.echo(f"  • {filename}")

        # Show year summary
        if valid:
            years = {}
            for _, year, _ in valid:
                years[year] = years.get(year, 0) + 1

            click.echo("\nYear summary:")
            for year in sorted(years.keys()):
                click.echo(f"  {year}: {years[year]} file(s)")

    except (TxtBuildError, Exception) as e:
        handle_cli_error(ctx, e, "validate", {"inbox": inbox})


if __name__ == "__main__":
    cli(obj={})
