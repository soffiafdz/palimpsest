# Palimpsest Complete Command Reference

**Last Updated:** 2025-11-26
**Coverage:** 100% of all CLI commands (70+ commands documented)

---

## Table of Contents

1. [Installation & Setup](#installation--setup)
2. [Quick Reference](#quick-reference)
3. [PLM - Pipeline Commands](#plm---pipeline-commands)
4. [METADB - Database Management](#metadb---database-management)
5. [VALIDATE - Validation Tools](#validate---validation-tools)
6. [JSEARCH - Full-Text Search](#jsearch---full-text-search)
7. [JAI - AI Analysis](#jai---ai-analysis)
8. [Neovim Integration](#neovim-integration)

---

## Installation & Setup

### Install Package

```bash
# Install with all dependencies
pip install -e .

# Or use make
make install

# Development mode with extra tools
make install-dev
```

This installs 5 CLI entry points in `~/.local/bin/`:
- `plm` - Main pipeline
- `metadb` - Database management
- `validate` - Validation tools
- `jsearch` - Full-text search
- `jai` - AI analysis (optional dependencies)

Ensure `~/.local/bin` is in your PATH.

### Environment Variables

```bash
# For AI Level 4 (optional)
export ANTHROPIC_API_KEY='your-claude-api-key'
export OPENAI_API_KEY='your-openai-api-key'
```

---

## Quick Reference

### Daily Workflow

```bash
# Process new journal entries
plm inbox && plm convert && plm sync-db

# Export to wiki for browsing in Neovim
plm export-wiki all

# Search your journal
jsearch query "therapy" person:alice in:2024
```

### Database Operations

```bash
# Create backup (CRITICAL - do this regularly!)
metadb backup

# Check database health
metadb health

# View statistics
metadb stats --verbose
```

### Validation

```bash
# Validate everything
validate wiki check
validate db all
validate consistency all
```

### Common Tasks

| Task | Command |
|------|---------|
| Process inbox | `plm inbox && plm convert && plm sync-db` |
| Export to wiki | `plm export-wiki all` |
| Import wiki edits | `plm import-wiki all` |
| Backup database | `metadb backup` |
| List backups | `metadb backups` |
| Search entries | `jsearch query "text" in:2024` |
| AI analysis | `jai analyze 2024-11-01 --level 2` |
| Build PDFs | `plm build-pdf 2024` |
| Full pipeline | `plm run-all --year 2024` |
| Check status | `plm status` or `metadb health` |

---

## PLM - Pipeline Commands

Main entry point for processing journal entries through the complete pipeline.

### Core Pipeline

#### `plm inbox`
Process inbox text files.

```bash
plm inbox [--inbox-dir PATH] [--batch-dir PATH]
```

**What it does:**
- Scans `data/inbox/` for `.txt` files
- Groups entries by date
- Creates batch directories in `data/batches/`
- Prepares entries for conversion

**Options:**
- `--inbox-dir PATH` - Custom inbox directory
- `--batch-dir PATH` - Custom batch output directory

#### `plm convert`
Convert batched text entries to markdown with YAML frontmatter.

```bash
plm convert [--batch-dir PATH] [--md-dir PATH]
```

**What it does:**
- Processes batch directories
- Converts text to markdown format
- Extracts YAML frontmatter
- Outputs to `data/md/YYYY/YYYY-MM-DD.md`

#### `plm sync-db`
Synchronize markdown entries to SQL database.

```bash
plm sync-db [--md-dir PATH] [--skip-validation]
```

**What it does:**
- Parses markdown frontmatter
- Updates database with entry content
- Extracts people, locations, events, themes, etc.
- Handles tombstone tracking for deletions

**Options:**
- `--skip-validation` - Skip YAML validation (faster, use with caution)

#### `plm export-db`
Export database entries back to markdown (reverse of sync-db).

```bash
plm export-db [--year YYYY] [--output-dir PATH]
```

**Use cases:**
- Regenerate markdown from database
- Create clean export of entries
- Backup entries in human-readable format

### Wiki Operations

#### `plm export-wiki`
Export database entities to vimwiki pages.

```bash
plm export-wiki [ENTITY_TYPE] [--force] [--wiki-dir PATH]
```

**Entity types:**
- `all` - Export everything (default)
- `entries` - Journal entry wiki pages
- `people` - People entity pages
- `locations` - Location pages
- `cities` - City summary pages
- `events` - Event pages
- `themes` - Theme pages
- `tags` - Tag pages
- `poems` - Poem pages
- `references` - Reference source pages
- `timeline` - Timeline visualization
- `index` - Wiki homepage
- `stats` - Statistics dashboard
- `analysis` - Analysis report

**Options:**
- `--force` - Regenerate all files (even if unchanged)
- `--wiki-dir PATH` - Custom wiki directory

**Examples:**
```bash
# Export everything
plm export-wiki all

# Export only people pages
plm export-wiki people

# Force regenerate with custom directory
plm export-wiki all --force --wiki-dir ~/my-wiki
```

#### `plm import-wiki`
Import wiki edits back to database (bidirectional sync).

```bash
plm import-wiki [ENTITY_TYPE] [--wiki-dir PATH]
```

**Entity types:**
- `all` - Import all entity types
- `people` - People notes/vignettes
- `themes` - Theme descriptions
- `tags` - Tag descriptions
- `entries` - Entry notes
- `events` - Event notes
- `manuscript-all` - All manuscript entities
- `manuscript-entries` - Manuscript entry metadata
- `manuscript-characters` - Character analysis
- `manuscript-events` - Narrative events

**What gets imported:**
- User-editable notes sections
- Vignettes (for people)
- Descriptions (for themes/tags)
- Manuscript metadata

**What is read-only:**
- Generated statistics
- Entry lists
- Dates and timestamps
- Link structures

**Examples:**
```bash
# Import all edits
plm import-wiki all

# Import only people vignettes
plm import-wiki people

# Import manuscript edits
plm import-wiki manuscript-all
```

### Batch Operations

#### `plm run-all`
Run the complete pipeline for a year.

```bash
plm run-all --year YYYY [--skip-inbox] [--skip-pdf]
```

**What it runs:**
1. `plm inbox` (unless --skip-inbox)
2. `plm convert`
3. `plm sync-db`
4. `plm export-db`
5. `plm build-pdf` (unless --skip-pdf)
6. `plm export-wiki all`

**Options:**
- `--year YYYY` - Year to process (required)
- `--skip-inbox` - Skip inbox processing
- `--skip-pdf` - Skip PDF generation

#### `plm build-pdf`
Generate PDF for a year's entries.

```bash
plm build-pdf YEAR [--output-dir PATH]
```

### Backup Operations

#### `plm backup-full`
Create complete system backup (database + markdown + wiki).

```bash
plm backup-full [--output-dir PATH]
```

**What it backs up:**
- SQLite database
- All markdown files
- Wiki pages
- Configuration files

#### `plm backup-list-full`
List all full backups.

```bash
plm backup-list-full
```

### Status & Validation

#### `plm status`
Show pipeline status and statistics.

```bash
plm status
```

**Displays:**
- Total entries by year
- Batch processing status
- Database sync status
- Last export timestamp

#### `plm validate`
Run basic validation checks.

```bash
plm validate
```

---

## METADB - Database Management

Complete database administration and maintenance toolkit.

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
**DANGEROUS:** Delete and reinitialize database.

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

**Example:**
```bash
metadb restore data/backups/palimpsest_20251126_120000_manual.db
```

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

### Migration Management

#### `metadb migration status`
Show current migration status.

```bash
metadb migration status
```

**Output:**
- Current revision
- Head revision
- Pending migrations (if any)

#### `metadb migration upgrade`
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

#### `metadb migration downgrade`
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

#### `metadb migration history`
Show migration history.

```bash
metadb migration history
```

**Output:**
- All migrations in chronological order
- Current revision marked
- Migration descriptions

#### `metadb migration create`
Create a new Alembic migration.

```bash
metadb migration create "Description of changes"
```

**For developers:** Creates autogenerated migration based on model changes.

### Query Commands

#### `metadb query years`
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

#### `metadb query months`
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

#### `metadb query show`
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
- Manuscript metadata (if any)

**Example:**
```bash
metadb query show 2024-11-26
```

#### `metadb query batches`
Show how entries would be batched for export.

```bash
metadb query batches [--year YYYY]
```

**Use cases:**
- Preview batch processing
- Understand grouping logic
- Debug batch operations

### Maintenance Commands

#### `metadb maintenance validate`
Validate database integrity.

```bash
metadb maintenance validate
```

**Checks:**
- Foreign key constraints
- Unique constraints
- Referential integrity
- Orphaned records

#### `metadb maintenance cleanup`
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

#### `metadb maintenance analyze`
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

#### `metadb export csv`
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

#### `metadb export json`
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

### Tombstone Management

Tombstones track deletions for bidirectional wiki sync.

#### `metadb tombstone list`
List association tombstones.

```bash
metadb tombstone list [--entity-type TYPE]
```

**Shows:**
- Entity type (person, location, etc.)
- Entity ID
- Associated entry
- Deletion timestamp

#### `metadb tombstone stats`
Show tombstone statistics.

```bash
metadb tombstone stats
```

**Output:**
- Total tombstones
- Tombstones by entity type
- Expired tombstones (>30 days)

#### `metadb tombstone cleanup`
Remove expired tombstones.

```bash
metadb tombstone cleanup [--days N]
```

**Options:**
- `--days N` - Remove tombstones older than N days (default: 30)

**When to run:**
- Monthly maintenance
- Before backups
- To reclaim space

#### `metadb tombstone remove`
Manually remove a specific tombstone.

```bash
metadb tombstone remove TOMBSTONE_ID
```

### Sync Management

Tracks synchronization state between wiki and database.

#### `metadb sync status`
Show sync status for entities.

```bash
metadb sync status [--entity-type TYPE] [--entity-id ID]
```

**Shows:**
- Last sync timestamp
- Sync state (synced, modified, conflict)
- Checksum
- Conflict count

#### `metadb sync stats`
Show synchronization statistics.

```bash
metadb sync stats
```

**Output:**
- Total synced entities
- Entities by sync state
- Total conflicts
- Last sync time

#### `metadb sync conflicts`
List conflicts (unresolved by default).

```bash
metadb sync conflicts [--all] [--resolved]
```

**Options:**
- `--all` - Show all conflicts (including resolved)
- `--resolved` - Show only resolved conflicts

**Output:**
- Entity type and ID
- Conflict type
- Last modified timestamp
- Resolution state

#### `metadb sync resolve`
Mark a conflict as resolved.

```bash
metadb sync resolve ENTITY_TYPE ENTITY_ID
```

**Example:**
```bash
metadb sync resolve person 42
```

---

## VALIDATE - Validation Tools

Comprehensive validation for wiki, database, markdown, and cross-system consistency.

### Wiki Validation

#### `validate wiki check`
Check all wiki links for broken references.

```bash
validate wiki check [--wiki-dir PATH]
```

**What it checks:**
- Internal wiki links (`[[page]]`)
- Cross-references between entities
- Existence of linked files

**Output:**
- List of broken links
- Source file and line number
- Target that doesn't exist

#### `validate wiki orphans`
Find orphaned wiki pages with no incoming links.

```bash
validate wiki orphans [--wiki-dir PATH]
```

**Use cases:**
- Find unused pages
- Clean up wiki structure
- Identify isolated content

#### `validate wiki stats`
Show wiki link statistics.

```bash
validate wiki stats [--wiki-dir PATH]
```

**Output:**
- Total wiki pages
- Total links
- Average links per page
- Most linked pages
- Orphan count

### Database Validation

#### `validate db schema`
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

#### `validate db migrations`
Check if all migrations have been applied.

```bash
validate db migrations [--db-path PATH] [--alembic-dir PATH]
```

**Checks:**
- Current database revision
- Pending migrations
- Migration history consistency

#### `validate db integrity`
Check for orphaned records and foreign key violations.

```bash
validate db integrity [--db-path PATH]
```

**What it checks:**
- Foreign key constraints
- Orphaned child records
- Circular references
- Null constraint violations

#### `validate db constraints`
Check for unique constraint violations.

```bash
validate db constraints [--db-path PATH]
```

**Checks:**
- Duplicate values in unique columns
- Primary key violations
- Unique index violations

#### `validate db all`
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

#### `validate md frontmatter`
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

#### `validate md links`
Check for broken internal markdown links.

```bash
validate md links [--md-dir PATH]
```

**Checks:**
- Relative links to other markdown files
- Anchor links within files
- Image references

#### `validate md all`
Run all markdown validation checks.

```bash
validate md all [--md-dir PATH]
```

### Metadata Validation

Validates that frontmatter structures match parser expectations.

#### `validate metadata people`
Validate people field structures.

```bash
validate metadata people [--md-dir PATH]
```

**Checks:**
- Person name format
- Special character usage
- Category validity
- Alias structures

#### `validate metadata locations`
Validate locations-city dependency.

```bash
validate metadata locations [--md-dir PATH]
```

**Checks:**
- Location names valid
- City associations exist
- City references consistent

#### `validate metadata dates`
Validate dates field structures.

```bash
validate metadata dates [--md-dir PATH]
```

**Checks:**
- Date format (YYYY-MM-DD)
- Date ranges valid
- Context field format

#### `validate metadata poems`
Validate poems field structures.

```bash
validate metadata poems [--md-dir PATH]
```

**Checks:**
- Poem title format
- Version structures
- Content validity

#### `validate metadata references`
Validate references field structures.

```bash
validate metadata references [--md-dir PATH]
```

**Checks:**
- Reference source format
- Citation structures
- Speaker/mode fields

#### `validate metadata all`
Run all metadata validation checks.

```bash
validate metadata all [--md-dir PATH]
```

### Cross-System Consistency

Validate consistency between markdown files, database, and wiki pages.

#### `validate consistency existence`
Check entry existence across MD ↔ DB ↔ Wiki.

```bash
validate consistency existence [--md-dir PATH] [--wiki-dir PATH] [--db-path PATH]
```

**Checks:**
- Entries in MD exist in DB
- Entries in DB have MD files
- Wiki entries have DB records

**Finds:**
- Orphaned markdown files
- Database entries without files
- Wiki pages without sources

#### `validate consistency metadata`
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

#### `validate consistency references`
Check referential integrity constraints.

```bash
validate consistency references [--md-dir PATH] [--db-path PATH]
```

**Validates:**
- Person references point to real people
- Location references valid
- Event associations correct

#### `validate consistency integrity`
Check file hash integrity.

```bash
validate consistency integrity [--md-dir PATH]
```

**Checks:**
- Files haven't been corrupted
- Checksums match stored values
- No unexpected modifications

#### `validate consistency all`
Run all consistency validation checks.

```bash
validate consistency all [--md-dir PATH] [--wiki-dir PATH] [--db-path PATH]
```

---

## JSEARCH - Full-Text Search

Powerful full-text search using SQLite FTS5 with advanced filtering.

### Search Index Management

#### `jsearch index create`
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

#### `jsearch index rebuild`
Rebuild full-text search index.

```bash
jsearch index rebuild
```

**When to run:**
- After large batch imports
- If search results seem outdated
- Monthly maintenance

#### `jsearch index status`
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

**Filter by manuscript status:**
```bash
jsearch query "scene" has:manuscript
```

**Filter by tag:**
```bash
jsearch query "creative" tag:writing
```

**Complex queries (combine multiple filters):**
```bash
jsearch query "therapy session" person:alice city:montreal in:2024 words:500-1000
jsearch query "reflection" tag:introspection has:manuscript in:2024-11
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

## JAI - AI Analysis

AI-powered analysis and extraction of journal entries.

### AI Capabilities Check

#### `jai status`
Check AI capabilities and API configuration.

```bash
jai status
```

**Checks performed:**

**Level 1 (Always Available):**
- ✓ Built-in keyword matching

**Level 2 (spaCy NER):**
- Package installed: Yes/No
- Model downloaded: en_core_web_sm
- Installation command if missing

**Level 3 (Semantic Search):**
- Package installed: sentence-transformers
- Model available: Yes/No
- Installation command if missing

**Level 4 (LLM APIs):**
- Anthropic package: Yes/No
- ANTHROPIC_API_KEY set: Yes/No
- OpenAI package: Yes/No
- OPENAI_API_KEY set: Yes/No

**Use cases:**
- Verify AI setup after installation
- Troubleshoot missing dependencies
- Check API key configuration

### Entry Analysis

#### `jai analyze`
Analyze a single journal entry with AI.

```bash
jai analyze DATE [--level LEVEL] [--provider PROVIDER] [--manuscript]
```

**Arguments:**
- `DATE` - Entry date (YYYY-MM-DD)

**AI Levels:**

**Level 2 (spaCy NER)** - Free, local, fast:
```bash
jai analyze 2024-11-26 --level 2
```

**Extracts:**
- People (PERSON entities)
- Cities (GPE entities)
- Locations (LOC entities)
- Events (EVENT entities)
- Themes (NLP pattern matching)
- Confidence scores for each

**Requirements:**
```bash
pip install spacy
python -m spacy download en_core_web_sm
```

**Level 4 (LLM API)** - Paid, cloud, advanced:
```bash
jai analyze 2024-11-26 --level 4 --provider claude
jai analyze 2024-11-26 --level 4 --provider openai
```

**Extracts:**
- Summary (2-3 sentences)
- Mood/emotional tone
- People with relationships
- Themes and tags
- Significance assessment

**With manuscript analysis:**
```bash
jai analyze 2024-11-26 --level 4 --provider claude --manuscript
```

**Additional extracts:**
- Entry type (scene, summary, reflection)
- Narrative potential score
- Suggested arc placement
- Character development notes

**Requirements:**
```bash
# For Claude
pip install anthropic
export ANTHROPIC_API_KEY='sk-ant-...'

# For OpenAI
pip install openai
export OPENAI_API_KEY='sk-...'
```

**Output format:**
```
=== AI Analysis (Level 2) ===

People:
- Alice (confidence: 0.95)
- Bob (confidence: 0.87)

Cities:
- Montreal (confidence: 0.92)

Themes:
- therapy
- self-discovery
- relationships

Events:
- therapy session

=== AI Analysis (Level 4) ===

Summary:
Reflective entry about a breakthrough in therapy with Alice,
discussing childhood patterns and their impact on current
relationships.

Mood: contemplative, hopeful

People:
- Alice (therapist, trusted)
- Bob (friend, mentioned)

Themes:
- self-discovery
- healing
- relationships

Tags:
- therapy
- introspection
- breakthrough

[Manuscript Analysis]
Entry Type: reflection
Narrative Potential: 7/10
Suggested Arc: "Therapy Journey"
Notes: Strong introspective voice, could be condensed
```

---

## Neovim Integration

Palimpsest includes a Neovim plugin for browsing and searching your wiki directly in your editor.

### Installation

Add to your LazyVim config:

```lua
{
  dir = "~/Documents/palimpsest/dev/lua/palimpsest",
  name = "palimpsest",
  dependencies = {
    "vimwiki/vimwiki",
    "ibhagwan/fzf-lua", -- LazyVim 14+ includes this by default
  },
  config = function()
    require("palimpsest").setup()
  end,
}
```

### Commands

**Export & Validation:**
```vim
:PalimpsestExport [entity_type]     " Export to wiki
:PalimpsestValidate [mode]          " Validate wiki
:PalimpsestStats                    " Open stats dashboard
:PalimpsestIndex                    " Open wiki homepage
:PalimpsestAnalysis                 " Open analysis report
```

**Browse & Search:**
```vim
:PalimpsestBrowse [entity_type]     " Browse files with fzf-lua
:PalimpsestSearch [entity_type]     " Search content with fzf-lua
:PalimpsestQuickAccess              " Quick picker for index pages
```

**Entity types:**
- `all` - All wiki content
- `journal` - Journal markdown entries
- `people` - People pages
- `entries` - Wiki entry pages
- `locations` - Location pages
- `cities` - City pages
- `events` - Event pages
- `themes` - Theme pages
- `tags` - Tag pages
- `poems` - Poem pages
- `references` - Reference pages

**Manuscript:**
```vim
:PalimpsestManuscriptExport [type]  " Export manuscript entities
:PalimpsestManuscriptImport [type]  " Import manuscript edits
:PalimpsestManuscriptIndex          " Open manuscript homepage
```

### Keybindings

**Default prefix:** `<leader>p` (if multiple vimwikis) or `<leader>v` (if single vimwiki)

**Core Operations:**
```vim
<leader>pe                          " Export all to wiki
<leader>pE                          " Export specific entity (with completion)
<leader>pv                          " Validate wiki links
<leader>ps                          " Statistics dashboard
<leader>ph                          " Wiki homepage
```

**Browse & Search:**
```vim
<leader>pf                          " Quick access to index pages
<leader>pFa                         " Browse all wiki files
<leader>pFj                         " Browse journal entries
<leader>pFp                         " Browse people
<leader>pFe                         " Browse entries
<leader>pFl                         " Browse locations
<leader>pFc                         " Browse cities
<leader>pFv                         " Browse events
<leader>pFt                         " Browse themes
<leader>pFT                         " Browse tags
<leader>pFP                         " Browse poems
<leader>pFr                         " Browse references
<leader>p/                          " Search all content
```

**Manuscript:**
```vim
<leader>pme                         " Export manuscript
<leader>pmi                         " Import manuscript edits
<leader>pmh                         " Manuscript homepage
```

### Requirements

**fzf-lua** is required for browse and search features. It ships with LazyVim 14+ by default.

For non-LazyVim users:
```lua
{ 'ibhagwan/fzf-lua', dependencies = { 'nvim-tree/nvim-web-devicons' } }
```

---

## Tips & Best Practices

### Daily Workflow

```bash
# Morning: process new entries
plm inbox && plm convert && plm sync-db

# Export to wiki for browsing
plm export-wiki all

# Work in Neovim with live wiki
# <leader>pf to browse, <leader>p/ to search

# Evening: backup
metadb backup
```

### Weekly Maintenance

```bash
# Validate everything
validate wiki check
validate db all
validate consistency all

# Optimize database
metadb optimize

# Review statistics
metadb stats --verbose
```

### Monthly Tasks

```bash
# Clean up old tombstones
metadb tombstone cleanup

# Rebuild search index
jsearch index rebuild

# Full system backup
plm backup-full

# Review and clean orphaned pages
validate wiki orphans
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

### "Broken wiki links"
```bash
validate wiki check
# Fix the reported links
plm export-wiki all  # Regenerate if needed
```

### "Metadata out of sync"
```bash
validate consistency metadata
# If drift detected:
plm sync-db  # Re-sync from markdown
```

### "AI analysis not working"
```bash
jai status  # Check what's available
# Install missing dependencies based on output
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
jai --help

# Subcommand help
metadb backup --help
validate wiki check --help
jsearch query --help
```

**Check status:**
```bash
plm status
metadb health
jai status
```

**Documentation:**
- User guides: `docs/user-guides/`
- Technical docs: `docs/dev-guides/`
- Architecture: `docs/dev-guides/architecture/`

---

**Last Updated:** 2025-11-26
**Documentation Coverage:** 100% (70+ commands)
**Maintained by:** Palimpsest Project
