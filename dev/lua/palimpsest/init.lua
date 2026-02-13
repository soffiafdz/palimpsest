-- Entrypoint
local M = {}

function M.setup()
	local config = require("palimpsest.config")

	-- Only activate if we're inside a palimpsest project
	if not config.in_project() then
		return
	end

	-- Load core modules
	require("palimpsest.vimwiki").setup()
	require("palimpsest.commands").setup()
	require("palimpsest.validators").setup()
	require("palimpsest.keymaps").setup()
	require("palimpsest.autocmds").setup()

	-- Load context detection (eager — used by keymaps and commands)
	require("palimpsest.context")

	-- Initialize entity cache (async refresh on startup)
	require("palimpsest.cache").refresh_all()

	-- Check if fzf-lua is available (optional dependency)
	local has_fzf, _ = pcall(require, "fzf-lua")
	if not has_fzf then
		vim.notify(
			"fzf-lua not found - browse and search features disabled. Install with LazyVim or add fzf-lua plugin.",
			vim.log.levels.WARN
		)
	end
end

return M
