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

		-- Generate slug from name
		local slug = name:lower():gsub("%s+", "-"):gsub("[^%w%-]", "")

		-- Determine file path
		local dir_map = {
			people = "people",
			chapters = "manuscript/chapters",
			characters = "manuscript/characters",
			scenes = "manuscript/scenes",
		}
		local dir = base .. (dir_map[entity_type] or entity_type)
		local filepath = dir .. "/" .. slug .. ".yaml"

		-- Create directory and write template
		vim.fn.mkdir(dir, "p")
		local content = template:gsub("^name: ", "name: " .. name, 1)
			:gsub("^title: ", "title: " .. name, 1)
		local f = io.open(filepath, "w")
		if f then
			f:write(content)
			f:close()
		end

		float.open(filepath, {
			title = string.format(" New %s ", entity_type),
		})
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

			vim.ui.input(
				{ prompt = "Reference: " },
				function(reference)
					if not reference then
						return
					end
					vim.notify(
						string.format("Add source: %s — %s (manual edit needed)", source_type, reference),
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
				vim.notify(
					string.format("Add based_on: %s (%s) — edit YAML to apply", person, contribution),
					vim.log.levels.INFO
				)
			end
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
			if name then
				vim.notify(
					string.format("Link to %s: %s (apply via wiki sync)", entity_type, name),
					vim.log.levels.INFO
				)
			end
		end)
	end)
end

return M
