#!/usr/bin/env python3
"""
Palimpsest Database Management CLI
-----------------------------------

Modular command-line interface for database management.

This module provides the main CLI group and shared context setup
for all database commands.

Command Structure:
    - Setup & Initialization (setup)
    - Migration Management (migration)
    - Backup & Restore (backup, backups, restore)
    - Query & Browse (query)
    - Maintenance (maintenance)
    - Manuscript (manuscript)
    - Stats & Health (stats, health, optimize)

Usage:
    # Get general help
    metadb --help

    # Get help for a specific command group
    metadb query --help

    # Get help for a specific command
    metadb query show --help
"""
import click
import logging
from pathlib import Path

from dev.core.paths import DB_PATH, ALEMBIC_DIR, LOG_DIR, BACKUP_DIR
from dev.database import PalimpsestDB


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
    "--log-dir",
    type=click.Path(),
    default=str(LOG_DIR),
    help="Path to log directory",
)
@click.option(
    "--backup-dir",
    type=click.Path(),
    default=str(BACKUP_DIR),
    help="Path to backup directory",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Show detailed errors and tracebacks",
)
@click.pass_context
def cli(ctx, db_path, alembic_dir, log_dir, backup_dir, verbose):
    """Palimpsest Database Management CLI"""

    # Suppress Alembic INFO logging by default
    logging.getLogger("alembic").setLevel(logging.WARNING)

    ctx.ensure_object(dict)
    ctx.obj["db_path"] = Path(db_path)
    ctx.obj["alembic_dir"] = Path(alembic_dir)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["backup_dir"] = Path(backup_dir)
    ctx.obj["verbose"] = verbose


def get_db(ctx) -> PalimpsestDB:
    """Get or create database instance from context."""
    if "db" not in ctx.obj:
        ctx.obj["db"] = PalimpsestDB(
            db_path=ctx.obj["db_path"],
            alembic_dir=ctx.obj["alembic_dir"],
            log_dir=ctx.obj["log_dir"],
            backup_dir=ctx.obj["backup_dir"],
            enable_auto_backup=False,
        )
    return ctx.obj["db"]


# Import and register command modules
# These imports must come after CLI group definition
from .setup import init, reset  # noqa: E402
from .migration import migration  # noqa: E402
from .backup import backup, backups, restore  # noqa: E402
from .query import query  # noqa: E402
from .maintenance import maintenance, stats, health, optimize  # noqa: E402
from .prune import prune_orphans  # noqa: E402
from .manuscript import manuscript  # noqa: E402

# Register top-level commands
cli.add_command(init)
cli.add_command(reset)
cli.add_command(backup)
cli.add_command(backups)
cli.add_command(restore)
cli.add_command(stats)
cli.add_command(health)
cli.add_command(optimize)
cli.add_command(prune_orphans)

# Register command groups
cli.add_command(migration)
cli.add_command(query)
cli.add_command(maintenance)
cli.add_command(manuscript)


if __name__ == "__main__":
    cli(obj={})
