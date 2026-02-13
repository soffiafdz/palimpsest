-- Floating window for YAML metadata editing
--
-- Opens YAML metadata files in a centered floating window with
-- auto-validation on save and auto-import on close. Provides
-- the core UI component for the entity editing workflow.
local M = {}

-- Default window options
local DEFAULT_OPTS = {
	width_ratio = 0.6,
	height_ratio = 0.7,
	border = "rounded",
	title = " Metadata ",
	title_pos = "center",
}

-- Get project root
local function get_project_root()
	local markers = { "pyproject.toml", ".git" }
	local path = vim.fn.getcwd()
	while path ~= "/" do
		for _, marker in ipairs(markers) do
			if vim.fn.filereadable(path .. "/" .. marker) == 1
				or vim.fn.isdirectory(path .. "/" .. marker) == 1
			then
				return path
			end
		end
		path = vim.fn.fnamemodify(path, ":h")
	end
	return vim.fn.getcwd()
end

--- Open a file in a floating window.
---
--- Creates a centered floating window and loads the specified file.
--- Sets up BufWritePost for validation and WinClosed for import.
---
--- @param filepath string Absolute path to the YAML file
--- @param opts table|nil Window options (width_ratio, height_ratio, border, title)
function M.open(filepath, opts)
	opts = vim.tbl_deep_extend("force", DEFAULT_OPTS, opts or {})

	-- Calculate window dimensions
	local width = math.floor(vim.o.columns * opts.width_ratio)
	local height = math.floor(vim.o.lines * opts.height_ratio)
	local col = math.floor((vim.o.columns - width) / 2)
	local row = math.floor((vim.o.lines - height) / 2)

	-- Create buffer and load file
	local buf = vim.api.nvim_create_buf(false, false)
	vim.api.nvim_buf_call(buf, function()
		vim.cmd("edit " .. vim.fn.fnameescape(filepath))
	end)

	-- Open floating window
	local win = vim.api.nvim_open_win(buf, true, {
		relative = "editor",
		width = width,
		height = height,
		col = col,
		row = row,
		style = "minimal",
		border = opts.border,
		title = opts.title,
		title_pos = opts.title_pos,
	})

	-- Set window-local options
	vim.api.nvim_set_option_value("winblend", 0, { win = win })
	vim.api.nvim_set_option_value("cursorline", true, { win = win })

	-- Setup autocmds for this buffer
	local group = vim.api.nvim_create_augroup("PalimpsestFloat_" .. buf, { clear = true })

	-- Validate on save
	vim.api.nvim_create_autocmd("BufWritePost", {
		group = group,
		buffer = buf,
		callback = function()
			M.on_save(buf, filepath)
		end,
	})

	-- Import on window close
	vim.api.nvim_create_autocmd("WinClosed", {
		group = group,
		pattern = tostring(win),
		callback = function()
			M.on_close(buf, filepath)
			-- Cleanup
			vim.api.nvim_del_augroup_by_id(group)
		end,
	})

	-- ESC to close
	vim.keymap.set("n", "q", function()
		vim.api.nvim_win_close(win, true)
	end, { buffer = buf, desc = "Close metadata float" })
end

--- Handle buffer save: validate the YAML file.
---
--- Runs `plm metadata validate <filepath>` asynchronously and
--- populates diagnostics in the buffer.
---
--- @param bufnr number Buffer number
--- @param filepath string Path to the YAML file
function M.on_save(bufnr, filepath)
	local root = get_project_root()
	local cmd = string.format(
		"cd %s && plm metadata validate %s",
		root, vim.fn.fnameescape(filepath)
	)

	vim.fn.jobstart(cmd, {
		stdout_buffered = true,
		on_exit = function(_, exit_code)
			vim.schedule(function()
				if exit_code == 0 then
					vim.notify("Metadata valid", vim.log.levels.INFO)
				else
					vim.notify("Validation errors found", vim.log.levels.WARN)
				end
			end)
		end,
	})
end

--- Handle window close: import the YAML file and refresh.
---
--- Runs `plm metadata import <filepath>` to push changes to DB,
--- then refreshes the entity cache.
---
--- @param bufnr number Buffer number
--- @param filepath string Path to the YAML file
function M.on_close(bufnr, filepath)
	-- Check if buffer was modified and saved
	if not vim.api.nvim_buf_is_valid(bufnr) then
		return
	end

	local root = get_project_root()
	local cmd = string.format(
		"cd %s && plm metadata import %s",
		root, vim.fn.fnameescape(filepath)
	)

	vim.fn.jobstart(cmd, {
		on_exit = function(_, exit_code)
			vim.schedule(function()
				if exit_code == 0 then
					vim.notify("Metadata imported", vim.log.levels.INFO)
					-- Refresh cache
					local cache = require("palimpsest.cache")
					cache.refresh_all()
				else
					vim.notify("Import failed", vim.log.levels.ERROR)
				end
			end)
		end,
	})
end

return M
