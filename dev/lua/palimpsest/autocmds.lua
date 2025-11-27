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

	-- Validate markdown frontmatter on save for entry files
	vim.api.nvim_create_autocmd("BufWritePost", {
		group = "palimpsest_validators",
		pattern = palimpsest.paths.wiki .. "/entries/**/*.md",
		callback = function(args)
			validators.validate_frontmatter(args.buf)
		end,
	})

	-- Validate all markdown files in wiki on save
	vim.api.nvim_create_autocmd("BufWritePost", {
		group = "palimpsest_validators",
		pattern = palimpsest.paths.wiki .. "/**/*.md",
		callback = function(args)
			-- Skip log entries (they have simpler structure)
			local filepath = vim.api.nvim_buf_get_name(args.buf)
			if not filepath:match("/log/") then
				validators.validate_links(args.buf)
			end
		end,
	})
end

return M
