-- Shared utilities for Palimpsest nvim plugin
local M = {}

--- Find the Palimpsest project root directory.
---
--- Walks up from the current file's directory looking for marker files.
--- Falls back to cwd if no markers are found.
---
--- @return string Absolute path to the project root
function M.get_project_root()
	local markers = { "pyproject.toml", ".git", "palimpsest.db" }
	local path = vim.fn.expand("%:p:h")

	while path ~= "/" do
		for _, marker in ipairs(markers) do
			if vim.fn.filereadable(path .. "/" .. marker) == 1
				or vim.fn.isdirectory(path .. "/" .. marker) == 1
			then
				return path
			end
		end
		path = vim.fn.fnamemodify(path, ":h")
	end

	return vim.fn.getcwd()
end

return M
