local awful = require("awful")
local status_widget = require("status-widget")

local Volume = { mt = {}, wmt = {} }
Volume.wmt.__index = Volume
Volume.__index = Volume

function Volume:new(args)
    local obj = setmetatable({}, Volume)
    obj.step = args.step or 10

    local widget, text = status_widget.new("volume-high")
    local _, volume_text_timer = awful.widget.watch(
        "pactl get-sink-volume @DEFAULT_SINK@", 5,
        function(_, stdout)
            local volume = stdout:match("(%d+)%%")
            if volume then
                text:set_text(volume .. "%")
                return
            end
        end,
        text
    )
    obj.volume_text_timer = volume_text_timer

    obj.widget = widget

    return obj
end

function Volume:up()
    awful.spawn.easy_async("pactl set-sink-volume @DEFAULT_SINK@ +" .. self.step .. "%", function()
        self.volume_text_timer:emit_signal("timeout")
    end)
end

function Volume:down()
    awful.spawn.easy_async("pactl set-sink-volume @DEFAULT_SINK@ -" .. self.step .. "%", function()
        self.volume_text_timer:emit_signal("timeout")
    end)
end

function Volume.mt:__call(...)
    return Volume.new(...)
end

return Volume
