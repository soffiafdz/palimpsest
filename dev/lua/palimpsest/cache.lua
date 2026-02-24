-- Entity name cache for Palimpsest autocomplete
--
-- Caches entity names from the database via the plm CLI for use
-- in autocompletion and entity resolution. Supports lazy refresh
-- and per-type invalidation.
local M = {}

local get_project_root = require("palimpsest.utils").get_project_root

-- Internal cache: entity_type → list of names
local _cache = {}

--- Refresh the cache for a specific entity type.
---
--- Calls `plm metadata list-entities --type {type} --format json`
--- and stores the result. Runs asynchronously via jobstart.
---
--- @param entity_type string Entity type key (people, locations, etc.)
--- @param callback function|nil Optional callback(names) on completion
function M.refresh(entity_type, callback)
	local root = get_project_root()
	local cmd = string.format(
		"cd %s && plm metadata list-entities --type %s --format json",
		root, entity_type
	)

	local output = {}
	vim.fn.jobstart(cmd, {
		stdout_buffered = true,
		on_stdout = function(_, data)
			if data then
				for _, line in ipairs(data) do
					if line ~= "" then
						table.insert(output, line)
					end
				end
			end
		end,
		on_exit = function(_, exit_code)
			if exit_code == 0 and #output > 0 then
				local json_str = table.concat(output, "")
				local ok, names = pcall(vim.fn.json_decode, json_str)
				if ok and type(names) == "table" then
					_cache[entity_type] = names
				end
			end
			if callback then
				callback(_cache[entity_type] or {})
			end
		end,
	})
end

--- Refresh all entity types.
---
--- Triggers parallel refreshes for all known entity types.
function M.refresh_all()
	local types = {
		"people", "locations", "cities", "arcs",
		"chapters", "characters", "scenes",
	}
	for _, entity_type in ipairs(types) do
		M.refresh(entity_type)
	end
end

--- Get cached entity names for a type.
---
--- Returns the cached list immediately. If the cache is empty,
--- triggers a lazy refresh and returns an empty list.
---
--- @param entity_type string Entity type key
--- @return table List of entity name strings
function M.get(entity_type)
	if not _cache[entity_type] then
		-- Trigger lazy refresh
		M.refresh(entity_type)
		return {}
	end
	return _cache[entity_type]
end

--- Create a completion source function for a given entity type.
---
--- Returns a function suitable for use with nvim completion APIs
--- that provides entity name suggestions.
---
--- @param entity_type string Entity type key
--- @return function Completion function(lead) → list of matches
function M.completion_source(entity_type)
	return function(lead)
		local names = M.get(entity_type)
		if not lead or lead == "" then
			return names
		end

		local matches = {}
		local lower_lead = lead:lower()
		for _, name in ipairs(names) do
			if name:lower():find(lower_lead, 1, true) then
				table.insert(matches, name)
			end
		end
		return matches
	end
end

--- Clear the entire cache or a specific entity type.
---
--- @param entity_type string|nil Type to clear (nil clears all)
function M.clear(entity_type)
	if entity_type then
		_cache[entity_type] = nil
	else
		_cache = {}
	end
end

return M
