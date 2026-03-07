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
	entity_type = entity_type or "people"

	local root = get_project_root()
	local base = root .. "/data/metadata/"

	-- Generate template based on type
	local templates = {
		people = "name: \nlastname: \nrelation_type: friend\n",
		chapters = "title: \nnumber: \ntype: prose\nstatus: draft\n",
		characters = "name: \nrole: \nis_narrator: false\ndescription: \n",
		scenes = "name: \nchapter: \norigin: journaled\nstatus: fragment\ndescription: \n",
	}

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

--- Add a source entry to a manuscript scene YAML.
---
--- Provides guided insertion with autocomplete for entry dates
--- and scene names.
function M.add_source()
	local ctx = context_mod.detect()
	if not ctx or ctx.type ~= "scene" then
		vim.notify("Must be on a manuscript scene page", vim.log.levels.WARN)
		return
	end

	-- Select source type
	vim.ui.select(
		{ "scene", "entry", "thread", "external" },
		{ prompt = "Source type:" },
		function(source_type)
			if not source_type then
				return
			end

			local ref_prompt = source_type == "entry" and "Entry date (YYYY-MM-DD): " or "Reference: "
			vim.ui.input(
				{ prompt = ref_prompt },
				function(reference)
					if not reference or reference == "" then
						return
					end

					local yaml_path = resolve_yaml_path(ctx)
					if not yaml_path or vim.fn.filereadable(yaml_path) == 0 then
						vim.notify("Scene YAML not found", vim.log.levels.ERROR)
						return
					end

					-- Build source entry lines
					local source_lines = { "  - source_type: " .. source_type }
					if source_type == "entry" then
						table.insert(source_lines, "    entry_date: " .. reference)
					elseif source_type == "external" then
						table.insert(source_lines, "    note: " .. reference)
					else
						table.insert(source_lines, "    reference: " .. reference)
					end

					-- Read existing YAML, append source entry
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
						string.format("Added source: %s — %s", source_type, reference),
						vim.log.levels.INFO
					)
				end
			)
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
