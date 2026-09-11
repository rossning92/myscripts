local awful = require("awful")
local status_widget = require("status-widget")

local memory_widget = {}

local function worker()
    local widget, text = status_widget.new("ram")
    local _, timer = awful.widget.watch(
        "free -b",
        1,
        function(_, stdout)
            local total, used = stdout:match("Mem:%s+(%S+)%s+(%S+)")
            if total and used then
                local percentage = math.floor(tonumber(used) / tonumber(total) * 100 + 0.5)
                text:set_text(string.format("%-3s", math.min(percentage, 99) .. "%"))
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
