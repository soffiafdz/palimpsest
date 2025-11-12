#!/usr/bin/env python3
"""
pdfbuilder.py
-------------------
Build yearly journal PDFs from Markdown files with Pandoc.

Generates two PDF types:
1. Clean PDF - Reading/distribution version
2. Notes PDF - Annotation version with line numbers and review formatting

Features:
- Monthly chapter organization
- Custom LaTeX preambles
- Automatic TOC generation
- Temporary file management
- Build statistics tracking

Usage:
    builder = PdfBuilder(
        year="2025",
        md_dir=Path("journal/md"),
        pdf_dir=Path("journal/pdf"),
        preamble=Path("journal/latex/preamble.tex"),
        preamble_notes=Path("journal/latex/preamble_notes.tex"),
        logger=logger
    )
    stats = builder.build()
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import calendar
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# --- Third party ---
from pypandoc import convert_file

from dev.builders.base import BuilderStats as BaseStats
from dev.core.exceptions import PdfBuildError
from dev.core.logging_manager import PalimpsestLogger
from dev.core.temporal_files import TemporalFileManager
from dev.utils.md import split_frontmatter


# ----- LaTeX Command Constants -----
"""LaTeX formatting commands for PDF generation."""

LATEX_NEWPAGE = "\\newpage\n\n"
"""LaTeX command to insert a page break."""

LATEX_NO_LINE_NUMBERS = "\\nolinenumbers\n"
"""LaTeX command to disable line numbering."""

LATEX_LINE_NUMBERS = "\\linenumbers\n"
"""LaTeX command to enable line numbering."""

LATEX_RESET_LINE_COUNTER = "\\setcounter{linenumber}{1}\n"
"""LaTeX command to reset line number counter to 1."""

LATEX_TOC = "\\tableofcontents\n"
"""LaTeX command to generate table of contents."""

ANNOTATION_TEMPLATE = [
    "",
    "- **Curation**: Reference | Quote | Fragments | Source",
    "- **City**: "
    "____________________________________________________________________________",
    "- **People**: "
    "__________________________________________________________________________",
    "- **Locations**: "
    "_______________________________________________________________________",
    "- **References**: "
    "______________________________________________________________________",
    "- **Epigraph**: "
    "________________________________________________________________________",
    "- **Poem(s)**: "
    "_________________________________________________________________________",
    "- **Connections**: "
    "_____________________________________________________________________",
    "- **Tags**: "
    "____________________________________________________________________________",
    "",
    "---",
    "",
]
"""
Annotation template for notes PDF generation.

Template inserted after each daily entry header in notes PDFs to provide
structured space for manual review and annotation. Includes fields for
curation notes, locations, people, references, epigraphs, poems, connections,
and tags.
"""

PANDOC_ENGINE = "tectonic"
"""Pandoc PDF engine to use for compilation (tectonic is a modern, self-contained LaTeX engine)."""

PANDOC_DOCUMENT_CLASS = "extarticle"
"""LaTeX document class for PDF generation (extarticle supports additional font sizes)."""

PDF_TITLE = "Palimpsest"
"""Default title for generated PDFs."""

PDF_AUTHOR = "Sofía F."
"""Default author name for generated PDFs."""

AUTHOR_BIRTH_YEAR = 1993
"""Birth year used to calculate age annotation in PDF metadata."""


# ---- Classes ----
class BuildStats(BaseStats):
    """
    Track PDF build statistics.

    Extends BuilderStats base class with PDF-specific metrics.
    """

    def __init__(self) -> None:
        """Initialize PDF build statistics."""
        super().__init__()
        self.files_processed: int = 0
        self.pdfs_created: int = 0
        self.errors: int = 0

    def summary(self) -> str:
        """
        Get formatted summary of PDF build.

        Returns:
            Summary string with file count, PDFs created, errors, and duration
        """
        return (
            f"{self.files_processed} entries, "
            f"{self.pdfs_created} PDFs created, "
            f"{self.errors} errors in {self.duration():.2f}s"
        )


class PdfBuilder:
    """
    Build yearly journal PDFs from Markdown files.

    Assembles, concatenates, and exports a year's journal entries into
    formatted PDFs using Pandoc with custom LaTeX preambles.

    Attributes:
        year: Target year (e.g. '2025')
        md_dir: Directory containing source Markdown files
        pdf_dir: Output directory for PDFs
        preamble: LaTeX preamble for clean PDF
        preamble_notes: LaTeX preamble for notes PDF
        force_overwrite: If True, overwrite existing PDFs
        logger: Optional logger for operations
        keep_temp_on_error: If True, preserve temp files when errors occur
    """

    # --- Initialization ---
    def __init__(
        self,
        year: str,
        md_dir: Path,
        pdf_dir: Path,
        preamble: Optional[Path] = None,
        preamble_notes: Optional[Path] = None,
        force_overwrite: bool = False,
        keep_temp_on_error: bool = True,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize PdfBuilder.

        Args:
            year: Four-digit year (e.g., '2025')
            md_dir: Directory where Markdown files are stored
            pdf_dir: Output directory for PDFs
            preamble: Path to LaTeX preamble for clean PDF
            preamble_notes: Path to LaTeX preamble for notes PDF
            force_overwrite: Overwrite existing PDFs
            keep_temp_on_error: Preserve temp files on error for debugging
            logger: Optional logger
        """
        self.year = year
        self.md_dir = md_dir
        self.pdf_dir = pdf_dir
        self.preamble = preamble
        self.preamble_notes = preamble_notes
        self.force_overwrite = force_overwrite
        self.keep_temp_on_error = keep_temp_on_error
        self.logger = logger

    def gather_md(self) -> List[Path]:
        """
        Collect all Markdown files for the specified year.

        Returns:
            Sorted list of Markdown file paths

        Raises:
            PdfBuildError: If directory not found or no files found
        """
        md_year = self.md_dir / self.year

        if self.logger:
            self.logger.log_debug(f"Looking for Markdown files in: {md_year}")

        if not md_year.exists() or not md_year.is_dir():
            raise PdfBuildError(f"Markdown directory not found: {md_year}")

        files = sorted(md_year.glob(f"{self.year}-*.md"))

        if not files:
            raise PdfBuildError(f"No Markdown files found in {md_year}")

        if self.logger:
            self.logger.log_debug(f"Found {len(files)} Markdown entries")

        return files

    def _write_temp_md(
        self, files: List[Path], tmp_path: Path, notes: bool = False
    ) -> None:
        """
        Concatenate Markdown files into temporary file.

        Adds monthly chapter headers and optional notes formatting
        (line numbers, annotation templates).

        Args:
            files: List of daily Markdown files
            tmp_path: Path to temporary output file
            notes: If True, include notes formatting

        Raises:
            PdfBuildError: If file writing fails
        """
        if self.logger:
            pdf_type = "notes" if notes else "clean"
            self.logger.log_debug(
                f"Creating concatenated {pdf_type} Markdown: {tmp_path.name}"
            )

        # Group files by month
        months: Dict[str, List[Path]] = defaultdict(list)
        for md_file in sorted(files):
            parts = md_file.stem.split("-")
            if len(parts) < 2:
                if self.logger:
                    self.logger.log_warning(
                        f"Skipping malformed filename: {md_file.stem}"
                    )
                continue
            _, month_str, *_ = parts
            months[month_str].append(md_file)

        if self.logger:
            self.logger.log_debug(
                f"Grouped into {len(months)} months for year {self.year}"
            )

        try:
            with tmp_path.open("w", encoding="utf-8") as tmp:
                # Process each month
                for month_str in sorted(months.keys(), key=lambda m: int(m)):
                    month_name = calendar.month_name[int(month_str)]

                    # Month chapter header
                    tmp.write(LATEX_NEWPAGE)
                    if notes:
                        tmp.write(LATEX_NO_LINE_NUMBERS)
                    tmp.write(f"# {month_name}, {self.year}\n\n")

                    # Process daily entries
                    first_day = True
                    for md_file in months[month_str]:
                        content = md_file.read_text(encoding="utf-8")

                        # Strip YAML frontmatter using utility function
                        _, body_lines = split_frontmatter(content)
                        content = '\n'.join(body_lines)

                        if notes:
                            # Add notes formatting
                            lines = content.splitlines()
                            updated_lines = []
                            inserted = False

                            for line in lines:
                                # Insert notes template after date header
                                if line.startswith("##") and not inserted:
                                    if not first_day:
                                        updated_lines.append(LATEX_NEWPAGE.strip())
                                    updated_lines.append(LATEX_NO_LINE_NUMBERS.strip())
                                    updated_lines.append(line)
                                    updated_lines.extend(ANNOTATION_TEMPLATE)
                                    updated_lines.append(
                                        LATEX_RESET_LINE_COUNTER.strip()
                                    )
                                    updated_lines.append(LATEX_LINE_NUMBERS.strip())
                                    inserted = True
                                    first_day = False
                                else:
                                    updated_lines.append(line)

                            tmp.write("\n".join(updated_lines))
                        else:
                            tmp.write(content)

                        tmp.write("\n\n")

                # Add table of contents at end
                tmp.write(LATEX_NEWPAGE)
                if notes:
                    tmp.write(LATEX_NO_LINE_NUMBERS)
                tmp.write(LATEX_TOC)

        except OSError as e:
            raise PdfBuildError(
                f"Failed to write temporary file {tmp_path}: {e}"
            ) from e

    def _run_pandoc(
        self,
        in_md: Path,
        out_pdf: Path,
        preamble: Path,
        metadata: Dict[str, str],
        extra_vars: Dict[str, str],
    ) -> None:
        """
        Convert Markdown to PDF using Pandoc.

        Args:
            in_md: Source Markdown file
            out_pdf: Output PDF file
            preamble: LaTeX preamble file
            metadata: Pandoc metadata key-value pairs
            extra_vars: Additional LaTeX variables

        Raises:
            PdfBuildError: If conversion fails
        """
        if not in_md.is_file():
            raise PdfBuildError(f"Markdown file not found: {in_md}")

        # Build Pandoc arguments
        args = [
            "--from",
            "markdown",
            "--pdf-engine",
            PANDOC_ENGINE,
            "--include-in-header",
            str(preamble),
            "--variable",
            f"documentclass:{PANDOC_DOCUMENT_CLASS}",
        ]

        # Add metadata
        for key, value in metadata.items():
            args.extend(["--metadata", f"{key}: {value}"])

        # Add extra variables
        for key, value in extra_vars.items():
            args.extend(["--variable", f"{key}:{value}"])

        if self.logger:
            self.logger.log_debug(f"Running Pandoc: {in_md.name} → {out_pdf.name}")
            self.logger.log_debug(f"Temp file location: {in_md}")

        try:
            convert_file(str(in_md), to="pdf", outputfile=str(out_pdf), extra_args=args)
        except (OSError, RuntimeError) as e:
            raise PdfBuildError(
                f"Pandoc conversion failed: {in_md} → {out_pdf}: {e}"
            ) from e

    def build(self) -> BuildStats:
        """
        Execute complete PDF build process.

        Builds clean and/or notes PDFs based on available preambles.

        Returns:
            BuildStats with build results

        Raises:
            PdfBuildError: If build fails
        """
        stats = BuildStats()

        if self.logger:
            self.logger.log_operation(
                "pdf_build_start",
                {
                    "year": self.year,
                    "md_dir": str(self.md_dir),
                    "pdf_dir": str(self.pdf_dir),
                },
            )

        # Validate preambles
        if not self.preamble and not self.preamble_notes:
            raise PdfBuildError("At least one preamble file must be provided")

        if self.preamble and not self.preamble.is_file():
            raise PdfBuildError(f"Clean preamble not found: {self.preamble}")

        if self.preamble_notes and not self.preamble_notes.is_file():
            raise PdfBuildError(f"Notes preamble not found: {self.preamble_notes}")

        # Ensure output directory exists
        try:
            self.pdf_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise PdfBuildError(
                f"Cannot create PDF directory {self.pdf_dir}: {e}"
            ) from e

        # Common Pandoc metadata
        metadata = {
            "title": PDF_TITLE,
            "date": f"{self.year} — {int(self.year) - AUTHOR_BIRTH_YEAR} years old",
            "author": PDF_AUTHOR,
        }

        # LaTeX variables for different PDF types
        clean_vars = {"fontsize": "12pt"}
        notes_vars = {"fontsize": "12pt", "linestretch": "1.9"}

        # Gather files
        try:
            files = self.gather_md()
            stats.files_processed = len(files)
        except PdfBuildError:
            raise

        # Use TemporalFileManager for proper cleanup
        temp_manager = TemporalFileManager()
        error_occurred = False

        try:
            # Build clean PDF
            if self.preamble:
                clean_pdf = self.pdf_dir / f"{self.year}.pdf"

                if clean_pdf.exists():
                    if not self.force_overwrite:
                        if self.logger:
                            self.logger.log_info(
                                f"Clean PDF exists, skipping: {clean_pdf.name}"
                            )
                    else:
                        if self.logger:
                            self.logger.log_debug(
                                f"Clean PDF exists, overwriting: {clean_pdf.name}"
                            )
                        clean_pdf.unlink()

                        tmp_clean = temp_manager.create_temp_file(
                            suffix=".md", prefix=f"palimpsest_{self.year}_clean_"
                        )

                        self._write_temp_md(files, tmp_clean, notes=False)
                        self._run_pandoc(
                            tmp_clean, clean_pdf, self.preamble, metadata, clean_vars
                        )

                        stats.pdfs_created += 1

                        if self.logger:
                            self.logger.log_operation(
                                "pdf_created", {"type": "clean", "file": str(clean_pdf)}
                            )
                else:
                    # File doesn't exist, create it
                    tmp_clean = temp_manager.create_temp_file(
                        suffix=".md", prefix=f"palimpsest_{self.year}_clean_"
                    )

                    self._write_temp_md(files, tmp_clean, notes=False)
                    self._run_pandoc(
                        tmp_clean, clean_pdf, self.preamble, metadata, clean_vars
                    )

                    stats.pdfs_created += 1

                    if self.logger:
                        self.logger.log_operation(
                            "pdf_created", {"type": "clean", "file": str(clean_pdf)}
                        )

            # Build notes PDF
            if self.preamble_notes:
                notes_pdf = self.pdf_dir / f"{self.year}-notes.pdf"

                if notes_pdf.exists():
                    if not self.force_overwrite:
                        if self.logger:
                            self.logger.log_info(
                                f"Notes PDF exists, skipping: {notes_pdf.name}"
                            )
                    else:
                        if self.logger:
                            self.logger.log_debug(
                                f"Notes PDF exists, overwriting: {notes_pdf.name}"
                            )
                        notes_pdf.unlink()

                        tmp_notes = temp_manager.create_temp_file(
                            suffix=".md", prefix=f"palimpsest_{self.year}_notes_"
                        )

                        self._write_temp_md(files, tmp_notes, notes=True)
                        self._run_pandoc(
                            tmp_notes, notes_pdf, self.preamble_notes, metadata, notes_vars
                        )

                        stats.pdfs_created += 1

                        if self.logger:
                            self.logger.log_operation(
                                "pdf_created", {"type": "notes", "file": str(notes_pdf)}
                            )
                else:
                    # File doesn't exist, create it
                    tmp_notes = temp_manager.create_temp_file(
                        suffix=".md", prefix=f"palimpsest_{self.year}_notes_"
                    )

                    self._write_temp_md(files, tmp_notes, notes=True)
                    self._run_pandoc(
                        tmp_notes, notes_pdf, self.preamble_notes, metadata, notes_vars
                    )

                    stats.pdfs_created += 1

                    if self.logger:
                        self.logger.log_operation(
                            "pdf_created", {"type": "notes", "file": str(notes_pdf)}
                        )

        except PdfBuildError:
            stats.errors += 1
            error_occurred = True
            raise

        finally:
            # Clean up with option to preserve on error
            if error_occurred and self.keep_temp_on_error:
                if self.logger:
                    self.logger.log_warning(
                        f"Error occurred - preserving temp files for debugging: "
                        f"{[str(f) for f in temp_manager.active_files]}"
                    )
            else:
                cleanup_stats = temp_manager.cleanup()
                if self.logger and cleanup_stats["files_removed"] > 0:
                    self.logger.log_debug(
                        f"Cleaned up {cleanup_stats['files_removed']} temporary files"
                    )

        if self.logger:
            self.logger.log_operation("pdf_build_complete", {"stats": stats.summary()})

        return stats
