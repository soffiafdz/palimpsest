# Vimwiki Generation System

Generate navigable wiki pages from the Palimpsest database for
browsing journal metadata and editing manuscript structure within Neovim,
with static site rendering via Quartz for browser access.

## Purpose

The wiki system provides a structured, hyperlinked view of the database
as clean markdown pages. Pages are designed for dual consumption:

- **Neovim**: Primary editing environment with `[[wikilinks]]`, linting,
  and sync commands
- **Quartz**: Static site generator for browser rendering with graph
  visualization, backlinks, and full-text search

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
            │  plm wiki    │
            │  publish     │
            │  (copy +     │
            │  frontmatter)│
            └──────┬───────┘
                   ▼
            ┌──────────────┐
            │    Quartz    │
            │  (static     │
            │   site gen)  │
            └──────────────┘
```

Three content paths:

- **Journal wiki** (generated): DB → Jinja2 → wiki pages (read-only)
- **YAML metadata** (per-entity): DB → YAML files ↔ Palimpsest nvim
  plugin (floating window editing) → DB
- **Manuscript wiki** (mixed): DB → wiki pages → user edits prose
  (Character, Chapter) → validate → sync → DB → regenerate
- **Browser**: wiki → `plm wiki publish` (copy + frontmatter injection)
  → Quartz build → static site

### Round-Trip Cycle

Two editing paths feed back into the database:

**YAML metadata path** (Part, ManuscriptScene metadata, journal entities):

1. **Generate**: DB exports YAML metadata files
2. **Edit**: User opens `:PalimpsestEdit` → floating window with YAML
3. **Save**: YAML validated and ingested into DB on window close
4. **Regenerate**: DB re-renders wiki pages with updated metadata

**Wiki prose path** (Chapter, Character, ManuscriptScene prose):

1. **Generate**: DB renders wiki pages via Jinja2 templates
2. **Edit**: User modifies wiki pages directly in Neovim
3. **Validate**: Linter checks edits on save (async, advisory)
4. **Sync**: On explicit user command, validated pages are parsed and
   ingested into DB
5. **Regenerate**: DB re-renders pages, normalizing content and adding
   computed data (backlinks, cross-references, status badges)

Every piece of user-written content maps to a DB field. Nothing is
lost in the round-trip — the user's text passes through ingest before
generation overwrites the file.

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
- "Character `[[Léaa]]` not found — did you mean `[[Léa]]`?"
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
plm wiki sync                    # Full: ingest + regenerate
plm wiki sync --ingest           # Wiki → DB only
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
| `data/narrative_analysis/` | Metadata YAML validator | `dev/validators/metadata_yaml.py` |
| `data/wiki/manuscript/` | Manuscript wiki validator | New — `dev/wiki/validator.py` |

All validators are accessible through a single CLI entry point:
`plm lint <filepath>`. The Neovim plugin calls this and renders
the output as native diagnostics. The existing validators need
adaptation to emit structured diagnostics (file, line, column,
severity, message) rather than just pass/fail results.

## Wiki Page Design

Wiki pages are clean markdown with no user-facing YAML frontmatter.
Structure is conveyed through consistent heading conventions and
wiki-style links (`[[Entity Name]]`).

The Jinja2 generator may inject YAML frontmatter for Quartz metadata
(title, tags, aliases for link resolution), but this is invisible to
the user's editing workflow — it is regenerated on every sync cycle.

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

## Static Site Generation (Quartz)

[Quartz](https://quartz.jzhao.xyz/) is the static site generator for
browser-based wiki access. It was chosen because:

- **Native `[[wikilink]]` support**: Resolves wiki-style links to HTML
  links without plugins or transformation
- **Backlinks**: Automatically generates backlink sections on each page
- **Graph visualization**: Interactive graph view of page connections
- **Full-text search**: Built-in client-side search
- **Clean markdown input**: Expects the same markdown format we generate
- **Obsidian compatibility**: Handles the same link conventions

### Quartz Integration

The wiki directory (`data/wiki/`) serves as the Quartz content directory.
The build step is a simple `npx quartz build` after wiki generation.

```bash
# Generate wiki, then build static site
plm wiki generate
cd data/wiki && npx quartz build

# Or as a combined command
plm wiki publish
```

### Design Constraints for Quartz Compatibility

- `[[wikilinks]]` must resolve to actual file paths in the directory tree
- Generator-injected YAML frontmatter provides Quartz metadata (title,
  tags, aliases) without the user needing to maintain it
- Directory structure must be flat enough for wikilink resolution
  (Quartz resolves `[[Page Name]]` by searching all directories)
- File names must be URL-safe slugs matching the page title

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
plm wiki lint <filepath>

# Sync manuscript (ingest + regenerate)
plm wiki sync

# Build static site (Quartz)
plm wiki publish
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

## Resolved Design Questions

### Wiki Page Schema — RESOLVED

Detailed designs for all 27 page types documented in
`docs/development/wiki-page-designs.md`. Includes exact heading
conventions, parsing rules, zone breakdowns, and mockups for every
entity type. Key architectural decisions:

- **YAML + floating window** for manuscript structural metadata (Part,
  ManuscriptScene metadata)
- **Pure wiki editing** for Character and Chapter (no YAML files)
- **Sources and Based On** in wiki with guided insertion commands
- **Journal entity metadata** in per-entity YAML files (People, Locations)
  or single files (Cities, Arcs)
- **11 Palimpsest nvim commands** with DB-backed autocomplete

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
   - `timeline_table.jinja2` — Month-by-month density table
   - `frequent_people.jinja2` — Bulleted wikilinked list with counts
   - `thread_display.jinja2` — Thread heading + dates + content + people
   - `patterns_section.jinja2` — Co-occurring tags/themes list

4. **Custom Jinja2 filters** (`dev/wiki/filters.py`):
   - `wikilink(name, display)` — `[[name]]` or `[[name|display]]`
   - `date_long(d)` — `Tuesday, November 8, 2024`
   - `date_range(start, end)` — `Nov 2024 – Jan 2025`
   - `mid_dot_join(items)` — `[[A]] · [[B]] · [[C]]`
   - `adaptive_list(items, threshold)` — inline or bulleted by count
   - `timeline_table(monthly_counts)` — full markdown table
   - `source_path(entity, wiki_root)` — relative path to source file

5. **Empty section suppression:** Per-section `{% if data %}` blocks.
   No wrapping macro — explicit conditionals are more readable.

6. **User prose verbatim:** DB stores exact text from wiki sections
   (synopsis, description, notes). Templates output `{{ chapter.synopsis }}`
   with no transformation, trimming, or normalization. Parser captures
   raw text between section headings.

7. **Quartz frontmatter as post-processing:** Templates always output
   clean markdown (no YAML frontmatter). Quartz metadata (title, aliases,
   tags) injected by a separate post-processing step during
   `plm wiki publish`, not by templates. Keeps editing experience clean.

### Parser Implementation — RESOLVED

**Approach:** Markdown AST via `markdown-it-py` with custom wikilink plugin.

**Rationale:**
- Most robust handling of markdown variations (code blocks, nested
  formatting, blockquotes inside prose sections)
- `markdown-it-py` is the Python port of `markdown-it`, which Quartz
  uses internally — same parsing rules guarantee round-trip consistency
- Natively understands heading levels, blockquotes, lists — the exact
  structures our wiki sections use
- Additional dependency is trivial (project already uses SQLAlchemy,
  Jinja2, Click, PyYAML)
- Custom plugin for `[[wikilink]]` inline syntax

**Architecture:**

```
Wiki file → markdown-it-py AST
         → Section splitter (walk tree, group nodes by ## headings)
         → Per-section extractors:
             Prose sections (Synopsis, Description, Notes):
               Reassemble raw text from AST nodes, preserve verbatim
             List sections (Scenes, Characters, Arcs, Poems):
               Extract list item nodes, parse [[wikilinks]] from text
             Structured sections (Sources, Based On):
               Extract patterns from text nodes (type + wikilink + metadata)
             Blockquote sections (References):
               Extract blockquote content, parse attribution + mode
```

**What gets parsed (manuscript pages only):**

| Page | Heading | Content Extractor | DB Target |
|------|---------|-------------------|-----------|
| Chapter | `#` | Title text | `chapter.title` |
| Chapter | metadata line | Number, part, type, status | scalar fields |
| Chapter | `## Synopsis` | Prose (verbatim) | `chapter.content` |
| Chapter | `## Scenes` | Wikilink list (ordered) | `chapter_scenes` M2M |
| Chapter | `## Characters` | Wikilink list | `chapter_characters` M2M |
| Chapter | `## Arcs` | Wikilink list | `chapter.arcs` M2M |
| Chapter | `## Notes` | Prose (verbatim) | `chapter.notes` |
| Chapter | `## References` | Blockquotes + attribution | `manuscript_references` |
| Chapter | `## Poems` | Wikilink list | `chapter_poems` M2M |
| Character | `#` | Name text (strip " (character)") | `character.name` |
| Character | `## Description` | Prose (verbatim) | `character.description` |
| Character | `## Based On` | Structured: wikilink + contribution + notes | `person_character_map` |
| ManuscriptScene | `#` | Name text | `manuscript_scene.name` |
| ManuscriptScene | `## Description` | Prose (verbatim) | `manuscript_scene.description` |
| ManuscriptScene | `## Sources` | Structured: type + wikilink + name | `manuscript_sources` |
| ManuscriptScene | `## Notes` | Prose (verbatim) | `manuscript_scene.notes` |

**Wikilink resolution:** Parser extracts `[[Display Name]]` from AST,
resolves to entity ID via DB lookup (slug or display_name match).
Unresolved links flagged as lint errors.

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

**New modules needed for wiki design commands:**

```
dev/lua/palimpsest/
├── (existing modules)
├── float.lua          # Floating window management
│                      #   Open YAML in popup, save/close flow
│                      #   Configurable size (60% default, larger for big files)
├── context.lua        # Page type detection
│                      #   Detect current wiki page entity type
│                      #   Resolve entity slug from file path/heading
│                      #   Determine available commands per context
├── entity.lua         # Entity editing commands
│                      #   PalimpsestEdit: open metadata YAML via float.lua
│                      #   PalimpsestNew: create entity from template
│                      #   PalimpsestAdd*: guided insertion with autocomplete
│                      #   PalimpsestLinkTo*: bidirectional linking
└── cache.lua          # Entity list caching for autocomplete
                       #   On buffer enter / sync: call plm to dump entity lists
                       #   Cache as Lua tables (people names, scene names, etc.)
                       #   Provide completion source for nvim-cmp or native
```

**Autocomplete strategy:** Cache + async CLI. On sync or buffer enter,
plugin calls `plm` to export entity lists as JSON. Cached in Lua tables.
Autocomplete works against cached tables (instant). Cache refreshes on
`:PalimpsestSync`.

**Command registration:** Extend `commands.lua` setup function with new
commands. Add keybindings to `keymaps.lua` under new groups:
- `<leader>pe` / `<leader>ve` — Edit metadata (`:PalimpsestEdit`)
- `<leader>pn` / `<leader>vn` — New entity (`:PalimpsestNew`)
- Context-sensitive add commands available in manuscript buffers

### `plm lint` Output Format — RESOLVED

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

4. **Batch mode:** `plm lint <path>` accepts files or directories,
   returns array of file results.

5. **Output format:** `--format json|text`, auto-detect based on TTY.
   JSON for Neovim/programmatic consumers, colored text summary for
   terminal use.

### Quartz Configuration — RESOLVED

Quartz is the **secondary** rendering layer — a static site for browser
reading, discovery, and graph visualization. Vimwiki is primary.

**Publish pipeline:**

```
wiki/                              quartz/content/
  journal/people/clara.md    →       journal/people/clara.md
  (clean markdown)                   (YAML frontmatter + same markdown)
```

`plm wiki publish` copies wiki files into the Quartz `content/`
directory, injecting YAML frontmatter during the copy. Source wiki
files are never modified. The Quartz output directory is disposable
and `.gitignore`d.

**Decisions:**

1. **Frontmatter injection:** `plm wiki publish` injects per-file:
   - `title` — from `# Heading`
   - `aliases` — entity aliases from DB (enables `[[Nymi]]` → Nymeria)
   - `tags` — entity type label (for graph coloring / filtering)
   - `date` — for entry pages (chronological sorting)
   - `draft: true` — for WIP pages to exclude from rendering

2. **Theme:** Quartz defaults with minimal overrides. Serif body font
   for manuscript prose readability. Dark mode enabled (built-in).

3. **Layout:**
   - Left sidebar: folder tree (journal / manuscript / indexes)
   - Right sidebar: table of contents + local graph
   - Backlinks section at page bottom (auto-generated by Quartz)

4. **Navigation:** Folder hierarchy matches wiki structure:
   ```
   Journal/
     Entries/ People/ Locations/ Tags/ Themes/ Arcs/ Events/
   Manuscript/
     Parts/ Chapters/ Characters/ Scenes/
   Indexes/
   ```
   Custom index pages replace Quartz auto-generated folder pages.

5. **Graph — local:** Depth 2, shown on every page in right sidebar.
   Primary discovery tool for following connections.

6. **Graph — global:** Filtered to hub entities only (People, Arcs,
   Chapters). Individual entries omitted to keep the visualization
   usable at 1000+ pages.

7. **Graph coloring:** Entity type injected as `tags` frontmatter →
   Quartz colors graph nodes by tag. Distinct colors for People,
   Locations, Arcs, Entries, Chapters.

8. **Plugins enabled:** WikiLinks, Backlinks, Graph, TableOfContents,
   Search (Flexsearch). FolderPage disabled (custom indexes instead).

## Open Design Questions

All design questions resolved.
