local awful = require("awful")
local status_widget = require("status-widget")

local gpu_widget = {}

local function worker()
    if os.execute("command -v nvidia-smi >/dev/null 2>&1") ~= true then
        return nil
    end

    local widget, text, graph = status_widget.new_graph("expansion-card")
    local vram_display, vram_text, vram_graph = status_widget.new_graph(nil, "#6272a4")
    widget:add(vram_display)

    -- `-l 1` reports GPU data every 1 second
    awful.spawn.with_line_callback('nvidia-smi --query-gpu=utilization.gpu,temperature.gpu,memory.used,memory.total --format=csv,noheader,nounits -l 1', {
        stdout = function(line)
            local utilization, temperature, memory_used, memory_total =
                line:match("(%d+)%s*,%s*(%d+)%s*,%s*(%d+)%s*,%s*(%d+)")
            utilization = tonumber(utilization)
            if utilization then
                graph:add_value(utilization)
            end
            memory_used = tonumber(memory_used)
            memory_total = tonumber(memory_total)
            if memory_used and memory_total and memory_total > 0 then
                vram_graph:add_value(memory_used / memory_total * 100)
                vram_text:set_text(string.format("%.1fG", memory_used / 1024))
            end
            if temperature then
                text:set_text(temperature .. "°C")
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
