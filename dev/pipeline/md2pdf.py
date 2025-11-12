#!/usr/bin/env python3
"""
md2pdf.py
-------------------
Generate yearly journal PDFs from Markdown entries.

Builds two PDF versions from daily Markdown files:
1. Clean PDF - Reading/archival version
2. Notes PDF - Annotation version with line numbers

Uses Pandoc with custom LaTeX preambles for professional typography.

Usage:
    # Build PDFs for a specific year
    python -m dev.pipeline.md2pdf build 2025

    # Build with custom directories
    python -m dev.pipeline.md2pdf build 2025 -i path/to/md -o path/to/pdf

    # Force overwrite existing PDFs
    python -m dev.pipeline.md2pdf build 2025 --force

    # Verbose output
    python -m dev.pipeline.md2pdf build 2025 -v
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import click
import sys
from pathlib import Path

# --- Local imports ---
from dev.core.paths import TEX_DIR, MD_DIR, PDF_DIR, LOG_DIR
from dev.core.exceptions import PdfBuildError
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.core.cli_utils import setup_logger
from dev.builders.pdfbuilder import PdfBuilder, BuildStats


@click.group()
@click.option(
    "--log-dir",
    type=click.Path(),
    default=str(LOG_DIR),
    help="Directory for log files",
)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
@click.pass_context
def cli(ctx: click.Context, log_dir: str, verbose: bool) -> None:
    """md2pdf - Generate yearly journal PDFs from Markdown"""
    ctx.ensure_object(dict)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["verbose"] = verbose
    ctx.obj["logger"] = setup_logger(Path(log_dir), "md2pdf")


@cli.command()
@click.argument("year")
@click.option(
    "-i",
    "--input",
    type=click.Path(),
    default=str(MD_DIR),
    help=f"Markdown source directory (default: {MD_DIR})",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=str(PDF_DIR),
    help=f"PDF output directory (default: {PDF_DIR})",
)
@click.option(
    "--preamble",
    type=click.Path(exists=True),
    default=str(TEX_DIR / "preamble.tex"),
    help="LaTeX preamble for clean PDF",
)
@click.option(
    "--preamble-notes",
    type=click.Path(exists=True),
    default=str(TEX_DIR / "preamble_notes.tex"),
    help="LaTeX preamble for notes PDF",
)
@click.option("-f", "--force", is_flag=True, help="Force overwrite existing PDFs")
@click.option("--debug", is_flag=True, help="Keep temp files on error for debugging")
@click.pass_context
def build(
    ctx: click.Context,
    year: str,
    input: str,
    output: str,
    preamble: str,
    preamble_notes: str,
    force: bool,
    debug: bool,
) -> None:
    """Build clean and notes PDFs for a specific year."""
    logger: PalimpsestLogger = ctx.obj["logger"]

    try:
        # Validate year format
        if not year.isdigit() or len(year) != 4:
            raise PdfBuildError(f"Invalid year format: {year} (expected YYYY)")

        input_dir = Path(input)
        output_dir = Path(output)
        preamble_path = Path(preamble) if preamble else None
        preamble_notes_path = Path(preamble_notes) if preamble_notes else None

        click.echo(f"📚 Building PDFs for year {year}")

        # Create builder
        builder = PdfBuilder(
            year=year,
            md_dir=input_dir,
            pdf_dir=output_dir,
            preamble=preamble_path,
            preamble_notes=preamble_notes_path,
            force_overwrite=force,
            keep_temp_on_error=debug,
            logger=logger,
        )

        # Execute build
        stats: BuildStats = builder.build()

        # Report results
        click.echo("\n✅ PDF build complete:")
        click.echo(f"  Markdown entries: {stats.files_processed}")
        click.echo(f"  PDFs created: {stats.pdfs_created}")

        if stats.pdfs_created > 0:
            if preamble_path:
                clean_pdf = output_dir / f"{year}.pdf"
                click.echo(f"  📄 Clean PDF: {clean_pdf}")
            if preamble_notes_path:
                notes_pdf = output_dir / f"{year}-notes.pdf"
                click.echo(f"  📝 Notes PDF: {notes_pdf}")

        if stats.errors > 0:
            click.echo(f"  ⚠️  Errors: {stats.errors}")

        click.echo(f"  Duration: {stats.duration():.2f}s")

    except (PdfBuildError, Exception) as e:
        handle_cli_error(ctx, e, "build_pdf", {"year": year})


@cli.command()
@click.argument("year")
@click.option(
    "-i",
    "--input",
    type=click.Path(),
    default=str(MD_DIR),
    help=f"Markdown source directory (default: {MD_DIR})",
)
@click.pass_context
def validate(ctx: click.Context, year: str, input: str) -> None:
    """Validate Markdown files for a specific year."""
    try:
        # Validate year format
        if not year.isdigit() or len(year) != 4:
            raise PdfBuildError(f"Invalid year format: {year} (expected YYYY)")

        input_dir = Path(input)
        year_dir = input_dir / year

        click.echo(f"🔍 Validating Markdown files for {year}")

        if not year_dir.exists():
            click.echo(f"❌ Directory not found: {year_dir}", err=True)
            sys.exit(1)

        # Find all markdown files
        md_files = sorted(year_dir.glob(f"{year}-*.md"))

        if not md_files:
            click.echo(f"⚠️  No Markdown files found in {year_dir}")
            return

        click.echo(f"Found {len(md_files)} entries")

        # Basic validation
        malformed = []
        for md_file in md_files:
            parts = md_file.stem.split("-")
            if len(parts) != 3:
                malformed.append(md_file.name)

        if malformed:
            click.echo(f"\n⚠️  Malformed filenames ({len(malformed)}):")
            for filename in malformed:
                click.echo(f"  • {filename}")
        else:
            click.echo("\n✅ All filenames valid")

        # Date range
        if md_files:
            first_entry = md_files[0].stem
            last_entry = md_files[-1].stem
            click.echo(f"\nDate range: {first_entry} to {last_entry}")

    except (PdfBuildError, Exception) as e:
        handle_cli_error(ctx, e, "validate_pdf", {"year": year})


if __name__ == "__main__":
    cli(obj={})
