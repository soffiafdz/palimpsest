"""
Sync State Management Commands
-------------------------------

Commands for managing synchronization state and conflict detection.

Sync state tracks entity modifications and conflicts across
multiple machines for multi-machine journal synchronization.

Commands:
    - conflicts: List unresolved/resolved conflicts
    - resolve: Mark conflict as resolved
    - stats: Show sync statistics
    - status: Show sync state for entity or summary
"""
import click

from dev.core.logging_manager import handle_cli_error
from dev.core.exceptions import DatabaseError
from dev.database.sync_state_manager import SyncStateManager
from . import get_db


@click.group()
@click.pass_context
def sync(ctx: click.Context) -> None:
    """Manage synchronization state and conflict detection."""
    pass


@sync.command("conflicts")
@click.option("--resolved", is_flag=True, help="Show resolved conflicts instead of unresolved")
@click.pass_context
def sync_conflicts(ctx, resolved):
    """List conflicts (unresolved by default)."""
    try:
        db = get_db(ctx)

        with db.session_scope() as session:
            sync_mgr = SyncStateManager(session, db.logger)
            conflicts = sync_mgr.list_conflicts(resolved=resolved)

            if not conflicts:
                status = "resolved" if resolved else "unresolved"
                click.echo(f"No {status} conflicts found")
                return

            status_text = "Resolved" if resolved else "Unresolved"
            click.echo(f"\n⚠️  {status_text} Conflicts ({len(conflicts)})")
            click.echo("=" * 70)

            for state in conflicts:
                click.echo(f"\n{state.entity_type} ID: {state.entity_id}")
                click.echo(f"  Last synced: {state.last_synced_at.isoformat()}")
                click.echo(f"  Sync source: {state.sync_source}")
                if state.machine_id:
                    click.echo(f"  Machine: {state.machine_id}")
                if state.sync_hash:
                    click.echo(f"  Hash: {state.sync_hash[:12]}...")
                click.echo(f"  Resolved: {state.conflict_resolved}")

    except DatabaseError as e:
        handle_cli_error(ctx, e, "sync_conflicts")


@sync.command("resolve")
@click.argument("entity_type")
@click.argument("entity_id", type=int)
@click.pass_context
def sync_resolve(ctx, entity_type, entity_id):
    """Mark a conflict as resolved."""
    try:
        db = get_db(ctx)

        with db.session_scope() as session:
            sync_mgr = SyncStateManager(session, db.logger)

            if sync_mgr.mark_conflict_resolved(entity_type, entity_id):
                click.echo(f"\n✅ Marked conflict as resolved: {entity_type} {entity_id}")
            else:
                click.echo(f"\n⚠️  Sync state not found: {entity_type} {entity_id}")

    except DatabaseError as e:
        handle_cli_error(ctx, e, "sync_resolve")


@sync.command("stats")
@click.pass_context
def sync_stats(ctx):
    """Show synchronization statistics."""
    try:
        db = get_db(ctx)

        with db.session_scope() as session:
            sync_mgr = SyncStateManager(session, db.logger)
            stats = sync_mgr.get_statistics()

            click.echo("\n📊 Sync State Statistics")
            click.echo("=" * 70)

            click.echo(f"\nTotal entities tracked: {stats['total']}")
            click.echo(f"Conflicts (unresolved): {stats['conflicts_unresolved']}")
            click.echo(f"Conflicts (resolved): {stats['conflicts_resolved']}")

            if stats['by_entity_type']:
                click.echo("\nBy entity type:")
                for entity_type, count in sorted(stats['by_entity_type'].items()):
                    click.echo(f"  {entity_type}: {count}")

            if stats['by_source']:
                click.echo("\nBy sync source:")
                for source, count in sorted(stats['by_source'].items()):
                    click.echo(f"  {source}: {count}")

            if stats['by_machine']:
                click.echo("\nBy machine:")
                for machine, count in sorted(stats['by_machine'].items()):
                    click.echo(f"  {machine}: {count}")

    except DatabaseError as e:
        handle_cli_error(ctx, e, "sync_stats")


@sync.command("status")
@click.argument("entity_type", required=False)
@click.argument("entity_id", type=int, required=False)
@click.pass_context
def sync_status(ctx, entity_type, entity_id):
    """Show sync status for a specific entity or all entities."""
    try:
        db = get_db(ctx)

        with db.session_scope() as session:
            sync_mgr = SyncStateManager(session, db.logger)

            if entity_type and entity_id:
                # Show specific entity
                state = sync_mgr.get(entity_type, entity_id)

                if not state:
                    click.echo(f"\n⚠️  No sync state for {entity_type} {entity_id}")
                    return

                click.echo(f"\n📊 Sync State: {entity_type} {entity_id}")
                click.echo("=" * 70)
                click.echo(f"Last synced: {state.last_synced_at.isoformat()}")
                click.echo(f"Sync source: {state.sync_source}")
                if state.sync_hash:
                    click.echo(f"Hash: {state.sync_hash}")
                if state.machine_id:
                    click.echo(f"Machine: {state.machine_id}")
                click.echo(f"Modified since sync: {state.modified_since_sync}")
                click.echo(f"Conflict detected: {state.conflict_detected}")
                click.echo(f"Conflict resolved: {state.conflict_resolved}")
            else:
                # Show summary
                stats = sync_mgr.get_statistics()
                click.echo("\n📊 Sync Status Summary")
                click.echo("=" * 70)
                click.echo(f"Total entities tracked: {stats['total']}")
                click.echo(f"Active conflicts: {stats['conflicts_unresolved']}")

                if stats['conflicts_unresolved'] > 0:
                    click.echo("\n⚠️  Use 'metadb sync conflicts' to see details")

    except DatabaseError as e:
        handle_cli_error(ctx, e, "sync_status")
