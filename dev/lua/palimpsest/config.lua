-- Misc config vars
local home = vim.fn.expand("~")
local root = home .. "/Documents/palimpsest"
local templates_dir = root .. "templates/wiki"

local M = {}

M.paths = {
	root = root,
	wiki = root .. "/data/wiki",
	log = root .. "/data/wiki/log",
	journal = root .. "/data/journal/content/md",
	templates = templates_dir,
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
