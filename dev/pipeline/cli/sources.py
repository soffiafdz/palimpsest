"""
Source Processing Commands
---------------------------

Commands for processing raw journal exports.

Commands:
    - inbox: Process raw exports (src → txt)

This is the first step in the pipeline: raw data → formatted text.
"""
from __future__ import annotations

import click
from pathlib import Path

from dev.core.paths import INBOX_DIR, ARCHIVE_DIR, TXT_DIR
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.pipeline.src2txt import process_inbox


@click.command()
@click.option(
    "--inbox",
    type=click.Path(),
    default=str(INBOX_DIR),
    help="Inbox directory with raw exports",
)
@click.option(
    "--output",
    type=click.Path(),
    default=str(TXT_DIR),
    help="Output directory for formatted text",
)
@click.pass_context
def inbox(ctx: click.Context, inbox: str, output: str) -> None:
    """
    Process inbox: format and organize raw 750words exports.

    This is STEP 1 of the pipeline - transforms raw text exports into
    organized monthly text files.
    """
    logger: PalimpsestLogger = ctx.obj["logger"]

    click.echo("📥 Processing inbox...")

    try:
        stats = process_inbox(
            inbox_dir=Path(inbox),
            output_dir=Path(output),
            archive_dir=ARCHIVE_DIR,
            logger=logger,
        )

        click.echo("\n✅ Inbox processing complete:")
        click.echo(f"  Files found: {stats.files_found}")
        click.echo(f"  Files processed: {stats.files_processed}")
        if stats.files_skipped > 0:
            click.echo(f"  Files skipped: {stats.files_skipped}")
        click.echo(f"  Years updated: {stats.years_updated}")
        if stats.errors > 0:
            click.echo(f"  ⚠️  Errors: {stats.errors}")
        click.echo(f"  Duration: {stats.duration():.2f}s")

    except Exception as e:
        handle_cli_error(ctx, e, "inbox")


__all__ = ["inbox"]
