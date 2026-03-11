# Palimpsest Command Reference

Complete reference for all Palimpsest CLI commands.

---

## Installation

```bash
# Install from repository
pip install -e .
```

This installs two CLI entry points:
- `plm` - Pipeline and database management (includes validation via `plm validate`)
- `jsearch` - Full-text search

---

## Quick Reference

### Daily Workflow

```bash
# Process new journal entries
plm inbox && plm convert && plm sync

# Sync after git pull on another machine
plm sync

# Search your journal
jsearch query "therapy" person:alice in:2024
```

### Wiki Operations

```bash
# Generate wiki pages
plm wiki generate

# Lint and sync manuscript
plm wiki lint data/wiki/ && plm wiki sync
```

### Metadata Management

```bash
# Export/import YAML metadata
plm metadata export --type people
plm metadata import data/metadata/people/clara.yaml
```

### Database Operations

```bash
# Create backup (do this regularly!)
plm db backup

# Check database health
plm db health

# View statistics
plm db stats --verbose
```

### Validation

```bash
# Validate database
plm validate db all

# Validate consistency
plm validate consistency all
```

---

## PLM - Pipeline Commands

Pipeline processing for journal entries.

### Data Pipeline

#### `plm inbox`

Process inbox text files.

```bash
plm inbox [--inbox PATH] [--output PATH]
```

**What it does:**
- Scans inbox directory for raw 750words exports
- Groups entries by date
- Creates formatted text files
- Prepares entries for conversion

**Options:**
- `--inbox PATH` - Inbox directory with raw exports (defaults to `data/journal/sources/inbox`)
- `--output PATH` - Output directory for formatted text (defaults to `data/journal/sources/txt`)

#### `plm convert`

Convert formatted text to Markdown entries.

```bash
plm convert [-i PATH] [-o PATH] [-f] [--dry-run] [--yaml-dir PATH] [--no-yaml]
```

**What it does:**
- Processes formatted text files
- Converts text to markdown format
- Generates YAML metadata skeletons
- Outputs to `data/journal/content/md/YYYY/YYYY-MM-DD.md`

**Options:**
- `-i/--input PATH` - Input directory with formatted text files (defaults to `data/journal/sources/txt`)
- `-o/--output PATH` - Output directory for Markdown files (defaults to `data/journal/content/md`)
- `-f/--force` - Force overwrite existing files
- `--dry-run` - Preview changes without modifying files
- `--yaml-dir PATH` - Output directory for YAML metadata skeletons
- `--no-yaml` - Disable YAML skeleton generation

#### `plm sync`

Synchronize database with files and regenerate outputs.

```bash
plm sync [--no-wiki] [--commit] [--dry-run] [--years RANGE] [-v]
```

**What it does:**
- Imports shared DB state from JSON exports (cross-machine changes)
- Processes journal entries where content hash changed (local edits)
- Imports entity YAML metadata (people, locations, chapters, etc.)
- Re-exports DB to JSON if any changes were detected
- Regenerates wiki pages (unless `--no-wiki`)
- Optionally commits data/ submodule (with `--commit`)

**Options:**
- `--no-wiki` - Skip wiki page regeneration
- `--commit` - Auto-commit changes in data/ submodule
- `--dry-run` - Preview changes without modifying database
- `--years RANGE` - Limit entries import scope (e.g., `2024` or `2021-2025`)
- `-v/--verbose` - Show detailed per-entity output

**Examples:**
```bash
# Standard sync after git pull
plm sync

# Sync without wiki, auto-commit data submodule
plm sync --no-wiki --commit

# Preview what would change
plm sync --dry-run

# Limit to specific years
plm sync --years 2024-2025
```

**Use cases:**
- Cross-machine workflow (sync after `git pull`)
- Daily workflow after processing new entries
- Replacing the old `entries import → json export → wiki generate` chain

#### `plm export`

Export database entities to JSON files.

```bash
plm export [--no-commit]
```

**What it does:**
- Exports all database entities to JSON format using natural keys
- Creates structured export for version control
- Outputs to `data/exports/journal/`

**Options:**
- `--no-commit` - Write JSON files without creating a git commit

**Use cases:**
- Manual JSON export outside of sync workflow
- Editor integration (Neovim plugin uses this after entity edits)

### Build Commands

#### `plm build pdf`

Build PDFs for a year's entries.

```bash
plm build pdf YEAR [-i PATH] [-o PATH] [-f] [--debug]
```

**Arguments:**
- `YEAR` - Year to build (required)

**What it does:**
- Generates clean and annotated PDF versions
- Uses Pandoc + LaTeX for typography
- Outputs to `data/journal/content/pdf/`

**Options:**
- `-i/--input PATH` - Input directory with Markdown files
- `-o/--output PATH` - Output directory for PDFs
- `-f/--force` - Force overwrite existing PDFs
- `--debug` - Keep temp files on error for debugging

**Requirements:**
- Pandoc 2.19+
- XeLaTeX or Tectonic
- Cormorant Garamond font

### Batch Operations

#### `plm pipeline run`

Run the complete pipeline end-to-end.

```bash
plm pipeline run [--year YEAR] [--skip-inbox] [--skip-sync] [--skip-pdf] [--backup]
```

**Options:**
- `--year YEAR` - Specific year to process (optional)
- `--skip-inbox` - Skip inbox processing
- `--skip-sync` - Skip sync (import/export/wiki)
- `--skip-pdf` - Skip PDF generation
- `--backup` - Create DB backup after completion

**What it runs:**
1. `plm inbox` (unless `--skip-inbox`)
2. `plm convert`
3. `plm sync` (unless `--skip-sync`)
4. `plm build pdf` (unless `--skip-pdf`, requires `--year`)
5. `plm db backup` (only with `--backup`)

### Backup Operations

#### `plm db backup --full`

Create complete system backup.

```bash
plm db backup --full [--suffix TEXT]
```

**What it backs up:**
- SQLite database
- All markdown files
- Configuration files

**Options:**
- `--suffix TEXT` - Optional suffix for backup filename

**Output:**
- Timestamped compressed archive in `data/backups/`

#### `plm db backups --full`

List all available full backups.

```bash
plm db backups --full
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

Run validation checks across all subsystems.

```bash
plm validate COMMAND
```

**Commands:**
- `pipeline` - Validate pipeline directory structure and dependencies
- `entry` - Validate journal entries (MD + YAML)
- `db` - Database integrity checks (schema, migrations, constraints)
- `md` - Markdown file validation (frontmatter, links)
- `frontmatter` - Metadata parser compatibility (people, locations, dates, poems, references)
- `consistency` - Cross-system consistency (existence, metadata, references, integrity)

See the [Validation Suite](#plm-validate---validation-suite) section for full details on each subcommand.

#### `plm validate entry`

Validate journal entry files.

```bash
plm validate entry [DATE] [-f FILE] [-y YEAR] [--years RANGE] [--all] [-q]
```

**Arguments:**
- `DATE` - Specific entry date to validate (optional)

**Options:**
- `-f/--file PATH` - Validate a specific file
- `-y/--year YEAR` - Validate all entries in a year (e.g., `2024`)
- `--years RANGE` - Validate a year range (e.g., `2021-2025`)
- `--all` - Validate all entries
- `-q/--quickfix` - Output in quickfix format for Neovim integration

#### `plm build metadata`

Build PDF from metadata YAML files for a year.

```bash
plm build metadata YEAR [-i PATH] [-o PATH] [-f] [--debug]
```

**Arguments:**
- `YEAR` - Year to build (required)

**Options:**
- `-i/--input PATH` - Input directory with YAML files
- `-o/--output PATH` - Output directory for PDF
- `-f/--force` - Force overwrite existing PDF
- `--debug` - Keep temp files on error for debugging

### Wiki Commands

#### `plm wiki generate`

Generate wiki pages from database.

```bash
plm wiki generate [--section SECTION] [--type TYPE] [--output-dir PATH]
```

**What it does:**
- Renders journal and manuscript pages via Jinja2 templates
- Creates index pages with cross-references
- Outputs clean markdown with `[[wikilinks]]`
- Populates `data/wiki/` directory structure

**Options:**
- `--section` - Generate only a specific section: `journal`, `manuscript`, `indexes`
- `--type` - Generate only a specific entity type (e.g., `people`, `locations`)
- `--output-dir PATH` - Custom output directory (defaults to `data/wiki`)

**Examples:**
```bash
# Generate everything
plm wiki generate

# Generate only journal pages
plm wiki generate --section journal

# Generate only people pages
plm wiki generate --type people
```

#### `plm wiki lint`

Lint wiki files for structural issues and broken wikilinks.

```bash
plm wiki lint <path> [--format FORMAT]
```

**Arguments:**
- `path` - File or directory to lint (required)

**What it does:**
- Validates wiki page structure (headings, sections)
- Checks `[[wikilinks]]` resolve to known entities
- Reports missing required sections, invalid metadata
- Returns structured diagnostics with file, line, severity, and code

**Options:**
- `--format` - Output format: `json` or `text` (auto-detects based on TTY)

**Examples:**
```bash
# Lint a single file
plm wiki lint data/wiki/manuscript/chapters/the-gray-fence.md

# Lint entire wiki directory
plm wiki lint data/wiki/

# JSON output for Neovim integration
plm wiki lint data/wiki/ --format json
```

**Diagnostic Codes:**
- Errors (block sync): `UNRESOLVED_WIKILINK`, `MISSING_REQUIRED_SECTION`, `INVALID_METADATA`
- Warnings: `EMPTY_SECTION`, `ORPHAN_SCENE`, `MISSING_SOURCES`

#### `plm wiki sync`

Sync manuscript metadata and wiki pages with database.

```bash
plm wiki sync [--ingest] [--generate]
```

**What it does:**
- Validates manuscript wiki pages (errors block sync)
- Imports YAML metadata files into database (ingest)
- Regenerates wiki pages from updated database (generate)
- Only overwrites pages where DB state diverges from disk

**Sync cycle:**
1. **Validate**: Run validator on all manuscript wiki files
2. **Ingest**: Import YAML metadata for chapters, characters, and scenes via MetadataImporter
3. **Regenerate**: Render all manuscript pages from DB

**Options:**
- `--ingest` - Only import YAML metadata → DB (skip regeneration)
- `--generate` - Only regenerate DB → wiki (skip ingestion)

**Note:** `--ingest` and `--generate` are mutually exclusive. Without either flag, runs the full cycle: ingest + regenerate.

**Examples:**
```bash
# Full sync cycle
plm wiki sync

# Ingest only (YAML metadata → DB)
plm wiki sync --ingest

# Regenerate only (DB → wiki)
plm wiki sync --generate
```

### Metadata Commands

#### `plm metadata export`

Export entity metadata to YAML files.

```bash
plm metadata export [--type TYPE] [--output-dir PATH]
```

**What it does:**
- Exports database entities as structured YAML files
- Per-entity files for people, locations, chapters, characters, scenes
- Single files for cities, arcs
- Outputs to `data/metadata/` directory

**Options:**
- `--type` - Export only a specific type: `people`, `locations`, `cities`, `arcs`, `chapters`, `characters`, `scenes`, `neighborhoods`, `relation_types`, `entries`, `journal_scenes`, `threads`, `poems`, `reference_sources`
- `--output-dir PATH` - Custom output directory (defaults to `data/metadata`)

**Examples:**
```bash
# Export all entity types
plm metadata export

# Export only people
plm metadata export --type people
```

#### `plm metadata import`

Import YAML metadata files into database.

```bash
plm metadata import [<path>] [--type TYPE]
```

**Arguments:**
- `path` - Single YAML file to import (optional if using `--type`)

**What it does:**
- Validates YAML structure against schema
- Imports metadata into database
- Reports import errors with diagnostic codes

**Options:**
- `--type` - Import all YAML files of a specific entity type

**Examples:**
```bash
# Import a single file
plm metadata import data/metadata/people/clara.yaml

# Import all people
plm metadata import --type people
```

#### `plm metadata validate`

Validate a YAML metadata file against its schema.

```bash
plm metadata validate <path>
```

**Arguments:**
- `path` - YAML file to validate (required)

**What it does:**
- Checks YAML syntax and structure
- Validates against the entity type schema
- Reports errors and warnings with severity and diagnostic codes

**Exit codes:**
- `0` - Valid (no errors)
- `1` - Validation errors found

#### `plm metadata list`

List entity names for autocomplete support.

```bash
plm metadata list --type TYPE [--format FORMAT]
```

**What it does:**
- Queries database for all entity names of a given type
- Outputs names as plain text or JSON array
- Used by the Neovim plugin for entity name caching

**Options:**
- `--type` - Entity type (required): `people`, `locations`, `cities`, `arcs`, `chapters`, `characters`, `scenes`, `neighborhoods`, `relation_types`, `entries`, `journal_scenes`, `threads`, `poems`, `reference_sources`
- `--format` - Output format: `text` (default) or `json`

**Output formats by entity type:**
- Most types return plain names/titles
- `entries` returns ISO dates (`2024-11-26`)
- `journal_scenes` and `threads` return `name::date` composites (`Morning Walk::2024-11-26`)

**Examples:**
```bash
# List all people names
plm metadata list --type people

# JSON output for programmatic consumption
plm metadata list --type chapters --format json

# List journal scenes with entry dates
plm metadata list --type journal_scenes

# List reference sources
plm metadata list --type reference_sources --format json
```

#### `plm metadata rename`

Rename an entity across the database and all YAML/wiki files.

```bash
plm metadata rename ENTITY_TYPE OLD_NAME NEW_NAME [--city CITY] [--apply]
```

**Arguments:**
- `ENTITY_TYPE` - Entity type: `location`, `tag`, `theme`, `arc`, `person`, `city`, `motif`, `event`
- `OLD_NAME` - Current entity name
- `NEW_NAME` - New entity name

**Options:**
- `--city CITY` - City for location disambiguation (when multiple locations share a name)
- `--apply` - Execute the rename (default is dry-run preview)

**Examples:**
```bash
# Preview rename
plm metadata rename person "Alice Smith" "Alice Johnson"

# Execute rename
plm metadata rename person "Alice Smith" "Alice Johnson" --apply

# Rename location with city disambiguation
plm metadata rename location "Main Street" "High Street" --city montreal --apply
```

---

## METADB - Database Management

Database administration and maintenance.

### Setup & Initialization

#### `plm db init`

Initialize database and Alembic migrations.

```bash
plm db init [--alembic-only] [--db-only]
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

#### `plm db reset`

Delete and reinitialize database.

```bash
plm db reset [--yes] [--keep-backups]
```

**What it does:**
- Deletes `palimpsest.db`
- Removes Alembic version table
- Optionally deletes backups
- Runs `plm db init` to recreate

**Options:**
- `--yes` - Skip confirmation prompt
- `--keep-backups` - Don't delete existing backups

⚠️ **WARNING:** This permanently deletes all data!

### Backup & Restore

#### `plm db backup`

Create timestamped backup.

```bash
plm db backup [--type TYPE] [--suffix TEXT]
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

#### `plm db backups`

List all available backups.

```bash
plm db backups
```

**Output shows:**
- Filename
- Timestamp
- File size
- Backup type

#### `plm db restore`

Restore from a backup file.

```bash
plm db restore BACKUP_PATH [--yes]
```

**What it does:**
- Validates backup file
- Creates backup of current database
- Replaces current database with backup
- Verifies restoration

**Options:**
- `--yes` - Skip confirmation prompt

### Health & Statistics

#### `plm db stats`

Display database statistics.

```bash
plm db stats [--verbose]
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

#### `plm db health`

Run comprehensive health check.

```bash
plm db health [--fix]
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

#### `plm db optimize`

Optimize database performance.

```bash
plm db optimize [--yes]
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

#### `plm db prune`

Detect and remove orphaned entities.

```bash
plm db prune [--type TYPE] [--list] [--dry-run]
```

**What it does:**
- Finds entities with no associations
- Reports orphaned records
- Optionally removes them

**Options:**
- `--type TYPE` - Entity type to prune: `people`, `locations`, `cities`, `tags`, `themes`, `arcs`, `events`, `reference_sources`, `poems`, `motifs`, `all` (default: `all`)
- `--list` - Only list orphans, don't delete
- `--dry-run` - Show what would be deleted without deleting

### Migration Management

#### `plm db migration`

Manage database migrations.

```bash
plm db migration COMMAND
```

**Commands:**

##### `status`

Show current migration status.

```bash
plm db migration status
```

**Output:**
- Current revision
- Head revision
- Pending migrations (if any)

##### `upgrade`

Upgrade database to specified revision.

```bash
plm db migration upgrade [REVISION]
```

**Arguments:**
- `REVISION` - Target revision (default: `head`)

**Examples:**
```bash
# Upgrade to latest
plm db migration upgrade

# Upgrade to specific revision
plm db migration upgrade abc123

# Upgrade one step
plm db migration upgrade +1
```

##### `downgrade`

Downgrade database to specified revision.

```bash
plm db migration downgrade REVISION
```

**Examples:**
```bash
# Downgrade one step
plm db migration downgrade -1

# Downgrade to specific revision
plm db migration downgrade abc123
```

##### `history`

Show migration history.

```bash
plm db migration history
```

**Output:**
- All migrations in chronological order
- Current revision marked
- Migration descriptions

##### `create`

Create a new Alembic migration.

```bash
plm db migration create "Description of changes"
```

**For developers:** Creates autogenerated migration based on model changes.

### Query Commands

#### `plm db query`

Browse and query database content.

```bash
plm db query COMMAND
```

**Commands:**

##### `years`

List all years with entry counts.

```bash
plm db query years
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
plm db query months YEAR
```

**Example:**
```bash
plm db query months 2024
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
plm db query show YYYY-MM-DD
```

**Output includes:**
- Entry content
- All people mentioned
- Locations and cities
- Events and themes
- Tags and references

**Example:**
```bash
plm db query show 2024-11-26
```

##### `batches`

Show how entries would be batched for export.

```bash
plm db query batches [--threshold N]
```

**Options:**
- `--threshold N` - Batch size threshold (default: 500)

**Use cases:**
- Preview batch processing
- Understand grouping logic
- Debug batch operations

### Maintenance Commands

#### `plm db maintenance`

Database maintenance and optimization.

```bash
plm db maintenance COMMAND
```

**Commands:**

##### `validate`

Validate database integrity.

```bash
plm db maintenance validate
```

**Checks:**
- Foreign key constraints
- Unique constraints
- Referential integrity
- Orphaned records

##### `cleanup`

Clean up orphaned records.

```bash
plm db maintenance cleanup
```

**What it removes:**
- Orphaned associations
- Dangling foreign keys
- Empty/null records

Prompts for confirmation before proceeding.

##### `analyze`

Generate detailed analytics report.

```bash
plm db maintenance analyze
```

**Report includes:**
- Table sizes
- Index usage statistics
- Query performance metrics
- Growth trends

---

## PLM VALIDATE - Validation Suite

Comprehensive validation for database, markdown, and consistency.
Accessed via `plm validate` (registered as a subcommand of the pipeline CLI).

### Database Validation

#### `plm validate db`

Validate database integrity and constraints.

```bash
plm validate db COMMAND
```

**Commands:**

##### `schema`

Check for schema drift between models and database.

```bash
plm validate db schema [--db-path PATH]
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
plm validate db migrations [--db-path PATH] [--alembic-dir PATH]
```

**Checks:**
- Current database revision
- Pending migrations
- Migration history consistency

##### `integrity`

Check for orphaned records and foreign key violations.

```bash
plm validate db integrity [--db-path PATH]
```

**What it checks:**
- Foreign key constraints
- Orphaned child records
- Circular references
- Null constraint violations

##### `constraints`

Check for unique constraint violations.

```bash
plm validate db constraints [--db-path PATH]
```

**Checks:**
- Duplicate values in unique columns
- Primary key violations
- Unique index violations

##### `all`

Run all database validation checks.

```bash
plm validate db all [--db-path PATH]
```

**Runs:**
- schema
- migrations
- integrity
- constraints

### Markdown Validation

#### `plm validate md`

Validate markdown journal entry files.

```bash
plm validate md COMMAND
```

**Commands:**

##### `frontmatter`

Validate YAML frontmatter in markdown files.

```bash
plm validate md frontmatter [--md-dir PATH]
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
plm validate md links [--md-dir PATH]
```

**Checks:**
- Relative links to other markdown files
- Anchor links within files
- Image references

##### `all`

Run all markdown validation checks.

```bash
plm validate md all [--md-dir PATH]
```

### Frontmatter Validation

#### `plm validate frontmatter`

Validate frontmatter structures for parser compatibility.

```bash
plm validate frontmatter COMMAND
```

**Commands:**

##### `people`

Validate people field structures.

```bash
plm validate frontmatter people [--md-dir PATH]
```

**Checks:**
- Person name format
- Special character usage
- Category validity
- Alias structures

##### `locations`

Validate locations-city dependency.

```bash
plm validate frontmatter locations [--md-dir PATH]
```

**Checks:**
- Location names valid
- City associations exist
- City references consistent

##### `dates`

Validate dates field structures.

```bash
plm validate frontmatter dates [--md-dir PATH]
```

**Checks:**
- Date format (YYYY-MM-DD)
- Date ranges valid
- Context field format

##### `poems`

Validate poems field structures.

```bash
plm validate frontmatter poems [--md-dir PATH]
```

**Checks:**
- Poem title format
- Version structures
- Content validity

##### `references`

Validate references field structures.

```bash
plm validate frontmatter references [--md-dir PATH]
```

**Checks:**
- Reference source format
- Citation structures
- Speaker/mode fields

##### `all`

Run all frontmatter validation checks.

```bash
plm validate frontmatter all [--md-dir PATH]
```

### Cross-System Consistency

#### `plm validate consistency`

Validate consistency across systems.

```bash
plm validate consistency COMMAND
```

**Commands:**

##### `existence`

Check entry existence across MD ↔ DB.

```bash
plm validate consistency existence [--md-dir PATH] [--db-path PATH]
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
plm validate consistency metadata [--md-dir PATH] [--db-path PATH]
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
plm validate consistency references [--md-dir PATH] [--db-path PATH]
```

**Validates:**
- Person references point to real people
- Location references valid
- Event associations correct

##### `integrity`

Check file hash integrity.

```bash
plm validate consistency integrity [--md-dir PATH]
```

**Checks:**
- Files haven't been corrupted
- Checksums match stored values
- No unexpected modifications

##### `all`

Run all consistency validation checks.

```bash
plm validate consistency all [--md-dir PATH] [--db-path PATH]
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
plm inbox && plm convert && plm sync

# Search your journal
jsearch query "therapy" person:alice in:2024

# Evening: backup
plm db backup
```

### Weekly Maintenance

```bash
# Validate everything
plm validate db all
plm validate consistency all

# Optimize database
plm db optimize

# Review statistics
plm db stats --verbose
```

### Monthly Tasks

```bash
# Rebuild search index
jsearch index rebuild

# Full system backup
plm db backup --full

# Check database health
plm db health
```

### Wiki Workflow

```bash
# Generate wiki from database
plm wiki generate

# Edit manuscript pages in Neovim, then sync
plm wiki lint data/wiki/manuscript/
plm wiki sync

# Export metadata for entity editing
plm metadata export --type people

# After editing YAML, import back
plm metadata import --type people
```

### Before Major Changes

```bash
# Create backup
plm db backup --suffix "before-major-change"

# Validate current state
plm validate consistency all

# [Make your changes]

# Validate again
plm validate consistency all

# If something breaks, restore:
plm db restore data/backups/palimpsest_..._before-major-change.db
```

---

## Troubleshooting

### "Database not initialized"
```bash
plm db init
```

### "Search index not found"
```bash
jsearch index create
```

### "Metadata out of sync"
```bash
plm validate consistency metadata
# If drift detected:
plm sync  # Re-sync everything
```

### "Slow database queries"
```bash
plm db optimize
jsearch index rebuild
```

---

## Getting Help

**View command help:**
```bash
plm --help
plm db --help
jsearch --help

# Subcommand help
plm db backup --help
plm validate db --help
jsearch query --help
```

**Check status:**
```bash
plm status
plm db health
```

---

**Last Updated:** 2026-03-10
