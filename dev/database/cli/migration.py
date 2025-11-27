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
"""
import click

from dev.core.logging_manager import handle_cli_error
from dev.core.exceptions import DatabaseError
from . import get_db


@click.group()
@click.pass_context
def migration(ctx: click.Context) -> None:
    """Database migration management (Alembic operations)."""
    pass


@migration.command("create")
@click.argument("message")
@click.option(
    "--autogenerate", is_flag=True, help="Auto-generate migration from models"
)
@click.pass_context
def migration_create(ctx, message, autogenerate):
    """Create a new Alembic migration."""
    try:
        click.echo(f"📝 Creating migration: {message}")
        db = get_db(ctx)

        if autogenerate:
            click.echo("🔍 Auto-generating migration from model changes...")

        revision = db.create_migration(message)
        click.echo(f"✅ Migration created: {revision}")

        if autogenerate:
            click.echo("💡 Review the auto-generated migration file, then run: metadb migration upgrade")
        else:
            click.echo("💡 Edit the migration file and then run: metadb migration upgrade")

    except DatabaseError as e:
        handle_cli_error(ctx, e, "migration_create")


@migration.command("upgrade")
@click.option("--revision", default="head", help="Target revision (default: head)")
@click.pass_context
def migration_upgrade(ctx, revision):
    """Upgrade database to specified revision."""
    try:
        click.echo(f"⬆️  Upgrading database to: {revision}")
        db = get_db(ctx)
        db.upgrade_database(revision)
        click.echo("✅ Database upgraded successfully!")

    except DatabaseError as e:
        handle_cli_error(
            ctx,
            e,
            "migration_upgrade",
            additional_context={"revision": revision},
        )


@migration.command("downgrade")
@click.argument("revision")
@click.pass_context
def migration_downgrade(ctx, revision):
    """Downgrade database to specified revision."""
    try:
        click.echo(f"⬇️  Downgrading database to: {revision}")
        db = get_db(ctx)
        db.downgrade_database(revision)
        click.echo("✅ Database downgraded successfully!")

    except DatabaseError as e:
        handle_cli_error(
            ctx,
            e,
            "migration_downgrade",
            additional_context={"revision": revision},
        )


@migration.command("status")
@click.pass_context
def migration_status(ctx):
    """Show current migration status."""
    try:
        db = get_db(ctx)
        status = db.get_migration_history()

        click.echo("\n📊 Migration Status")
        click.echo("=" * 50)
        click.echo(f"Current Revision: {status.get('current_revision', 'None')}")
        click.echo(f"Status: {status.get('status', 'Unknown')}")

        if "error" in status:
            click.echo(f"⚠️  Error: {status['error']}")

    except DatabaseError as e:
        handle_cli_error(ctx, e, "migration_status")


@migration.command("history")
@click.pass_context
def migration_history(ctx):
    """Show migration history."""
    try:
        db = get_db(ctx)
        status = db.get_migration_history()

        click.echo("\n📜 Migration History")
        click.echo("=" * 50)

        if "history" in status and status["history"]:
            for migration in status["history"]:
                click.echo(f"  • {migration}")
        else:
            click.echo("  No migrations found")

    except DatabaseError as e:
        handle_cli_error(ctx, e, "migration_history")
