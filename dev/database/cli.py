#!/usr/bin/env python3
"""
cli.py
-------------------
Command-line interface for Palimpsest database management.

Provides comprehensive commands for database initialization, migration,
backup, health monitoring, and maintenance operations.

Command Groups:
    Setup & Initialization:
        - init: Initialize database and Alembic
        - reset: Reset database (dangerous!)

    Migration Management:
        - migration-create: Create new migration
        - migration-upgrade: Upgrade to revision
        - migration-downgrade: Downgrade to revision
        - migration-status: Show migration status
        - migration-history: Show migration history

    Backup & Restore:
        - backup: Create timestamped backup
        - backups: List all backups
        - restore: Restore from backup

    Monitoring:
        - stats: Database statistics
        - health: Health check
        - validate: Integrity validation

    Maintenance:
        - cleanup: Remove orphaned records
        - optimize: Optimize database

    Export:
        - export-csv: Export to CSV files
        - export-json: Export to JSON

Usage:
    metadb init
    metadb stats --verbose
    metadb backup --type daily
    metadb health --fix
"""
import sys
import click
import json
import logging
from pathlib import Path

from dev.core.paths import DB_PATH, ALEMBIC_DIR, LOG_DIR, BACKUP_DIR
from dev.core.exceptions import (
    DatabaseError,
    BackupError,
    ExportError,
    HealthCheckError,
)

from . import PalimpsestDB, QueryOptimizer, HierarchicalBatcher


@click.group()
@click.option(
    "--db-path",
    type=click.Path(),
    default=str(DB_PATH),
    help="Path to database file",
)
@click.option(
    "--alembic-dir",
    type=click.Path(),
    default=str(ALEMBIC_DIR),
    help="Path to Alembic directory",
)
@click.option(
    "--log-dir",
    type=click.Path(),
    default=str(LOG_DIR),
    help="Path to log directory",
)
@click.option(
    "--backup-dir",
    type=click.Path(),
    default=str(BACKUP_DIR),
    help="Path to backup directory",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Show detailed errors and tracebacks",
)
@click.pass_context
def cli(ctx, db_path, alembic_dir, log_dir, backup_dir, verbose):
    """Palimpsest Database Management CLI"""

    # Suppress Alembic INFO logging by default
    logging.getLogger("alembic").setLevel(logging.WARNING)

    ctx.ensure_object(dict)
    ctx.obj["db_path"] = Path(db_path)
    ctx.obj["alembic_dir"] = Path(alembic_dir)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["backup_dir"] = Path(backup_dir)
    ctx.obj["verbose"] = verbose


def get_db(ctx) -> PalimpsestDB:
    """Get or create database instance."""
    if "db" not in ctx.obj:
        ctx.obj["db"] = PalimpsestDB(
            db_path=ctx.obj["db_path"],
            alembic_dir=ctx.obj["alembic_dir"],
            log_dir=ctx.obj["log_dir"],
            backup_dir=ctx.obj["backup_dir"],
            enable_auto_backup=False,
        )
    return ctx.obj["db"]


# ===== Setup & Initialization =====
@cli.command()
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
        # Get logger from context
        logger = ctx.obj.get("logger")
        if logger:
            error_msg = logger.log_cli_error(
                e,
                {"operation": "init"},
                show_traceback=ctx.obj.get("verbose", False),
            )
        else:
            error_msg = f"❌ Initialization failed: {e}"

        click.echo(error_msg, err=True)
        sys.exit(1)


@cli.command()
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
        # Get logger from context
        logger = ctx.obj.get("logger")
        if logger:
            error_msg = logger.log_cli_error(
                e,
                {"operation": "init"},
                show_traceback=ctx.obj.get("verbose", False),
            )
        else:
            error_msg = f"❌ Reset failed: {e}"

        click.echo(error_msg, err=True)
        sys.exit(1)


# ===== Migration Management =====
@cli.command()
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

        # TODO: Add autogenerate support
        if autogenerate:
            click.echo("⚠️  Auto-generate not yet implemented, creating empty migration")

        revision = db.create_migration(message)
        click.echo(f"✅ Migration created: {revision}")
        click.echo("💡 Edit the migration file and then run: metadb migration-upgrade")

    except DatabaseError as e:
        # Get logger from context
        logger = ctx.obj.get("logger")
        if logger:
            error_msg = logger.log_cli_error(
                e,
                {"operation": "init"},
                show_traceback=ctx.obj.get("verbose", False),
            )
        else:
            error_msg = f"❌ Migration creation failed: {e}"

        click.echo(error_msg, err=True)
        sys.exit(1)


@cli.command()
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
        # Get logger from context
        logger = ctx.obj.get("logger")
        if logger:
            error_msg = logger.log_cli_error(
                e,
                {"operation": "init"},
                show_traceback=ctx.obj.get("verbose", False),
            )
        else:
            error_msg = f"❌ Database upgrade failed: {e}"

        click.echo(error_msg, err=True)
        sys.exit(1)


@cli.command()
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
        # Get logger from context
        logger = ctx.obj.get("logger")
        if logger:
            error_msg = logger.log_cli_error(
                e,
                {"operation": "init"},
                show_traceback=ctx.obj.get("verbose", False),
            )
        else:
            error_msg = f"❌ Database downgrade failed: {e}"

        click.echo(error_msg, err=True)
        sys.exit(1)


@cli.command()
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
        # Get logger from context
        logger = ctx.obj.get("logger")
        if logger:
            error_msg = logger.log_cli_error(
                e,
                {"operation": "init"},
                show_traceback=ctx.obj.get("verbose", False),
            )
        else:
            error_msg = f"❌ Failed to get migration status: {e}"

        click.echo(error_msg, err=True)
        sys.exit(1)


@cli.command()
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
        # Get logger from context
        logger = ctx.obj.get("logger")
        if logger:
            error_msg = logger.log_cli_error(
                e,
                {"operation": "init"},
                show_traceback=ctx.obj.get("verbose", False),
            )
        else:
            error_msg = f"❌ Failed to get migration history: {e}"

        click.echo(error_msg, err=True)
        sys.exit(1)


# ===== Backup & Restore =====
@cli.command()
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
        # Get logger from context
        logger = ctx.obj.get("logger")
        if logger:
            error_msg = logger.log_cli_error(
                e,
                {"operation": "init"},
                show_traceback=ctx.obj.get("verbose", False),
            )
        else:
            error_msg = f"❌ Backup failed: {e}"

        click.echo(error_msg, err=True)
        sys.exit(1)


@cli.command()
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
        # Get logger from context
        logger = ctx.obj.get("logger")
        if logger:
            error_msg = logger.log_cli_error(
                e,
                {"operation": "init"},
                show_traceback=ctx.obj.get("verbose", False),
            )
        else:
            error_msg = f"❌ Failed to list backups: {e}"

        click.echo(error_msg, err=True)
        sys.exit(1)


@cli.command()
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
        # Get logger from context
        logger = ctx.obj.get("logger")
        if logger:
            error_msg = logger.log_cli_error(
                e,
                {"operation": "init"},
                show_traceback=ctx.obj.get("verbose", False),
            )
        else:
            error_msg = f"❌ Restore failed: {e}"

        click.echo(error_msg, err=True)
        sys.exit(1)


# ===== Monitoring =====
@cli.command()
@click.argument("entry_date")
@click.option(
    "--full", is_flag=True, help="Show all details including references/poems"
)
@click.pass_context
def show(ctx, entry_date, full):
    """Display a single entry with optimized loading."""
    try:
        db = get_db(ctx)

        with db.session_scope() as session:
            if full:
                # Load everything
                entry = db.get_entry(session, entry_date)
                if entry:
                    entry_ids = [entry.id]
                    entry = QueryOptimizer.for_export(session, entry_ids)[0]
            else:
                # Use optimized display query
                entry = db.get_entry_for_display(session, entry_date)

            if not entry:
                click.echo(f"❌ No entry found for {entry_date}", err=True)
                sys.exit(1)

            # Display entry
            click.echo(f"\n📅 {entry.date.isoformat()}")
            click.echo(
                f"📊 {entry.word_count} words, {entry.reading_time:.1f} min read"
            )

            if entry.people:
                click.echo(f"\n👥 People ({len(entry.people)}):")
                for person in entry.people:
                    click.echo(f"  • {person.display_name}")

            if entry.locations:
                click.echo(f"\n📍 Locations ({len(entry.locations)}):")
                for loc in entry.locations:
                    click.echo(f"  • {loc.name} ({loc.city.city})")

            if entry.events:
                click.echo(f"\n🎯 Events ({len(entry.events)}):")
                for event in entry.events:
                    click.echo(f"  • {event.display_name}")

            if entry.tags:
                click.echo(f"\n🏷️  Tags: {', '.join(tag.tag for tag in entry.tags)}")

            if full and entry.references:
                click.echo(f"\n📚 References ({len(entry.references)}):")
                for ref in entry.references:
                    click.echo(f"  • {ref.content_preview}")
                    if ref.source:
                        click.echo(f"    Source: {ref.source.display_name}")

            if full and entry.poems:
                click.echo(f"\n✍️  Poems ({len(entry.poems)}):")
                for poem_version in entry.poems:
                    click.echo(
                        f"  • {poem_version.poem.title} ({poem_version.line_count} lines)"
                    )

    except DatabaseError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def years(ctx):
    """List all years with entry counts."""
    try:
        db = get_db(ctx)

        with db.session_scope() as session:
            years = HierarchicalBatcher.get_years(session)

            click.echo("\n📅 Available Years:\n")

            for year in years:
                count = HierarchicalBatcher.count_year_entries(session, year)
                click.echo(f"  {year}: {count:4d} entries")

            click.echo(f"\nTotal: {len(years)} years")

    except DatabaseError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("year", type=int)
@click.pass_context
def months(ctx, year):
    """List all months in a year with entry counts."""
    try:
        db = get_db(ctx)

        with db.session_scope() as session:
            months = HierarchicalBatcher.get_months_for_year(session, year)

            if not months:
                click.echo(f"⚠️  No entries found for {year}")
                return

            month_names = [
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            ]

            click.echo(f"\n📅 Entries in {year}:\n")

            total = 0
            for month in months:
                count = HierarchicalBatcher.count_month_entries(session, year, month)
                total += count
                click.echo(
                    f"  {month_names[month-1]} ({month:02d}): {count:3d} entries"
                )

            click.echo(f"\nTotal: {total} entries")

    except DatabaseError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--threshold", type=int, default=500, help="Batch threshold")
@click.pass_context
def batches(ctx, threshold):
    """Show how entries would be batched for export."""
    try:
        db = get_db(ctx)

        with db.session_scope() as session:
            batches = HierarchicalBatcher.create_batches(session, threshold)

            click.echo(f"\n📦 Hierarchical Batches (threshold={threshold}):\n")

            yearly_batches = [b for b in batches if b.is_yearly]
            monthly_batches = [b for b in batches if b.is_monthly]

            if yearly_batches:
                click.echo("Full Year Batches:")
                for batch in yearly_batches:
                    click.echo(f"  • {batch.year}: {batch.entry_count} entries")

            if monthly_batches:
                click.echo("\nMonthly Batches:")
                current_year = None
                for batch in monthly_batches:
                    if batch.year != current_year:
                        click.echo(f"\n  {batch.year}:")
                        current_year = batch.year
                    click.echo(
                        f"    • {batch.period_label}: {batch.entry_count} entries"
                    )

            total_entries = sum(b.entry_count for b in batches)
            click.echo(f"\nTotal: {len(batches)} batches, {total_entries} entries")

    except DatabaseError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--verbose", is_flag=True, help="Show detailed statistics")
@click.pass_context
def stats(ctx, verbose):
    """Display database statistics."""
    try:
        db = get_db(ctx)
        stats_data = db.get_stats()

        click.echo("\n📊 Database Statistics")
        click.echo("=" * 50)

        # Core tables
        click.echo("\nCore Tables:")
        click.echo(f"  Entries: {stats_data.get('entries', 0)}")
        click.echo(f"  People: {stats_data.get('people', 0)}")
        click.echo(f"  Cities: {stats_data.get('cities', 0)}")
        click.echo(f"  Locations: {stats_data.get('locations', 0)}")
        click.echo(f"  Events: {stats_data.get('events', 0)}")
        click.echo(f"  Tags: {stats_data.get('tags', 0)}")

        # Manuscript tables
        if verbose:
            click.echo("\nManuscript:")
            click.echo(f"  Entries: {stats_data.get('manuscript_entries', 0)}")
            click.echo(f"  People: {stats_data.get('manuscript_people', 0)}")
            click.echo(f"  Events: {stats_data.get('manuscript_events', 0)}")
            click.echo(f"  Themes: {stats_data.get('themes', 0)}")
            click.echo(f"  Arcs: {stats_data.get('arcs', 0)}")

        # Content stats
        click.echo("\nContent:")
        click.echo(f"  Total Words: {stats_data.get('total_words', 0):,}")
        if "average_words_per_entry" in stats_data:
            click.echo(
                f"  Average Words/Entry: {stats_data['average_words_per_entry']:.1f}"
            )

        # Date range
        if "date_range" in stats_data:
            dr = stats_data["date_range"]
            click.echo("\nDate Range:")
            click.echo(f"  First Entry: {dr['first_entry']}")
            click.echo(f"  Last Entry: {dr['last_entry']}")
            click.echo(f"  Total Days: {dr['total_days']}")

    except DatabaseError as e:
        # Get logger from context
        logger = ctx.obj.get("logger")
        if logger:
            error_msg = logger.log_cli_error(
                e,
                {"operation": "init"},
                show_traceback=ctx.obj.get("verbose", False),
            )
        else:
            error_msg = f"❌ Failed to get statistics: {e}"

        click.echo(error_msg, err=True)
        sys.exit(1)


@cli.command()
@click.option("--fix", is_flag=True, help="Attempt to fix issues")
@click.pass_context
def health(ctx, fix):
    """Run comprehensive health check."""
    try:
        db = get_db(ctx)
        health_data = db.check_health()

        click.echo("\n🏥 Database Health Check")
        click.echo("=" * 50)
        click.echo(f"Status: {health_data['status'].upper()}")

        if health_data["issues"]:
            click.echo(f"\n⚠️  Issues Found ({len(health_data['issues'])}):")
            for issue in health_data["issues"]:
                click.echo(f"  • {issue}")
        else:
            click.echo("\n✅ No issues found!")

        if health_data["recommendations"]:
            click.echo(f"\n💡 Recommendations ({len(health_data['recommendations'])}):")
            for rec in health_data["recommendations"]:
                click.echo(f"  • {rec}")

        if fix and health_data["issues"]:
            click.echo("\n🔧 Attempting fixes...")
            with db.session_scope() as session:
                results = db.health_monitor.cleanup_orphaned_records(
                    session, dry_run=False
                )
                click.echo("\nCleanup Results:")
                total_cleaned = 0
                for key, value in results.items():
                    if isinstance(value, int) and value > 0:
                        click.echo(f"  • {key}: {value}")
                        total_cleaned += value

                if total_cleaned == 0:
                    click.echo("  No orphaned records found")

    except DatabaseError as e:
        # Get logger from context
        logger = ctx.obj.get("logger")
        if logger:
            error_msg = logger.log_cli_error(
                e,
                {"operation": "init"},
                show_traceback=ctx.obj.get("verbose", False),
            )
        else:
            error_msg = f"❌ Health check failed: {e}"

        click.echo(error_msg, err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def validate(ctx):
    """Validate database integrity."""
    try:
        db = get_db(ctx)
        with db.session_scope() as session:
            orphans = db.health_monitor._check_orphaned_records(session)
            integrity = db.health_monitor._check_data_integrity(session)

            click.echo("\n🔍 Database Validation")
            click.echo("=" * 50)

            total_orphans = sum(orphans.values())
            if total_orphans > 0:
                click.echo(f"\n⚠️  Found {total_orphans} orphaned records:")
                for table, count in orphans.items():
                    if count > 0:
                        click.echo(f"  • {table}: {count}")
            else:
                click.echo("\n✅ No orphaned records found")

            total_integrity_issues = sum(
                v for v in integrity.values() if isinstance(v, int)
            )
            if total_integrity_issues > 0:
                click.echo(f"\n⚠️  Found {total_integrity_issues} integrity issues:")
                for check, count in integrity.items():
                    if isinstance(count, int) and count > 0:
                        click.echo(f"  • {check}: {count}")
            else:
                click.echo("✅ No integrity issues found")

    except DatabaseError as e:
        # Get logger from context
        logger = ctx.obj.get("logger")
        if logger:
            error_msg = logger.log_cli_error(
                e,
                {"operation": "init"},
                show_traceback=ctx.obj.get("verbose", False),
            )
        else:
            error_msg = f"❌ Validation failed: {e}"

        click.echo(error_msg, err=True)
        sys.exit(1)


# ===== Maintenance =====
@cli.command()
@click.confirmation_option(prompt="This will remove orphaned records. Continue?")
@click.pass_context
def cleanup(ctx):
    """Clean up orphaned records."""
    try:
        db = get_db(ctx)
        click.echo("🧹 Cleaning up orphaned records...")
        results = db.cleanup_all_metadata()

        click.echo("\n✅ Cleanup Complete:")
        total_removed = 0
        for table, count in results.items():
            if count > 0:
                click.echo(f"  • {table}: {count} removed")
                total_removed += count

        if total_removed == 0:
            click.echo("  No orphaned records found")
        else:
            click.echo(f"\nTotal removed: {total_removed}")

    except DatabaseError as e:
        # Get logger from context
        logger = ctx.obj.get("logger")
        if logger:
            error_msg = logger.log_cli_error(
                e,
                {"operation": "init"},
                show_traceback=ctx.obj.get("verbose", False),
            )
        else:
            error_msg = f"❌ Cleanup failed: {e}"

        click.echo(error_msg, err=True)
        sys.exit(1)


@cli.command()
@click.confirmation_option(
    prompt="Optimization can take time and requires exclusive access. Continue?"
)
@click.pass_context
def optimize(ctx):
    """Optimize database performance (VACUUM + ANALYZE)."""
    try:
        db = get_db(ctx)
        click.echo("🔧 Optimizing database...")

        with db.session_scope() as session:
            results = db.health_monitor.optimize_database(session)

        if results:
            click.echo("\n✅ Optimization Complete:")
            if "space_reclaimed_bytes" in results:
                reclaimed = results["space_reclaimed_bytes"]
                mb_reclaimed = reclaimed / 1024 / 1024
                click.echo(
                    f"  Space reclaimed: {reclaimed:,} bytes ({mb_reclaimed:.2f} MB)"
                )
            if "vacuum_completed" in results:
                status = "✓" if results["vacuum_completed"] else "✗"
                click.echo(f"  VACUUM: {status}")
            if "analyze_completed" in results:
                status = "✓" if results["analyze_completed"] else "✗"
                click.echo(f"  ANALYZE: {status}")
        else:
            click.echo("⚠️  No optimization performed")

    except (HealthCheckError, DatabaseError) as e:
        # Get logger from context
        logger = ctx.obj.get("logger")
        if logger:
            error_msg = logger.log_cli_error(
                e,
                {"operation": "init"},
                show_traceback=ctx.obj.get("verbose", False),
            )
        else:
            error_msg = f"❌ Optimization failed: {e}"

        click.echo(error_msg, err=True)
        sys.exit(1)


# ===== Export =====
@cli.command()
@click.option("--year", type=int, help="Export specific year")
@click.option("--threshold", type=int, default=500, help="Batch threshold")
@click.pass_context
def export_optimized(ctx, year, threshold):
    """Export entries with optimized batch processing."""
    try:
        db = get_db(ctx)

        click.echo("📊 Analyzing entry distribution...")

        with db.session_scope() as session:
            if year:
                entries = db.get_entries_by_year(session, year)
                click.echo(f"✅ Loaded {len(entries)} entries for {year}")
            else:
                batches = db.get_hierarchical_batches(session, threshold)
                click.echo(f"✅ Created {len(batches)} hierarchical batches:")
                for batch in batches:
                    click.echo(f"  • {batch}")

    except DatabaseError as e:
        logger = ctx.obj.get("logger")
        if logger:
            error_msg = logger.log_cli_error(
                e,
                {"operation": "export_optimized"},
                show_traceback=ctx.obj.get("verbose", False),
            )
        else:
            error_msg = f"❌ Export failed: {e}"

        click.echo(error_msg, err=True)
        sys.exit(1)


@cli.command()
@click.argument("output_dir", type=click.Path())
@click.pass_context
def export_csv(ctx, output_dir):
    """Export all tables to CSV files."""
    try:
        db = get_db(ctx)
        click.echo(f"📤 Exporting to CSV: {output_dir}")

        with db.session_scope() as session:
            exported = db.export_to_csv(session, output_dir)

        click.echo(f"\n✅ Export Complete ({len(exported)} tables):")
        for table, path in exported.items():
            click.echo(f"  • {table}: {path}")

    except ExportError as e:
        # Get logger from context
        logger = ctx.obj.get("logger")
        if logger:
            error_msg = logger.log_cli_error(
                e,
                {"operation": "init"},
                show_traceback=ctx.obj.get("verbose", False),
            )
        else:
            error_msg = f"❌ CSV export failed: {e}"

        click.echo(error_msg, err=True)
        sys.exit(1)


@cli.command()
@click.argument("output_file", type=click.Path())
@click.pass_context
def export_json(ctx, output_file):
    """Export complete database to JSON."""
    try:
        db = get_db(ctx)
        click.echo(f"📤 Exporting to JSON: {output_file}")

        with db.session_scope() as session:
            exported = db.export_to_json(session, output_file)

        click.echo(f"✅ Export complete: {exported}")

    except ExportError as e:
        # Get logger from context
        logger = ctx.obj.get("logger")
        if logger:
            error_msg = logger.log_cli_error(
                e,
                {"operation": "init"},
                show_traceback=ctx.obj.get("verbose", False),
            )
        else:
            error_msg = f"❌ JSON export failed: {e}"

        click.echo(error_msg, err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def analyze(ctx):
    """Generate detailed analytics report."""
    try:
        db = get_db(ctx)

        with db.session_scope() as session:
            stats = db.query_analytics.get_database_stats(session)
            manuscript = db.query_analytics.get_manuscript_analytics(session)

        click.echo("\n📈 Analytics Report")
        click.echo("=" * 70)

        click.echo("\nDatabase Overview:")
        click.echo(json.dumps(stats, indent=2, default=str))

        click.echo("\nManuscript Analytics:")
        click.echo(json.dumps(manuscript, indent=2, default=str))

    except DatabaseError as e:
        # Get logger from context
        logger = ctx.obj.get("logger")
        if logger:
            error_msg = logger.log_cli_error(
                e,
                {"operation": "init"},
                show_traceback=ctx.obj.get("verbose", False),
            )
        else:
            error_msg = f"❌ Analytics failed: {e}"

        click.echo(error_msg, err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli(obj={})
