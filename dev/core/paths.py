#!/usr/bin/env python3
"""
paths.py
-------------------
Set of pathlib Paths to be loaded by the modules.
Generate daily Markdown files for Vimwiki reference and PDF generation.

Notes
==============
- Manages two types of 750w metadata entry formats.
- Adds YAML front-matter metadata entries to be filled after review.
"""
from pathlib import Path

# ----- Project directory -----
ROOT: Path = Path(__file__).resolve().parents[2]
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
