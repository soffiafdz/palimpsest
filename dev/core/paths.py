#!/usr/bin/env python3
"""
paths.py
-------------------
Path constants and configuration for the Palimpsest project.

This module defines all project paths as Path objects for consistent path handling
across the codebase. Paths are organized by category (journal, database, dev tools, etc.)
and relative to the project root directory.

Project Structure:
    ROOT/
    ├── dev/                          # Development code and scripts
    ├── data/
    │   ├── metadata/
    │   │   ├── palimpsest.db         # SQLite database
    │   │   ├── journal/{YYYY}/       # Journal YAML exports
    │   │   └── manuscript/           # Manuscript YAML exports
    │   ├── journal/
    │   │   └── content/md/           # Journal entries (ground truth prose)
    │   ├── wiki/                     # VimWiki output (source of truth for metadata)
    │   ├── manuscript/drafts/        # Prose drafts for longer chapters
    │   ├── legacy/                   # Archived data (extracted notes, etc.)
    │   └── narrative_analysis/       # DEPRECATED: delete after jumpstart
    ├── logs/                         # Application logs
    ├── backups/                      # Database backups
    └── tmp/                          # Temporary files

Ground Truth Sources:
    - Journal prose: MD files (data/journal/content/md/)
    - Journal metadata: Wiki (editable) → DB → YAML export
    - Manuscript content: Wiki + drafts → DB → YAML export

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

# ---- Narrative Analysis (DEPRECATED: delete after jumpstart) ----
NARRATIVE_ANALYSIS_DIR = DATA_DIR / "narrative_analysis"

# ---- Entity Curation ----
CURATION_DIR = DATA_DIR / "curation"
CURATION_PEOPLE_DIR = CURATION_DIR / "people"
CURATION_LOCATIONS_DIR = CURATION_DIR / "locations"

# ---- Metadata YAML Exports ----
# Machine-generated exports for git version control
METADATA_DIR = DATA_DIR / "metadata"
JOURNAL_YAML_DIR = METADATA_DIR / "journal"      # Journal YAML exports by year
MANUSCRIPT_YAML_DIR = METADATA_DIR / "manuscript"  # Manuscript YAML exports
MANUSCRIPT_CHAPTERS_DIR = MANUSCRIPT_YAML_DIR / "chapters"
MANUSCRIPT_CHARACTERS_DIR = MANUSCRIPT_YAML_DIR / "characters"

# ---- Manuscript Drafts ----
MANUSCRIPT_DIR = DATA_DIR / "manuscript"
DRAFTS_DIR = MANUSCRIPT_DIR / "drafts"           # Prose drafts for longer chapters

# ---- Legacy Archive ----
LEGACY_DIR = DATA_DIR / "legacy"
NOTES_ARCHIVE = LEGACY_DIR / "notes_archive.yaml"  # Extracted notes from MD frontmatter

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
EVENTS_DIR = WIKI_DIR / "events"


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
