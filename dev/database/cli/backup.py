"""
Backup & Restore Commands
--------------------------

Database backup and restore operations.

Commands:
    - backup: Create timestamped backup
    - backups: List all backups
    - restore: Restore from backup

Usage:
    # Create a manual backup
    metadb backup --type manual --suffix "pre-update"

    # List all backups
    metadb backups

    # Restore from a specific backup file
    metadb restore /path/to/backup.db
"""
import click
from pathlib import Path

from dev.core.logging_manager import handle_cli_error
from dev.core.exceptions import BackupError, DatabaseError
from . import get_db


@click.command()
@click.option(
    "--type",
    type=click.Choice(["manual", "daily", "weekly"]),
    default="manual",
    help="Backup type",
)
@click.option("--suffix", default=None, help="Optional backup suffix")
@click.pass_context
def backup(ctx, type, suffix):
    """Create timestamped backup."""
    try:
        click.echo(f"💾 Creating {type} backup...")
        db = get_db(ctx)
        backup_path = db.create_backup(backup_type=type, suffix=suffix)
        click.echo(f"✅ Backup created: {backup_path}")

    except BackupError as e:
        handle_cli_error(
            ctx,
            e,
            "backup",
            additional_context={"type": type},
        )


@click.command()
@click.pass_context
def backups(ctx):
    """List all available backups."""
    try:
        db = get_db(ctx)
        backups_dict = db.list_backups()

        click.echo("\n📦 Available Backups")
        click.echo("=" * 70)

        total = 0
        for backup_type, backup_list in backups_dict.items():
            if backup_list:
                click.echo(f"\n{backup_type.upper()}:")
                for backup in backup_list:
                    click.echo(f"  • {backup['name']}")
                    click.echo(f"    Created: {backup['created']}")
                    click.echo(f"    Size: {backup['size']:,} bytes")
                    click.echo(f"    Age: {backup['age_days']} days")
                    total += 1

        if total == 0:
            click.echo("\n  No backups found")
        else:
            click.echo(f"\nTotal backups: {total}")

    except DatabaseError as e:
        handle_cli_error(ctx, e, "backups")


@click.command()
@click.argument("backup_path", type=click.Path(exists=True))
@click.confirmation_option(
    prompt="⚠️  This will overwrite the current database! Continue?"
)
@click.pass_context
def restore(ctx, backup_path):
    """Restore from a backup file."""
    try:
        click.echo(f"♻️  Restoring from: {backup_path}")
        db = get_db(ctx)
        db.restore_backup(Path(backup_path))
        click.echo("✅ Database restored successfully!")

    except BackupError as e:
        handle_cli_error(
            ctx,
            e,
            "restore",
            additional_context={"backup_path": backup_path},
        )
