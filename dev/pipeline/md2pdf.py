#!/usr/bin/env python3
"""
md2pdf.py
-------------------
Generate yearly journal PDFs from Markdown entries.

Builds two PDF versions from daily Markdown files:
1. Clean PDF - Reading/archival version
2. Notes PDF - Annotation version with line numbers

Uses Pandoc with custom LaTeX preambles for professional typography.

Programmatic API:
    from dev.pipeline.md2pdf import build_pdf

    stats = build_pdf(year, md_dir, pdf_dir, preamble, preamble_notes,
                      force_overwrite=False, logger=logger)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from typing import Optional

# --- Local imports ---
from dev.core.exceptions import PdfBuildError
from dev.core.logging_manager import PalimpsestLogger
from dev.builders.pdfbuilder import PdfBuilder, BuildStats


# --- Programmatic API ---


def build_pdf(
    year: str,
    md_dir: Path,
    pdf_dir: Path,
    preamble: Optional[Path] = None,
    preamble_notes: Optional[Path] = None,
    force_overwrite: bool = False,
    keep_temp_on_error: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> BuildStats:
    """
    Build clean and notes PDFs for a specific year.

    This is the programmatic API for md2pdf processing, used by:
    - The pipeline CLI (python -m dev.pipeline.cli build-pdf)
    - The standalone CLI (python -m dev.pipeline.md2pdf build)

    Args:
        year: Year to build (YYYY format)
        md_dir: Markdown source directory
        pdf_dir: PDF output directory
        preamble: LaTeX preamble for clean PDF (defaults to TEX_DIR/preamble.tex)
        preamble_notes: LaTeX preamble for notes PDF (defaults to TEX_DIR/preamble_notes.tex)
        force_overwrite: Force overwrite existing PDFs
        keep_temp_on_error: Keep temp files on error for debugging
        logger: Optional logger instance

    Returns:
        BuildStats with files_processed, pdfs_created, etc.

    Raises:
        PdfBuildError: If build fails
    """
    # Validate year format
    if not year.isdigit() or len(year) != 4:
        raise PdfBuildError(f"Invalid year format: {year} (expected YYYY)")

    # Apply defaults
    if preamble is None:
        preamble = TEX_DIR / "preamble.tex"
    if preamble_notes is None:
        preamble_notes = TEX_DIR / "preamble_notes.tex"

    # Create builder
    builder = PdfBuilder(
        year=year,
        md_dir=md_dir,
        pdf_dir=pdf_dir,
        preamble=preamble,
        preamble_notes=preamble_notes,
        force_overwrite=force_overwrite,
        keep_temp_on_error=keep_temp_on_error,
        logger=logger,
    )

    # Execute build
    stats: BuildStats = builder.build()

    return stats


