#!/usr/bin/env python3
"""
Palimpsest Pipeline CLI
------------------------

Unified command-line interface for the complete journal processing pipeline.

Orchestrates the full workflow:
1. inbox → Process raw exports (src → txt)
2. convert → Convert formatted text to Markdown (txt → md)
3. sync → Synchronize DB with files and regenerate outputs
4. build pdf → Generate yearly PDFs (md → pdf)

Top-Level Commands:
    - inbox: Process raw exports
    - convert: Convert formatted text to Markdown
    - sync: Synchronize DB with files (JSON import → entries → metadata → export → wiki)
    - export: Export DB entities to JSON
    - status: Show pipeline status

Command Groups:
    - Build: build pdf, build metadata
    - DB: db init, db backup, db upgrade, ...
    - Pipeline: pipeline run
    - Wiki: wiki generate, wiki lint, wiki sync
    - Metadata: metadata export, metadata import, metadata validate, metadata list
    - Validate: validate pipeline, validate entry, validate db, ...

Usage:
    # Synchronize after git pull (replaces entries import + json export + wiki generate)
    plm sync

    # Run complete pipeline
    plm pipeline run

    # Individual steps (in order)
    plm inbox                  # Process raw exports
    plm convert                # Convert to Markdown
    plm sync                   # Synchronize everything
    plm build pdf 2025         # Generate PDFs

    # Database management
    plm db init
    plm db backup
    plm db stats

    # Backups and maintenance
    plm status
    plm validate
"""
from __future__ import annotations

import logging

import click
from pathlib import Path

from dev.core.paths import LOG_DIR, DB_PATH, ALEMBIC_DIR, BACKUP_DIR
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


# --- Command groups ---

@click.group()
@click.pass_context
def build(ctx: click.Context) -> None:
    """Build output files."""
    pass


@click.group()
@click.pass_context
def pipeline(ctx: click.Context) -> None:
    """Pipeline orchestration."""
    pass


@click.group()
@click.option(
    "--db-path",
    type=click.Path(),
    default=str(DB_PATH),
    help="Path to database file",
)
@click.option(
    "--alembic-dir",
    type=click.Path(),
    default=str(ALEMBIC_DIR),
    help="Path to Alembic directory",
)
@click.option(
    "--backup-dir",
    type=click.Path(),
    default=str(BACKUP_DIR),
    help="Path to backup directory",
)
@click.pass_context
def db(ctx: click.Context, db_path: str, alembic_dir: str, backup_dir: str) -> None:
    """Database management commands."""
    logging.getLogger("alembic").setLevel(logging.WARNING)
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = Path(db_path)
    ctx.obj["alembic_dir"] = Path(alembic_dir)
    ctx.obj["log_dir"] = ctx.obj.get("log_dir", Path(str(LOG_DIR)))
    ctx.obj["backup_dir"] = Path(backup_dir)


# Import and register commands from submodules
# These imports must come after CLI group definition
from .sources import inbox  # noqa: E402
from .text import convert  # noqa: E402
from .export import export_json  # noqa: E402
from .pdf import build_pdf  # noqa: E402
from .metadata_pdf import build_metadata_pdf  # noqa: E402
from .maintenance import run_pipeline, status, validate  # noqa: E402
from .wiki import wiki  # noqa: E402
from .metadata_yaml import metadata  # noqa: E402
from .sync import sync  # noqa: E402
from .manuscript import manuscript  # noqa: E402

# Import database CLI commands
from dev.database.cli.setup import init, reset  # noqa: E402
from dev.database.cli.migration import (  # noqa: E402
    create, upgrade, downgrade, migration_status, history,
)
from dev.database.cli.backup import backup, backups, restore  # noqa: E402
from dev.database.cli.query import show, years, months, batches  # noqa: E402
from dev.database.cli.maintenance import (  # noqa: E402
    stats as db_stats, health, optimize, analyze,
)
from dev.database.cli.prune import prune_orphans  # noqa: E402

# Register top-level commands
cli.add_command(inbox)
cli.add_command(convert)
cli.add_command(status)
cli.add_command(sync)
cli.add_command(export_json, "export")

# Register command groups
cli.add_command(build)
cli.add_command(pipeline)
cli.add_command(db)
cli.add_command(validate)
cli.add_command(wiki)
cli.add_command(metadata)
cli.add_command(manuscript)

# Register subcommands under groups
build.add_command(build_pdf)
build.add_command(build_metadata_pdf)
pipeline.add_command(run_pipeline)

# Register all DB subcommands (flattened from metadb)
db.add_command(init)
db.add_command(reset)
db.add_command(backup)
db.add_command(backups)
db.add_command(restore)
db.add_command(db_stats)
db.add_command(health)
db.add_command(optimize)
db.add_command(analyze)
db.add_command(prune_orphans)
db.add_command(create)
db.add_command(upgrade)
db.add_command(downgrade)
db.add_command(migration_status)
db.add_command(history)
db.add_command(show)
db.add_command(years)
db.add_command(months)
db.add_command(batches)


if __name__ == "__main__":
    cli(obj={})
