local awful = require("awful")
local status_widget = require("status-widget")

local disk_usage_widget = {}

local function worker()
    local widget, text = status_widget.new("stacked-disk")
    local _, timer = awful.widget.watch(
        "df --output=pcent /",
        30,
        function(_, stdout)
            local percentage = stdout:match("\n%s*(%d+)%%")
            if percentage then
                text:set_text(string.format("%-3s", math.min(tonumber(percentage), 99) .. "%"))
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
