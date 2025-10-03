#!/usr/bin/env python3
"""
txt2md.py
-------------------
Convert pre-cleaned 750words .txt (monthly) exports into daily Markdown files.
Pure text conversion with minimal YAML frontmatter - no db integration.

Generates daily Markdown files with basic computed metadata only:
- date (from entry parsing)
- word_count (computed)
- reading_time (computed)

Complex YAML metadata handling is deferred to yaml2sql/MdEntry pipeline.

    journal/
    ├── sources/
    │   └── txt/
    │       └── <YYYY>
    │           └── <YYYY-MM>.md
    └── content/
        └── md/
            └── <YYYY>
                └── <YYYY-MM-DD>.md

Usage:
    python txt2md.py -i input_file.txt [-o output_dir/]
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import sys
import click
import logging

from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

# --- Local imports ---
from dev.core.paths import LOG_DIR, MD_DIR  # , TMP_DIR  , ROOT
from dev.core.temporal_files import TemporalFileManager
from dev.core.logging_manager import PalimpsestLogger
from dev.dataclasses.txt_entry import TxtEntry


# ----- Conversion Error -----
class ConversionError(Exception):
    """Exception for conversion errors."""

    pass


# ----- Conversion Stats -----
class ConversionStats:
    """Track conversion statistics."""

    def __init__(self):
        self.files_processed = 0
        self.entries_created = 0
        self.entries_skipped = 0
        self.errors = 0
        self.start_time = datetime.now()

    def duration(self) -> float:
        """Get elapsed time in seconds."""
        return (datetime.now() - self.start_time).total_seconds()

    def summary(self) -> str:
        """Get summary string."""
        return (
            f"{self.files_processed} files processed, "
            f"{self.entries_created} entries created, "
            f"{self.entries_skipped} skipped, "
            f"{self.errors} errors in {self.duration():.2f}s"
        )


# ----- Functions -----
# ---- Logging ----
def setup_logger(log_dir: Path, verbose: bool = False) -> PalimpsestLogger:
    """Setup logging for txt2md operations."""
    operations_log_dir = log_dir / "operations"
    operations_log_dir.mkdir(parents=True, exist_ok=True)

    logger = PalimpsestLogger(operations_log_dir, component_name="txt2md")

    if verbose:
        logger.main_logger.setLevel(logging.DEBUG)
        for handler in logger.main_logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(logging.DEBUG)

    return logger


# ---- Conversion ----
def process_entry(
    entry: TxtEntry,
    output_dir: Path,
    force_overwrite: bool,
    minimal_yaml: bool,
    logger: Optional[PalimpsestLogger] = None,
) -> Optional[Path]:
    """
    Process a single entry and write to file.

    Returns:
        Path to created file, or None if skipped

    Raises:
        ConversionError: If processing fails
    """
    if logger:
        logger.log_debug(f"Processing entry dated {entry.date.isoformat()}")

    # Create year directory structure
    year_dir = output_dir / str(entry.date.year)
    year_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{entry.date.isoformat()}.md"
    output_path = year_dir / filename

    # Check for existing files
    if output_path.exists() and not force_overwrite:
        if logger:
            logger.log_debug(f"{output_path.name} exists, skipping")
        return None

    # Generate markdown content
    if minimal_yaml:
        content = _generate_minimal_markdown(entry)
    else:
        content = entry.to_markdown()

    # Write file
    output_path.write_text(content, encoding="utf-8")

    if logger:
        action = "Overwrote" if output_path.exists() else "Created"
        logger.log_debug(f"{action} file: {output_path.name}")

    return output_path


def convert_file(
    input_path: Path,
    output_dir: Path,
    force_overwrite: bool = False,
    minimal_yaml: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> ConversionStats:
    """
    Convert a single .txt file to multiple Markdown files.

    Returns:
        ConversionStats with results

    Raises:
        ConversionError: If conversion fails
    """
    stats = ConversionStats()

    if not input_path.exists():
        raise ConversionError(f"Input file not found: {input_path}")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    if logger:
        logger.log_operation(
            "convert_file_start", {"input": str(input_path), "output": str(output_dir)}
        )

    # Parse entries from .txt file
    try:
        with TemporalFileManager() as temp_manager:
            # For large files, use temporary processing
            if input_path.stat().st_size > 50 * 1024 * 1024:  # 50MB+
                if logger:
                    logger.log_debug("Large file detected, using temporary processing")
                temp_file = temp_manager.create_temp_file(suffix=".txt")
                temp_file.write_text(
                    input_path.read_text(encoding="utf-8"), encoding="utf-8"
                )
                entries = TxtEntry.from_file(temp_file, verbose=False)
            else:
                entries = TxtEntry.from_file(input_path, verbose=False)

        if logger:
            logger.log_operation(
                "entries_parsed", {"file": input_path.name, "count": len(entries)}
            )
    except Exception as e:
        if logger:
            logger.log_error(e, {"operation": "parse_file", "file": str(input_path)})
        raise ConversionError(f"Failed to parse {input_path}: {e}") from e

    if not entries:
        if logger:
            logger.log_info(f"No entries found in {input_path}")
        return stats

    # Process each entry
    for entry in entries:
        try:
            result = process_entry(
                entry, output_dir, force_overwrite, minimal_yaml, logger
            )
            if result:
                stats.entries_created += 1
            else:
                stats.entries_skipped += 1
        except ConversionError as e:
            stats.errors += 1
            if logger:
                logger.log_error(
                    e, {"operation": "process_entry", "date": str(entry.date)}
                )

    stats.files_processed = 1

    if logger:
        logger.log_operation("convert_file_complete", {"stats": stats.summary()})

    return stats


def convert_directory(
    input_dir: Path,
    output_dir: Path,
    pattern: str = "*.txt",
    force_overwrite: bool = False,
    minimal_yaml: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> ConversionStats:
    """
    Convert all .txt files in a directory.

    Returns:
        ConversionStats with results

    Raises:
        ConversionError: If directory not found
    """
    total_stats = ConversionStats()

    if not input_dir.exists():
        raise ConversionError(f"Input directory not found: {input_dir}")

    txt_files = list(input_dir.glob(pattern))
    if not txt_files:
        if logger:
            logger.log_info(f"No .txt files found in {input_dir}")
        return total_stats

    if logger:
        logger.log_operation(
            "convert_directory_start",
            {"input": str(input_dir), "files_found": len(txt_files)},
        )

    # Process each file
    for txt_file in txt_files:
        try:
            if logger:
                logger.log_info(f"Processing {txt_file.name}")

            stats = convert_file(
                txt_file, output_dir, force_overwrite, minimal_yaml, logger
            )

            # Aggregate stats
            total_stats.files_processed += stats.files_processed
            total_stats.entries_created += stats.entries_created
            total_stats.entries_skipped += stats.entries_skipped
            total_stats.errors += stats.errors

        except ConversionError as e:
            total_stats.errors += 1
            if logger:
                logger.log_error(
                    e, {"operation": "convert_file", "file": str(txt_file)}
                )

    if logger:
        logger.log_operation(
            "convert_directory_complete", {"stats": total_stats.summary()}
        )

    return total_stats


# ----- Helper -----
def _generate_minimal_markdown(entry: TxtEntry) -> str:
    """Generate Markdown with minimal YAML frontmatter (date only)."""
    lines = [
        "---",
        f"date: {entry.date.isoformat()}",
        "---",
        "",
        f"# {entry.header}",
        "",
    ]
    lines.extend(entry.body)
    return "\n".join(lines)


# ----- CLI -----
@click.group()
@click.option(
    "--log-dir",
    type=click.Path(),
    default=str(LOG_DIR),
    help="Directory for log files",
)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
@click.pass_context
def cli(ctx, log_dir, verbose):
    """txt2md - Convert 750words .txt exports to Markdown"""
    ctx.ensure_object(dict)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["verbose"] = verbose
    ctx.obj["logger"] = setup_logger(Path(log_dir), verbose)


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=str(MD_DIR),
    help=f"Output directory (default: {MD_DIR})",
)
@click.option("-f", "--force", is_flag=True, help="Overwrite existing files")
@click.option("--minimal", is_flag=True, help="Generate minimal YAML (date only)")
@click.pass_context
def convert(ctx, input_file, output, force, minimal):
    """Convert a single .txt file to Markdown entries."""
    logger = ctx.obj["logger"]

    try:
        input_path = Path(input_file)
        output_dir = Path(output)

        click.echo(f"📄 Converting {input_path.name}")

        stats = convert_file(
            input_path,
            output_dir,
            force_overwrite=force,
            minimal_yaml=minimal,
            logger=logger,
        )

        click.echo("\n✅ Conversion complete:")
        click.echo(f"  Created: {stats.entries_created} entries")
        if stats.entries_skipped > 0:
            click.echo(f"  Skipped: {stats.entries_skipped} entries")
        if stats.errors > 0:
            click.echo(f"  Errors: {stats.errors}")
        click.echo(f"  Duration: {stats.duration():.2f}s")

    except ConversionError as e:
        click.echo(f"❌ Conversion failed: {e}", err=True)
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
    "-o",
    "--output",
    type=click.Path(),
    default=str(MD_DIR),
    help=f"Output directory (default: {MD_DIR})",
)
@click.option(
    "-p", "--pattern", default="*.txt", help="File pattern to match (default: *.txt)"
)
@click.option("-f", "--force", is_flag=True, help="Overwrite existing files")
@click.option("--minimal", is_flag=True, help="Generate minimal YAML (date only)")
@click.pass_context
def batch(ctx, input_dir, output, pattern, force, minimal):
    """Convert all .txt files in a directory."""
    logger = ctx.obj["logger"]

    try:
        input_path = Path(input_dir)
        output_dir = Path(output)

        click.echo(f"📁 Processing directory: {input_path}")

        stats = convert_directory(
            input_path,
            output_dir,
            pattern=pattern,
            force_overwrite=force,
            minimal_yaml=minimal,
            logger=logger,
        )

        click.echo("\n✅ Batch conversion complete:")
        click.echo(f"  Files processed: {stats.files_processed}")
        click.echo(f"  Entries created: {stats.entries_created}")
        if stats.entries_skipped > 0:
            click.echo(f"  Entries skipped: {stats.entries_skipped}")
        if stats.errors > 0:
            click.echo(f"  Errors: {stats.errors}")
        click.echo(f"  Duration: {stats.duration():.2f}s")

    except ConversionError as e:
        click.echo(f"❌ Batch conversion failed: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        if ctx.obj["verbose"]:
            import traceback

            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.pass_context
def validate(ctx, input_file):
    """Validate a .txt file without converting."""
    try:
        input_path = Path(input_file)

        click.echo(f"🔍 Validating {input_path.name}")

        # Parse entries
        entries: List[TxtEntry] = TxtEntry.from_file(input_path, verbose=False)

        click.echo("\n✅ Validation successful:")
        click.echo(f"  Entries found: {len(entries)}")

        # Show date range
        if entries:
            dates: List[date] = [e.date for e in entries]
            click.echo(f"  Date range: {min(dates)} to {max(dates)}")

            # Show stats
            total_words: int = sum(e.word_count for e in entries)
            avg_words: float = total_words / len(entries)
            click.echo(f"  Total words: {total_words:,}")
            click.echo(f"  Average words/entry: {avg_words:.0f}")

    except Exception as e:
        click.echo(f"❌ Validation failed: {e}", err=True)
        if ctx.obj.get("verbose"):
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    cli(obj={})
