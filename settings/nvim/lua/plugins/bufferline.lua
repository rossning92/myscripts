return {
    'akinsho/bufferline.nvim',
    version = '*',
    dependencies = { 'nvim-tree/nvim-web-devicons' },
    opts = {
        options = {
            diagnostics = 'nvim_lsp',
            always_show_bufferline = true,
            show_close_icon = false,
            show_buffer_close_icons = false,
        },
    },
}
