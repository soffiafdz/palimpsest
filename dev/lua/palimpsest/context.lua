-- Context detection for Palimpsest wiki pages
--
-- Detects entity type, section, and slug from wiki file paths.
-- Used by entity commands and keymaps to provide context-sensitive
-- behavior based on which wiki page is currently open.
local M = {}

-- Path patterns mapping subdirectory to entity info
local PATH_PATTERNS = {
	-- Journal entities
	{ pattern = "journal/entries/", type = "entry", section = "journal" },
	{ pattern = "journal/people/", type = "person", section = "journal" },
	{ pattern = "journal/locations/", type = "location", section = "journal" },
	{ pattern = "journal/cities/", type = "city", section = "journal" },
	{ pattern = "journal/events/", type = "event", section = "journal" },
	{ pattern = "journal/arcs/", type = "arc", section = "journal" },
	{ pattern = "journal/tags/", type = "tag", section = "journal" },
	{ pattern = "journal/themes/", type = "theme", section = "journal" },
	{ pattern = "journal/poems/", type = "poem", section = "journal" },
	{ pattern = "journal/references/", type = "reference", section = "journal" },
	{ pattern = "journal/motifs/", type = "motif", section = "journal" },
	-- Manuscript entities
	{ pattern = "manuscript/chapters/", type = "chapter", section = "manuscript" },
	{ pattern = "manuscript/characters/", type = "character", section = "manuscript" },
	{ pattern = "manuscript/scenes/", type = "scene", section = "manuscript" },
	-- Index pages
	{ pattern = "indexes/", type = "index", section = "indexes" },
}

--- Detect context from a wiki file path.
---
--- Analyzes the file path to determine what type of entity page
--- is currently open, which section it belongs to, and the entity
--- slug from the filename.
---
--- @param filepath string|nil File path (defaults to current buffer)
--- @return table|nil Context table with type, section, slug keys, or nil
function M.detect(filepath)
	filepath = filepath or vim.fn.expand("%:p")
	if not filepath or filepath == "" then
		return nil
	end

	-- Normalize path separators
	filepath = filepath:gsub("\\", "/")

	for _, pat in ipairs(PATH_PATTERNS) do
		local idx = filepath:find(pat.pattern, 1, true)
		if idx then
			-- Extract slug from filename (without extension)
			local after_pattern = filepath:sub(idx + #pat.pattern)
			local slug = after_pattern:match("([^/]+)%.md$")
			return {
				type = pat.type,
				section = pat.section,
				slug = slug,
			}
		end
	end

	-- Check for main index
	if filepath:match("wiki/index%.md$") then
		return { type = "index", section = "main", slug = "index" }
	end

	return nil
end

--- Get available commands for the current context.
---
--- Returns a list of command names that are valid for the detected
--- entity type and section. Used for context-sensitive command menus.
---
--- @param context table|nil Context from detect()
--- @return table List of available command name strings
function M.available_commands(context)
	local commands = { "PalimpsestSync", "PalimpsestGenerate" }

	if not context then
		return commands
	end

	-- Always available for any wiki page
	table.insert(commands, "PalimpsestLint")

	-- Entity types with metadata YAML (includes all manuscript types)
	local yaml_types = {
		entry = true,
		person = true,
		location = true,
		city = true,
		arc = true,
		chapter = true,
		character = true,
		scene = true,
	}
	if yaml_types[context.type] then
		table.insert(commands, "PalimpsestEdit")
	end

	return commands
end

--- Check if the current buffer is a wiki page.
---
--- @return boolean True if current buffer is inside the wiki directory
function M.is_wiki_page()
	local filepath = vim.fn.expand("%:p")
	return filepath:find("data/wiki/", 1, true) ~= nil
end

--- Get entity type suitable for metadata commands.
---
--- Maps context types to the entity type keys used by the
--- plm metadata CLI commands.
---
--- @param context table Context from detect()
--- @return string|nil Entity type key for metadata commands
function M.metadata_type(context)
	if not context then
		return nil
	end

	local type_map = {
		person = "people",
		location = "locations",
		city = "cities",
		arc = "arcs",
		chapter = "chapters",
		character = "characters",
		scene = "scenes",
	}

	return type_map[context.type]
end

return M
