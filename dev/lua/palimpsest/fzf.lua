-- fzf-lua integration for Palimpsest wiki
local palimpsest = require("palimpsest.config")
local M = {}

-- Browse wiki entities by type
function M.browse(entity_type)
	local has_fzf, fzf = pcall(require, "fzf-lua")
	if not has_fzf then
		vim.notify("fzf-lua is not installed", vim.log.levels.ERROR)
		return
	end

	local wiki_dir = palimpsest.paths.wiki
	local journal_dir = palimpsest.paths.journal

	-- Define search paths for each entity type
	local entity_paths = {
		all = wiki_dir,
		journal = journal_dir,
		people = wiki_dir .. "/people",
		entries = wiki_dir .. "/entries",
		locations = wiki_dir .. "/locations",
		cities = wiki_dir .. "/cities",
		events = wiki_dir .. "/events",
		themes = wiki_dir .. "/themes",
		tags = wiki_dir .. "/tags",
		poems = wiki_dir .. "/poems",
		references = wiki_dir .. "/references",
	}

	local search_path = entity_paths[entity_type] or wiki_dir

	-- Check if path exists
	if vim.fn.isdirectory(search_path) == 0 then
		vim.notify("Directory not found: " .. search_path, vim.log.levels.ERROR)
		return
	end

	-- Use fzf-lua files with the specific directory
	fzf.files({
		prompt = "Palimpsest: " .. (entity_type or "all") .. "> ",
		cwd = search_path,
		cmd = "fd -t f -e md",
		winopts = {
			height = 0.85,
			width = 0.80,
			preview = {
				layout = "vertical",
				vertical = "down:60%",
			},
		},
	})
end

-- Search wiki content by entity type
function M.search(entity_type)
	local has_fzf, fzf = pcall(require, "fzf-lua")
	if not has_fzf then
		vim.notify("fzf-lua is not installed", vim.log.levels.ERROR)
		return
	end

	local wiki_dir = palimpsest.paths.wiki
	local journal_dir = palimpsest.paths.journal

	-- Define search paths for each entity type
	local entity_paths = {
		all = { wiki_dir, journal_dir },
		wiki = wiki_dir,
		journal = journal_dir,
		people = wiki_dir .. "/people",
		entries = wiki_dir .. "/entries",
		locations = wiki_dir .. "/locations",
		cities = wiki_dir .. "/cities",
		events = wiki_dir .. "/events",
		themes = wiki_dir .. "/themes",
		tags = wiki_dir .. "/tags",
		poems = wiki_dir .. "/poems",
		references = wiki_dir .. "/references",
	}

	local search_paths = entity_paths[entity_type]

	-- Handle both single path and multiple paths
	if type(search_paths) == "string" then
		search_paths = { search_paths }
	elseif not search_paths then
		search_paths = { wiki_dir }
	end

	-- Verify all paths exist
	for _, path in ipairs(search_paths) do
		if vim.fn.isdirectory(path) == 0 then
			vim.notify("Directory not found: " .. path, vim.log.levels.WARN)
		end
	end

	-- For multiple paths, use glob pattern to search both
	if #search_paths > 1 then
		-- Create a glob pattern that matches both directories
		local search_pattern = ""
		for i, path in ipairs(search_paths) do
			if i > 1 then
				search_pattern = search_pattern .. " "
			end
			search_pattern = search_pattern .. path
		end

		fzf.live_grep({
			prompt = "Search All Content: " .. (entity_type or "all") .. "> ",
			cmd = "rg --column --line-number --no-heading --color=always --smart-case -- ",
			-- fzf-lua will search in all specified directories
			cwd = search_paths[1], -- Use first as base
			rg_opts = "--hidden --follow -g '!.git' -- " .. table.concat(search_paths, " "),
			winopts = {
				height = 0.85,
				width = 0.80,
			},
		})
	else
		-- Single path, simpler
		fzf.live_grep({
			prompt = "Search: " .. (entity_type or "all") .. "> ",
			cwd = search_paths[1],
			winopts = {
				height = 0.85,
				width = 0.80,
			},
		})
	end
end

-- Quick access to specific wiki pages
function M.quick_access()
	local has_fzf, fzf = pcall(require, "fzf-lua")
	if not has_fzf then
		vim.notify("fzf-lua is not installed", vim.log.levels.ERROR)
		return
	end

	local wiki_dir = palimpsest.paths.wiki

	-- Define quick access pages
	local pages = {
		{ name = "Wiki Homepage", path = wiki_dir .. "/index.md" },
		{ name = "Statistics Dashboard", path = wiki_dir .. "/stats.md" },
		{ name = "Timeline", path = wiki_dir .. "/timeline.md" },
		{ name = "People Index", path = wiki_dir .. "/people.md" },
		{ name = "Entries Index", path = wiki_dir .. "/entries.md" },
		{ name = "Locations Index", path = wiki_dir .. "/locations.md" },
		{ name = "Cities Index", path = wiki_dir .. "/cities.md" },
		{ name = "Events Index", path = wiki_dir .. "/events.md" },
		{ name = "Themes Index", path = wiki_dir .. "/themes.md" },
		{ name = "Tags Index", path = wiki_dir .. "/tags.md" },
		{ name = "Poems Index", path = wiki_dir .. "/poems.md" },
		{ name = "References Index", path = wiki_dir .. "/references.md" },
	}

	-- Filter to only existing pages and format for fzf
	local entries = {}
	for _, page in ipairs(pages) do
		if vim.fn.filereadable(page.path) == 1 then
			-- Format: "Name :: /path/to/file"
			table.insert(entries, page.name .. " :: " .. page.path)
		end
	end

	if #entries == 0 then
		vim.notify("No wiki pages found. Generate them first with :PalimpsestExport", vim.log.levels.WARN)
		return
	end

	-- Use fzf_exec for custom entries
	fzf.fzf_exec(entries, {
		prompt = "Palimpsest Wiki Pages> ",
		actions = {
			["default"] = function(selected)
				if not selected or #selected == 0 then
					return
				end
				-- Extract path from "Name :: /path/to/file" format
				local path = selected[1]:match(":: (.+)$")
				if path then
					vim.cmd("edit " .. path)
				end
			end,
		},
		winopts = {
			height = 0.50,
			width = 0.60,
			preview = {
				layout = "vertical",
				vertical = "down:60%",
			},
		},
		fzf_opts = {
			["--delimiter"] = "::",
			["--with-nth"] = "1", -- Only show the name part in fzf
		},
	})
end

return M
