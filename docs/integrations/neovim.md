# Neovim Integration Guide

> **Note:** This integration is designed for journal markdown file browsing and searching.
> Wiki features are not currently implemented.

Palimpsest includes a Neovim/Lua package (`dev/lua/palimpsest`) that provides editor integration for working with journal entries.

## Features

- **fzf-lua Integration** - Browse and search wiki entities and journal entries
- **Automatic Validation** - On-save validation with LSP-style diagnostics
- **VimWiki Templates** - Automated log entry creation
- **which-key Integration** - Discoverable keybindings with visual menus

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

#### Validation

| Keymap | Action |
|--------|--------|
| `<leader>vvw` | Validate wiki links |

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

#### Validation

| Keymap | Action |
|--------|--------|
| `<leader>pvw` | Validate wiki links |

---

## Validation

Palimpsest automatically validates markdown files on save with inline LSP-style diagnostics.

### Automatic Validation

**On Save (BufWritePost):**
- Entry files (`data/wiki/entries/**/*.md`) → Frontmatter validation
- All wiki files → Link validation

### Manual Validation

```vim
:PalimpsestValidateFrontmatter    " Validate YAML frontmatter
:PalimpsestValidateMetadata       " Validate metadata fields
:PalimpsestValidateLinks          " Validate markdown links
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

## Export/Import Commands

Standard Palimpsest wiki commands are also available:

```vim
:PalimpsestExport [entity]         " Export from database to wiki
:PalimpsestValidate [mode]         " Validate wiki cross-references
:PalimpsestStats                   " Open statistics dashboard
:PalimpsestIndex                   " Open wiki homepage
:PalimpsestAnalysis                " Open analysis report

" Manuscript-specific
:PalimpsestManuscriptExport [entity]
:PalimpsestManuscriptImport [entity]
:PalimpsestManuscriptIndex
```

See `:help PalimpsestExport` for full command details.

---

## Templates

The package includes a template for diary/log entries located in `templates/wiki/`:

- `log.template` - Diary/log entry template (auto-populated on `VimwikiMakeDiaryNote`)

**Note:** Entity pages (people, locations, events, themes) are **not** generated from templates. They are fully constructed by the Python builders from database queries using the `to_wiki()` methods in each WikiEntity dataclass. The complete wiki page including all sections (Appearances, Related Entries, etc.) is generated directly from the database when you run `plm export-wiki`.

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
┌─────────────────────────────────────┐
│         Neovim Editor               │
│  ┌───────────────────────────────┐  │
│  │  palimpsest.nvim Package      │  │
│  │  ├── fzf.lua        (browse)  │  │
│  │  ├── validators.lua (lint)    │  │
│  │  ├── templates.lua  (diary)   │  │
│  │  ├── autocmds.lua   (hooks)   │  │
│  │  ├── commands.lua   (cmds)    │  │
│  │  ├── keymaps.lua    (keys)    │  │
│  │  └── vimwiki.lua    (config)  │  │
│  └───────────────────────────────┘  │
│           │                          │
│           ▼                          │
│  ┌───────────────────────────────┐  │
│  │  External Dependencies        │  │
│  │  ├── fzf-lua (browse/search)  │  │
│  │  ├── which-key (keybindings)  │  │
│  │  ├── ripgrep (search backend) │  │
│  │  └── fd (file finding)        │  │
│  └───────────────────────────────┘  │
│           │                          │
│           ▼                          │
│  ┌───────────────────────────────┐  │
│  │  Async Job Execution          │  │
│  │  - Python validators only     │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│     Python Backend                  │
│  ┌───────────────────────────────┐  │
│  │  validators/                  │  │
│  │  ├── md.py       (frontmatter)│  │
│  │  └── wiki.py     (links)      │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │  builders/wiki.py             │  │
│  │  - WikiEntity.from_database() │  │
│  │  - WikiEntity.to_wiki()       │  │
│  │  Generates complete wiki pages│  │
│  └───────────────────────────────┘  │
│           │                          │
│           ▼                          │
│  ┌───────────────────────────────┐  │
│  │  palimpsest.db (SQLite)       │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

The Neovim package acts as a frontend to the Python backend:
- **Browse/Search** - Direct file access via fzf-lua + ripgrep (wiki + journal)
- **Keybindings** - Managed via which-key.nvim for discoverability
- **Validation** - Calls Python validators asynchronously
- **Templates** - Only for diary entries (VimWiki integration)

**Wiki page generation is handled entirely by Python:** When you run `plm export-wiki`, the Python builders query the database and generate complete wiki pages using the `WikiEntity.to_wiki()` methods. No templates are involved in this process.

---

## See Also

- [Command Reference](command-reference.md) - Full CLI command list
- [SQL-Wiki Guide](sql-wiki-guide.md) - Database-wiki synchronization
- [Metadata Quick Reference](metadata-quick-reference.md) - YAML frontmatter format
