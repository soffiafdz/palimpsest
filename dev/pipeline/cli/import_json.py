#!/usr/bin/env python3
"""
import_json.py
--------------
CLI command for importing database entities from JSON export files.

Provides the ``plm import-json`` command that reads JSON files
produced by ``plm export-json`` and rebuilds the database using
upsert semantics (idempotent).

Commands:
    plm import-json                    - Import all entities
    plm import-json --dry-run          - Preview without writing

Usage:
    plm import-json
    plm import-json --input-dir path/to/exports
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from typing import Optional

# --- Third-party imports ---
import click

# --- Local imports ---
from dev.core.logging_manager import handle_cli_error
from dev.core.paths import ALEMBIC_DIR, BACKUP_DIR, DB_PATH, LOG_DIR


@click.command("import-json")
@click.option(
    "--input-dir",
    type=click.Path(exists=True),
    default=None,
    help="Input directory (defaults to data/exports)",
)
@click.pass_context
def import_json(ctx: click.Context, input_dir: Optional[str]) -> None:
    """
    Import database entities from JSON export files.

    Reads JSON files produced by ``plm export-json`` and imports them
    into the database using upsert semantics. Safe to run multiple
    times on the same data (idempotent).

    Examples:
        # Import from default exports directory
        plm import-json

        # Import from a specific directory
        plm import-json --input-dir path/to/exports
    """
    try:
        logger = ctx.obj["logger"]

        from dev.database.manager import PalimpsestDB
        from dev.pipeline.import_json import JSONImporter

        db = PalimpsestDB(
            db_path=DB_PATH,
            alembic_dir=ALEMBIC_DIR,
            log_dir=LOG_DIR,
            backup_dir=BACKUP_DIR,
            enable_auto_backup=False,
        )

        importer = JSONImporter(
            db,
            input_dir=Path(input_dir) if input_dir else None,
            logger=logger,
        )

        click.echo("Importing database entities from JSON...")
        stats = importer.import_all()

        click.echo("Import complete:")
        for entity_type, count in stats.items():
            if count > 0:
                click.echo(f"  {entity_type}: {count}")

    except Exception as e:
        handle_cli_error(ctx, e, "import_json")
