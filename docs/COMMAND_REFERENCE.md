# Palimpsest Command Reference

Complete reference for all available commands in the Palimpsest system.

## Available Commands

Palimpsest provides four main command-line tools:

1. **`journal`** - Wrapper script for common pipeline operations (user-friendly)
2. **`plm`** - Pipeline commands (direct access)
3. **`metadb`** - Database management commands
4. **`plm-search`** - Full-text search commands
5. **`plm-ai`** - AI-assisted analysis commands

---

## 1. Journal Wrapper (`journal`)

User-friendly wrapper around `plm` commands with simplified syntax.

### Commands

```bash
# Pipeline Operations
journal inbox           # Process inbox (raw exports → formatted text)
journal convert         # Convert text to markdown
journal sync            # Sync database from markdown
journal export          # Export database to markdown
journal pdf YEAR        # Build PDFs for specific year

# Backup Operations
journal backup-full     # Create full compressed backup
journal backup-list     # List all full backups

# Control Commands
journal run-all [YEAR]  # Run complete pipeline
journal status          # Show pipeline status
journal validate        # Validate pipeline integrity
journal help            # Show help message
```

### Examples

```bash
# Process new entries
journal inbox
journal convert
journal sync

# Build PDFs for 2024
journal pdf 2024

# Run everything for 2024
journal run-all 2024

# Create backup
journal backup-full
```

---

## 2. Pipeline Commands (`plm`)

Direct access to pipeline operations with full options.

### Commands

```bash
plm inbox [OPTIONS]
  -i, --inbox PATH    Inbox directory (default: journal/inbox)
  -o, --output PATH   Output directory (default: journal/sources/txt)
  -v, --verbose       Verbose logging

plm convert [OPTIONS]
  -i, --input PATH    Input directory or file (default: journal/sources/txt)
  -o, --output PATH   Output directory (default: journal/content/md)
  -f, --force         Force overwrite existing files
  --dry-run           Preview without modifying files
  -v, --verbose       Verbose logging

plm sync-db [OPTIONS]
  -i, --input PATH    Input directory (default: journal/content/md)
  -f, --force         Force update all entries
  --dry-run           Preview without modifying database
  -v, --verbose       Verbose logging

plm export-db [OPTIONS]
  -o, --output PATH   Output directory (default: journal/content/md)
  -f, --force         Force overwrite existing files
  --dry-run           Preview without writing files
  -v, --verbose       Verbose logging

plm build-pdf YEAR [OPTIONS]
  -i, --input PATH    Input directory (default: journal/content/md)
  -o, --output PATH   Output directory (default: journal/output/pdf)
  -f, --force         Force overwrite existing PDFs
  --debug             Keep temp files on error
  -v, --verbose       Verbose logging

plm backup-full [OPTIONS]
  --suffix SUFFIX     Optional backup suffix
  -v, --verbose       Verbose logging

plm backup-list-full
  List all available full data backups

plm run-all [OPTIONS]
  --year YEAR         Specific year to process
  --skip-inbox        Skip inbox processing
  --skip-pdf          Skip PDF generation
  --backup            Create backup after completion
  -v, --verbose       Verbose logging

plm status
  Show pipeline status and statistics

plm validate
  Validate pipeline integrity
```

### Examples

```bash
# Convert specific file
plm convert -i journal/sources/txt/2024/2024-11.txt -o journal/content/md

# Sync database with dry run
plm sync-db --dry-run

# Build PDFs with debug
plm build-pdf 2024 --debug

# Run full pipeline for 2024 with backup
plm run-all --year 2024 --backup
```

---

## 3. Database Commands (`metadb`)

Comprehensive database management and monitoring.

### Initialization

```bash
metadb init [OPTIONS]
  --alembic-only      Initialize Alembic only
  --db-only           Initialize database only
  --verbose           Show detailed errors

metadb reset [OPTIONS]
  --keep-backups      Keep existing backups
  --verbose           Show detailed errors
  # Confirmation required!
```

### Migrations

```bash
metadb migration-create MESSAGE [OPTIONS]
  --autogenerate      Auto-generate from models

metadb migration-upgrade [OPTIONS]
  --revision REV      Target revision (default: head)

metadb migration-downgrade REVISION

metadb migration-status
  Show current migration status

metadb migration-history
  Show migration history
```

### Backups

```bash
metadb backup [OPTIONS]
  --type TYPE         Backup type: manual, daily, weekly (default: manual)
  --suffix SUFFIX     Optional suffix

metadb backups
  List all available backups

metadb restore BACKUP_PATH
  Restore from backup file
  # Confirmation required!
```

### Monitoring

```bash
metadb stats [OPTIONS]
  --verbose           Show detailed statistics

metadb health [OPTIONS]
  --fix               Attempt to fix issues

metadb validate
  Validate database integrity

metadb show ENTRY_DATE [OPTIONS]
  --full              Show all details including references/poems

metadb years
  List all years with entry counts

metadb months YEAR
  List months in year with entry counts

metadb batches [OPTIONS]
  --threshold N       Batch threshold (default: 500)
```

### Maintenance

```bash
metadb cleanup
  Clean up orphaned records
  # Confirmation required!

metadb optimize
  Optimize database (VACUUM + ANALYZE)
  # Confirmation required!
```

### Export

```bash
metadb export-csv OUTPUT_DIR
  Export all tables to CSV files

metadb export-json OUTPUT_FILE
  Export complete database to JSON

metadb analyze
  Generate detailed analytics report
```

### Examples

```bash
# Initialize database
metadb init

# Create manual backup
metadb backup --type manual --suffix before-migration

# Check database health
metadb health

# View entry details
metadb show 2024-11-01 --full

# Export analytics
metadb analyze > analytics-report.json
```

---

## 4. Search Commands (`plm-search`)

Full-text search with advanced filtering.

### Commands

```bash
plm-search "QUERY" [FILTERS] [OPTIONS]

Filters:
  person:NAME         Filter by person mentioned
  tag:TAG             Filter by tag
  event:EVENT         Filter by event
  city:CITY           Filter by city
  theme:THEME         Filter by theme
  in:YEAR             Filter by year
  year:YEAR           Same as in:YEAR
  month:MONTH         Filter by month (1-12)
  from:DATE           Filter from date (YYYY-MM-DD)
  to:DATE             Filter to date (YYYY-MM-DD)
  words:MIN-MAX       Filter by word count range
  time:MIN-MAX        Filter by reading time range
  has:manuscript      Only entries with manuscript status
  status:STATUS       Filter by manuscript status
  sort:FIELD          Sort by: relevance, date, word_count
  limit:N             Limit results (default: 10)
  offset:N            Skip first N results

Options:
  -v, --verbose       Show detailed output

# Index Management
plm-search index --create
  Create FTS5 search index

plm-search index --rebuild
  Rebuild search index

plm-search index --status
  Check index status
```

### Examples

```bash
# Simple text search
plm-search "anxiety therapy"

# Search with person filter
plm-search "alice" person:alice in:2024

# Complex filtering
plm-search "reflection" city:montreal words:500-1000 has:manuscript

# Date range search
plm-search "therapy" from:2024-01-01 to:2024-06-30

# Sorted and paginated
plm-search "writing" sort:word_count limit:20 offset:10

# Create search index
plm-search index --create
```

---

## 5. AI Analysis Commands (`plm-ai`)

AI-assisted metadata extraction and analysis (optional).

### Commands

```bash
plm-ai status
  Check AI dependencies and capabilities

plm-ai analyze ENTRY_DATE [OPTIONS]
  --level LEVEL       Intelligence level (2, 3, or 4)
  --provider PROVIDER Provider for level 4: claude, openai
  --manuscript        Include manuscript analysis
  -v, --verbose       Show detailed output

plm-ai batch [OPTIONS]
  --level LEVEL       Intelligence level (2, 3, or 4)
  --provider PROVIDER Provider for level 4: claude, openai
  --limit N           Limit entries to process
  --start-date DATE   Start from date
  --end-date DATE     End at date
  -v, --verbose       Show detailed output

plm-ai similar ENTRY_DATE [OPTIONS]
  --limit N           Number of similar entries (default: 10)
  --min-score SCORE   Minimum similarity score (0.0-1.0)
  -v, --verbose       Show detailed output

plm-ai cluster [OPTIONS]
  --num-clusters N    Number of clusters (default: 10)
  --method METHOD     Clustering method: kmeans, hierarchical
  -v, --verbose       Show detailed output
```

### Intelligence Levels

**Level 2: spaCy NER (Free)**
- Entity extraction (people, locations, organizations)
- Theme detection
- Requires: `pip install spacy` + `python -m spacy download en_core_web_sm`

**Level 3: Sentence Transformers (Free)**
- Semantic similarity search
- Theme clustering
- Requires: `pip install sentence-transformers faiss-cpu`

**Level 4: LLM APIs (Paid)**
- Advanced analysis with Claude or OpenAI
- Manuscript narrative analysis
- Character voice and arc suggestions
- Requires API key (Claude or OpenAI)

### Examples

```bash
# Check what's installed
plm-ai status

# Analyze with spaCy
plm-ai analyze 2024-11-01 --level 2

# Analyze with Claude
plm-ai analyze 2024-11-01 --level 4 --manuscript

# Analyze with OpenAI
plm-ai analyze 2024-11-01 --level 4 --provider openai

# Batch analyze
plm-ai batch --level 2 --limit 100

# Find similar entries
plm-ai similar 2024-11-01 --limit 10

# Cluster by theme
plm-ai cluster --num-clusters 15
```

---

## 6. Wiki Commands (Python Modules)

Export and import wiki pages (not yet available as CLI commands).

### Export

```bash
python -m dev.pipeline.sql2wiki export all [--force]
python -m dev.pipeline.sql2wiki export people [--force]
python -m dev.pipeline.sql2wiki export entries [--force]
python -m dev.pipeline.sql2wiki export events [--force]
python -m dev.pipeline.sql2wiki export cities [--force]
python -m dev.pipeline.sql2wiki export tags [--force]
python -m dev.pipeline.sql2wiki export themes [--force]
python -m dev.pipeline.sql2wiki export manuscript [--force]
```

### Import

```bash
python -m dev.pipeline.wiki2sql import all
python -m dev.pipeline.wiki2sql import people
python -m dev.pipeline.wiki2sql import entries
python -m dev.pipeline.wiki2sql import manuscript
```

---

## Make Commands

Simplified Makefile targets for batch processing.

```bash
make all              # Run complete pipeline
make inbox            # Process inbox
make md               # Convert all text to markdown
make db               # Sync database
make pdf              # Build all PDFs

# Year-specific
make 2024             # Build everything for 2024
make 2024-md          # Build only markdown for 2024
make 2024-pdf         # Build only PDFs for 2024

# Database operations
make init-db          # Initialize database
make backup           # Create database backup
make backup-full      # Create full data backup
make backup-list      # List database backups
make backup-list-full # List full data backups
make stats            # Show database statistics
make health           # Run health check
make analyze          # Generate analytics

# Installation
make install          # Install CLI commands to ~/.local/bin
make uninstall        # Remove CLI commands

# Cleaning
make clean            # Remove markdown and PDFs
make clean-md         # Remove markdown files
make clean-pdf        # Remove PDF files

# Verbosity
make V=1 <target>     # Verbose output
make V=2 <target>     # Very verbose (show commands)
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Process new entries | `journal inbox && journal convert && journal sync` |
| Build PDFs | `journal pdf 2024` |
| Search entries | `plm-search "query" person:alice in:2024` |
| AI analysis | `plm-ai analyze 2024-11-01 --level 2` |
| Database backup | `metadb backup` |
| Full pipeline | `journal run-all 2024` or `make 2024` |
| Check status | `journal status` or `metadb health` |
| Export wiki | `python -m dev.pipeline.sql2wiki export all` |

---

## Global Options

Most commands support these global options:

- `-v, --verbose` - Enable verbose logging
- `--help` - Show command-specific help
- `--log-dir PATH` - Custom log directory (plm and metadb)

---

## Environment Variables

```bash
# For AI Level 4 (optional)
export ANTHROPIC_API_KEY='your-claude-api-key'  # For Claude
export OPENAI_API_KEY='your-openai-api-key'     # For OpenAI
```

---

## See Also

- [README.md](../README.md) - Project overview and setup
- [BIDIRECTIONAL_SYNC_GUIDE.md](bidirectional-sync-guide.md) - Wiki sync documentation
- [METADATA_GUIDE_YAML_SQL.md](metadata-guide-yaml-sql.md) - YAML metadata format
- [example-yaml.md](example-yaml.md) - Example entry format
