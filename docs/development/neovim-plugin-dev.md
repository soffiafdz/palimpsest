# Neovim Package Development Guide

> **Note:** This plugin provides journal file browsing and search capabilities.
> Wiki features are not currently implemented.

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
└── vimwiki.lua       # VimWiki configuration
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

**Important:** Entity wiki pages (people, locations, events, themes) are **NOT** generated from templates. They are fully constructed by Python builders via `WikiEntity.to_wiki()` methods when `plm export-wiki` is run.

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
        { "<leader>pF", group = "browse entities" },
        { "<leader>pFa", "<cmd>lua require('palimpsest.fzf').browse('all')<cr>", desc = "Browse wiki" },
        { "<leader>pFj", "<cmd>lua require('palimpsest.fzf').browse('journal')<cr>", desc = "Browse journal" },
        { "<leader>p/", "<cmd>lua require('palimpsest.fzf').search('all')<cr>", desc = "Search all content" },
        { "<leader>p?w", "<cmd>lua require('palimpsest.fzf').search('wiki')<cr>", desc = "Search wiki" },
        { "<leader>p?j", "<cmd>lua require('palimpsest.fzf').search('journal')<cr>", desc = "Search journal" },
        -- ... more keybindings
    })
else
    -- Single vimwiki - use <leader>v prefix
    wk.add({
        { "<leader>v", group = "Palimpsest", icon = { icon = palimpsest_icon, color = "green" } },
        { "<leader>vF", group = "browse entities" },
        { "<leader>vFa", "<cmd>lua require('palimpsest.fzf').browse('all')<cr>", desc = "Browse wiki" },
        { "<leader>vFj", "<cmd>lua require('palimpsest.fzf').browse('journal')<cr>", desc = "Browse journal" },
        { "<leader>v/", "<cmd>lua require('palimpsest.fzf').search('all')<cr>", desc = "Search all content" },
        { "<leader>v?w", "<cmd>lua require('palimpsest.fzf').search('wiki')<cr>", desc = "Search wiki" },
        { "<leader>v?j", "<cmd>lua require('palimpsest.fzf').search('journal')<cr>", desc = "Search journal" },
        -- ... more keybindings
    })
end
```

**Benefits:**
- Discoverable keybindings via which-key popup menus
- Grouped keybindings with visual hierarchy
- Icons and descriptions for better UX

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

### Wiki Page Generation

Wiki pages are **NOT** generated from templates. They are fully constructed by Python builders.

**How SQL→Wiki Export Works:**

1. User runs `plm export-wiki [entity_type]`
2. Python `GenericEntityExporter.export_all()` queries database
3. For each database entity, calls `WikiEntity.from_database(db_entity, wiki_dir, journal_dir)`
4. WikiEntity dataclass constructs complete page via `to_wiki()` method
5. `to_wiki()` generates all sections including "Appearances", "Related Entries", etc.
6. Complete markdown content written to wiki file

**Example flow for Person entity:**

```python
# In GenericEntityExporter.export_single()
wiki_entity = Person.from_database(db_person, wiki_dir, journal_dir)
content = "\n".join(wiki_entity.to_wiki())  # Generates entire page
write_if_changed(wiki_entity.path, content, force)
```

The `to_wiki()` method in each WikiEntity dataclass (Person, Location, Event, Theme, etc.) contains all the logic for generating the complete wiki page including database queries for related entries, appearances, etc.

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

1. **Create database model** in `dev/database/models.py`
2. **Create WikiEntity dataclass** in `dev/dataclasses/wiki_*.py`:
   - Implement `from_database(db_entity, wiki_dir, journal_dir)` classmethod
   - Implement `to_wiki()` method that generates complete markdown
3. **Register entity** in SQL→Wiki pipeline with `EntityConfig`
4. **Add to fzf-lua** browse/search (see "Adding New Entity Types" above)

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
