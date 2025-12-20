"""
Palimpsest Development Package
===============================

A personal journal metadata management and PDF compilation system.

This package contains the complete toolkit for processing, organizing, and
analyzing journal entries with rich metadata. It converts raw text exports
into structured Markdown files with YAML frontmatter, maintains a SQLite
database of relationships and themes, and generates annotated PDFs for
review and curation.

Main Components:
    - pipeline: Multi-stage processing (src -> txt -> md -> db -> pdf)
    - database: SQLAlchemy ORM with entity managers and query analytics
    - builders: PDF and text generation
    - core: Logging, validation, paths, backup management
    - dataclasses: Entry data structures (Markdown, Wiki, Text)
    - utils: Filesystem, markdown, wiki, and parser utilities

Primary Interfaces:
    - dev.pipeline.cli: Pipeline orchestration CLI
    - dev.database.cli: Database management CLI
    - dev.database.manager.PalimpsestDB: Main database interface

Example Usage:
    >>> from dev.database import PalimpsestDB
    >>> from dev.core.paths import DB_PATH, ALEMBIC_DIR, LOG_DIR
    >>> db = PalimpsestDB(db_path=DB_PATH, alembic_dir=ALEMBIC_DIR, log_dir=LOG_DIR)
    >>> with db.session_scope() as session:
    ...     entries = session.query(Entry).filter(Entry.year == 2024).all()

Version: 2.0.0
Author: Part of Palimpsest project
License: MIT

See Also:
    - README.md: Project overview and quick start
    - dev/database/managers/README.md: Manager architecture overview
"""

__version__ = "2.0.0"
__author__ = "Palimpsest Project"

# Expose primary interfaces for convenience
from dev.database.manager import PalimpsestDB
from dev.core.paths import DATA_DIR, DB_PATH, LOG_DIR, MD_DIR, PDF_DIR

__all__ = [
    "PalimpsestDB",
    "DATA_DIR",
    "DB_PATH",
    "LOG_DIR",
    "MD_DIR",
    "PDF_DIR",
]
