local palimpsest_icon = "󰂺"
local has_wk, wk = pcall(require, "which-key")

local M = {}

-- Context-specific keymaps per entity type.
-- key: suffix appended to the entity prefix (e.g., "s" → <prefix>es)
local CONTEXT_KEYMAPS = {
	scene = {
		{ key = "s", cmd = "<cmd>PalimpsestAddSource<cr>", desc = "Add source", icon = "󰁅" },
		{ key = "h", cmd = "<cmd>PalimpsestSetChapter<cr>", desc = "Set chapter", icon = "󰉋" },
		{ key = "a", cmd = "<cmd>PalimpsestAddCharacter<cr>", desc = "Add character", icon = "󰙃" },
		{ key = "o", cmd = "<cmd>PalimpsestOpenSources<cr>", desc = "Open sources", icon = "󰈔" },
		{ key = "R", cmd = "<cmd>PalimpsestRename<cr>", desc = "Rename scene", icon = "󰑕" },
	},
	chapter = {
		{ key = "p", cmd = "<cmd>PalimpsestSetPart<cr>", desc = "Set part", icon = "󰉋" },
		{ key = "S", cmd = "<cmd>PalimpsestAddScene<cr>", desc = "Add scene", icon = "󰕧" },
		{ key = "o", cmd = "<cmd>PalimpsestOpenSources<cr>", desc = "Open draft", icon = "󰈔" },
		{ key = "R", cmd = "<cmd>PalimpsestRename<cr>", desc = "Rename chapter", icon = "󰑕" },
	},
	character = {
		{ key = "b", cmd = "<cmd>PalimpsestAddBasedOn<cr>", desc = "Add based_on", icon = "󰌹" },
		{ key = "R", cmd = "<cmd>PalimpsestRename<cr>", desc = "Rename character", icon = "󰑕" },
	},
	entry = {
		{ key = "l", cmd = "<cmd>PalimpsestLinkToManuscript<cr>", desc = "Link to manuscript", icon = "󰿟" },
	},
	person = {
		{ key = "c", cmd = "<cmd>PalimpsestEditCuration<cr>", desc = "Edit curation", icon = "󰒓" },
		{ key = "R", cmd = "<cmd>PalimpsestRename<cr>", desc = "Rename person", icon = "󰑕" },
	},
	location = {
		{ key = "c", cmd = "<cmd>PalimpsestEditCuration<cr>", desc = "Edit curation", icon = "󰒓" },
		{ key = "R", cmd = "<cmd>PalimpsestRename<cr>", desc = "Rename location", icon = "󰑕" },
	},
	city = {
		{ key = "c", cmd = "<cmd>PalimpsestEditCuration<cr>", desc = "Edit curation", icon = "󰒓" },
	},
}

--- Register buffer-local context keymaps for the current wiki page.
---
--- @param bufnr number Buffer number
--- @param prefix string Key prefix ("<leader>p" or "<leader>v")
local function register_context_keymaps(bufnr, prefix)
	if vim.b[bufnr].palimpsest_context_keymaps then
		return
	end

	local ctx = require("palimpsest.context").detect()
	if not ctx then
		return
	end

	local keymaps = CONTEXT_KEYMAPS[ctx.type]
	if not keymaps then
		return
	end

	local entries = {}
	for _, km in ipairs(keymaps) do
		table.insert(entries, {
			prefix .. "e" .. km.key,
			km.cmd,
			desc = km.desc,
			icon = km.icon,
			buffer = bufnr,
		})
	end

	if #entries > 0 then
		wk.add(entries)
		vim.b[bufnr].palimpsest_context_keymaps = true
	end
end

function M.setup()
	if not has_wk then
		vim.notify("which-key not found - palimpsest keymaps disabled", vim.log.levels.WARN)
		return
	end

	local prefix
	if #vim.g.vimwiki_list > 1 then
		prefix = "<leader>p"
		wk.add({
			{ "<leader>v", group = "vimwiki" },
			{
				group = "palimpsest",
				icon = { icon = palimpsest_icon, color = "green" },
				{ "<leader>p", group = "palimpsest", icon = { icon = palimpsest_icon, color = "green" } },
				{ "<leader>pw", "<cmd>1VimwikiIndex<cr>", desc = "Palimpsest Index", icon = "󰖬" },
				{ "<leader>pt", "<cmd>1VimwikiTabIndex<cr>", desc = "Palimpsest Index (New tab)", icon = "󰖬" },
				{ "<leader>pi", "<cmd>1VimwikiDiaryIndex<cr>", desc = "Palimpsest Log", icon = "󰃭" },
				{ "<leader>p<leader>w", "<cmd>1VimwikiMakeDiaryNote<cr>", desc = "Palimpsest Log (Today)", icon = "󰃮" },
				{ "<leader>p<leader>t", "<cmd>1VimwikiTabMakeDiaryNote<cr>", desc = "Palimpsest Log (Today, new tab)", icon = "󰃮" },
				{ "<leader>pr", "<Plug>VimwikiDiaryGenerateLinks", desc = "Rebuild log links", icon = "󰑓" },
				-- Entity commands (universal)
				{ "<leader>pe", group = "entity", icon = "󰕘" },
				{ "<leader>pee", "<cmd>PalimpsestEdit<cr>", desc = "Edit metadata (float)", icon = "󰏫" },
				{ "<leader>pen", "<cmd>PalimpsestNew<cr>", desc = "New entity...", icon = "" },
				{ "<leader>pex", "<cmd>PalimpsestMetadataExport<cr>", desc = "Export metadata YAML", icon = "󰈔" },
				-- Wiki operations
				{ "<leader>pL", "<cmd>PalimpsestLint<cr>", desc = "Wiki lint", icon = "󱩾" },
				{ "<leader>pG", "<cmd>PalimpsestGenerate<cr>", desc = "Wiki generate", icon = "󰯬" },
				-- Validators
				{ "<leader>pv", group = "validators", icon = "󰱽" },
				{ "<leader>pvf", "<cmd>PalimpsestValidateFrontmatter<cr>", desc = "Validate frontmatter", icon = "󰈮" },
				{ "<leader>pvm", "<cmd>PalimpsestValidateMetadata<cr>", desc = "Validate frontmatter structure", icon = "󰘦" },
				{ "<leader>pvl", "<cmd>PalimpsestValidateLinks<cr>", desc = "Validate markdown links", icon = "󰌹" },
				{ "<leader>pve", "<cmd>PalimpsestValidateEntry<cr>", desc = "Validate entry (quickfix)", icon = "󰃤" },
				{ "<leader>ph", "<cmd>PalimpsestIndex<cr>", desc = "Wiki homepage", icon = "󰋜" },
				-- Manuscript commands
				{ "<leader>pm", group = "manuscript", icon = "󱥏" },
				{ "<leader>pmg", "<cmd>PalimpsestGenerate manuscript<cr>", desc = "Generate manuscript", icon = "󰯬" },
				{ "<leader>pmh", "<cmd>PalimpsestManuscriptIndex<cr>", desc = "Manuscript homepage", icon = "󰋜" },
				-- fzf-lua wiki browser
				{ "<leader>pf", "<cmd>PalimpsestQuickAccess<cr>", desc = "Quick access wiki pages", icon = "󰄶" },
				{ "<leader>pF", group = "browse entities", icon = "󰈞" },
				{ "<leader>pFa", "<cmd>lua require('palimpsest.fzf').browse('all')<cr>", desc = "Browse wiki", icon = "󰖬" },
				{ "<leader>pFj", "<cmd>lua require('palimpsest.fzf').browse('journal')<cr>", desc = "Browse journal", icon = "󰃭" },
				{ "<leader>pFp", "<cmd>lua require('palimpsest.fzf').browse('people')<cr>", desc = "Browse people", icon = "󰋍" },
				{ "<leader>pFe", "<cmd>lua require('palimpsest.fzf').browse('entries')<cr>", desc = "Browse entries", icon = "󰧮" },
				{ "<leader>pFl", "<cmd>lua require('palimpsest.fzf').browse('locations')<cr>", desc = "Browse locations", icon = "󰍎" },
				{ "<leader>pFc", "<cmd>lua require('palimpsest.fzf').browse('cities')<cr>", desc = "Browse cities", icon = "󰄝" },
				{ "<leader>pFv", "<cmd>lua require('palimpsest.fzf').browse('events')<cr>", desc = "Browse events", icon = "󰙹" },
				{ "<leader>pFt", "<cmd>lua require('palimpsest.fzf').browse('themes')<cr>", desc = "Browse themes", icon = "󰓹" },
				{ "<leader>pFT", "<cmd>lua require('palimpsest.fzf').browse('tags')<cr>", desc = "Browse tags", icon = "󰓹" },
				{ "<leader>pFP", "<cmd>lua require('palimpsest.fzf').browse('poems')<cr>", desc = "Browse poems", icon = "󰎈" },
				{ "<leader>pFr", "<cmd>lua require('palimpsest.fzf').browse('references')<cr>", desc = "Browse references", icon = "󰈙" },
				-- Manuscript browse
				{ "<leader>pFm", "<cmd>lua require('palimpsest.fzf').browse('manuscript')<cr>", desc = "Browse manuscript", icon = "󱥏" },
				{ "<leader>pFM", group = "manuscript entities", icon = "󱥏" },
				{ "<leader>pFMc", "<cmd>lua require('palimpsest.fzf').browse('manuscript-chapters')<cr>", desc = "Manuscript chapters", icon = "󰯂" },
				{ "<leader>pFMh", "<cmd>lua require('palimpsest.fzf').browse('manuscript-characters')<cr>", desc = "Manuscript characters", icon = "󰙃" },
				{ "<leader>pFMs", "<cmd>lua require('palimpsest.fzf').browse('manuscript-scenes')<cr>", desc = "Manuscript scenes", icon = "󰕧" },
				{ "<leader>p/w", "<cmd>lua require('palimpsest.fzf').search('wiki')<cr>", desc = "Search wiki", icon = "󰍉" },
				{ "<leader>p/j", "<cmd>lua require('palimpsest.fzf').search('journal')<cr>", desc = "Search journal", icon = "󰍉" },
				{ "<leader>p/m", "<cmd>lua require('palimpsest.fzf').search('manuscript')<cr>", desc = "Search manuscript", icon = "󰍉" },
			},
		})
	else
		prefix = "<leader>v"
		wk.add({
			{
				group = "Palimpsest",
				icon = { icon = palimpsest_icon, color = "green" },
				{ "<leader>v", group = "Palimpsest", icon = { icon = palimpsest_icon, color = "green" } },
				{ "<leader>vw", "<Plug>VimwikiIndex", desc = "Palimpsest Index", icon = "󰖬" },
				{ "<leader>vt", "<Plug>VimwikiTabIndex", desc = "Palimpsest Index (New tab)", icon = "󰖬" },
				{ "<leader>vi", "<Plug>VimwikiDiaryIndex", desc = "Palimpsest Log", icon = "󰃭" },
				{ "<leader>v<leader>w", "<Plug>VimwikiMakeDiaryNote", desc = "Palimpsest Log (Today)", icon = "󰃮" },
				{ "<leader>v<leader>t", "<Plug>VimwikiTabMakeDiaryNote", desc = "Palimpsest Log (Today, new tab)", icon = "󰃮" },
				{ "<leader>v<leader>i", "<Plug>VimwikiDiaryGenerateLinks", desc = "Rebuild log links", icon = "󰑓" },
				-- Entity commands (universal)
				{ "<leader>ve", group = "entity", icon = "󰕘" },
				{ "<leader>vee", "<cmd>PalimpsestEdit<cr>", desc = "Edit metadata (float)", icon = "󰏫" },
				{ "<leader>ven", "<cmd>PalimpsestNew<cr>", desc = "New entity...", icon = "" },
				{ "<leader>vex", "<cmd>PalimpsestMetadataExport<cr>", desc = "Export metadata YAML", icon = "󰈔" },
				-- Wiki operations
				{ "<leader>vL", "<cmd>PalimpsestLint<cr>", desc = "Wiki lint", icon = "󱩾" },
				{ "<leader>vG", "<cmd>PalimpsestGenerate<cr>", desc = "Wiki generate", icon = "󰯬" },
				-- Validators
				{ "<leader>vv", group = "validators", icon = "󰱽" },
				{ "<leader>vvf", "<cmd>PalimpsestValidateFrontmatter<cr>", desc = "Validate frontmatter", icon = "󰈮" },
				{ "<leader>vvm", "<cmd>PalimpsestValidateMetadata<cr>", desc = "Validate frontmatter structure", icon = "󰘦" },
				{ "<leader>vvl", "<cmd>PalimpsestValidateLinks<cr>", desc = "Validate markdown links", icon = "󰌹" },
				{ "<leader>vve", "<cmd>PalimpsestValidateEntry<cr>", desc = "Validate entry (quickfix)", icon = "󰃤" },
				{ "<leader>vh", "<cmd>PalimpsestIndex<cr>", desc = "Wiki homepage", icon = "󰋜" },
				-- Manuscript commands
				{ "<leader>vm", group = "manuscript", icon = "󱥏" },
				{ "<leader>vmg", "<cmd>PalimpsestGenerate manuscript<cr>", desc = "Generate manuscript", icon = "󰯬" },
				{ "<leader>vmh", "<cmd>PalimpsestManuscriptIndex<cr>", desc = "Manuscript homepage", icon = "󰋜" },
				-- fzf-lua wiki browser
				{ "<leader>vf", "<cmd>PalimpsestQuickAccess<cr>", desc = "Quick access wiki pages", icon = "󰄶" },
				{ "<leader>vF", group = "browse entities", icon = "󰈞" },
				{ "<leader>vFa", "<cmd>lua require('palimpsest.fzf').browse('all')<cr>", desc = "Browse wiki", icon = "󰖬" },
				{ "<leader>vFj", "<cmd>lua require('palimpsest.fzf').browse('journal')<cr>", desc = "Browse journal", icon = "󰃭" },
				{ "<leader>vFp", "<cmd>lua require('palimpsest.fzf').browse('people')<cr>", desc = "Browse people", icon = "󰋍" },
				{ "<leader>vFe", "<cmd>lua require('palimpsest.fzf').browse('entries')<cr>", desc = "Browse entries", icon = "󰧮" },
				{ "<leader>vFl", "<cmd>lua require('palimpsest.fzf').browse('locations')<cr>", desc = "Browse locations", icon = "󰍎" },
				{ "<leader>vFc", "<cmd>lua require('palimpsest.fzf').browse('cities')<cr>", desc = "Browse cities", icon = "󰄝" },
				{ "<leader>vFv", "<cmd>lua require('palimpsest.fzf').browse('events')<cr>", desc = "Browse events", icon = "󰙹" },
				{ "<leader>vFt", "<cmd>lua require('palimpsest.fzf').browse('themes')<cr>", desc = "Browse themes", icon = "󰓹" },
				{ "<leader>vFT", "<cmd>lua require('palimpsest.fzf').browse('tags')<cr>", desc = "Browse tags", icon = "󰓹" },
				{ "<leader>vFP", "<cmd>lua require('palimpsest.fzf').browse('poems')<cr>", desc = "Browse poems", icon = "󰎈" },
				{ "<leader>vFr", "<cmd>lua require('palimpsest.fzf').browse('references')<cr>", desc = "Browse references", icon = "󰈙" },
				-- Manuscript browse
				{ "<leader>vFm", "<cmd>lua require('palimpsest.fzf').browse('manuscript')<cr>", desc = "Browse manuscript", icon = "󱥏" },
				{ "<leader>vFM", group = "manuscript entities", icon = "󱥏" },
				{ "<leader>vFMc", "<cmd>lua require('palimpsest.fzf').browse('manuscript-chapters')<cr>", desc = "Manuscript chapters", icon = "󰯂" },
				{ "<leader>vFMh", "<cmd>lua require('palimpsest.fzf').browse('manuscript-characters')<cr>", desc = "Manuscript characters", icon = "󰙃" },
				{ "<leader>vFMs", "<cmd>lua require('palimpsest.fzf').browse('manuscript-scenes')<cr>", desc = "Manuscript scenes", icon = "󰕧" },
				{ "<leader>v/w", "<cmd>lua require('palimpsest.fzf').search('wiki')<cr>", desc = "Search wiki", icon = "󰍉" },
				{ "<leader>v/j", "<cmd>lua require('palimpsest.fzf').search('journal')<cr>", desc = "Search journal", icon = "󰍉" },
				{ "<leader>v/m", "<cmd>lua require('palimpsest.fzf').search('manuscript')<cr>", desc = "Search manuscript", icon = "󰍉" },
			},
		})
		-- Remove unnecessary keymaps (pcall in case vimwiki hasn't set them yet)
		pcall(vim.api.nvim_del_keymap, "n", "<leader>v<leader>y") -- Diary (yesterday)
		pcall(vim.api.nvim_del_keymap, "n", "<leader>v<leader>m") -- Diary (tomorrow)
	end

	-- Context-aware entity keymaps via BufEnter autocmd
	local group = vim.api.nvim_create_augroup("PalimpsestContextKeymaps", { clear = true })
	vim.api.nvim_create_autocmd("BufEnter", {
		group = group,
		pattern = { "*.md", "*.yaml" },
		callback = function(args)
			local filepath = vim.api.nvim_buf_get_name(args.buf)
			if filepath:find("data/wiki/", 1, true) or filepath:find("data/metadata/", 1, true) then
				register_context_keymaps(args.buf, prefix)
			end
		end,
	})
end

return M
