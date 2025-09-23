#!/usr/bin/env python3
"""
cli.py
-------------------
Command-line interface for Palimpsest database management.

Provides commands to initialize the database, set up Alembic migrations,
create initial migration files, and inspect or backup the database.
This CLI is meant for local setup and maintenance; it does not serve a web API.

Commands:
    - bootstrap           Initialize Alembic + database + initial migration
    - init-db             Initialize or migrate the database
    - create-migration    Create a new Alembic migration file
    - upgrade-db          Upgrade the database to a specified revision (default: head)
    - downgrade-db        Downgrade the database to a specified revision
    - backup-db           Create a timestamped backup of the SQLite database
    - stats               Print database statistics (counts of entries, people, events, etc.)

Notes
==============
- Uses the DBManager class to manage database and Alembic operations.
- Intended for first-time setup or maintenance of the local SQLite DB.
- No webserver functionality included.
"""
import argparse
import logging
from pathlib import Path
from scripts.metadata.manager import PalimpsestDB
from scripts.metadata.models import Entry

logger = logging.getLogger(__name__)


def main() -> None:
    """Parse CLI arguments and execute the appropriate DBManager actions."""
    parser = argparse.ArgumentParser(description="Palimpsest Database CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- Bootstrap command ---
    parser_bootstrap = subparsers.add_parser(
        "bootstrap", help="Initialize Alembic, database, and initial migration"
    )
    parser_bootstrap.add_argument(
        "--db", type=str, default="data/palimpsest.db", help="Path to SQLite database"
    )
    parser_bootstrap.add_argument(
        "--alembic-dir",
        type=str,
        default="alembic",
        help="Directory for Alembic migrations",
    )

    # --- Create migration ---
    parser_migrate = subparsers.add_parser(
        "create-migration", help="Create a new Alembic migration"
    )
    parser_migrate.add_argument("message", type=str, help="Migration description")

    # --- Upgrade database ---
    parser_upgrade = subparsers.add_parser(
        "upgrade-db", help="Upgrade database to a given revision (default: head)"
    )
    parser_upgrade.add_argument(
        "--revision", type=str, default="head", help="Target revision"
    )

    # --- Downgrade database ---
    parser_downgrade = subparsers.add_parser(
        "downgrade-db", help="Downgrade database to a given revision"
    )
    parser_downgrade.add_argument("revision", type=str, help="Target revision")

    # --- Backup database ---
    parser_backup = subparsers.add_parser(
        "backup-db", help="Backup the database to a timestamped file"
    )
    parser_backup.add_argument("--suffix", type=str, help="Suffix for backup file")

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

    args = parser.parse_args()

    # Initialize DBManager
    db_path = Path(getattr(args, "db", "data/palimpsest.db"))
    alembic_dir = Path(getattr(args, "alembic_dir", "alembic"))
    manager = PalimpsestDB(db_path=db_path, alembic_dir=alembic_dir)

    # --- Dispatch commands ---
    if args.command == "bootstrap":
        logger.info("Bootstrapping database...")
        manager.init_alembic()
        manager.init_database()
        manager.create_migration("Initial schema")
        logger.info("Bootstrap complete.")

    elif args.command == "create-migration":
        manager.create_migration(args.message)
        logger.info(f"Migration '{args.message}' created.")

    elif args.command == "upgrade-db":
        manager.upgrade_database(args.revision)
        logger.info(f"Database upgraded to {args.revision}.")

    elif args.command == "downgrade-db":
        manager.downgrade_database(args.revision)
        logger.info(f"Database downgraded to {args.revision}.")

    elif args.command == "backup-db":
        backup_file = manager.backup_database(args.suffix)
        logger.info(f"Database backed up to: {backup_file}")

    elif args.command == "stats":
        stats = manager.get_database_stats()

        # Filter tables if requested
        if args.tables:
            requested = {t.strip() for t in args.tables.split(",")}
            stats = {
                k: v
                for k, v in stats.items()
                if k in requested or k == "migration_status"
            }

        # Adjust recent entries count
        if "entries_updated_last_7_days" in stats and args.recent_days != 7:
            from datetime import datetime, timedelta

            with manager.session_scope() as session:
                week_ago = datetime.now() - timedelta(days=args.recent_days)
                stats["entries_updated_last_N_days"] = (
                    session.query(Entry).filter(Entry.updated_at >= week_ago).count()
                )
            stats.pop("entries_updated_last_7_days", None)

        for key, value in stats.items():
            logger.info(f"{key}: {value}")


if __name__ == "__main__":
    main()
