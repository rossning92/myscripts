-- A starting point for Neovim config: https://github.com/nvim-lua/kickstart.nvim/blob/master/init.lua

vim.loader.enable() -- Cache Lua bytecode to speed up require()

pcall(require, 'local')

vim.wo.relativenumber = true
vim.wo.number = true
vim.g.mapleader = " "
vim.opt.shortmess:append("IA")    -- Disable intro message and swapfile warning
vim.opt.clipboard = "unnamedplus" -- Use system clipboard
vim.opt.termguicolors = true
vim.opt.mouse = ""                -- Disable mouse
vim.opt.ignorecase = true
vim.opt.smartcase = true
vim.opt.incsearch = true
vim.opt.hlsearch = true

-- Folding: detect folds from indentation, but open files fully expanded.
vim.opt.foldmethod = "indent"
vim.opt.foldenable = true
vim.opt.foldlevel = 99
vim.opt.foldlevelstart = 99
vim.opt.foldcolumn = "1"

vim.keymap.set('n', '<Esc>', '<cmd>nohlsearch<CR>')

vim.g.loaded_netrw = 1         -- built-in file explorer (replaced by telescope)
vim.g.loaded_netrwPlugin = 1   -- netrw's plugin wrapper
vim.g.loaded_matchit = 1       -- extended % matching for HTML tags, if/else, etc.
vim.g.loaded_tarPlugin = 1
vim.g.loaded_zipPlugin = 1
vim.g.loaded_gzip = 1
vim.g.loaded_2html_plugin = 1
vim.g.loaded_tutor_mode_plugin = 1

-- Better up/down movement
vim.keymap.set('n', '<up>', "v:count == 0 ? 'gk' : 'k'", { expr = true, silent = true })
vim.keymap.set('n', '<down>', "v:count == 0 ? 'gj' : 'j'", { expr = true, silent = true })
vim.keymap.set('i', '<up>', '<C-o>gk', { silent = true })
vim.keymap.set('i', '<down>', '<C-o>gj', { silent = true })

-- Scroll 5 lines and recenter the cursor
vim.keymap.set("n", "<C-u>", "5<C-y>5kzz", { noremap = true, silent = true })
vim.keymap.set("n", "<C-d>", "5<C-e>5jzz", { noremap = true, silent = true })

-- Copy current file path to clipboard
vim.keymap.set("n", "<leader>yp", function()
  vim.fn.setreg("+", vim.fn.expand("%:p"))
end, { desc = "Copy file path" })

-- Quickly save the file
vim.keymap.set("i", "WW", "<Esc>:w<CR>i")
vim.keymap.set({ "n", "o" }, "WW", ":w<CR>")

-- Quickly save and exit
vim.keymap.set("i", "ZZ", "<Esc>:wq<CR>")
vim.keymap.set({ "n", "o" }, "ZZ", ":wq<CR>")

-- Terminal settings
vim.api.nvim_command("autocmd TermOpen * startinsert")
vim.api.nvim_command("autocmd TermOpen * setlocal nonumber norelativenumber signcolumn=no")

-- auto-reload files when modified externally
-- https://unix.stackexchange.com/a/383044
vim.o.autoread = true
-- vim.api.nvim_create_autocmd({ "BufEnter", "CursorHold", "CursorHoldI", "FocusGained" }, {
--   command = "checktime",
--   pattern = { "*" },
-- })
vim.fn.timer_start(3000, vim.schedule_wrap(function()
  vim.cmd('checktime')
end), { ["repeat"] = -1 })
local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"

if not (vim.uv or vim.loop).fs_stat(lazypath) then
  vim.fn.system({
    "git",
    "clone",
    "--filter=blob:none",
    "https://github.com/folke/lazy.nvim.git",
    "--branch=stable", -- latest stable release
    lazypath,
  })
end
vim.opt.rtp:prepend(lazypath)

require("lazy").setup({
  spec = {
    { import = "plugins" },
  },
})
