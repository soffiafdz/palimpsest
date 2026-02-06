# Palimpsest Complete Feature Testing Plan

> **Note:** Wiki system tests (Section 6) reference features not yet implemented.
> Skip wiki-related test steps until the wiki module is built.

**Last Updated:** 2025-11-29
**Purpose:** Comprehensive testing guide for all Palimpsest features from beginning to end

---

## Table of Contents

1. [Overview](#overview)
2. [Testing Checklist Summary](#testing-checklist-summary)
3. [Environment & Setup Testing](#environment--setup-testing)
4. [Basic Pipeline Testing](#basic-pipeline-testing)
5. [Rich Metadata Testing](#rich-metadata-testing)
6. [Wiki System Testing](#wiki-system-testing)
7. [Search & Query Testing](#search--query-testing)
8. [Advanced Metadata Testing](#advanced-metadata-testing)
9. [NLP & Analysis Testing](#nlp--analysis-testing)
10. [PDF Generation Testing](#pdf-generation-testing)
11. [Batch Operations & Integration Testing](#batch-operations--integration-testing)
12. [Database Management Testing](#database-management-testing)
13. [Conflict Resolution & Sync Testing](#conflict-resolution--sync-testing)
14. [Export Testing](#export-testing)
15. [Neovim Integration Testing](#neovim-integration-testing)
16. [Stress Testing](#stress-testing)
17. [Error Handling & Edge Cases](#error-handling--edge-cases)
18. [Recommended Testing Order](#recommended-testing-order)

---

## Overview

This plan tests the full Palimpsest data flow pipeline:

```
Raw Export → Formatted Text → Markdown → Database → Wiki → Search/Analysis → PDF
```

Tests are organized by **complexity level** so you can start simple and build confidence before testing advanced features.

### Key Data Flow Stages

1. **Ingestion:** `inbox → txt → md`
2. **Database Sync:** `md → database` (YAML frontmatter)
3. **Wiki System:** `database ↔ wiki` (bidirectional)
4. **Search & Analysis:** Query database with FTS5, extract metadata with NLP
5. **Export:** `database → pdf` (annotated reading copies)

---

## Testing Checklist Summary

Use this checklist to track your progress:

### Core Pipeline

- [x] Database initialization
- [x] src2txt conversion
- [x] txt2md conversion
- [x] import-metadata database import
- [x] export-json database export

### Metadata & Entities

- [ ] People extraction
- [ ] Location extraction
- [ ] City tracking
- [ ] Event management
- [ ] Tag assignment
- [ ] Theme categorization
- [ ] Date mentions
- [ ] Reference citations
- [ ] Poem versions
- [ ] Manuscript metadata

### Wiki System

- [ ] sql2wiki export
- [ ] wiki2sql import
- [ ] Editable field sync
- [ ] Read-only field protection
- [ ] Link validation
- [ ] Manuscript wiki

### Search & Analysis

- [ ] FTS5 search index
- [ ] Basic text search
- [ ] Filtered search (person, city, tag, etc.)
- [ ] Search sorting
- [ ] NLP analysis (optional)

### PDF Generation

- [ ] Clean PDF
- [ ] Notes PDF
- [ ] LaTeX formatting

### Database Management

- [ ] Backup creation
- [ ] Restore functionality
- [ ] Health checks
- [ ] Optimization
- [ ] Migrations
- [ ] Validation

### Advanced Features

- [ ] Sync state management
- [ ] Conflict resolution
- [ ] Tombstone tracking
- [ ] CSV export
- [ ] JSON export
- [ ] Neovim integration (optional)

### Error Handling

- [ ] Invalid YAML handling
- [ ] Missing dependency messages
- [ ] Empty database operations
- [ ] Conflict detection

---

## Environment & Setup Testing

**Goal:** Verify your environment is correctly configured

### 1.0 Initial Installation (New Machines Only)

If setting up Palimpsest on a new machine, follow these steps:

#### Core Installation

```bash
# Install the package in editable mode
# This registers all CLI commands: plm, metadb, jsearch, validate, nlp
pip install -e .
```

**Note:** If using micromamba/conda, ensure you're in the correct environment first.

#### Verify Core Commands

```bash
# Test that all core commands are available
plm --help
metadb --help
jsearch --help
validate --help
nlp --help
```

If any command shows "command not found", reinstall with `pip install -e .`

#### Optional NLP Dependencies

The NLP features are optional. Install based on the analysis level you want:

**Using micromamba/conda:**

```bash
# Level 2 (spaCy) + Level 3 (transformers)
micromamba install -c conda-forge spacy sentence-transformers
python -m spacy download en_core_web_sm
```

**Using pip:**

```bash
# Level 2 (spaCy) + Level 3 (transformers)
pip install spacy sentence-transformers
python -m spacy download en_core_web_sm

# Level 4: LLM APIs (optional, paid)
pip install anthropic  # For Claude
pip install openai     # For OpenAI
```

**Analysis Levels:**

- Level 1: Keyword matching (always available, no install needed)
- Level 2: spaCy NER (free, local ML-based entity extraction)
- Level 3: Semantic search (free, transformer-based similarity)
- Level 4: LLM APIs (paid, requires API keys)

For Level 4, set environment variables:

```bash
export ANTHROPIC_API_KEY='your-key-here'  # For Claude
export OPENAI_API_KEY='your-key-here'     # For OpenAI
```

### 1.1 Database Initialization

```bash
# Check if database exists
metadb health

# If issues, reset and initialize
metadb backup --suffix "before-testing"
metadb init

# Verify schema
validate db schema
metadb stats
```

**Expected:** Database healthy, all tables present, migration status current

### 1.2 Search Index Setup

```bash
# Create FTS5 search index
jsearch index create

# Verify
jsearch index status
```

**Expected:** Index created successfully

### 1.3 Check Dependencies

```bash
# Check NLP capabilities (optional)
nlp status

# Check pipeline status
plm status
```

**Expected:** All core dependencies present, optional NLP noted if missing

---

## Basic Pipeline Testing

**Goal:** Test the core X2Y pipeline with minimal data

### 2.1 Test Data Preparation

Create a test entry to use throughout:

```bash
# Create test directory structure
mkdir -p data/journal/inbox
mkdir -p data/test-entries

# Create a minimal test entry
cat > data/test-entries/test-entry.txt << 'EOF'
Monday, November 25, 2024

Had coffee at Café Olimpico with Ana this morning. We discussed my thesis progress and she gave me some great feedback. The weather was cold but beautiful - typical Montreal November.

Later, I visited the library at McGill to work on Chapter 3. Made good progress on the identity section, drawing on Sartre's Being and Nothingness.

Feeling hopeful about finishing by spring.

Word count: 65
EOF
```

### 2.2 Test src2txt (if applicable to your workflow)

```bash
# Copy test file to inbox
cp data/test-entries/test-entry.txt data/journal/inbox/

# Process inbox
plm inbox

# Verify output
ls -la data/journal/sources/txt/
```

**Expected:** Formatted text file created, original archived

### 2.3 Test txt2md Conversion

```bash
# Convert to markdown
plm convert

# Check output
ls -la data/journal/content/md/2024/
cat data/journal/content/md/2025/2024-11-25.md
```

**Expected:**

- Markdown file with YAML frontmatter
- Computed fields: `date`, `word_count`, `reading_time`
- Body content preserved

### 2.4 Test Metadata Import

```bash
# Import metadata to database
plm import-metadata

# Verify
metadb query show 2024-11-25
```

**Expected:** Entry appears in database with correct metadata

### 2.5 Test JSON Export

```bash
# Export database to JSON
plm export-json

# Verify JSON output exists
ls data/exports/
```

**Expected:** Exported file matches database state

---

## Rich Metadata Testing

**Goal:** Test complex metadata extraction and relationships

### 3.1 Create Rich Metadata Entry

Edit `data/journal/content/md/2024/2024-11-25.md` to add metadata:

```yaml
---
date: 2024-11-25
word_count: 65
reading_time: 0.3

city: Montreal
locations:
  - Café Olimpico
  - McGill Library

people:
  - Ana Sofía
  - "@Myself"

tags:
  - thesis
  - philosophy
  - reflection

events:
  - thesis-writing

dates:
  - 2025-04-01 (thesis defense date)

references:
  - content: "Existence precedes essence"
    speaker: Jean-Paul Sartre
    mode: paraphrase
    source:
      title: Being and Nothingness
      type: book
      author: Jean-Paul Sartre

manuscript:
  status: draft
  themes:
    - identity
    - academic-life
---
```

### 3.2 Sync Rich Metadata

```bash
# Sync updated entry
plm import-metadata

# Verify all relationships
metadb query show 2024-11-25
```

**Expected:** All entities extracted:

- People: Ana Sofía, Myself
- Locations: Café Olimpico, McGill Library
- City: Montreal
- Tags: thesis, philosophy, reflection
- Events: thesis-writing
- Dates: 2025-04-01
- References: Being and Nothingness
- Manuscript metadata

### 3.3 Test Validators

```bash
# Validate YAML structure
validate md frontmatter

# Validate metadata consistency
validate metadata all

# Validate database integrity
validate db integrity
```

**Expected:** All validations pass

---

## Wiki System Testing

**Goal:** Test bidirectional wiki sync

### 4.1 Export Database to Wiki

```bash
# Export everything
plm export-wiki all

# Verify structure
ls -R data/wiki/
```

**Expected:** Wiki directory populated with:

- `wiki/index.md`
- `wiki/entries/2024/2024-11-25.md`
- `wiki/people/ana-sofia.md`
- `wiki/locations/montreal/cafe-olimpico.md`
- `wiki/cities/montreal.md`
- `wiki/events/thesis-writing.md`
- Etc.

### 4.2 Verify Wiki Links

```bash
# Check for broken links
validate wiki check

# View wiki stats
validate wiki stats
```

**Expected:** No broken links, stats show all entities

### 4.3 Test Wiki Editing → Database Import

Open a wiki page and edit the **notes** section:

```bash
# Edit event notes
vim data/wiki/events/thesis-writing.md

# Add to the "Notes" section:
# Major narrative arc in manuscript. Represents protagonist's
# intellectual journey and struggle with identity.

# Save and import
plm import-wiki all

# Verify notes were imported
metadb query "SELECT notes FROM events WHERE name='thesis-writing'"
```

**Expected:** Notes appear in database

### 4.4 Test Read-Only Field Protection

Edit a **read-only field** in wiki (like entry count) and verify it's regenerated:

```bash
# Edit timeline in wiki (read-only)
# Change "Entries: 1" to "Entries: 999" in wiki/events/thesis-writing.md

# Export again (should regenerate)
plm export-wiki events --force

# Check if it was overwritten back to 1
cat data/wiki/events/thesis-writing.md | grep "Entries:"
```

**Expected:** Read-only field regenerated to correct value (1)

---

## Search & Query Testing

**Goal:** Test full-text search and filtering

### 5.1 Rebuild Search Index

```bash
# Rebuild index with test data
jsearch index rebuild

# Check status
jsearch index status
```

**Expected:** Index contains test entry

### 5.2 Test Basic Search

```bash
# Search for text
jsearch query "coffee"
jsearch query "thesis"
jsearch query "Sartre"
```

**Expected:** Test entry appears in results

### 5.3 Test Filtered Search

```bash
# Filter by person
jsearch query "coffee" person:"Ana Sofía"

# Filter by city
jsearch query "library" city:Montreal

# Filter by year
jsearch query "thesis" in:2024

# Filter by word count
jsearch query "coffee" words:50-100

# Filter by tag
jsearch query "reflection" tag:philosophy

# Complex filter
jsearch query "thesis" person:"Ana Sofía" city:Montreal in:2024
```

**Expected:** Filters work correctly, results match criteria

### 5.4 Test Sorting

```bash
# Sort by date
jsearch query "thesis" --sort date

# Sort by word count
jsearch query "thesis" --sort word_count

# Sort by relevance (default)
jsearch query "thesis" --sort relevance
```

**Expected:** Results sorted correctly

---

## Advanced Metadata Testing

**Goal:** Test poems, manuscript wiki, and complex relationships

### 6.1 Test Poem Versions

Add a poem to your test entry:

```yaml
poems:
  - title: Winter in Montreal
    versions:
      - content: |
          Snow falls softly
          On cobblestone streets
          Memories frozen
        revision_date: 2024-11-25
        notes: "First draft"
```

```bash
# Sync
plm import-metadata

# Verify poem created
metadb query show 2024-11-25

# Export wiki to see poem page
plm export-wiki poems

# Check poem wiki
cat data/wiki/poems/winter-in-montreal.md
```

**Expected:** Poem entity created with version history

### 6.2 Test Manuscript Wiki

```bash
# Export manuscript wiki
plm export-wiki all  # Includes manuscript

# Check manuscript structure
ls -la data/wiki/manuscript/

# Verify manuscript entry page
cat data/wiki/manuscript/entries/2024/2024-11-25.md
```

**Expected:** Manuscript wiki populated with:

- Entry status: draft
- Themes: identity, academic-life
- Character notes sections

### 6.3 Edit Manuscript Metadata

```bash
# Edit manuscript entry
vim data/wiki/manuscript/entries/2024/2024-11-25.md

# Add to "Notes" section:
# Key entry for Chapter 3. Captures turning point in thesis journey.
# Expand café conversation for manuscript version.

# Add to "Character Notes":
# Ana Sofía: wisdom figure, catalyst for realization

# Import manuscript edits
plm import-wiki manuscript-all

# Verify
metadb query show 2024-11-25 | grep -A5 "manuscript"
```

**Expected:** Manuscript notes imported to database

---

## NLP & Analysis Testing

**Goal:** Test automated text analysis (optional, requires dependencies)

### 7.1 Check NLP Status

```bash
nlp status
```

**Expected:** Shows available analysis levels

### 7.2 Test Level 2 (spaCy) - If Available

```bash
# Analyze entry
nlp analyze 2024-11-25 --level 2
```

**Expected:** Entity extraction:

- People: Ana Sofía
- Locations: Montreal, McGill
- Themes detected

### 7.3 Test Level 4 (LLM) - If API Keys Set

```bash
# Analyze with Claude (if API key set)
nlp analyze 2024-11-25 --level 4 --provider claude

# Analyze for manuscript
nlp analyze 2024-11-25 --level 4 --manuscript
```

**Expected:** Detailed analysis with themes, mood, manuscript potential

---

## PDF Generation Testing

**Goal:** Test PDF compilation

### 8.1 Build Year PDF

```bash
# Build PDF for 2024
plm build-pdf 2024

# Check output
ls -la data/journal/content/pdf/
```

**Expected:** Two PDFs generated:

- `2024.pdf` (clean reading version)
- `2024-notes.pdf` (annotated version with line numbers)

### 8.2 Verify PDF Contents

Open PDFs and check:

- Title page
- Table of contents
- Entry formatting
- Epigraphs (if any)
- Line numbers (notes version only)
- LaTeX formatting

---

## Batch Operations & Integration Testing

**Goal:** Test complete pipeline end-to-end

### 9.1 Run Complete Pipeline

```bash
# Run everything for 2024
plm run-all --year 2024
```

**Expected:** Executes in order:

1. Inbox processing
2. Conversion
3. Database sync
4. Wiki export
5. PDF build

### 9.2 Test Incremental Updates

Add another test entry and verify incremental processing:

```bash
# Create second test entry
cat > data/journal/inbox/test-entry-2.txt << 'EOF'
Tuesday, November 26, 2024

Follow-up meeting with Ana at the library. Made significant progress on Chapter 3.

Word count: 20
EOF

# Run pipeline
plm inbox && plm convert && plm import-metadata

# Verify only new entry processed
metadb query show 2024-11-26
```

**Expected:** Only new entry processed (hash-based change detection)

### 9.3 Test Validation Suite

```bash
# Run all validators
validate wiki check
validate db all
validate md all
validate consistency all
```

**Expected:** All validations pass

---

## Database Management Testing

**Goal:** Test backup, restore, and maintenance

### 10.1 Test Backup

```bash
# Create backup
metadb backup --suffix "test-complete"

# List backups
metadb backups
```

**Expected:** Backup created with timestamp

### 10.2 Test Database Queries

```bash
# Query years
metadb query years

# Query months
metadb query months 2024

# Show specific entry
metadb query show 2024-11-25
```

**Expected:** Accurate query results

### 10.3 Test Health & Optimization

```bash
# Health check
metadb health

# Optimize database
metadb optimize

# Check stats
metadb stats --verbose
```

**Expected:** Database healthy, optimizations complete

### 10.4 Test Restore (Destructive - Use Caution!)

```bash
# Backup current state
metadb backup --suffix "before-restore-test"

# List available backups
metadb backups

# Restore from earlier backup
metadb restore data/backups/palimpsest_YYYYMMDD_HHMMSS_test-complete.db

# Verify restoration
metadb stats
```

**Expected:** Database restored to backup state

---

## Conflict Resolution & Sync Testing

**Goal:** Test sync state management and conflict handling

### 11.1 Check Sync Status

```bash
# View sync state
metadb sync status

# View stats
metadb sync stats
```

**Expected:** Shows sync timestamps and states

### 11.2 Create Sync Conflict (Advanced)

```bash
# Edit same field in markdown and wiki
vim data/journal/content/md/2024/2024-11-25.md  # Edit notes field
vim data/wiki/entries/2024/2024-11-25.md        # Edit notes field differently

# Sync both
plm import-metadata
plm import-wiki entries

# Check conflicts
metadb sync conflicts
```

**Expected:** Conflict detected, resolution workflow presented

### 11.3 Test Tombstone Management

```bash
# List tombstones
metadb tombstone list

# View stats
metadb tombstone stats

# Cleanup old tombstones (if any)
metadb tombstone cleanup --days 30
```

**Expected:** Tombstone tracking working

---

## Export Testing

**Goal:** Test data export capabilities

### 12.1 Export to CSV

```bash
# Export all tables
metadb export csv data/exports/

# Check output
ls -la data/exports/
head data/exports/entries.csv
```

**Expected:** CSV files for all tables

### 12.2 Export to JSON

```bash
# Export complete database
metadb export json data/exports/palimpsest-export.json

# Check file
cat data/exports/palimpsest-export.json | jq '.entries | length'
```

**Expected:** Complete JSON export

---

## Neovim Integration Testing

**Goal:** Test Neovim plugin (if using)

### 13.1 Verify Plugin Installation

```vim
:PalimpsestIndex
```

**Expected:** Opens wiki homepage

### 13.2 Test Browse Commands

```vim
:PalimpsestBrowse people
:PalimpsestBrowse entries
:PalimpsestQuickAccess
```

**Expected:** FZF picker opens with wiki files

### 13.3 Test Search Commands

```vim
:PalimpsestSearch all "thesis"
```

**Expected:** Search results in FZF

---

## Stress Testing

**Goal:** Test with larger datasets

### 14.1 Create Bulk Test Data

Create a script to generate multiple test entries:

```bash
# Create 10 test entries
for i in {1..10}; do
    date=$(date -d "2024-11-$((15+i))" +%Y-%m-%d)
    cat > "data/journal/inbox/test-$i.txt" <<EOF
$(date -d "$date" +"%A, %B %d, %Y")

Test entry $i. Working on thesis with various people and visiting Montreal locations.

Word count: 15
EOF
done
```

### 14.2 Process Bulk Data

```bash
# Process all
plm inbox && plm convert && plm import-metadata

# Verify
metadb query months 2024
```

**Expected:** All entries processed

### 14.3 Test Bulk Operations

```bash
# Export all to wiki
plm export-wiki all

# Rebuild search index
jsearch index rebuild

# Generate statistics
metadb stats --verbose
```

**Expected:** System handles bulk operations smoothly

---

## Error Handling & Edge Cases

**Goal:** Test system resilience

### 15.1 Test Invalid YAML

Create entry with malformed YAML:

```bash
cat > data/journal/content/md/2024/2024-11-30.md << 'EOF'
---
date: 2024-11-30
people:
  - Invalid [syntax
---

Test invalid YAML
EOF

# Try to sync
plm import-metadata
```

**Expected:** Clear error message, other entries still processed

### 15.2 Test Missing Dependencies

```bash
# Try to use NLP without installing
nlp analyze 2024-11-25 --level 2
```

**Expected:** Helpful error message with installation instructions

### 15.3 Test Empty Database Operations

```bash
# Try operations on fresh database
metadb reset --yes
metadb init

# Query empty database
metadb stats
jsearch query "anything"
```

**Expected:** Graceful handling of empty state

---

## Recommended Testing Order

1. **Start Simple:** Environment setup + basic pipeline with 1 entry
2. **Add Complexity:** Rich metadata + wiki system
3. **Test Queries:** Search functionality
4. **Advanced Features:** Poems, manuscript, NLP
5. **End-to-End:** PDF + complete pipeline
6. **Maintenance:** Backup, restore, optimization
7. **Edge Cases:** Conflicts, errors, stress testing

---

## Tips for Testing

### Before You Start

1. **Backup your real data** before any testing:

   ```bash
   metadb backup --suffix "before-testing"
   ```

2. **Consider using a separate testing environment:**

   ```bash
   # Copy entire project to test directory
   cp -r ~/Documents/palimpsest ~/Documents/palimpsest-test
   cd ~/Documents/palimpsest-test
   ```

3. **Track your progress** using the checklist above

### During Testing

- **Document issues** as you encounter them
- **Take notes** on unexpected behavior
- **Save command outputs** for troubleshooting
- **Test incrementally** - don't skip phases

### After Testing

- **Review what worked** and what didn't
- **Update documentation** based on findings
- **Consider automating** frequently-run test scenarios
- **Restore from backup** if needed:
  ```bash
  metadb restore data/backups/palimpsest_YYYYMMDD_HHMMSS_before-testing.db
  ```

---

## Common Issues & Solutions

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
plm import-metadata  # Re-sync from markdown
```

### "Text analysis not working"

```bash
nlp status  # Check what's available
# Install missing dependencies based on output
```

### "Slow database queries"

```bash
metadb optimize
jsearch index rebuild
```

---

## Next Steps After Testing

Once you've completed testing:

1. **Review all checkboxes** - identify any gaps
2. **Document your workflow** - what works best for your use case
3. **Set up automation** - cron jobs for backups, etc.
4. **Configure Neovim integration** - if using
5. **Start using the system** with real journal entries!

---

## Support & Resources

- **User Guides:** `docs/user-guides/`
- **Technical Docs:** `docs/dev-guides/`
- **Architecture:** `docs/dev-guides/architecture/`
- **Command Reference:** `docs/user-guides/command-reference.md`
- **Wiki Guide:** `docs/user-guides/sql-wiki-guide.md`

For help with specific commands:

```bash
plm --help
metadb --help
validate --help
jsearch --help
nlp --help
```

---

**Happy Testing!**
