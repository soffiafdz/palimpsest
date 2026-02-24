#!/usr/bin/env python3
"""
Palimpsest Pipeline CLI
------------------------

Unified command-line interface for the complete journal processing pipeline.

Orchestrates the full workflow:
1. inbox → Process raw exports (src → txt)
2. convert → Convert formatted text to Markdown (txt → md)
3. import-metadata → Import metadata YAML into database
4. build-pdf → Generate yearly PDFs (md → pdf)

Command Groups:
    - Source Processing: inbox
    - Text Conversion: convert
    - Database: import-metadata, prune-orphans
    - Export: export-json
    - PDF Generation: build-pdf, build-metadata-pdf
    - Maintenance: backup-full, backup-list-full, run-all, status, validate

Usage:
    # Run complete pipeline
    plm run-all

    # Individual steps (in order)
    plm inbox              # Process raw exports
    plm convert            # Convert to Markdown
    plm import-metadata    # Import metadata to database
    plm build-pdf 2025     # Generate PDFs

    # Database operations
    plm import-metadata
    plm prune-orphans
    plm export-json

    # Backups and maintenance
    plm backup-full
    plm backup-list-full
    plm status
    plm validate
"""
from __future__ import annotations

import click
from pathlib import Path

from dev.core.paths import LOG_DIR
from dev.core.cli import setup_logger


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
    """Palimpsest Journal Processing Pipeline"""
    ctx.ensure_object(dict)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["verbose"] = verbose
    ctx.obj["logger"] = setup_logger(Path(log_dir), "pipeline")


# Import and register commands from submodules
# These imports must come after CLI group definition
from .sources import inbox  # noqa: E402
from .text import convert  # noqa: E402
from .database import import_metadata, prune_orphans  # noqa: E402
from .export import export_json  # noqa: E402
from .pdf import build_pdf  # noqa: E402
from .metadata_pdf import build_metadata_pdf  # noqa: E402
from .maintenance import backup_full, backup_list_full, run_all, status, validate  # noqa: E402
from .wiki import wiki  # noqa: E402
from .metadata_yaml import metadata  # noqa: E402

# Register commands
cli.add_command(inbox)
cli.add_command(convert)
cli.add_command(import_metadata)
cli.add_command(export_json)
cli.add_command(prune_orphans)
cli.add_command(build_pdf)
cli.add_command(build_metadata_pdf)
cli.add_command(backup_full)
cli.add_command(backup_list_full)
cli.add_command(run_all)
cli.add_command(status)
cli.add_command(validate)
cli.add_command(wiki)
cli.add_command(metadata)


if __name__ == "__main__":
    cli(obj={})
