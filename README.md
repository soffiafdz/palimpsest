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
- **Wiki system**: Bidirectional sync between database and Markdown wiki for editing and curation
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

# Sync database
plm sync-db

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
                                 md/      (markdown + YAML)
                                   ↓            ↑
                                yaml2sql   sql2yaml
                                   ↓            ↑
                                database (SQLite + metadata + FTS5)
                                   ↓            ↑
                                sql2wiki   wiki2sql
                                   ↓            ↑
                                 wiki/    (editable wiki pages)
                                   ├── entries/
                                   ├── people/
                                   ├── events/
                                   └── manuscript/

                                 md2pdf
                                   ↓
                                 pdf/     (annotated PDFs)
```

### Pipeline Scripts (X2Y Pattern)

Each pipeline step is implemented as a standalone script with both CLI and programmatic API:

- **`src2txt.py`**: Process raw 750words exports → formatted text files
  - Validates filenames, runs format script, archives originals
  - Archives to: `data/journal/sources/archive/`

- **`txt2md.py`**: Convert formatted text → Markdown with YAML frontmatter
  - Parses entries, computes metadata (word count, reading time)

- **`yaml2sql.py`**: Sync Markdown YAML → Database
  - Parses complex metadata, manages relationships

- **`sql2yaml.py`**: Export Database → Markdown YAML
  - Regenerates frontmatter while preserving body content

- **`md2pdf.py`**: Build Markdown → PDFs (clean & notes versions)
  - Uses Pandoc + LaTeX for professional typography

- **Wiki scripts**: Bidirectional sync between database and wiki
  - `sql2wiki.py`: Database → Wiki pages
  - `wiki2sql.py`: Wiki edits → Database

### Data Flow Paths

1. **Journal → Database**: `inbox → txt → md → database` (via YAML frontmatter)
2. **Database → Wiki**: `database → wiki` (for editing and curation)
3. **Wiki → Database**: `wiki → database` (import edits back)
4. **Search & Analysis**: Query database with FTS5
5. **Export**: `database → pdf` (annotated reading copies)

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
│   │   ├── md_entry.py        # YAML frontmatter
│   │   ├── wiki_*.py          # Wiki page classes
│   │   └── manuscript_*.py    # Manuscript wiki classes
│   ├── pipeline/               # Processing scripts
│   │   ├── yaml2sql.py        # YAML → Database
│   │   ├── sql2yaml.py        # Database → YAML
│   │   ├── sql2wiki.py        # Database → Wiki
│   │   ├── wiki2sql.py        # Wiki → Database
│   │   ├── search.py          # Search CLI
│   └── utils/                  # Utilities (fs, md, parsers)
├── templates/                  # LaTeX preambles, wiki templates
├── tests/                      # Integration tests
│   └── integration/
│       ├── test_search.py     # Search tests
│       ├── test_sql_to_wiki.py # Wiki export tests
│       └── test_wiki_to_sql.py # Wiki import tests
├── data/                       # Personal content (git submodule)
│   ├── journal/
│   │   ├── inbox/
│   │   ├── sources/txt/
│   │   ├── content/md/
│   │   └── annotations/
│   ├── manuscript/
│   ├── wiki/                   # Generated wiki
│   │   ├── entries/
│   │   ├── people/
│   │   ├── events/
│   │   ├── cities/
│   │   └── manuscript/
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
plm inbox [-i INBOX] [-o OUTPUT]

# Convert text to markdown
plm convert [-i INPUT] [-o OUTPUT] [-f]

# Sync database from markdown
plm sync-db [-i INPUT] [-f]

# Export database to markdown
plm export-db [-o OUTPUT] [-f]

# Build PDFs
plm build-pdf YEAR [-i INPUT] [-o OUTPUT] [-f]

# Complete pipeline
plm run-all [--year YEAR] [--skip-inbox] [--skip-pdf]

# Status
plm status
plm validate
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

## Wiki System

The wiki provides an editable interface for curating and annotating your journal:

### Export Database to Wiki

```bash
# Export everything
plm export-wiki all

# Export specific entity types
plm export-wiki people
plm export-wiki entries
plm export-wiki manuscript

# Force overwrite existing files
plm export-wiki all --force
```

### Import Wiki Edits to Database

```bash
# Import all wiki edits
plm import-wiki all

# Import specific entity type
plm import-wiki people
plm import-wiki entries
plm import-wiki manuscript
```

### Wiki Structure

```
wiki/
├── index.md                    # Main index
├── people/
│   ├── index.md               # People index
│   └── alice.md               # Person page (editable notes)
├── entries/
│   ├── index.md               # Entries index
│   └── 2024-11-01.md          # Entry page (editable notes)
├── events/
│   └── therapy-session.md     # Event page
├── cities/
│   └── montreal.md            # City page
└── manuscript/
    ├── index.md               # Manuscript index
    ├── entries/
    │   └── 2024-11-01.md      # Manuscript entry (adaptation notes)
    └── characters/
        └── alexandra.md        # Character page (voice, arc, description)
```

### Editable Fields

**Main Wiki** (only `notes` fields are editable):

- Person pages: Add biographical notes, relationship context
- Entry pages: Add editorial notes, manuscript potential
- Event/City pages: Add context notes

**Manuscript Wiki** (detailed curation fields):

- Manuscript entries: Entry type, narrative arc, character notes, adaptation notes
- Characters: Character description, arc, voice notes, appearance notes
- Themes, arcs, and other manuscript-specific metadata

See [Synchronization Guide](docs/guides/synchronization.md) for complete documentation.

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
- **[Command Reference](docs/reference/commands.md)** - Complete CLI command documentation (70+ commands)
- **[Metadata Field Reference](docs/reference/metadata-field-reference.md)** - All YAML frontmatter fields with examples
- **[Metadata Examples](docs/reference/metadata-examples.md)** - Template entries and patterns
- **[Wiki Field Reference](docs/reference/wiki-fields.md)** - Wiki page structure and editable fields

### Guides
- **[Synchronization Guide](docs/guides/synchronization.md)** - Multi-machine workflows and bidirectional sync
- **[Conflict Resolution](docs/guides/conflict-resolution.md)** - Handling concurrent edits across machines
- **[Manuscript Features](docs/guides/manuscript-features.md)** - Manuscript wiki and curation features
- **[Migration Guide](docs/guides/migration.md)** - Upgrading between versions

### Integrations
- **[Neovim Integration](docs/integrations/neovim.md)** - Editor integration and vimwiki features

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
