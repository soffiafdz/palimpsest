local palimpsest = require("palimpsest.config")
local templates = require("palimpsest.templates")
local M = {}

-- Track YAML metadata buffers that have been saved (for conditional import)
local _saved_yaml_buffers = {}

--- Check if a buffer is currently displayed in a floating window.
---@param bufnr number Buffer number
---@return boolean
local function buf_in_float(bufnr)
	for _, win in ipairs(vim.api.nvim_list_wins()) do
		if vim.api.nvim_win_get_buf(win) == bufnr then
			local config = vim.api.nvim_win_get_config(win)
			if config.relative ~= "" then
				return true
			end
		end
	end
	return false
end

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

	-- Validate YAML metadata on save (skip if in float — float handles its own)
	vim.api.nvim_create_autocmd("BufWritePost", {
		group = "palimpsest_validators",
		pattern = palimpsest.paths.metadata .. "/**/*.yaml",
		callback = function(args)
			if buf_in_float(args.buf) then return end
			_saved_yaml_buffers[args.buf] = vim.api.nvim_buf_get_name(args.buf)
			local float = require("palimpsest.float")
			float.on_save(args.buf, _saved_yaml_buffers[args.buf])
		end,
	})

	-- Import metadata when leaving YAML buffer (only if saved, skip if float)
	vim.api.nvim_create_autocmd("BufWinLeave", {
		group = "palimpsest_validators",
		pattern = palimpsest.paths.metadata .. "/**/*.yaml",
		callback = function(args)
			local filepath = _saved_yaml_buffers[args.buf]
			if not filepath then return end
			if buf_in_float(args.buf) then return end
			-- Only import when leaving the last window showing this buffer
			local wins = vim.fn.win_findbuf(args.buf)
			if #wins > 1 then return end
			_saved_yaml_buffers[args.buf] = nil
			local float = require("palimpsest.float")
			float.on_close(args.buf, filepath)
		end,
	})
end

return M
