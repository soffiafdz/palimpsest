# Palimpsest

**A personal journal metadata management and PDF compilation system.**

Palimpsest is a personal project consisting of a Python-based toolkit for processing, organizing, and analyzing journal entries with rich metadata. It converts raw text exports into structured Markdown files with YAML frontmatter, maintains a SQLite database of relationships and themes, and generates annotated PDFs for review and curation.

Originally built for managing my decade+ archive from [750words.com](https://750words.com), Palimpsest provides me the infrastructure for transforming my personal documentary writings into searchable, cross-referenced material suitable for memoir or creative non-fiction projects.

---

## Features

- **Multi-stage processing pipeline**: Raw exports → Formatted text → Markdown → Database → Wiki → PDFs
- **Rich metadata extraction**: Track people, locations, events, themes, dates, and references
- **Database-backed queries**: SQLAlchemy ORM with relationship mapping and analytics
- **Wiki system**: Bidirectional sync between database and Markdown wiki for editing and curation
- **Full-text search**: SQLite FTS5 with advanced filtering (people, dates, themes, word count, etc.)
- **AI-assisted analysis** (optional): Entity extraction, theme detection, semantic search with 4 intelligence levels
- **Manuscript subwiki**: Dedicated wiki for curating journal entries into literary material
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
                                    database (SQLite + metadata + FTS5)
                                     ↓            ↑
                                    sql2wiki  wiki2sql
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

### Data Flow Paths

1. **Journal → Database**: `inbox → txt → md → database` (via YAML frontmatter)
2. **Database → Wiki**: `database → wiki` (for editing and curation)
3. **Wiki → Database**: `wiki → database` (import edits back)
4. **Search & AI**: Query database with FTS5, extract metadata with AI
5. **Export**: `database → pdf` (annotated reading copies)

---

## Directory Structure

```
palimpsest/
├── dev/                        # Source code
│   ├── ai/                     # AI analysis (optional)
│   │   ├── extractors.py      # spaCy NER, theme extraction
│   │   ├── semantic_search.py # Sentence transformers
│   │   ├── claude_assistant.py # Claude API integration
│   │   └── openai_assistant.py # OpenAI API integration
│   ├── bin/                    # CLI wrappers (journal, metadb)
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
│   │   └── ai_assist.py       # AI analysis CLI
│   └── utils/                  # Utilities (fs, md, parsers)
├── templates/                  # LaTeX preambles, wiki templates
├── tests/                      # Integration tests
│   └── integration/
│       ├── test_search.py     # Search tests
│       ├── test_ai_extraction.py # AI tests
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
├── docs/
│   └── BIDIRECTIONAL_SYNC_GUIDE.md # Wiki sync documentation
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

### Search Commands

```bash
# Text search with filters
palimpsest search "query text" [filters]
palimpsest search "therapy" person:alice in:2024 words:100-500
palimpsest search "reflection" city:montreal has:manuscript

# Index management
palimpsest search index --create
palimpsest search index --rebuild
palimpsest search index --status

# Available filters:
# person:NAME, tag:TAG, event:EVENT, city:CITY, theme:THEME
# in:YEAR, year:YEAR, month:MONTH
# from:DATE, to:DATE
# words:MIN-MAX, time:MIN-MAX
# has:manuscript, status:STATUS
# sort:relevance|date|word_count, limit:N
```

### AI Analysis Commands

```bash
# Check AI capabilities
palimpsest ai status

# Analyze single entry (Level 2: spaCy NER)
palimpsest ai analyze 2024-11-01 --level 2

# Analyze with Claude API (Level 4)
palimpsest ai analyze 2024-11-01 --level 4 --manuscript

# Batch analyze entries
palimpsest ai batch --level 2 --limit 10

# Find semantically similar entries (Level 3)
palimpsest ai similar 2024-11-01 --limit 10

# Cluster entries by theme
palimpsest ai cluster --num-clusters 10
```

**AI Intelligence Levels:**
- **Level 2**: spaCy NER (free) - Entity extraction, theme detection
- **Level 3**: Sentence Transformers (free) - Semantic similarity search
- **Level 4**: LLM APIs (paid) - Advanced analysis, manuscript curation (Claude or OpenAI)

See [Search & AI Documentation](#search--ai-features) for details.

---

## Wiki System

The wiki provides an editable interface for curating and annotating your journal:

### Export Database to Wiki

```bash
# Export everything
journal wiki-export

# Export specific year
journal wiki-export --year 2024

# Force overwrite
journal wiki-export --force
```

### Import Wiki Edits to Database

```bash
# Import all wiki edits
journal wiki-import

# Import specific entity type
journal wiki-import --type people
journal wiki-import --type entries
journal wiki-import --type manuscript
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

See [BIDIRECTIONAL_SYNC_GUIDE.md](BIDIRECTIONAL_SYNC_GUIDE.md) for complete documentation.

---

## Search & AI Features

### Full-Text Search (FTS5)

**Built-in**, free, fast full-text search with advanced filters:

```bash
# Search entry text
palimpsest search "anxiety therapy"

# Combine text + metadata
palimpsest search "alice" person:alice in:2024

# Complex filtering
palimpsest search "reflection" city:montreal words:500-1000 has:manuscript
```

**How it works:**
- SQLite FTS5 virtual table with Porter stemming
- BM25 ranking for relevance scoring
- Searches actual entry content, not just metadata
- Auto-sync triggers keep index up-to-date

**Create search index:**
```bash
palimpsest search index --create
```

### AI-Assisted Analysis (Optional)

Progressive intelligence levels - use what you need:

#### Level 2: spaCy NER (Free) ⭐⭐⭐⭐☆

**Entity extraction using ML:**
- Detects people, locations, cities, organizations, events
- Theme identification
- Confidence scoring

**Install:**
```bash
pip install spacy
python -m spacy download en_core_web_sm
```

**Usage:**
```bash
palimpsest ai analyze 2024-11-01 --level 2
```

#### Level 3: Sentence Transformers (Free) ⭐⭐⭐⭐☆

**Semantic similarity search:**
- Find similar entries by meaning (not just keywords)
- Theme clustering
- Understanding context

**Install:**
```bash
pip install sentence-transformers
pip install faiss-cpu  # optional, for faster search
```

**Usage:**
```bash
# Find similar entries
palimpsest ai similar 2024-11-01 --limit 10

# Cluster by theme
palimpsest ai cluster --num-clusters 10
```

#### Level 4: LLM APIs (Paid) ⭐⭐⭐⭐⭐

**Most accurate analysis:**
- Advanced entity extraction
- Manuscript narrative analysis
- Character voice and arc suggestions
- Theme identification with context

**Two providers supported:**

**Claude (Anthropic):**
- Cost: ~$0.007/entry (Haiku), ~$0.075/entry (Sonnet)
- Install: `pip install anthropic`
- API Key: `export ANTHROPIC_API_KEY='your-key'`

**OpenAI (GPT-4):**
- Cost: ~$0.003/entry (GPT-4o mini), ~$0.025/entry (GPT-4o)
- Install: `pip install openai`
- API Key: `export OPENAI_API_KEY='your-key'`

**Usage:**
```bash
# Analyze with Claude (default)
palimpsest ai analyze 2024-11-01 --level 4 --manuscript

# Analyze with OpenAI
palimpsest ai analyze 2024-11-01 --level 4 --provider openai --manuscript

# Batch analyze with OpenAI
palimpsest ai batch --level 4 --provider openai --limit 10
```

**Check what's installed:**
```bash
palimpsest ai status
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

### Core Dependencies

- Python 3.10+
- SQLAlchemy 2.0+
- Click 8.0+
- Pandoc 2.19+
- Tectonic or XeLaTeX
- Cormorant Garamond font (for PDFs)

See `environment.yaml` for complete list.

### Optional AI Dependencies

**Level 2 (spaCy NER):**
```bash
pip install spacy
python -m spacy download en_core_web_sm
```

**Level 3 (Semantic Search):**
```bash
pip install sentence-transformers
pip install faiss-cpu  # optional, faster search
```

**Level 4 (LLM APIs):**
```bash
# Claude (Anthropic)
pip install anthropic
export ANTHROPIC_API_KEY='your-key'

# OpenAI (GPT-4)
pip install openai
export OPENAI_API_KEY='your-key'
```

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
