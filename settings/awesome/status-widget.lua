local beautiful = require("beautiful")
local gears = require("gears")
local wibox = require("wibox")

local dpi = require("beautiful.xresources").apply_dpi
local icon_dir = gears.filesystem.get_configuration_dir() .. "icons/"

local status_widget = {}

function status_widget.icon_path(name)
    return icon_dir .. name .. ".svg"
end

function status_widget.new(icon_name)
    local icon_size = beautiful.wibar_height or dpi(18)

    local icon = wibox.widget {
        image = status_widget.icon_path(icon_name),
        resize = true,
        forced_width = icon_size,
        forced_height = icon_size,
        widget = wibox.widget.imagebox,
    }

    local text = wibox.widget.textbox()

    local widget = wibox.widget {
        icon,
        text,
        layout = wibox.layout.fixed.horizontal,
    }

    return widget, text, icon
end

return status_widget
