local palimpsest = require("palimpsest.config")
local templates = require("palimpsest.templates")
local M = {}

--- Set up template autocmds (shared between full and deck modes).
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

--- Write or update the .sync-pending marker file.
--- Records which manuscript files were edited on the deck so the main
--- machine knows to ingest before regenerating.
---@param file_path string Absolute path of the saved file
local function write_sync_pending(file_path)
	local wiki_dir = palimpsest.paths.wiki
	if not wiki_dir then
		return
	end

	local marker_path = wiki_dir .. "/.sync-pending"

	-- Compute relative path from wiki dir
	local rel_path = file_path:sub(#wiki_dir + 2) -- strip wiki_dir + "/"

	-- Read existing marker or start fresh
	local data = { machine = "writer-deck", timestamp = "", files = {} }
	local f = io.open(marker_path, "r")
	if f then
		local content = f:read("*a")
		f:close()
		local ok, parsed = pcall(vim.fn.json_decode, content)
		if ok and type(parsed) == "table" then
			data = parsed
		end
	end

	-- Deduplicate: add file only if not already listed
	local found = false
	for _, existing in ipairs(data.files or {}) do
		if existing == rel_path then
			found = true
			break
		end
	end
	if not found then
		data.files = data.files or {}
		table.insert(data.files, rel_path)
	end

	-- Update timestamp
	data.timestamp = os.date("!%Y-%m-%dT%H:%M:%S")
	data.machine = data.machine or "writer-deck"

	-- Write marker
	local out = io.open(marker_path, "w")
	if out then
		out:write(vim.fn.json_encode(data))
		out:close()
	end
end

--- Full setup: templates + all validators (main machine).
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

--- Deck setup: templates + sync-pending marker writer (no Python).
M.setup_deck = function()
	vim.api.nvim_create_augroup("vimwiki_templates", { clear = true })
	setup_templates("vimwiki_templates")

	-- Sync-pending marker: track manuscript edits for main machine
	vim.api.nvim_create_augroup("palimpsest_deck_sync", { clear = true })
	vim.api.nvim_create_autocmd("BufWritePost", {
		group = "palimpsest_deck_sync",
		pattern = palimpsest.paths.wiki .. "/manuscript/**/*.md",
		callback = function(args)
			write_sync_pending(vim.api.nvim_buf_get_name(args.buf))
		end,
	})
end

return M
