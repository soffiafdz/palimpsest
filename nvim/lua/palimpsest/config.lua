-- Misc config vars
local home = vim.fn.expand("~")
local root = home .. "/Documents/palimpsest"

local M = {}

M.paths = {
	root = root,
	wiki = root .. "/wiki",
}

M.vimwiki = {
	name = "Palimpsest",
	syntax = "markdown",
	ext = ".md",
	links_space_char = "_",
	diary_rel_path = "log",
	diary_header = [[Session Log\n]],
}

return M
