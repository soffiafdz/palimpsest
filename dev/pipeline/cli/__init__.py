#!/usr/bin/env python3
"""
Palimpsest Pipeline CLI
------------------------

Unified command-line interface for the complete journal processing pipeline.

Orchestrates the full workflow:
1. inbox → Process raw exports (src → txt)
2. convert → Convert formatted text to Markdown (txt → md)
3. sync-db → Populate database from Markdown metadata (yaml → SQL)
4. export-db → Export database to Markdown (SQL → yaml)
5. export-wiki → Export database entities to vimwiki (SQL → wiki)
6. import-wiki → Import wiki edits back to database (wiki → SQL)
7. build-pdf → Generate yearly PDFs (md → pdf)

Command Groups:
    - Source Processing: inbox
    - Text Conversion: convert
    - Database Sync: sync-db, export-db
    - Wiki Sync: export-wiki, import-wiki
    - PDF Generation: build-pdf
    - Curation: curation extract, curation validate, curation consolidate,
                curation import, curation summary
    - Maintenance: backup-full, backup-list-full, run-all, status, validate

Usage:
    # Run complete pipeline
    plm run-all

    # Individual steps (in order)
    plm inbox              # Process raw exports
    plm convert            # Convert to Markdown
    plm sync-db            # Sync to database
    plm export-wiki all    # Export to wiki
    plm build-pdf 2025     # Generate PDFs

    # Wiki operations
    plm export-wiki people
    plm import-wiki entries

    # Database operations
    plm export-db
    plm sync-db

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
from .database import sync_db, export_db, import_metadata, prune_orphans  # noqa: E402
from .export import export_json  # noqa: E402
from .wiki import export_wiki, import_wiki  # noqa: E402
from .pdf import build_pdf  # noqa: E402
from .maintenance import backup_full, backup_list_full, run_all, status, validate  # noqa: E402
from .narrative_structure import narrative  # noqa: E402

# Register commands
cli.add_command(inbox)
cli.add_command(convert)
cli.add_command(sync_db)
cli.add_command(export_db)
cli.add_command(import_metadata)
cli.add_command(export_json)
cli.add_command(prune_orphans)
cli.add_command(export_wiki)
cli.add_command(import_wiki)
cli.add_command(build_pdf)
cli.add_command(backup_full)
cli.add_command(backup_list_full)
cli.add_command(run_all)
cli.add_command(status)
cli.add_command(validate)
cli.add_command(narrative)


if __name__ == "__main__":
    cli(obj={})
