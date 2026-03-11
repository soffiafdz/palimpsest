-- Entrypoint
local M = {}

function M.setup()
	local config = require("palimpsest.config")

	-- Only activate if we're inside a palimpsest project
	if not config.in_project() then
		return
	end

	-- Always load (pure Lua, no Python dependency)
	require("palimpsest.vimwiki").setup()
	require("palimpsest.keymaps").setup()
	require("palimpsest.context")

	-- Override vimwiki's file: link handler to open in nvim
	-- instead of delegating to the OS (which opens wrong apps).
	-- Also resolves __PALIMPSEST__ placeholder so links work across machines.
	local root = require("palimpsest.config").get_root() or ""
	vim.g._palimpsest_root = root
	vim.cmd([[
		function! VimwikiLinkHandler(link)
			if a:link =~# '^file:'
				let l:path = substitute(a:link, '^file:', '', '')
				let l:path = substitute(l:path, '__PALIMPSEST__', g:_palimpsest_root, 'g')
				execute 'edit ' . fnameescape(l:path)
				return 1
			endif
			return 0
		endfunction
	]])

	-- Full setup: all modules including Python-dependent
	require("palimpsest.commands").setup()
	require("palimpsest.validators").setup()
	require("palimpsest.autocmds").setup()

	-- Initialize entity cache (async refresh on startup)
	require("palimpsest.cache").refresh_all()

	-- Check if a picker backend is available (fzf-lua or snacks.nvim)
	local has_fzf = pcall(require, "fzf-lua")
	local has_snacks, snacks = pcall(require, "snacks")
	if not has_fzf and not (has_snacks and snacks.picker) then
		vim.notify(
			"No picker found (fzf-lua or snacks.nvim) — browse and search disabled",
			vim.log.levels.INFO
		)
	end
end

return M
