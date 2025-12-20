#!/usr/bin/env python3
"""
src2txt.py
----------
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

Programmatic API:
    from dev.pipeline.src2txt import process_inbox
    stats = process_inbox(inbox_dir, output_dir, archive_dir, logger)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from typing import Optional

# --- Local imports ---
from dev.core.paths import ARCHIVE_DIR, FORMATTING_SCRIPT
from dev.core.logging_manager import PalimpsestLogger
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
