#!/usr/bin/env python3
"""
export.py
---------
Database export commands for the pipeline CLI.

Commands for exporting database content to JSON files for git version
control and cross-machine synchronization.

Commands:
    - export-json: Export all entities to JSON files

Usage:
    # Export all database entities
    plm export-json
"""
# --- Annotations ---
from __future__ import annotations

# --- Third-party imports ---
import click

# --- Local imports ---
from dev.core.logging_manager import handle_cli_error
from dev.core.paths import DB_PATH, ALEMBIC_DIR, LOG_DIR, BACKUP_DIR
from dev.database.manager import PalimpsestDB
from dev.pipeline.export_json import JSONExporter


@click.command("export-json")
@click.pass_context
def export_json(ctx: click.Context) -> None:
    """
    Export database entities to JSON files for version control.

    Exports all entities (entries, people, locations, scenes, events, etc.)
    to individual JSON files organized by entity type. These JSON exports
    are machine-generated files using IDs for relationships, designed for
    git version control and cross-machine database synchronization.

    Unlike metadata YAML files (human-authored ground truth), these JSON
    exports are machine-focused with ID-based relationships and automatic
    git commits with detailed README changelog.

    Examples:
        # Export all entities
        plm export-json
    """
    try:
        logger = ctx.obj["logger"]

        # Initialize database and exporter
        db = PalimpsestDB(
            db_path=DB_PATH,
            alembic_dir=ALEMBIC_DIR,
            log_dir=LOG_DIR,
            backup_dir=BACKUP_DIR,
            enable_auto_backup=False,
        )
        exporter = JSONExporter(db, logger=logger)

        # Execute export
        click.echo("Exporting all database entities to JSON...")
        exporter.export_all()
        click.echo("✅ Export complete - see data/exports/README.md for details")

    except Exception as e:
        handle_cli_error(ctx, e, "export_json")
