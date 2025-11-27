"""
Setup & Initialization Commands
--------------------------------

Database and Alembic initialization commands.

Commands:
    - init: Initialize database and Alembic
    - reset: Reset database (dangerous!)
"""
import click
from pathlib import Path

from dev.core.logging_manager import handle_cli_error
from dev.core.exceptions import DatabaseError
from . import get_db


@click.command()
@click.option("--alembic-only", is_flag=True, help="Initialize Alembic only")
@click.option("--db-only", is_flag=True, help="Initialize database only")
@click.pass_context
def init(ctx, alembic_only, db_only):
    """Initialize database and Alembic (complete setup)."""
    try:
        db = get_db(ctx)

        if alembic_only:
            click.echo("📁 Initializing Alembic...")
            db.init_alembic()
            click.echo("✅ Alembic initialized!")
        elif db_only:
            click.echo("🗄️  Initializing database schema...")
            db.initialize_schema()
            click.echo("✅ Database initialized!")
        else:
            click.echo("🚀 Initializing Palimpsest database...")
            click.echo("📁 Initializing Alembic...")
            db.init_alembic()
            click.echo("🗄️  Initializing database schema...")
            db.initialize_schema()
            click.echo("✅ Complete setup finished!")

    except DatabaseError as e:
        handle_cli_error(ctx, e, "init")


@click.command()
@click.confirmation_option(prompt="⚠️  This will DELETE the database! Are you sure?")
@click.option("--keep-backups", is_flag=True, help="Keep existing backups")
@click.pass_context
def reset(ctx, keep_backups):
    """Reset database (DANGEROUS - deletes all data!)."""
    try:
        db_path = ctx.obj["db_path"]

        click.echo("🗑️  Resetting database...")

        # Delete database file
        if db_path.exists():
            db_path.unlink()
            click.echo(f"  Deleted: {db_path}")

        # Reinitialize
        click.echo("🔄 Reinitializing...")
        db = get_db(ctx)
        db.init_alembic()
        db.initialize_schema()

        click.echo("✅ Database reset complete!")

        if not keep_backups:
            click.echo("💡 Tip: Use --keep-backups to preserve backup files")

    except DatabaseError as e:
        handle_cli_error(ctx, e, "reset")
