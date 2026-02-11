"""
Text Conversion Commands
-------------------------

Commands for converting formatted text to Markdown.

Commands:
    - convert: Convert text to Markdown (txt → md)

This is the second step in the pipeline: formatted text → Markdown with metadata.
"""
from __future__ import annotations

import click
from pathlib import Path

from dev.core.paths import TXT_DIR, MD_DIR, JOURNAL_YAML_DIR
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.pipeline.txt2md import convert_directory, convert_file


@click.command()
@click.option(
    "-i",
    "--input",
    type=click.Path(),
    default=str(TXT_DIR),
    help="Input directory with formatted text files",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=str(MD_DIR),
    help="Output directory for Markdown files",
)
@click.option("-f", "--force", is_flag=True, help="Force overwrite existing files")
@click.option("--dry-run", is_flag=True, help="Preview changes without modifying files")
@click.option(
    "--yaml-dir",
    type=click.Path(),
    default=str(JOURNAL_YAML_DIR),
    show_default=True,
    help="Output directory for YAML metadata skeletons",
)
@click.option(
    "--no-yaml",
    is_flag=True,
    help="Disable YAML skeleton generation",
)
@click.pass_context
def convert(
    ctx: click.Context,
    input: str,
    output: str,
    force: bool,
    dry_run: bool,
    yaml_dir: str,
    no_yaml: bool,
) -> None:
    """
    Convert formatted text to Markdown entries.

    This is STEP 2 of the pipeline - transforms monthly text files into
    individual daily Markdown files with minimal YAML frontmatter.
    """
    logger: PalimpsestLogger = ctx.obj["logger"]

    # Resolve yaml_dir: None if disabled, Path otherwise
    resolved_yaml_dir = None if no_yaml else Path(yaml_dir)

    if dry_run:
        click.echo("📝 Converting text to Markdown (DRY RUN - no files will be modified)...")
        click.echo()
        input_path = Path(input)

        if input_path.is_dir():
            txt_files = sorted(input_path.rglob("*.txt"))
            click.echo(f"Would process {len(txt_files)} .txt files:")
            for txt_file in txt_files:
                click.echo(f"  • {txt_file.relative_to(input_path)}")
        elif input_path.is_file():
            click.echo("Would process 1 file:")
            click.echo(f"  • {input_path.name}")

        click.echo(f"\nOutput directory: {output}")
        if resolved_yaml_dir:
            click.echo(f"YAML skeleton directory: {resolved_yaml_dir}")
        else:
            click.echo("YAML skeletons: disabled")
        click.echo(f"Force overwrite: {force}")
        click.echo("\n💡 Run without --dry-run to execute conversion")
        return

    click.echo("📝 Converting text to Markdown...")

    try:
        stats = None
        input_path = Path(input)
        if input_path.is_dir():
            stats = convert_directory(
                input_dir=input_path,
                output_dir=Path(output),
                force_overwrite=force,
                logger=logger,
                yaml_dir=resolved_yaml_dir,
            )

        if input_path.is_file():
            stats = convert_file(
                input_path=input_path,
                output_dir=Path(output),
                force_overwrite=force,
                logger=logger,
                yaml_dir=resolved_yaml_dir,
            )

        if stats:
            click.echo("\n✅ Conversion complete:")
            click.echo(f"  Files processed: {stats.files_processed}")
            click.echo(f"  Entries created: {stats.entries_created}")
            if stats.skeletons_created or stats.skeletons_skipped:
                click.echo(f"  Skeletons created: {stats.skeletons_created}")
                click.echo(f"  Skeletons skipped: {stats.skeletons_skipped}")
            click.echo(f"  Duration: {stats.duration():.2f}s")

    except Exception as e:
        handle_cli_error(
            ctx,
            e,
            "convert",
            additional_context={"input": input, "output": output},
        )


__all__ = ["convert"]
