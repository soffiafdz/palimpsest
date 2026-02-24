-- Picker integration for Palimpsest wiki (fzf-lua with snacks.nvim fallback)
local palimpsest = require("palimpsest.config")
local M = {}

--- Detect the available picker backend.
--- Prefers fzf-lua; falls back to snacks.nvim picker.
--- @return string|nil backend "fzf" or "snacks", or nil if none available
--- @return table|nil picker the picker module
local function get_picker()
	local has_fzf, fzf = pcall(require, "fzf-lua")
	if has_fzf then
		return "fzf", fzf
	end
	local has_snacks, snacks = pcall(require, "snacks")
	if has_snacks and snacks.picker then
		return "snacks", snacks.picker
	end
	return nil, nil
end

-- Entity type to directory path mapping (shared by browse and search)
local function entity_paths()
	local wiki_dir = palimpsest.paths.wiki
	local journal_dir = palimpsest.paths.journal
	return {
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
		manuscript = wiki_dir .. "/manuscript",
		["manuscript-chapters"] = wiki_dir .. "/manuscript/chapters",
		["manuscript-characters"] = wiki_dir .. "/manuscript/characters",
		["manuscript-scenes"] = wiki_dir .. "/manuscript/scenes",
	}
end

-- Browse wiki entities by type
function M.browse(entity_type)
	local backend, picker = get_picker()
	if not backend then
		vim.notify("No picker available (install fzf-lua or snacks.nvim)", vim.log.levels.ERROR)
		return
	end

	local paths = entity_paths()
	local search_path = paths[entity_type] or palimpsest.paths.wiki
	local prompt = "Palimpsest: " .. (entity_type or "all") .. "> "

	-- Multi-directory case (e.g., 'all' = wiki + journal)
	if type(search_path) == "table" then
		local valid_dirs = {}
		for _, dir in ipairs(search_path) do
			if vim.fn.isdirectory(dir) == 1 then
				table.insert(valid_dirs, dir)
			end
		end
		if #valid_dirs == 0 then
			vim.notify("No wiki directories found", vim.log.levels.ERROR)
			return
		end

		if backend == "fzf" then
			local shellescape_dirs = {}
			for _, dir in ipairs(valid_dirs) do
				table.insert(shellescape_dirs, vim.fn.shellescape(dir))
			end
			picker.files({
				prompt = prompt,
				cmd = "fd -t f -e md . " .. table.concat(shellescape_dirs, " "),
				winopts = {
					height = 0.85,
					width = 0.80,
					preview = { layout = "vertical", vertical = "down:60%" },
				},
			})
		else
			picker.files({
				title = prompt,
				dirs = valid_dirs,
			})
		end
		return
	end

	-- Single directory case
	if vim.fn.isdirectory(search_path) == 0 then
		vim.notify("Directory not found: " .. search_path, vim.log.levels.ERROR)
		return
	end

	if backend == "fzf" then
		picker.files({
			prompt = prompt,
			cwd = search_path,
			cmd = "fd -t f -e md",
			winopts = {
				height = 0.85,
				width = 0.80,
				preview = { layout = "vertical", vertical = "down:60%" },
			},
		})
	else
		picker.files({
			title = prompt,
			cwd = search_path,
		})
	end
end

-- Search wiki content by entity type
function M.search(entity_type)
	local backend, picker = get_picker()
	if not backend then
		vim.notify("No picker available (install fzf-lua or snacks.nvim)", vim.log.levels.ERROR)
		return
	end

	local paths = entity_paths()
	local search_path = paths[entity_type]

	if not search_path then
		vim.notify("Invalid search type: " .. (entity_type or "nil"), vim.log.levels.ERROR)
		return
	end

	if type(search_path) == "table" then
		search_path = search_path[1]
	end

	if vim.fn.isdirectory(search_path) == 0 then
		vim.notify("Directory not found: " .. search_path, vim.log.levels.WARN)
		return
	end

	if backend == "fzf" then
		picker.live_grep({
			prompt = "Search " .. entity_type .. "> ",
			cwd = search_path,
			winopts = { height = 0.85, width = 0.80 },
		})
	else
		picker.grep({
			title = "Search " .. entity_type,
			cwd = search_path,
		})
	end
end

-- Quick access to specific wiki pages
function M.quick_access()
	local backend, picker = get_picker()
	if not backend then
		vim.notify("No picker available (install fzf-lua or snacks.nvim)", vim.log.levels.ERROR)
		return
	end

	local wiki_dir = palimpsest.paths.wiki

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

	-- Filter to existing pages
	local existing = {}
	for _, page in ipairs(pages) do
		if vim.fn.filereadable(page.path) == 1 then
			table.insert(existing, page)
		end
	end

	if #existing == 0 then
		vim.notify("No wiki pages found. Generate them first with :PalimpsestGenerate", vim.log.levels.WARN)
		return
	end

	if backend == "fzf" then
		local entries = {}
		for _, page in ipairs(existing) do
			table.insert(entries, page.name .. " :: " .. page.path)
		end

		picker.fzf_exec(entries, {
			prompt = "Palimpsest Wiki Pages> ",
			actions = {
				["default"] = function(selected)
					if not selected or #selected == 0 then
						return
					end
					local path = selected[1]:match(":: (.+)$")
					if path then
						vim.cmd("edit " .. path)
					end
				end,
			},
			winopts = {
				height = 0.50,
				width = 0.60,
				preview = { layout = "vertical", vertical = "down:60%" },
			},
			fzf_opts = {
				["--delimiter"] = "::",
				["--with-nth"] = "1",
			},
		})
	else
		local items = {}
		for _, page in ipairs(existing) do
			table.insert(items, { text = page.name, file = page.path })
		end

		picker.pick({
			title = "Palimpsest Wiki Pages",
			items = items,
			format = "text",
			confirm = function(p, item)
				p:close()
				if item and item.file then
					vim.cmd("edit " .. item.file)
				end
			end,
		})
	end
end

return M
