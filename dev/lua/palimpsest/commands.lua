-- Palimpsest commands for wiki operations, entity editing, and navigation
local M = {}

local get_project_root = require("palimpsest.utils").get_project_root

-- Helper: open a wiki file, generating first if it doesn't exist
local function open_wiki_file(file_path, generate_opts)
	if vim.fn.filereadable(file_path) == 1 then
		vim.cmd("edit " .. file_path)
		return
	end

	-- Generate first, then open in the on_exit callback
	vim.notify("File not found, generating...", vim.log.levels.INFO)
	local root = get_project_root()
	local cmd = "cd " .. root .. " && plm wiki generate"

	if generate_opts and generate_opts.section then
		cmd = cmd .. " --section " .. generate_opts.section
	end

	vim.fn.jobstart(cmd, {
		on_exit = function(_, exit_code)
			vim.schedule(function()
				if exit_code == 0 and vim.fn.filereadable(file_path) == 1 then
					vim.cmd("edit " .. file_path)
				else
					vim.notify("Failed to generate: " .. file_path, vim.log.levels.ERROR)
				end
			end)
		end,
	})
end

-- Open wiki index
function M.index()
	local root = get_project_root()
	open_wiki_file(root .. "/data/wiki/index.md")
end

-- Open manuscript index
function M.manuscript_index()
	local root = get_project_root()
	open_wiki_file(root .. "/data/wiki/indexes/manuscript-index.md")
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
	local wiki_dir = root .. "/data/wiki"
	local cmd = "cd " .. root .. " && plm wiki lint " .. wiki_dir .. " --format json"

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

-- Wiki publish: run plm wiki publish asynchronously
function M.wiki_publish(opts)
	opts = opts or {}
	local root = get_project_root()
	local cmd = "cd " .. root .. " && plm wiki publish"

	if opts.output_dir then
		cmd = cmd .. " --output-dir " .. opts.output_dir
	end

	vim.notify("Publishing to Quartz...", vim.log.levels.INFO)
	vim.fn.jobstart(cmd, {
		on_exit = function(_, exit_code)
			vim.schedule(function()
				if exit_code == 0 then
					vim.notify("Wiki publish completed", vim.log.levels.INFO)
				else
					vim.notify("Wiki publish failed", vim.log.levels.ERROR)
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

-- Validate entry: run plm validate entry with quickfix output
function M.validate_entry(entry_date)
	local root = get_project_root()

	-- Auto-detect date from current buffer filename if not provided
	if not entry_date or entry_date == "" then
		local filename = vim.fn.expand("%:t:r")
		if filename:match("^%d%d%d%d%-%d%d%-%d%d$") then
			entry_date = filename
		else
			vim.notify("Cannot detect entry date from current file", vim.log.levels.WARN)
			return
		end
	end

	local cmd = string.format(
		"cd %s && plm validate entry %s --quickfix 2>&1",
		root, entry_date
	)

	local output_lines = {}
	vim.fn.jobstart(cmd, {
		stdout_buffered = true,
		on_stdout = function(_, data)
			if data then
				for _, line in ipairs(data) do
					if line ~= "" then
						table.insert(output_lines, line)
					end
				end
			end
		end,
		on_exit = function(_, exit_code)
			vim.schedule(function()
				if exit_code == 0 and #output_lines == 0 then
					vim.notify("Entry validation passed", vim.log.levels.INFO)
				else
					-- Parse quickfix-format output
					local qf_items = {}
					for _, line in ipairs(output_lines) do
						local file, lnum, col, msg = line:match("^(.+):(%d+):(%d+): (.+)$")
						if file then
							table.insert(qf_items, {
								filename = file,
								lnum = tonumber(lnum),
								col = tonumber(col),
								text = msg,
							})
						end
					end
					if #qf_items > 0 then
						vim.fn.setqflist(qf_items, "r")
						vim.cmd("copen")
						vim.notify(
							string.format("Entry validation: %d issues", #qf_items),
							vim.log.levels.WARN
						)
					elseif #output_lines > 0 then
						vim.notify(table.concat(output_lines, "\n"), vim.log.levels.WARN)
					end
				end
			end)
		end,
	})
end

-- Deck mode: navigation-only commands (no Python dependency)
function M.setup_deck()
	-- Navigation commands (open pre-generated wiki files)
	vim.api.nvim_create_user_command("PalimpsestIndex", function()
		M.index()
	end, {
		desc = "Open wiki index/homepage",
	})

	vim.api.nvim_create_user_command("PalimpsestManuscriptIndex", function()
		M.manuscript_index()
	end, {
		desc = "Open manuscript wiki index/homepage",
	})

	-- fzf-lua commands (optional — gracefully handled if missing)
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
				"motifs",
				"manuscript",
				"manuscript-chapters",
				"manuscript-characters",
				"manuscript-scenes",
			}
		end,
	})

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
				"motifs",
				"manuscript",
				"manuscript-chapters",
				"manuscript-characters",
				"manuscript-scenes",
			}
		end,
	})

	vim.api.nvim_create_user_command("PalimpsestQuickAccess", function()
		require("palimpsest.fzf").quick_access()
	end, {
		desc = "Quick access to wiki index pages",
	})
end

-- Full setup: all commands including Python-dependent operations
function M.setup()
	-- Index command
	vim.api.nvim_create_user_command("PalimpsestIndex", function()
		M.index()
	end, {
		desc = "Open wiki index/homepage",
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
				"motifs",
				"manuscript",
				"manuscript-chapters",
				"manuscript-characters",
				"manuscript-scenes",
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
				"motifs",
				"manuscript",
				"manuscript-chapters",
				"manuscript-characters",
				"manuscript-scenes",
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

	-- Wiki publish command
	vim.api.nvim_create_user_command("PalimpsestPublish", function()
		M.wiki_publish()
	end, {
		desc = "Publish wiki to Quartz",
	})

	-- Entity edit command (opens YAML in floating window)
	vim.api.nvim_create_user_command("PalimpsestEdit", function()
		require("palimpsest.entity").edit()
	end, {
		desc = "Edit current entity metadata in floating window",
	})

	-- Curation file edit command (opens neighborhoods/relation_types YAML)
	vim.api.nvim_create_user_command("PalimpsestEditCuration", function()
		require("palimpsest.entity").edit_curation()
	end, {
		desc = "Edit curation file for current entity type",
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
			return {
				"people", "locations", "cities", "arcs",
				"chapters", "characters", "scenes",
				"neighborhoods", "relation_types",
			}
		end,
	})

	-- Cache refresh command
	vim.api.nvim_create_user_command("PalimpsestCacheRefresh", function()
		require("palimpsest.cache").refresh_all()
		vim.notify("Entity cache refreshing...", vim.log.levels.INFO)
	end, {
		desc = "Refresh entity name cache",
	})

	-- Validate entry command (quickfix integration)
	vim.api.nvim_create_user_command("PalimpsestValidateEntry", function(opts)
		M.validate_entry(opts.args)
	end, {
		nargs = "?",
		desc = "Validate journal entry (MD + YAML) with quickfix",
		complete = function()
			return {}
		end,
	})
end

return M
