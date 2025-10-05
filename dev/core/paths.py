#!/usr/bin/env python3
"""
paths.py
-------------------
Set of pathlib Paths to be loaded by the modules.
Generate daily Markdown files for Vimwiki reference and PDF generation.

├── journal
│   ├── archive
│   ├── bin
│   ├── inbox
│   ├── latex
│   ├── md
│   │   ├── 2015
│   │   ├── 2016
│   │   ├── 2017
│   │   ├── 2018
│   │   ├── 2019
│   │   ├── 2021
│   │   ├── 2022
│   │   ├── 2023
│   │   ├── 2024
│   │   └── 2025
│   ├── pdf
│   ├── txt
│   │   ├── 2015
│   │   ├── 2016
│   │   ├── 2017
│   │   ├── 2018
│   │   ├── 2019
│   │   ├── 2021
│   │   ├── 2022
│   │   ├── 2023
│   │   ├── 2024
│   │   └── 2025
│   └── metadata.json
├── code
│   ├── md2json
│   ├── md2pdf
│   ├── md2wiki
│   └── txt2md
├── vignettes
└── wiki
    ├── log
    ├── people
    └── snippets
Notes
==============
- Manages two types of 750w metadata entry formats.
- Adds YAML front-matter metadata entries to be filled after review.
"""
from pathlib import Path

# ----- Project directory -----
ROOT: Path = Path(__file__).resolve().parents[1]

# ---- Dev ----
DEV_DIR = ROOT / "dev"

# --- Converters/Pipeline ---
FORMATTING_SCRIPT = DEV_DIR / "bin" / "init_format"
# TODO: Adapt these. New logic for structure
# TXT2MD_DIR: Path = ROOT / "code" / "txt2md"
# MD2WIKI_DIR: Path = ROOT / "code" / "md2wiki"

# --- Database ---
DB_PATH = ROOT / "palimpsest.db"
ALEMBIC_DIR = DEV_DIR / "migrations"

# ---- Journal ----
# LATEX_DIR = ROOT / "journal" / "latex"
JOURNAL_DIR = ROOT / "journal"
INBOX_DIR = JOURNAL_DIR / "inbox"
ARCHIVE_DIR = JOURNAL_DIR / "sources" / "archive"
TXT_DIR = JOURNAL_DIR / "sources" / "txt"
MD_DIR = JOURNAL_DIR / "content" / "md"
PDF_DIR = JOURNAL_DIR / "content" / "pdf"

# ---- Backup & Logs & Temp ----
BACKUP_DIR = ROOT / "backups"
LOG_DIR = ROOT / "logs"
TMP_DIR = ROOT / "tmp"

# ---- Templates ----
TEX_DIR = ROOT / "templates" / "tex"

# ---- Vignettes ----
VIGNETTES_DIR = ROOT / "vignettes"

# ---- Vimwiki ----
WIKI_DIR = ROOT / "wiki"
INVENTORY_DIR = WIKI_DIR / "inventory"
PEOPLE_DIR = WIKI_DIR / "people"
SNIPPETS_DIR = WIKI_DIR / "snippets"
