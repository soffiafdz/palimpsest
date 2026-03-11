"""
Migration Management Commands
------------------------------

Database migration commands using Alembic.

Commands:
    - create: Create a new migration
    - upgrade: Upgrade to a revision
    - downgrade: Downgrade to a revision
    - status: Show migration status
    - history: Show migration history

Usage:
    plm db create "Added new person entity"
    plm db upgrade
    plm db downgrade <revision_id>
    plm db status
    plm db history
"""
import click

from dev.core.logging_manager import handle_cli_error
from dev.core.exceptions import DatabaseError
from . import get_db


@click.command("create")
@click.argument("message")
@click.option(
    "--autogenerate", is_flag=True, help="Auto-generate migration from models"
)
@click.pass_context
def create(ctx, message, autogenerate):
    """Create a new Alembic migration."""
    try:
        click.echo(f"Creating migration: {message}")
        db = get_db(ctx)

        if autogenerate:
            click.echo("Auto-generating migration from model changes...")

        revision = db.create_migration(message)
        click.echo(f"[OK]Migration created: {revision}")

        if autogenerate:
            click.echo("[TIP]Review the auto-generated migration file, then run: plm db upgrade")
        else:
            click.echo("[TIP]Edit the migration file and then run: plm db upgrade")

    except DatabaseError as e:
        handle_cli_error(ctx, e, "create")


@click.command("upgrade")
@click.option("--revision", default="head", help="Target revision (default: head)")
@click.pass_context
def upgrade(ctx, revision):
    """Upgrade database to specified revision."""
    try:
        click.echo(f"Upgrading database to: {revision}")
        db = get_db(ctx)
        db.upgrade_database(revision)
        click.echo("[OK]Database upgraded successfully!")

    except DatabaseError as e:
        handle_cli_error(
            ctx,
            e,
            "upgrade",
            additional_context={"revision": revision},
        )


@click.command("downgrade")
@click.argument("revision")
@click.pass_context
def downgrade(ctx, revision):
    """Downgrade database to specified revision."""
    try:
        click.echo(f"Downgrading database to: {revision}")
        db = get_db(ctx)
        db.downgrade_database(revision)
        click.echo("[OK]Database downgraded successfully!")

    except DatabaseError as e:
        handle_cli_error(
            ctx,
            e,
            "downgrade",
            additional_context={"revision": revision},
        )


@click.command("migration-status")
@click.pass_context
def migration_status(ctx):
    """Show current migration status."""
    try:
        db = get_db(ctx)
        status = db.get_migration_history()

        click.echo("\nMigration Status")
        click.echo("=" * 50)
        click.echo(f"Current Revision: {status.get('current_revision', 'None')}")
        click.echo(f"Status: {status.get('status', 'Unknown')}")

        if "error" in status:
            click.echo(f"[WARN] Error: {status['error']}")

    except DatabaseError as e:
        handle_cli_error(ctx, e, "migration_status")


@click.command("history")
@click.pass_context
def history(ctx):
    """Show migration history."""
    try:
        db = get_db(ctx)
        status = db.get_migration_history()

        click.echo("\nMigration History")
        click.echo("=" * 50)

        if "history" in status and status["history"]:
            for migration in status["history"]:
                click.echo(f"  • {migration}")
        else:
            click.echo("  No migrations found")

    except DatabaseError as e:
        handle_cli_error(ctx, e, "history")
