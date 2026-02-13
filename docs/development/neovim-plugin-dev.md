# Neovim Package Development Guide

Technical documentation for developing and extending the Palimpsest Neovim integration package.

## Package Structure

```
dev/lua/palimpsest/
├── init.lua          # Entry point and setup
├── config.lua        # Configuration and paths
├── fzf.lua           # fzf-lua integration (browse/search)
├── validators.lua    # Validation integration
├── templates.lua     # Template system
├── autocmds.lua      # Autocommands
├── commands.lua      # User commands
├── keymaps.lua       # Key bindings (which-key)
├── vimwiki.lua       # VimWiki configuration
├── context.lua       # Page type detection from file path
├── cache.lua         # Entity list caching for autocomplete
├── float.lua         # Floating window management for YAML editing
└── entity.lua        # Entity editing commands
```

---

## Module Responsibilities

### init.lua

Entry point that loads all submodules:

```lua
function M.setup()
    require("palimpsest.vimwiki").setup()
    require("palimpsest.commands").setup()
    require("palimpsest.validators").setup()
    require("palimpsest.keymaps").setup()
    require("palimpsest.autocmds").setup()
end
```

### config.lua

Defines project paths and configuration:

```lua
M.paths = {
    root = "~/Documents/palimpsest",
    wiki = root .. "/data/wiki",
    log = root .. "/data/wiki/log",
    journal = root .. "/data/journal/content/md",
    templates = root .. "/templates/wiki",
}
```

### fzf.lua

fzf-lua integration for browsing files and searching content:

**Key Functions:**

- `M.browse(entity_type)` - Browse files by entity type using fzf-lua's `files()` picker
- `M.search(entity_type)` - Search content using fzf-lua's `live_grep()` with ripgrep

**Browse Implementation:**

```lua
function M.browse(entity_type)
    local has_fzf, fzf = pcall(require, "fzf-lua")
    if not has_fzf then
        vim.notify("fzf-lua is not installed", vim.log.levels.ERROR)
        return
    end

    local entity_paths = {
        all = { journal_dir, wiki_dir },
        wiki = wiki_dir,
        journal = journal_dir,
        people = wiki_dir .. "/people",
        -- ... other entity types
    }

    fzf.files({
        prompt = "Palimpsest: " .. entity_type .. "> ",
        cwd = search_path,
        cmd = "fd -t f -e md",  -- Uses fd for fast file finding
        winopts = { height = 0.85, width = 0.80 },
    })
end
```

**Search Implementation:**

```lua
function M.search(entity_type)
    -- For single paths
    fzf.live_grep({
        prompt = "Search: " .. entity_type .. "> ",
        cwd = search_paths[1],
        winopts = { height = 0.85, width = 0.80 },
    })

    -- For multiple paths (e.g., "all" = wiki + journal)
    local rg_cmd = "rg --column --line-number --no-heading --color=always --smart-case --hidden --follow -g '!.git' "
    rg_cmd = rg_cmd .. table.concat(search_paths, " ")

    fzf.live_grep({
        prompt = "Search All Content: " .. entity_type .. "> ",
        cmd = rg_cmd,  -- Custom ripgrep command with multiple paths
        winopts = { height = 0.85, width = 0.80 },
    })
end
```

**Dependencies:**
- `fzf-lua` - Neovim plugin for fuzzy finding
- `ripgrep` (rg) - Fast text search tool
- `fd` - Fast file finding tool (optional, falls back to `find`)

### validators.lua

Async validation integration with Python backend:

**Architecture:**

1. Runs Python validators via `vim.fn.jobstart()`
2. Parses output (stdout/stderr)
3. Converts to Neovim diagnostics
4. Displays via diagnostic API

**Python Validator Layers:**

The Python validation system uses a 3-layer architecture:

1. **Schema Layer** (`dev/validators/schema.py`) - Enum and type validation
2. **Format Layer** (`dev/validators/md.py`, `metadata.py`) - Markdown/YAML structure validation
3. **Database Layer** (`dev/validators/db.py`, `consistency.py`) - Referential integrity validation

See [Validator Architecture](./validator-architecture.md) for details.

**Key Functions:**

- `M.validate_frontmatter(bufnr)` - YAML frontmatter validation (uses `md.py`)
- `M.validate_metadata(bufnr)` - Metadata field validation (uses `metadata.py`)
- `M.validate_links(bufnr)` - Link validation (uses `md.py`)

**Diagnostic Format:**

```lua
{
    bufnr = bufnr,
    lnum = line_number - 1,  -- 0-indexed
    col = 0,
    severity = vim.diagnostic.severity.ERROR,  -- or WARN
    source = "palimpsest",
    message = "[category] message\n💡 suggestion",
}
```

### templates.lua

Template system for VimWiki diary entries only:

**Core Functions:**

- `read_template(name)` - Load template file
- `substitute_variables(lines, variables)` - Replace `{{var}}` placeholders
- `M.insert_template(name, variables, cursor_pos)` - Insert processed template

**Current Usage:**

- `M.populate_log()` - Creates diary/log entries (triggered by VimWiki autocmd on `BufNewFile` for log files)

### autocmds.lua

Autocommand definitions:

**Template Formatting:**

```lua
-- Set filetype for .template files
pattern = palimpsest.paths.templates .. "*.template"
→ vim.bo.filetype = "markdown"
```

**Log Entry Population:**

```lua
-- Populate new log entries from template
pattern = palimpsest.paths.log .. "*.md"
event = "BufNewFile"
→ templates.populate_log()
```

**Validators:**

```lua
-- Validate entry frontmatter on save
pattern = palimpsest.paths.wiki .. "/entries/**/*.md"
event = "BufWritePost"
→ validators.validate_frontmatter(bufnr)

-- Validate all wiki links on save
pattern = palimpsest.paths.wiki .. "/**/*.md"
event = "BufWritePost"
→ validators.validate_links(bufnr)
```

### commands.lua

User command definitions using `vim.api.nvim_create_user_command()`:

**Command Structure:**

```lua
vim.api.nvim_create_user_command("PalimpsestBrowse", function(opts)
    local entity_type = opts.args ~= "" and opts.args or "all"
    require("palimpsest.fzf").browse(entity_type)
end, {
    nargs = "?",
    desc = "Browse wiki entities with fzf-lua",
    complete = function()
        return { "all", "wiki", "journal", "people", ... }
    end,
})

vim.api.nvim_create_user_command("PalimpsestSearch", function(opts)
    local entity_type = opts.args ~= "" and opts.args or "all"
    require("palimpsest.fzf").search(entity_type)
end, {
    nargs = "?",
    desc = "Search wiki/journal content with ripgrep",
    complete = function()
        return { "all", "wiki", "journal", "people", ... }
    end,
})
```

**Wiki and Entity Commands:**

The `setup()` function also registers wiki operation commands (`PalimpsestSync`, `PalimpsestLint`, `PalimpsestGenerate`), entity editing commands (`PalimpsestEdit`, `PalimpsestNew`, `PalimpsestAddSource`, `PalimpsestAddBasedOn`, `PalimpsestLinkToManuscript`), and metadata commands (`PalimpsestMetadataExport`, `PalimpsestCacheRefresh`). These delegate to `commands.wiki_sync()`, `commands.wiki_lint()`, `commands.wiki_generate()`, `entity.edit()`, `cache.refresh_all()`, etc.

### keymaps.lua

Key binding registration using `which-key.nvim`:

**Dual Configuration:**

- Single vimwiki → `<leader>v` prefix
- Multiple vimwikis → `<leader>p` prefix

**Structure:**

Uses which-key.nvim's `add()` API for registering keybindings with descriptions and groups:

```lua
local wk = require("which-key")

-- Check if multiple vimwikis are configured
if #vim.g.vimwiki_list > 1 then
    -- Multiple vimwikis - use <leader>p prefix
    wk.add({
        { "<leader>p", group = "Palimpsest", icon = { icon = palimpsest_icon, color = "green" } },
        -- Entity commands (YAML floating window)
        { "<leader>pe", group = "entity" },
        { "<leader>pee", "<cmd>PalimpsestEdit<cr>", desc = "Edit metadata (float)" },
        { "<leader>pen", "<cmd>PalimpsestNew<cr>", desc = "New entity..." },
        { "<leader>pes", "<cmd>PalimpsestAddSource<cr>", desc = "Add source to scene" },
        { "<leader>peb", "<cmd>PalimpsestAddBasedOn<cr>", desc = "Add based_on to character" },
        { "<leader>pel", "<cmd>PalimpsestLinkToManuscript<cr>", desc = "Link to manuscript" },
        { "<leader>pex", "<cmd>PalimpsestMetadataExport<cr>", desc = "Export metadata YAML" },
        { "<leader>per", "<cmd>PalimpsestCacheRefresh<cr>", desc = "Refresh entity cache" },
        -- Wiki operations
        { "<leader>pS", "<cmd>PalimpsestSync<cr>", desc = "Wiki sync" },
        { "<leader>pL", "<cmd>PalimpsestLint<cr>", desc = "Wiki lint" },
        { "<leader>pG", "<cmd>PalimpsestGenerate<cr>", desc = "Wiki generate" },
        -- Browse/Search
        { "<leader>pF", group = "browse entities" },
        { "<leader>pFa", "...", desc = "Browse wiki" },
        { "<leader>p/w", "...", desc = "Search wiki" },
        -- ... more keybindings
    })
else
    -- Single vimwiki - use <leader>v prefix (same structure, different prefix)
end
```

**Binding Groups:**

| Group | Prefix | Purpose |
|-------|--------|---------|
| Entity | `e` | YAML metadata editing (edit, new, add source, based_on, link, export, cache) |
| Wiki ops | uppercase | Sync (`S`), Lint (`L`), Generate (`G`), Export (`E`) |
| Browse | `F` | fzf-lua file browsing by entity type |
| Search | `/` | ripgrep content search by scope |
| Validators | `v` | Validation commands (wiki links, frontmatter, metadata) |
| Manuscript | `m` | Manuscript export, import, index |

**Benefits:**
- Discoverable keybindings via which-key popup menus
- Grouped keybindings with visual hierarchy
- Icons and descriptions for better UX

### context.lua

Page type detection from wiki file paths. Used by entity commands and keymaps to provide context-sensitive behavior.

**Key Functions:**

- `M.detect(filepath)` — Analyze file path to determine entity type, section, and slug
- `M.available_commands(context)` — Return valid commands for the detected context
- `M.is_wiki_page()` — Check if current buffer is inside the wiki directory
- `M.metadata_type(context)` — Map context type to `plm metadata` entity type key

**Path Patterns:**

Matches 15 subdirectory patterns covering journal entities (entry, person, location, city, event, arc, tag, theme, poem, reference, motif), manuscript entities (chapter, character, scene), and index pages.

**Return Value:**

```lua
{
    type = "chapter",     -- Entity type
    section = "manuscript", -- Section (journal/manuscript/indexes)
    slug = "the-gray-fence" -- Entity slug from filename
}
```

### cache.lua

Entity name caching for autocomplete support. Calls `plm metadata list-entities` asynchronously and stores results in Lua tables.

**Key Functions:**

- `M.refresh(entity_type, callback)` — Refresh cache for one type (async via jobstart)
- `M.refresh_all()` — Trigger parallel refreshes for all entity types
- `M.get(entity_type)` — Get cached names (triggers lazy refresh if empty)
- `M.completion_source(entity_type)` — Return a completion function for nvim APIs
- `M.clear(entity_type)` — Clear cache (one type or all)

**Cached Entity Types:** people, locations, cities, arcs, chapters, characters, scenes

**Usage:**

```lua
-- Get names for autocomplete
local people = require("palimpsest.cache").get("people")

-- Create a completion source
local complete_fn = require("palimpsest.cache").completion_source("people")
local matches = complete_fn("Cla")  -- Returns names matching "Cla"
```

### float.lua

Floating window management for YAML metadata editing. Creates centered popup windows with auto-validation on save and auto-import on close.

**Key Functions:**

- `M.open(filepath, opts)` — Open YAML file in floating window
- `M.on_save(bufnr, filepath)` — Handle save: runs `plm metadata validate`
- `M.on_close(bufnr, filepath)` — Handle close: runs `plm metadata import` and refreshes cache

**Window Options:**

```lua
{
    width_ratio = 0.6,    -- 60% of editor width
    height_ratio = 0.7,   -- 70% of editor height
    border = "rounded",
    title = " Metadata ",
    title_pos = "center",
}
```

**Autocmds:** Sets up `BufWritePost` (validate) and `WinClosed` (import) per floating buffer. Cleanup runs on window close. Press `q` to close.

### entity.lua

Context-aware entity editing commands. Detects the current wiki page type and opens the corresponding YAML metadata file in a floating window.

**Key Functions:**

- `M.edit()` — Open metadata YAML for current page entity (via context detection + float)
- `M.new(entity_type)` — Create entity from template with name prompt
- `M.add_source()` — Guided source insertion for manuscript scenes (type + reference)
- `M.add_based_on()` — Guided person mapping for characters (person + contribution)
- `M.link_to_manuscript()` — Link journal entries to chapters or scenes

**Dependencies:** Requires `context.lua` (page detection), `float.lua` (popup UI), `cache.lua` (entity names for autocomplete)

**YAML Path Resolution:**

- Per-entity files: `data/metadata/{people,locations,manuscript/chapters,...}/{slug}.yaml`
- Single files: `data/metadata/cities.yaml`, `data/metadata/arcs.yaml`

---

## Python Backend Integration

### Validators

Lua calls Python validators via subprocess:

```bash
python -m dev.validators.cli.markdown frontmatter <filepath>
```

**Output Format:**
The validator should output structured messages that Lua can parse:

```
❌ [frontmatter]:3 Required field 'date' missing
   💡 Add 'date: <value>' to frontmatter
```

### Wiki System

The Python wiki system (`dev/wiki/`) handles generation, linting, sync, and publishing. The Lua plugin interacts with it via the `plm wiki` and `plm metadata` CLI commands:

- `plm wiki generate` — Generate wiki pages from database
- `plm wiki lint <path>` — Lint wiki files (returns JSON diagnostics)
- `plm wiki sync` — Bidirectional manuscript sync
- `plm metadata export/import` — YAML metadata file management
- `plm metadata list-entities` — Entity name lists for autocomplete

---

## Extending the Package

### Adding New Validators

1. **Create Python validator** in `dev/validators/`
2. **Add CLI command** in `dev/validators/cli/`
3. **Add Lua wrapper** in `validators.lua`:

```lua
function M.validate_custom(bufnr)
    bufnr = bufnr or vim.api.nvim_get_current_buf()
    local filepath = vim.api.nvim_buf_get_name(bufnr)

    vim.diagnostic.reset(ns, bufnr)

    local root = get_project_root()
    local cmd = string.format(
        "cd %s && python -m dev.validators.cli.custom %s 2>&1",
        vim.fn.shellescape(root),
        vim.fn.shellescape(filepath)
    )

    vim.fn.jobstart(cmd, {
        stdout_buffered = true,
        on_stdout = function(_, data)
            local output = table.concat(data, "\n")
            local diagnostics = parse_validation_output(output, bufnr)
            if #diagnostics > 0 then
                vim.diagnostic.set(ns, bufnr, diagnostics, {})
            end
        end,
    })
end
```

4. **Add autocmd** in `autocmds.lua`
5. **Add command** in `commands.lua`

### Adding New Entity Types

To add a new entity type to fzf-lua browse/search:

1. **Update `fzf.lua`** entity paths in both `browse()` and `search()` functions:

```lua
local entity_paths = {
    all = { journal_dir, wiki_dir },
    wiki = wiki_dir,
    journal = journal_dir,
    custom_entity = wiki_dir .. "/custom_entities",
    -- ...
}
```

2. **Update `commands.lua`** completion for both Browse and Search commands:

```lua
complete = function()
    return {
        "all",
        "wiki",
        "journal",
        "custom_entity",
        -- ...
    }
end
```

3. **Add keymap** in `keymaps.lua` (for both single and multiple vimwiki configs):

```lua
-- Single vimwiki
{ "<leader>vFx", "<cmd>lua require('palimpsest.fzf').browse('custom_entity')<cr>", desc = "Browse custom entities" },

-- Multiple vimwikis
{ "<leader>pFx", "<cmd>lua require('palimpsest.fzf').browse('custom_entity')<cr>", desc = "Browse custom entities" },
```

### Adding New Wiki Entity Types

To add a new wiki entity type to the export system:

1. **Create database model** in `dev/database/models/`
2. **Add export config** in `dev/wiki/configs.py`
3. **Create Jinja2 template** in `dev/wiki/templates/`
4. **Add to fzf-lua** browse/search (see "Adding New Entity Types" above)
5. **Update context.lua** PATH_PATTERNS if the entity has a wiki directory

---

## Testing

### Manual Testing

```vim
" Test fzf-lua browse
:PalimpsestBrowse journal
:PalimpsestBrowse all

" Test fzf-lua search
:PalimpsestSearch all
:PalimpsestSearch wiki
:PalimpsestSearch journal

" Test which-key keybindings
:WhichKey <leader>v
:WhichKey <leader>p

" Test validators
:PalimpsestValidateFrontmatter

" Check diagnostics
:lua vim.diagnostic.get(0)

" Check autocmds
:autocmd palimpsest_validators
```

### Debug Output

```vim
" Enable verbose logging
:set verbose=9

" Check messages
:messages

" Inspect variables
:lua print(vim.inspect(require('palimpsest.config').paths))

" Test Python subprocess
:!python -m dev.validators.cli.markdown frontmatter <filepath>
```

---

## Performance Considerations

### Async Execution

All Python subprocess calls use `vim.fn.jobstart()` with async callbacks to prevent editor blocking:

```lua
vim.fn.jobstart(cmd, {
    stdout_buffered = true,  -- Buffer output for efficiency
    on_stdout = function(_, data)
        -- Process in background
    end,
})
```

### Diagnostic Throttling

Validators run on `BufWritePost` (after save) rather than real-time to avoid performance issues with large files.

### File Pattern Matching

Autocmds use specific patterns to avoid unnecessary validation:

```lua
-- Only validate entry files
pattern = palimpsest.paths.wiki .. "/entries/**/*.md"

-- Skip log files
if not filepath:match("/log/") then
    validate()
end
```

---

## Error Handling

### Graceful Degradation

```lua
-- Check for fzf-lua availability
local has_fzf, fzf = pcall(require, "fzf-lua")
if not has_fzf then
    vim.notify("fzf-lua not found - browse/search disabled", vim.log.levels.ERROR)
    return
end

-- Check for which-key availability
local has_which_key, wk = pcall(require, "which-key")
if not has_which_key then
    vim.notify("which-key not found - keybindings will work but won't be discoverable", vim.log.levels.WARN)
    return
end
```

### Error Messages

Use appropriate log levels:

```lua
vim.notify("Validation passed", vim.log.levels.INFO)
vim.notify("Section not found", vim.log.levels.WARN)
vim.notify("Python validator failed", vim.log.levels.ERROR)
```

### Subprocess Errors

```lua
on_exit = function(_, exit_code)
    if exit_code ~= 0 then
        vim.notify("Validation failed", vim.log.levels.ERROR)
    else
        vim.diagnostic.reset(ns, bufnr)
    end
end
```

---

## Best Practices

1. **Async by Default** - Never block the editor with long-running operations
2. **Path Validation** - Always check paths exist before operations
3. **Error Handling** - Use `pcall()` for require statements
4. **User Feedback** - Provide clear notifications for user actions
5. **Pattern Specificity** - Use specific autocmd patterns to avoid performance issues
6. **Backend Separation** - Keep UI logic in Lua, data logic in Python
7. **Diagnostic API** - Use standard Neovim diagnostic API for consistency
8. **Discoverable Keybindings** - Use which-key.nvim for organized, searchable keybindings
9. **Multi-path Search** - When searching multiple directories with ripgrep, build the command properly with all paths

---

## See Also

- [fzf-lua Documentation](https://github.com/ibhagwan/fzf-lua)
- [which-key.nvim Documentation](https://github.com/folke/which-key.nvim)
- [Neovim Diagnostic API](https://neovim.io/doc/user/diagnostic.html)
- [ripgrep User Guide](https://github.com/BurntSushi/ripgrep/blob/master/GUIDE.md)
- [User Guide](../../user-guides/neovim-integration.md)
