# Vimwiki Generation System

Generate navigable wiki pages from the Palimpsest database for
browsing journal metadata and editing manuscript structure within Neovim.

## Purpose

The wiki system provides a structured, hyperlinked view of the database
as clean markdown pages rendered in Neovim with `[[wikilinks]]`, linting,
and sync commands.

Content types:
- **Journal pages**: Read-only, regenerated from DB on demand
- **Manuscript pages**: Bidirectional — user edits wiki, syncs back to DB

## Architecture Overview

### Data Flow

```
                      ┌─────────────┐
                      │   Database   │
                      └──────┬──────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
 ┌──────────────┐   ┌───────────────┐   ┌────────────────┐
 │ Journal Wiki  │   │ YAML Metadata │   │ Manuscript Wiki │
 │ (generated)   │   │ (per-entity)  │   │ (mixed)         │
 └──────┬───────┘   └───────┬───────┘   └───────┬────────┘
        │                   │                    │
        │            ┌──────▼───────┐     ┌──────▼───────┐
        │            │  Palimpsest  │     │   Validate   │
        │            │  nvim plugin │     │   (linter)   │
        │            │  (float edit)│     └──────┬───────┘
        │            └──────┬───────┘            │
        │                   │              ┌─────▼──────┐
        │                   └──────┐       │    Sync    │
        │                          │       │  (ingest)  │
        │                          │       └─────┬──────┘
        │                          │             │
        │                          └──────┬──────┘
        │                                 │
        └────────────┬────────────────────┘
                     ▼
            ┌──────────────┐
            │  data/wiki/  │
            │  (markdown)  │
            └──────────────┘
```

Content paths:

- **Journal wiki** (generated): DB → Jinja2 → wiki pages (read-only)
- **YAML metadata** (per-entity): DB → YAML files ↔ Palimpsest nvim
  plugin (floating window editing) → DB
- **Manuscript wiki** (generated dashboards): DB → Jinja2 → structural
  wiki pages (scenes, characters, arcs) with links to external draft files
- **Manuscript drafts** (external files): Prose lives at
  `data/manuscript/drafts/{slug}.md`, linked from chapter wiki pages

### Round-Trip Cycle

Two editing paths feed back into the database:

**YAML metadata path** (all manuscript entities + journal entities):

1. **Generate**: DB exports YAML metadata files
2. **Edit**: User opens `:PalimpsestEdit` → floating window with YAML
3. **Save**: YAML validated and ingested into DB on window close
4. **Regenerate**: DB re-renders wiki pages with updated metadata

**Draft prose path** (Chapter prose):

1. **Generate**: `:PalimpsestNew chapters` creates YAML metadata + draft
   file stub at `data/manuscript/drafts/{slug}.md`
2. **Edit**: User writes prose in the draft file (opened from chapter
   wiki page link or directly)
3. **Structural metadata**: Scenes, characters, arcs managed via YAML
   metadata (floating window editing)
4. **Regenerate**: Wiki pages regenerated from DB to reflect metadata
   changes (scene assignments, character additions, etc.)

### Regeneration Safety

Sync only writes pages where DB state diverges from what is on disk:

1. Import YAML metadata files, update DB entities
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

Backed by `plm wiki lint <filepath>`, which outputs JSON diagnostics
(file, line, column, severity, message).

Example diagnostics:
- "Character `[[Léaa]]` not found — did you mean `[[Léa]]`?"
- "Invalid status value `Draft` — expected `draft`"
- "Scene link `[[Morning Walk]]` does not exist"

### 2. Validator (CLI, pre-sync gate)

Strict pass/fail check that blocks DB ingestion. Called internally
by the sync command. Shares validation logic with the linter —
same rules, different output format (pass/fail vs. diagnostics).

### 3. Sync (CLI, on demand)

Imports YAML metadata into DB, then regenerates wiki pages. Never runs
silently or automatically — always triggered explicitly by the user.

```bash
plm wiki sync                    # Full: ingest + regenerate
plm wiki sync --ingest           # YAML metadata → DB only
plm wiki sync --generate         # DB → Wiki only
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
| `data/metadata/` | Metadata YAML validator | `dev/wiki/metadata.py` |
| `data/wiki/manuscript/` | Manuscript wiki validator | New — `dev/wiki/validator.py` |

All validators are accessible through a single CLI entry point:
`plm wiki lint <filepath>`. The Neovim plugin calls this and renders
the output as native diagnostics. The existing validators need
adaptation to emit structured diagnostics (file, line, column,
severity, message) rather than just pass/fail results.

## Wiki Page Design

Wiki pages are clean markdown with no user-facing YAML frontmatter.
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
- [[Léa]] — mentioned

## Sources
Journal entries that feed this chapter.
- [[2024-11-08]] — Scene 3 (the fence encounter)
- [[2025-01-15]] — Whole entry

## Notes
Free-form user notes about this chapter.

## References
- *Important Book* by Author (thematic)
```

Wiki pages use heading conventions (`## Scenes`, `## Characters`, etc.)
and link patterns (`[[...]]`) for readability. Structural metadata is
managed via YAML files, not parsed from the wiki markdown.

## Template Engine

Jinja2 templates render SQLAlchemy ORM objects into clean markdown.
Custom filters handle wiki link formatting, date formatting, and
list rendering.

```
dev/wiki/
├── __init__.py          # Public API
├── renderer.py          # Jinja2 template rendering engine
├── exporter.py          # Database → wiki generation orchestrator
├── validator.py         # Wiki page validation / linting
├── sync.py              # Manuscript sync (validate → YAML import → regenerate)
├── metadata.py          # YAML metadata export/import/validation
├── context.py           # Context builder for template rendering
├── configs.py           # Entity export configurations
├── filters.py           # Custom Jinja2 filters
├── rename.py            # Entity rename across DB and files
├── mdit_wikilink.py     # markdown-it-py wikilink plugin
└── templates/
    ├── journal/
    │   ├── entry.jinja2
    │   ├── person.jinja2
    │   ├── location.jinja2
    │   ├── city.jinja2
    │   ├── event.jinja2
    │   ├── arc.jinja2
    │   ├── tag.jinja2
    │   ├── theme.jinja2
    │   ├── motif.jinja2
    │   ├── poem.jinja2
    │   └── reference_source.jinja2
    ├── manuscript/
    │   ├── chapter.jinja2
    │   ├── character.jinja2
    │   ├── manuscript_scene.jinja2
    │   └── part.jinja2
    ├── indexes/
    │   ├── main.jinja2
    │   ├── manuscript.jinja2
    │   ├── entries.jinja2
    │   ├── people.jinja2
    │   ├── places.jinja2
    │   ├── events.jinja2
    │   ├── arcs.jinja2
    │   ├── tags.jinja2
    │   ├── themes.jinja2
    │   ├── motifs.jinja2
    │   ├── poems.jinja2
    │   └── references.jinja2
    └── macros/
        ├── entry_listing.jinja2
        └── thread_display.jinja2
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
plm wiki lint <filepath>

# Sync manuscript (ingest + regenerate)
plm wiki sync
```

## Neovim Plugin Integration

The Neovim plugin (`palimpsest.nvim` or similar) provides:

### Commands

- `:PalimpsestGenerate` — Regenerate wiki pages from DB
- `:PalimpsestLint` — Run linter on current buffer
- `:PalimpsestEdit` — Open entity metadata YAML in floating window
- `:PalimpsestEditCuration` — Open curation YAML in floating window
- `:PalimpsestNew` — Create a new entity from template
- `:PalimpsestAddSource` — Add source to manuscript scene (guided)
- `:PalimpsestAddBasedOn` — Add person mapping to character (guided)
- `:PalimpsestSetChapter` — Assign scene to chapter (guided)
- `:PalimpsestAddCharacter` — Add character to scene (guided)
- `:PalimpsestOpenSources` — Open draft file or journal entries in splits
- `:PalimpsestLinkToManuscript` — Link journal entity to manuscript
- `:PalimpsestRename` — Rename an entity across DB and files
- `:PalimpsestIndex` — Open wiki main index
- `:PalimpsestManuscriptIndex` — Open manuscript index
- `:PalimpsestBrowse` — Browse wiki pages via fzf
- `:PalimpsestSearch` — Search journal entries
- `:PalimpsestQuickAccess` — Quick access to common pages
- `:PalimpsestMetadataExport` — Export metadata for current entity
- `:PalimpsestValidateEntry` — Validate current journal entry
- `:PalimpsestValidateFrontmatter` — Validate frontmatter
- `:PalimpsestValidateMetadata` — Validate metadata YAML
- `:PalimpsestValidateLinks` — Validate wikilinks

### Linter Integration

Hooks into Neovim's diagnostic system (via `nvim-lint`, ALE, or custom
`vim.diagnostic` provider). Runs `plm wiki lint` asynchronously on `BufWritePost`.
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

## Resolved Design Questions

### Wiki Page Schema — RESOLVED

Detailed designs for all 27 page types documented in
`docs/development/wiki-page-designs.md`. Includes exact heading
conventions, parsing rules, zone breakdowns, and mockups for every
entity type. Key architectural decisions:

- **YAML + floating window** for all manuscript entities (Chapter,
  Character, ManuscriptScene, Part)
- **External draft files** for chapter prose at `data/manuscript/drafts/`
- **Sources and Based On** managed via guided nvim plugin commands
- **Journal entity metadata** in per-entity YAML files (People, Locations)
  or single files (Cities, Arcs)
- **22 Palimpsest nvim commands** with DB-backed autocomplete

### Template Design — RESOLVED

1. **Pre-computation layer:** Context builders (in exporter/orchestrator)
   query DB, compute aggregates (co-occurrence, frequency counts, arc
   grouping), pass prepared context dicts to templates. Templates are
   dumb renderers — no queries, no computation.

2. **One template per entity type:** Tier-based conditionals within single
   template (e.g., Person template checks `tier == "narrator"` /
   `"frequent"` / `"infrequent"`). Avoids duplicating shared logic
   across multiple templates.

3. **Reusable macros:** Shared patterns as Jinja2 macros in
   `templates/macros/`:
   - `entry_listing.jinja2` — Year → month → week hierarchy
   - `thread_display.jinja2` — Thread heading + dates + content + people

4. **Custom Jinja2 filters** (`dev/wiki/filters.py`):
   - `wikilink(name, display)` — `[[name]]` or `[[name|display]]`
   - `date_long(d)` — `Tuesday, November 8, 2024`
   - `date_range(start, end)` — `Nov 2024 – Jan 2025`
   - `mid_dot_join(items)` — `[[A]] · [[B]] · [[C]]`
   - `adaptive_list(items, threshold)` — inline or bulleted by count
   - `timeline_table(monthly_counts)` — full markdown table
   - `source_path(entity, wiki_root)` — relative path to source file
   - `entry_date_short(d)` — short date format for entry references
   - `entry_date_display(d)` — display format for entry dates
   - `month_display(d)` — month name display
   - `flexible_date_display(d)` — flexible date formatting
   - `thread_date_range(thread)` — thread date span display
   - `chunked_list(items, size)` — split list into chunks
   - `zpad(n)` — zero-padded number

5. **Empty section suppression:** Per-section `{% if data %}` blocks.
   No wrapping macro — explicit conditionals are more readable.

6. **Prose in external drafts:** Chapter prose lives in external draft
   files (`data/manuscript/drafts/{slug}.md`), linked from wiki pages.
   Short-form content (vignettes, poems) uses the Chapter `content` DB
   field. Scene descriptions stored in DB via YAML metadata.

7. **Clean markdown output:** Templates output clean markdown with no
   YAML frontmatter. Keeps editing experience clean in Neovim.

### Metadata Ingestion — RESOLVED

**Approach:** YAML metadata files imported via `MetadataImporter`.

**Rationale:**
- Manuscript metadata is edited via per-entity YAML files (floating
  window in Neovim), not by parsing wiki markdown
- YAML provides a structured, validated format that maps directly to
  DB fields without ambiguous parsing
- Same `MetadataImporter` handles both standalone `plm metadata import`
  and the sync cycle's ingest step
- Wiki pages are read-only generated dashboards — structural truth
  lives in YAML metadata and the database

**Architecture:**

```
YAML metadata files → MetadataImporter
                    → Schema validation
                    → Entity resolution (name → DB ID)
                    → Upsert into database
                    → WikiExporter regenerates wiki pages
```

**What gets ingested (manuscript entity types):**

| Entity Type | YAML Location | Key Fields |
|-------------|---------------|------------|
| Chapter | `data/metadata/chapters/{slug}.yaml` | title, part, type, status, synopsis, scenes, notes |
| Character | `data/metadata/characters/{slug}.yaml` | name, description, person mappings (based_on) |
| ManuscriptScene | `data/metadata/scenes/{slug}.yaml` | name, origin, status, description, sources, notes |

**Entity resolution:** Importer resolves entity references by name
(slug or display_name match via DB lookup). Unresolved references
produce import errors.

### Neovim Plugin Architecture — RESOLVED

**Existing implementation:** `dev/lua/palimpsest/`

The plugin already provides:
- **commands.lua** — Export, validate, import, stats, index commands
- **keymaps.lua** — which-key.nvim bindings (`<leader>v` or `<leader>p`)
- **fzf.lua** — fzf-lua integration for browse/search
- **validators.lua** — Async Python validator → Neovim diagnostics
- **autocmds.lua** — Validation on save, template population
- **templates.lua** — Template system for diary entries
- **config.lua** — Project root detection, path configuration
- **vimwiki.lua** — VimWiki instance registration

**Architecture pattern:** Plugin shells out to `plm` CLI for all DB
operations. No direct SQLite access from Lua. fzf-lua provides
fuzzy-finder UI. which-key.nvim provides discoverable keybindings.

**Plugin modules:**

```
dev/lua/palimpsest/
├── init.lua           # Plugin entry point and setup
├── commands.lua       # All :Palimpsest* command registration
├── keymaps.lua        # which-key.nvim bindings
├── config.lua         # Project root detection, path configuration
├── autocmds.lua       # Validation on save, template population
├── float.lua          # Floating window management (YAML popup editing)
├── context.lua        # Page type detection (entity type, slug resolution)
├── entity.lua         # Entity editing (edit, new, add source/based_on/character)
├── cache.lua          # Entity list caching for autocomplete
├── fzf.lua            # fzf-lua integration for browse/search
├── validators.lua     # Async Python validator → Neovim diagnostics
├── templates.lua      # Template system for diary entries
├── vimwiki.lua        # VimWiki instance registration
└── utils.lua          # Shared utility functions
```

**Autocomplete strategy:** Cache + async CLI. On entity edit or buffer
enter, plugin calls `plm` to export entity lists as JSON. Cached in Lua
tables. Autocomplete works against cached tables (instant). Cache
refreshes automatically after every metadata import.

**Command registration:** Extend `commands.lua` setup function with new
commands. Add keybindings to `keymaps.lua` under new groups:
- `<leader>pe` / `<leader>ve` — Edit metadata (`:PalimpsestEdit`)
- `<leader>pn` / `<leader>vn` — New entity (`:PalimpsestNew`)
- Context-sensitive add commands available in manuscript buffers

### `plm wiki lint` Output Format — RESOLVED

**JSON diagnostic schema** consumed by both the Neovim plugin
(`validators.lua`) and the pre-sync validator.

**Schema:**

```json
[
  {
    "file": "wiki/manuscript/chapters/the-gray-fence.md",
    "diagnostics": [
      {
        "line": 12,
        "col": 1,
        "end_line": 12,
        "end_col": 24,
        "severity": "error",
        "code": "UNRESOLVED_WIKILINK",
        "message": "Unresolved wikilink: [[Clarizrd]]",
        "source": "palimpsest"
      }
    ]
  }
]
```

**Decisions:**

1. **Severity levels:** `error` / `warning` / `info` / `hint` — maps
   1:1 to `vim.diagnostic.severity`

2. **Errors block sync, warnings don't:** Unresolved wikilinks and
   missing required sections are errors (corrupt DB data). Empty
   sections and orphan scenes are warnings (work-in-progress).

3. **Diagnostic codes:** Namespaced strings for programmatic filtering:
   - Errors: `UNRESOLVED_WIKILINK`, `MISSING_REQUIRED_SECTION`,
     `INVALID_METADATA`, `DUPLICATE_ENTRY`
   - Warnings: `EMPTY_SECTION`, `ORPHAN_SCENE`, `MISSING_SOURCES`
   - Info: `LONG_SYNOPSIS`, `UNLINKED_CHARACTER`

4. **Batch mode:** `plm wiki lint <path>` accepts files or directories,
   returns array of file results.

5. **Output format:** `--format json|text`, auto-detect based on TTY.
   JSON for Neovim/programmatic consumers, colored text summary for
   terminal use.

## Open Design Questions

All design questions resolved.
