local palimpsest_icon = ""
local has_wk, wk = pcall(require, "which-key")

local M = {}

function M.setup()
	if not has_wk then
		vim.notify("which-key not found - palimpsest keymaps disabled", vim.log.levels.WARN)
		return
	end

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
				-- Entity commands (YAML floating window)
				{ "<leader>pe", group = "entity" },
				{ "<leader>pee", "<cmd>PalimpsestEdit<cr>", desc = "Edit metadata (float)" },
				{ "<leader>pen", "<cmd>PalimpsestNew<cr>", desc = "New entity..." },
				{ "<leader>pes", "<cmd>PalimpsestAddSource<cr>", desc = "Add source to scene" },
				{ "<leader>peb", "<cmd>PalimpsestAddBasedOn<cr>", desc = "Add based_on to character" },
				{ "<leader>pel", "<cmd>PalimpsestLinkToManuscript<cr>", desc = "Link to manuscript" },
				{ "<leader>pex", "<cmd>PalimpsestMetadataExport<cr>", desc = "Export metadata YAML" },
				{ "<leader>per", "<cmd>PalimpsestCacheRefresh<cr>", desc = "Refresh entity cache" },
				-- Wiki operations
				{ "<leader>pE", "<cmd>PalimpsestExport<cr>", desc = "Export all to wiki" },
				{ "<leader>pS", "<cmd>PalimpsestSync<cr>", desc = "Wiki sync" },
				{ "<leader>pL", "<cmd>PalimpsestLint<cr>", desc = "Wiki lint" },
				{ "<leader>pG", "<cmd>PalimpsestGenerate<cr>", desc = "Wiki generate" },
				-- Validators
				{ "<leader>pv", group = "validators" },
				{ "<leader>pvw", "<cmd>PalimpsestValidate check<cr>", desc = "Validate wiki links" },
				{ "<leader>pvo", "<cmd>PalimpsestValidate orphans<cr>", desc = "Find orphaned pages" },
				{ "<leader>pvf", "<cmd>PalimpsestValidateFrontmatter<cr>", desc = "Validate frontmatter" },
				{ "<leader>pvm", "<cmd>PalimpsestValidateMetadata<cr>", desc = "Validate metadata" },
				{ "<leader>pvl", "<cmd>PalimpsestValidateLinks<cr>", desc = "Validate markdown links" },
				{ "<leader>ps", "<cmd>PalimpsestStats<cr>", desc = "Statistics dashboard" },
				{ "<leader>pa", "<cmd>PalimpsestAnalysis<cr>", desc = "Analysis report" },
				{ "<leader>ph", "<cmd>PalimpsestIndex<cr>", desc = "Wiki homepage" },
				-- Manuscript commands
				{ "<leader>pm", group = "manuscript" },
				{ "<leader>pme", "<cmd>PalimpsestManuscriptExport<cr>", desc = "Export manuscript" },
				{ "<leader>pmE", "<cmd>PalimpsestManuscriptExport ", desc = "Export manuscript entity..." },
				{ "<leader>pmi", "<cmd>PalimpsestManuscriptImport<cr>", desc = "Import manuscript edits" },
				{ "<leader>pmh", "<cmd>PalimpsestManuscriptIndex<cr>", desc = "Manuscript homepage" },
				-- fzf-lua wiki browser
				{ "<leader>pf", "<cmd>PalimpsestQuickAccess<cr>", desc = "Quick access wiki pages" },
				{ "<leader>pF", group = "browse entities" },
				{ "<leader>pFa", "<cmd>lua require('palimpsest.fzf').browse('all')<cr>", desc = "Browse wiki" },
				{ "<leader>pFj", "<cmd>lua require('palimpsest.fzf').browse('journal')<cr>", desc = "Browse journal" },
				{ "<leader>pFp", "<cmd>lua require('palimpsest.fzf').browse('people')<cr>", desc = "Browse people" },
				{ "<leader>pFe", "<cmd>lua require('palimpsest.fzf').browse('entries')<cr>", desc = "Browse entries" },
				{ "<leader>pFl", "<cmd>lua require('palimpsest.fzf').browse('locations')<cr>", desc = "Browse locations" },
				{ "<leader>pFc", "<cmd>lua require('palimpsest.fzf').browse('cities')<cr>", desc = "Browse cities" },
				{ "<leader>pFv", "<cmd>lua require('palimpsest.fzf').browse('events')<cr>", desc = "Browse events" },
				{ "<leader>pFt", "<cmd>lua require('palimpsest.fzf').browse('themes')<cr>", desc = "Browse themes" },
				{ "<leader>pFT", "<cmd>lua require('palimpsest.fzf').browse('tags')<cr>", desc = "Browse tags" },
				{ "<leader>pFP", "<cmd>lua require('palimpsest.fzf').browse('poems')<cr>", desc = "Browse poems" },
				{ "<leader>pFr", "<cmd>lua require('palimpsest.fzf').browse('references')<cr>", desc = "Browse references" },
				-- Manuscript browse
				{ "<leader>pFm", "<cmd>lua require('palimpsest.fzf').browse('manuscript')<cr>", desc = "Browse manuscript" },
				{ "<leader>pFM", group = "manuscript entities" },
				{ "<leader>pFMe", "<cmd>lua require('palimpsest.fzf').browse('manuscript-entries')<cr>", desc = "Manuscript entries" },
				{ "<leader>pFMc", "<cmd>lua require('palimpsest.fzf').browse('manuscript-characters')<cr>", desc = "Manuscript characters" },
				{ "<leader>pFMa", "<cmd>lua require('palimpsest.fzf').browse('manuscript-arcs')<cr>", desc = "Manuscript arcs" },
				{ "<leader>pFMv", "<cmd>lua require('palimpsest.fzf').browse('manuscript-events')<cr>", desc = "Manuscript events" },
				{ "<leader>p/w", "<cmd>lua require('palimpsest.fzf').search('wiki')<cr>", desc = "Search wiki" },
				{ "<leader>p/j", "<cmd>lua require('palimpsest.fzf').search('journal')<cr>", desc = "Search journal" },
				{ "<leader>p/m", "<cmd>lua require('palimpsest.fzf').search('manuscript')<cr>", desc = "Search manuscript" },
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
				-- Entity commands (YAML floating window)
				{ "<leader>ve", group = "entity" },
				{ "<leader>vee", "<cmd>PalimpsestEdit<cr>", desc = "Edit metadata (float)" },
				{ "<leader>ven", "<cmd>PalimpsestNew<cr>", desc = "New entity..." },
				{ "<leader>ves", "<cmd>PalimpsestAddSource<cr>", desc = "Add source to scene" },
				{ "<leader>veb", "<cmd>PalimpsestAddBasedOn<cr>", desc = "Add based_on to character" },
				{ "<leader>vel", "<cmd>PalimpsestLinkToManuscript<cr>", desc = "Link to manuscript" },
				{ "<leader>vex", "<cmd>PalimpsestMetadataExport<cr>", desc = "Export metadata YAML" },
				{ "<leader>ver", "<cmd>PalimpsestCacheRefresh<cr>", desc = "Refresh entity cache" },
				-- Wiki operations
				{ "<leader>vE", "<cmd>PalimpsestExport<cr>", desc = "Export all to wiki" },
				{ "<leader>vS", "<cmd>PalimpsestSync<cr>", desc = "Wiki sync" },
				{ "<leader>vL", "<cmd>PalimpsestLint<cr>", desc = "Wiki lint" },
				{ "<leader>vG", "<cmd>PalimpsestGenerate<cr>", desc = "Wiki generate" },
				-- Validators
				{ "<leader>vv", group = "validators" },
				{ "<leader>vvw", "<cmd>PalimpsestValidate check<cr>", desc = "Validate wiki links" },
				{ "<leader>vvo", "<cmd>PalimpsestValidate orphans<cr>", desc = "Find orphaned pages" },
				{ "<leader>vvf", "<cmd>PalimpsestValidateFrontmatter<cr>", desc = "Validate frontmatter" },
				{ "<leader>vvm", "<cmd>PalimpsestValidateMetadata<cr>", desc = "Validate metadata" },
				{ "<leader>vvl", "<cmd>PalimpsestValidateLinks<cr>", desc = "Validate markdown links" },
				{ "<leader>vs", "<cmd>PalimpsestStats<cr>", desc = "Statistics dashboard" },
				{ "<leader>va", "<cmd>PalimpsestAnalysis<cr>", desc = "Analysis report" },
				{ "<leader>vh", "<cmd>PalimpsestIndex<cr>", desc = "Wiki homepage" },
				-- Manuscript commands
				{ "<leader>vm", group = "manuscript" },
				{ "<leader>vme", "<cmd>PalimpsestManuscriptExport<cr>", desc = "Export manuscript" },
				{ "<leader>vmE", "<cmd>PalimpsestManuscriptExport ", desc = "Export manuscript entity..." },
				{ "<leader>vmi", "<cmd>PalimpsestManuscriptImport<cr>", desc = "Import manuscript edits" },
				{ "<leader>vmh", "<cmd>PalimpsestManuscriptIndex<cr>", desc = "Manuscript homepage" },
				-- fzf-lua wiki browser
				{ "<leader>vf", "<cmd>PalimpsestQuickAccess<cr>", desc = "Quick access wiki pages" },
				{ "<leader>vF", group = "browse entities" },
				{ "<leader>vFa", "<cmd>lua require('palimpsest.fzf').browse('all')<cr>", desc = "Browse wiki" },
				{ "<leader>vFj", "<cmd>lua require('palimpsest.fzf').browse('journal')<cr>", desc = "Browse journal" },
				{ "<leader>vFp", "<cmd>lua require('palimpsest.fzf').browse('people')<cr>", desc = "Browse people" },
				{ "<leader>vFe", "<cmd>lua require('palimpsest.fzf').browse('entries')<cr>", desc = "Browse entries" },
				{ "<leader>vFl", "<cmd>lua require('palimpsest.fzf').browse('locations')<cr>", desc = "Browse locations" },
				{ "<leader>vFc", "<cmd>lua require('palimpsest.fzf').browse('cities')<cr>", desc = "Browse cities" },
				{ "<leader>vFv", "<cmd>lua require('palimpsest.fzf').browse('events')<cr>", desc = "Browse events" },
				{ "<leader>vFt", "<cmd>lua require('palimpsest.fzf').browse('themes')<cr>", desc = "Browse themes" },
				{ "<leader>vFT", "<cmd>lua require('palimpsest.fzf').browse('tags')<cr>", desc = "Browse tags" },
				{ "<leader>vFP", "<cmd>lua require('palimpsest.fzf').browse('poems')<cr>", desc = "Browse poems" },
				{ "<leader>vFr", "<cmd>lua require('palimpsest.fzf').browse('references')<cr>", desc = "Browse references" },
				-- Manuscript browse
				{ "<leader>vFm", "<cmd>lua require('palimpsest.fzf').browse('manuscript')<cr>", desc = "Browse manuscript" },
				{ "<leader>vFM", group = "manuscript entities" },
				{ "<leader>vFMe", "<cmd>lua require('palimpsest.fzf').browse('manuscript-entries')<cr>", desc = "Manuscript entries" },
				{ "<leader>vFMc", "<cmd>lua require('palimpsest.fzf').browse('manuscript-characters')<cr>", desc = "Manuscript characters" },
				{ "<leader>vFMa", "<cmd>lua require('palimpsest.fzf').browse('manuscript-arcs')<cr>", desc = "Manuscript arcs" },
				{ "<leader>vFMv", "<cmd>lua require('palimpsest.fzf').browse('manuscript-events')<cr>", desc = "Manuscript events" },
				{ "<leader>v/w", "<cmd>lua require('palimpsest.fzf').search('wiki')<cr>", desc = "Search wiki" },
				{ "<leader>v/j", "<cmd>lua require('palimpsest.fzf').search('journal')<cr>", desc = "Search journal" },
				{ "<leader>v/m", "<cmd>lua require('palimpsest.fzf').search('manuscript')<cr>", desc = "Search manuscript" },
			},
		})
		-- Remove unnecessary keymaps
		vim.api.nvim_del_keymap("n", "<leader>v<leader>y") -- Diary (yesterday)
		vim.api.nvim_del_keymap("n", "<leader>v<leader>m") -- Diary (tomorrow)
	end
end

return M
