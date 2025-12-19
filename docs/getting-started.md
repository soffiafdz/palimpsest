# Getting Started with Palimpsest

Welcome to Palimpsest! This guide will help you understand what Palimpsest is, how it works, and get you started with your first workflow.

## What is Palimpsest?

Palimpsest is a comprehensive system for managing structured journal entries that combines three powerful layers:

1. **YAML Frontmatter**: Rich metadata in your markdown journal files
2. **SQL Database**: Structured storage and querying of your entries
3. **Vimwiki Interface**: Browse and edit your metadata as interconnected wiki pages

### The Problem It Solves

Traditional journaling is either:
- **Unstructured**: Easy to write but hard to search, analyze, or cross-reference
- **Database-driven**: Powerful queries but tedious data entry and poor writing experience

Palimpsest gives you the best of both worlds:
- Write naturally in markdown with your favorite editor
- Add metadata as YAML frontmatter (dates, people, locations, tags, etc.)
- Automatically sync to a SQL database for powerful queries and analysis
- Browse and edit through an auto-generated vimwiki
- Track changes across multiple machines with conflict detection

## Core Concepts

### 1. YAML Frontmatter

Each journal entry contains YAML metadata at the top:

```yaml
---
date: 2024-01-15
tags: [reflection, work]
people:
  - Alice Johnson
  - Bob Smith
city: Montreal
epigraph: "The only way out is through."
---

Your journal entry content here...
```

This metadata makes your entries:
- **Searchable**: Find all entries mentioning a person or location
- **Analyzable**: Track patterns over time
- **Connected**: See relationships between entries, people, and places

→ Learn more: [Metadata Field Reference](reference/metadata-field-reference.md)

### 2. SQL Database

Behind the scenes, Palimpsest maintains a SQL database that:
- **Stores** all your metadata in structured tables (entries, people, locations, events, etc.)
- **Validates** your YAML to catch errors early
- **Tracks changes** with hash-based sync state for multi-machine workflows
- **Enables powerful queries** through the `jsearch` command

You rarely interact with the database directly - it's managed automatically through commands.

→ Learn more: [Command Reference](reference/commands.md)

### 3. Vimwiki Interface

Palimpsest generates a complete vimwiki from your database:

```
wiki/
├── entries/           # All your journal entries by date
├── people/            # Person pages with backlinks to entries
├── locations/         # Location pages with related entries
├── cities/            # City pages
├── events/            # Event pages
├── tags/              # Tag index pages
└── ...
```

Each wiki page shows:
- **Entity details**: Names, dates, metadata
- **Backlinks**: Which entries mention this person/location/tag
- **Editable notes**: Add wiki notes that sync back to the database

→ Learn more: [Wiki Field Reference](reference/wiki-fields.md)

### 4. Bidirectional Sync

Palimpsest maintains three synchronization paths:

```
YAML Files ↔ SQL Database → Vimwiki
              ↑_______________|
           (notes only)
```

- **YAML ↔ SQL**: Fully bidirectional - changes flow both ways
- **SQL → Wiki**: One-way export - wiki pages regenerate from database
- **Wiki → SQL**: One-way import - wiki notes sync back to database

This allows you to:
- Edit your journal files directly
- Or edit through the wiki interface
- Changes propagate automatically

→ Learn more: [Synchronization Guide](guides/synchronization.md)

### 5. Conflict Detection

When working across multiple machines, Palimpsest:
- **Tracks sync state** with content hashes for every entry and entity
- **Detects conflicts** when the same entity is modified on different machines
- **Uses last-write-wins** resolution (configurable)
- **Preserves tombstones** to track deletions across machines

→ Learn more: [Conflict Resolution](guides/conflict-resolution.md)

## Quick Setup

### Prerequisites

- Python 3.10+
- Git (for version control and multi-machine sync)
- Optional: Neovim (for editor integration)

### Installation

```bash
# Install Palimpsest
pip install palimpsest  # (or your installation method)

# Initialize the database
metadb init

# Verify installation
plm --help
metadb --help
validate --help
jsearch --help
```

### Directory Structure

Palimpsest expects a specific directory structure:

```
your-journal/
├── inbox/              # New entries go here
├── data/               # Processed YAML entries
│   ├── entries/
│   ├── people/
│   ├── locations/
│   └── ...
├── wiki/               # Generated vimwiki
└── .palimpsest.db      # SQL database (auto-created)
```

## Your First Workflow

Let's create your first journal entry and see how Palimpsest works.

### Step 1: Create a Journal Entry

Create a file `inbox/2024-01-15.md`:

```markdown
---
date: 2024-01-15
tags: [first-entry, reflection]
city: Montreal
epigraph: "A journey of a thousand miles begins with a single step."
---

# Getting Started

Today I'm setting up Palimpsest for the first time. I'm excited to see
how this structured journaling approach will help me track patterns and
connections in my life.

I'm writing this from Montreal, where I've been thinking a lot about
new beginnings.
```

### Step 2: Process the Entry

```bash
# Convert inbox entry to structured data
plm inbox

# This creates data/entries/2024-01-15.md with validated YAML
```

### Step 3: Sync to Database

```bash
# Import all YAML files to SQL database
plm sync-db

# Check what was created
metadb stats
```

You should see:
- 1 entry
- 1 city (Montreal)
- 2 tags (first-entry, reflection)

### Step 4: Export to Wiki

```bash
# Generate vimwiki from database
plm export-wiki

# Browse the wiki
cd wiki
ls
```

You'll see:
- `wiki/entries/2024-01-15.md` - Your entry in wiki format
- `wiki/cities/montreal.md` - City page with backlink to your entry
- `wiki/tags/first-entry.md` - Tag page with backlinks

### Step 5: Edit Wiki Notes

Open `wiki/cities/montreal.md` and add some notes:

```markdown
# Montreal

## Metadata
- **Type**: City
- **Entries**: 1

## Entries Mentioning Montreal
- [2024-01-15](../entries/2024-01-15.md)

## Notes
Montreal is the largest city in Quebec. I lived here during 2024 and
found it to be incredibly vibrant and multicultural.
```

### Step 6: Sync Wiki Notes Back

```bash
# Import wiki notes to database
plm import-wiki

# Export to wiki again (to verify)
plm export-wiki
```

Your Montreal notes are now stored in the database!

### Step 7: Search Your Entries

```bash
# Search for entries mentioning Montreal
jsearch Montreal

# Search with filters
jsearch --city Montreal --tag reflection
```

## Navigation to Specialized Guides

Now that you understand the basics, explore these guides based on your needs:

### Daily Journaling
- [Command Reference](reference/commands.md) - Essential commands for daily use
- [Metadata Quick Reference](reference/metadata-field-reference.md#quick-start) - Common field patterns

### Multi-Machine Setup
- [Synchronization Guide](guides/synchronization.md) - Working across laptop/desktop
- [Conflict Resolution](guides/conflict-resolution.md) - Handling concurrent edits

### Advanced Metadata
- [Metadata Field Reference](reference/metadata-field-reference.md) - All available fields
- [Metadata Examples](reference/metadata-examples.md) - Complex entry examples
- [Wiki Field Reference](reference/wiki-fields.md) - Understanding entity types

### Editor Integration
- [Neovim Integration](integrations/neovim.md) - Browse, search, and validate in Neovim

### Development
- [Development Overview](development/README.md) - Contributing to Palimpsest
- [Architecture](development/architecture.md) - System design and patterns

## Common Gotchas

Even experienced users run into these:

1. **@ prefix for aliases**: Use `@alias` syntax to mark alternative names
   ```yaml
   people:
     - name: Robert Johnson
       alias: "@Bob"  # Note the @ prefix
   ```

2. **Name variants create different people**: "Bob Smith" and "Robert Smith" are different people
   - Use the `alias` field to link them

3. **Entry date is auto-included in dates**: Don't manually add entry date to `mentioned_dates`

4. **Multiple cities need dict format**:
   ```yaml
   city: Montreal  # Single city (string)

   cities:         # Multiple cities (dict)
     - name: Montreal
     - name: Toronto
   ```

5. **References need content OR description**:
   ```yaml
   references:
     - mode: direct
       type: quote
       content: "The quote text"  # Either content...

     - mode: paraphrase
       description: "Summary of the idea"  # ...or description
   ```

→ Full list: [Metadata Common Gotchas](reference/metadata-field-reference.md#common-gotchas)

## Essential Commands Quick Reference

```bash
# Daily workflow
plm inbox          # Process new entries
plm sync-db        # Sync to database
plm export-wiki    # Update wiki

# Validation
validate wiki      # Check wiki formatting
validate db-schema # Verify database schema
validate metadata  # Check YAML metadata

# Search
jsearch "search term"
jsearch --person "Alice" --tag work
jsearch --date-range 2024-01-01 2024-12-31

# Database management
metadb stats       # Show database statistics
metadb backup      # Create backup
metadb health      # Check sync state

# Full pipeline
plm run-all        # inbox + sync-db + export-wiki
```

→ Complete reference: [Command Reference](reference/commands.md)

## Success Metrics

You'll know Palimpsest is working when:

1. **Inbox entries process cleanly** - `plm inbox` validates and moves files to `data/`
2. **Database stays in sync** - `metadb stats` shows expected counts
3. **Wiki generates successfully** - `plm export-wiki` creates wiki pages
4. **Searches work** - `jsearch` finds your entries
5. **Multi-machine sync is clean** - No unexpected conflicts (check `metadb health`)

## Next Steps

1. **Set up your daily workflow**: Create entries, sync to database, browse wiki
2. **Add rich metadata**: Explore [all available fields](reference/metadata-field-reference.md)
3. **Set up multi-machine sync**: Follow the [Synchronization Guide](guides/synchronization.md)
4. **Integrate with your editor**: Try the [Neovim Integration](integrations/neovim.md)
5. **Explore advanced features**: Manuscript wikis, NLP analysis, PDF export

## Troubleshooting

- **Validation errors**: Check [Metadata Common Gotchas](reference/metadata-field-reference.md#common-gotchas)
- **Sync conflicts**: See [Conflict Resolution](guides/conflict-resolution.md)
- **Wiki import failures**: Review [Wiki Field Reference](reference/wiki-fields.md)
- **Command issues**: Check [Command Reference](reference/commands.md)

Welcome to Palimpsest! Happy journaling! 📔
