#!/usr/bin/env python3
"""
paths.py
-------------------
Path constants and configuration for the Palimpsest project.

This module defines all project paths as Path objects for consistent path handling
across the codebase. Paths are organized by category (journal, database, dev tools, etc.)
and relative to the project root directory.

The project structure:
    ROOT/
    ├── dev/           # Development code and scripts
    ├── data/          # User data (journal, metadata, wiki)
    ├── logs/          # Application logs
    ├── backups/       # Database backups
    └── tmp/           # Temporary files

All paths are resolved at import time and validated to ensure the project
structure is intact.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import sys
from pathlib import Path


def _get_project_root() -> Path:
    """
    Determine project root directory.

    Assumes this file is at ROOT/dev/core/paths.py and navigates up
    the directory tree to find ROOT.

    Returns:
        Path object for project root

    Raises:
        RuntimeError: If project root cannot be determined or validated
    """
    current_file = Path(__file__).resolve()

    # Navigate up: paths.py -> core/ -> dev/ -> ROOT/
    root = current_file.parent.parent.parent

    # Validate that this looks like a valid project root
    # Check for dev directory as a sanity check
    if not (root / "dev").is_dir():
        raise RuntimeError(
            f"Cannot determine valid project root. "
            f"Expected {root / 'dev'} to exist. "
            f"Current file: {current_file}"
        )

    return root


# ----- Project directory -----
ROOT: Path = _get_project_root()
DATA_DIR = ROOT / "data"  # Personal data (private)

# ---- Dev ----
DEV_DIR = ROOT / "dev"

# --- Converters/Pipeline ---
FORMATTING_SCRIPT = DEV_DIR / "bin" / "init_format"
TEX_DIR = ROOT / "templates" / "tex"

# --- Database ---
ALEMBIC_DIR = DEV_DIR / "migrations"
DB_DIR = DATA_DIR / "metadata"
DB_PATH = DB_DIR / "palimpsest.db"

# ---- Journal ----
JOURNAL_DIR = DATA_DIR / "journal"
INBOX_DIR = JOURNAL_DIR / "inbox"
ARCHIVE_DIR = JOURNAL_DIR / "sources" / "archive"
TXT_DIR = JOURNAL_DIR / "sources" / "txt"
MD_DIR = JOURNAL_DIR / "content" / "md"
PDF_DIR = JOURNAL_DIR / "content" / "pdf"

# ---- Narrative Structure (Scenes/Events/Arcs) ----
NARRATIVE_ANALYSIS_DIR = JOURNAL_DIR / "narrative_analysis"
EVENTS_DIR = NARRATIVE_ANALYSIS_DIR / "_events"
ARCS_DIR = NARRATIVE_ANALYSIS_DIR / "_arcs"

# ---- Logs & Temp & Backups----
LOG_DIR = ROOT / "logs"
TMP_DIR = ROOT / "tmp"
BACKUP_DIR = ROOT / "backups"

# ---- Vignettes ----
VIGNETTES_DIR = DATA_DIR / "vignettes"

# ---- Vimwiki ----
WIKI_DIR = DATA_DIR / "wiki"
INVENTORY_DIR = WIKI_DIR / "inventory"
PEOPLE_DIR = WIKI_DIR / "people"
SNIPPETS_DIR = WIKI_DIR / "snippets"


# ----- Path Validation -----
def _validate_critical_paths() -> None:
    """
    Validate that critical paths exist.

    Checks that essential directories exist and are accessible.
    Prints warnings for missing paths but doesn't fail - allows
    the module to be imported even if data directories aren't set up yet.
    """
    # Critical paths that should always exist
    critical_paths = [
        (ROOT, "project root"),
        (DEV_DIR, "development directory"),
    ]

    # Warn about missing critical paths
    missing_paths = []
    for path, description in critical_paths:
        if not path.exists():
            missing_paths.append(f"{description} ({path})")

    if missing_paths:
        print(
            "Warning: Critical paths missing:\n  " + "\n  ".join(missing_paths),
            file=sys.stderr,
        )


# Validate paths on module import
_validate_critical_paths()
