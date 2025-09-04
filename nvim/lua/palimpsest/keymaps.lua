local MiniIcons = require("mini.icons")
local icon_data = MiniIcons.get("extension", ".md")
local palimpsest_icon = icon_data and icon_data.icon or ""
local wk = require("which-key")

local M = {}

function M.setup()
	if #vim.g.vimwiki_list > 1 then
		-- If there are another vimwiki(s) set up:
		-- create a new group specifically for Palimpsest.
		wk.add({
			-- Do I need to specify icon here?
			{ "<leader>v", group = "vimwiki" },
			{
				group = "palimpsest",
				icon = { icon = palimpsest_icon, color = "green" },
				{ "<leader>p", group = "palimpsest" },
				{ "<leader>pw", "<cmd>1VimwikiIndex<cr>", desc = "Palimpsest Index" },
				{ "<leader>pt", "<cmd>1VimwikiTabIndex<cr>", desc = "Palimpsest Index (New tab)" },
				{ "<leader>pi", "<cmd>1VimwikiDiaryIndex<cr>", desc = "Palimpsest Log" },
				{ "<leader>p<leader>w", "<cmd>1VimwikiMakeDiaryNote<cr>", desc = "Palimpsest Log (Today)" },
				{ "<leader>p<leader>t", "<cmd>1VimwikiTabMakeDiaryNote<cr>", desc = "Palimpsest Log (Today, new tab)" },
				{ "<leader>pr", "<Plug>VimwikiDiaryGenerateLinks", desc = "Rebuild log links" },
			},
		})
	else
		-- If not, Redefine names/group
		wk.add({
			{
				group = "Palimpsest",
				icon = { icon = palimpsest_icon, color = "green" },
				{ "<leader>v", group = "Palimpsest" },
				{ "<leader>vw", "<Plug>VimwikiIndex", desc = "Palimpsest Index" },
				{ "<leader>vt", "<Plug>VimwikiTabIndex", desc = "Palimpsest Index (New tab)" },
				{ "<leader>vi", "<Plug>VimwikiDiaryIndex", desc = "Palimpsest Log" },
				{ "<leader>v<leader>w", "<Plug>VimwikiMakeDiaryNote", desc = "Palimpsest Log (Today)" },
				{ "<leader>v<leader>t", "<Plug>VimwikiTabMakeDiaryNote", desc = "Palimpsest Log (Today, new tab)" },
				{ "<leader>v<leader>i", "<Plug>VimwikiDiaryGenerateLinks", desc = "Rebuild log links" },
			},
		})
		-- Remove unnecessary keymaps
		vim.api.nvim_del_keymap("n", "<leader>vs") -- Select vimwikis
		vim.api.nvim_del_keymap("n", "<leader>v<leader>y") -- Diary (yesterday)
		vim.api.nvim_del_keymap("n", "<leader>v<leader>m") -- Diary (tomorrow)
	end
end

return M
