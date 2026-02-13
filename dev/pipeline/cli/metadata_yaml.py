#!/usr/bin/env python3
"""
metadata_yaml.py
----------------
CLI commands for YAML metadata file management.

Provides the ``plm metadata`` command group for exporting, importing,
validating, and listing entity metadata as structured YAML files.

Commands:
    plm metadata export                    - Export all entity types
    plm metadata export --type people      - Export specific type
    plm metadata import <path>             - Import single file
    plm metadata import --type people      - Import all of a type
    plm metadata validate <path>           - Validate YAML file
    plm metadata list-entities --type people --format json

Usage:
    plm metadata export --type chapters
    plm metadata list-entities --type people --format json
    plm metadata validate data/metadata/people/clara.yaml
    plm metadata import data/metadata/people/clara.yaml
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import json
from pathlib import Path
from typing import Optional

# --- Third-party imports ---
import click

# --- Local imports ---
from dev.core.logging_manager import handle_cli_error
from dev.core.paths import DB_PATH


ENTITY_TYPES = [
    "people", "locations", "cities", "arcs",
    "chapters", "characters", "scenes",
]


@click.group()
@click.pass_context
def metadata(ctx: click.Context) -> None:
    """YAML metadata file management commands."""
    pass


@metadata.command()
@click.option(
    "--type",
    "entity_type",
    type=click.Choice(ENTITY_TYPES),
    default=None,
    help="Export only a specific entity type",
)
@click.option(
    "--output-dir",
    type=click.Path(),
    default=None,
    help="Output directory (defaults to data/metadata)",
)
@click.pass_context
def export(
    ctx: click.Context,
    entity_type: Optional[str],
    output_dir: Optional[str],
) -> None:
    """Export entity metadata to YAML files."""
    from dev.database.manager import PalimpsestDB
    from dev.wiki.metadata import MetadataExporter

    logger = ctx.obj.get("logger")

    try:
        db = PalimpsestDB(DB_PATH)
        exporter = MetadataExporter(
            db,
            output_dir=Path(output_dir) if output_dir else None,
            logger=logger,
        )
        exporter.export_all(entity_type=entity_type)

        click.echo("Metadata export complete.")
        for key, value in exporter.stats.items():
            click.echo(f"  {key}: {value}")

    except Exception as e:
        handle_cli_error(ctx, e, "metadata_export")
        raise


@metadata.command(name="import")
@click.argument("path", type=click.Path(exists=True), required=False)
@click.option(
    "--type",
    "entity_type",
    type=click.Choice(ENTITY_TYPES),
    default=None,
    help="Import all YAML files of a specific entity type",
)
@click.pass_context
def import_cmd(
    ctx: click.Context,
    path: Optional[str],
    entity_type: Optional[str],
) -> None:
    """Import YAML metadata files into database."""
    from dev.database.manager import PalimpsestDB
    from dev.wiki.metadata import MetadataImporter

    logger = ctx.obj.get("logger")

    if not path and not entity_type:
        raise click.UsageError(
            "Provide a file path or --type to specify what to import"
        )

    try:
        db = PalimpsestDB(DB_PATH)
        importer = MetadataImporter(db, logger=logger)

        if path:
            diagnostics = importer.import_file(Path(path))
            if any(d.severity == "error" for d in diagnostics):
                for d in diagnostics:
                    if d.severity == "error":
                        click.echo(
                            f"  ERROR [{d.code}] {d.message}", err=True
                        )
                raise SystemExit(1)
            click.echo(f"Imported: {path}")
        else:
            stats = importer.import_all(entity_type=entity_type)
            click.echo("Metadata import complete.")
            for key, value in stats.items():
                click.echo(f"  {key}: {value}")

    except SystemExit:
        raise
    except Exception as e:
        handle_cli_error(ctx, e, "metadata_import")
        raise


@metadata.command()
@click.argument("path", type=click.Path(exists=True))
@click.pass_context
def validate(ctx: click.Context, path: str) -> None:
    """Validate a YAML metadata file against its schema."""
    import json as json_mod

    from dev.wiki.metadata import MetadataValidator

    try:
        validator = MetadataValidator()
        diagnostics = validator.validate_file(Path(path))

        if not diagnostics:
            click.echo("Valid.")
            return

        for d in diagnostics:
            color = {
                "error": "red",
                "warning": "yellow",
                "info": "blue",
            }.get(d.severity, "white")
            click.echo(
                f"  {click.style(d.severity, fg=color)} "
                f"[{d.code}] {d.message}"
            )

        error_count = sum(1 for d in diagnostics if d.severity == "error")
        if error_count > 0:
            raise SystemExit(1)

    except SystemExit:
        raise
    except Exception as e:
        handle_cli_error(ctx, e, "metadata_validate")
        raise


@metadata.command(name="list-entities")
@click.option(
    "--type",
    "entity_type",
    type=click.Choice(ENTITY_TYPES),
    required=True,
    help="Entity type to list",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
@click.pass_context
def list_entities(
    ctx: click.Context,
    entity_type: str,
    output_format: str,
) -> None:
    """List entity names for autocomplete support."""
    from dev.database.manager import PalimpsestDB
    from dev.wiki.metadata import MetadataExporter

    try:
        db = PalimpsestDB(DB_PATH)
        exporter = MetadataExporter(db)
        names = exporter.list_entities(entity_type)

        if output_format == "json":
            click.echo(json.dumps(names))
        else:
            for name in names:
                click.echo(name)

    except Exception as e:
        handle_cli_error(ctx, e, "metadata_list_entities")
        raise
