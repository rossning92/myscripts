local awful = require("awful")
local status_widget = require("status-widget")

local disk_usage_widget = {}

local function worker()
    local widget, text = status_widget.new("harddisk")
    local _, timer = awful.widget.watch(
        "df -h --output=used,size /",
        30,
        function(_, stdout)
            local used, size = stdout:match("\n%s*(%S+)%s+(%S+)")
            if used and size then
                local formatted_used = used:gsub("G$", "")
                text:set_text(formatted_used .. "/" .. size)
            end
        end
    )

    widget.disk_timer = timer
    return widget
end

return setmetatable(disk_usage_widget, {
    __call = function(_)
        return worker()
    end
})
