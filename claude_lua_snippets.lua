-- ~/.config/nvim/lua/journal/init.lua
-- Journal Archive Plugin for Neovim

local M = {}

-- Configuration
M.config = {
	python_script = vim.fn.stdpath("config") .. "/scripts/journal_db.py",
	journal_directory = "~/journal",
	auto_sync = true,
}

-- Setup function
function M.setup(opts)
	opts = opts or {}
	M.config = vim.tbl_extend("force", M.config, opts)

	-- Create user commands
	vim.api.nvim_create_user_command("JournalEditMeta", M.edit_metadata, {})
	vim.api.nvim_create_user_command("JournalSync", M.sync_directory, {})
	vim.api.nvim_create_user_command("JournalNewEntry", M.new_entry, {})

	-- Auto-sync on save for markdown files
	if M.config.auto_sync then
		vim.api.nvim_create_autocmd("BufWritePost", {
			pattern = "*.md",
			callback = function()
				local file_path = vim.fn.expand("%:p")
				M.sync_file(file_path)
			end,
		})
	end

	-- Set up key mappings
	vim.keymap.set("n", "<leader>je", M.edit_metadata, { desc = "Edit journal metadata" })
	vim.keymap.set("n", "<leader>js", M.sync_directory, { desc = "Sync journal directory" })
	vim.keymap.set("n", "<leader>jn", M.new_entry, { desc = "New journal entry" })
end

-- Call Python API
function M.call_python_api(action, params)
	params = params or {}
	params.action = action

	local cmd = string.format("python3 %s %s", M.config.python_script, action)
	for key, value in pairs(params) do
		if key ~= "action" then
			cmd = cmd .. string.format(" %s=%s", key, vim.fn.shellescape(tostring(value)))
		end
	end

	local result = vim.fn.system(cmd)
	local success, json_result = pcall(vim.fn.json_decode, result)

	if not success then
		vim.notify("Error calling Python API: " .. result, vim.log.levels.ERROR)
		return nil
	end

	if json_result.error then
		vim.notify("API Error: " .. json_result.error, vim.log.levels.ERROR)
		return nil
	end

	return json_result
end

-- Get metadata for current file
function M.get_current_metadata()
	local file_path = vim.fn.expand("%:p")
	if not file_path or file_path == "" then
		vim.notify("No file open", vim.log.levels.WARN)
		return nil
	end

	local result = M.call_python_api("get_metadata", { file_path = file_path })
	return result and result.metadata or nil
end

-- Update metadata for current file
function M.update_current_metadata(metadata)
	local file_path = vim.fn.expand("%:p")
	if not file_path or file_path == "" then
		vim.notify("No file open", vim.log.levels.WARN)
		return false
	end

	local result = M.call_python_api("update_metadata", {
		file_path = file_path,
		metadata = vim.fn.json_encode(metadata),
	})

	return result and result.success or false
end

-- Get autocomplete values for a field
function M.get_autocomplete(field)
	local result = M.call_python_api("get_autocomplete", { field = field })
	return result and result.values or {}
end

-- Sync current file
function M.sync_file(file_path)
	file_path = file_path or vim.fn.expand("%:p")
	M.call_python_api("sync_file", { file_path = file_path })
end

-- Sync entire directory
function M.sync_directory()
	local result = M.call_python_api("sync_directory", {
		directory = vim.fn.expand(M.config.journal_directory),
	})
	if result and result.success then
		vim.notify("Journal directory synced", vim.log.levels.INFO)
	end
end

-- Create metadata editing interface
function M.edit_metadata()
	local metadata = M.get_current_metadata()
	if not metadata then
		return
	end

	-- Create floating window for metadata editing
	local buf = vim.api.nvim_create_buf(false, true)
	local width = 80
	local height = 25
	local row = (vim.o.lines - height) / 2
	local col = (vim.o.columns - width) / 2

	local win = vim.api.nvim_open_win(buf, true, {
		relative = "editor",
		width = width,
		height = height,
		row = row,
		col = col,
		border = "rounded",
		title = " Edit Journal Metadata ",
		title_pos = "center",
	})

	-- Populate buffer with current metadata
	local lines = M.format_metadata_for_editing(metadata)
	vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)

	-- Set buffer options
	vim.api.nvim_buf_set_option(buf, "buftype", "nofile")
	vim.api.nvim_buf_set_option(buf, "filetype", "yaml")

	-- Key mappings for the metadata buffer
	local function close_and_save()
		local updated_lines = vim.api.nvim_buf_get_lines(buf, 0, -1, false)
		local updated_metadata = M.parse_metadata_from_editing(updated_lines)

		if M.update_current_metadata(updated_metadata) then
			vim.notify("Metadata updated successfully", vim.log.levels.INFO)
			vim.cmd("e!") -- Reload current buffer to show changes
		else
			vim.notify("Failed to update metadata", vim.log.levels.ERROR)
		end

		vim.api.nvim_win_close(win, true)
	end

	local function close_without_saving()
		vim.api.nvim_win_close(win, true)
	end

	-- Set up key mappings
	vim.keymap.set("n", "<CR>", close_and_save, { buffer = buf, desc = "Save and close" })
	vim.keymap.set("n", "<Esc>", close_without_saving, { buffer = buf, desc = "Close without saving" })
	vim.keymap.set("n", "q", close_without_saving, { buffer = buf, desc = "Close without saving" })

	-- Enable completion for certain fields
	M.setup_metadata_completion(buf)
end

-- Format metadata for editing in the floating window
function M.format_metadata_for_editing(metadata)
	local lines = {
		"date: " .. (metadata.date or ""),
		"word_count: " .. (metadata.word_count or 0),
		"reading_time: " .. (metadata.reading_time or 0.0),
		"status: " .. (metadata.status or "unreviewed"),
		"excerpted: " .. (metadata.excerpted and "true" or "false"),
		"epigraph: " .. (metadata.epigraph or ""),
		"",
		"# People (one per line):",
	}

	for _, person in ipairs(metadata.people or {}) do
		table.insert(lines, "- " .. person)
	end

	table.insert(lines, "")
	table.insert(lines, "# Themes (one per line):")
	for _, theme in ipairs(metadata.themes or {}) do
		table.insert(lines, "- " .. theme)
	end

	table.insert(lines, "")
	table.insert(lines, "# Tags (one per line):")
	for _, tag in ipairs(metadata.tags or {}) do
		table.insert(lines, "- " .. tag)
	end

	table.insert(lines, "")
	table.insert(lines, "# Locations (one per line):")
	for _, location in ipairs(metadata.location or {}) do
		table.insert(lines, "- " .. location)
	end

	table.insert(lines, "")
	table.insert(lines, "# Events (one per line):")
	for _, event in ipairs(metadata.events or {}) do
		table.insert(lines, "- " .. event)
	end

	table.insert(lines, "")
	table.insert(lines, "# References (one per line):")
	for _, ref in ipairs(metadata.references or {}) do
		table.insert(lines, "- " .. ref)
	end

	table.insert(lines, "")
	table.insert(lines, "# Notes:")
	table.insert(lines, metadata.notes or "")

	return lines
end

-- Parse metadata from editing buffer
function M.parse_metadata_from_editing(lines)
	local metadata = {}
	local current_section = nil
	local notes_started = false
	local notes_lines = {}

	for _, line in ipairs(lines) do
		if notes_started then
			table.insert(notes_lines, line)
		elseif line:match("^date:") then
			metadata.date = line:gsub("^date:%s*", "")
		elseif line:match("^word_count:") then
			metadata.word_count = tonumber(line:gsub("^word_count:%s*", "")) or 0
		elseif line:match("^reading_time:") then
			metadata.reading_time = tonumber(line:gsub("^reading_time:%s*", "")) or 0.0
		elseif line:match("^status:") then
			metadata.status = line:gsub("^status:%s*", "")
		elseif line:match("^excerpted:") then
			local value = line:gsub("^excerpted:%s*", ""):lower()
			metadata.excerpted = value == "true"
		elseif line:match("^epigraph:") then
			metadata.epigraph = line:gsub("^epigraph:%s*", "")
		elseif line:match("^# People") then
			current_section = "people"
			metadata.people = {}
		elseif line:match("^# Themes") then
			current_section = "themes"
			metadata.themes = {}
		elseif line:match("^# Tags") then
			current_section = "tags"
			metadata.tags = {}
		elseif line:match("^# Locations") then
			current_section = "location"
			metadata.location = {}
		elseif line:match("^# Events") then
			current_section = "events"
			metadata.events = {}
		elseif line:match("^# References") then
			current_section = "references"
			metadata.references = {}
		elseif line:match("^# Notes") then
			notes_started = true
		elseif line:match("^%- ") and current_section then
			local item = line:gsub("^%- ", "")
			if item ~= "" then
				table.insert(metadata[current_section], item)
			end
		end
	end

	if #notes_lines > 0 then
		metadata.notes = table.concat(notes_lines, "\n"):gsub("^%s+", ""):gsub("%s+$", "")
	end

	return metadata
end

-- Setup completion for metadata fields
function M.setup_metadata_completion(buf)
	-- Custom completion function
	local function complete_metadata(findstart, base)
		if findstart == 1 then
			local line = vim.api.nvim_get_current_line()
			local col = vim.api.nvim_win_get_cursor(0)[2]
			local start = string.find(string.sub(line, 1, col), "%S*$")
			return start and (start - 1) or col
		else
			local line = vim.api.nvim_get_current_line()
			local completions = {}

			-- Determine what kind of completion we need
			local field_type = nil
			if line:match("^%- ") then
				-- We're in a list item, figure out which section
				local buf_lines = vim.api.nvim_buf_get_lines(buf, 0, -1, false)
				local current_line_num = vim.api.nvim_win_get_cursor(0)[1]

				for i = current_line_num - 1, 1, -1 do
					local prev_line = buf_lines[i]
					if prev_line:match("^# People") then
						field_type = "people"
						break
					elseif prev_line:match("^# Themes") then
						field_type = "themes"
						break
					elseif prev_line:match("^# Tags") then
						field_type = "tags"
						break
					elseif prev_line:match("^# Locations") then
						field_type = "locations"
						break
					elseif prev_line:match("^# Events") then
						field_type = "events"
						break
					end
				end
			elseif line:match("^status:") then
				completions = { "unreviewed", "reviewed", "published", "archived" }
			end

			if field_type then
				local values = M.get_autocomplete(field_type)
				for _, value in ipairs(values) do
					if value:lower():find(base:lower(), 1, true) then
						table.insert(completions, value)
					end
				end
			end

			return completions
		end
	end

	vim.api.nvim_buf_set_option(buf, "completefunc", 'v:lua.require("journal").complete_metadata')
	_G.journal_complete_metadata = complete_metadata
end

-- Create new journal entry
function M.new_entry()
	local date = vim.fn.input("Date (YYYY-MM-DD, default today): ")
	if date == "" then
		date = os.date("%Y-%m-%d")
	end

	local title = vim.fn.input("Entry title (optional): ")
	local filename = date .. (title ~= "" and ("_" .. title:gsub("%s+", "_"):lower()) or "") .. ".md"
	local filepath = vim.fn.expand(M.config.journal_directory) .. "/" .. filename

	-- Create initial metadata
	local metadata = {
		date = date,
		word_count = 0,
		reading_time = 0.0,
		status = "unreviewed",
		excerpted = false,
		epigraph = "",
		people = {},
		references = {},
		themes = {},
		tags = {},
		location = {},
		events = {},
		notes = "",
	}

	-- Create file with metadata
	local yaml_content = vim.fn.system(
		'python3 -c "import yaml; print(yaml.dump(' .. vim.fn.string(metadata) .. ', default_flow_style=False))"'
	)
	local content = "---\n" .. yaml_content .. "---\n\n# " .. (title ~= "" and title or date) .. "\n\n"

	vim.fn.writefile(vim.split(content, "\n"), filepath)
	vim.cmd("edit " .. filepath)

	-- Sync to database
	M.sync_file(filepath)

	vim.notify("New journal entry created: " .. filename, vim.log.levels.INFO)
end

-- Expose completion function globally
M.complete_metadata = _G.journal_complete_metadata

return M
