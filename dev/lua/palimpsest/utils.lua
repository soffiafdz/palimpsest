-- Shared utilities for Palimpsest nvim plugin
local M = {}

--- Get the Palimpsest project root directory.
---
--- Delegates to config.lua's root detection (uses .palimpsest marker).
---
--- @return string Absolute path to the project root
function M.get_project_root()
	local root = require("palimpsest.config").get_root()
	return root or vim.fn.getcwd()
end

return M
