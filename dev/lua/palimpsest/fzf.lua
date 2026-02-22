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
		people = wiki_dir .. "/journal/people",
		entries = wiki_dir .. "/journal/entries",
		locations = wiki_dir .. "/journal/locations",
		cities = wiki_dir .. "/journal/cities",
		events = wiki_dir .. "/journal/events",
		themes = wiki_dir .. "/journal/themes",
		tags = wiki_dir .. "/journal/tags",
		poems = wiki_dir .. "/journal/poems",
		references = wiki_dir .. "/journal/references",
		motifs = wiki_dir .. "/journal/motifs",
		-- Manuscript paths
		manuscript = wiki_dir .. "/manuscript",
		["manuscript-chapters"] = wiki_dir .. "/manuscript/chapters",
		["manuscript-characters"] = wiki_dir .. "/manuscript/characters",
		["manuscript-scenes"] = wiki_dir .. "/manuscript/scenes",
	}

	local search_path = entity_paths[entity_type] or wiki_dir

	-- Handle multi-directory case (e.g., 'all' = wiki + journal)
	if type(search_path) == "table" then
		-- Verify at least one directory exists
		local valid_dirs = {}
		for _, dir in ipairs(search_path) do
			if vim.fn.isdirectory(dir) == 1 then
				table.insert(valid_dirs, vim.fn.shellescape(dir))
			end
		end
		if #valid_dirs == 0 then
			vim.notify("No wiki directories found", vim.log.levels.ERROR)
			return
		end

		fzf.files({
			prompt = "Palimpsest: " .. (entity_type or "all") .. "> ",
			cmd = "fd -t f -e md . " .. table.concat(valid_dirs, " "),
			winopts = {
				height = 0.85,
				width = 0.80,
				preview = {
					layout = "vertical",
					vertical = "down:60%",
				},
			},
		})
		return
	end

	-- Single directory case
	if vim.fn.isdirectory(search_path) == 0 then
		vim.notify("Directory not found: " .. search_path, vim.log.levels.ERROR)
		return
	end

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
		people = wiki_dir .. "/journal/people",
		entries = wiki_dir .. "/journal/entries",
		locations = wiki_dir .. "/journal/locations",
		cities = wiki_dir .. "/journal/cities",
		events = wiki_dir .. "/journal/events",
		themes = wiki_dir .. "/journal/themes",
		tags = wiki_dir .. "/journal/tags",
		poems = wiki_dir .. "/journal/poems",
		references = wiki_dir .. "/journal/references",
		motifs = wiki_dir .. "/journal/motifs",
		-- Manuscript paths
		manuscript = wiki_dir .. "/manuscript",
		["manuscript-chapters"] = wiki_dir .. "/manuscript/chapters",
		["manuscript-characters"] = wiki_dir .. "/manuscript/characters",
		["manuscript-scenes"] = wiki_dir .. "/manuscript/scenes",
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

	-- Define quick access pages (must match actual generated paths)
	local pages = {
		{ name = "Wiki Homepage", path = wiki_dir .. "/index.md" },
		{ name = "People Index", path = wiki_dir .. "/indexes/people-index.md" },
		{ name = "Entries Index", path = wiki_dir .. "/indexes/entry-index.md" },
		{ name = "Places Index", path = wiki_dir .. "/indexes/places-index.md" },
		{ name = "Events Index", path = wiki_dir .. "/indexes/event-index.md" },
		{ name = "Arcs Index", path = wiki_dir .. "/indexes/arc-index.md" },
		{ name = "Tags Index", path = wiki_dir .. "/indexes/tags-index.md" },
		{ name = "Themes Index", path = wiki_dir .. "/indexes/themes-index.md" },
		{ name = "Poems Index", path = wiki_dir .. "/indexes/poems-index.md" },
		{ name = "References Index", path = wiki_dir .. "/indexes/references-index.md" },
		{ name = "Manuscript Index", path = wiki_dir .. "/indexes/manuscript-index.md" },
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
		vim.notify("No wiki pages found. Generate them first with :PalimpsestGenerate", vim.log.levels.WARN)
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
