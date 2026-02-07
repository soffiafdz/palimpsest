# Palimpsest Command Reference

Complete reference for all Palimpsest CLI commands.

---

## Installation

```bash
# Install from repository
pip install -e .
```

This installs four CLI entry points:
- `plm` - Pipeline management
- `metadb` - Database management
- `validate` - Validation suite
- `jsearch` - Full-text search

---

## Quick Reference

### Daily Workflow

```bash
# Process new journal entries
plm inbox && plm convert && plm import-metadata

# Search your journal
jsearch query "therapy" person:alice in:2024
```

### Database Operations

```bash
# Create backup (do this regularly!)
metadb backup

# Check database health
metadb health

# View statistics
metadb stats --verbose
```

### Validation

```bash
# Validate database
validate db all

# Validate consistency
validate consistency all
```

---

## PLM - Pipeline Commands

Pipeline processing for journal entries.

### Data Pipeline

#### `plm inbox`

Process inbox text files.

```bash
plm inbox [--inbox-dir PATH] [--batch-dir PATH]
```

**What it does:**
- Scans inbox directory for `.txt` files
- Groups entries by date
- Creates batch directories
- Prepares entries for conversion

**Options:**
- `--inbox-dir PATH` - Custom inbox directory
- `--batch-dir PATH` - Custom batch output directory

#### `plm convert`

Convert formatted text to Markdown entries.

```bash
plm convert [--batch-dir PATH] [--md-dir PATH]
```

**What it does:**
- Processes batch directories
- Converts text to markdown format
- Extracts basic metadata (word count, reading time)
- Outputs to `data/journal/content/md/YYYY/YYYY-MM-DD.md`

**Options:**
- `--batch-dir PATH` - Custom batch directory
- `--md-dir PATH` - Custom markdown output directory

#### `plm import-metadata`

Import metadata YAML files into database.

```bash
plm import-metadata [--metadata-dir PATH] [--skip-validation]
```

**What it does:**
- Parses metadata YAML files
- Updates database with entry metadata
- Extracts people, locations, events, themes, etc.
- Handles tombstone tracking for deletions

**Options:**
- `--metadata-dir PATH` - Custom metadata directory
- `--skip-validation` - Skip YAML validation (faster, use with caution)

**Note:** This is a one-time import command for human-authored narrative analysis.

#### `plm export-json`

Export database entities to JSON files.

```bash
plm export-json [--output-dir PATH]
```

**What it does:**
- Exports all database entities to JSON format
- Creates structured export for version control
- Outputs to `data/exports/`

**Use cases:**
- Version control of database state
- Backup in human-readable format
- Data migration

#### `plm prune-orphans`

Remove orphaned entities from database.

```bash
plm prune-orphans [--dry-run]
```

**What it does:**
- Finds entities with no associations
- Removes orphaned records
- Cleans up unused data

**Options:**
- `--dry-run` - Show what would be deleted without deleting

### Build Commands

#### `plm build-pdf`

Build PDFs for a year's entries.

```bash
plm build-pdf YEAR [--output-dir PATH]
```

**Arguments:**
- `YEAR` - Year to build (required)

**What it does:**
- Generates clean and annotated PDF versions
- Uses Pandoc + LaTeX for typography
- Outputs to `data/journal/content/pdf/`

**Requirements:**
- Pandoc 2.19+
- XeLaTeX or Tectonic
- Cormorant Garamond font

### Batch Operations

#### `plm run-all`

Run the complete pipeline end-to-end.

```bash
plm run-all --year YEAR [--skip-inbox] [--skip-pdf]
```

**Options:**
- `--year YEAR` - Year to process (required)
- `--skip-inbox` - Skip inbox processing
- `--skip-pdf` - Skip PDF generation

**What it runs:**
1. `plm inbox` (unless `--skip-inbox`)
2. `plm convert`
3. `plm import-metadata`
4. `plm export-json`
5. `plm build-pdf` (unless `--skip-pdf`)

### Backup Operations

#### `plm backup-full`

Create complete system backup.

```bash
plm backup-full [--output-dir PATH]
```

**What it backs up:**
- SQLite database
- All markdown files
- Configuration files

**Output:**
- Timestamped compressed archive in `data/backups/`

#### `plm backup-list-full`

List all available full backups.

```bash
plm backup-list-full
```

**Output:**
- Backup filename
- Timestamp
- File size

### Status & Validation

#### `plm status`

Show pipeline status and statistics.

```bash
plm status
```

**Displays:**
- Total entries by year
- Batch processing status
- Last export timestamp

#### `plm validate`

Run validation checks.

```bash
plm validate COMMAND
```

**Commands:**
- `pipeline` - Validate pipeline directory structure
- `entry` - Validate journal entries (MD + YAML)

---

## METADB - Database Management

Database administration and maintenance.

### Setup & Initialization

#### `metadb init`

Initialize database and Alembic migrations.

```bash
metadb init [--alembic-only] [--db-only]
```

**What it does:**
- Creates `palimpsest.db` SQLite database
- Runs schema creation
- Initializes Alembic migration tracking
- Sets up FTS5 search indexes

**Options:**
- `--alembic-only` - Only initialize Alembic (skip DB creation)
- `--db-only` - Only create database (skip Alembic)

**When to use:**
- First time setup
- After deleting database
- Fresh installation

#### `metadb reset`

Delete and reinitialize database.

```bash
metadb reset [--yes] [--keep-backups]
```

**What it does:**
- Deletes `palimpsest.db`
- Removes Alembic version table
- Optionally deletes backups
- Runs `metadb init` to recreate

**Options:**
- `--yes` - Skip confirmation prompt
- `--keep-backups` - Don't delete existing backups

⚠️ **WARNING:** This permanently deletes all data!

### Backup & Restore

#### `metadb backup`

Create timestamped backup.

```bash
metadb backup [--type TYPE] [--suffix TEXT]
```

**Backup types:**
- `manual` - Manual backup (default)
- `daily` - Daily automated backup
- `weekly` - Weekly automated backup

**Options:**
- `--type` - Backup type (affects filename)
- `--suffix` - Custom suffix for filename

**Output:**
```
data/backups/palimpsest_YYYYMMDD_HHMMSS_TYPE.db
```

**Best practices:**
- Backup before major changes
- Automate daily backups with cron
- Keep multiple backup generations

#### `metadb backups`

List all available backups.

```bash
metadb backups
```

**Output shows:**
- Filename
- Timestamp
- File size
- Backup type

#### `metadb restore`

Restore from a backup file.

```bash
metadb restore BACKUP_PATH [--yes]
```

**What it does:**
- Validates backup file
- Creates backup of current database
- Replaces current database with backup
- Verifies restoration

**Options:**
- `--yes` - Skip confirmation prompt

### Health & Statistics

#### `metadb stats`

Display database statistics.

```bash
metadb stats [--verbose]
```

**Standard output:**
- Total entries
- Entries by year
- Total people, locations, events
- Database file size

**Verbose output adds:**
- Entries by month
- Top 10 people by mentions
- Top 10 locations
- Tag usage statistics
- Theme distribution

#### `metadb health`

Run comprehensive health check.

```bash
metadb health [--fix]
```

**Checks performed:**
- Database file exists and is readable
- Schema matches ORM models
- No foreign key violations
- No orphaned records
- Migrations are up to date
- FTS5 index is synced

**Options:**
- `--fix` - Attempt automatic repairs

**Exit codes:**
- `0` - All checks passed
- `1` - Issues found (see output)

#### `metadb optimize`

Optimize database performance.

```bash
metadb optimize [--yes]
```

**What it does:**
- Runs SQLite `VACUUM` (defragments, reclaims space)
- Runs `ANALYZE` (updates query planner statistics)
- Rebuilds FTS5 indexes

**When to use:**
- After large deletions
- Database feels slow
- Before backups
- Monthly maintenance

**Options:**
- `--yes` - Skip confirmation

⚠️ **Note:** Can take several minutes on large databases.

#### `metadb prune-orphans`

Detect and remove orphaned entities.

```bash
metadb prune-orphans [--dry-run]
```

**What it does:**
- Finds entities with no associations
- Reports orphaned records
- Optionally removes them

**Options:**
- `--dry-run` - Show what would be deleted without deleting

### Migration Management

#### `metadb migration`

Manage database migrations.

```bash
metadb migration COMMAND
```

**Commands:**

##### `status`

Show current migration status.

```bash
metadb migration status
```

**Output:**
- Current revision
- Head revision
- Pending migrations (if any)

##### `upgrade`

Upgrade database to specified revision.

```bash
metadb migration upgrade [REVISION]
```

**Arguments:**
- `REVISION` - Target revision (default: `head`)

**Examples:**
```bash
# Upgrade to latest
metadb migration upgrade

# Upgrade to specific revision
metadb migration upgrade abc123

# Upgrade one step
metadb migration upgrade +1
```

##### `downgrade`

Downgrade database to specified revision.

```bash
metadb migration downgrade REVISION
```

**Examples:**
```bash
# Downgrade one step
metadb migration downgrade -1

# Downgrade to specific revision
metadb migration downgrade abc123
```

##### `history`

Show migration history.

```bash
metadb migration history
```

**Output:**
- All migrations in chronological order
- Current revision marked
- Migration descriptions

##### `create`

Create a new Alembic migration.

```bash
metadb migration create "Description of changes"
```

**For developers:** Creates autogenerated migration based on model changes.

### Query Commands

#### `metadb query`

Browse and query database content.

```bash
metadb query COMMAND
```

**Commands:**

##### `years`

List all years with entry counts.

```bash
metadb query years
```

**Output:**
```
Year    Entries
2024    365
2023    312
2022    289
```

##### `months`

List all months in a year with entry counts.

```bash
metadb query months YEAR
```

**Example:**
```bash
metadb query months 2024
```

**Output:**
```
Month      Entries
2024-01    31
2024-02    29
...
```

##### `show`

Display a single entry with all metadata.

```bash
metadb query show YYYY-MM-DD
```

**Output includes:**
- Entry content
- All people mentioned
- Locations and cities
- Events and themes
- Tags and references

**Example:**
```bash
metadb query show 2024-11-26
```

##### `batches`

Show how entries would be batched for export.

```bash
metadb query batches [--year YYYY]
```

**Use cases:**
- Preview batch processing
- Understand grouping logic
- Debug batch operations

### Maintenance Commands

#### `metadb maintenance`

Database maintenance and optimization.

```bash
metadb maintenance COMMAND
```

**Commands:**

##### `validate`

Validate database integrity.

```bash
metadb maintenance validate
```

**Checks:**
- Foreign key constraints
- Unique constraints
- Referential integrity
- Orphaned records

##### `cleanup`

Clean up orphaned records.

```bash
metadb maintenance cleanup [--dry-run]
```

**What it removes:**
- Orphaned associations
- Dangling foreign keys
- Empty/null records

**Options:**
- `--dry-run` - Show what would be deleted without deleting

##### `analyze`

Generate detailed analytics report.

```bash
metadb maintenance analyze [--output PATH]
```

**Report includes:**
- Table sizes
- Index usage statistics
- Query performance metrics
- Growth trends

### Export Commands

#### `metadb export`

Export database to various formats.

```bash
metadb export COMMAND
```

**Commands:**

##### `csv`

Export all tables to CSV files.

```bash
metadb export csv [--output-dir PATH]
```

**Output:**
```
exports/
  entries.csv
  people.csv
  locations.csv
  ...
```

**Use cases:**
- Data analysis in Excel/pandas
- Backup in human-readable format
- Migration to other systems

##### `json`

Export complete database to JSON.

```bash
metadb export json [--output PATH]
```

**Output format:**
```json
{
  "entries": [...],
  "people": [...],
  "locations": [...],
  ...
}
```

**Use cases:**
- Complete data export
- System migration
- API integration

---

## VALIDATE - Validation Suite

Comprehensive validation for database, markdown, and consistency.

### Database Validation

#### `validate db`

Validate database integrity and constraints.

```bash
validate db COMMAND
```

**Commands:**

##### `schema`

Check for schema drift between models and database.

```bash
validate db schema [--db-path PATH]
```

**What it checks:**
- Table structure matches ORM models
- Column types match
- Constraints match
- Indexes match

**When to run:**
- After model changes
- Before/after migrations
- Troubleshooting issues

##### `migrations`

Check if all migrations have been applied.

```bash
validate db migrations [--db-path PATH] [--alembic-dir PATH]
```

**Checks:**
- Current database revision
- Pending migrations
- Migration history consistency

##### `integrity`

Check for orphaned records and foreign key violations.

```bash
validate db integrity [--db-path PATH]
```

**What it checks:**
- Foreign key constraints
- Orphaned child records
- Circular references
- Null constraint violations

##### `constraints`

Check for unique constraint violations.

```bash
validate db constraints [--db-path PATH]
```

**Checks:**
- Duplicate values in unique columns
- Primary key violations
- Unique index violations

##### `all`

Run all database validation checks.

```bash
validate db all [--db-path PATH]
```

**Runs:**
- schema
- migrations
- integrity
- constraints

### Markdown Validation

#### `validate md`

Validate markdown journal entry files.

```bash
validate md COMMAND
```

**Commands:**

##### `frontmatter`

Validate YAML frontmatter in markdown files.

```bash
validate md frontmatter [--md-dir PATH]
```

**What it validates:**
- YAML syntax correctness
- Required fields present
- Field types correct
- Date formats valid

**Common issues found:**
- Malformed YAML
- Missing colons
- Incorrect indentation
- Invalid date formats

##### `links`

Check for broken internal markdown links.

```bash
validate md links [--md-dir PATH]
```

**Checks:**
- Relative links to other markdown files
- Anchor links within files
- Image references

##### `all`

Run all markdown validation checks.

```bash
validate md all [--md-dir PATH]
```

### Frontmatter Validation

#### `validate frontmatter`

Validate frontmatter structures for parser compatibility.

```bash
validate frontmatter COMMAND
```

**Commands:**

##### `people`

Validate people field structures.

```bash
validate frontmatter people [--md-dir PATH]
```

**Checks:**
- Person name format
- Special character usage
- Category validity
- Alias structures

##### `locations`

Validate locations-city dependency.

```bash
validate frontmatter locations [--md-dir PATH]
```

**Checks:**
- Location names valid
- City associations exist
- City references consistent

##### `dates`

Validate dates field structures.

```bash
validate frontmatter dates [--md-dir PATH]
```

**Checks:**
- Date format (YYYY-MM-DD)
- Date ranges valid
- Context field format

##### `poems`

Validate poems field structures.

```bash
validate frontmatter poems [--md-dir PATH]
```

**Checks:**
- Poem title format
- Version structures
- Content validity

##### `references`

Validate references field structures.

```bash
validate frontmatter references [--md-dir PATH]
```

**Checks:**
- Reference source format
- Citation structures
- Speaker/mode fields

##### `all`

Run all frontmatter validation checks.

```bash
validate frontmatter all [--md-dir PATH]
```

### Cross-System Consistency

#### `validate consistency`

Validate consistency across systems.

```bash
validate consistency COMMAND
```

**Commands:**

##### `existence`

Check entry existence across MD ↔ DB.

```bash
validate consistency existence [--md-dir PATH] [--db-path PATH]
```

**Checks:**
- Entries in MD exist in DB
- Entries in DB have MD files

**Finds:**
- Orphaned markdown files
- Database entries without files

##### `metadata`

Check metadata synchronization between MD and DB.

```bash
validate consistency metadata [--md-dir PATH] [--db-path PATH]
```

**Compares:**
- YAML frontmatter vs DB fields
- People lists
- Location associations
- Theme/tag assignments

**Detects:**
- Outdated database
- Unsaved markdown changes
- Sync drift

##### `references`

Check referential integrity constraints.

```bash
validate consistency references [--md-dir PATH] [--db-path PATH]
```

**Validates:**
- Person references point to real people
- Location references valid
- Event associations correct

##### `integrity`

Check file hash integrity.

```bash
validate consistency integrity [--md-dir PATH]
```

**Checks:**
- Files haven't been corrupted
- Checksums match stored values
- No unexpected modifications

##### `all`

Run all consistency validation checks.

```bash
validate consistency all [--md-dir PATH] [--db-path PATH]
```

---

## JSEARCH - Full-Text Search

Full-text search using SQLite FTS5 with advanced filtering.

### Search Index Management

#### `jsearch index`

Manage full-text search index.

```bash
jsearch index COMMAND
```

**Commands:**

##### `create`

Create full-text search index.

```bash
jsearch index create
```

**What it does:**
- Creates FTS5 virtual table
- Indexes all entry content
- Includes metadata for filtering

**When to run:**
- First time setup
- After database reset

##### `rebuild`

Rebuild full-text search index.

```bash
jsearch index rebuild
```

**When to run:**
- After large batch imports
- If search results seem outdated
- Monthly maintenance

##### `status`

Check full-text search index status.

```bash
jsearch index status
```

**Output:**
- Index exists: Yes/No
- Indexed entries: N
- Last updated: timestamp

### Query Interface

#### `jsearch query`

Search journal entries with filters.

```bash
jsearch query "search terms" [FILTERS] [OPTIONS]
```

**Query Syntax:**

**Free text search:**
```bash
jsearch query "therapy sessions"
jsearch query "alice and bob"
jsearch query "creative writing"
```

**Filter by person:**
```bash
jsearch query "reflection" person:alice
jsearch query "dinner" person:bob person:charlie
```

**Filter by location/city:**
```bash
jsearch query "coffee" city:montreal
jsearch query "restaurant" city:"new york"
```

**Filter by date:**
```bash
jsearch query "birthday" in:2024
jsearch query "vacation" in:2024-07
jsearch query "therapy" in:2023 in:2024
```

**Filter by word count:**
```bash
jsearch query "long entry" words:1000-
jsearch query "short note" words:-200
jsearch query "medium length" words:500-1000
```

**Filter by tag:**
```bash
jsearch query "creative" tag:writing
```

**Complex queries (combine multiple filters):**
```bash
jsearch query "therapy session" person:alice city:montreal in:2024 words:500-1000
jsearch query "reflection" tag:introspection in:2024-11
```

**Options:**
- `--limit N` - Maximum results (default: 50)
- `--sort FIELD` - Sort by: `relevance`, `date`, `word_count` (default: relevance)
- `--verbose` - Show detailed metadata

**Examples:**
```bash
# Simple search
jsearch query "therapy"

# Search with person filter
jsearch query "conversation" person:alice

# Complex query with multiple filters
jsearch query "creative writing" city:montreal in:2024 words:500- --limit 20 --sort date

# Verbose output with metadata
jsearch query "important decision" --verbose
```

**Output format (standard):**
```
2024-11-26 | 847 words | therapy session with alice
2024-11-15 | 612 words | deep conversation about therapy
...
```

**Output format (verbose):**
```
Date: 2024-11-26
Word Count: 847
People: alice, bob
City: montreal
Tags: therapy, introspection
Themes: self-discovery

therapy session with alice discussing...
```

---

## Common Workflows

### Daily Workflow

```bash
# Morning: process new entries
plm inbox && plm convert && plm import-metadata

# Search your journal
jsearch query "therapy" person:alice in:2024

# Evening: backup
metadb backup
```

### Weekly Maintenance

```bash
# Validate everything
validate db all
validate consistency all

# Optimize database
metadb optimize

# Review statistics
metadb stats --verbose
```

### Monthly Tasks

```bash
# Rebuild search index
jsearch index rebuild

# Full system backup
plm backup-full

# Check database health
metadb health
```

### Before Major Changes

```bash
# Create backup
metadb backup --suffix "before-major-change"

# Validate current state
validate consistency all

# [Make your changes]

# Validate again
validate consistency all

# If something breaks, restore:
metadb restore data/backups/palimpsest_..._before-major-change.db
```

---

## Troubleshooting

### "Database not initialized"
```bash
metadb init
```

### "Search index not found"
```bash
jsearch index create
```

### "Metadata out of sync"
```bash
validate consistency metadata
# If drift detected:
plm import-metadata  # Re-import from metadata
```

### "Slow database queries"
```bash
metadb optimize
jsearch index rebuild
```

---

## Getting Help

**View command help:**
```bash
plm --help
metadb --help
validate --help
jsearch --help

# Subcommand help
metadb backup --help
validate db check --help
jsearch query --help
```

**Check status:**
```bash
plm status
metadb health
```

---

**Last Updated:** 2026-02-06
