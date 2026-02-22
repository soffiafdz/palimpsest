-- Entrypoint
local M = {}

function M.setup()
	local config = require("palimpsest.config")

	-- Only activate if we're inside a palimpsest project
	if not config.in_project() then
		return
	end

	local deck_mode = vim.g.palimpsest_deck_mode or false

	-- Always load (pure Lua, no Python dependency)
	require("palimpsest.vimwiki").setup()
	require("palimpsest.keymaps").setup()
	require("palimpsest.context")

	-- Override vimwiki's file: link handler to open in nvim
	-- instead of delegating to the OS (which opens wrong apps).
	vim.cmd([[
		function! VimwikiLinkHandler(link)
			if a:link =~# '^file:'
				let l:path = substitute(a:link, '^file:', '', '')
				execute 'edit ' . fnameescape(l:path)
				return 1
			endif
			return 0
		endfunction
	]])

	if deck_mode then
		-- Deck: minimal autocmds + sync-pending marker writer
		require("palimpsest.autocmds").setup_deck()
		require("palimpsest.commands").setup_deck()
	else
		-- Full: all modules including Python-dependent
		require("palimpsest.commands").setup()
		require("palimpsest.validators").setup()
		require("palimpsest.autocmds").setup()

		-- Initialize entity cache (async refresh on startup)
		require("palimpsest.cache").refresh_all()

		-- Notify if deck edits are pending
		local wiki_dir = config.paths.wiki
		if wiki_dir and vim.fn.filereadable(wiki_dir .. "/.sync-pending") == 1 then
			vim.notify("Deck edits pending — run :PalimpsestSync", vim.log.levels.WARN)
		end
	end

	-- Check if fzf-lua is available (optional dependency)
	local has_fzf, _ = pcall(require, "fzf-lua")
	if not has_fzf then
		vim.notify(
			"fzf-lua not found - browse and search features disabled",
			vim.log.levels.INFO
		)
	end
end

return M
