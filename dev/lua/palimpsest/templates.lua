local palimpsest = require("palimpsest.config")
local M = {}

-- Read template and return its lines
local function read_template(template_name)
	local template_path = palimpsest.paths.templates .. "/" .. template_name .. ".template"
	local file = io.open(template_path, "r")

	if not file then
		vim.notify("Template not found: " .. template_path, vim.log.levels.ERROR)
		return {}
	end

	local content = file:read("*all")
	file:close()

	return vim.split(content, "\n")
end

-- Substitute variables
local function substitute_variables(lines, variables)
	local result = {}
	local missing_vars = {}

	for _, line in ipairs(lines) do
		local processed_line = line

		-- First pass: collect all variables in this line
		local vars_in_line = {}
		for var_name in line:gmatch("{{([^}]+)}}") do
			vars_in_line[var_name] = true
		end

		-- Second pass: replace variables and track missing ones
		for var_name in pairs(vars_in_line) do
			local pattern = "{{" .. var_name .. "}}"

			if variables[var_name] ~= nil then
				-- Variable found - substitute it
				processed_line = processed_line:gsub(pattern, tostring(variables[var_name]))
			else
				-- Variable missing - track it and leave placeholder
				missing_vars[var_name] = true
				-- Optionally: replace with highlighted placeholder
				-- processed_line = processed_line:gsub(pattern, '***MISSING:' .. var_name .. '***')
			end
		end

		table.insert(result, processed_line)
	end

	-- Warn about missing variables
	if next(missing_vars) then
		local missing_list = {}
		for var_name in pairs(missing_vars) do
			table.insert(missing_list, var_name)
		end
		table.sort(missing_list)

		local message = string.format("Template warning: Missing variables: %s", table.concat(missing_list, ", "))
		vim.notify(message, vim.log.levels.WARN)
	end

	return result
end

-- Main template insertion
function M.insert_template(template_name, variables, cursor_position)
	variables = variables or {}

	-- Add common variables
	-- TODO: Maybe current path?
	variables.date = variables.date or os.date("%Y-%m-%d")
	variables.time = variables.time or os.date("%H:%M")

	-- Read and process template
	local lines = read_template(template_name)
	if #lines == 0 then
		return
	end

	-- Cursor logic
	local target_cursor_pos = nil
	if not cursor_position then
		for i, line in ipairs(lines) do
			local cursor_col = line:find("{{cursor}}")
			if cursor_col then
				target_cursor_pos = { i, cursor_col - 1 }
				break
			end
		end
	end

	variables.cursor = ""

	local processed_lines = substitute_variables(lines, variables)

	-- Insert into buffer
	vim.api.nvim_buf_set_lines(0, 0, 0, false, processed_lines)

	-- Set cursor position if specified
	local final_cursor_pos = cursor_position or target_cursor_pos
	if final_cursor_pos then
		vim.api.nvim_win_set_cursor(0, final_cursor_pos)
	end
end

-- Specific template functions (for backend use only)
-- Log template for diary entries
function M.populate_log()
	M.insert_template("log", {})
end

return M
