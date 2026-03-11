local palimpsest = require("palimpsest.config")
local templates = require("palimpsest.templates")
local M = {}

--- Set up template autocmds.
---@param group string Augroup name
local function setup_templates(group)
	-- Templates formatting
	vim.api.nvim_create_autocmd({ "BufRead", "BufNewFile" }, {
		group = group,
		pattern = palimpsest.paths.templates .. "*.template",
		callback = function()
			vim.bo.filetype = "markdown"
		end,
	})

	-- Populate new Palimpsest log entries
	vim.api.nvim_create_autocmd("BufNewFile", {
		group = group,
		pattern = palimpsest.paths.log .. "*.md",
		callback = templates.populate_log,
	})
end

--- Full setup: templates + all validators.
M.setup = function()
	vim.api.nvim_create_augroup("vimwiki_templates", { clear = true })
	setup_templates("vimwiki_templates")

	-- Validators (Python-dependent)
	local validators = require("palimpsest.validators")
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

	-- Lint wiki pages on save
	vim.api.nvim_create_autocmd("BufWritePost", {
		group = "palimpsest_validators",
		pattern = palimpsest.paths.wiki .. "/**/*.md",
		callback = function(args)
			validators.validate_wiki_page(args.buf)
		end,
	})
end

return M
