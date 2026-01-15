-- Palimpsest configuration with auto-detection
local M = {}

-- Cache for project root (nil = not yet detected, false = not found)
local cached_root = nil

--- Find the project root by walking up from a starting path.
--- Looks for the .palimpsest marker file.
---@param start_path string|nil Starting path (defaults to current file or cwd)
---@return string|nil root The project root path, or nil if not found
local function find_project_root(start_path)
	local path = start_path or vim.fn.expand("%:p:h")
	if path == "" then
		path = vim.fn.getcwd()
	end

	-- Walk up the directory tree
	while path and path ~= "/" and path ~= "" do
		local marker_path = path .. "/.palimpsest"
		if vim.fn.filereadable(marker_path) == 1 then
			return path
		end
		-- Go up one directory
		local parent = vim.fn.fnamemodify(path, ":h")
		if parent == path then
			break
		end
		path = parent
	end
	return nil
end

--- Get the project root, using cache after first detection.
---@return string|nil root The project root path, or nil if not in project
function M.get_root()
	if cached_root == nil then
		cached_root = find_project_root() or false
	end
	return cached_root or nil
end

--- Check if we're inside a palimpsest project.
---@return boolean
function M.in_project()
	return M.get_root() ~= nil
end

--- Clear the cached root (useful if cwd changes).
function M.clear_cache()
	cached_root = nil
end

-- Lazy-initialized paths table
M.paths = setmetatable({}, {
	__index = function(_, key)
		local root = M.get_root()
		if not root then
			return nil
		end
		local paths = {
			root = root,
			wiki = root .. "/data/wiki",
			log = root .. "/data/wiki/log",
			journal = root .. "/data/journal/content/md",
			templates = root .. "/templates/wiki",
		}
		return paths[key]
	end,
})

M.vimwiki = {
	name = "Palimpsest",
	syntax = "markdown",
	ext = ".md",
	links_space_char = "_",
	diary_rel_path = "log",
	diary_header = [[Session Log\n]],
}

return M
