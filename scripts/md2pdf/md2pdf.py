#!/usr/bin/env python3
"""
md2pdf.py
-------------------

Command-line interface for generating yearly journal PDFs (clean and
review-notes versions) from daily Markdown entries using the PdfBuilder class.

This script parses command-line arguments to determine the year, source and
output directories, and LaTeX preamble files. It then instantiates PdfBuilder
with the appropriate configuration, executes the build process, and reports the
outcome.

Features:
    - Builds a 'clean' PDF suitable for distribution or archiving.
    - Builds a 'review-notes' PDF, which includes line numbers and other markup
      for review.
    - Supports verbose mode for detailed progress reporting.
    - Handles file and conversion errors gracefully, reporting user-friendly
      messages.

Arguments:
    year                 Four-digit year to process (e.g., '2025').
    -i, --indir          Path to the root directory containing Markdown files
                            (default: 'journal/md').
    -o, --outdir         Output directory for resulting PDFs
                            (default: 'journal/pdf').
    --preamble           Path to the LaTeX preamble for the clean PDF
                            (default: 'journal/latex/preamble.tex').
    --preamble-notes     Path to the LaTeX preamble for the notes PDF
                            (default: 'journal/latex/preamble_notes.tex').
    -v, --verbose        Enable verbose output for diagnostics.

Typical usage:
    python build_pdf.py 2025 --verbose
    python build_pdf.py 2024 --indir ~/journals/md --outdir ~/journals/pdf

Requires:
    - Python 3.7+
    - The pdfbuilder module (must be in your PYTHONPATH or same directory)
    - Pandoc and LaTeX installed and available to pypandoc
    - pypandoc Python package

"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import argparse
import sys
from pathlib import Path

# --- Local imports ---
from scripts.paths import LATEX_DIR, MD_DIR, PDF_DIR
from scripts.md2pdf.pdfbuilder import PdfBuilder


# ----- Argument parser -----
def parse_args() -> argparse.Namespace:
    """
    Arguments:
        - year: Four digit year to build.
        - indir: Directory to read Markdown files from.
        - outdir: Directory to save the yearly PDFs.
        - preamble: LaTeX preamble file for formatting.
        - preamble_notes: LaTeX preamble file for formatting (Notes).
        - clobber: Overwrite existing files.
        - verbose: Logging.
    """
    p = argparse.ArgumentParser(
        description="Build clean + review PDFs for a journal year"
    )

    # --- ARGUMENTS ---
    p.add_argument("year", help="Four-digit year to build (e.g. 2025)")
    p.add_argument(
        "-i", "--indir", default=MD_DIR, help="Root directory of Markdown files"
    )
    p.add_argument(
        "-o", "--outdir", default=PDF_DIR, help="Directory to write PDFs into"
    )
    p.add_argument(
        "--preamble",
        default=LATEX_DIR / "preamble.tex",
        help="Path to LaTeX preamble for clean PDF",
    )
    p.add_argument(
        "--preamble-notes",
        default=LATEX_DIR / "preamble_notes.tex",
        help="Path to LaTeX preamble for review-notes PDF",
    )
    p.add_argument(
        "-f",
        "--force",
        "--clobber",
        action="store_true",
        help="Overwrite existing output PDFs (quiet skip otherwise)",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    return p.parse_args()


# ----- Main -----
def main() -> None:
    """
    CLI entrypoint:
        - Parse command-line arguments
        - Gather per-entry Markdown files for the given year
        - Concatenate them into a temp .md
        - Run Pandoc twice to produce:
            * a clean PDF
            * a review-notes PDF with line numbers & watermark
    """
    args = parse_args()

    clean_pdf: Path = Path(args.outdir) / f"{args.year}.pdf"
    notes_pdf: Path = Path(args.outdir) / f"{args.year}-notes.pdf"

    builder = PdfBuilder(
        year=args.year,
        md_dir=Path(args.indir),
        pdf_dir=Path(args.outdir),
        preamble=Path(args.preamble),
        preamble_notes=Path(args.preamble_notes),
        verbose=args.verbose,
        clobber=args.force,
    )

    try:
        builder.build()
    except FileNotFoundError as e:
        print(f"[md2pdf] →  File not found: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"[md2pdf] →  Runtime error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"[md2pdf] →  Unexpected error: {e}", file=sys.stderr)
        sys.exit(3)


# ---- Main call ----
if __name__ == "__main__":
    main()
