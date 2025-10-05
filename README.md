# Palimpsest

**A personal journal metadata management and PDF compilation system.**

Palimpsest is a personal project consisting of a Python-based toolkit for processing, organizing, and analyzing journal entries with rich metadata. It converts raw text exports into structured Markdown files with YAML frontmatter, maintains a SQLite database of relationships and themes, and generates annotated PDFs for review and curation.

Originally built for managing my decade+ archive from [750words.com](https://750words.com), Palimpsest provides me the infrastructure for transforming my personal documentary writings into searchable, cross-referenced material suitable for memoir or creative non-fiction projects.

---

## Features

- **Multi-stage processing pipeline**: Raw exports → Formatted text → Markdown → Database → PDFs
- **Rich metadata extraction**: Track people, locations, events, themes, dates, and references
- **Database-backed queries**: SQLAlchemy ORM with relationship mapping and analytics
- **PDF generation**: Create clean reading copies and annotated review versions
- **Vim/Neovim integration**: Vimwiki templates and automation (optional)
- **Makefile orchestration**: Simple commands for batch processing and year-based builds

---

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/soffiafdz/palimpsest.git
cd palimpsest

# Create conda/micromamba environment
micromamba env create -f environment.yaml
micromamba activate palimpsest

# Set up data directory (private submodule or local)
# Option 1: With private submodule
git submodule update --init --recursive

# Option 2: Create local data directory
mkdir -p data/journal/{inbox,sources/txt,content/{md,pdf}}
mkdir -p data/metadata

# Initialize database
metadb init
```

### Basic Usage

```bash
# Process new journal exports
journal inbox

# Convert to markdown
journal convert

# Sync database
journal sync

# Build PDFs for a year
journal pdf 2024

# Or run complete pipeline
journal run-all 2024
```

### Using Make

```bash
# Process everything
make all

# Year-specific
make 2024
make 2024-md   # Markdown only
make 2024-pdf  # PDFs only

# Database operations
make init-db
make backup
make stats
```

---

## Pipeline Architecture

```
inbox/ (raw exports) → source2txt → txt/     (formatted text)
                                     ↓
                                    txt2md
                                     ↓
                                    md/      (markdown + YAML)
                                     ↓            ↑
                                    yaml2sql  sql2yaml
                                     ↓            ↑
                                    database (SQLite + metadata)
                                     ↓
                                    md2pdf
                                     ↓
                                    pdf/     (annotated PDFs)
```

---

## Directory Structure

```
palimpsest/
├── dev/                        # Source code
│   ├── bin/                    # CLI wrappers (journal, metadb)
│   ├── builders/               # PDF and text builders
│   ├── core/                   # Logging, validation, paths
│   ├── database/               # SQLAlchemy ORM and managers
│   ├── dataclasses/            # Entry data structures
│   ├── pipeline/               # Processing scripts
│   └── utils/                  # Utilities (fs, md, parsers)
├── templates/                  # LaTeX preambles, wiki templates
├── data/                       # Personal content (git submodule)
│   ├── journal/
│   │   ├── inbox/
│   │   ├── sources/txt/
│   │   ├── content/md/
│   │   └── annotations/
│   ├── manuscript/
│   ├── wiki/
│   └── metadata/
│       └── palimpsest.db
├── environment.yaml
├── Makefile
└── README.md
```

---

## Command Reference

### Pipeline Commands

```bash
# Process inbox (raw exports → formatted text)
journal inbox [-i INBOX] [-o OUTPUT]

# Convert text to markdown
journal convert [-i INPUT] [-o OUTPUT] [-f]

# Sync database from markdown
journal sync [-i INPUT] [-f]

# Export database to markdown
journal export [-o OUTPUT] [-f]

# Build PDFs
journal pdf YEAR [-i INPUT] [-o OUTPUT] [-f]

# Complete pipeline
journal run-all [--year YEAR] [--skip-inbox] [--skip-pdf]

# Status
journal status
journal validate
```

### Database Commands

```bash
# Initialize
metadb init [--alembic-only] [--db-only]
metadb reset [--keep-backups]

# Migrations
metadb migration-create MESSAGE [--autogenerate]
metadb migration-upgrade [--revision REV]
metadb migration-status
metadb migration-history

# Backups
metadb backup [--type TYPE] [--suffix SUFFIX]
metadb backups
metadb restore BACKUP_PATH

# Monitoring
metadb stats [--verbose]
metadb health [--fix]
metadb validate

# Maintenance
metadb cleanup
metadb optimize

# Export
metadb export-csv OUTPUT_DIR
metadb export-json OUTPUT_FILE
metadb analyze
```

---

## Markdown Format

### Entry Structure

```yaml
---
date: 2024-01-15
word_count: 850
reading_time: 4.2

city: Montreal
locations: [Cafe X, Library]

people: [Maria-Jose, "@Friend (Full Name)"]
tags: [writing, reflection]
events: [thesis-defense]

epigraph: "Quote text here"
epigraph_attribution: Author Name

dates:
  - 2024-06-01 (thesis exam)

references:
  - content: "Referenced quote"
    speaker: Speaker Name
    source:
      title: Book Title
      type: book
      author: Author Name

manuscript:
  status: draft
  edited: false
  themes: [identity, memory]
---
## Monday, January 15, 2024

Entry content here...
```

See `example_yaml.md` for complete examples.

---

## Database Schema

Core tables:

- `entries` - Journal entries with metadata
- `people` - People mentioned (with aliases, relationships)
- `cities` - Geographic cities
- `locations` - Specific venues/places
- `events` - Thematic events spanning entries
- `tags` - Keyword tags
- `dates` - Referenced dates with context
- `references` - External citations
- `poems` - Poetry versions

Manuscript tables:

- `manuscript_entries` - Curation status
- `manuscript_people` - Character adaptations
- `manuscript_events` - Event transformations
- `themes` - Thematic categories
- `arcs` - Narrative arcs

---

## Development

### Running Tests

```bash
pytest tests/
```

### Adding Migrations

```bash
# Create migration
metadb migration-create "add_new_field"

# Edit generated file in alembic/versions/

# Apply migration
metadb migration-upgrade
```

### Code Style

Uses Ruff for linting. Code follows:

- Type hints throughout
- Click for CLI interfaces
- Emoji-style terminal output
- Comprehensive logging

---

## Dependencies

- Python 3.10+
- SQLAlchemy 2.0+
- Click 8.0+
- Pandoc 2.19+
- Tectonic or XeLaTeX
- Cormorant Garamond font (for PDFs)

See `environment.yaml` for complete list.

---

## Configuration

Edit `dev/core/paths.py` to customize:

- Data directory location
- Database path
- Output directories
- Template paths

---

## About the Name

A _palimpsest_ is a manuscript that has been scraped clean for reuse—yet traces of the original text remain visible beneath. This project embodies that concept: writing layered over writing, memory overwritten but never fully erased.

---

## License

MIT License - See LICENSE file for details.

---

## Acknowledgments

Built for managing journal archives from [750words.com](https://750words.com). Inspired by the practice of daily writing and the challenge of transforming private reflection into public art.
