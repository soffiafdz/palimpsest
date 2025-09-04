local MiniIcons = require("mini.icons")
local icon_data = MiniIcons.get("extension", ".md")
local palimpsest_icon = icon_data and icon_data.icon or ""
local wk = require("which-key")

local M = {}

function M.setup()
	if #vim.g.vimwiki_list > 1 then
		wk.add({
			{
				group = "palimpsest",
				icon = { icon = palimpsest_icon, color = "green" },
				{ "<leader>p", group = "palimpsest" },
				{ "<leader>pw", "<cmd>1VimwikiIndex<cr>", desc = "Palimpsest Index" },
				{ "<leader>pt", "<cmd>1VimwikiTabIndex<cr>", desc = "Palimpsest Index (New tab)" },
				{ "<leader>pl", "<cmd>1VimwikiDiaryIndex<cr>", desc = "Palimpsest Log" },
				{ "<leader>p<leader>w", "<cmd>1VimwikiMakeDiaryNote<cr>", desc = "Palimpsest Log (Today)" },
				{ "<leader>p<leader>t", "<cmd>1VimwikiTabMakeDiaryNote<cr>", desc = "Palimpsest Log (Today, new tab)" },
				{ "<leader>pr", "<Plug>VimwikiDiaryGenerateLinks", desc = "Rebuild log links" },
			},
		})
	else
		wk.add({
			{
				group = "Palimpsest",
				icon = { icon = palimpsest_icon, color = "green" },
				{ "<leader>v", group = "Palimpsest" },
				{ "<leader>vw", "<Plug>VimwikiIndex", desc = "Palimpsest Index" },
				{ "<leader>vt", "<Plug>VimwikiTabIndex", desc = "Palimpsest Index (New tab)" },
				{ "<leader>vl", "<Plug>VimwikiDiaryIndex", desc = "Palimpsest Log" },
				{ "<leader>v<leader>w", "<Plug>VimwikiMakeDiaryNote", desc = "Palimpsest Log (Today)" },
				{ "<leader>v<leader>t", "<Plug>VimwikiTabMakeDiaryNote", desc = "Palimpsest Log (Today, new tab)" },
				{ "<leader>vr", "<Plug>VimwikiDiaryGenerateLinks", desc = "Rebuild log links" },
			},
		})
	end
end

return M
