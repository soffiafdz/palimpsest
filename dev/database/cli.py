#!/usr/bin/env python3
"""
cli.py
-------------------
Command-line interface for Palimpsest database management.

Provides comprehensive commands for database initialization, migration,
backup, health monitoring, and maintenance operations. This CLI leverages
the refactored modular database architecture.

Commands:
    Database Setup:
        - bootstrap: Complete setup (Alembic + database + migration)
        - init-alembic: Initialize Alembic migration environment
        - init-db: Initialize or migrate the database

    Migration Management:
        - create-migration: Create a new Alembic migration
        - upgrade-db: Upgrade database to specified revision
        - downgrade-db: Downgrade database to specified revision
        - migration-status: Show current migration status

    Backup Operations:
        - backup-db: Create timestamped backup
        - list-backups: List all available backups
        - restore-backup: Restore from a backup file

    Monitoring & Maintenance:
        - stats: Display database statistics
        - health: Run comprehensive health check
        - validate: Validate database integrity
        - cleanup: Clean up orphaned records

    Data Export:
        - export-csv: Export all tables to CSV files
        - export-json: Export complete database to JSON

    Advanced:
        - query: Run custom queries (read-only by default)
        - analyze: Generate detailed analytics report

Usage:
    python -m database.cli [command] [options]

Examples:
    python -m database.cli bootstrap
    python -m database.cli stats --verbose
    python -m database.cli backup-db --type daily
    python -m database.cli health --fix
"""
import sys
import click
from pathlib import Path

# from typing import Optional
import json

from dev.core.paths import DB_PATH, ALEMBIC_DIR, LOG_DIR, BACKUP_DIR

from . import (
    PalimpsestDB,
    DatabaseError,
    BackupError,
    ExportError,
    HealthCheckError,
)


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
@click.pass_context
def cli(ctx, db_path, alembic_dir, log_dir, backup_dir):
    """Palimpsest Database Management CLI"""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = Path(db_path)
    ctx.obj["alembic_dir"] = Path(alembic_dir)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["backup_dir"] = Path(backup_dir)


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


# ===== Database Setup Commands =====
@cli.command()
@click.pass_context
def bootstrap(ctx):
    """Complete database setup (Alembic + database + migration)."""
    try:
        click.echo("🚀 Bootstrapping Palimpsest database...")
        db = get_db(ctx)

        # Initialize Alembic
        click.echo("📁 Initializing Alembic...")
        db.init_alembic()

        # Initialize database
        click.echo("🗄️  Initializing database schema...")
        db.initialize_schema()

        click.echo("✅ Bootstrap complete!")

    except DatabaseError as e:
        click.echo(f"❌ Bootstrap failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def init_alembic(ctx):
    """Initialize Alembic migration environment."""
    try:
        click.echo("📁 Initializing Alembic...")
        db = get_db(ctx)
        db.init_alembic()
        click.echo("✅ Alembic initialized successfully!")

    except DatabaseError as e:
        click.echo(f"❌ Alembic initialization failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def init_db(ctx):
    """Initialize or migrate the database."""
    try:
        click.echo("🗄️  Initializing databas schema...")
        db = get_db(ctx)
        db.initialize_schema()
        click.echo("✅ Database schema initialized successfully!")

    except DatabaseError as e:
        click.echo(f"❌ Database initialization failed: {e}", err=True)
        sys.exit(1)


# ===== Migration Management =====
@cli.command()
@click.argument("message")
@click.pass_context
def create_migration(ctx, message):
    """Create a new Alembic migration."""
    try:
        click.echo(f"📝 Creating migration: {message}")
        db = get_db(ctx)
        revision = db.create_migration(message)
        click.echo(f"✅ Migration created: {revision}")

    except DatabaseError as e:
        click.echo(f"❌ Migration creation failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--revision", default="head", help="Target revision")
@click.pass_context
def upgrade_db(ctx, revision):
    """Upgrade database to specified revision."""
    try:
        click.echo(f"⬆️  Upgrading database to: {revision}")
        db = get_db(ctx)
        db.upgrade_database(revision)
        click.echo("✅ Database upgraded successfully!")

    except DatabaseError as e:
        click.echo(f"❌ Database upgrade failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("revision")
@click.pass_context
def downgrade_db(ctx, revision):
    """Downgrade database to specified revision."""
    try:
        click.echo(f"⬇️  Downgrading database to: {revision}")
        db = get_db(ctx)
        db.downgrade_database(revision)
        click.echo("✅ Database downgraded successfully!")

    except DatabaseError as e:
        click.echo(f"❌ Database downgrade failed: {e}", err=True)
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
        click.echo(f"❌ Failed to get migration status: {e}", err=True)
        sys.exit(1)


# ===== Backup Operations =====
@cli.command()
@click.option("--type", default="manual", help="Backup type (manual/daily/weekly)")
@click.option("--suffix", default=None, help="Optional backup suffix")
@click.pass_context
def backup_db(ctx, type, suffix):
    """Create timestamped backup."""
    try:
        click.echo(f"💾 Creating {type} backup...")
        db = get_db(ctx)
        backup_path = db.create_backup(backup_type=type, suffix=suffix)
        click.echo(f"✅ Backup created: {backup_path}")

    except BackupError as e:
        click.echo(f"❌ Backup failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def list_backups(ctx):
    """List all available backups."""
    try:
        db = get_db(ctx)
        backups = db.list_backups()

        click.echo("\n📦 Available Backups")
        click.echo("=" * 70)

        for backup_type, backup_list in backups.items():
            if backup_list:
                click.echo(f"\n{backup_type.upper()}:")
                for backup in backup_list:
                    click.echo(f"  • {backup['name']}")
                    click.echo(f"    Created: {backup['created']}")
                    click.echo(f"    Size: {backup['size']:,} bytes")
                    click.echo(f"    Age: {backup['age_days']} days")

    except DatabaseError as e:
        click.echo(f"❌ Failed to list backups: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("backup_path", type=click.Path(exists=True))
@click.confirmation_option(
    prompt="Are you sure you want to restore? This will overwrite the current database."
)
@click.pass_context
def restore_backup(ctx, backup_path):
    """Restore from a backup file."""
    try:
        click.echo(f"♻️  Restoring from: {backup_path}")
        db = get_db(ctx)
        db.restore_backup(Path(backup_path))
        click.echo("✅ Database restored successfully!")

    except BackupError as e:
        click.echo(f"❌ Restore failed: {e}", err=True)
        sys.exit(1)


# ===== Monitoring & Maintenance =====
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
        click.echo(f"❌ Failed to get statistics: {e}", err=True)
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
            click.echo("\n⚠️  Issues Found:")
            for issue in health_data["issues"]:
                click.echo(f"  • {issue}")
        else:
            click.echo("\n✅ No issues found!")

        if health_data["recommendations"]:
            click.echo("\n💡 Recommendations:")
            for rec in health_data["recommendations"]:
                click.echo(f"  • {rec}")

        if fix and health_data["issues"]:
            click.echo("\n🔧 Attempting fixes...")
            with db.session_scope() as session:
                results = db.health_monitor.cleanup_orphaned_records(
                    session, dry_run=False
                )
                click.echo("\nCleanup Results:")
                for key, value in results.items():
                    if isinstance(value, int) and value > 0:
                        click.echo(f"  • {key}: {value}")

    except DatabaseError as e:
        click.echo(f"❌ Health check failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def validate(ctx):
    """Validate database integrity."""
    try:
        db = get_db(ctx)
        with db.session_scope() as session:
            # Check for orphaned records
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
        click.echo(f"❌ Validation failed: {e}", err=True)
        sys.exit(1)


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
        for table, count in results.items():
            if count > 0:
                click.echo(f"  • {table}: {count} removed")

    except DatabaseError as e:
        click.echo(f"❌ Cleanup failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--vacuum", is_flag=True, help="Run VACUUM to reclaim space")
@click.option("--analyze", is_flag=True, help="Run ANALYZE to update statistics")
@click.confirmation_option(
    prompt="Optimization can take time and requires exclusive access. Continue?"
)
@click.pass_context
def optimize(ctx, vacuum, analyze):
    """Optimize database performance."""
    try:
        db = get_db(ctx)
        results = None

        click.echo("🔧 Optimizing database...")

        with db.session_scope() as session:
            if vacuum or analyze or (not vacuum and not analyze):
                # If no flags or both flags, do full optimization
                results = db.health_monitor.optimize_database(session)
            else:
                # TODO: Implemente partial optimization
                # click.echo("🔧 Running optimization...")
                # Implement partial optimization if needed
                click.echo("Partial optimization not yet implemented.")

        if results:
            click.echo("\n✅ Optimization Complete:")
            if "space_reclaimed_bytes" in results:
                reclaimed = results["space_reclaimed_bytes"]
                click.echo(
                    f"  Space reclaimed: {reclaimed:,} bytes ({reclaimed / 1024 / 1024:.2f} MB)"
                )
            if "vacuum_completed" in results:
                click.echo(f"  VACUUM: {'✓' if results['vacuum_completed'] else '✗'}")
            if "analyze_completed" in results:
                click.echo(f"  ANALYZE: {'✓' if results['analyze_completed'] else '✗'}")
        else:
            click.echo("⚠️  No optimization performed")

    except HealthCheckError as e:
        click.echo(f"❌ Optimization failed: {e}", err=True)
        sys.exit(1)
    except DatabaseError as e:
        click.echo(f"❌ Database error: {e}", err=True)
        sys.exit(1)


# ===== Data Export =====
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

        click.echo("\n✅ Export Complete:")
        for table, path in exported.items():
            click.echo(f"  • {table}: {path}")

    except ExportError as e:
        click.echo(f"❌ CSV export failed: {e}", err=True)
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
        click.echo(f"❌ JSON export failed: {e}", err=True)
        sys.exit(1)


# ===== Advanced Commands =====
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

        # Database stats
        click.echo("\nDatabase Overview:")
        click.echo(json.dumps(stats, indent=2, default=str))

        # Manuscript analytics
        click.echo("\nManuscript Analytics:")
        click.echo(json.dumps(manuscript, indent=2, default=str))

    except DatabaseError as e:
        click.echo(f"❌ Analytics failed: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli(obj={})
