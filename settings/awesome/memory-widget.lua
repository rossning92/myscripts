local awful = require("awful")
local status_widget = require("status-widget")

local memory_widget = {}

local function worker()
    local widget, text = status_widget.new("memory")
    local _, timer = awful.widget.watch(
        'free -h',
        1,
        function(_, stdout)
            local total, used = stdout:match("Mem:%s+(%S+)%s+(%S+)")
            if total and used then
                local formatted_used = used:gsub("Gi", "")
                local formatted_total = total:gsub("Gi", "G")
                text:set_text(formatted_used .. "/" .. formatted_total)
            end
        end
    )

    widget.memory_timer = timer
    return widget
end

return setmetatable(memory_widget, {
    __call = function(_)
        return worker()
    end
})
