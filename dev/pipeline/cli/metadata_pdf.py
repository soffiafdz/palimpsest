"""
Metadata PDF Generation Commands
---------------------------------

Commands for generating metadata curation PDFs from YAML files.

Commands:
    - build-metadata-pdf: Build metadata PDF from YAML (yaml → pdf)

Generates two-column PDF compilations of journal metadata (scenes, events,
themes, arcs, threads) for manuscript curation decisions.
"""
from __future__ import annotations

import click
from pathlib import Path

from dev.core.paths import JOURNAL_YAML_DIR, PDF_DIR, TEX_DIR
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.pipeline import metadata2pdf


@click.command("build-metadata-pdf")
@click.argument("year")
@click.option(
    "-i",
    "--input",
    type=click.Path(),
    default=str(JOURNAL_YAML_DIR),
    help="Input directory with YAML files",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=str(PDF_DIR),
    help="Output directory for PDF",
)
@click.option("-f", "--force", is_flag=True, help="Force overwrite existing PDF")
@click.option("--debug", is_flag=True, help="Keep temp files on error for debugging")
@click.pass_context
def build_metadata_pdf(
    ctx: click.Context,
    year: str,
    input: str,
    output: str,
    force: bool,
    debug: bool,
) -> None:
    """
    Build metadata curation PDF for a year.

    Generates a two-column PDF compilation of metadata (scenes, events,
    themes, arcs, threads) from YAML files for manuscript curation decisions.
    """
    logger: PalimpsestLogger = ctx.obj["logger"]

    click.echo(f"📋 Building metadata PDF for {year}...")

    try:
        stats = metadata2pdf.build_metadata_pdf(
            year=year,
            yaml_dir=Path(input),
            pdf_dir=Path(output),
            preamble=TEX_DIR / "preamble_metadata.tex",
            force_overwrite=force,
            keep_temp_on_error=debug,
            logger=logger,
        )

        click.echo("\n✅ Metadata PDF build complete:")
        click.echo(f"  YAML files processed: {stats.files_processed}")
        click.echo(f"  PDFs created: {stats.pdfs_created}")
        click.echo(f"  Duration: {stats.duration():.2f}s")

    except Exception as e:
        handle_cli_error(
            ctx,
            e,
            "build_metadata_pdf",
            additional_context={"year": year},
        )


__all__ = ["build_metadata_pdf"]
