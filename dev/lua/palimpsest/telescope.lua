-- Telescope integration for Palimpsest wiki
local M = {}

-- Get the project root directory
local function get_project_root()
	local markers = { "pyproject.toml", ".git", "palimpsest.db" }
	local path = vim.fn.expand("%:p:h")

	while path ~= "/" do
		for _, marker in ipairs(markers) do
			if vim.fn.filereadable(path .. "/" .. marker) == 1 or vim.fn.isdirectory(path .. "/" .. marker) == 1 then
				return path
			end
		end
		path = vim.fn.fnamemodify(path, ":h")
	end

	return vim.fn.getcwd()
end

-- Browse wiki entities by type
function M.browse(entity_type)
	local has_telescope, telescope = pcall(require, "telescope.builtin")
	if not has_telescope then
		vim.notify("Telescope is not installed", vim.log.levels.ERROR)
		return
	end

	local root = get_project_root()
	local wiki_dir = root .. "/data/wiki"

	-- Define search paths for each entity type
	local entity_paths = {
		all = wiki_dir,
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

	-- Use telescope find_files with the specific directory
	telescope.find_files({
		prompt_title = "Palimpsest Wiki: " .. (entity_type or "all"),
		cwd = search_path,
		find_command = { "fd", "-t", "f", "-e", "md" },
	})
end

-- Search wiki content by entity type
function M.search(entity_type)
	local has_telescope, telescope = pcall(require, "telescope.builtin")
	if not has_telescope then
		vim.notify("Telescope is not installed", vim.log.levels.ERROR)
		return
	end

	local root = get_project_root()
	local wiki_dir = root .. "/data/wiki"

	local entity_paths = {
		all = wiki_dir,
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

	if vim.fn.isdirectory(search_path) == 0 then
		vim.notify("Directory not found: " .. search_path, vim.log.levels.ERROR)
		return
	end

	-- Use telescope live_grep with the specific directory
	telescope.live_grep({
		prompt_title = "Search Wiki: " .. (entity_type or "all"),
		cwd = search_path,
	})
end

-- Quick access to specific wiki pages
function M.quick_access()
	local has_telescope, telescope_builtin = pcall(require, "telescope.builtin")
	local has_pickers, pickers = pcall(require, "telescope.pickers")
	local has_finders, finders = pcall(require, "telescope.finders")
	local has_conf, conf = pcall(require, "telescope.config")
	local has_actions, actions = pcall(require, "telescope.actions")
	local has_action_state, action_state = pcall(require, "telescope.actions.state")

	if not (has_telescope and has_pickers and has_finders and has_conf and has_actions and has_action_state) then
		vim.notify("Telescope dependencies not available", vim.log.levels.ERROR)
		return
	end

	local root = get_project_root()
	local wiki_dir = root .. "/data/wiki"

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

	-- Filter to only existing pages
	local existing_pages = {}
	for _, page in ipairs(pages) do
		if vim.fn.filereadable(page.path) == 1 then
			table.insert(existing_pages, page)
		end
	end

	-- Create telescope picker
	pickers
		.new({}, {
			prompt_title = "Palimpsest Wiki Pages",
			finder = finders.new_table({
				results = existing_pages,
				entry_maker = function(entry)
					return {
						value = entry,
						display = entry.name,
						ordinal = entry.name,
						path = entry.path,
					}
				end,
			}),
			sorter = conf.values.generic_sorter({}),
			attach_mappings = function(prompt_bufnr, map)
				actions.select_default:replace(function()
					actions.close(prompt_bufnr)
					local selection = action_state.get_selected_entry()
					vim.cmd("edit " .. selection.path)
				end)
				return true
			end,
		})
		:find()
end

-- Setup telescope extension
function M.setup()
	-- Register with telescope if available
	local has_telescope, telescope = pcall(require, "telescope")
	if has_telescope then
		telescope.register_extension({
			exports = {
				palimpsest = M.quick_access,
				browse = M.browse,
				search = M.search,
			},
		})
	end
end

return M
