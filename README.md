# Palimpsest

**A personal journal metadata management and PDF compilation system.**

[![Tests](https://github.com/soffiafdz/palimpsest/actions/workflows/test.yml/badge.svg)](https://github.com/soffiafdz/palimpsest/actions/workflows/test.yml)
[![Integration Tests](https://github.com/soffiafdz/palimpsest/actions/workflows/integration.yml/badge.svg)](https://github.com/soffiafdz/palimpsest/actions/workflows/integration.yml)
[![Security](https://github.com/soffiafdz/palimpsest/actions/workflows/security.yml/badge.svg)](https://github.com/soffiafdz/palimpsest/actions/workflows/security.yml)
[![codecov](https://codecov.io/gh/soffiafdz/palimpsest/branch/main/graph/badge.svg)](https://codecov.io/gh/soffiafdz/palimpsest)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

Palimpsest is a personal project consisting of a Python-based toolkit for processing, organizing, and analyzing journal entries with rich metadata. It converts raw text exports into structured Markdown files with YAML frontmatter, maintains a SQLite database of relationships and themes, and generates annotated PDFs for review and curation.

Originally built for managing my decade+ archive from [750words.com](https://750words.com), Palimpsest provides me the infrastructure for transforming my personal documentary writings into searchable, cross-referenced material suitable for memoir or creative non-fiction projects.

---

## Features

- **Multi-stage processing pipeline**: Raw exports → Formatted text → Markdown → Database → Wiki → PDFs
- **Rich metadata extraction**: Track people, locations, events, themes, dates, and references
- **Database-backed queries**: SQLAlchemy ORM with relationship mapping and analytics
- **Wiki system**: Primary editable workspace with database sync and YAML exports for git
- **Full-text search**: SQLite FTS5 with advanced filtering (people, dates, themes, word count, etc.)
- **Manuscript subwiki**: Dedicated wiki for curating journal entries into literary material
- **PDF generation**: Create clean reading copies and annotated review versions
- **Vim/Neovim integration**: Vimwiki templates and automation (optional)

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
plm inbox

# Convert to markdown
plm convert

# Import metadata to database
plm import-metadata

# Build PDFs for a year
plm build-pdf 2024

# Or run complete pipeline
plm run-all 2024
```

---

## Pipeline Architecture

```
inbox/ (raw exports) → src2txt → txt/     (formatted text)
                                   ↓
                                 txt2md
                                   ↓
                                 md/      (markdown prose + minimal frontmatter)
                                   +
                          metadata YAML/   (narrative analysis - human-authored)
                                   ↓
                            import-metadata (one-time import)
                                   ↓
                                database  (LOCAL ONLY - not in git)
                                   ↓
                              export-json
                                   ↓
                              JSON export  (git-tracked for version control)

                                  md/
                                   ↓
                                 md2pdf
                                   ↓
                                 pdf/     (annotated PDFs)
```

### Pipeline Scripts

Each pipeline step is implemented as a standalone script with both CLI and programmatic API:

- **`src2txt.py`**: Process raw 750words exports → formatted text files
  - Validates filenames, runs format script, archives originals
  - Archives to: `data/journal/sources/archive/`

- **`txt2md.py`**: Convert formatted text → Markdown with YAML frontmatter
  - Parses entries, computes metadata (word count, reading time)

- **`metadata_importer.py`**: Import metadata YAML → Database
  - Parses complex metadata, manages relationships
  - One-time import for narrative analysis

- **`export_json.py`**: Export Database → JSON
  - Exports entities for version control

- **`md2pdf.py`**: Build Markdown → PDFs (clean & notes versions)
  - Uses Pandoc + LaTeX for professional typography

### Data Flow Paths

1. **Initial Import**: `inbox → txt → md + metadata YAML → database` (one-time)
2. **Version Control**: `database → JSON export` (git-tracked)
3. **Search & Analysis**: Query database with FTS5
4. **Export**: `md → pdf` (annotated reading copies)

**Note**: Database is LOCAL ONLY (not version controlled). JSON exports provide git tracking.

---

## Directory Structure

```
palimpsest/
├── dev/                        # Source code
│   ├── builders/               # PDF and text builders
│   ├── core/                   # Logging, validation, paths
│   ├── database/               # SQLAlchemy ORM and managers
│   │   ├── models.py          # Main database models
│   │   ├── models_manuscript.py # Manuscript models
│   │   ├── search.py          # Search query engine
│   │   └── search_index.py    # FTS5 index manager
│   ├── dataclasses/            # Entry data structures
│   │   ├── txt_entry.py       # TXT file conversion
│   │   └── metadata_entry.py  # Metadata YAML structures
│   ├── pipeline/               # Processing scripts
│   │   ├── src2txt.py         # Raw → TXT
│   │   ├── txt2md.py          # TXT → Markdown
│   │   ├── metadata_importer.py # Metadata → Database
│   │   ├── export_json.py     # Database → JSON
│   │   ├── search.py          # Search CLI
│   └── utils/                  # Utilities (fs, md, parsers)
├── templates/                  # LaTeX preambles, wiki templates
├── tests/                      # Integration tests
│   └── integration/
│       └── test_search.py     # Search tests
├── data/                       # Personal content (git submodule)
│   ├── journal/
│   │   ├── inbox/
│   │   ├── sources/txt/
│   │   ├── content/md/
│   │   └── annotations/
│   └── metadata/
│       └── palimpsest.db
├── docs/                       # Documentation
│   ├── README.md              # Documentation index
│   ├── getting-started.md     # New user onboarding
│   ├── reference/             # Command and field references
│   ├── guides/                # User guides and workflows
│   ├── integrations/          # Editor integrations
│   └── development/           # Developer documentation
├── environment.yaml
└── README.md
```

---

## Command Reference

### Pipeline Commands

```bash
# Process inbox (raw exports → formatted text)
plm inbox

# Convert text to markdown
plm convert

# Import metadata to database
plm import-metadata

# Export database to JSON
plm export-json

# Build PDFs
plm build-pdf YEAR

# Complete pipeline
plm run-all --year YEAR

# Status and validation
plm status
plm validate pipeline
plm validate entry
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

### Search Commands

```bash
# Text search with filters
jsearch "query text" [filters]
jsearch "therapy" person:alice in:2024 words:100-500
jsearch "reflection" city:montreal has:manuscript

# Index management
jsearch index --create
jsearch index --rebuild
jsearch index --status

# Available filters:
# person:NAME, tag:TAG, event:EVENT, city:CITY, theme:THEME
# in:YEAR, year:YEAR, month:MONTH
# from:DATE, to:DATE
# words:MIN-MAX, time:MIN-MAX
# has:manuscript, status:STATUS
# sort:relevance|date|word_count, limit:N
```

---

## Search & Analysis Features

### Full-Text Search (FTS5)

**Built-in**, free, fast full-text search with advanced filters:

```bash
# Search entry text
jsearch "anxiety therapy"

# Combine text + metadata
jsearch "alice" person:alice in:2024

# Complex filtering
jsearch "reflection" city:montreal words:500-1000 has:manuscript
```

**How it works:**

- SQLite FTS5 virtual table with Porter stemming
- BM25 ranking for relevance scoring
- Searches actual entry content, not just metadata
- Auto-sync triggers keep index up-to-date

**Create search index:**

```bash
jsearch index --create
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

people: [Alda, "@Friend (Full Name)"]
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

See [Metadata Examples](docs/reference/metadata-examples.md) for complete examples.

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

### Continuous Integration

The project uses GitHub Actions for automated testing and quality checks:

**Test Workflow** (runs on every push/PR):

- Linting with Ruff
- Unit tests on Python 3.10, 3.11, 3.12
- Coverage reporting (80% minimum)

**Integration Workflow** (runs on main branch):

- Full integration tests with system dependencies
- Daily scheduled runs

**Security Workflow** (runs weekly):

- Dependency vulnerability scanning with pip-audit
- CodeQL security analysis

All workflows are defined in `.github/workflows/`. Status badges are displayed at the top of this README.

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

### Core Dependencies

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

## Documentation

Comprehensive documentation is available in the `docs/` directory:

### Getting Started
- **[Getting Started Guide](docs/getting-started.md)** - New user onboarding with core concepts and first workflow

### Reference
- **[Command Reference](docs/reference/commands.md)** - Complete CLI command documentation
- **[Metadata Field Reference](docs/reference/metadata-field-reference.md)** - All YAML frontmatter fields with examples
- **[Metadata Examples](docs/reference/metadata-examples.md)** - Template entries and patterns

### Guides
- **[Migration Guide](docs/guides/migration.md)** - Upgrading between versions

### Integrations
- **[Neovim Integration](docs/integrations/neovim.md)** - Editor integration features

### Development
- **[Development Overview](docs/development/README.md)** - Contributing and architecture
- **[Architecture](docs/development/architecture.md)** - System design and modular organization
- **[Database Managers](docs/development/database-managers.md)** - Entity manager patterns
- **[Validators](docs/development/validators.md)** - Validation system architecture
- **[Tombstones](docs/development/tombstones.md)** - Deletion tracking implementation
- **[Type Checking](docs/development/type-checking.md)** - Pyright configuration and patterns
- **[Testing](docs/development/testing.md)** - Comprehensive testing guide
- **[Neovim Plugin Development](docs/development/neovim-plugin-dev.md)** - Extending the Neovim integration

---

## About the Name

A _palimpsest_ is a manuscript that has been scraped clean for reuse—yet traces of the original text remain visible beneath. This project embodies that concept: writing layered over writing, memory overwritten but never fully erased.

---

## License

MIT License - See LICENSE file for details.

---

## Acknowledgments

Built for managing journal archives from [750words.com](https://750words.com). Inspired by the practice of daily writing and the challenge of transforming private reflection into public art.
