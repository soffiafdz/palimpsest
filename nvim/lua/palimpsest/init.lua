-- Entrypoint
local M = {}

function M.setup()
	-- Load files
	require("palimpsest.vimwiki").setup()
	require("palimpsest.keymaps").setup()
end

return M
