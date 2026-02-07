# Vimwiki Generation System

Generate navigable wiki pages from the Palimpsest database for
browsing journal metadata and editing manuscript structure within Neovim.

## Purpose

The wiki system provides a structured, hyperlinked view of the database
as clean markdown pages, suitable for browser rendering (Quartz or similar).

- **Journal pages**: Read-only, regenerated from DB on demand
- **Manuscript pages**: Bidirectional — user edits wiki, syncs back to DB

## Architecture Overview

### Data Flow

```
                    ┌─────────────┐
                    │   Database   │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            │            ▼
     ┌────────────┐        │   ┌────────────────┐
     │  Journal    │        │   │  Manuscript     │
     │  Wiki Pages │        │   │  Wiki Pages     │
     │  (read-only)│        │   │  (editable)     │
     └────────────┘        │   └───────┬────────┘
                           │           │
                           │     ┌─────▼─────┐
                           │     │  Validate  │
                           │     │  (linter)  │
                           │     └─────┬─────┘
                           │           │
                           │     ┌─────▼─────┐
                           │     │   Sync     │
                           │     │  (ingest)  │
                           │     └─────┬─────┘
                           │           │
                           └───────────┘
```

- **Journal**: DB → Wiki (one-way generation)
- **Manuscript**: DB → Wiki → User edits → Validate → Sync → DB → Regenerate

### Round-Trip Cycle

The manuscript workflow follows a read-edit-sync-regenerate loop:

1. **Generate**: DB renders wiki pages via Jinja2 templates
2. **Edit**: User modifies wiki pages freely in Neovim
3. **Validate**: Linter checks edits on save (async, advisory)
4. **Sync**: On explicit user command, validated pages are ingested into DB
5. **Regenerate**: DB re-renders pages, normalizing content and adding
   computed data (backlinks, cross-references, status badges)

Every piece of user-written content on a wiki page maps to a DB field.
Nothing is lost in the round-trip — the user's text passes through
ingest before generation overwrites the file.

### Regeneration Safety

Sync only writes pages where DB state diverges from what is on disk:

1. Parse edited wiki pages, update DB
2. Render all pages from DB into memory
3. Compare rendered output against existing files
4. Only overwrite pages that actually differ

This prevents clobbering in-progress work on pages the user hasn't synced.

## Three-Layer Validation Architecture

### 1. Linter (Neovim, async on save)

Advisory diagnostics with line-level feedback. Runs asynchronously on
`BufWritePost` (or debounced on `TextChanged` for real-time feedback).
Outputs structured diagnostics rendered as:

- Inline virtual text
- Gutter signs
- Quickfix list population

Backed by `plm lint <filepath>`, which outputs JSON diagnostics
(file, line, column, severity, message).

Example diagnostics:
- "Character `[[Claara]]` not found — did you mean `[[Clara]]`?"
- "Invalid status value `Draft` — expected `draft`"
- "Scene link `[[Morning Walk]]` does not exist"

### 2. Validator (CLI, pre-sync gate)

Strict pass/fail check that blocks DB ingestion. Called internally
by the sync command. Shares validation logic with the linter —
same rules, different output format (pass/fail vs. diagnostics).

### 3. Sync (CLI, on demand)

Parses validated wiki pages into DB, then regenerates. Never runs
silently or automatically — always triggered explicitly by the user.

```bash
plm sync manuscript              # Full: ingest + regenerate
plm sync manuscript --ingest     # Wiki → DB only
plm sync manuscript --generate   # DB → Wiki only
```

### Unified Validation Entry Point

The three-layer validation architecture is not manuscript-specific.
It extends to **all** Palimpsest file types. Existing validators
(`dev/validators/`) for frontmatter, markdown, metadata YAML, and
schema already perform the validation logic — what's new is wiring
them into a single CLI entry point with structured, line-level
diagnostic output suitable for Neovim's diagnostic system.

This means journal markdown and narrative analysis YAML files get
the same inline linting experience as manuscript wiki pages: save
a file, see errors as gutter signs and virtual text, fix at your
own pace.

The linter routes to the appropriate validator based on file type:

| File location | Validator | Existing code |
|---------------|-----------|---------------|
| `data/journal/content/md/` | Frontmatter + markdown validators | `dev/validators/frontmatter.py`, `dev/validators/md.py` |
| `data/narrative_analysis/` | Metadata YAML validator | `dev/validators/metadata_yaml.py` |
| `data/wiki/manuscript/` | Manuscript wiki validator | New — `dev/wiki/validator.py` |

All validators are accessible through a single CLI entry point:
`plm lint <filepath>`. The Neovim plugin calls this and renders
the output as native diagnostics. The existing validators need
adaptation to emit structured diagnostics (file, line, column,
severity, message) rather than just pass/fail results.

## Wiki Page Design

Wiki pages are clean markdown — no YAML frontmatter, no hidden metadata.
Structure is conveyed through consistent heading conventions and
wiki-style links (`[[Entity Name]]`).

### Manuscript Chapter Page Example

```markdown
# The Gray Fence

**Part:** I — Arrival
**Type:** prose | **Status:** draft

## Synopsis
User writes a brief summary here.

## Scenes
- [[Morning at the Fence]] (journaled, included)
- [[The Dog Walker]] (invented, fragment)

## Characters
- [[Sofia]] — protagonist, narrator
- [[Clara]] — mentioned

## Arcs
- [[The Long Wanting]]

## Sources
Journal entries that feed this chapter.
- [[2024-11-08]] — Scene 3 (the fence encounter)
- [[2025-01-15]] — Whole entry

## Notes
Free-form user notes about this chapter.

## References
- *Important Book* by Author (thematic)
```

Parsing relies on heading conventions (`## Scenes`, `## Characters`, etc.)
and link patterns (`[[...]]`) rather than frontmatter or special syntax.

## Template Engine

Jinja2 templates render SQLAlchemy ORM objects into clean markdown.
Custom filters handle wiki link formatting, date formatting, and
list rendering.

```
dev/wiki/
├── __init__.py          # Public API (WikiRenderer, WikiExporter)
├── renderer.py          # Jinja2 template rendering engine
├── exporter.py          # Database -> wiki generation orchestrator
├── parser.py            # Wiki -> database ingestion (manuscript)
├── validator.py         # Wiki page validation / linting
├── configs.py           # Entity export configurations
├── filters.py           # Custom Jinja2 filters
└── templates/
    ├── journal/
    │   ├── entry.jinja2
    │   ├── person.jinja2
    │   ├── location.jinja2
    │   ├── event.jinja2
    │   ├── tag.jinja2
    │   ├── theme.jinja2
    │   ├── poem.jinja2
    │   └── reference.jinja2
    ├── manuscript/
    │   ├── chapter.jinja2
    │   ├── character.jinja2
    │   ├── scene.jinja2
    │   └── part.jinja2
    └── indexes/
        ├── main.jinja2
        ├── people.jinja2
        ├── locations.jinja2
        └── entries.jinja2
```

## Entity Types

### Journal (read-only)

- **Entry**: Date-based pages with people, locations, scenes, events,
  threads, tags, themes, references
- **Person**: Name, relation type, entries mentioned in, character mappings
- **Location**: Name, city, entries mentioned in
- **Event**: Name, linked scenes and entries
- **Tag/Theme/Arc**: Name, linked entries
- **Poem**: Content, versions, linked entries
- **Reference**: Content, source, mode, linked entry

### Manuscript (editable)

- **Chapter**: Title, part, type, status, synopsis, scenes, characters,
  arcs, sources, notes, references
- **Character**: Name, role, narrator flag, chapters, person mappings
- **ManuscriptScene**: Name, origin, status, sources, chapter
- **Part**: Number, title, chapters

## Directory Structure

```
data/wiki/
├── index.md                 # Main index with links to all sections
├── journal/
│   ├── entries/
│   │   └── YYYY/
│   │       └── YYYY-MM-DD.md
│   ├── people/
│   │   └── {slug}.md
│   ├── locations/
│   │   └── {city}/
│   │       └── {location}.md
│   ├── events/
│   │   └── {slug}.md
│   ├── tags/
│   │   └── {name}.md
│   ├── themes/
│   │   └── {name}.md
│   ├── poems/
│   │   └── {slug}.md
│   └── references/
│       └── {slug}.md
└── manuscript/
    ├── chapters/
    │   └── {slug}.md
    ├── characters/
    │   └── {slug}.md
    ├── scenes/
    │   └── {slug}.md
    └── parts/
        └── {number}-{slug}.md
```

## Index Pages

- **Main index**: Links to all section indexes
- **People index**: Alphabetical list with relation types
- **Location index**: Grouped by city
- **Entry index**: Grouped by year/month
- **Event index**: Chronological list
- **Tag/Theme cloud**: Frequency-sorted
- **Manuscript index**: Parts → chapters → scenes hierarchy

## CLI Integration

```bash
# Generate all wiki pages
plm wiki generate

# Generate specific section
plm wiki generate --section journal
plm wiki generate --section manuscript

# Generate specific entity type
plm wiki generate --type people

# Lint a wiki page (structured diagnostics)
plm lint <filepath>

# Sync manuscript (ingest + regenerate)
plm sync manuscript

# Validate before sync (dry run)
plm validate manuscript
```

## Neovim Plugin Integration

The Neovim plugin (`palimpsest.nvim` or similar) provides:

### Commands

- `:PalimpsestSync` — Sync manuscript wiki edits back to DB, regenerate
- `:PalimpsestGenerate` — Regenerate wiki pages from DB
- `:PalimpsestStatus` — Show dirty files, lint errors, last sync time
- `:PalimpsestLint` — Run linter on current buffer

### Linter Integration

Hooks into Neovim's diagnostic system (via `nvim-lint`, ALE, or custom
`vim.diagnostic` provider). Runs `plm lint` asynchronously on `BufWritePost`.
Diagnostics appear as inline virtual text and gutter signs.

File type routing:
- Journal markdown → frontmatter/markdown validators
- Narrative analysis YAML → metadata YAML validator
- Manuscript wiki pages → manuscript wiki validator

### Save/Quit Behavior

- **`BufWritePost`**: Triggers async lint, tracks file as "dirty" (edited
  since last sync)
- **`VimLeavePre`**: Checks dirty set. If validated files haven't been
  synced, prompts: "N manuscript pages changed since last sync.
  Sync now? [y/n/q]". Files with lint errors get a warning only.

### Safety

- Sync is always explicit — never runs silently or automatically
- Sync refuses to ingest pages with validation errors
- Sync warns/blocks if any manuscript buffers have unsaved changes
  (`BufModified` check)
- Status line indicator shows dirty page count and lint error count
