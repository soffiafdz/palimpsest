#!/usr/bin/env python3
"""
Palimpsest Pipeline CLI
------------------------

Unified command-line interface for the complete journal processing pipeline.

Orchestrates the full workflow:
1. Process inbox → Format raw exports
2. txt2md → Convert formatted text to Markdown
3. yaml2sql → Populate database from Markdown metadata
4. sql2yaml → Export database to Markdown
5. md2pdf → Generate yearly PDFs
6. Wiki export/import

Command Groups:
    - YAML→SQL: inbox, convert, sync-db
    - SQL→Wiki: export-db, export-wiki, build-pdf
    - Wiki→SQL: import-wiki
    - Maintenance: backup-full, backup-list-full, run-all, status, validate

Usage:
    # Run complete pipeline
    plm run-all

    # Individual steps
    plm inbox
    plm convert
    plm sync-db
    plm export-db
    plm build-pdf 2025

    # Wiki operations
    plm export-wiki
    plm import-wiki

    # Backups
    plm backup-full
    plm backup-list-full

    # Status and validation
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
from .yaml2sql import inbox, convert, sync_db
from .sql2wiki import export_db, export_wiki, build_pdf
from .wiki2sql import import_wiki
from .maintenance import backup_full, backup_list_full, run_all, status, validate

# Register commands
cli.add_command(inbox)
cli.add_command(convert)
cli.add_command(sync_db)
cli.add_command(export_db)
cli.add_command(export_wiki)
cli.add_command(build_pdf)
cli.add_command(import_wiki)
cli.add_command(backup_full)
cli.add_command(backup_list_full)
cli.add_command(run_all)
cli.add_command(status)
cli.add_command(validate)


if __name__ == "__main__":
    cli(obj={})
