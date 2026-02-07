# Vimwiki Generation System

Generate navigable vimwiki pages from the Palimpsest database for
browsing and editing journal metadata within Neovim.

## Purpose

The wiki system provides a structured, hyperlinked view of the journal
database as vimwiki pages. Journal wiki pages are read-only (regenerated
from DB on demand). Manuscript wiki pages support bidirectional editing.

## Template Engine

Jinja2 templates render SQLAlchemy ORM objects directly into vimwiki
markup. Custom filters handle wiki link formatting (`[[Entity Name]]`),
date formatting, and list rendering.

```
dev/wiki/
├── __init__.py          # Public API (WikiRenderer, WikiExporter)
├── renderer.py          # Jinja2 template rendering engine
├── exporter.py          # Database -> wiki generation orchestrator
├── configs.py           # Entity export configurations
├── filters.py           # Custom Jinja2 filters
└── templates/
    ├── entry.jinja2     # Entry wiki page
    ├── person.jinja2    # Person page
    ├── city.jinja2      # City page
    ├── location.jinja2  # Location page
    ├── event.jinja2     # Event page
    ├── tag.jinja2       # Tag page
    ├── theme.jinja2     # Theme page
    ├── poem.jinja2      # Poem page
    ├── reference.jinja2 # Reference page
    └── indexes/         # Index page templates
```

## Entity Types for Wiki Pages

Each entity type gets its own wiki page template:

- **Entry**: Date-based pages with people, locations, scenes, events,
  threads, tags, themes, references
- **Person**: Name, relation type, entries mentioned in, character
  mappings
- **Location**: Name, city, entries mentioned in
- **Event**: Name, linked scenes and entries
- **Tag/Theme/Arc**: Name, linked entries
- **Poem**: Content, versions, linked entries
- **Reference**: Content, source, mode, linked entry

## Directory Structure

```
data/wiki/
├── index.wiki           # Main index with links to all sections
├── entries/
│   └── YYYY/
│       └── YYYY-MM-DD.wiki
├── people/
│   └── {slug}.wiki
├── locations/
│   └── {city}/
│       └── {location}.wiki
├── events/
│   └── {slug}.wiki
├── inventory/           # Tags, themes, arcs index pages
├── snippets/            # Poem and reference pages
└── manuscript/          # Manuscript chapter/character pages
```

## Index Pages

- **Main index**: Links to all section indexes
- **People index**: Alphabetical list with relation types
- **Location index**: Grouped by city
- **Entry index**: Grouped by year/month
- **Event index**: Chronological list
- **Tag/Theme cloud**: Frequency-sorted

## CLI Integration

```bash
# Generate all wiki pages
plm wiki generate

# Generate specific entity type
plm wiki generate --type people

# Generate single entry
plm wiki generate --entry 2024-01-15
```

## Data Flow

- **Journal**: DB -> Wiki (one-way, regenerated on demand)
- **Manuscript**: Wiki <-> DB (bidirectional, wiki edits sync back)

The wiki is a presentation layer. The database is the source of truth
for journal metadata. Manuscript wiki pages support manual editing,
with a sync mechanism to push changes back to the database.

## Neovim Plugin Integration

The `dev/lua/palimpsest/` plugin provides:

- `:PalimpsestWiki` - Generate/regenerate wiki pages
- `:PalimpsestSync` - Sync manuscript wiki edits back to DB
- Navigation keybindings for jumping between wiki pages
- Automatic wiki regeneration on database changes
