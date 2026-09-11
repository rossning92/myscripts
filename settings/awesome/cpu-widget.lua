local awful = require("awful")
local gears = require("gears")
local status_widget = require("status-widget")

local cpu_widget = {}

local function worker()
    local widget, text = status_widget.new("cpu")
    local prev_total = 0
    local prev_idle = 0
    local usage_text = "--%"
    local temperature_text
    local temperature_path

    local function update_text()
        local value = usage_text
        if temperature_text then
            value = value .. " " .. temperature_text
        end
        text:set_text(value)
    end

    local function read_file(path)
        local file = io.open(path, "r")
        if not file then return nil end
        local value = file:read("*l")
        file:close()
        return value
    end

    local function update_stats()
        local cpu_line = read_file("/proc/stat")
        if cpu_line then
            local user, nice, system, idle, iowait, irq, softirq, steal, guest, guest_nice = cpu_line:match(
                "cpu%s+(%d+)%s+(%d+)%s+(%d+)%s+(%d+)%s+(%d+)%s+(%d+)%s+(%d+)%s+(%d+)%s+(%d+)%s+(%d+)")
            if user then
                local idle_sum = idle + iowait
                local total = user + nice + system + idle + iowait + irq + softirq + steal + guest + guest_nice
                local diff_total = total - prev_total
                local diff_idle = idle_sum - prev_idle
                if diff_total > 0 then
                    local usage = math.floor(((diff_total - diff_idle) / diff_total) * 100 + 0.5)
                    usage_text = string.format("%-3s", math.min(usage, 99) .. "%")
                end
                prev_total = total
                prev_idle = idle_sum
            end
        end

        local millidegrees = temperature_path and tonumber(read_file(temperature_path))
        if millidegrees then
            local temperature = math.floor(millidegrees / 1000 + 0.5)
            local temperature_value = tostring(math.min(temperature, 99))
            temperature_text = temperature_value .. "°C" .. string.rep(" ", 2 - #temperature_value)
        end
        update_text()
    end

    -- Resolve the CPU sensor once; hwmon numbers can change between boots.
    local find_temperature_sensor = [[
        for driver in k10temp zenpower coretemp cpu_thermal; do
            for hwmon in /sys/class/hwmon/hwmon*; do
                [ "$(cat "$hwmon/name" 2>/dev/null)" = "$driver" ] || continue
                for wanted in Tctl "Package id 0" "CPU Package" CPU; do
                    for label in "$hwmon"/temp*_label; do
                        [ "$(cat "$label" 2>/dev/null)" = "$wanted" ] || continue
                        printf '%s\n' "${label%_label}_input"
                        exit
                    done
                done
                if [ "$driver" = cpu_thermal ] && [ -r "$hwmon/temp1_input" ]; then
                    printf '%s\n' "$hwmon/temp1_input"
                    exit
                fi
            done
        done
        for wanted in "CPU Package" CPU; do
            for label in /sys/class/hwmon/hwmon*/temp*_label; do
                [ "$(cat "$label" 2>/dev/null)" = "$wanted" ] || continue
                printf '%s\n' "${label%_label}_input"
                exit
            done
        done
    ]]

    awful.spawn.easy_async_with_shell(find_temperature_sensor, function(stdout)
        temperature_path = stdout:match("^([^\n]+)")
        update_stats()
    end)

    widget.cpu_timer = gears.timer {
        timeout = 1,
        autostart = true,
        call_now = true,
        callback = update_stats,
    }
    return widget
end

return setmetatable(cpu_widget, {
    __call = function(_)
        return worker()
    end
})
