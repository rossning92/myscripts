local gears = require("gears")
local status_widget = require("status-widget")

local function read_file(path)
    local file = io.open(path, "r")
    if not file then
        return nil
    end

    local value = file:read("*l")
    file:close()
    return value
end

local function find_battery()
    for index = 0, 9 do
        local path = "/sys/class/power_supply/BAT" .. index
        if gears.filesystem.file_readable(path .. "/capacity") then
            return path
        end
    end
end

local function worker()
    local battery_path = find_battery()
    if not battery_path then
        return nil
    end

    local widget, text, icon = status_widget.new("battery")

    local function update()
        local level = tonumber(read_file(battery_path .. "/capacity"))
        local status = read_file(battery_path .. "/status")

        if level then
            local icon_name = status == "Charging" and "battery-charging" or "battery"
            icon:set_image(status_widget.icon(icon_name))
            text:set_text(level .. "%")
        end
    end

    widget.battery_timer = gears.timer {
        timeout = 10,
        autostart = true,
        call_now = true,
        callback = update,
    }

    return widget
end

return setmetatable({}, {
    __call = function(_)
        return worker()
    end
})
