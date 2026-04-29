-- https://awesomewm.org/doc/api/sample%20files/rc.lua.html

-- If LuaRocks is installed, make sure that packages installed through it are
-- found (e.g. lgi). If LuaRocks is not installed, do nothing.
pcall(require, "luarocks.loader")

local splitscreen = require("splitscreen")

-- Standard awesome library
local gears = require("gears")
local awful = require("awful")
require("awful.autofocus")
-- Widget and layout library
local wibox = require("wibox")
-- Theme handling library
local beautiful = require("beautiful")
-- Notification library
local naughty = require("naughty")
local menubar = require("menubar")
local hotkeys_popup = require("awful.hotkeys_popup")

---@diagnostic disable: undefined-global
client = client
awesome = awesome
screen = screen
root = root

-- Enable hotkeys help widget for VIM and other apps
-- when client with a matching name is opened:
require("awful.hotkeys_popup.keys")
-- require('mouse-follow-focus')

--- Define custom widgets
local battery_widget = require("battery-widget")
local brightness_widget = require("brightness-widget")
local cpu_widget = require("cpu-widget")
local gpu_widget = require("gpu-widget")
local disk_usage_widget = require("disk-usage-widget")
local memory_widget = require("memory-widget")
local temperature_widget = require("temperature-widget")
local volume_widget = require('volume-widget')

local cyclefocus = require('cyclefocus')

-- {{{ Error handling
-- Check if awesome encountered an error during startup and fell back to
-- another config (This code will only ever execute for the fallback config)
if awesome.startup_errors then
    naughty.notify({
        preset = naughty.config.presets.critical,
        title = "Oops, there were errors during startup!",
        text = awesome.startup_errors
    })
end

-- Handle runtime errors after startup
do
    local in_error = false
    awesome.connect_signal("debug::error", function(err)
        -- Make sure we don't go into an endless error loop
        if in_error then
            return
        end
        in_error = true

        naughty.notify({
            preset = naughty.config.presets.critical,
            title = "Oops, an error happened!",
            text = tostring(err)
        })
        in_error = false
    end)
end
-- }}}

-- {{{ Variable definitions
-- Themes define colours, icons, font and wallpapers.
-- beautiful.init(gears.filesystem.get_themes_dir() .. "default/theme.lua")
beautiful.init(gears.filesystem.get_configuration_dir() .. "themes/dracula.lua")
-- beautiful.wallpaper = nil

-- This is used later as the default terminal and editor to run.
local terminal = "alacritty"
local editor = os.getenv("EDITOR") or "editor"
local editor_cmd = terminal .. " -e " .. editor

-- Default modkey.
-- Usually, Mod4 is the key with a logo between Control and Alt.
-- If you do not like this or do not have such a key,
-- I suggest you to remap Mod4 to another key using xmodmap or other tools.
-- However, you can use another modifier like Mod1, but it may interact with others.
local modkey = "Mod4"

-- Table of layouts to cover with awful.layout.inc, order matters.
awful.layout.layouts = { -- awful.layout.suit.floating,
    awful.layout.suit.max,
}
-- }}}

-- {{{ Menu
-- Menubar configuration
menubar.utils.terminal = terminal -- Set the terminal for applications that require it
-- }}}

-- {{{ Wibar
-- Create a textclock widget
local mytextclock = wibox.widget.textclock('%m/%d %H:%M')

-- Create a wibox for each screen and add it
local taglist_buttons = gears.table.join(awful.button({}, 1, function(t)
    t:view_only()
end), awful.button({ modkey }, 1, function(t)
    if client.focus then
        client.focus:move_to_tag(t)
    end
end), awful.button({}, 3, awful.tag.viewtoggle), awful.button({ modkey }, 3, function(t)
    if client.focus then
        client.focus:toggle_tag(t)
    end
end), awful.button({}, 4, function(t)
    awful.tag.viewnext(t.screen)
end), awful.button({}, 5, function(t)
    awful.tag.viewprev(t.screen)
end))

local tasklist_buttons = gears.table.join(awful.button({}, 1, function(c)
    if c == client.focus then
        c.minimized = true
    else
        c:emit_signal("request::activate", "tasklist", {
            raise = true
        })
    end
end), awful.button({}, 3, function()
    awful.menu.client_list({
        theme = {
            width = 250
        }
    })
end), awful.button({}, 4, function()
    awful.client.focus.byidx(1)
end), awful.button({}, 5, function()
    awful.client.focus.byidx(-1)
end))

local function set_wallpaper(s)
    -- Wallpaper
    if beautiful.wallpaper then
        local wallpaper = beautiful.wallpaper
        -- If wallpaper is a function, call it with the screen
        if type(wallpaper) == "function" then
            wallpaper = wallpaper(s)
        end
        gears.wallpaper.maximized(wallpaper, s, true)
    else
        gears.wallpaper.set("#000000")
    end
end

-- When a screen's geometry changes (e.g. different resolution)
screen.connect_signal("property::geometry", function()
    set_wallpaper()
    splitscreen:init_layout()
end)


local volume = volume_widget:new({})

awful.screen.connect_for_each_screen(function(s)
    -- Wallpaper
    set_wallpaper(s)

    -- Each screen has its own tag table.
    awful.tag({ "1" }, s, awful.layout.layouts[1])

    -- Create a promptbox for each screen
    s.mypromptbox = awful.widget.prompt()
    -- Create an imagebox widget which will contain an icon indicating which layout we're using.
    -- We need one layoutbox per screen.
    s.mylayoutbox = awful.widget.layoutbox(s)
    s.mylayoutbox:buttons(gears.table.join(awful.button({}, 1, function()
        awful.layout.inc(1)
    end), awful.button({}, 3, function()
        awful.layout.inc(-1)
    end), awful.button({}, 4, function()
        awful.layout.inc(1)
    end), awful.button({}, 5, function()
        awful.layout.inc(-1)
    end)))

    -- Create a tasklist widget
    s.mytasklist = awful.widget.tasklist {
        screen = s,
        filter = awful.widget.tasklist.filter.currenttags,
        buttons = tasklist_buttons,
        widget_template = {
            {
                {
                    {
                        id = 'icon_role',
                        widget = wibox.widget.imagebox,
                    },
                    halign = 'center',
                    valign = 'center',
                    widget = wibox.container.place,
                },
                {
                    id = 'text_role',
                    widget = wibox.widget.textbox,
                },
                layout = wibox.layout.fixed.horizontal,
            },
            id = 'background_role',
            widget = wibox.container.background,
        }
    }

    -- Create the wibox
    s.mywibox = awful.wibar({
        position = "top",
        screen = s
    })

    local systray = wibox.widget.systray()

    local right_widgets = {
        layout = wibox.layout.fixed.horizontal,
    }

    for _, w in ipairs({
        cpu_widget(),
        gpu_widget() or false,
        temperature_widget {},
        volume.widget,
        brightness_widget {},
        memory_widget {},
        disk_usage_widget {},
        battery_widget {} or false,
        systray,
        mytextclock,
    }) do
        if w then table.insert(right_widgets, w) end
    end

    -- Add widgets to the wibox
    s.mywibox:setup {
        layout = wibox.layout.align.horizontal,
        { -- Left widgets
            layout = wibox.layout.fixed.horizontal,
            -- s.mytaglist,
            s.mypromptbox
        },
        s.mytasklist, -- Middle widget
        right_widgets
    }
end)
-- }}}

-- {{{ Key bindings
local globalkeys = gears.table.join(
    awful.key({ modkey, }, "h", hotkeys_popup.show_help,
        { description = "show help", group = "awesome" }),
    -- awful.key({ modkey, }, "Left", awful.tag.viewprev,
    --     { description = "view previous", group = "tag" }),
    -- awful.key({ modkey, }, "Right", awful.tag.viewnext,
    --     { description = "view next", group = "tag" }),
    -- awful.key({ modkey, }, "Escape", awful.tag.history.restore,
    --     { description = "go back", group = "tag" }),

    -- awful.key({ modkey, }, "j",
    --     function()
    --         awful.client.focus.byidx(1)
    --     end,
    --     { description = "focus next by index", group = "client" }
    -- ),
    -- awful.key({ modkey, }, "k",
    --     function()
    --         awful.client.focus.byidx(-1)
    --     end,
    --     { description = "focus previous by index", group = "client" }
    -- ),
    -- awful.key({ modkey, }, "w", function() mymainmenu:show() end,
    --     { description = "show main menu", group = "awesome" }),

    -- Layout manipulation
    awful.key({ modkey, "Shift" }, "j", function()
        awful.client.swap.byidx(1)
    end, {
        description = "swap with next client by index",
        group = "client"
    }),
    awful.key({ modkey, "Shift" }, "k", function()
        awful.client.swap.byidx(-1)
    end, {
        description = "swap with previous client by index",
        group = "client"
    }),
    awful.key({ modkey }, "f", function()
        local c = client.focus
        if c then
            c.floating = not c.floating
            if c.floating then
                c.width = 1920
                c.height = 1080
                awful.placement.centered(c, { honor_workarea = true })
            end
        end
    end, { description = "toggle window floating 1920x1080", group = "client" }),
    awful.key({ modkey, "Control" }, "j", function()
        awful.screen.focus_relative(1)
    end, {
        description = "focus the next screen",
        group = "screen"
    }),
    awful.key({ modkey, "Control" }, "k", function()
        awful.screen.focus_relative(-1)
    end, {
        description = "focus the previous screen",
        group = "screen"
    }),
    awful.key({ modkey }, "u", awful.client.urgent.jumpto, {
        description = "jump to urgent client",
        group = "client"
    }),
    -- awful.key({ "Mod1" }, "Tab", function()
    --     awful.client.focus.history.previous()
    --     if client.focus then
    --         client.focus:raise()
    --     end
    -- end, {
    --     description = "go back",
    --     group = "client"
    -- }),
    awful.key({ "Mod1" }, "Tab", function()
        cyclefocus.cycle({ modifier = "Alt_L" })
    end, {
        description = "cycle through clients",
        group = "client"
    }),

    -- Standard program
    -- awful.key({ modkey, }, "Return", function() awful.spawn(terminal) end,
    --     { description = "open a terminal", group = "launcher" }),
    awful.key({ modkey, "Control" }, "r", awesome.restart,
        { description = "reload awesome", group = "awesome" }),
    awful.key({ modkey, "Shift" }, "q", awesome.quit,
        { description = "quit awesome", group = "awesome" }),

    awful.key({ modkey, "Control" }, "h", function()
        awful.tag.incncol(1, nil, true)
    end, {
        description = "increase the number of columns",
        group = "layout"
    }),
    awful.key({ modkey, "Control" }, "l", function()
        awful.tag.incncol(-1, nil, true)
    end, {
        description = "decrease the number of columns",
        group = "layout"
    }),
    awful.key({ modkey, "Control" }, "n", function()
        local c = awful.client.restore()
        -- Focus restored client
        if c then
            c:emit_signal("request::activate", "key.unminimize", {
                raise = true
            })
        end
    end, {
        description = "restore minimized",
        group = "client"
    }),

    -- Prompt
    -- awful.key({ modkey }, "r", function()
    --     awful.screen.focused().mypromptbox:run()
    -- end, {
    --     description = "run prompt",
    --     group = "launcher"
    -- }),
    -- awful.key({ modkey }, "x", function()
    --     awful.prompt.run {
    --         prompt = "Run Lua code: ",
    --         textbox = awful.screen.focused().mypromptbox.widget,
    --         exe_callback = awful.util.eval,
    --         history_path = awful.util.get_cache_dir() .. "/history_eval"
    --     }
    -- end, {
    --     description = "lua execute prompt",
    --     group = "awesome"
    -- }),
    awful.key({ modkey }, "\\", function()
        splitscreen:toggle_layout()
    end, {
        description = "toggle fake screen layout",
        group = "layouts"
    }),

    -- Menubar
    awful.key({ modkey }, "r", function() menubar.show() end,
        { description = "show the menubar", group = "launcher" }),

    -- Volume control
    awful.key({}, "XF86AudioRaiseVolume", function()
        volume:up()
    end),
    awful.key({}, "XF86AudioLowerVolume", function()
        volume:down()
    end),
    awful.key({ modkey }, "Up", function()
        volume:up()
    end),
    awful.key({ modkey }, "Down", function()
        volume:down()
    end),

    -- Media control
    awful.key({}, "F10", function()
        awful.util.spawn("playerctl play-pause", false)
    end, {
        description = "play/pause media",
        group = "media"
    }),

    -- Brightness control
    awful.key({}, "XF86MonBrightnessUp", function()
        brightness_widget:inc()
    end, {
        description = "increase brightness",
        group = "custom"
    }),
    awful.key({}, "XF86MonBrightnessDown", function()
        brightness_widget:dec()
    end, {
        description = "decrease brightness",
        group = "custom"
    }),
    awful.key({ modkey, "Mod1" }, "Up", function()
        brightness_widget:inc()
    end, {
        description = "increase brightness",
        group = "custom"
    }),
    awful.key({ modkey, "Mod1" }, "Down", function()
        brightness_widget:dec()
    end, {
        description = "decrease brightness",
        group = "custom"
    }),

    awful.key({ modkey }, "a", naughty.destroy_all_notifications,
        { description = "clear notifications", group = "awesome" }),

    -- Lock screen
    awful.key({ modkey }, "l", function()
        awful.spawn("betterlockscreen -l --off 5")
    end, {
        description = "lock screen",
        group = "system"
    })
)

local clientkeys = gears.table.join(
-- awful.key({ modkey }, "f", function(c)
--     c.fullscreen = not c.fullscreen
--     c:raise()
-- end, {
--     description = "toggle fullscreen",
--     group = "client"
-- }),
    awful.key({ "Mod1" }, "F4", function(c)
        c:kill()
    end, {
        description = "close",
        group = "client"
    }),
    awful.key({ "Mod1" }, "q", function(c)
        c:kill()
    end, {
        description = "close",
        group = "client"
    }),
    awful.key({ modkey, "Control" }, "space", awful.client.floating.toggle, {
        description = "toggle floating",
        group = "client"
    }),
    awful.key({ modkey, "Control" }, "Return", function(c)
        c:swap(awful.client.getmaster())
    end, {
        description = "move to master",
        group = "client"
    }),
    awful.key({ modkey }, "o", function(c)
        -- Cycle to the next screen
        -- Compared to using c:move_to_screen(), the following does not move the mouse position.
        local current_screen = c.screen.index
        local next_screen = (current_screen % screen.count()) + 1
        c.screen = screen[next_screen]
    end, { description = "cycle client through screens", group = "client" }),
    awful.key({ modkey }, "t", function(c)
        c.ontop = not c.ontop
    end, {
        description = "toggle keep on top",
        group = "client"
    }),
    awful.key({ modkey }, "n", function(c)
        -- The client currently has the input focus, so it cannot be
        -- minimized, since minimized clients can't have the focus.
        c.minimized = true
    end, {
        description = "minimize",
        group = "client"
    })
)

local clientbuttons = gears.table.join(
    awful.button({}, 1, function(c)
        c:emit_signal("request::activate", "mouse_click", {
            raise = true
        })
    end),
    awful.button({ modkey }, 1, function(c)
        c:emit_signal("request::activate", "mouse_click", {
            raise = true
        })
        awful.mouse.client.move(c)
    end),
    awful.button({ modkey }, 3, function(c)
        c:emit_signal("request::activate", "mouse_click", {
            raise = true
        })
        awful.mouse.client.resize(c)
    end),
    awful.button(
        { modkey },
        4 -- mouse wheel scroll up
        , function(c)
            awful.util.spawn("pactl set-sink-volume @DEFAULT_SINK@ +5%", false)
        end
    ),
    awful.button(
        { modkey },
        5, -- mouse wheel scroll down
        function(c)
            awful.util.spawn("pactl set-sink-volume @DEFAULT_SINK@ -5%", false)
        end
    )
)

-- Set keys
root.keys(globalkeys)
-- }}}

-- {{{ Rules
-- Rules to apply to new clients (through the "manage" signal).
awful.rules.rules = { -- All clients will match this rule.
    {
        rule = {},
        properties = {
            border_width = beautiful.border_width,
            border_color = beautiful.border_normal,
            focus = awful.client.focus.filter,
            raise = true,
            keys = clientkeys,
            buttons = clientbuttons,
            screen = awful.screen.preferred,
            placement = awful.placement.no_overlap + awful.placement.no_offscreen
        }
    }, -- Floating clients.
    {
        rule_any = {
            instance = { "DTA",                                                     -- Firefox addon DownThemAll.
                "copyq",                                                            -- Includes session name in class.
                "pinentry" },
            class = { "Arandr", "Blueman-manager", "Gpick", "Kruler", "MessageWin", -- kalarm.
                "Sxiv",
                "Tor Browser",                                                      -- Needs a fixed window size to avoid fingerprinting by screen size.
                "Wpa_gui", "veromix", "xtightvncviewer", "mpv", },

            -- Note that the name property shown in xprop might be set slightly after creation of the client
            -- and the name shown there might not match defined rules here.
            name = { "Event Tester" -- xev.
            },
            role = { "AlarmWindow", -- Thunderbird's calendar.
                "ConfigManager",    -- Thunderbird's about:config.
                -- "pop-up" -- e.g. Google Chrome's (detached) Developer Tools.
            }
        },
        properties = {
            floating = true
        }
    }, -- Add titlebars to normal clients and dialogs
    {
        rule_any = {
            type = { "normal", "dialog" }
        },
        properties = {
            titlebars_enabled = false
        }
    } -- Set Firefox to always map on the tag named "2" on screen 1.
    -- { rule = { class = "Firefox" },
    --   properties = { screen = 1, tag = "2" } },
}
-- }}}

-- {{{ Signals
-- Signal function to execute when a new client appears.
client.connect_signal("manage", function(c)
    -- Set the windows at the slave,
    -- i.e. put it at the end of others instead of setting it master.
    -- if not awesome.startup then awful.client.setslave(c) end

    if awesome.startup and not c.size_hints.user_position and not c.size_hints.program_position then
        -- Prevent clients from being unreachable after screen count changes.
        awful.placement.no_offscreen(c)
    end

    if c.floating or (c.first_tag and c.first_tag.layout.name == "floating") then
        -- Center the new window on the screen
        awful.placement.centered(c, { honor_workarea = true, honor_padding = true })
    end
end)

-- Add a titlebar if titlebars_enabled is set to true in the rules.
client.connect_signal("request::titlebars", function(c)
    -- buttons for the titlebar
    local buttons = gears.table.join(awful.button({}, 1, function()
        c:emit_signal("request::activate", "titlebar", {
            raise = true
        })
        awful.mouse.client.move(c)
    end), awful.button({}, 3, function()
        c:emit_signal("request::activate", "titlebar", {
            raise = true
        })
        awful.mouse.client.resize(c)
    end))

    awful.titlebar(c):setup {
        { -- Left
            awful.titlebar.widget.iconwidget(c),
            buttons = buttons,
            layout = wibox.layout.fixed.horizontal
        },
        {     -- Middle
            { -- Title
                align = "center",
                widget = awful.titlebar.widget.titlewidget(c)
            },
            buttons = buttons,
            layout = wibox.layout.flex.horizontal
        },
        { -- Right
            awful.titlebar.widget.floatingbutton(c),
            awful.titlebar.widget.maximizedbutton(c),
            awful.titlebar.widget.stickybutton(c),
            awful.titlebar.widget.ontopbutton(c),
            awful.titlebar.widget.closebutton(c),
            layout = wibox.layout.fixed.horizontal()
        },
        layout = wibox.layout.align.horizontal
    }
end)

-- -- Enable sloppy focus, so that focus follows mouse.
-- client.connect_signal("mouse::enter", function(c)
--     c:emit_signal("request::activate", "mouse_enter", {
--         raise = false
--     })
-- end)

client.connect_signal("focus", function(c)
    c.border_color = beautiful.border_focus
end)

client.connect_signal("unfocus", function(c)
    c.border_color = beautiful.border_normal
end)
-- }}}

splitscreen:init_layout()
