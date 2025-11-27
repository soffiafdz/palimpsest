-- Entrypoint
local M = {}

function M.setup()
	-- Load files
	require("palimpsest.vimwiki").setup()
	require("palimpsest.commands").setup()
	require("palimpsest.validators").setup()
	require("palimpsest.keymaps").setup()
	require("palimpsest.autocmds").setup()

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
