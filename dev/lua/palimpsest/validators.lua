-- Validator integration for Palimpsest
-- Runs Python validators and displays results as Neovim diagnostics
local palimpsest = require("palimpsest.config")
local M = {}

-- Namespace for diagnostics
local ns = vim.api.nvim_create_namespace("palimpsest_validators")

-- Get project root
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

-- Parse validator output and convert to diagnostics
local function parse_validation_output(output, bufnr)
	local diagnostics = {}

	-- The Python validator outputs in a structured format
	-- We need to parse it and create diagnostic entries
	-- Expected format: file:line:severity:category:message

	for line in output:gmatch("[^\r\n]+") do
		-- Look for error/warning indicators
		local severity, category, line_num, message

		-- Try to match various output patterns
		-- Pattern 1: "❌ [category]:line message" or "⚠️  [category]:line message"
		severity, category, line_num, message = line:match("([❌⚠️]+)%s*%[([^%]]+)%]:(%d+)%s+(.+)")

		if severity then
			local diag_severity = vim.diagnostic.severity.ERROR
			if severity:find("⚠") then
				diag_severity = vim.diagnostic.severity.WARN
			end

			local lnum = tonumber(line_num) or 1
			table.insert(diagnostics, {
				bufnr = bufnr,
				lnum = lnum - 1, -- 0-indexed
				col = 0,
				severity = diag_severity,
				source = "palimpsest",
				message = string.format("[%s] %s", category, message),
			})
		end

		-- Pattern 2: Look for suggestion lines "💡 suggestion"
		local suggestion = line:match("💡%s+(.+)")
		if suggestion and #diagnostics > 0 then
			-- Append suggestion to last diagnostic
			diagnostics[#diagnostics].message = diagnostics[#diagnostics].message .. "\n💡 " .. suggestion
		end

		-- Pattern 3: Generic error/warning messages
		if not severity and (line:find("error", 1, true) or line:find("Error", 1, true)) then
			table.insert(diagnostics, {
				bufnr = bufnr,
				lnum = 0,
				col = 0,
				severity = vim.diagnostic.severity.ERROR,
				source = "palimpsest",
				message = line,
			})
		elseif not severity and (line:find("warning", 1, true) or line:find("Warning", 1, true)) then
			table.insert(diagnostics, {
				bufnr = bufnr,
				lnum = 0,
				col = 0,
				severity = vim.diagnostic.severity.WARN,
				source = "palimpsest",
				message = line,
			})
		end
	end

	return diagnostics
end

-- Run markdown frontmatter validation
function M.validate_frontmatter(bufnr)
	bufnr = bufnr or vim.api.nvim_get_current_buf()
	local filepath = vim.api.nvim_buf_get_name(bufnr)

	if filepath == "" then
		return
	end

	-- Clear existing diagnostics
	vim.diagnostic.reset(ns, bufnr)

	local root = get_project_root()
	local cmd = string.format("cd %s && validate md frontmatter %s 2>&1",
		vim.fn.shellescape(root),
		vim.fn.shellescape(filepath))

	-- Run asynchronously
	local diagnostics = {}
	vim.fn.jobstart(cmd, {
		stdout_buffered = true,
		stderr_buffered = true,
		on_stdout = function(_, data)
			if data then
				local output = table.concat(data, "\n")
				local parsed = parse_validation_output(output, bufnr)
				vim.list_extend(diagnostics, parsed)
			end
		end,
		on_stderr = function(_, data)
			if data and #data > 0 and data[1] ~= "" then
				local output = table.concat(data, "\n")
				local parsed = parse_validation_output(output, bufnr)
				vim.list_extend(diagnostics, parsed)
			end
		end,
		on_exit = function(_, exit_code)
			if exit_code == 0 then
				-- Validation passed - clear diagnostics and notify
				vim.diagnostic.reset(ns, bufnr)
				vim.notify("Frontmatter validation passed ✓", vim.log.levels.INFO)
			else
				-- Validation failed - set diagnostics
				if #diagnostics > 0 then
					vim.diagnostic.set(ns, bufnr, diagnostics, {})
				end
			end
		end,
	})
end

-- Run metadata validation
function M.validate_metadata(bufnr)
	bufnr = bufnr or vim.api.nvim_get_current_buf()
	local filepath = vim.api.nvim_buf_get_name(bufnr)

	if filepath == "" then
		return
	end

	-- Clear existing diagnostics
	vim.diagnostic.reset(ns, bufnr)

	local root = get_project_root()
	local cmd = string.format("cd %s && validate metadata all %s 2>&1",
		vim.fn.shellescape(root),
		vim.fn.shellescape(filepath))

	-- Run asynchronously
	local diagnostics = {}
	vim.fn.jobstart(cmd, {
		stdout_buffered = true,
		stderr_buffered = true,
		on_stdout = function(_, data)
			if data then
				local output = table.concat(data, "\n")
				local parsed = parse_validation_output(output, bufnr)
				vim.list_extend(diagnostics, parsed)
			end
		end,
		on_stderr = function(_, data)
			if data and #data > 0 and data[1] ~= "" then
				local output = table.concat(data, "\n")
				local parsed = parse_validation_output(output, bufnr)
				vim.list_extend(diagnostics, parsed)
			end
		end,
		on_exit = function(_, exit_code)
			if exit_code == 0 then
				-- Validation passed - clear diagnostics and notify
				vim.diagnostic.reset(ns, bufnr)
				vim.notify("Metadata validation passed ✓", vim.log.levels.INFO)
			else
				-- Validation failed - set diagnostics
				if #diagnostics > 0 then
					vim.diagnostic.set(ns, bufnr, diagnostics, {})
				end
			end
		end,
	})
end

-- Validate markdown links
function M.validate_links(bufnr)
	bufnr = bufnr or vim.api.nvim_get_current_buf()
	local filepath = vim.api.nvim_buf_get_name(bufnr)

	if filepath == "" then
		return
	end

	-- Clear existing diagnostics
	vim.diagnostic.reset(ns, bufnr)

	local root = get_project_root()
	local cmd = string.format("cd %s && validate md links 2>&1",
		vim.fn.shellescape(root))

	-- Run asynchronously
	local diagnostics = {}
	vim.fn.jobstart(cmd, {
		stdout_buffered = true,
		stderr_buffered = true,
		on_stdout = function(_, data)
			if data then
				local output = table.concat(data, "\n")
				local parsed = parse_validation_output(output, bufnr)
				vim.list_extend(diagnostics, parsed)
			end
		end,
		on_stderr = function(_, data)
			if data and #data > 0 and data[1] ~= "" then
				local output = table.concat(data, "\n")
				local parsed = parse_validation_output(output, bufnr)
				vim.list_extend(diagnostics, parsed)
			end
		end,
		on_exit = function(_, exit_code)
			if exit_code == 0 then
				-- Validation passed - clear diagnostics
				vim.diagnostic.reset(ns, bufnr)
			else
				-- Validation failed - set diagnostics
				if #diagnostics > 0 then
					vim.diagnostic.set(ns, bufnr, diagnostics, {})
				end
			end
		end,
	})
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
		desc = "Validate metadata fields",
	})

	vim.api.nvim_create_user_command("PalimpsestValidateLinks", function()
		M.validate_links()
	end, {
		desc = "Validate markdown links",
	})
end

return M
