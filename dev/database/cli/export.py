"""
Export Commands
---------------

Database export commands to various formats.

Commands:
    - csv: Export all tables to CSV files
    - json: Export complete database to JSON
"""
import click

from dev.core.logging_manager import handle_cli_error
from dev.core.exceptions import ExportError
from dev.database import ExportManager
from . import get_db


@click.group()
@click.pass_context
def export(ctx: click.Context) -> None:
    """Export database to various formats."""
    pass


@export.command("csv")
@click.argument("output_dir", type=click.Path())
@click.pass_context
def export_csv(ctx, output_dir):
    """Export all tables to CSV files."""
    try:
        db = get_db(ctx)
        click.echo(f"📤 Exporting to CSV: {output_dir}")

        with db.session_scope() as session:
            exported = ExportManager.export_to_csv(session, output_dir)

        click.echo(f"\n✅ Export Complete ({len(exported)} tables):")
        for table, path in exported.items():
            click.echo(f"  • {table}: {path}")

    except ExportError as e:
        handle_cli_error(
            ctx,
            e,
            "export_csv",
            additional_context={"output_dir": output_dir},
        )


@export.command("json")
@click.argument("output_file", type=click.Path())
@click.pass_context
def export_json(ctx, output_file):
    """Export complete database to JSON."""
    try:
        db = get_db(ctx)
        click.echo(f"📤 Exporting to JSON: {output_file}")

        export_mgr = ExportManager()
        with db.session_scope() as session:
            exported = export_mgr.export_to_json(session, output_file)

        click.echo(f"✅ Export complete: {exported}")

    except ExportError as e:
        handle_cli_error(
            ctx,
            e,
            "export_json",
            additional_context={"output_file": output_file},
        )
