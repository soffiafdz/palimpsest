# Getting Started with Palimpsest

Welcome to Palimpsest! This guide will help you understand what Palimpsest is, how it works, and get you started with your first workflow.

## What is Palimpsest?

Palimpsest is a comprehensive system for managing structured journal entries that combines two powerful layers:

1. **Markdown + YAML**: Rich metadata in your markdown journal files
2. **SQL Database**: Structured storage and querying of your entries

### The Problem It Solves

Traditional journaling is either:
- **Unstructured**: Easy to write but hard to search, analyze, or cross-reference
- **Database-driven**: Powerful queries but tedious data entry and poor writing experience

Palimpsest gives you the best of both worlds:
- Write naturally in markdown with your favorite editor
- Add metadata as YAML frontmatter (dates, people, locations, tags, etc.)
- Import metadata to a SQL database for powerful queries and analysis
- Search with full-text search and complex filtering

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
- **Enables powerful queries** through the `jsearch` command

You rarely interact with the database directly - it's managed automatically through commands.

→ Learn more: [Command Reference](reference/commands.md)

### 3. Metadata YAML Files

For narrative analysis, you can create separate metadata YAML files that contain detailed analysis:
- Scenes and events
- Character arcs
- Themes and motifs
- Threads connecting moments across time

These are imported once to the database via `plm import-metadata`.

→ Learn more: [Metadata Field Reference](reference/metadata-field-reference.md)

## Quick Setup

### Prerequisites

- Python 3.10+
- Git (for version control)
- Optional: Neovim (for editor integration)

### Installation

```bash
# Install Palimpsest
pip install -e .

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
├── inbox/              # New 750words exports
├── data/
│   ├── journal/
│   │   ├── sources/txt/    # Formatted text files
│   │   └── content/md/     # Markdown entries
│   ├── metadata/           # Narrative analysis YAML
│   └── palimpsest.db       # SQL database
```

## Your First Workflow

Let's create your first journal entry and see how Palimpsest works.

### Step 1: Create a Journal Entry

Create a file `data/journal/content/md/2024/2024-01-15.md`:

```markdown
---
date: 2024-01-15
word_count: 150
reading_time: 0.75
tags: [first-entry, reflection]
city: Montreal
epigraph: "A journey of a thousand miles begins with a single step."
---

## Wednesday, January 15, 2024

Today I'm setting up Palimpsest for the first time. I'm excited to see
how this structured journaling approach will help me track patterns and
connections in my life.

I'm writing this from Montreal, where I've been thinking a lot about
new beginnings.
```

### Step 2: Create Metadata (Optional)

For deeper narrative analysis, create `data/metadata/2024/2024-01-15.yaml`:

```yaml
date: 2024-01-15
summary: First Palimpsest entry reflecting on new beginnings

scenes:
  - name: "Setting Up"
    description: "Configuring Palimpsest for first use"
    date: 2024-01-15

tags: [first-entry, reflection]
themes: [new-beginnings, tools]
```

### Step 3: Import to Database

```bash
# Import metadata to database
plm import-metadata

# Check what was created
metadb stats
```

You should see:
- 1 entry
- 1 city (Montreal)
- 2 tags (first-entry, reflection)
- 1 scene

### Step 4: Search Your Entries

```bash
# Search for entries mentioning Montreal
jsearch query "Montreal"

# Search with filters
jsearch query "reflection" city:Montreal tag:first-entry
```

### Step 5: Export Database (Optional)

```bash
# Export to JSON for version control
plm export-json

# Creates data/exports/*.json files
```

## Navigation to Specialized Guides

Now that you understand the basics, explore these guides based on your needs:

### Daily Journaling
- [Command Reference](reference/commands.md) - Essential commands for daily use
- [Metadata Field Reference](reference/metadata-field-reference.md) - All available fields
- [Metadata Examples](reference/metadata-examples.md) - Complex entry examples

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
     - Alice Johnson
     - "@Bob (Robert Johnson)"  # Alias format
   ```

2. **Name variants create different people**: "Bob Smith" and "Robert Smith" are different people
   - Use the alias syntax to link them

3. **Entry date is auto-included**: Don't manually add entry date to scenes/threads

4. **Multiple cities need array format**:
   ```yaml
   city: Montreal  # Single city (string)

   cities:         # Multiple cities (array)
     - Montreal
     - Toronto
   ```

5. **References need content**:
   ```yaml
   references:
     - content: "The quote text"
       source:
         title: "Book Title"
         type: book
         author: "Author Name"
   ```

→ Full list: [Metadata Field Reference](reference/metadata-field-reference.md#common-gotchas)

## Essential Commands Quick Reference

```bash
# Daily workflow
plm inbox               # Process 750words exports
plm convert             # Convert text to markdown
plm import-metadata     # Import metadata to database

# Search
jsearch query "search term"
jsearch query "therapy" person:alice tag:work in:2024

# Database management
metadb stats            # Show database statistics
metadb backup           # Create backup
metadb health           # Check database health

# Validation
validate db all         # Validate database
validate consistency all # Check consistency

# Full pipeline
plm run-all --year 2024
```

→ Complete reference: [Command Reference](reference/commands.md)

## Success Metrics

You'll know Palimpsest is working when:

1. **Inbox entries process cleanly** - `plm inbox` validates and moves files
2. **Database stays healthy** - `metadb stats` shows expected counts
3. **Searches work** - `jsearch` finds your entries
4. **Validation passes** - No errors from `validate db all`

## Next Steps

1. **Set up your daily workflow**: Create entries, import metadata, search
2. **Add rich metadata**: Explore [all available fields](reference/metadata-field-reference.md)
3. **Integrate with your editor**: Try the [Neovim Integration](integrations/neovim.md)
4. **Explore advanced features**: Full-text search, PDF export, database queries

## Troubleshooting

- **Validation errors**: Check [Metadata Field Reference](reference/metadata-field-reference.md)
- **Command issues**: Check [Command Reference](reference/commands.md)
- **Database issues**: Run `metadb health --fix`

Welcome to Palimpsest! Happy journaling! 📔
