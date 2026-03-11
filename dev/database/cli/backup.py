"""
Backup & Restore Commands
--------------------------

Database backup and restore operations.

Commands:
    - backup: Create timestamped backup (--full for full data backup)
    - backups: List all backups (--full for full data backups)
    - restore: Restore from backup

Usage:
    plm db backup --type manual --suffix "pre-update"
    plm db backup --full
    plm db backups
    plm db backups --full
    plm db restore /path/to/backup.db
"""
import click
from datetime import datetime
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
@click.option("--full", is_flag=True, help="Create full compressed backup of entire data directory")
@click.pass_context
def backup(ctx, type, suffix, full):
    """Create timestamped backup."""
    if full:
        from dev.core.paths import DB_PATH, BACKUP_DIR, DATA_DIR
        from dev.core.backup_manager import BackupManager
        from dev.core.logging_manager import PalimpsestLogger

        click.echo("Creating full data backup...")
        click.echo("   (This may take a while for large archives)")

        try:
            logger = ctx.obj.get("logger")
            backup_mgr = BackupManager(
                db_path=DB_PATH,
                backup_dir=ctx.obj.get("backup_dir", BACKUP_DIR),
                data_dir=DATA_DIR,
                logger=logger,
            )

            backup_path = backup_mgr.create_full_backup(suffix=suffix)
            backup_size = backup_path.stat().st_size
            backup_size_mb = backup_size / (1024 * 1024)

            click.echo("\n[OK]Full backup created:")
            click.echo(f"  Location: {backup_path}")
            click.echo(f"  Size: {backup_size_mb:.2f} MB ({backup_size:,} bytes)")

        except BackupError as e:
            handle_cli_error(ctx, e, "backup")
    else:
        try:
            click.echo(f"Creating {type} backup...")
            db = get_db(ctx)
            backup_path = db.create_backup(backup_type=type, suffix=suffix)
            click.echo(f"[OK]Backup created: {backup_path}")

        except BackupError as e:
            handle_cli_error(
                ctx,
                e,
                "backup",
                additional_context={"type": type},
            )


@click.command()
@click.option("--full", is_flag=True, help="List full data backups instead of DB backups")
@click.pass_context
def backups(ctx, full):
    """List all available backups."""
    if full:
        from dev.core.paths import DB_PATH, BACKUP_DIR, DATA_DIR
        from dev.core.backup_manager import BackupManager

        try:
            logger = ctx.obj.get("logger")
            backup_mgr = BackupManager(
                db_path=DB_PATH,
                backup_dir=ctx.obj.get("backup_dir", BACKUP_DIR),
                data_dir=DATA_DIR,
                logger=logger,
            )

            if (
                not hasattr(backup_mgr, "full_backup_dir")
                or not backup_mgr.full_backup_dir.exists()
            ):
                click.echo("No full backups directory found")
                return

            backup_list = sorted(backup_mgr.full_backup_dir.glob("*.tar.gz"))

            if not backup_list:
                click.echo("No full backups found")
                return

            click.echo("\nFull Data Backups")
            click.echo("=" * 70)

            for b in backup_list:
                stat = b.stat()
                size_mb = stat.st_size / (1024 * 1024)
                created = datetime.fromtimestamp(stat.st_mtime)
                age_days = (datetime.now() - created).days

                click.echo(f"\n  • {b.name}")
                click.echo(f"    Created: {created.strftime('%Y-%m-%d %H:%M:%S')}")
                click.echo(f"    Size: {size_mb:.2f} MB ({stat.st_size:,} bytes)")
                click.echo(f"    Age: {age_days} days")

            click.echo(f"\nTotal backups: {len(backup_list)}")
            click.echo(f"Location: {backup_mgr.full_backup_dir}")

        except Exception as e:
            handle_cli_error(ctx, e, "backups")
    else:
        try:
            db = get_db(ctx)
            backups_dict = db.list_backups()

            click.echo("\nAvailable Backups")
            click.echo("=" * 70)

            total = 0
            for backup_type, backup_list in backups_dict.items():
                if backup_list:
                    click.echo(f"\n{backup_type.upper()}:")
                    for b in backup_list:
                        click.echo(f"  • {b['name']}")
                        click.echo(f"    Created: {b['created']}")
                        click.echo(f"    Size: {b['size']:,} bytes")
                        click.echo(f"    Age: {b['age_days']} days")
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
    prompt="[WARN] This will overwrite the current database! Continue?"
)
@click.pass_context
def restore(ctx, backup_path):
    """Restore from a backup file."""
    try:
        click.echo(f"Restoring from: {backup_path}")
        db = get_db(ctx)
        db.restore_backup(Path(backup_path))
        click.echo("[OK]Database restored successfully!")

    except BackupError as e:
        handle_cli_error(
            ctx,
            e,
            "restore",
            additional_context={"backup_path": backup_path},
        )
