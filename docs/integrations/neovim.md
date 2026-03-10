# Neovim Integration Guide

Palimpsest includes a Neovim/Lua package (`dev/lua/palimpsest`) that provides editor integration for working with journal entries, wiki pages, and manuscript editing.

## Features

- **fzf-lua Integration** - Browse and search wiki entities and journal entries
- **Automatic Validation** - On-save validation with LSP-style diagnostics
- **VimWiki Templates** - Automated log entry creation
- **which-key Integration** - Discoverable keybindings with visual menus
- **Wiki Operations** - Generate, lint, and sync wiki pages
- **Entity Editing** - YAML metadata editing in floating windows
- **Entity Caching** - Autocomplete support via cached entity names
- **Context Detection** - Commands adapt based on current wiki page type

---

## Installation

The Lua package is located at `dev/lua/palimpsest/`. To use it in Neovim:

### Option 1: Lazy.nvim

```lua
{
    dir = "~/Documents/palimpsest/dev/lua/palimpsest",
    name = "palimpsest",
    dependencies = {
        "vimwiki/vimwiki",
        "ibhagwan/fzf-lua",
        "folke/which-key.nvim",
    },
    config = function()
        require("palimpsest").setup()
    end,
}
```

### Option 2: Packer.nvim

```lua
use {
    "~/Documents/palimpsest/dev/lua/palimpsest",
    requires = {
        "vimwiki/vimwiki",
        "ibhagwan/fzf-lua",
        "folke/which-key.nvim",
    },
    config = function()
        require("palimpsest").setup()
    end,
}
```

### Option 3: Manual

```lua
-- In your init.lua
vim.opt.runtimepath:append("~/Documents/palimpsest/dev/lua")
require("palimpsest").setup()
```

---

## Commands

### Browse Commands

Browse markdown files by entity type or location using fzf-lua:

```vim
:PalimpsestBrowse [entity_type]
```

**Available entity types:**
- `all` - Both wiki and journal markdown files
- `wiki` - All wiki markdown files
- `journal` - Journal entries (data/journal/content/md/)
- `people` - Person entity pages
- `entries` - Entry metadata pages
- `locations` - Location pages
- `cities` - City pages
- `events` - Event pages
- `themes` - Theme pages
- `tags` - Tag pages
- `poems` - Poem pages
- `references` - Reference pages

**Examples:**
```vim
:PalimpsestBrowse journal      " Browse journal entries
:PalimpsestBrowse people       " Browse people pages
:PalimpsestBrowse all          " Browse all files (wiki + journal)
```

### Search Commands

Search content across wiki and journal files using ripgrep:

```vim
:PalimpsestSearch [scope]
```

**Available scopes:**
- `all` - Search both wiki and journal (default)
- `wiki` - Search only wiki files
- `journal` - Search only journal entries
- Plus all entity types from browse command

**Examples:**
```vim
:PalimpsestSearch all          " Search everything
:PalimpsestSearch journal      " Search only journal entries
:PalimpsestSearch people       " Search only people pages
```

### Wiki Operation Commands

Commands for wiki generation and linting:

```vim
:PalimpsestLint                " Lint wiki pages for errors
:PalimpsestGenerate [section]  " Generate wiki pages from database
```

**Generate sections:** `journal`, `manuscript`, `indexes`

### Entity Editing Commands

Commands for editing YAML metadata in floating windows:

```vim
:PalimpsestEdit                " Edit current entity metadata (floating window)
:PalimpsestEditCuration        " Edit curation file (neighborhoods/relation_types)
:PalimpsestNew [type]          " Create new entity metadata
:PalimpsestAddSource           " Add source entry to manuscript scene
:PalimpsestAddBasedOn          " Add based_on person mapping to character
:PalimpsestLinkToManuscript    " Link current entry to manuscript
```

**New entity types:** `people`, `chapters`, `characters`, `scenes`

### Validation Commands

Commands for validating frontmatter, links, and entry consistency:

```vim
:PalimpsestValidateFrontmatter    " Validate markdown frontmatter
:PalimpsestValidateMetadata       " Validate all frontmatter structure
:PalimpsestValidateLinks          " Validate markdown links
:PalimpsestValidateEntry [DATE]   " Validate entry (MD + YAML) with quickfix
```

`:PalimpsestValidateEntry` auto-detects the entry date from the current buffer filename if not provided. Results populate the quickfix list.

### Metadata Commands

Commands for YAML metadata export:

```vim
:PalimpsestMetadataExport [type]  " Export entity metadata to YAML files
```

**Entity types:** `people`, `locations`, `cities`, `arcs`, `chapters`, `characters`, `scenes`, `neighborhoods`, `relation_types`

---

## Keybindings

Keybindings are managed by [which-key.nvim](https://github.com/folke/which-key.nvim) for discoverability. Press the leader key sequence to see available options in a popup menu.

### Single VimWiki Setup

If Palimpsest is your only vimwiki, keybindings use `<leader>v` prefix:

#### Core Keybindings

| Keymap | Action |
|--------|--------|
| `<leader>vw` | Open Palimpsest wiki index |
| `<leader>vi` | Open diary index |
| `<leader>v<leader>w` | Open today's diary entry |
| `<leader>v<leader>i` | Generate diary index |

#### Browse Files (via fzf-lua)

| Keymap | Action |
|--------|--------|
| `<leader>vFa` | Browse all wiki files |
| `<leader>vFj` | Browse journal entries |
| `<leader>vFp` | Browse people |
| `<leader>vFe` | Browse entries |
| `<leader>vFl` | Browse locations |
| `<leader>vFc` | Browse cities |
| `<leader>vFv` | Browse events |
| `<leader>vFt` | Browse themes |
| `<leader>vFT` | Browse tags |
| `<leader>vFP` | Browse poems |
| `<leader>vFr` | Browse references |

#### Search Content (via ripgrep + fzf-lua)

| Keymap | Action |
|--------|--------|
| `<leader>v/` | Search all content (wiki + journal) |
| `<leader>v?w` | Search wiki only |
| `<leader>v?j` | Search journal only |

#### Entity Editing

| Keymap | Action |
|--------|--------|
| `<leader>vee` | Edit metadata (floating window) |
| `<leader>vec` | Edit curation file (neighborhoods/relation_types) |
| `<leader>ven` | New entity |
| `<leader>ves` | Add source to scene |
| `<leader>veb` | Add based_on to character |
| `<leader>vel` | Link to manuscript |
| `<leader>vex` | Export metadata YAML |

#### Wiki Operations

| Keymap | Action |
|--------|--------|
| `<leader>vL` | Wiki lint |
| `<leader>vG` | Wiki generate |

#### Validation

| Keymap | Action |
|--------|--------|
| `<leader>vvw` | Lint wiki pages |
| `<leader>vvf` | Validate frontmatter |
| `<leader>vvm` | Validate frontmatter structure |
| `<leader>vvl` | Validate markdown links |
| `<leader>vve` | Validate entry (quickfix) |

#### Manuscript

| Keymap | Action |
|--------|--------|
| `<leader>vme` | Generate manuscript |
| `<leader>vmi` | Ingest manuscript edits |
| `<leader>vmh` | Manuscript homepage |

#### Quick Navigation

| Keymap | Action |
|--------|--------|
| `<leader>vs` | Statistics dashboard |
| `<leader>va` | Analysis report |
| `<leader>vh` | Wiki homepage |
| `<leader>vf` | Quick access wiki pages |

### Multiple VimWiki Setup

If you have multiple vimwikis configured, Palimpsest uses `<leader>p` prefix instead:

#### Core Keybindings

| Keymap | Action |
|--------|--------|
| `<leader>pw` | Open Palimpsest wiki index |
| `<leader>pi` | Open diary index |
| `<leader>p<leader>w` | Open today's diary entry |
| `<leader>p<leader>i` | Generate diary index |

#### Browse Files

| Keymap | Action |
|--------|--------|
| `<leader>pFa` | Browse all wiki files |
| `<leader>pFj` | Browse journal entries |
| `<leader>pFp` | Browse people |
| `<leader>pFe` | Browse entries |
| `<leader>pFl` | Browse locations |
| `<leader>pFc` | Browse cities |
| `<leader>pFv` | Browse events |
| `<leader>pFt` | Browse themes |
| `<leader>pFT` | Browse tags |
| `<leader>pFP` | Browse poems |
| `<leader>pFr` | Browse references |

#### Search Content

| Keymap | Action |
|--------|--------|
| `<leader>p/` | Search all content (wiki + journal) |
| `<leader>p?w` | Search wiki only |
| `<leader>p?j` | Search journal only |

#### Entity Editing

| Keymap | Action |
|--------|--------|
| `<leader>pee` | Edit metadata (floating window) |
| `<leader>pec` | Edit curation file (neighborhoods/relation_types) |
| `<leader>pen` | New entity |
| `<leader>pes` | Add source to scene |
| `<leader>peb` | Add based_on to character |
| `<leader>pel` | Link to manuscript |
| `<leader>pex` | Export metadata YAML |

#### Wiki Operations

| Keymap | Action |
|--------|--------|
| `<leader>pL` | Wiki lint |
| `<leader>pG` | Wiki generate |

#### Validation

| Keymap | Action |
|--------|--------|
| `<leader>pvw` | Lint wiki pages |
| `<leader>pvf` | Validate frontmatter |
| `<leader>pvm` | Validate frontmatter structure |
| `<leader>pvl` | Validate markdown links |
| `<leader>pve` | Validate entry (quickfix) |

#### Manuscript

| Keymap | Action |
|--------|--------|
| `<leader>pme` | Generate manuscript |
| `<leader>pmi` | Ingest manuscript edits |
| `<leader>pmh` | Manuscript homepage |

#### Quick Navigation

| Keymap | Action |
|--------|--------|
| `<leader>ps` | Statistics dashboard |
| `<leader>pa` | Analysis report |
| `<leader>ph` | Wiki homepage |
| `<leader>pf` | Quick access wiki pages |

---

## Validation

Palimpsest automatically validates markdown files on save with inline LSP-style diagnostics.

### Automatic Validation

**On Save (BufWritePost):**
- Journal entries (`data/journal/content/md/**/*.md`) → Frontmatter validation + Link validation
- Wiki pages (`data/wiki/**/*.md`) → Wiki lint validation

### Manual Validation

```vim
:PalimpsestValidateFrontmatter    " Validate YAML frontmatter
:PalimpsestValidateMetadata       " Validate all frontmatter structure
:PalimpsestValidateLinks          " Validate markdown links
:PalimpsestValidateEntry [DATE]   " Validate entry with quickfix output
```

### Validation Types

**Frontmatter Validation:**
- YAML syntax errors
- Required fields (e.g., `date`)
- Field type checking (e.g., `word_count: int`)
- Manuscript status validation
- Reference mode/type validation

**Link Validation:**
- Broken internal links
- Invalid link paths

### Diagnostic Display

Errors and warnings appear as LSP-style diagnostics:
- **Sign column** - Error/warning icons
- **Virtual text** - Inline error messages
- **Hover** - Full diagnostic details

Example output:
```
❌ [frontmatter]:3 Required field 'date' missing
   💡 Add 'date: <value>' to frontmatter
```

---

## Quick Navigation Commands

```vim
:PalimpsestStats                   " Open statistics dashboard
:PalimpsestIndex                   " Open wiki homepage
:PalimpsestAnalysis                " Open analysis report
:PalimpsestManuscriptIndex         " Open manuscript homepage
```

---

## Templates

The package includes a template for diary/log entries located in `templates/wiki/`:

- `log.template` - Diary/log entry template (auto-populated on `VimwikiMakeDiaryNote`)

---

## Configuration

The package automatically configures paths based on project structure:

```lua
-- Default paths (in dev/lua/palimpsest/config.lua)
local root = "~/Documents/palimpsest"

M.paths = {
    root = root,
    wiki = root .. "/data/wiki",
    log = root .. "/data/wiki/log",
    journal = root .. "/data/journal/content/md",
    templates = root .. "/templates/wiki",
}
```

These paths are used by:
- Telescope for browsing/searching
- Validators for file pattern matching
- VimWiki for diary entries

---

## Troubleshooting

### fzf-lua Not Working

- Ensure fzf-lua is installed: `:lua print(vim.inspect(require('fzf-lua')))`
- Verify ripgrep is available: `:!rg --version`
- Verify fd is available (for browse): `:!fd --version`
- Check for errors: `:messages`

### which-key Not Showing Keybindings

- Ensure which-key.nvim is installed
- Check keybindings registered: `:WhichKey <leader>v`
- For multiple vimwikis: `:WhichKey <leader>p`

### Validators Not Running

- Verify Python environment is active
- Test validator CLI: `python -m dev.validators.cli.markdown --help`
- Check autocmd groups: `:autocmd palimpsest_validators`

### Diagnostics Not Appearing

- Check diagnostic settings: `:lua vim.diagnostic.config()`
- Verify file matches pattern (e.g., `data/wiki/entries/**/*.md`)
- Run manual validation to test: `:PalimpsestValidateFrontmatter`

### Journal Files Not Found

- Verify journal path exists: `ls ~/Documents/palimpsest/data/journal/content/md/`
- Check config: `:lua print(require('palimpsest.config').paths.journal)`

---

## Architecture

```
┌──────────────────────────────────────────┐
│         Neovim Editor                    │
│  ┌────────────────────────────────────┐  │
│  │  palimpsest.nvim Package           │  │
│  │  ├── fzf.lua        (browse)       │  │
│  │  ├── validators.lua (lint)         │  │
│  │  ├── templates.lua  (diary)        │  │
│  │  ├── autocmds.lua   (hooks)        │  │
│  │  ├── commands.lua   (cmds)         │  │
│  │  ├── keymaps.lua    (keys)         │  │
│  │  ├── vimwiki.lua    (config)       │  │
│  │  ├── utils.lua      (shared util)  │  │
│  │  ├── context.lua    (page detect)  │  │
│  │  ├── cache.lua      (entity cache) │  │
│  │  ├── float.lua      (popup YAML)   │  │
│  │  └── entity.lua     (edit cmds)    │  │
│  └────────────────────────────────────┘  │
│           │                               │
│           ▼                               │
│  ┌────────────────────────────────────┐  │
│  │  External Dependencies             │  │
│  │  ├── fzf-lua (browse/search)       │  │
│  │  ├── which-key (keybindings)       │  │
│  │  ├── ripgrep (search backend)      │  │
│  │  └── fd (file finding)             │  │
│  └────────────────────────────────────┘  │
│           │                               │
│           ▼                               │
│  ┌────────────────────────────────────┐  │
│  │  Async Job Execution               │  │
│  │  - Python validators                │  │
│  │  - plm wiki (generate/lint)          │  │
│  │  - plm metadata (export/import)     │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│     Python Backend                       │
│  ┌────────────────────────────────────┐  │
│  │  validators/                       │  │
│  │  ├── md.py       (frontmatter)     │  │
│  │  └── wiki.py     (links)           │  │
│  └────────────────────────────────────┘  │
│  ┌────────────────────────────────────┐  │
│  │  wiki/                             │  │
│  │  ├── exporter.py  (DB → wiki)      │  │
│  │  ├── parser.py    (wiki → DB)      │  │
│  │  ├── validator.py (linting)        │  │
│  │  ├── sync.py      (bidirectional)  │  │
│  │  └── metadata.py  (YAML files)     │  │
│  └────────────────────────────────────┘  │
│           │                               │
│           ▼                               │
│  ┌────────────────────────────────────┐  │
│  │  palimpsest.db (SQLite)            │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

The Neovim package acts as a frontend to the Python backend:
- **Browse/Search** - Direct file access via fzf-lua + ripgrep (wiki + journal)
- **Keybindings** - Managed via which-key.nvim for discoverability
- **Validation** - Calls Python validators asynchronously
- **Templates** - Diary entries (VimWiki integration)
- **Wiki Operations** - Calls `plm wiki` CLI for generate, lint, sync
- **Entity Editing** - Opens YAML metadata in floating windows via `plm metadata`
- **Entity Caching** - Calls `plm metadata list` for autocomplete data

---

## Deck Mode (Writer Deck)

Deck mode is a lightweight plugin profile for the writer deck (Raspberry Pi Zero 2W), which runs a minimal neovim setup without Python. It enables manuscript editing via vimwiki with safety guards that prevent data loss from wiki/DB drift.

### Setup

Set `vim.g.palimpsest_deck_mode = true` before calling `setup()`:

```lua
config = function()
    vim.g.palimpsest_deck_mode = true
    require("palimpsest").setup()
end,
```

### Sync-Pending Marker

When a manuscript wiki file is saved on the deck, a `.sync-pending` marker (`data/wiki/.sync-pending`) is created tracking which files were edited. This marker:

- **Blocks** `plm wiki generate` and `plm wiki sync --generate` on the main machine
- **Is cleared** by `plm wiki sync` (full or ingest-only) after ingesting changes
- **Triggers a notification** on main machine nvim startup: "Deck edits pending"

The marker is a JSON file tracked in git:

```json
{
  "machine": "writer-deck",
  "timestamp": "2026-02-13T14:22:00",
  "files": ["manuscript/chapters/the-gray-fence.md"]
}
```

### Sync Workflow

```
Main Machine                          Writer Deck
────────────                          ───────────
plm wiki generate
git commit + push
                                      git pull (wiki pages available)
                                      edit manuscript in vimwiki
                                      BufWritePost creates .sync-pending
                                      git commit + push
git pull (sees .sync-pending)
plm wiki sync (ingest → clear → generate)
git commit + push
                                      git pull (clean state)
```

### Feature Matrix

| Feature | Main Machine | Writer Deck |
|---------|-------------|-------------|
| Vimwiki navigation | Yes | Yes |
| Read/edit wiki pages | Yes | Yes |
| Log entry templates | Yes | Yes |
| which-key menus | Yes | Yes |
| fzf-lua entity browse | Yes | No (use snacks.nvim) |
| Wiki on-save lint | Yes | No |
| Float YAML editing | Yes | No |
| Wiki sync/generate | Yes | No |
| Entity cache | Yes | No |
| Validation commands | Yes | No |
| Sync-pending marker | Reads + clears | Writes |
| Quick navigation | Yes | Yes |

### Available Deck Commands

Navigation (open pre-generated wiki files):
- `:PalimpsestIndex` - Wiki homepage
- `:PalimpsestManuscriptIndex` - Manuscript homepage
- `:PalimpsestQuickAccess` - Quick access wiki pages

Browse/Search (requires fzf-lua):
- `:PalimpsestBrowse [type]` - Browse wiki entities
- `:PalimpsestSearch [scope]` - Search wiki content

### Troubleshooting Deck Mode

**Wiki pages not found:**
- Ensure wiki pages are generated and committed on the main machine
- Run `git pull` in the data submodule on the deck

**Sync-pending not created:**
- Verify `vim.g.palimpsest_deck_mode = true` is set
- Check autocmd group: `:autocmd palimpsest_deck_sync`
- Only manuscript files (`wiki/manuscript/**/*.md`) trigger the marker

**Main machine blocked by stale marker:**
- Run `plm wiki sync` to ingest and clear the marker
- Or manually delete `data/wiki/.sync-pending` if edits were already handled

---

## See Also

- [Command Reference](command-reference.md) - Full CLI command list
- [SQL-Wiki Guide](sql-wiki-guide.md) - Database-wiki synchronization
- [Metadata Quick Reference](metadata-quick-reference.md) - YAML frontmatter format
