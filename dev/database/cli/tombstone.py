"""
Tombstone Management Commands
------------------------------

Commands for managing association tombstones.

Tombstones track deleted associations between entities for
synchronization across multiple machines.

Commands:
    - list: List association tombstones
    - stats: Show tombstone statistics
    - cleanup: Remove expired tombstones
    - remove: Manually remove specific tombstone

Usage:
    # List all current tombstones
    metadb tombstone list

    # List tombstones for a specific table
    metadb tombstone list --table entry_people

    # Show tombstone statistics
    metadb tombstone stats

    # Clean up expired tombstones (dry run)
    metadb tombstone cleanup --dry-run

    # Manually remove a specific tombstone
    metadb tombstone remove entry_people 1 5
"""
import click

from dev.core.logging_manager import handle_cli_error
from dev.core.exceptions import DatabaseError
from dev.database.tombstone_manager import TombstoneManager
from . import get_db


@click.group()
@click.pass_context
def tombstone(ctx: click.Context) -> None:
    """Manage association tombstones for deletion tracking."""
    pass


@tombstone.command("list")
@click.option("--table", help="Filter by table name (e.g., 'entry_people')")
@click.option("--limit", default=100, help="Maximum number to display (default: 100)")
@click.pass_context
def tombstone_list(ctx, table, limit):
    """List association tombstones."""
    try:
        db = get_db(ctx)

        with db.session_scope() as session:
            tombstone_mgr = TombstoneManager(session, db.logger)
            tombstones = tombstone_mgr.list_all(table_name=table, limit=limit)

            if not tombstones:
                click.echo("No tombstones found")
                return

            click.echo(f"\n🪦 Association Tombstones ({len(tombstones)})")
            click.echo("=" * 70)

            for t in tombstones:
                click.echo(f"\nTable: {t.table_name}")
                click.echo(f"  Left ID: {t.left_id}")
                click.echo(f"  Right ID: {t.right_id}")
                click.echo(f"  Removed at: {t.removed_at.isoformat()}")
                click.echo(f"  Removed by: {t.removed_by}")
                click.echo(f"  Source: {t.sync_source}")
                if t.removal_reason:
                    click.echo(f"  Reason: {t.removal_reason}")
                if t.expires_at:
                    click.echo(f"  Expires at: {t.expires_at.isoformat()}")
                else:
                    click.echo("  Expires: Never (permanent)")

            if len(tombstones) == limit:
                click.echo(f"\n(Showing first {limit} tombstones. Use --limit to see more)")

    except DatabaseError as e:
        handle_cli_error(ctx, e, "tombstone_list")


@tombstone.command("stats")
@click.pass_context
def tombstone_stats(ctx):
    """Show tombstone statistics."""
    try:
        db = get_db(ctx)

        with db.session_scope() as session:
            tombstone_mgr = TombstoneManager(session, db.logger)
            stats = tombstone_mgr.get_statistics()

            click.echo("\n📊 Tombstone Statistics")
            click.echo("=" * 70)

            click.echo(f"\nTotal tombstones: {stats['total']}")
            click.echo(f"Expired tombstones: {stats['expired']}")

            if stats['by_table']:
                click.echo("\nBy table:")
                for table, count in sorted(stats['by_table'].items()):
                    click.echo(f"  {table}: {count}")

            if stats['by_source']:
                click.echo("\nBy sync source:")
                for source, count in sorted(stats['by_source'].items()):
                    click.echo(f"  {source}: {count}")

    except DatabaseError as e:
        handle_cli_error(ctx, e, "tombstone_stats")


@tombstone.command("cleanup")
@click.option("--dry-run", is_flag=True, help="Show what would be deleted without deleting")
@click.pass_context
def tombstone_cleanup(ctx, dry_run):
    """Remove expired tombstones."""
    try:
        db = get_db(ctx)

        with db.session_scope() as session:
            tombstone_mgr = TombstoneManager(session, db.logger)
            count = tombstone_mgr.cleanup_expired(dry_run=dry_run)

            if dry_run:
                click.echo(f"\n🔍 Dry run: Would delete {count} expired tombstones")
                click.echo("Run without --dry-run to actually delete")
            else:
                click.echo(f"\n✅ Cleaned up {count} expired tombstones")

    except DatabaseError as e:
        handle_cli_error(ctx, e, "tombstone_cleanup")


@tombstone.command("remove")
@click.argument("table_name")
@click.argument("left_id", type=int)
@click.argument("right_id", type=int)
@click.confirmation_option(prompt="Remove this tombstone?")
@click.pass_context
def tombstone_remove(ctx, table_name, left_id, right_id):
    """Manually remove a specific tombstone."""
    try:
        db = get_db(ctx)

        with db.session_scope() as session:
            tombstone_mgr = TombstoneManager(session, db.logger)

            if tombstone_mgr.remove_tombstone(table_name, left_id, right_id):
                click.echo(f"\n✅ Removed tombstone: {table_name}({left_id}, {right_id})")
            else:
                click.echo(f"\n⚠️  Tombstone not found: {table_name}({left_id}, {right_id})")

    except DatabaseError as e:
        handle_cli_error(ctx, e, "tombstone_remove")
