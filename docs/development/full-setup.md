# Full Setup Guide

> **Note:** Wiki-related steps (`export-wiki`, `WikiExporter`) are not yet implemented.
> Use `plm import-metadata` for database import and `plm export-db` for exports.

Complete instructions for setting up Palimpsest from scratch on a new machine.

---

## Prerequisites

- Python 3.10+
- Git
- [micromamba](https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html) or conda
- SQLite 3
- LaTeX (for PDF generation): `texlive` or similar

---

## 1. Clone Repository with Data Submodule

```bash
# Clone main repository
git clone git@github.com:soffiafdz/palimpsest.git
cd palimpsest

# Initialize and clone data submodule
git submodule update --init --recursive
```

This creates:
```
palimpsest/
├── dev/                    # Source code
├── docs/                   # Documentation
├── tests/                  # Test suite
├── templates/              # LaTeX templates
├── data/                   # Data submodule (private)
│   ├── journal/
│   │   ├── inbox/          # New entries
│   │   ├── sources/txt/    # Formatted text by year
│   │   ├── content/md/     # Markdown entries by year
│   │   ├── content/pdf/    # Compiled PDFs
│   │   └── narrative_analysis/
│   ├── metadata/           # SQLite database
│   ├── wiki/               # Generated wiki
│   └── vignettes/          # Special entries
└── environment.yaml        # Conda environment
```

---

## 2. Create Python Environment

```bash
# Using micromamba (recommended)
micromamba env create -f environment.yaml
micromamba activate palimpsest

# Or using conda
conda env create -f environment.yaml
conda activate palimpsest
```

Verify installation:
```bash
python -m dev.pipeline.cli --help
```

---

## 3. Initialize/Migrate Database

### Fresh Database

If no database exists:
```bash
# Create database with current schema
alembic upgrade head
```

### Existing Database

If database exists but needs migrations:
```bash
# Check current migration status
alembic current

# Check available migrations
alembic heads

# Apply pending migrations
alembic upgrade head
```

### Verify Database

```bash
# Check pipeline status (includes DB connection test)
python -m dev.pipeline.cli status

# Should show directory paths and file counts
```

---

## 4. Run Full Pipeline

### Option A: Run Everything

```bash
python -m dev.pipeline.cli run-all 2024
```

This runs: inbox → convert → sync-db → export-wiki → build-pdf for the specified year.

### Option B: Step by Step

```bash
# 1. Process inbox (raw exports → formatted txt)
python -m dev.pipeline.cli inbox

# 2. Convert to markdown (txt → md with YAML frontmatter)
python -m dev.pipeline.cli convert

# 3. Sync database (md YAML → SQLite)
python -m dev.pipeline.cli sync-db

# 4. Export wiki (database → wiki pages)
python -m dev.pipeline.cli export-wiki

# 5. Build PDFs for a year
python -m dev.pipeline.cli build-pdf 2024
```

---

## 5. Verify Setup

### Check Pipeline Status

```bash
python -m dev.pipeline.cli status
```

Expected output:
```
📊 Pipeline Status

Directories:
  ✓ Inbox: .../data/journal/inbox
  ✓ Text: .../data/journal/sources/txt
  ✓ Markdown: .../data/journal/content/md
  ✓ PDF: .../data/journal/content/pdf

File counts:
  - txt files: N
  - md files: N
  - pdf files: N

Database:
  - Entries: N
  - People: N
  - Locations: N
  ...
```

### Run Validation

```bash
python -m dev.pipeline.cli validate
```

### Run Tests

```bash
python -m pytest tests/ -q
```

---

## 6. Common Tasks

### Update After Pull

After pulling new changes:
```bash
# Update submodule
git submodule update --recursive

# Apply any new migrations
alembic upgrade head

# Regenerate wiki if needed
python -m dev.pipeline.cli export-wiki
```

### Regenerate Wiki

```bash
# Full wiki regeneration
python -m dev.pipeline.cli export-wiki --force

# Narrative pages only (arcs, events, scenes)
python -c "
from dev.wiki.exporter import WikiExporter
from dev.database.manager import PalimpsestDB
from dev.core.paths import DB_PATH, WIKI_DIR

db = PalimpsestDB(DB_PATH)
exporter = WikiExporter(db, WIKI_DIR)
exporter.export_narrative(force=True)
"
```

### Rebuild PDFs

```bash
# Single year
python -m dev.pipeline.cli build-pdf 2024

# With notes version
python -m dev.pipeline.cli build-pdf 2024 --notes
```

### Process New Entries

```bash
# 1. Place raw exports in inbox/
# 2. Run inbox processing
python -m dev.pipeline.cli inbox

# 3. Convert to markdown
python -m dev.pipeline.cli convert

# 4. Sync to database
python -m dev.pipeline.cli sync-db

# 5. Update wiki
python -m dev.pipeline.cli export-wiki
```

---

## 7. Troubleshooting

### Database Migration Errors

If migrations fail with SQLite constraint errors:
```bash
# Check current state
alembic current

# For SQLite, some operations need batch mode
# Check if migration uses batch_alter_table for constraint changes
```

### Missing Data Submodule

If `data/` is empty:
```bash
git submodule update --init --recursive
```

### Import Errors

Ensure PYTHONPATH includes project root:
```bash
PYTHONPATH=/path/to/palimpsest python -m dev.pipeline.cli status
```

Or install in development mode:
```bash
pip install -e .
```

### PDF Build Failures

Ensure LaTeX is installed:
```bash
# Arch Linux
sudo pacman -S texlive-basic texlive-latex texlive-latexextra

# Ubuntu/Debian
sudo apt install texlive-latex-base texlive-latex-extra
```

---

## 8. Directory Reference

| Directory | Purpose |
|-----------|---------|
| `data/journal/inbox/` | Raw 750words exports drop zone |
| `data/journal/sources/txt/YYYY/` | Formatted text files by year |
| `data/journal/content/md/YYYY/` | Markdown entries with YAML |
| `data/journal/content/pdf/` | Compiled PDFs |
| `data/journal/narrative_analysis/` | Analysis files and manifests |
| `data/metadata/palimpsest.db` | SQLite database |
| `data/wiki/` | Generated vimwiki pages |

---

## 9. Key Commands Reference

```bash
# Pipeline
plm inbox              # Process inbox
plm convert            # txt → md
plm sync-db            # md → database
plm export-wiki        # database → wiki
plm build-pdf YEAR     # md → pdf
plm run-all YEAR       # Full pipeline
plm status             # Show status
plm validate           # Run validation

# Database
alembic current        # Check migration status
alembic upgrade head   # Apply migrations
alembic downgrade -1   # Rollback one migration

# Testing
pytest tests/ -q       # Run tests
pytest --cov=dev       # With coverage
ruff check dev/        # Linting
```
