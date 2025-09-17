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
├── scripts
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

# Project directory
ROOT: Path = Path(__file__).resolve().parents[1]

# Scripts directories
TXT2MD_DIR: Path = ROOT / "scripts" / "txt2md"
MD2WIKI_DIR: Path = ROOT / "scripts" / "md2wiki"

# Journal directories
ARCHIVE_DIR: Path = ROOT / "journal" / "archive"
INBOX_DIR: Path = ROOT / "journal" / "inbox"
LATEX_DIR: Path = ROOT / "journal" / "latex"
MD_DIR: Path = ROOT / "journal" / "md"
TXT_DIR: Path = ROOT / "journal" / "txt"
PDF_DIR: Path = ROOT / "journal" / "pdf"

# Metadata DB
METADATA_DB: Path = ROOT / "palimpsest.db"
METADATA_ALEMBIC: Path = ROOT / "alembic"

# Wiki directories
WIKI_DIR: Path = ROOT / "wiki"
INVENTORY_DIR: Path = WIKI_DIR / "inventory"
PEOPLE_DIR: Path = WIKI_DIR / "people"
SNIPPETS_DIR: Path = WIKI_DIR / "snippets"

# Vignettes
VIGNETTES_DIR: Path = ROOT / "vignettes"
