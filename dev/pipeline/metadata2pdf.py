#!/usr/bin/env python3
"""
metadata2pdf.py
---------------
Generate metadata curation PDFs from YAML files.

Builds PDF compilations of journal metadata (scenes, events, themes, arcs, etc.)
formatted for manuscript curation decisions. Uses two-column layout with arc markers
to highlight narrative structure and thematic richness.

Key Features:
    - Two-column layout (summary/rating left, structure/themes right)
    - Arc markers for narrative tracking
    - Star ratings for manuscript potential
    - Chronological organization with monthly chapters
    - Complete metadata display (scenes, events, themes, motifs, threads)

Usage:
    from dev.pipeline.metadata2pdf import build_metadata_pdf

    stats = build_metadata_pdf(
        year="2025",
        yaml_dir=JOURNAL_YAML_DIR,
        pdf_dir=PDF_DIR,
        preamble=TEX_DIR / "preamble_metadata.tex",
        force_overwrite=False,
        logger=logger
    )

Dependencies:
    - MetadataEntry: Parses YAML metadata files
    - MetadataPdfBuilder: Orchestrates PDF generation
    - Pandoc + Tectonic: PDF compilation
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from typing import Optional

# --- Local imports ---
from dev.core.exceptions import PdfBuildError
from dev.core.logging_manager import PalimpsestLogger
from dev.core.paths import TEX_DIR
from dev.builders.metadata_pdfbuilder import MetadataPdfBuilder, BuildStats


# --- Programmatic API ---


def build_metadata_pdf(
    year: str,
    yaml_dir: Path,
    pdf_dir: Path,
    preamble: Optional[Path] = None,
    force_overwrite: bool = False,
    keep_temp_on_error: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> BuildStats:
    """
    Build metadata curation PDF for a specific year.

    This is the programmatic API for metadata PDF generation, used by:
    - The pipeline CLI (python -m dev.pipeline.cli build-metadata-pdf)
    - The standalone CLI (python -m dev.pipeline.metadata2pdf build)

    Args:
        year: Year to build (YYYY format)
        yaml_dir: YAML metadata directory (contains YYYY/ subdirectories)
        pdf_dir: PDF output directory
        preamble: LaTeX preamble for metadata PDF (defaults to TEX_DIR/preamble_metadata.tex)
        force_overwrite: Force overwrite existing PDF
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
        preamble = TEX_DIR / "preamble_metadata.tex"

    # Create builder
    builder = MetadataPdfBuilder(
        year=year,
        yaml_dir=yaml_dir,
        pdf_dir=pdf_dir,
        preamble=preamble,
        force_overwrite=force_overwrite,
        keep_temp_on_error=keep_temp_on_error,
        logger=logger,
    )

    # Execute build
    stats: BuildStats = builder.build()

    return stats
