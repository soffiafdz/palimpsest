#!/usr/bin/env python3
"""
build_pdf.py

Generate both a clean PDF and a review-notes PDF for a given year.
"""

import argparse
import sys
import tempfile
from pathlib import Path
from typing import List, Sequence

import pypandoc

# Determine project root relative to /scripts
SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parent

# Default locations under project root
MD_ROOT = PROJECT_ROOT / "journal" / "md"
LATEX_ROOT = PROJECT_ROOT / "journal" / "latex"
PDF_ROOT = PROJECT_ROOT / "journal" / "pdf"


def gather_md(year: str, md_root: Path) -> List[Path]:
    """
    input:
        year: target year string (e.g. "2025")
        md_root: Path to root of Markdown files (e.g. "md/")
    output:
        List of Paths to Markdown files named "{year}-*.md", sorted lexically.
    process:
        - Verify that md_root/year exists and is a directory.
        - Glob for files matching "year-*.md".
        - Exit with an error if no files are found.
    """
    md_year = md_root / year
    if not md_year.exists() or not md_year.is_dir():
        sys.stderr.write(f"Error: Markdown directory not found: {md_year}\n")
        sys.exit(1)
    files = sorted(md_year.glob(f"{year}-*.md"))
    if not files:
        sys.stderr.write(f"Error: No Markdown files found in {md_year}\n")
        sys.exit(1)
    return files


def write_temp_md(
    files: Sequence[Path],
    tmp_path: Path,
    year: str,
    verbose: bool = False
) -> None:
    """
    input:
        files: sequence of Paths to per-entry Markdown files
        tmp_path: Path to a temporary .md file to write
        year: the target year string for title
        verbose: if True, print progress messages
    output:
        None (writes concatenated Markdown to tmp_path)
    process:
        - Writes a title page ("% Journal Entries — {year}").
        - Inserts a Pandoc table of contents directive.
        - For each file: writes "\newpage" + blank line, then the file’s contents.
    """
    if verbose:
        print(f"Writing concatenated Markdown to {tmp_path}")
    with tmp_path.open("w", encoding="utf-8") as tmp:
        # Title page and TOC
        tmp.write(f"% Journal Entries — {year}\n")
        tmp.write("\\tableofcontents\n\n")
        # Entries, each on its own page
        for md_file in files:
            tmp.write("\\newpage\n\n")
            tmp.write(md_file.read_text(encoding="utf-8"))
            tmp.write("\n\n")


def run_pandoc(
    src_md: Path,
    dest_pdf: Path,
    preamble: Path,
    extra_args_base: Sequence[str],
    verbose: bool = False
) -> None:
    """
    input:
        src_md: Path to the source Markdown file
        dest_pdf: Path where the PDF should be written
        preamble: Path to a LaTeX preamble file to include
        extra_args_base: list of additional Pandoc arguments
            (e.g. ["--toc", "--toc-depth", "2"])
        verbose: if True, print progress messages
    output:
        None (writes PDF to dest_pdf)
    process:
        Calls pypandoc.convert_file with the given arguments
            to produce a PDF via xelatex.
    """
    args = [
        "--from", "markdown",
        "--pdf-engine", "xelatex",
        "--include-in-header", str(preamble),
    ] + list(extra_args_base)
    if verbose:
        cmd_str = "pandoc " + " ".join(args) + f" {src_md} -o {dest_pdf}"
        print(f"Running Pandoc command:\n  {cmd_str}")
    pypandoc.convert_file(
        str(src_md),
        to="pdf",
        outputfile=str(dest_pdf),
        extra_args=args
    )


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
    parser = argparse.ArgumentParser(
        description="Build clean + review PDFs for a journal year"
    )
    parser.add_argument(
        "year",
        help="Four-digit year to build (e.g. 2025)"
    )
    parser.add_argument(
        "-i", "--indir",
        default=str(MD_ROOT),
        help="Root directory of Markdown files"
    )
    parser.add_argument(
        "-o", "--outdir",
        default=str(PDF_ROOT),
        help="Directory to write PDFs into"
    )
    parser.add_argument(
        "--preamble",
        default=str(LATEX_ROOT / "preamble.tex"),
        help="Path to LaTeX preamble for clean PDF"
    )
    parser.add_argument(
        "--preamble-notes",
        default=str(LATEX_ROOT / "preamble_notes.tex"),
        help="Path to LaTeX preamble for review-notes PDF"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    args = parser.parse_args()

    year: str = args.year
    md_root: Path = Path(args.indir)
    pdf_root: Path = Path(args.outdir)
    preamble_clean: Path = Path(args.preamble)
    preamble_notes: Path = Path(args.preamble_notes)
    verbose: bool = args.verbose

    if not preamble_clean.is_file() and not preamble_notes.is_file():
        sys.stderr.write(f"Error creating PDF no preamble file found\n")
        sys.exit(1)

    if verbose:
        print(f"Project root: {PROJECT_ROOT}")
        print(f"Markdown root: {md_root}")
        print(f"PDF output dir: {pdf_root}")
        if preamble_clean.is_file():
            print(f"Clean preamble: {preamble_clean}")
        if preamble_notes.is_file():
            print(f"Notes preamble: {preamble_notes}")

    # Ensure output directory exists
    try:
        pdf_root.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        sys.stderr.write(
            f"Error creating PDF output directory {pdf_root}: {e}\n"
        )
        sys.exit(1)

    # Gather Markdown files
    if verbose:
        print(f"Gathering Markdown files for year {year}")
    files: List[Path] = gather_md(year, md_root)
    if verbose:
        print(f"Found {len(files)} files")

    # Build a temporary concatenated Markdown
    tmp_file = Path(
        tempfile.NamedTemporaryFile(suffix=".md", delete=False).name
    )
    write_temp_md(files, tmp_file, year)

    # Common Pandoc args: TOC, margins, font size
    extra_common = [
        "--toc", "--toc-depth", "2",
        "--variable", "geometry:margin=1in",
        "--variable", "fontsize:11pt",
    ]

        # 1) Clean PDF
    if preamble_clean.is_file():
        clean_pdf: Path = pdf_root / f"{year}.pdf"
        run_pandoc(tmp_file, clean_pdf, preamble_clean, extra_common)
        print(f"→ Clean PDF: {clean_pdf}")

    # 2) Review-notes PDF
    if preamble_notes.is_file():
        notes_pdf: Path = pdf_root / f"{year}-notes.pdf"
        extra_notes = extra_common + ["--variable", "geometry:margin=1.25in"]
        run_pandoc(tmp_file, notes_pdf, preamble_notes, extra_notes)
        print(f"→ Review PDF: {notes_pdf}")

    # Clean up temporary file
    try:
        tmp_file.unlink()
        if verbose:
            print(f"[verbose] Removed temporary file {tmp_file}")
    except Exception:
        pass


if __name__ == "__main__":
    main()
