-- Palimpsest commands for wiki export, validation, and statistics
local M = {}

-- Get the project root directory
local function get_project_root()
	-- Try to find palimpsest project root by looking for marker files
	local markers = { "pyproject.toml", ".git", "palimpsest.db" }
	local path = vim.fn.expand("%:p:h")

	-- Walk up the directory tree
	while path ~= "/" do
		for _, marker in ipairs(markers) do
			if vim.fn.filereadable(path .. "/" .. marker) == 1 or vim.fn.isdirectory(path .. "/" .. marker) == 1 then
				return path
			end
		end
		path = vim.fn.fnamemodify(path, ":h")
	end

	-- Fallback to current working directory
	return vim.fn.getcwd()
end

-- Execute a shell command and capture output
local function execute_command(cmd, opts)
	opts = opts or {}
	local notify = opts.notify ~= false
	local show_output = opts.show_output ~= false

	if notify then
		vim.notify("Running: " .. cmd, vim.log.levels.INFO)
	end

	-- Execute command and capture output
	local output = vim.fn.system(cmd)
	local exit_code = vim.v.shell_error

	-- Check for errors
	if exit_code ~= 0 then
		vim.notify("Command failed with exit code " .. exit_code, vim.log.levels.ERROR)
		if show_output and output and output ~= "" then
			vim.notify(output, vim.log.levels.ERROR)
		end
		return false, output
	end

	-- Show success
	if notify then
		vim.notify("Command completed successfully", vim.log.levels.INFO)
	end

	if show_output and output and output ~= "" then
		-- Open output in a split
		vim.cmd("new")
		vim.api.nvim_buf_set_lines(0, 0, -1, false, vim.split(output, "\n"))
		vim.bo.buftype = "nofile"
		vim.bo.bufhidden = "wipe"
		vim.bo.filetype = "palimpsest-output"
	end

	return true, output
end

-- Export entities to wiki
function M.export(entity_type)
	entity_type = entity_type or "all"

	local valid_types = {
		"all",
		"index",
		"stats",
		"timeline",
		"analysis",
		"entries",
		"people",
		"locations",
		"cities",
		"events",
		"themes",
		"tags",
		"poems",
		"references",
		"manuscript",
		"manuscript-entries",
		"manuscript-characters",
		"manuscript-arcs",
		"manuscript-events",
	}

	-- Validate entity type
	if not vim.tbl_contains(valid_types, entity_type) then
		vim.notify("Invalid entity type: " .. entity_type, vim.log.levels.ERROR)
		vim.notify("Valid types: " .. table.concat(valid_types, ", "), vim.log.levels.INFO)
		return
	end

	local root = get_project_root()
	local cmd = string.format("cd %s && plm export-wiki %s", root, entity_type)

	execute_command(cmd, { show_output = true })
end

-- Validate wiki cross-references
function M.validate(mode)
	mode = mode or "check"

	local valid_modes = { "check", "orphans", "stats" }

	if not vim.tbl_contains(valid_modes, mode) then
		vim.notify("Invalid validation mode: " .. mode, vim.log.levels.ERROR)
		vim.notify("Valid modes: " .. table.concat(valid_modes, ", "), vim.log.levels.INFO)
		return
	end

	local root = get_project_root()
	local cmd = string.format("cd %s && python -m dev.pipeline.validate_wiki %s", root, mode)

	execute_command(cmd, { show_output = true })
end

-- Open statistics dashboard
function M.stats()
	local root = get_project_root()
	local stats_path = root .. "/data/wiki/stats.md"

	-- Check if stats file exists
	if vim.fn.filereadable(stats_path) == 0 then
		-- Generate it first
		vim.notify("Statistics dashboard not found, generating...", vim.log.levels.INFO)
		M.export("stats")

		-- Wait a moment for generation
		vim.wait(1000)
	end

	-- Open stats file
	if vim.fn.filereadable(stats_path) == 1 then
		vim.cmd("edit " .. stats_path)
	else
		vim.notify("Failed to generate statistics dashboard", vim.log.levels.ERROR)
	end
end

-- Open wiki index
function M.index()
	local root = get_project_root()
	local index_path = root .. "/data/wiki/index.md"

	-- Check if index exists
	if vim.fn.filereadable(index_path) == 0 then
		-- Generate it first
		vim.notify("Wiki index not found, generating...", vim.log.levels.INFO)
		M.export("index")

		-- Wait a moment for generation
		vim.wait(1000)
	end

	-- Open index file
	if vim.fn.filereadable(index_path) == 1 then
		vim.cmd("edit " .. index_path)
	else
		vim.notify("Failed to generate wiki index", vim.log.levels.ERROR)
	end
end

-- Open analysis report
function M.analysis()
	local root = get_project_root()
	local analysis_path = root .. "/data/wiki/analysis.md"

	-- Check if analysis report exists
	if vim.fn.filereadable(analysis_path) == 0 then
		-- Generate it first
		vim.notify("Analysis report not found, generating...", vim.log.levels.INFO)
		M.export("analysis")

		-- Wait a moment for generation
		vim.wait(1000)
	end

	-- Open analysis file
	if vim.fn.filereadable(analysis_path) == 1 then
		vim.cmd("edit " .. analysis_path)
	else
		vim.notify("Failed to generate analysis report", vim.log.levels.ERROR)
	end
end

-- Export manuscript entities to wiki
function M.manuscript_export(entity_type)
	entity_type = entity_type or "manuscript"

	local valid_types = {
		"manuscript",
		"manuscript-entries",
		"manuscript-characters",
		"manuscript-arcs",
		"manuscript-events",
	}

	-- Validate entity type
	if not vim.tbl_contains(valid_types, entity_type) then
		vim.notify("Invalid manuscript entity type: " .. entity_type, vim.log.levels.ERROR)
		vim.notify("Valid types: " .. table.concat(valid_types, ", "), vim.log.levels.INFO)
		return
	end

	local root = get_project_root()
	local cmd = string.format("cd %s && plm export-wiki %s", root, entity_type)

	execute_command(cmd, { show_output = true })
end

-- Import manuscript wiki edits to database
function M.manuscript_import(entity_type)
	entity_type = entity_type or "manuscript-all"

	local valid_types = {
		"manuscript-all",
		"manuscript-entries",
		"manuscript-characters",
		"manuscript-events",
	}

	-- Validate entity type
	if not vim.tbl_contains(valid_types, entity_type) then
		vim.notify("Invalid import entity type: " .. entity_type, vim.log.levels.ERROR)
		vim.notify("Valid types: " .. table.concat(valid_types, ", "), vim.log.levels.INFO)
		return
	end

	local root = get_project_root()
	local cmd = string.format("cd %s && plm import-wiki %s", root, entity_type)

	execute_command(cmd, { show_output = true })
end

-- Open manuscript index
function M.manuscript_index()
	local root = get_project_root()
	local index_path = root .. "/data/wiki/manuscript/index.md"

	-- Check if index exists
	if vim.fn.filereadable(index_path) == 0 then
		-- Generate it first
		vim.notify("Manuscript index not found, generating...", vim.log.levels.INFO)
		M.manuscript_export("all")

		-- Wait a moment for generation
		vim.wait(1000)
	end

	-- Open index file
	if vim.fn.filereadable(index_path) == 1 then
		vim.cmd("edit " .. index_path)
	else
		vim.notify("Failed to generate manuscript index", vim.log.levels.ERROR)
	end
end

-- Wiki sync: run plm wiki sync asynchronously
function M.wiki_sync(opts)
	opts = opts or {}
	local root = get_project_root()
	local cmd = "cd " .. root .. " && plm wiki sync"

	if opts.ingest then
		cmd = cmd .. " --ingest"
	elseif opts.generate then
		cmd = cmd .. " --generate"
	end

	vim.notify("Running wiki sync...", vim.log.levels.INFO)
	vim.fn.jobstart(cmd, {
		on_exit = function(_, exit_code)
			vim.schedule(function()
				if exit_code == 0 then
					vim.notify("Wiki sync completed", vim.log.levels.INFO)
				else
					vim.notify("Wiki sync failed (exit " .. exit_code .. ")", vim.log.levels.ERROR)
				end
			end)
		end,
	})
end

-- Wiki lint: run plm wiki lint asynchronously
function M.wiki_lint(opts)
	opts = opts or {}
	local root = get_project_root()
	local cmd = "cd " .. root .. " && plm wiki lint --format json"

	vim.fn.jobstart(cmd, {
		stdout_buffered = true,
		on_stdout = function(_, data)
			if data then
				vim.schedule(function()
					local json_str = table.concat(data, "")
					if json_str ~= "" then
						local ok, diagnostics = pcall(vim.fn.json_decode, json_str)
						if ok and type(diagnostics) == "table" then
							vim.notify(
								string.format("Lint: %d diagnostics", #diagnostics),
								#diagnostics > 0 and vim.log.levels.WARN or vim.log.levels.INFO
							)
						end
					end
				end)
			end
		end,
		on_exit = function(_, exit_code)
			vim.schedule(function()
				if exit_code ~= 0 then
					vim.notify("Wiki lint failed", vim.log.levels.ERROR)
				end
			end)
		end,
	})
end

-- Wiki generate: run plm wiki generate asynchronously
function M.wiki_generate(opts)
	opts = opts or {}
	local root = get_project_root()
	local cmd = "cd " .. root .. " && plm wiki generate"

	if opts.section then
		cmd = cmd .. " --section " .. opts.section
	end
	if opts.entity_type then
		cmd = cmd .. " --type " .. opts.entity_type
	end

	vim.notify("Generating wiki pages...", vim.log.levels.INFO)
	vim.fn.jobstart(cmd, {
		on_exit = function(_, exit_code)
			vim.schedule(function()
				if exit_code == 0 then
					vim.notify("Wiki generation completed", vim.log.levels.INFO)
				else
					vim.notify("Wiki generation failed", vim.log.levels.ERROR)
				end
			end)
		end,
	})
end

-- Metadata export: run plm metadata export asynchronously
function M.metadata_export(entity_type)
	local root = get_project_root()
	local cmd = "cd " .. root .. " && plm metadata export"

	if entity_type and entity_type ~= "" then
		cmd = cmd .. " --type " .. entity_type
	end

	vim.notify("Exporting metadata YAML...", vim.log.levels.INFO)
	vim.fn.jobstart(cmd, {
		on_exit = function(_, exit_code)
			vim.schedule(function()
				if exit_code == 0 then
					vim.notify("Metadata export completed", vim.log.levels.INFO)
				else
					vim.notify("Metadata export failed", vim.log.levels.ERROR)
				end
			end)
		end,
	})
end

-- Setup user commands
function M.setup()
	-- Export command with completion
	vim.api.nvim_create_user_command("PalimpsestExport", function(opts)
		M.export(opts.args)
	end, {
		nargs = "?",
		desc = "Export entities from database to wiki",
		complete = function()
			return {
				"all",
				"index",
				"stats",
				"analysis",
				"timeline",
				"entries",
				"people",
				"locations",
				"cities",
				"events",
				"themes",
				"tags",
				"poems",
				"references",
				"manuscript",
				"manuscript-entries",
				"manuscript-characters",
				"manuscript-arcs",
				"manuscript-events",
			}
		end,
	})

	-- Validate command with completion
	vim.api.nvim_create_user_command("PalimpsestValidate", function(opts)
		M.validate(opts.args)
	end, {
		nargs = "?",
		desc = "Validate wiki cross-references",
		complete = function()
			return { "check", "orphans", "stats" }
		end,
	})

	-- Stats command
	vim.api.nvim_create_user_command("PalimpsestStats", function()
		M.stats()
	end, {
		desc = "Open statistics dashboard",
	})

	-- Index command
	vim.api.nvim_create_user_command("PalimpsestIndex", function()
		M.index()
	end, {
		desc = "Open wiki index/homepage",
	})

	-- Analysis command
	vim.api.nvim_create_user_command("PalimpsestAnalysis", function()
		M.analysis()
	end, {
		desc = "Open analysis report with visualizations",
	})

	-- Manuscript export command with completion
	vim.api.nvim_create_user_command("PalimpsestManuscriptExport", function(opts)
		M.manuscript_export(opts.args)
	end, {
		nargs = "?",
		desc = "Export manuscript entities to wiki",
		complete = function()
			return {
				"manuscript",
				"manuscript-entries",
				"manuscript-characters",
				"manuscript-arcs",
				"manuscript-events",
			}
		end,
	})

	-- Manuscript import command with completion
	vim.api.nvim_create_user_command("PalimpsestManuscriptImport", function(opts)
		M.manuscript_import(opts.args)
	end, {
		nargs = "?",
		desc = "Import manuscript wiki edits to database",
		complete = function()
			return {
				"manuscript-all",
				"manuscript-entries",
				"manuscript-characters",
				"manuscript-events",
			}
		end,
	})

	-- Manuscript index command
	vim.api.nvim_create_user_command("PalimpsestManuscriptIndex", function()
		M.manuscript_index()
	end, {
		desc = "Open manuscript wiki index/homepage",
	})

	-- fzf-lua browse commands
	vim.api.nvim_create_user_command("PalimpsestBrowse", function(opts)
		local entity_type = opts.args ~= "" and opts.args or "all"
		require("palimpsest.fzf").browse(entity_type)
	end, {
		nargs = "?",
		desc = "Browse wiki entities with fzf-lua",
		complete = function()
			return {
				"all",
				"journal",
				"people",
				"entries",
				"locations",
				"cities",
				"events",
				"themes",
				"tags",
				"poems",
				"references",
				"manuscript",
				"manuscript-entries",
				"manuscript-characters",
				"manuscript-arcs",
				"manuscript-events",
			}
		end,
	})

	-- fzf-lua search command
	vim.api.nvim_create_user_command("PalimpsestSearch", function(opts)
		local entity_type = opts.args ~= "" and opts.args or "wiki"
		require("palimpsest.fzf").search(entity_type)
	end, {
		nargs = "?",
		desc = "Search wiki content with fzf-lua",
		complete = function()
			return {
				"wiki",
				"journal",
				"people",
				"entries",
				"locations",
				"cities",
				"events",
				"themes",
				"tags",
				"poems",
				"references",
				"manuscript",
				"manuscript-entries",
				"manuscript-characters",
				"manuscript-arcs",
				"manuscript-events",
			}
		end,
	})

	-- fzf-lua quick access command
	vim.api.nvim_create_user_command("PalimpsestQuickAccess", function()
		require("palimpsest.fzf").quick_access()
	end, {
		desc = "Quick access to wiki index pages",
	})

	-- Wiki sync command
	vim.api.nvim_create_user_command("PalimpsestSync", function(opts)
		local args = {}
		if opts.args == "ingest" then
			args.ingest = true
		elseif opts.args == "generate" then
			args.generate = true
		end
		M.wiki_sync(args)
	end, {
		nargs = "?",
		desc = "Sync wiki pages with database",
		complete = function()
			return { "ingest", "generate" }
		end,
	})

	-- Wiki lint command
	vim.api.nvim_create_user_command("PalimpsestLint", function()
		M.wiki_lint()
	end, {
		desc = "Lint wiki pages for errors",
	})

	-- Wiki generate command
	vim.api.nvim_create_user_command("PalimpsestGenerate", function(opts)
		local args = {}
		local parts = vim.split(opts.args or "", "%s+")
		for _, part in ipairs(parts) do
			if part ~= "" then
				if vim.tbl_contains({ "journal", "manuscript", "indexes" }, part) then
					args.section = part
				else
					args.entity_type = part
				end
			end
		end
		M.wiki_generate(args)
	end, {
		nargs = "?",
		desc = "Generate wiki pages from database",
		complete = function()
			return { "journal", "manuscript", "indexes" }
		end,
	})

	-- Entity edit command (opens YAML in floating window)
	vim.api.nvim_create_user_command("PalimpsestEdit", function()
		require("palimpsest.entity").edit()
	end, {
		desc = "Edit current entity metadata in floating window",
	})

	-- Entity new command
	vim.api.nvim_create_user_command("PalimpsestNew", function(opts)
		local entity_type = opts.args ~= "" and opts.args or nil
		require("palimpsest.entity").new(entity_type)
	end, {
		nargs = "?",
		desc = "Create new entity metadata",
		complete = function()
			return { "people", "chapters", "characters", "scenes" }
		end,
	})

	-- Add source to manuscript scene
	vim.api.nvim_create_user_command("PalimpsestAddSource", function()
		require("palimpsest.entity").add_source()
	end, {
		desc = "Add source entry to manuscript scene",
	})

	-- Add based_on person mapping to character
	vim.api.nvim_create_user_command("PalimpsestAddBasedOn", function()
		require("palimpsest.entity").add_based_on()
	end, {
		desc = "Add based_on person mapping to character",
	})

	-- Link journal entry to manuscript
	vim.api.nvim_create_user_command("PalimpsestLinkToManuscript", function()
		require("palimpsest.entity").link_to_manuscript()
	end, {
		desc = "Link current entry to manuscript scene or chapter",
	})

	-- Metadata export command
	vim.api.nvim_create_user_command("PalimpsestMetadataExport", function(opts)
		M.metadata_export(opts.args)
	end, {
		nargs = "?",
		desc = "Export entity metadata to YAML files",
		complete = function()
			return { "people", "locations", "cities", "arcs", "chapters", "characters", "scenes" }
		end,
	})

	-- Cache refresh command
	vim.api.nvim_create_user_command("PalimpsestCacheRefresh", function()
		require("palimpsest.cache").refresh_all()
		vim.notify("Entity cache refreshing...", vim.log.levels.INFO)
	end, {
		desc = "Refresh entity name cache",
	})
end

return M
