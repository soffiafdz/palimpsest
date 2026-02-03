#!/usr/bin/env python3
"""
init_db.py
----------
Initialize a fresh database from SQLAlchemy models.

This script creates all tables defined in dev/database/models/ using
SQLAlchemy's metadata.create_all(). Use this instead of migrations when
starting fresh or when migrations have chain dependencies that don't
work for empty databases.

Usage:
    python -m dev.bin.init_db [--force]

Options:
    --force     Delete existing database without prompting

Notes:
    - Creates tables at the path defined in dev/core/paths.py (DB_PATH)
    - Backs up existing database to .bak if present
    - Seeds controlled vocabularies (motifs)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import shutil
import sys
from datetime import datetime
from pathlib import Path

# --- Third-party imports ---
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

# --- Local imports ---
from dev.core.paths import BACKUP_DIR, DB_PATH
from dev.database.models import Base
from dev.database.models.metadata import CONTROLLED_MOTIFS, Motif


def backup_existing_db(db_path: Path) -> Path | None:
    """
    Backup existing database if it exists.

    Args:
        db_path: Path to the database file

    Returns:
        Path to backup file, or None if no backup was needed
    """
    if not db_path.exists():
        return None

    # Ensure backup directory exists
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{db_path.stem}_pre_init_{timestamp}.db"
    backup_path = BACKUP_DIR / backup_name
    shutil.copy2(db_path, backup_path)
    print(f"Backed up existing database to: {backup_path}")
    return backup_path


def create_fresh_database(db_path: Path, force: bool = False) -> None:
    """
    Create a fresh database with all tables from models.

    Args:
        db_path: Path to the database file
        force: If True, delete existing database without prompting
    """
    # Handle existing database
    if db_path.exists():
        if not force:
            response = input(f"Database exists at {db_path}. Delete and recreate? [y/N]: ")
            if response.lower() != "y":
                print("Aborted.")
                sys.exit(0)

        backup_existing_db(db_path)
        db_path.unlink()
        print(f"Deleted existing database: {db_path}")

    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Create engine and all tables
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)

    # Verify tables were created
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"\nCreated {len(tables)} tables:")
    for table in sorted(tables):
        print(f"  - {table}")

    # Seed controlled vocabularies
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Seed motifs
        print(f"\nSeeding {len(CONTROLLED_MOTIFS)} controlled motifs...")
        for motif_name in CONTROLLED_MOTIFS:
            motif = Motif(name=motif_name)
            session.add(motif)
        session.commit()
        print("Motifs seeded successfully.")
    except Exception as e:
        session.rollback()
        print(f"Error seeding motifs: {e}")
        raise
    finally:
        session.close()

    print(f"\nDatabase created successfully at: {db_path}")


def main() -> None:
    """Main entry point."""
    force = "--force" in sys.argv

    print("=" * 60)
    print("Palimpsest Database Initialization")
    print("=" * 60)
    print(f"\nTarget: {DB_PATH}")

    create_fresh_database(DB_PATH, force=force)


if __name__ == "__main__":
    main()
