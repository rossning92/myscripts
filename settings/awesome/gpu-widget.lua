local awful = require("awful")
local beautiful = require("beautiful")
local wibox = require("wibox")
local dpi = require("beautiful.xresources").apply_dpi
local status_widget = require("status-widget")

local gpu_widget = {}

local function worker()
    if os.execute("command -v nvidia-smi >/dev/null 2>&1") ~= true then
        return nil
    end

    local widget = status_widget.new("expansion-card")
    local graph = wibox.widget {
        max_value = 100,
        forced_width = dpi(36),
        forced_height = dpi(12),
        color = beautiful.border_focus,
        background_color = beautiful.bg_focus,
        step_width = dpi(2),
        step_spacing = 0,
        widget = wibox.widget.graph,
    }
    widget:add(wibox.container.mirror(graph, { horizontal = true }))

    -- `-l 1` reports GPU data every 1 second
    awful.spawn.with_line_callback('nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits -l 1', {
        stdout = function(line)
            local utilization = tonumber(line:match("(%d+)"))
            if utilization then
                graph:add_value(utilization)
            end
        end
    })

    return widget
end

return setmetatable(gpu_widget, {
    __call = function(_)
        return worker()
    end
})
