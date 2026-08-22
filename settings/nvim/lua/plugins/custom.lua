local function read_text_file(filepath)
    local file, err = io.open(filepath, "r")
    if not file then
        error("Error: Could not open file '" .. filepath .. "'. " .. (err or "Unknown error"))
    end

    local text = file:read("*a")
    file:close()
    os.remove(filepath)
    return text
end

local function get_selected_text()
    local mode = vim.fn.mode()
    local start_pos = vim.fn.getpos("v")
    local end_pos = vim.fn.getpos(".")

    -- Swap start_pos and end_pos if start comes after end.
    if start_pos[2] > end_pos[2] or (start_pos[2] == end_pos[2] and start_pos[3] > end_pos[3]) then
        start_pos, end_pos = end_pos, start_pos
    end

    -- Retrieve the lines in the buffer from start_pos to end_pos.
    local lines = vim.api.nvim_buf_get_lines(0, start_pos[2] - 1, end_pos[2], false)

    -- Extract text only within the region defined by start_pos and end_pos.
    local text = ""
    if mode == 'v' then
        text = vim.api.nvim_buf_get_text(0, start_pos[2] - 1, start_pos[3] - 1, end_pos[2] - 1, end_pos[3], {})[1]
    else
        text = table.concat(lines, '\n')
        start_pos[3] = 1
        end_pos[3] = #(lines[#lines] or '')
    end

    return text, start_pos, end_pos
end

local function replace_text(text, start_pos, end_pos)
    -- Split the reconstructed text back into lines.
    local lines = {}
    for line in text:gmatch("[^\r\n]+") do
        table.insert(lines, line)
    end

    -- Set the modified lines back to the buffer.
    -- vim.api.nvim_buf_set_lines(0, start_pos[2] - 1, end_pos[2], false, lines)
    vim.api.nvim_buf_set_text(0, start_pos[2] - 1, start_pos[3] - 1, end_pos[2] - 1, end_pos[3], lines)

    -- Move cursor to the end of the last line of the replaced text.
    vim.api.nvim_win_set_cursor(0, { start_pos[2] + #lines - 1, #lines[#lines] })
end

local function run_in_terminal(cmd, opts)
    opts = opts or {}

    -- Create a new buffer (unlisted and scratch)
    local bufnr = vim.api.nvim_create_buf(false, true)

    -- Split the current window and open the new buffer in the bottom half
    vim.cmd('split')
    vim.cmd('wincmd J') -- Move the new split to the bottom
    local win_id = vim.api.nvim_get_current_win()
    if opts.height then
        vim.api.nvim_win_set_height(win_id, opts.height)
    end
    vim.api.nvim_win_set_buf(win_id, bufnr)

    -- Start a terminal and run command
    vim.fn.termopen(cmd, {
        on_exit = function(_, exit_code, _)
            if exit_code == 0 then
                -- Close the window if exit code is 0
                vim.api.nvim_win_close(win_id, true)
                if opts.on_exit then
                    opts.on_exit()
                end
            end
        end
    })
end

local function is_windows()
    local os_name = os.getenv("OS")
    return os_name and os_name:lower():match("windows")
end

-- Workaround: If Neovim is running on Windows within MSYS2, we should force set
-- the default shell to cmd.exe in order to have commands like `termopen`
-- working properly.
if is_windows() then
    vim.o.shell = "cmd.exe"
end

local function write_to_temp_file(content, extension)
    local file_path = os.tmpname() .. (extension or "")
    local file = io.open(file_path, "w")
    if file then
        file:write(content)
        file:close()
    end
    return file_path
end

local function edit_selected_text(opts)
    local text, start_pos, end_pos = get_selected_text()
    local input_file = nil
    local output_file = os.tmpname()
    local command = "run_script r/ai/chat_menu.py -o " .. output_file

    opts = opts or {}

    if opts.message then
        input_file = write_to_temp_file(text, ".txt")
        command = command .. " --context " .. input_file .. " " .. vim.fn.shellescape(opts.message)
    elseif opts.prefix then
        local prompt = opts.prefix .. text
        input_file = write_to_temp_file(prompt)
        command = command .. " -i " .. input_file
    else
        input_file = write_to_temp_file(text, ".txt")
        command = command .. " --context " .. input_file
    end

    run_in_terminal(command, {
        height = 5,
        on_exit = function()
            local new_text = read_text_file(output_file)
            replace_text(new_text, start_pos, end_pos)

            if input_file then
                os.remove(input_file)
            end
        end
    })
end

local function fix()
    edit_selected_text({
        message = "rephrase and fix grammar"
    })
end

local function inline_chat()
    edit_selected_text()
end
vim.keymap.set({ "n", "i", "v", "x" }, "<C-k>i", inline_chat)
vim.keymap.set({ "n", "i", "v", "x" }, "<C-k>f", fix)

local function append_line(line)
    line = string.gsub(line, '^%s*(.-)%s*$', '%1') -- trim trailing spaces

    local current_line = vim.api.nvim_get_current_line()
    local cur_row_number = vim.api.nvim_win_get_cursor(0)[1] -- 1-based

    -- Determine where to insert this new line
    local insert_index -- zero-based
    if current_line == "" then
        insert_index = cur_row_number - 1
    else
        insert_index = cur_row_number
    end

    -- Insert line
    vim.api.nvim_buf_set_lines(0, insert_index, insert_index, false, { line })

    -- Move cursor to the end of the newly inserted line
    vim.api.nvim_win_set_cursor(0, {
        insert_index + 1, -- row number: 1-based
        #line             -- column index: 0-based
    })
end

local function speech_to_text()
    local tmp_file = os.tmpname()
    run_in_terminal("run_script r/speech_to_text.py -o " .. tmp_file, {
        height = 1,
        on_exit = function()
            local text = read_text_file(tmp_file)
            os.remove(tmp_file)
            if text ~= "" then
                append_line(text)
            end
        end
    })
end
vim.keymap.set('n', "<leader><space>", speech_to_text)

local function run_agent()
    local full_path = vim.api.nvim_buf_get_name(0)
    if full_path ~= "" then
        local mode = vim.fn.mode()

        if mode == "v" or mode == "V" or mode == "\22" then
            -- Get selected line ranges
            local start_pos = vim.fn.getpos("v")
            local end_pos = vim.fn.getpos(".")
            local line_start = start_pos[2]
            local line_end = end_pos[2]

            -- Swap line start and end if start comes after end
            if line_start > line_end then
                line_start, line_end = line_end, line_start
            end

            -- Concatenate selected line range at the end
            full_path = full_path .. "#" .. line_start .. "-" .. line_end
        end

        run_in_terminal('start_script --cd=false r/ai/agent.py --context ' .. vim.fn.shellescape(full_path), {
            on_exit = function()
                -- Reload the current file from disk
                vim.api.nvim_command('edit!')
            end
        })
    end
end
vim.keymap.set({ "n", "i", "v", "x" }, "<M-i>", run_agent)

local function start_script_with_selection()
    local text = get_selected_text()
    local temp_file = write_to_temp_file(text, ".txt")
    vim.fn.jobstart('start_script r/ai/ask.py ' .. temp_file)
end
vim.keymap.set({ "n", "i", "v", "x" }, "<C-k>a", start_script_with_selection)

return {}
