-- Entity commands for Palimpsest wiki pages
--
-- Provides context-aware entity editing commands that detect
-- the current wiki page type and open the corresponding YAML
-- metadata file in a floating window. Supports creating new
-- entities, editing existing ones, and guided insertions.
local M = {}

local context_mod = require("palimpsest.context")
local float = require("palimpsest.float")
local cache = require("palimpsest.cache")
local get_project_root = require("palimpsest.utils").get_project_root

--- Strip accents from UTF-8 text, replacing with ASCII base characters.
---
--- @param text string UTF-8 input
--- @return string ASCII-normalized text
local function strip_accents(text)
	local map = {
		a = "àáâãäåÀÁÂÃÄÅ",
		e = "èéêëÈÉÊË",
		i = "ìíîïÌÍÎÏ",
		o = "òóôõöÒÓÔÕÖ",
		u = "ùúûüÙÚÛÜ",
		n = "ñÑ",
		c = "çÇ",
	}
	for plain, accented in pairs(map) do
		for char in accented:gmatch("[%z\1-\127\194-\244][\128-\191]*") do
			text = text:gsub(char, plain)
		end
	end
	return text
end

-- Map entity type to YAML directory relative to data/metadata/
local YAML_PATHS = {
	person = "people",
	location = "locations",
	chapter = "manuscript/chapters",
	character = "manuscript/characters",
	scene = "manuscript/scenes",
}

-- Map entity type to single-file YAML path
local YAML_FILES = {
	city = "cities.yaml",
	arc = "arcs.yaml",
}

-- Map context type to curation YAML file
local CURATION_FILES = {
	location = "neighborhoods.yaml",
	city = "neighborhoods.yaml",
	person = "relation_types.yaml",
}

--- Resolve the YAML path for the current entity.
---
--- @param ctx table Context from context.detect()
--- @return string|nil Absolute path to the YAML file
local function resolve_yaml_path(ctx)
	if not ctx or not ctx.slug then
		return nil
	end

	local root = get_project_root()
	local base = root .. "/data/metadata/"

	-- Entry metadata: slug is YYYY-MM-DD, YAML at journal/YYYY/YYYY-MM-DD.yaml
	if ctx.type == "entry" then
		local year = ctx.slug:sub(1, 4)
		return base .. "journal/" .. year .. "/" .. ctx.slug .. ".yaml"
	end

	-- Per-entity file
	if YAML_PATHS[ctx.type] then
		return base .. YAML_PATHS[ctx.type] .. "/" .. ctx.slug .. ".yaml"
	end

	-- Single-file (city, arc)
	if YAML_FILES[ctx.type] then
		return base .. YAML_FILES[ctx.type]
	end

	return nil
end

--- Edit the metadata for the current wiki page entity.
---
--- Detects context from the current buffer, resolves the YAML
--- metadata file path, and opens it in a floating window.
function M.edit()
	local ctx = context_mod.detect()
	if not ctx then
		vim.notify("Not on a wiki entity page", vim.log.levels.WARN)
		return
	end

	local yaml_path = resolve_yaml_path(ctx)
	if not yaml_path then
		vim.notify(
			"No metadata file for entity type: " .. (ctx.type or "unknown"),
			vim.log.levels.WARN
		)
		return
	end

	-- Check if file exists
	if vim.fn.filereadable(yaml_path) == 0 then
		vim.notify(
			"Metadata file not found: " .. yaml_path .. "\nRun :PalimpsestMetadataExport first",
			vim.log.levels.WARN
		)
		return
	end

	local title = string.format(" %s: %s ", ctx.type, ctx.slug or "")
	float.open(yaml_path, { title = title })
end

--- Edit the curation file for the current page's entity type.
---
--- Opens neighborhoods.yaml when on a location or city page,
--- relation_types.yaml when on a person page.
function M.edit_curation()
	local ctx = context_mod.detect()
	if not ctx then
		vim.notify("Not on a wiki entity page", vim.log.levels.WARN)
		return
	end

	local curation_file = CURATION_FILES[ctx.type]
	if not curation_file then
		vim.notify(
			"No curation file for entity type: " .. (ctx.type or "unknown"),
			vim.log.levels.WARN
		)
		return
	end

	local root = get_project_root()
	local yaml_path = root .. "/data/metadata/" .. curation_file

	if vim.fn.filereadable(yaml_path) == 0 then
		vim.notify(
			"Curation file not found: " .. yaml_path .. "\nRun :PalimpsestMetadataExport first",
			vim.log.levels.WARN
		)
		return
	end

	local title = string.format(" %s ", curation_file)
	float.open(yaml_path, { title = title })
end

--- Create a new entity of the given type.
---
--- Creates a template YAML file and opens it in a floating window
--- for the user to fill in.
---
--- @param entity_type string Entity type (people, chapters, etc.)
function M.new(entity_type)
	local root = get_project_root()
	local base = root .. "/data/metadata/"

	-- Generate template based on type
	local templates = {
		people = "name: \nlastname: \nrelation_type: friend\n",
		chapters = "title: \nnumber: \ndate:   # YYYY-MM-DD (when the chapter is set)\ntype: prose  # prose | vignette | poem\nstatus: draft  # draft | revised | final\ndraft_path: \n",
		characters = "name: \nrole: \nis_narrator: false\ndescription: \n",
		scenes = "name: \nchapter: \norigin: journaled  # journaled | inferred | invented | composite\nstatus: fragment  # fragment | draft | included | cut\ndescription: \ncharacters:\nnotes:\n",
	}

	-- Prompt for type if not provided
	if not entity_type then
		local types = vim.tbl_keys(templates)
		table.sort(types)
		vim.ui.select(types, { prompt = "Entity type:" }, function(choice)
			if choice then
				M.new(choice)
			end
		end)
		return
	end

	local template = templates[entity_type]
	if not template then
		vim.notify("Cannot create entity of type: " .. entity_type, vim.log.levels.WARN)
		return
	end

	-- Prompt for name
	vim.ui.input({ prompt = "Entity name: " }, function(name)
		if not name or name == "" then
			return
		end

		-- Generate slug: normalize accents, then ASCII-safe
		local slug = strip_accents(name):lower():gsub("%s+", "-"):gsub("[^%w%-]", ""):gsub("%-+", "-"):gsub("^%-+", ""):gsub("%-+$", "")

		-- Determine file path (reuse YAML_PATHS with plural→singular key mapping)
		local type_to_path = {
			people = YAML_PATHS.person,
			chapters = YAML_PATHS.chapter,
			characters = YAML_PATHS.character,
			scenes = YAML_PATHS.scene,
		}
		local dir = base .. (type_to_path[entity_type] or entity_type)
		local filepath = dir .. "/" .. slug .. ".yaml"

		-- Create directory and write template
		vim.fn.mkdir(dir, "p")
		local content = template:gsub("name: \n", "name: " .. name .. "\n", 1)
			:gsub("title: \n", "title: " .. name .. "\n", 1)

		-- For chapters, create draft file and set draft_path
		if entity_type == "chapters" then
			local draft_rel = "data/manuscript/drafts/" .. slug .. ".md"
			content = content:gsub("draft_path: \n", "draft_path: " .. draft_rel .. "\n", 1)
			local draft_dir = root .. "/data/manuscript/drafts"
			vim.fn.mkdir(draft_dir, "p")
			local draft_path = draft_dir .. "/" .. slug .. ".md"
			if vim.fn.filereadable(draft_path) == 0 then
				local df = io.open(draft_path, "w")
				if df then
					df:write("# " .. name .. "\n\n")
					df:close()
				end
			end
		end

		local f = io.open(filepath, "w")
		if f then
			f:write(content)
			f:close()
		end

		float.open(filepath, {
			title = string.format(" New %s ", entity_type),
		})

		-- For scenes, prompt to select a chapter after the float opens
		if entity_type == "scenes" then
			vim.defer_fn(function()
				local chapters = cache.get("chapters")
				if #chapters == 0 then
					return
				end
				vim.ui.select(chapters, { prompt = "Chapter (Esc to skip):" }, function(chapter)
					if not chapter then
						return
					end
					-- Replace the empty chapter field in the file
					local lines = vim.fn.readfile(filepath)
					for i, line in ipairs(lines) do
						if line:match("^chapter: *$") then
							lines[i] = "chapter: " .. chapter
							vim.fn.writefile(lines, filepath)
							-- Reload the buffer if it's still open
							local buf = vim.fn.bufnr(filepath)
							if buf ~= -1 and vim.api.nvim_buf_is_valid(buf) then
								vim.api.nvim_buf_call(buf, function()
									vim.cmd("edit!")
								end)
							end
							break
						end
					end
				end)
			end, 100)
		end
	end)
end

--- Write source lines into a scene YAML file.
---
--- Handles finding or creating the sources: section and appending
--- the new source entry.
---
--- @param yaml_path string Path to the scene YAML file
--- @param source_lines table List of YAML lines to insert
--- @param source_type string Source type name for notification
--- @param label string Display label for notification
local function write_source_to_yaml(yaml_path, source_lines, source_type, label)
	local lines = vim.fn.readfile(yaml_path)
	local found_sources = false
	for i, line in ipairs(lines) do
		if line:match("^sources:") then
			found_sources = true
			if line:match("^sources: *$") or line:match("^sources: *null") then
				lines[i] = "sources:"
				local insert_at = i + 1
				for _, sl in ipairs(source_lines) do
					table.insert(lines, insert_at, sl)
					insert_at = insert_at + 1
				end
			else
				local insert_at = i + 1
				while insert_at <= #lines and lines[insert_at]:match("^%s") do
					insert_at = insert_at + 1
				end
				for j, sl in ipairs(source_lines) do
					table.insert(lines, insert_at + j - 1, sl)
				end
			end
			break
		end
	end

	if not found_sources then
		table.insert(lines, "sources:")
		for _, sl in ipairs(source_lines) do
			table.insert(lines, sl)
		end
	end

	vim.fn.writefile(lines, yaml_path)
	vim.notify(
		string.format("Added source: %s — %s", source_type, label),
		vim.log.levels.INFO
	)
end

--- Add a source entry to a manuscript scene YAML.
---
--- Provides guided insertion with cache-backed pickers for
--- entries, scenes, and threads. External sources use free-text input.
function M.add_source()
	local ctx = context_mod.detect()
	if not ctx or ctx.type ~= "scene" then
		vim.notify("Must be on a manuscript scene page", vim.log.levels.WARN)
		return
	end

	-- Select source type
	vim.ui.select(
		{ "entry", "scene", "thread", "external" },
		{ prompt = "Source type:" },
		function(source_type)
			if not source_type then
				return
			end

			local yaml_path = resolve_yaml_path(ctx)
			if not yaml_path or vim.fn.filereadable(yaml_path) == 0 then
				vim.notify("Scene YAML not found", vim.log.levels.ERROR)
				return
			end

			if source_type == "entry" then
				local entries = cache.get("entries")
				if #entries == 0 then
					vim.notify("No entries cached. Try :PalimpsestCacheRefresh", vim.log.levels.WARN)
					return
				end
				vim.ui.select(entries, { prompt = "Entry date:" }, function(entry_date)
					if not entry_date then
						return
					end
					write_source_to_yaml(yaml_path, {
						"  - source_type: entry",
						"    entry_date: " .. entry_date,
					}, "entry", entry_date)
				end)

			elseif source_type == "scene" then
				local scenes = cache.get("journal_scenes")
				if #scenes == 0 then
					vim.notify("No journal scenes cached. Try :PalimpsestCacheRefresh", vim.log.levels.WARN)
					return
				end
				vim.ui.select(scenes, { prompt = "Journal scene:" }, function(choice)
					if not choice then
						return
					end
					-- Parse "Name::YYYY-MM-DD"
					local name, entry_date = choice:match("^(.+)::(%d%d%d%d%-%d%d%-%d%d)$")
					if not name or not entry_date then
						vim.notify("Invalid scene format: " .. choice, vim.log.levels.ERROR)
						return
					end
					write_source_to_yaml(yaml_path, {
						"  - source_type: scene",
						"    entry_date: " .. entry_date,
						"    scene_name: " .. name,
					}, "scene", choice)
				end)

			elseif source_type == "thread" then
				local threads = cache.get("threads")
				if #threads == 0 then
					vim.notify("No threads cached. Try :PalimpsestCacheRefresh", vim.log.levels.WARN)
					return
				end
				vim.ui.select(threads, { prompt = "Thread:" }, function(choice)
					if not choice then
						return
					end
					-- Parse "Name::YYYY-MM-DD"
					local name, entry_date = choice:match("^(.+)::(%d%d%d%d%-%d%d%-%d%d)$")
					if not name or not entry_date then
						vim.notify("Invalid thread format: " .. choice, vim.log.levels.ERROR)
						return
					end
					write_source_to_yaml(yaml_path, {
						"  - source_type: thread",
						"    entry_date: " .. entry_date,
						"    thread_name: " .. name,
					}, "thread", choice)
				end)

			elseif source_type == "external" then
				vim.ui.input({ prompt = "External note: " }, function(note)
					if not note or note == "" then
						return
					end
					write_source_to_yaml(yaml_path, {
						"  - source_type: external",
						"    note: " .. note,
					}, "external", note)
				end)
			end
		end
	)
end

--- Add a based_on person mapping to a character YAML.
---
--- Provides guided insertion with autocomplete for person names.
function M.add_based_on()
	local ctx = context_mod.detect()
	if not ctx or ctx.type ~= "character" then
		vim.notify("Must be on a character page", vim.log.levels.WARN)
		return
	end

	local people = cache.get("people")
	if #people == 0 then
		vim.notify("No people cached. Try :PalimpsestCacheRefresh", vim.log.levels.WARN)
		return
	end

	vim.ui.select(people, { prompt = "Person:" }, function(person)
		if not person then
			return
		end

		vim.ui.select(
			{ "primary", "composite", "inspiration" },
			{ prompt = "Contribution:" },
			function(contribution)
				if not contribution then
					return
				end

				local yaml_path = resolve_yaml_path(ctx)
				if not yaml_path or vim.fn.filereadable(yaml_path) == 0 then
					vim.notify("Character YAML not found", vim.log.levels.ERROR)
					return
				end

				-- Read existing YAML, append based_on entry
				local lines = vim.fn.readfile(yaml_path)
				local new_entry = string.format("  - person: %s\n    contribution: %s", person, contribution)

				-- Find existing based_on section or add one
				local found_based_on = false
				for i, line in ipairs(lines) do
					if line:match("^based_on:") then
						found_based_on = true
						if line:match("^based_on: *$") or line:match("^based_on: *null") then
							-- Replace null/empty with list
							lines[i] = "based_on:"
							table.insert(lines, i + 1, "  - person: " .. person)
							table.insert(lines, i + 2, "    contribution: " .. contribution)
						else
							-- Append after last based_on entry
							local insert_at = i + 1
							while insert_at <= #lines and lines[insert_at]:match("^%s") do
								insert_at = insert_at + 1
							end
							table.insert(lines, insert_at, "  - person: " .. person)
							table.insert(lines, insert_at + 1, "    contribution: " .. contribution)
						end
						break
					end
				end

				if not found_based_on then
					table.insert(lines, "based_on:")
					table.insert(lines, "  - person: " .. person)
					table.insert(lines, "    contribution: " .. contribution)
				end

				vim.fn.writefile(lines, yaml_path)
				vim.notify(
					string.format("Added based_on: %s (%s)", person, contribution),
					vim.log.levels.INFO
				)
			end
		)
	end)
end

--- Set or change the chapter for a manuscript scene YAML.
---
--- Provides a picker for chapter selection from cached chapters.
--- Works from scene wiki pages or scene YAML files.
function M.set_chapter()
	local ctx = context_mod.detect()
	if not ctx or ctx.type ~= "scene" then
		vim.notify("Must be on a scene page", vim.log.levels.WARN)
		return
	end

	local chapters = cache.get("chapters")
	if #chapters == 0 then
		vim.notify("No chapters cached. Try :PalimpsestCacheRefresh", vim.log.levels.WARN)
		return
	end

	vim.ui.select(chapters, { prompt = "Chapter:" }, function(chapter)
		if not chapter then
			return
		end

		local yaml_path = resolve_yaml_path(ctx)
		if not yaml_path or vim.fn.filereadable(yaml_path) == 0 then
			vim.notify("Scene YAML not found", vim.log.levels.ERROR)
			return
		end

		local lines = vim.fn.readfile(yaml_path)
		local found = false
		for i, line in ipairs(lines) do
			if line:match("^chapter:") then
				lines[i] = "chapter: " .. chapter
				found = true
				break
			end
		end

		if not found then
			table.insert(lines, 2, "chapter: " .. chapter)
		end

		vim.fn.writefile(lines, yaml_path)
		vim.notify(
			string.format("Set chapter: %s", chapter),
			vim.log.levels.INFO
		)

		-- Reload buffer if open
		local buf = vim.fn.bufnr(yaml_path)
		if buf ~= -1 and vim.api.nvim_buf_is_valid(buf) then
			vim.api.nvim_buf_call(buf, function()
				vim.cmd("edit!")
			end)
		end
	end)
end

--- Add a character to a scene YAML.
---
--- Provides a picker for character selection from cached characters.
--- Works from scene wiki pages or scene YAML files.
function M.add_character()
	local ctx = context_mod.detect()
	if not ctx or ctx.type ~= "scene" then
		vim.notify("Must be on a scene page", vim.log.levels.WARN)
		return
	end

	local characters = cache.get("characters")
	if #characters == 0 then
		vim.notify("No characters cached. Try :PalimpsestCacheRefresh", vim.log.levels.WARN)
		return
	end

	vim.ui.select(characters, { prompt = "Character:" }, function(character)
		if not character then
			return
		end

		local yaml_path = resolve_yaml_path(ctx)
		if not yaml_path or vim.fn.filereadable(yaml_path) == 0 then
			vim.notify("Scene YAML not found", vim.log.levels.ERROR)
			return
		end

		local lines = vim.fn.readfile(yaml_path)
		local found_characters = false
		for i, line in ipairs(lines) do
			if line:match("^characters:") then
				found_characters = true
				if line:match("^characters: *$") or line:match("^characters: *null") then
					lines[i] = "characters:"
					table.insert(lines, i + 1, "  - " .. character)
				else
					-- Append after last characters entry
					local insert_at = i + 1
					while insert_at <= #lines and lines[insert_at]:match("^%s+%-") do
						-- Check for duplicate
						if lines[insert_at]:match("^%s+%-%s+" .. vim.pesc(character) .. "$") then
							vim.notify("Character already in scene", vim.log.levels.WARN)
							return
						end
						insert_at = insert_at + 1
					end
					table.insert(lines, insert_at, "  - " .. character)
				end
				break
			end
		end

		if not found_characters then
			table.insert(lines, "characters:")
			table.insert(lines, "  - " .. character)
		end

		vim.fn.writefile(lines, yaml_path)
		vim.notify(
			string.format("Added character: %s", character),
			vim.log.levels.INFO
		)

		-- Reload buffer if open
		local buf = vim.fn.bufnr(yaml_path)
		if buf ~= -1 and vim.api.nvim_buf_is_valid(buf) then
			vim.api.nvim_buf_call(buf, function()
				vim.cmd("edit!")
			end)
		end
	end)
end

--- Add a scene to the current chapter.
---
--- From a chapter context, presents a picker of manuscript scenes
--- and sets the selected scene's chapter field to this chapter.
function M.add_scene()
	local ctx = context_mod.detect()
	if not ctx or ctx.type ~= "chapter" then
		vim.notify("Must be on a chapter page", vim.log.levels.WARN)
		return
	end

	local scenes = cache.get("scenes")
	if #scenes == 0 then
		vim.notify("No scenes cached. Try :PalimpsestCacheRefresh", vim.log.levels.WARN)
		return
	end

	vim.ui.select(scenes, { prompt = "Scene to add:" }, function(scene_name)
		if not scene_name then
			return
		end

		-- Resolve scene YAML path
		local root = get_project_root()
		local scene_slug = strip_accents(scene_name):lower()
			:gsub("%s+", "-"):gsub("[^%w%-]", "")
			:gsub("%-+", "-"):gsub("^%-+", ""):gsub("%-+$", "")
		local scene_yaml = root .. "/data/metadata/manuscript/scenes/" .. scene_slug .. ".yaml"

		if vim.fn.filereadable(scene_yaml) == 0 then
			vim.notify("Scene YAML not found: " .. scene_yaml, vim.log.levels.ERROR)
			return
		end

		-- Get chapter title from current page YAML
		local chapter_yaml = resolve_yaml_path(ctx)
		if not chapter_yaml or vim.fn.filereadable(chapter_yaml) == 0 then
			vim.notify("Chapter YAML not found", vim.log.levels.ERROR)
			return
		end

		local ch_lines = vim.fn.readfile(chapter_yaml)
		local chapter_title = nil
		for _, line in ipairs(ch_lines) do
			local val = line:match("^title:%s*(.+)$")
			if val then
				chapter_title = val
				break
			end
		end

		if not chapter_title then
			vim.notify("Could not read chapter title", vim.log.levels.ERROR)
			return
		end

		-- Update scene YAML's chapter field
		local lines = vim.fn.readfile(scene_yaml)
		local found = false
		for i, line in ipairs(lines) do
			if line:match("^chapter:") then
				lines[i] = "chapter: " .. chapter_title
				found = true
				break
			end
		end

		if not found then
			table.insert(lines, 2, "chapter: " .. chapter_title)
		end

		vim.fn.writefile(lines, scene_yaml)
		vim.notify(
			string.format("Added scene: %s → %s", scene_name, chapter_title),
			vim.log.levels.INFO
		)
	end)
end

--- Open source materials related to current manuscript entity.
---
--- For chapters: opens the draft file in a vertical split.
--- For scenes: opens linked journal entries from YAML sources.
function M.open_sources()
	local ctx = context_mod.detect()
	if not ctx then
		vim.notify("Not on a manuscript page", vim.log.levels.WARN)
		return
	end

	local root = get_project_root()
	local yaml_path = resolve_yaml_path(ctx)
	if not yaml_path or vim.fn.filereadable(yaml_path) == 0 then
		vim.notify("YAML not found for this entity", vim.log.levels.WARN)
		return
	end

	local lines = vim.fn.readfile(yaml_path)

	if ctx.type == "chapter" then
		-- Open draft file
		for _, line in ipairs(lines) do
			local draft = line:match("^draft_path:%s*(.+)$")
			if draft and draft ~= "" then
				local draft_abs = root .. "/" .. draft
				if vim.fn.filereadable(draft_abs) == 1 then
					vim.cmd("vsplit " .. draft_abs)
				else
					vim.notify("Draft file not found: " .. draft, vim.log.levels.WARN)
				end
				return
			end
		end
		vim.notify("No draft_path set in chapter YAML", vim.log.levels.WARN)

	elseif ctx.type == "scene" then
		-- Collect entry dates from sources section
		local dates = {}
		local in_sources = false
		for _, line in ipairs(lines) do
			if line:match("^sources:") then
				in_sources = true
			elseif in_sources then
				if not line:match("^%s") then
					break -- Left sources section
				end
				local entry_date = line:match("entry_date:%s*(%d%d%d%d%-%d%d%-%d%d)")
				if entry_date then
					table.insert(dates, entry_date)
				end
			end
		end

		if #dates == 0 then
			vim.notify("No journal sources in scene YAML", vim.log.levels.WARN)
			return
		end

		-- Open each entry in a split
		for i, d in ipairs(dates) do
			local year = d:sub(1, 4)
			local md_path = root .. "/data/journal/content/md/" .. year .. "/" .. d .. ".md"
			if vim.fn.filereadable(md_path) == 1 then
				if i == 1 then
					vim.cmd("vsplit " .. md_path)
				else
					vim.cmd("split " .. md_path)
				end
			else
				vim.notify("Entry not found: " .. d, vim.log.levels.WARN)
			end
		end
	else
		vim.notify("Open sources only works on chapter/scene pages", vim.log.levels.WARN)
	end
end

--- Rename current entity (any per-file YAML type).
---
--- Renames the YAML file and updates the name/title field.
--- Type-specific propagation:
---   chapter: renames draft file, updates draft_path, updates scene chapter refs
---   character: updates chapter characters lists
---   person/location/scene: file + field only
function M.rename()
	local ctx = context_mod.detect()
	if not ctx then
		vim.notify("Not on an entity page", vim.log.levels.WARN)
		return
	end

	-- Only per-file entity types can be renamed
	if not YAML_PATHS[ctx.type] then
		vim.notify("Rename not available for " .. (ctx.type or "unknown"), vim.log.levels.WARN)
		return
	end

	local root = get_project_root()
	local old_yaml = resolve_yaml_path(ctx)
	if not old_yaml or vim.fn.filereadable(old_yaml) == 0 then
		vim.notify("YAML not found for this entity", vim.log.levels.WARN)
		return
	end

	-- Read current name for the prompt
	local lines = vim.fn.readfile(old_yaml)
	local current_name = ""
	local name_field = ctx.type == "chapter" and "title" or "name"
	for _, line in ipairs(lines) do
		local val = line:match("^" .. name_field .. ":%s*(.+)$")
		if val then
			current_name = val
			break
		end
	end

	vim.ui.input({ prompt = "New name: ", default = current_name }, function(new_name)
		if not new_name or new_name == "" or new_name == current_name then
			return
		end

		local new_slug = strip_accents(new_name):lower()
			:gsub("%s+", "-"):gsub("[^%w%-]", "")
			:gsub("%-+", "-"):gsub("^%-+", ""):gsub("%-+$", "")
		local old_slug = vim.fn.fnamemodify(old_yaml, ":t:r")

		if new_slug == old_slug then
			-- Only name changed, not slug — just update the field
			for i, line in ipairs(lines) do
				if line:match("^" .. name_field .. ":") then
					lines[i] = name_field .. ": " .. new_name
					break
				end
			end
			vim.fn.writefile(lines, old_yaml)
			vim.notify("Name updated (slug unchanged)", vim.log.levels.INFO)
			vim.cmd("edit!")
			return
		end

		-- Build new paths
		local yaml_dir = vim.fn.fnamemodify(old_yaml, ":h")
		local new_yaml = yaml_dir .. "/" .. new_slug .. ".yaml"

		if vim.fn.filereadable(new_yaml) == 1 then
			vim.notify("Target already exists: " .. new_slug .. ".yaml", vim.log.levels.ERROR)
			return
		end

		-- Update name/title field
		for i, line in ipairs(lines) do
			if line:match("^" .. name_field .. ":") then
				lines[i] = name_field .. ": " .. new_name
				break
			end
		end

		-- Chapter: rename draft file, update draft_path, update scene refs
		if ctx.type == "chapter" then
			for i, line in ipairs(lines) do
				local old_draft = line:match("^draft_path:%s*(.+)$")
				if old_draft and old_draft ~= "" then
					local new_draft_rel = "data/manuscript/drafts/" .. new_slug .. ".md"
					local old_draft_abs = root .. "/" .. old_draft
					local new_draft_abs = root .. "/" .. new_draft_rel
					if vim.fn.filereadable(old_draft_abs) == 1 then
						vim.fn.rename(old_draft_abs, new_draft_abs)
					end
					lines[i] = "draft_path: " .. new_draft_rel
					break
				end
			end

			local scene_dir = root .. "/data/metadata/manuscript/scenes"
			if vim.fn.isdirectory(scene_dir) == 1 then
				local scene_files = vim.fn.glob(scene_dir .. "/*.yaml", false, true)
				for _, sf in ipairs(scene_files) do
					local slines = vim.fn.readfile(sf)
					local changed = false
					for si, sline in ipairs(slines) do
						local ch = sline:match("^chapter:%s*(.+)$")
						if ch and ch == current_name then
							slines[si] = "chapter: " .. new_name
							changed = true
							break
						end
					end
					if changed then
						vim.fn.writefile(slines, sf)
					end
				end
			end
		end

		-- Character: update scene characters lists
		if ctx.type == "character" then
			local sc_dir = root .. "/data/metadata/manuscript/scenes"
			if vim.fn.isdirectory(sc_dir) == 1 then
				local sc_files = vim.fn.glob(sc_dir .. "/*.yaml", false, true)
				for _, sf in ipairs(sc_files) do
					local slines = vim.fn.readfile(sf)
					local changed = false
					for si, sline in ipairs(slines) do
						if sline:match("^%s*%-%s*" .. vim.pesc(current_name) .. "%s*$") then
							slines[si] = sline:gsub(vim.pesc(current_name), new_name)
							changed = true
						end
					end
					if changed then
						vim.fn.writefile(slines, sf)
					end
				end
			end
		end

		-- Write updated YAML and rename file
		vim.fn.writefile(lines, old_yaml)
		vim.fn.rename(old_yaml, new_yaml)

		-- Close old buffer and open new file
		local old_buf = vim.fn.bufnr(old_yaml)
		if old_buf ~= -1 then
			vim.api.nvim_buf_delete(old_buf, { force = true })
		end
		vim.cmd("edit " .. new_yaml)

		vim.notify(
			string.format("Renamed: %s → %s", old_slug, new_slug),
			vim.log.levels.INFO
		)
	end)
end

--- Link current entry to a manuscript scene or chapter.
---
--- Context-sensitive: detects current page type and offers
--- appropriate linking options.
function M.link_to_manuscript()
	local ctx = context_mod.detect()
	if not ctx then
		vim.notify("Not on a wiki page", vim.log.levels.WARN)
		return
	end

	local options = {}
	if ctx.type == "entry" or ctx.section == "journal" then
		options = { "Link to chapter", "Link to scene" }
	else
		vim.notify("Linking not available for this page type", vim.log.levels.WARN)
		return
	end

	vim.ui.select(options, { prompt = "Link type:" }, function(choice)
		if not choice then
			return
		end

		local entity_type = choice:find("chapter") and "chapters" or "scenes"
		local names = cache.get(entity_type)

		if #names == 0 then
			vim.notify("No " .. entity_type .. " cached", vim.log.levels.WARN)
			return
		end

		vim.ui.select(names, { prompt = "Select " .. entity_type .. ":" }, function(name)
			if not name then
				return
			end

			-- Get the entry date from context
			local entry_date = ctx.slug  -- slug is YYYY-MM-DD for entries

			-- Resolve the target entity's YAML path
			local root = get_project_root()
			local target_slug = strip_accents(name):lower():gsub("%s+", "-"):gsub("[^%w%-]", ""):gsub("%-+", "-"):gsub("^%-+", ""):gsub("%-+$", "")
			local yaml_subdir = entity_type == "chapters" and "manuscript/chapters" or "manuscript/scenes"
			local yaml_path = root .. "/data/metadata/" .. yaml_subdir .. "/" .. target_slug .. ".yaml"

			if vim.fn.filereadable(yaml_path) == 0 then
				vim.notify("YAML not found: " .. yaml_path, vim.log.levels.ERROR)
				return
			end

			if entity_type == "scenes" then
				-- Add entry as source to the scene YAML
				local lines = vim.fn.readfile(yaml_path)
				local source_lines = {
					"  - source_type: entry",
					"    entry_date: " .. entry_date,
				}
				local found_sources = false
				for i, line in ipairs(lines) do
					if line:match("^sources:") then
						found_sources = true
						if line:match("^sources: *$") or line:match("^sources: *null") then
							lines[i] = "sources:"
							local insert_at = i + 1
							for _, sl in ipairs(source_lines) do
								table.insert(lines, insert_at, sl)
								insert_at = insert_at + 1
							end
						else
							local insert_at = i + 1
							while insert_at <= #lines and lines[insert_at]:match("^%s") do
								insert_at = insert_at + 1
							end
							for j, sl in ipairs(source_lines) do
								table.insert(lines, insert_at + j - 1, sl)
							end
						end
						break
					end
				end
				if not found_sources then
					table.insert(lines, "sources:")
					for _, sl in ipairs(source_lines) do
						table.insert(lines, sl)
					end
				end
				vim.fn.writefile(lines, yaml_path)
			end

			vim.notify(
				string.format("Linked entry %s to %s: %s", entry_date, entity_type, name),
				vim.log.levels.INFO
			)
		end)
	end)
end

return M
