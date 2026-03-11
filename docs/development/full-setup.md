# Full Setup Guide

> Use `plm sync` to synchronize database, JSON exports, and wiki after setup or git pull.

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
│   │   └── content/pdf/    # Compiled PDFs
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
plm --help
```

---

## 3. Initialize/Migrate Database

### Fresh Database

If no database exists:
```bash
# Create database with current schema and stamp Alembic
plm db init
```

### Existing Database

If database exists but needs migrations:
```bash
# Check current migration status
plm db migration-status

# Apply pending migrations
plm db upgrade
```

### Verify Database

```bash
# Check pipeline status (includes DB connection test)
plm status

# Should show directory paths and file counts
```

---

## 4. Run Full Pipeline

### Option A: Run Everything

```bash
plm pipeline run --year 2024
```


### Option B: Step by Step

```bash
# 1. Process inbox (raw exports → formatted txt)
plm inbox

# 2. Convert to markdown (txt → md with YAML frontmatter)
plm convert

# 3. Sync: import entries + metadata, export JSON, generate wiki
plm sync

# 4. Build PDFs for a year
plm build pdf 2024
```

---

## 5. Verify Setup

### Check Pipeline Status

```bash
plm status
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
plm validate pipeline
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
plm db upgrade

# Sync everything (imports, exports, wiki)
plm sync
```

### Export Database

```bash
# Export to JSON for version control
plm export
```

### Rebuild PDFs

```bash
# Single year
plm build pdf 2024
```

### Process New Entries

```bash
# 1. Place raw exports in inbox/
# 2. Run inbox processing
plm inbox

# 3. Convert to markdown
plm convert

# 4. Sync database and regenerate outputs
plm sync
```

---

## 7. Troubleshooting

### Database Migration Errors

If migrations fail with SQLite constraint errors:
```bash
# Check current state
plm db migration-status

# For SQLite, some operations need batch mode
# Check if migration uses batch_alter_table for constraint changes
```

### Missing Data Submodule

If `data/` is empty:
```bash
git submodule update --init --recursive
```

### Import Errors

Install in development mode:
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
| `data/metadata/palimpsest.db` | SQLite database |
| `data/wiki/` | Generated vimwiki pages |

---

## 9. Key Commands Reference

```bash
# Pipeline
plm inbox              # Process inbox
plm convert            # txt → md
plm sync               # Synchronize DB ↔ files ↔ wiki
plm export             # Export DB → JSON (manual)
plm build pdf YEAR     # md → pdf
plm pipeline run --year YEAR  # Full pipeline
plm status             # Show status
plm validate           # Run validation

# Database
plm db migration-status  # Check migration status
plm db upgrade           # Apply migrations
plm db downgrade REV     # Rollback to revision

# Testing
pytest tests/ -q       # Run tests
pytest --cov=dev       # With coverage
ruff check dev/        # Linting
```
