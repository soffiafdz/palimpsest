# Neovim Package Development Guide

Technical documentation for developing and extending the Palimpsest Neovim integration package.

## Package Structure

```
dev/lua/palimpsest/
├── init.lua          # Entry point and setup
├── config.lua        # Configuration and paths
├── telescope.lua     # Telescope extension
├── validators.lua    # Validation integration
├── templates.lua     # Template system
├── autocmds.lua      # Autocommands
├── commands.lua      # User commands
├── keymaps.lua       # Key bindings
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

    -- Load telescope extension
    local has_telescope, telescope = pcall(require, "telescope")
    if has_telescope then
        telescope.load_extension("palimpsest")
    end
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

### telescope.lua

Telescope extension implementation following the official Telescope extension API:

**Key Functions:**
- `M.browse(entity_type)` - Browse files by entity type
- `M.search(entity_type)` - Search content with live_grep
- `M.quick_access()` - Custom picker for special pages
- `M.setup(ext_config, config)` - Extension registration (called by Telescope)

**Extension Structure:**
```lua
function M.setup(ext_config, config)
    return {
        exports = {
            palimpsest = M.quick_access,
            browse = function(opts)
                local entity_type = opts.entity or "all"
                M.browse(entity_type)
            end,
            search = function(opts)
                local entity_type = opts.entity or "all"
                M.search(entity_type)
            end,
        },
    }
end
```

### validators.lua

Async validation integration with Python backend:

**Architecture:**
1. Runs Python validators via `vim.fn.jobstart()`
2. Parses output (stdout/stderr)
3. Converts to Neovim diagnostics
4. Displays via diagnostic API

**Key Functions:**
- `M.validate_frontmatter(bufnr)` - YAML frontmatter validation
- `M.validate_metadata(bufnr)` - Metadata field validation
- `M.validate_links(bufnr)` - Link validation

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
    require("palimpsest.telescope").browse(entity_type)
end, {
    nargs = "?",
    desc = "Browse wiki entities with Telescope",
    complete = function()
        return { "all", "journal", "people", ... }
    end,
})
```

### keymaps.lua

Key binding registration using `which-key.nvim`:

**Dual Configuration:**
- Single vimwiki → `<leader>v` prefix
- Multiple vimwikis → `<leader>p` prefix

**Structure:**
```lua
wk.add({
    { "<leader>pF", group = "browse entities" },
    { "<leader>pFa", "<cmd>lua require('palimpsest.telescope').browse('all')<cr>", desc = "Browse wiki" },
    { "<leader>pFj", "<cmd>lua require('palimpsest.telescope').browse('journal')<cr>", desc = "Browse journal" },
    -- ...
})
```

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

To add a new entity type to Telescope:

1. **Update `telescope.lua`** entity paths:

```lua
local entity_paths = {
    all = wiki_dir,
    journal = journal_dir,
    custom_entity = wiki_dir .. "/custom_entities",
    -- ...
}
```

2. **Update `commands.lua`** completion:

```lua
complete = function()
    return {
        "all",
        "journal",
        "custom_entity",
        -- ...
    }
end
```

3. **Add keymap** in `keymaps.lua`:

```lua
{ "<leader>pFx", "<cmd>lua require('palimpsest.telescope').browse('custom_entity')<cr>", desc = "Browse custom entities" },
```

### Adding New Wiki Entity Types

To add a new wiki entity type to the export system:

1. **Create database model** in `dev/database/models.py`
2. **Create WikiEntity dataclass** in `dev/dataclasses/wiki_*.py`:
   - Implement `from_database(db_entity, wiki_dir, journal_dir)` classmethod
   - Implement `to_wiki()` method that generates complete markdown
3. **Register entity** in SQL→Wiki pipeline with `EntityConfig`
4. **Add to Telescope** entity paths (see "Adding New Entity Types" above)

---

## Testing

### Manual Testing

```vim
" Test Telescope browse
:PalimpsestBrowse journal

" Test search
:PalimpsestSearch all

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
-- Check for Telescope availability
local has_telescope, telescope = pcall(require, "telescope")
if not has_telescope then
    vim.notify("Telescope not found - features disabled", vim.log.levels.WARN)
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
8. **Extension Compliance** - Follow Telescope extension API standards

---

## See Also

- [Telescope Extension API](https://github.com/nvim-telescope/telescope.nvim/blob/master/developers.md)
- [Neovim Diagnostic API](https://neovim.io/doc/user/diagnostic.html)
- [User Guide](../user-guides/neovim-integration.md)
