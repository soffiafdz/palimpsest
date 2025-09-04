-- Entrypoint
local M = {}

function M.setup()
	-- Load files
	require("palimpsest.vimwiki").setup()
	require("palimpsest.keymaps").setup()
	require("palimpsest.autocmds").setup()
end

return M
