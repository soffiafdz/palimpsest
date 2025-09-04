-- Setup vimwiki instance
local palimpsest = require("palimpsest.config")
local palimpsest_wiki = {
	name = palimpsest.vimwiki.name,
	path = palimpsest.paths.wiki,
	syntax = palimpsest.vimwiki.syntax,
	ext = palimpsest.vimwiki.ext,
	links_space_char = palimpsest.vimwiki.links_space_char,
	diary_rel_path = palimpsest.vimwiki.diary_rel_path,
	diary_header = palimpsest.vimwiki.diary_header,
	diary_index = "index",
}

local M = {}

function M.setup()
	if vim.g.vimwiki_list ~= nil and vim.islist(vim.g.vimwiki_list) and #vim.g.vimwiki_list > 0 then
		table.insert(vim.g.vimwiki_list, 1, palimpsest_wiki)
	else
		vim.g.vimwiki_list = { palimpsest_wiki }
	end
end

return M
