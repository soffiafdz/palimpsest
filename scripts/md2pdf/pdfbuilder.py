#!/usr/bin/env python3
"""
pdfbuilder.py
-------------------

Module containing the PdfBuilder class for assembling and exporting journal
entries from Markdown files to PDF. Supports generating both a clean PDF and a
review-notes PDF with line numbers and custom LaTeX preambles.

Intended for use as a library module; can be imported and used by CLI scripts,
unit tests, or other interfaces.

Typical usage example:
    builder = PdfBuilder(
        year="2025",
        md_dir=Path("journal/md"),
        pdf_dir=Path("journal/pdf"),
        preamble=Path("journal/latex/preamble.tex")
        preamble_notes=Path("journal/latex/preamble_notes.tex")
        verbose=True
    )
    builder.build()

Classes:
    PdfBuilder -- main class encapsulating the build process
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import calendar
import tempfile
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Sequence, Optional

# --- Third party ---
from pypandoc import convert_file


# ---- Class definition ----
class PdfBuilder:
    """
    PdfBuilder assembles, concatenates, and exports a year's worth of journal
    entries from Markdown files into formatted PDFs.

    Attributes:
        year (str): Target year (e.g. '2025').
        md_dir (Path): Path to root directory containing Markdown files.
        pdf_dir (Path): Output directory for resulting PDFs.
        preamble (Path, optional): Path to the LaTeX preamble file.
        preamble_notes (Path, optional):
            Path to the LaTeX preamble file for notes.
        verbose (bool, optional): If True, print progress messages.
        clobber (bool, optional):
            If True, overwrite existing notes PDF.
            Regular PDF is always overwritten.

    Methods:
        gather_md():
            Locate and return all Markdown files for the target year.

        write_temp_md(files, tmp_path, notes=False):
            Concatenate Markdown files for export, optionally inserting notes formatting.

        run_pandoc(src_md, metadata, extra_args):
            Convert Markdown file to PDF using Pandoc with specified settings.

        build():
            Run the complete build process for both clean and notes PDFs.
    """

    # --- Initialization ---
    def __init__(
        self,
        year: str,
        md_dir: Path,
        pdf_dir: Path,
        preamble: Optional[Path],
        preamble_notes: Optional[Path],
        verbose: bool = False,
        clobber: bool = False
    ):
        """
        Initialize a PdfBuilder instance.

        Args:
            year (str): Year of the journal to build (e.g., '2025').
            md_dir (Path): Directory where Markdown files are stored.
            preamble (Path, optional): Path to the LaTeX preamble file.
            preamble_notes (Path, optional):
                Path to the LaTeX preamble file (Notes).
            notes (bool, optional): Whether output will be a notes PDF.
            verbose (bool, optional): Enable verbose output. Defaults to False.
        """
        self.year = year
        self.md_dir = md_dir
        self.pdf_dir = pdf_dir
        self.preamble = preamble
        self.preamble_notes = preamble_notes
        self.verbose = verbose
        self.clobber = clobber


    # --- Methods ---
    def gather_md(self) -> Sequence[Path]:
        """
        Collect all Markdown files for the specified year.

        Returns:
            Sequence[Path]: Sorted list of Markdown file paths for the year.

        Raises:
            FileNotFoundError:
                If the year's directory or no Markdown files are found.
        """
        md_year = self.md_dir / self.year

        if self.verbose:
            print(f"[PdfBuilder] →  Looking into: {str(md_year)}")

        if not md_year.exists() or not md_year.is_dir():
            raise FileNotFoundError(
                f"Markdown directory not found: {str(md_year)}\n"
            )

        files = sorted(md_year.glob(f"{self.year}-*.md"))

        if not files:
            raise FileNotFoundError(
                f"No Markdown files found in {str(md_year)}\n"
            )

        if self.verbose:
            print(f"[PdfBuilder] →  Found {len(files)} Markdown entries")

        return files


    def write_temp_md(
        self,
        files: Sequence[Path],
        tmp_path: Path,
        notes: bool = False
    ) -> None:
        """
        Concatenate a list of Markdown files into a single file, optionally
        adding formatting for review-notes (line numbers, directives).

        Args:
            files (Sequence[Path]): List of daily Markdown files to concatenate.
            tmp_path (Path): Path to the temporary Markdown file to create.
            notes (bool, optional):
                If True, include notes formatting. Defaults to False.

        Returns:
            None

        Raises:
            OSError: If the file cannot be opened or written to.
        """
        if self.verbose:
            md_type: str = "Markdown (notes)" if notes else "Markdown"
            print(
                "[PdfBuilder] →  "
                f"Preparing concatenated {md_type} on {tmp_path}"
            )

        if self.verbose:
            print(
                f"[PdfBuilder] →  Concatenating {len(files)} files"
            )
        months: Dict[str, List[Path]] = defaultdict(list)
        for md in sorted(files):
            parts = md.stem.split("-")
            if len(parts) < 2:
                # Not viable YYYY-MM-DD format; skip
                warnings.warn(
                    f"Skipping entry ({md.stem}) with no viable date",
                    UserWarning
                )
                continue
            _, month_str, *_ = parts
            months[month_str].append(md)
        if self.verbose:
            print(
                "[PdfBuilder] →  "
                f"Grouped {len(months)} months for year {self.year}"
            )

        if self.verbose:
            print(
                f"[PdfBuilder] →  Writing Markdown file on {str(tmp_path)}"
            )

        annotations_preamble: List[str] = [
            "",
            "- **Status**: discard | reference | fragments | source | quote",
            "- **People**: "
" __________________________________________________________________________",
            "- **Tags**: "
" ____________________________________________________________________________",
            "- **Themes**: "
" _________________________________________________________________________",
            "- **Epigraph**: "
" ________________________________________________________________________",
            "- **References**: "
" ______________________________________________________________________",
            "",
            "---",
            "",
        ]
        with tmp_path.open("w", encoding="utf-8") as tmp:
            # Per-month chapters
            for month_str in sorted(months.keys(), key=lambda m: int(m)):
                month_name = calendar.month_name[int(month_str)]

                tmp.write("\\newpage\n\n")
                if notes:
                    tmp.write("\\nolinenumbers\n")
                # level-1 CH heading
                tmp.write(f"# {month_name}, {self.year}\n\n")

                # dump each daily entry in that month
                first_day = True
                for md_file in months[month_str]:
                    content = md_file.read_text(encoding="utf-8")

                    if notes:
                        lines = content.splitlines()
                        updated_lines = []
                        inserted = False

                        for ln in lines:
                            if ln.startswith("##") and not inserted:
                                if not first_day:
                                    updated_lines.append("\\newpage")
                                updated_lines.extend([
                                    "\\nolinenumbers",
                                    ln
                                ])
                                updated_lines.extend(annotations_preamble)
                                updated_lines.extend([
                                    "\\setcounter{linenumber}{1}",
                                    "\\linenumbers"
                                ])
                                inserted = True
                                first_day = False
                            else:
                                updated_lines.append(ln)

                        tmp.write("\n".join(updated_lines))
                    else:
                        tmp.write(content)
                    tmp.write("\n\n")

            tmp.write("\\newpage\n\n")
            if notes:
                tmp.write("\\nolinenumbers\n")
            tmp.write("\\tableofcontents\n")


    def run_pandoc(
        self,
        in_md: Path,
        out_pdf: Path,
        preamble: Path,
        metadata: Sequence[str],
        extra_args: Sequence[str]
    ) -> None:
        """
        Generate a PDF from a Markdown file using Pandoc with LaTeX options.

        Args:
            in_md (Path): Path to the source Markdown file.
            out_pdf (Path): Path to the output PDF file.
            preamble (Path): Path to the LaTeX preamble file.
            metadata (Sequence[str]): List of metadata strings for Pandoc.
            extra_args (Sequence[str]): Additional Pandoc command-line arguments.

        Returns:
            None

        Raises:
            FileNotFoundError: If input Markdown is not found.
            RuntimeError: If Pandoc conversion fails.
            OSError: If Pandoc executable is not found or file access error.
        """
        if not in_md.is_file():
            raise FileNotFoundError(
                f"Markdown file not found: {str(in_md)}\n"
            )

        args: Sequence[str] = [
            "--from", "markdown",
            "--pdf-engine", "xelatex",
            "--include-in-header", str(preamble),
            "--variable", "documentclass:extarticle"
        ] + list(metadata) + list(extra_args)

        if self.verbose:
            cmd_str = (
                "pandoc " + " ".join(args) +
                f" {str(in_md)} -o {str(out_pdf)}"
            )
            print(f"[PdfBuilder] →  Running Pandoc command:\n  {cmd_str}")

        try:
            convert_file(
                str(in_md),
                to="pdf",
                outputfile=str(out_pdf),
                extra_args=args
            )
        except (OSError, RuntimeError) as e:
            # Add context and re-raise
            raise RuntimeError(
                "[PdfBuilder] →  Pandoc failed to convert "
                f"{in_md} → {out_pdf}: {e}"
            ) from e


    def build(self) -> None:
        """
        Execute the complete process:
            - Gather Markdown files for the year
            - Build concatenated Markdown
            - Run Pandoc for clean and notes PDFs
            - Output results to the PDF directory

        Returns:
            None

        Raises:
            Exception: On file I/O or conversion failures.
        """
        if not self.preamble.is_file() and not self.preamble_notes.is_file():
            raise FileNotFoundError("Preamble file(s) not found")

        if self.verbose:
            print(f"[PdfBuilder] →  Markdown dir: {self.md_dir}")
            print(f"[PdfBuilder] →  PDF output dir: {self.pdf_dir}")
            if self.preamble.is_file():
                print(f"[PdfBuilder] →  Preamble: {str(self.preamble)}")
            if self.preamble_notes.is_file():
                print(
                    "[PdfBuilder] →  Preamble (Notes): "
                    f"{str(self.preamble_notes)}"
                )

        # Ensure output directory exists
        try:
            self.pdf_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise OSError(
                f"Error creating PDF output directory {self.pdf_dir}: {e}"
            )

        # Common Pandoc args: TOC, margins, font size
        metadata = [
            "--metadata", "title: Palimpsest",
            "--metadata",
            f"date: {self.year} — {int(self.year) - 1993} years old",
            "--metadata", "author: Sofía F."
        ]

        extra_clean = [
            "--variable", "fontsize:12pt",
        ]

        extra_notes = [
            "--variable", "fontsize:12pt",
            "--variable", "linestretch:1.9"
        ]

        # Gather Markdown files
        files = self.gather_md()

        # Build a temporary concatenated Markdown for:
        tmp_file_clean: Optional[Path] = None
        tmp_file_notes: Optional[Path] = None

        # 1) Clean PDF
        clean_pdf: Path = self.pdf_dir / f"{self.year}.pdf"
        if self.preamble.is_file():
            if clean_pdf.exists():
                warnings.warn(
                    f"Warning: Clean PDF already exists: {clean_pdf}. "
                    "Overwritting it.",
                    UserWarning
                )
                clean_pdf.unlink()

            tmp_file_clean = Path(
                tempfile.NamedTemporaryFile(suffix=".md", delete=False).name
            )
            self.write_temp_md(files, tmp_file_clean)
            self.run_pandoc(
                in_md=tmp_file_clean,
                out_pdf=clean_pdf,
                preamble=self.preamble,
                metadata=metadata,
                extra_args=extra_clean
            )
            if self.verbose:
                print(f"[PdfBuilder] →  Clean PDF: {str(clean_pdf)}")

        # 2) Review-notes PDF
        notes_pdf: Path = self.pdf_dir / f"{self.year}-notes.pdf"
        if self.preamble_notes.is_file():
            if notes_pdf.exists() and not self.clobber:
                 warnings.warn(
                    "Warning: Notes PDF already exists and clobber is not set: "
                    f"{notes_pdf}. Skipping.",
                    UserWarning
                )
            else:
                tmp_file_notes = Path(
                    tempfile.NamedTemporaryFile(suffix=".md", delete=False).name
                )
                self.write_temp_md(files, tmp_file_notes, notes=True)
                self.run_pandoc(
                    in_md=tmp_file_notes,
                    out_pdf=notes_pdf,
                    preamble=self.preamble_notes,
                    metadata=metadata,
                    extra_args=extra_notes
                )
                if self.verbose:
                    print(f"[PdfBuilder] →  Review PDF: {str(notes_pdf)}")

        # Clean up temporary file
        for tmp_file in (tmp_file_clean, tmp_file_notes):
            if tmp_file is not None and tmp_file.is_file():
                try:
                    tmp_file.unlink()
                    if self.verbose:
                        print(
                            f"[PdfBuilder] →  Removed temporary file {tmp_file}"
                        )
                except Exception:
                    pass
