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
		all = { journal_dir, wiki_dir },
		journal = journal_dir,
		wiki = wiki_dir,
		people = wiki_dir .. "/people",
		entries = wiki_dir .. "/entries",
		locations = wiki_dir .. "/locations",
		cities = wiki_dir .. "/cities",
		events = wiki_dir .. "/events",
		themes = wiki_dir .. "/themes",
		tags = wiki_dir .. "/tags",
		poems = wiki_dir .. "/poems",
		references = wiki_dir .. "/references",
		-- Manuscript paths
		manuscript = wiki_dir .. "/manuscript",
		["manuscript-entries"] = wiki_dir .. "/manuscript/entries",
		["manuscript-characters"] = wiki_dir .. "/manuscript/characters",
		["manuscript-arcs"] = wiki_dir .. "/manuscript/arcs",
		["manuscript-events"] = wiki_dir .. "/manuscript/events",
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
		-- Manuscript paths
		manuscript = wiki_dir .. "/manuscript",
		["manuscript-entries"] = wiki_dir .. "/manuscript/entries",
		["manuscript-characters"] = wiki_dir .. "/manuscript/characters",
		["manuscript-arcs"] = wiki_dir .. "/manuscript/arcs",
		["manuscript-events"] = wiki_dir .. "/manuscript/events",
	}

	local search_path = entity_paths[entity_type]

	if not search_path then
		vim.notify("Invalid search type: " .. (entity_type or "nil"), vim.log.levels.ERROR)
		return
	end

	-- Verify path exists
	if vim.fn.isdirectory(search_path) == 0 then
		vim.notify("Directory not found: " .. search_path, vim.log.levels.WARN)
		return
	end

	-- Use live_grep with single directory
	fzf.live_grep({
		prompt = "Search " .. entity_type .. "> ",
		cwd = search_path,
		winopts = {
			height = 0.85,
			width = 0.80,
		},
	})
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
		-- Manuscript pages
		{ name = "Manuscript Homepage", path = wiki_dir .. "/manuscript/index.md" },
		{ name = "Manuscript Entries", path = wiki_dir .. "/manuscript/entries/entries.md" },
		{ name = "Manuscript Characters", path = wiki_dir .. "/manuscript/characters/characters.md" },
		{ name = "Manuscript Arcs", path = wiki_dir .. "/manuscript/arcs/arcs.md" },
		{ name = "Manuscript Events", path = wiki_dir .. "/manuscript/events/events.md" },
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
