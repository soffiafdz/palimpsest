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
    if not md_year.is_dir():
        sys.stderr.write(f"Error: no directory {md_year}\n")
        sys.exit(1)
    files = sorted(md_year.glob(f"{year}-*.md"))
    if not files:
        sys.stderr.write(f"Error: no Markdown files in {md_year}\n")
        sys.exit(1)
    return files

def write_temp_md(files: Sequence[Path], tmp_path: Path, year: str) -> None:
    """
    input:
        files: sequence of Paths to per-entry Markdown files
        tmp_path: Path to a temporary .md file to write
        year: the target year string for title
    output:
        None (writes concatenated Markdown to tmp_path)
    process:
        - Writes a title page ("% Journal Entries — {year}").
        - Inserts a Pandoc table of contents directive.
        - For each file: writes "\newpage" + blank line, then the file’s contents.
    """
    with open(tmp_path, "w") as tmp:
        tmp.write(f"% Journal Entries — {year}\n")
        tmp.write("\\tableofcontents\n\n")
        for f in files:
            tmp.write("\\newpage\n\n")
            tmp.write(f.read_text(encoding="utf-8"))
            tmp.write("\n\n")

def run_pandoc(
    src_md: Path,
    dest_pdf: Path,
    preamble: Path,
    extra_args_base: Sequence[str]
) -> None:
    """
    input:
        src_md: Path to the source Markdown file
        dest_pdf: Path where the PDF should be written
        preamble: Path to a LaTeX preamble file to include
        extra_args_base: list of additional Pandoc arguments
            (e.g. ["--toc", "--toc-depth", "2"])
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
        help="Root directory of Markdown files"
    )
    parser.add_argument(
        "-o", "--outdir",
        help="Directory to write PDFs into"
    )
    parser.add_argument(
        "--preamble",
        default="latex/preamble.tex",
        help="Path to LaTeX preamble for clean PDF"
    )
    parser.add_argument(
        "--preamble-notes",
        default="latex/preamble_notes.tex",
        help="Path to LaTeX preamble for review-notes PDF"
    )
    args = parser.parse_args()

    year: str = args.year
    md_root: Path = Path(args.indir)
    pdf_root: Path = Path(args.outdir)
    preamble_clean: Path = Path(args.preamble)
    preamble_notes: Path = Path(args.preamble_notes)

    # Ensure output directory exists
    try:
        pdf_root.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        sys.stderr.write(
            f"Error creating PDF output directory {pdf_root}: {e}\n"
        )
        sys.exit(1)

    # Gather Markdown files
    files: List[Path] = gather_md(year, md_root)

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
    clean_pdf: Path = pdf_root / f"{year}.pdf"
    run_pandoc(tmp_file, clean_pdf, preamble_clean, extra_common)
    print(f"→ Clean PDF: {clean_pdf}")

    # 2) Review-notes PDF
    notes_pdf: Path = pdf_root / f"{year}-notes.pdf"
    extra_notes = extra_common + ["--variable", "geometry:margin=1.25in"]
    run_pandoc(tmp_file, notes_pdf, preamble_notes, extra_notes)
    print(f"→ Review PDF: {notes_pdf}")

    # Clean up temporary file
    try:
        tmp_file.unlink()
    except Exception:
        pass

if __name__ == "__main__":
    main()
