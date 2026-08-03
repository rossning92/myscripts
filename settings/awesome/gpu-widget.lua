local awful = require("awful")
local status_widget = require("status-widget")

local gpu_widget = {}

local function worker()
    if os.execute("command -v nvidia-smi >/dev/null 2>&1") ~= true then
        return nil
    end

    local widget, text = status_widget.new("expansion-card")
    local icon = "󰢮";

    -- `-l 1` reports GPU data every 1 second
    awful.spawn.with_line_callback('nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits -l 1', {
        stdout = function(line)
            local utilization = line:match("(%d+)")
            if utilization then
                text:set_text(utilization .. "%")
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
