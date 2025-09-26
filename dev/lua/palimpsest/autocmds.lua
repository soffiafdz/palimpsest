local palimpsest = require("palimpsest.config")
local templates = require("palimpsest.templates")
local M = {}

M.setup = function()
	-- Templates
	vim.api.nvim_create_augroup("vimwiki_templates", { clear = true })

	-- Templates formatting
	vim.api.nvim_create_autocmd({ "BufRead", "BufNewFile" }, {
		group = "vimwiki_templates",
		pattern = palimpsest.paths.templates .. "*.template",
		callback = function()
			vim.bo.filetype = "markdown"
		end,
	})

	-- Populate new Palimpsest log entries
	vim.api.nvim_create_autocmd("BufNewFile", {
		group = "vimwiki_templates",
		pattern = palimpsest.paths.log .. "*.md",
		callback = templates.populate_log,
	})
end

return M
