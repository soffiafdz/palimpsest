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
import argparse
import atexit
import os
import logging
import shutil
import sys
import warnings

from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Optional

# --- Local imports ---
from dev.dataclasses.txt_entry import TxtEntry
from dev.paths import LOG_DIR, MD_DIR, ROOT, TMP_DIR


# ----- Functions -----
# ---- Temporal files ----
def setup_temp_directory(temp_base_dir: Path) -> Path:
    """Setup temporary directory for txt2md operations with automatic cleanup."""
    temp_dir = temp_base_dir / "txt2md"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Register cleanup function to run on exit
    def cleanup_temp():
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass  # Ignore cleanup errors

    atexit.register(cleanup_temp)
    return temp_dir


def create_temp_file(temp_dir: Path, suffix: str = "", content: str = "") -> Path:
    """Create a temporary file in the txt2md temp directory."""
    temp_file = (
        temp_dir / f"txt2md_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{suffix}"
    )
    if content:
        temp_file.write_text(content, encoding="utf-8")
    return temp_file


# ---- Logging ----
def setup_logging(log_dir: Path, verbose: bool = False) -> logging.Logger:
    """Setup logging for txt2md operations."""
    operations_log_dir = log_dir / "operations" / "txt2md"
    operations_log_dir.mkdir(parents=True, exist_ok=True)

    # Create logger
    logger = logging.getLogger("txt2md")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Clear any existing handlers
    logger.handlers.clear()

    # File handler
    log_file = log_dir / "txt2md.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO if verbose else logging.WARNING)

    # Formatters
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
    )

    file_handler.setFormatter(file_formatter)
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# ---- Conversion ----
def convert_file(
    input_path: Path,
    output_dir: Path,
    force_overwrite: bool = False,
    minimal_yaml: bool = False,
    logger: Optional[logging.Logger] = None,
    temp_dir: Optional[Path] = None,
) -> List[Path]:
    """
    Convert a single .txt file to multiple Markdown files.

    Args:
        input_path: Path to input .txt file
        output_dir: Directory to write Markdown files
        force_overwrite: Whether to overwrite existing files
        minimal_yaml: Generate minimal YAML frontmatter
        logger: Logger instance for output
        temp_dir: Temporary directory for intermediate files

    Returns:
        List of created file paths
    """
    start_time = datetime.now()

    if not input_path.exists():
        error_msg = f"Input file not found: {input_path}"
        if logger:
            logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    if logger:
        logger.info(f"Converting {input_path} to {output_dir}")
        if temp_dir:
            logger.debug(f"Using temporary directory: {temp_dir}")

    # Parse entries from .txt file
    try:
        if temp_dir and input_path.stat().st_size > 50 * 1024 * 1024:  # 50MB+
            if logger:
                logger.debug("Large file detected, using temporary processing")
            temp_file = create_temp_file(temp_dir, ".txt")
            shutil.copy2(input_path, temp_file)
            entries = TxtEntry.from_file(
                temp_file,
                verbose=bool(logger) and logger.level <= logging.DEBUG,
            )
            temp_file.unlink()
        else:
            entries = TxtEntry.from_file(
                input_path, verbose=bool(logger) and logger.level <= logging.DEBUG
            )

        if logger:
            logger.info(f"Parsed {len(entries)} entries from {input_path.name}")
    except Exception as e:
        error_msg = f"Failed to parse {input_path}: {e}"
        if logger:
            logger.error(error_msg)
        raise RuntimeError(error_msg) from e

    if not entries:
        warning_msg = f"No entries found in {input_path}"
        if logger:
            logger.warning(warning_msg)
        return []

    # Write Markdown files
    created_files = []
    skipped_files = []
    error_count = 0

    for entry in entries:
        try:
            if entry.date is None:
                warning_msg = "Skipping entry with no date"
                warnings.warn(warning_msg, UserWarning)
                if logger:
                    logger.warning(warning_msg)
                continue

            if logger and logger.level <= logging.DEBUG:
                logger.debug(f"Processing entry dated {entry.date.isoformat()}")

            # Create year directory structure
            year_dir = output_dir / str(entry.date.year)
            year_dir.mkdir(parents=True, exist_ok=True)

            filename = f"{entry.date.isoformat()}.md"
            output_path = year_dir / filename

            # Check for existing files
            file_existed = output_path.exists()
            if file_existed and not force_overwrite:
                warning_msg = f"{output_path.name} exists, skipping"
                warnings.warn(f"Warning: {warning_msg}", UserWarning)
                if logger:
                    logger.debug(warning_msg)
                skipped_files.append(output_path)
                continue

            # Generate markdown content
            if minimal_yaml:
                content = _generate_minimal_markdown(entry)
            else:
                content = entry.to_markdown()

            # Write file
            output_path.write_text(content, encoding="utf-8")
            created_files.append(output_path)

            if logger and logger.level <= logging.DEBUG:
                action = "Overwrote" if file_existed else "Created"
                logger.debug(f"{action} file: {output_path.name}")

        except Exception as e:
            error_count += 1
            error_msg = f"Error processing entry {entry.date}: {e}"
            if logger:
                logger.error(error_msg)
            print(error_msg, file=sys.stderr)

    # Summary logging
    duration = (datetime.now() - start_time).total_seconds()
    if logger:
        logger.info(
            f"Conversion complete: {len(created_files)} files created, "
            f"{len(skipped_files)} skipped, {error_count} errors "
            f"in {duration:.2f} seconds"
        )

    return created_files


def convert_directory(
    input_dir: Path,
    output_dir: Path,
    pattern: str = "*.txt",
    force_overwrite: bool = False,
    minimal_yaml: bool = False,
    logger: Optional[logging.Logger] = None,
    temp_dir: Optional[Path] = None,
) -> dict[str, List[Path]]:
    """
    Convert all .txt files in a directory.

    Args:
        input_dir: Directory containing .txt files
        output_dir: Directory to write Markdown files
        pattern: File pattern to match (default: "*.txt")
        force_overwrite: Whether to overwrite existing files
        minimal_yaml: Generate minimal YAML frontmatter
        logger: Logger instance for output
        temp_dir: Temporary directory for intermediater files

    Returns:
        Dictionary mapping input file names to lists of created output files
    """
    start_time = datetime.now()

    if not input_dir.exists():
        error_msg = f"Input directory not found: {input_dir}"
        if logger:
            logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    txt_files = list(input_dir.glob(pattern))
    if not txt_files:
        warning_msg = f"No .txt files found in {input_dir}"
        if logger:
            logger.warning(warning_msg)
        return {}

    if logger:
        logger.info(f"Found {len(txt_files)} .txt files to process")

    results = {}
    total_created = 0
    total_errors = 0

    for txt_file in txt_files:
        try:
            if logger:
                logger.info(f"Processing {txt_file.name}")

            created_files = convert_file(
                txt_file,
                output_dir,
                force_overwrite=force_overwrite,
                minimal_yaml=minimal_yaml,
                logger=logger,
                temp_dir=temp_dir,
            )
            results[txt_file.name] = created_files
            total_created += len(created_files)

        except Exception as e:
            total_errors += 1
            error_msg = f"Error converting {txt_file}: {e}"
            if logger:
                logger.error(error_msg)
            print(error_msg, file=sys.stderr)
            results[txt_file.name] = []

    # Summary logging
    duration = (datetime.now() - start_time).total_seconds()
    if logger:
        logger.info(
            f"Directory conversion complete: {len(txt_files)} files processed, "
            f"{total_created} markdown files created, {total_errors} errors "
            f"in {duration:.2f} seconds"
        )

    return results


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


# ----- Argument parser -----
def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments for pure text conversion

    Arguments:
        - input: Pre-cleaned monthly .txt export.
        - outdir: Directory to save the yearly directory with Markdown entries.
        - force/clobber: Overwrite existing files.
        - minimal: Generate minimal YAML (date only).
        - log-dir: Directory for log files
        - temp-dir: Directory for temporary files
        - verbose: Logging.
    """
    p = argparse.ArgumentParser(
        description="Convert pre-cleaned .txt into per-entry Markdown files"
    )

    # --- CORE ARGUMENTS ---
    p.add_argument(
        "-i",
        "--input",
        required=True,
        type=Path,
        help="Path to pre-cleaned .txt file",
    )
    p.add_argument(
        "-o",
        "--outdir",
        default=str(MD_DIR),
        type=Path,
        help=f"Root dir for output (default: {str(MD_DIR)})",
    )

    # --- BEHAVIOR ARGUMENTS ---
    p.add_argument(
        "-f",
        "--force",
        "--clobber",
        action="store_true",
        help="Overwrite existing markdown files (quiet skip otherwise)",
    )
    p.add_argument(
        "--minimal",
        action="store_true",
        help="Generate minimal YAML frontmatter (date only)",
    )
    p.add_argument(
        "--log-dir",
        type=Path,
        default=str(LOG_DIR),
        help=f"Base directory for log files (default: {str(LOG_DIR)})",
    )
    p.add_argument(
        "--temp-dir",
        type=Path,
        default=str(TMP_DIR),
        help=f"Base directory for temporary files (default: {str(TMP_DIR)})",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    return p.parse_args()


# ----- Main -----
def main() -> None:
    """
    CLI entrypoint:
        - parses --input and --output arguments
        - reads and ftfy-cleans the input file
        - splits into entries, extracts headers & bodies
        - formats bodies, groups into paragraphs
        - reflows prose paras, preserves soft-break paras
        - calculates word count & reading time
        - writes clean Markdown with basic YAML frontmatter
        - NO database operations, NO complex YAML generation
    """
    logger: Optional[logging.Logger] = None
    args: Optional[argparse.Namespace] = None

    try:
        args = parse_args()
        input_path = args.input
        outdir = args.outdir
        verbose = args.verbose

        # Setup logging and temp directory
        logger = setup_logging(args.log_dir, verbose)
        temp_dir = setup_temp_directory(args.temp_dir)

        logger.info("Starting txt2md conversion")
        logger.info(f"Project root: {str(ROOT)}")
        logger.info(f"Reading from: {str(input_path)}")
        logger.info(f"Writing to: {str(outdir)}")
        logger.info(f"Temporary directory: {str(temp_dir)}")

        # --- Failsafes ---
        if not input_path.exists():
            raise FileNotFoundError(f"Input not found: {str(input_path)}")
        if not input_path.is_file() or not os.access(str(input_path), os.R_OK):
            raise OSError(f"Cannot read input file: {str(input_path)}")

        try:
            outdir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise OSError(f"Error creating output dir {str(outdir)}: {e}")
        if not outdir.is_dir() or not os.access(outdir, os.W_OK):
            raise OSError(f"Cannot write to {str(outdir)}")

        # --- Process ---
        logger.info("Starting pure text conversion...")

        if input_path.is_file():
            # Single file conversion
            created_files = convert_file(
                input_path,
                outdir,
                force_overwrite=args.force,
                minimal_yaml=args.minimal,
                logger=logger,
                temp_dir=temp_dir,
            )
            logger.info(f"Created {len(created_files)} Markdown files")

        elif input_path.is_dir():
            # Directory conversion
            results = convert_directory(
                input_path,
                outdir,
                force_overwrite=args.force,
                minimal_yaml=args.minimal,
                logger=logger,
                temp_dir=temp_dir,
            )
            total_files = sum(len(files) for files in results.values())
            logger.info(
                f"Processed {len(results)} input files, "
                f"created {total_files} Markdown files"
            )

        else:
            raise OSError(f"Input must be a file or directory: {input_path}")

        logger.info("txt2md conversion completed successfully")

    # --- Exceptions ---
    except FileNotFoundError as e:
        error_msg = f"File error: {e}"
        if logger:
            logger.error(error_msg)
        print(error_msg, file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        error_msg = f"OS error: {e}"
        if logger:
            logger.error(error_msg)
        print(error_msg, file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        if logger:
            logger.error(error_msg)
        print(error_msg, file=sys.stderr)
        if args and args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(3)


if __name__ == "__main__":
    main()
