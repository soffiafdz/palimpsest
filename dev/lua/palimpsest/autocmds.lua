local palimpsest = require("palimpsest.config")
local templates = require("palimpsest.templates")
local validators = require("palimpsest.validators")
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

	-- Validators
	vim.api.nvim_create_augroup("palimpsest_validators", { clear = true })

	-- Validate markdown frontmatter on save for journal entry files
	vim.api.nvim_create_autocmd("BufWritePost", {
		group = "palimpsest_validators",
		pattern = palimpsest.paths.journal .. "/**/*.md",
		callback = function(args)
			validators.validate_frontmatter(args.buf)
		end,
	})

	-- Validate markdown links in journal entries on save
	vim.api.nvim_create_autocmd("BufWritePost", {
		group = "palimpsest_validators",
		pattern = palimpsest.paths.journal .. "/**/*.md",
		callback = function(args)
			validators.validate_links(args.buf)
		end,
	})
end

return M
