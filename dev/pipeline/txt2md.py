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

Programmatic API:
    from dev.pipeline.txt2md import convert_file, convert_directory
    stats = convert_file(input_path, output_dir, force_overwrite, logger)
    stats = convert_directory(input_dir, output_dir, force_overwrite, logger)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from typing import Optional

# --- Local imports ---
from dev.core.exceptions import Txt2MdError
from dev.core.temporal_files import TemporalFileManager
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.core.cli import ConversionStats
from dev.dataclasses.txt_entry import TxtEntry


# --- Conversion ---
def process_entry(
    entry: TxtEntry,
    output_dir: Path,
    force_overwrite: bool,
    minimal_yaml: bool,
    logger: Optional[PalimpsestLogger] = None,
) -> Optional[Path]:
    """
    Process a single TxtEntry and write to Markdown file.

    Implementation Logic:
    ---------------------
    Converts a parsed TxtEntry dataclass instance into a Markdown file with
    YAML frontmatter. Handles year-based directory organization and file
    existence checks.

    Processing Flow:
    1. Extracts date from entry for filename generation
    2. Creates year-based directory structure (output_dir/YYYY/)
    3. Checks for existing file (skips if exists unless force_overwrite)
    4. Generates Markdown content with frontmatter
    5. Writes to file with UTF-8 encoding

    Filename Generation:
    - Format: YYYY-MM-DD.md
    - Derived from entry.date field
    - Example: 2024-01-15.md

    Directory Structure:
    - Creates: output_dir/YYYY/
    - Example: md/2024/2024-01-15.md

    YAML Frontmatter Options:
    - minimal_yaml=True: Only date, word_count, reading_time
    - minimal_yaml=False: Uses entry.to_markdown() with full metadata

    Skip Logic:
    - If file exists and not force_overwrite: returns None
    - Logs skip action for debugging
    - No error raised (considered success)

    Args:
        entry: Parsed TxtEntry with date, content, and computed metadata
        output_dir: Base output directory (typically MD_DIR)
        force_overwrite: If True, overwrite existing files
        minimal_yaml: If True, generate minimal frontmatter only
        logger: Optional logger for debug output

    Returns:
        Path to created/overwritten file, or None if skipped

    Raises:
        Txt2MdError: If file write fails or directory creation fails
    """
    safe_logger(logger).log_debug(f"Processing entry dated {entry.date.isoformat()}")

    # Create year directory structure
    year_dir = output_dir / str(entry.date.year)
    year_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{entry.date.isoformat()}.md"
    output_path = year_dir / filename

    # Check for existing files
    if output_path.exists() and not force_overwrite:
        safe_logger(logger).log_debug(f"{output_path.name} exists, skipping")
        return None

    # Generate markdown content
    if minimal_yaml:
        content = _generate_minimal_markdown(entry)
    else:
        content = entry.to_markdown()

    # Write file
    output_path.write_text(content, encoding="utf-8")

    action = "Overwrote" if output_path.exists() else "Created"
    safe_logger(logger).log_debug(f"{action} file: {output_path.name}")

    return output_path


def convert_file(
    input_path: Path,
    output_dir: Path,
    force_overwrite: bool = False,
    minimal_yaml: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> ConversionStats:
    """
    Convert a single monthly .txt file to multiple daily Markdown files.

    Implementation Logic:
    ---------------------
    Takes a monthly text file (YYYY-MM.txt) containing multiple daily entries
    and splits it into individual daily Markdown files with YAML frontmatter.
    Core function for txt2md conversion pipeline.

    Processing Flow:
    1. Validates input file exists
    2. Creates output directory structure
    3. Parses file into TxtEntry objects (using TxtEntry.from_file())
    4. Processes each entry individually (calls process_entry())
    5. Tracks statistics (created/skipped/errors)
    6. Logs operation completion

    Large File Handling:
    - Files > 50MB use temporary file processing
    - Copies to temp location to avoid memory issues
    - TemporalFileManager handles cleanup automatically
    - Prevents memory exhaustion on large monthly exports

    Parsing Strategy:
    - TxtEntry.from_file() handles entry boundary detection
    - Identifies daily entries by date markers
    - Extracts content and computes metadata
    - Returns list of TxtEntry objects

    Error Handling:
    - Individual entry failures don't stop batch
    - Each error logged and counted in stats
    - Statistics track: files_processed, entries_created, entries_skipped, errors
    - Final operation logged with summary

    Statistics Tracking:
    - stats.files_processed: Always 1 (single file)
    - stats.entries_created: Count of new .md files written
    - stats.entries_skipped: Count of existing files not overwritten
    - stats.errors: Count of entry processing failures

    Args:
        input_path: Path to monthly .txt file (e.g., 2024-01.txt)
        output_dir: Base output directory (typically MD_DIR)
        force_overwrite: If True, overwrite existing .md files
        minimal_yaml: If True, generate minimal frontmatter only
        logger: Optional logger for operation tracking

    Returns:
        ConversionStats object with processing results

    Raises:
        Txt2MdError: If input file not found or critical parsing failure
    """
    stats = ConversionStats()

    if not input_path.exists():
        raise Txt2MdError(f"Input file not found: {input_path}")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_logger(logger).log_operation(
        "convert_file_start", {"input": str(input_path), "output": str(output_dir)}
    )

    # Parse entries from .txt file
    try:
        with TemporalFileManager() as temp_manager:
            # For large files, use temporary processing
            if input_path.stat().st_size > 50 * 1024 * 1024:  # 50MB+
                safe_logger(logger).log_debug("Large file detected, using temporary processing")
                temp_file = temp_manager.create_temp_file(suffix=".txt")
                temp_file.write_text(
                    input_path.read_text(encoding="utf-8"), encoding="utf-8"
                )
                entries = TxtEntry.from_file(temp_file, verbose=False)
            else:
                entries = TxtEntry.from_file(input_path, verbose=False)

        safe_logger(logger).log_operation(
            "entries_parsed", {"file": input_path.name, "count": len(entries)}
        )
    except Exception as e:
        safe_logger(logger).log_error(e, {"operation": "parse_file", "file": str(input_path)})
        raise Txt2MdError(f"Failed to parse {input_path}: {e}") from e

    if not entries:
        safe_logger(logger).log_info(f"No entries found in {input_path}")
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
        except Txt2MdError as e:
            stats.errors += 1
            safe_logger(logger).log_error(
                e, {"operation": "process_entry", "date": str(entry.date)}
            )

    stats.files_processed = 1

    safe_logger(logger).log_operation("convert_file_complete", {"stats": stats.summary()})

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
        Txt2MdError: If directory not found
    """
    total_stats = ConversionStats()

    if not input_dir.exists():
        raise Txt2MdError(f"Input directory not found: {input_dir}")

    txt_files = list(input_dir.rglob(pattern))
    if not txt_files:
        safe_logger(logger).log_info(f"No .txt files found in {input_dir}")
        return total_stats

    safe_logger(logger).log_operation(
        "convert_directory_start",
        {"input": str(input_dir), "files_found": len(txt_files)},
    )

    # Process each file
    for txt_file in txt_files:
        try:
            safe_logger(logger).log_info(f"Processing {txt_file.name}")

            stats = convert_file(
                txt_file, output_dir, force_overwrite, minimal_yaml, logger
            )

            # Aggregate stats
            total_stats.files_processed += stats.files_processed
            total_stats.entries_created += stats.entries_created
            total_stats.entries_skipped += stats.entries_skipped
            total_stats.errors += stats.errors

        except Txt2MdError as e:
            total_stats.errors += 1
            safe_logger(logger).log_error(
                e, {"operation": "convert_file", "file": str(txt_file)}
            )

    safe_logger(logger).log_operation(
        "convert_directory_complete", {"stats": total_stats.summary()}
    )

    return total_stats


# --- Helper ---
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


