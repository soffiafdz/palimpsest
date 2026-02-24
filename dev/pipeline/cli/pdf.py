"""
PDF Generation Commands
------------------------

Commands for generating PDF compilations from Markdown entries.

Commands:
    - build-pdf: Build yearly PDFs from Markdown (md → pdf)

This is a separate output pathway, independent of wiki operations.
"""
from __future__ import annotations

import click
from pathlib import Path

from dev.core.paths import MD_DIR, PDF_DIR, TEX_DIR
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.pipeline import md2pdf


@click.command("build-pdf")
@click.argument("year")
@click.option(
    "-i",
    "--input",
    type=click.Path(),
    default=str(MD_DIR),
    help="Input directory with Markdown files",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=str(PDF_DIR),
    help="Output directory for PDFs",
)
@click.option("-f", "--force", is_flag=True, help="Force overwrite existing PDFs")
@click.option("--debug", is_flag=True, help="Keep temp files on error for debugging")
@click.pass_context
def build_pdf(
    ctx: click.Context,
    year: str,
    input: str,
    output: str,
    force: bool,
    debug: bool,
) -> None:
    """
    Build clean and notes PDFs for a year.

    Generates professional typeset PDF documents from Markdown entries
    using Pandoc + LaTeX. Creates two versions: clean and notes.
    """
    logger: PalimpsestLogger = ctx.obj["logger"]

    click.echo(f"📚 Building PDFs for {year}...")

    try:
        stats = md2pdf.build_pdf(
            year=year,
            md_dir=Path(input),
            pdf_dir=Path(output),
            preamble=TEX_DIR / "preamble.tex",
            preamble_notes=TEX_DIR / "preamble_notes.tex",
            force_overwrite=force,
            keep_temp_on_error=debug,
            logger=logger,
        )

        click.echo("\n✅ PDF build complete:")
        click.echo(f"  Markdown entries: {stats.files_processed}")
        click.echo(f"  PDFs created: {stats.pdfs_created}")
        click.echo(f"  Duration: {stats.duration():.2f}s")

    except Exception as e:
        handle_cli_error(
            ctx,
            e,
            "build_pdf",
            additional_context={"year": year},
        )


__all__ = ["build_pdf"]
