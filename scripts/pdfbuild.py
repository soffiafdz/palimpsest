#!/usr/bin/env python3
"""
build_pdf.py

Generate both a clean PDF and a review-notes PDF for a given year.
"""

import argparse
import sys
import tempfile
import re
import calendar
from pathlib import Path
from collections import defaultdict
from typing import List, Sequence

import pypandoc

# Determine project root relative to /scripts
SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parent.parent

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
    notes: bool = False,
    verbose: bool = False
) -> None:
    """
    input:
        files: sequence of Paths to per-entry Markdown files
        tmp_path: Path to a temporary .md file to write
        year: the target year string for title
        notes: if the markdown file will be used for the notes version
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

    # Group daily files by month
    months: dict[str, list[Path]] = defaultdict(list)
    for md in sorted(files):
        parts = md.stem.split("-")
        if len(parts) < 2:
            # Not viable YYYY-MM-DD format; skip
            continue
        _, month_str, *_ = parts
        months[month_str].append(md)

    with tmp_path.open("w", encoding="utf-8") as tmp:
        # Per-month chapters
        for month_str in sorted(months.keys(), key=lambda m: int(m)):
            month_name = calendar.month_name[int(month_str)]

            tmp.write("\\newpage\n\n")
            if notes:
                tmp.write("\\nolinenumbers\n")
            tmp.write(f"# {month_name}, {year}\n\n")  # level-1 CH heading

            # dump each daily entry in that month
            for md_file in months[month_str]:
                content = md_file.read_text(encoding="utf-8")

                if notes:
                    lines = content.splitlines()
                    updated_lines = []
                    inserted = False

                    for line in lines:
                        if line.startswith("##") and not inserted:
                            updated_lines.append("\\nolinenumbers")
                            updated_lines.append(line)
                            updated_lines.append("\\setcounter{linenumber}{1}")
                            updated_lines.append("\\linenumbers")
                            inserted = True
                        else:
                            updated_lines.append(line)

                    tmp.write("\n".join(updated_lines))
                else:
                    tmp.write(content)
                tmp.write("\n\n")

        tmp.write("\\newpage\n\n")
        if notes:
            tmp.write("\\nolinenumbers\n")
        tmp.write("\\tableofcontents\n")


def run_pandoc(
    src_md: Path,
    dest_pdf: Path,
    preamble: Path,
    metadata: Sequence[str],
    extra_args: Sequence[str],
    verbose: bool = False
) -> None:
    """
    input:
        src_md: Path to the source Markdown file
        dest_pdf: Path where the PDF should be written
        preamble: Path to a LaTeX preamble file to include
        metadata: List with title, author, date
        extra_args: list of additional Pandoc arguments
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
        "--variable", "documentclass:extarticle"
    ] + list(metadata) + list(extra_args)
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
    # Common Pandoc args: TOC, margins, font size
    metadata = [
        "--metadata", "title: Palimpsest",
        "--metadata", f"date: {year} — {int(year) - 1993} years old",
        "--metadata", "author: Sofía F."
    ]

    extra_clean = [
        "--variable", "fontsize:12pt",
    ]

    extra_notes = [
        "--variable", "fontsize:14pt",
    ]

    # 1) Clean PDF
    if preamble_clean.is_file():
        tmp_file_clean = Path(
            tempfile.NamedTemporaryFile(suffix=".md", delete=False).name
        )
        write_temp_md(files, tmp_file_clean, year, False, verbose)
        clean_pdf: Path = pdf_root / f"{year}.pdf"
        run_pandoc(
            tmp_file_clean,
            clean_pdf,
            preamble_clean,
            metadata,
            extra_clean,
            verbose
        )
        print(f"→ Clean PDF: {clean_pdf}")

    # 2) Review-notes PDF
    if preamble_notes.is_file():
        tmp_file_notes = Path(
            tempfile.NamedTemporaryFile(suffix=".md", delete=False).name
        )
        write_temp_md(files, tmp_file_notes, year, True, verbose)
        notes_pdf: Path = pdf_root / f"{year}-notes.pdf"
        run_pandoc(
            tmp_file_notes,
            notes_pdf,
            preamble_notes,
            metadata,
            extra_notes,
            verbose
        )
        print(f"→ Review PDF: {notes_pdf}")

    # Clean up temporary file
    try:
        if tmp_file_clean.is_file():
            tmp_file_clean.unlink()
            if verbose:
                print(f"Removed temporary file {tmp_file_clean}")

        if tmp_file_notes.is_file():
            tmp_file_notes.unlink()
            if verbose:
                print(f"Removed temporary file {tmp_file_notes}")
    except Exception:
        pass


if __name__ == "__main__":
    main()
