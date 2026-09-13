local beautiful = require("beautiful")
local gears = require("gears")
local wibox = require("wibox")

local dpi = require("beautiful.xresources").apply_dpi
local icon_dir = gears.filesystem.get_configuration_dir() .. "icons/"

local status_widget = {}
local icon_cache = {}

function status_widget.icon(name, color)
    color = color or beautiful.fg_normal

    local key = name .. ":" .. color
    if not icon_cache[key] then
        icon_cache[key] = gears.color.recolor_image(
            icon_dir .. name .. ".svg",
            color
        )
    end

    return icon_cache[key]
end

function status_widget.new(icon_name)
    local icon_size = beautiful.wibar_height or dpi(18)

    local icon = wibox.widget {
        image = status_widget.icon(icon_name),
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

function status_widget.new_graph(icon_name, color)
    local widget, text
    if icon_name then
        widget, text = status_widget.new(icon_name)
    else
        text = wibox.widget.textbox()
    end

    local graph = wibox.widget {
        max_value = 100,
        color = color or beautiful.border_focus,
        background_color = beautiful.bg_focus,
        step_width = dpi(2),
        step_spacing = 0,
        widget = wibox.widget.graph,
    }
    text.font = "sans 7"
    local display = wibox.widget {
        wibox.container.mirror(graph, { horizontal = true }),
        {
            text,
            halign = "left",
            valign = "top",
            widget = wibox.container.place,
        },
        forced_width = dpi(36),
        forced_height = dpi(12),
        layout = wibox.layout.stack,
    }

    if icon_name then
        widget:set(2, display)
        display = widget
    end

    return display, text, graph
end

return status_widget
