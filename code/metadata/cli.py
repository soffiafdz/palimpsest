#!/usr/bin/env python3
"""
cli.py
-------------------
Command-line interface for Palimpsest database management.

Provides commands to initialize the database, set up Alembic migrations,
create initial migration files, and inspect or backup the database.
This CLI is meant for local setup and maintenance; it does not serve a web API.

Commands:
    - bootstrap           Initialize Alembic + database + initial migration (full setup)
    - init-alembic        Initialize Alembic migration environment only
    - init-db             Initialize or migrate the database only
    - create-migration    Create a new Alembic migration file
    - upgrade-db          Upgrade the database to a specified revision (default: head)
    - downgrade-db        Downgrade the database to a specified revision
    - backup-db           Create a timestamped backup of the SQLite database
    - stats               Print database statistics (counts of entries, people, events, etc.)
    - validate            Validate database integrity and relationships
    - cleanup             Clean up unused metadata entries
    - migration-status    Show current migration status

Notes
==============
- Uses the Palimpsest class to manage database and Alembic operations.
- Intended for first-time setup or maintenance of the local SQLite DB.
- No webserver functionality included.
"""
import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
from code.metadata.manager import PalimpsestDB, DatabaseError, ValidationError
from code.metadata.models import Entry
from code.paths import METADATA_DB, METADATA_ALEMBIC

# ----- Logging -----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ----- Functions -----
def ensure_directories_exist(db_path: Path, alembic_dir: Path) -> None:
    """Ensure database and alembic directories exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    alembic_dir.parent.mkdir(parents=True, exist_ok=True)


def format_stats_output(stats: dict, verbose: bool = False) -> None:
    """Format and print database statistics."""
    print("\n" + "=" * 50)
    print("DATABASE STATISTICS")
    print("=" * 50)

    # Core tables
    core_tables = [
        "entries",
        "dates",
        "locations",
        "people",
        "aliases",
        "references",
        "references_sources",
        "events",
        "poems",
        "poem_versions",
        "tags",
    ]

    print("\nCore Tables:")
    print("-" * 20)
    for table in core_tables:
        if table in stats:
            count = stats[table]
            print(f"  {table:20}: {count:6,}")

    # Manuscript tables
    manuscript_tables = [
        "manuscript_entries",
        "manuscript_people",
        "manuscript_events",
        "arcs",
        "themes",
    ]

    print("\nManuscript Tables:")
    print("-" * 20)
    for table in manuscript_tables:
        if table in stats:
            count = stats[table]
            print(f"  {table:20}: {count:6,}")

    # Recent activity
    if "entries_updated_last_7_days" in stats:
        print("\nRecent Activity:")
        print("-" * 20)
        print(f"  entries updated (7d) : {stats['entries_updated_last_7_days']:6,}")

    # Migration status
    if "migration_status" in stats:
        print("\nMigration Status:")
        print("-" * 20)
        migration_info = stats["migration_status"]
        if "error" in migration_info:
            print(f"  status              : ERROR - {migration_info['error']}")
        else:
            current_rev = migration_info.get("current_revision", "None")
            status = migration_info.get("status", "unknown")
            print(f"  current revision    : {current_rev}")
            print(f"  status              : {status}")

    # Verbose mode adds extra details
    if verbose:
        print("\nDetailed Information:")
        print("-" * 20)
        total_entries = stats.get("entries", 0)
        total_people = stats.get("people", 0)
        total_locations = stats.get("locations", 0)

        if total_entries > 0:
            avg_people_per_entry = (
                total_people / total_entries if total_people > 0 else 0
            )
            avg_locations_per_entry = (
                total_locations / total_entries if total_locations > 0 else 0
            )
            print(f"  avg people/entry     : {avg_people_per_entry:.2f}")
            print(f"  avg locations/entry  : {avg_locations_per_entry:.2f}")

        # Show all stats in verbose mode
        print("\nAll Statistics:")
        print("-" * 20)
        for key, value in sorted(stats.items()):
            if key not in ["migration_status"] and not key.startswith(
                "entries_updated"
            ):
                print(f"  {key:20}: {value:6,}")

    print("=" * 50 + "\n")


# ----- Main -----
def main() -> int:
    """Parse CLI arguments and execute the appropriate database actions."""
    parser = argparse.ArgumentParser(description="Palimpsest Database CLI")

    # Global arguments
    parser.add_argument(
        "--db",
        type=Path,
        default=METADATA_DB,
        help="Path to SQLite database (default: data/palimpsest.db)",
    )
    parser.add_argument(
        "--alembic-dir",
        type=Path,
        default=METADATA_ALEMBIC,
        help="Directory for Alembic migrations (default: alembic)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- Bootstrap command ---
    subparsers.add_parser(
        "bootstrap",
        help="Complete setup: Initialize Alembic, database, and create initial migration",
    )

    # --- Init Alembic ---
    subparsers.add_parser(
        "init-alembic", help="Initialize Alembic migration environment only"
    )

    # --- Init database ---
    subparsers.add_parser("init-db", help="Initialize or migrate the database only")

    # --- Create migration ---
    parser_migrate = subparsers.add_parser(
        "create-migration", help="Create a new Alembic migration"
    )
    parser_migrate.add_argument("message", type=str, help="Migration description")

    # --- Upgrade database ---
    parser_upgrade = subparsers.add_parser(
        "upgrade-db", help="Upgrade database to a given revision"
    )
    parser_upgrade.add_argument(
        "--revision", type=str, default="head", help="Target revision (default: head)"
    )

    # --- Downgrade database ---
    parser_downgrade = subparsers.add_parser(
        "downgrade-db", help="Downgrade database to a given revision"
    )
    parser_downgrade.add_argument(
        "revision", type=str, help="Target revision (required)"
    )

    # --- Backup database ---
    parser_backup = subparsers.add_parser(
        "backup-db", help="Create a timestamped backup of the database"
    )
    parser_backup.add_argument(
        "--suffix", type=str, help="Custom suffix for backup file (default: timestamp)"
    )

    # --- Migration status ---
    subparsers.add_parser(
        "migration-status", help="Show current migration status and history"
    )

    # --- Stats ---
    parser_stats = subparsers.add_parser("stats", help="Print database statistics")
    parser_stats.add_argument(
        "--tables",
        type=str,
        help="Comma-separated list of tables to show stats for (default: all)",
    )
    parser_stats.add_argument(
        "--recent-days",
        type=int,
        default=7,
        help="Include count of entries updated in the last N days (default: 7)",
    )

    # --- Validate ---
    subparsers.add_parser(
        "validate", help="Validate database integrity and check for issues"
    )

    # --- Cleanup ---
    parser_cleanup = subparsers.add_parser(
        "cleanup", help="Clean up unused metadata entries (tags, locations, etc.)"
    )
    parser_cleanup.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be cleaned up without making changes",
    )

    args = parser.parse_args()

    # Set logging level based on verbose flag
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose mode enabled")

    # Initialize paths
    db_path = Path(args.db).expanduser().resolve()
    alembic_dir = Path(args.alembic_dir).expanduser().resolve()

    logger.debug(f"Database path: {db_path}")
    logger.debug(f"Alembic directory: {alembic_dir}")

    # Ensure directories exist
    ensure_directories_exist(db_path, alembic_dir)

    try:
        # Initialize PalimpsestDB manager
        logger.debug("Initializing database manager...")
        manager = PalimpsestDB(db_path=db_path, alembic_dir=alembic_dir)

        # --- Dispatch commands ---
        if args.command == "bootstrap":
            logger.info("Starting complete database bootstrap...")
            logger.info("Step 1/4: Initializing Alembic...")
            manager.init_alembic()

            logger.info("Step 2/4: Initializing database...")
            manager.init_database()

            logger.info("Step 3/4: Creating initial migration...")
            manager.create_migration("Initial schema")

            logger.info("Step 4/4: Generating statistics...")
            stats = manager.get_database_stats()
            format_stats_output(stats)

            logger.info("Bootstrap complete! Database is ready to use.")

        elif args.command == "init-alembic":
            logger.info("Initializing Alembic migration environment...")
            manager.init_alembic()
            logger.info("Alembic initialization complete.")

        elif args.command == "init-db":
            logger.info("Initializing database...")
            manager.init_database()
            logger.info("Database initialization complete.")

        elif args.command == "create-migration":
            logger.info(f"Creating migration: '{args.message}'...")
            manager.create_migration(args.message)
            logger.info(f"Migration '{args.message}' created successfully.")

        elif args.command == "upgrade-db":
            logger.info(f"Upgrading database to {args.revision}...")
            manager.upgrade_database(args.revision)
            logger.info(f"Database upgraded to {args.revision} successfully.")

        elif args.command == "downgrade-db":
            logger.warning(f"Downgrading database to {args.revision}...")
            response = input(
                "Are you sure you want to downgrade? This may cause data loss. (y/N): "
            )
            if response.lower() != "y":
                logger.info("Downgrade cancelled.")
                return 0

            manager.downgrade_database(args.revision)
            logger.info(f"Database downgraded to {args.revision} successfully.")

        elif args.command == "backup-db":
            logger.info("Creating database backup...")
            backup_file = manager.backup_database(args.suffix)
            logger.info(f"Database backed up successfully to: {backup_file}")

        elif args.command == "migration-status":
            logger.info("Checking migration status...")
            status = manager.get_migration_history()

            print("\nMigration Status:")
            print("-" * 30)
            if "error" in status:
                print(f"ERROR: {status['error']}")
                return 1
            else:
                current_rev = status.get("current_revision", "None")
                migration_status = status.get("status", "unknown")
                print(f"Current revision: {current_rev}")
                print(f"Status: {migration_status}")

        elif args.command == "stats":
            logger.info("Retrieving database statistics...")
            stats = manager.get_database_stats()

            # Filter tables if requested
            if args.tables:
                requested = {t.strip() for t in args.tables.split(",")}
                stats = {
                    k: v
                    for k, v in stats.items()
                    if k in requested or k == "migration_status"
                }

            # Adjust recent entries count if different from default
            if args.recent_days != 7:
                with manager.session_scope() as session:
                    cutoff = datetime.now() - timedelta(days=args.recent_days)
                    recent_count = (
                        session.query(Entry).filter(Entry.updated_at >= cutoff).count()
                    )
                    stats[f"entries_updated_last_{args.recent_days}_days"] = (
                        recent_count
                    )
                    stats.pop("entries_updated_last_7_days", None)

            format_stats_output(stats, args.verbose)

        elif args.command == "validate":
            logger.info("Validating database integrity...")

            # Basic validation checks
            with manager.session_scope() as session:
                # Check for entries without files
                missing_files = (
                    session.query(Entry).filter(Entry.file_path.is_(None)).count()
                )

                # Check for orphaned references
                from code.metadata.models import Reference

                orphaned_refs = (
                    session.query(Reference)
                    .filter(Reference.entry_id.is_(None))
                    .count()
                )

                issues = []
                if missing_files > 0:
                    issues.append(
                        f"Found {missing_files} entries with missing file paths"
                    )
                if orphaned_refs > 0:
                    issues.append(f"Found {orphaned_refs} orphaned references")

                if issues:
                    logger.warning("Database validation found issues:")
                    for issue in issues:
                        logger.warning(f"  - {issue}")
                    return 1
                else:
                    logger.info("Database validation passed - no issues found.")

        elif args.command == "cleanup":
            if args.dry_run:
                logger.info("Running cleanup in dry-run mode...")
                # Note: This would require implementing a dry-run mode in the manager
                logger.info(
                    "Dry-run mode not yet implemented. Use without --dry-run to proceed."
                )
                return 1
            else:
                logger.info("Cleaning up unused metadata entries...")
                results = manager.cleanup_all_metadata()

                total_cleaned = sum(results.values())
                if total_cleaned > 0:
                    logger.info(
                        f"Cleanup completed. Removed {total_cleaned} unused entries:"
                    )
                    for table, count in results.items():
                        if count > 0:
                            logger.info(f"  - {table}: {count} entries")
                else:
                    logger.info("No unused entries found - database is clean.")

        else:
            logger.error(f"Unknown command: {args.command}")
            return 1

    except DatabaseError as e:
        logger.error(f"Database error: {e}")
        return 1
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        return 1
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user.")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback

            logger.debug(traceback.format_exc())
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
