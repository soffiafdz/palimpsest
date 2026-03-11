-- Validator integration for Palimpsest
-- Runs Python validators and displays results as Neovim diagnostics
local palimpsest = require("palimpsest.config")
local get_project_root = require("palimpsest.utils").get_project_root
local M = {}

-- Namespace for diagnostics
local ns = vim.api.nvim_create_namespace("palimpsest_validators")

-- Parse JSON diagnostics from plm CLI output
local function parse_json_diagnostics(json_str, bufnr)
	local ok, parsed = pcall(vim.fn.json_decode, json_str)
	if not ok or type(parsed) ~= "table" then
		return {}
	end

	local diagnostics = {}
	for _, diag in ipairs(parsed) do
		local severity = vim.diagnostic.severity.ERROR
		if diag.severity == "warning" then
			severity = vim.diagnostic.severity.WARN
		elseif diag.severity == "info" then
			severity = vim.diagnostic.severity.INFO
		end

		table.insert(diagnostics, {
			bufnr = bufnr,
			lnum = (diag.line or 1) - 1,
			col = (diag.col or 1) - 1,
			severity = severity,
			source = "palimpsest",
			message = diag.message or "Validation error",
		})
	end

	return diagnostics
end

-- Generic validator runner: shell command with --format json, parsed into diagnostics
local function run_validator(bufnr, cmd_suffix, success_msg)
	bufnr = bufnr or vim.api.nvim_get_current_buf()
	local filepath = vim.api.nvim_buf_get_name(bufnr)

	if filepath == "" then
		return
	end

	-- Clear existing diagnostics
	vim.diagnostic.reset(ns, bufnr)

	local root = get_project_root()
	local cmd = string.format("cd %s && %s 2>&1",
		vim.fn.shellescape(root), cmd_suffix)

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
				if exit_code == 0 then
					vim.diagnostic.reset(ns, bufnr)
					if success_msg then
						vim.notify(success_msg, vim.log.levels.INFO)
					end
					return
				end

				-- Parse JSON diagnostics
				local json_str = table.concat(output_lines, "")
				local diagnostics = parse_json_diagnostics(json_str, bufnr)
				if #diagnostics > 0 then
					vim.diagnostic.set(ns, bufnr, diagnostics, {})
				end
			end)
		end,
	})
end

-- Run markdown frontmatter validation
function M.validate_frontmatter(bufnr)
	bufnr = bufnr or vim.api.nvim_get_current_buf()
	local filepath = vim.api.nvim_buf_get_name(bufnr)

	run_validator(bufnr,
		string.format("plm validate md frontmatter %s --format json",
			vim.fn.shellescape(filepath)),
		"Frontmatter validation passed")
end

-- Run frontmatter structure validation (people, locations, dates, references, poems)
function M.validate_metadata(bufnr)
	run_validator(bufnr,
		"plm validate frontmatter all --format json",
		"Metadata validation passed")
end

-- Validate markdown links
function M.validate_links(bufnr)
	run_validator(bufnr,
		"plm validate md links --format json",
		nil)
end

-- Run wiki page lint validation
function M.validate_wiki_page(bufnr)
	bufnr = bufnr or vim.api.nvim_get_current_buf()
	local filepath = vim.api.nvim_buf_get_name(bufnr)

	run_validator(bufnr,
		string.format("plm wiki lint %s --format json",
			vim.fn.shellescape(filepath)),
		nil)
end

-- Setup function
function M.setup()
	-- User commands for manual validation
	vim.api.nvim_create_user_command("PalimpsestValidateFrontmatter", function()
		M.validate_frontmatter()
	end, {
		desc = "Validate markdown frontmatter",
	})

	vim.api.nvim_create_user_command("PalimpsestValidateMetadata", function()
		M.validate_metadata()
	end, {
		desc = "Validate all frontmatter structure",
	})

	vim.api.nvim_create_user_command("PalimpsestValidateLinks", function()
		M.validate_links()
	end, {
		desc = "Validate markdown links",
	})
end

return M
