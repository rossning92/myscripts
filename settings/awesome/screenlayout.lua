local awful = require("awful")
local M = {}

-- Change this to another ratio when desired, for example 16 / 10 or 21 / 9.
local USABLE_ASPECT_RATIO = 16 / 9
local MAIN_PANE_RATIO = 1 / 2

local pin_state = nil

-- Keep newly managed clients on the main (left) screen while a client is
-- pinned. Otherwise, preserve Awesome's normal preferred-screen behavior.
function M.preferred_screen(c)
    if pin_state
        and pin_state.parent_screen
        and pin_state.parent_screen.valid
    then
        return pin_state.parent_screen
    end

    return awful.screen.preferred(c)
end

-- Keep a wide display's Awesome-managed region at the configured aspect ratio.
-- The unused pixels to the right remain part of the black root background.
function M.apply_usable_region()
    if pin_state or screen.count() ~= 1 then return end

    local s = screen[1]
    local geo = s.geometry
    local target_width = math.floor(geo.height * USABLE_ASPECT_RATIO + 0.5)
    if geo.width > target_width then
        s:fake_resize(geo.x, geo.y, target_width, geo.height)
    end
end

local function create_pinned_region(parent)
    local original_geometry = parent.geometry
    local main_width = math.floor(original_geometry.width * MAIN_PANE_RATIO + 0.5)
    local pinned_width = original_geometry.width - main_width

    parent:fake_resize(
        original_geometry.x,
        original_geometry.y,
        main_width,
        original_geometry.height
    )

    local pinned_screen = screen.fake_add(
        original_geometry.x + main_width,
        original_geometry.y,
        pinned_width,
        original_geometry.height
    )
    for _, tag in pairs(pinned_screen.tags) do
        tag.layout = awful.layout.suit.max
    end

    return pinned_screen, original_geometry
end

local function restore_usable_region()
    local state = pin_state
    if not state then return end
    pin_state = nil

    local c = state.client
    if c and c.valid then
        if state.parent_screen and state.parent_screen.valid then
            c.screen = state.parent_screen
        end
        if state.tag and state.tag.valid then
            c:tags({ state.tag })
        end

        c.sticky = state.sticky
        c.ontop = state.ontop
        c.floating = state.floating
        c.fullscreen = state.fullscreen
        c.maximized = state.maximized
        c:emit_signal("request::activate", "screenlayout.unpin", { raise = true })
    end

    if state.pinned_screen and state.pinned_screen.valid then
        state.pinned_screen:fake_remove()
    end
    if state.parent_screen and state.parent_screen.valid then
        local geo = state.original_geometry
        state.parent_screen:fake_resize(geo.x, geo.y, geo.width, geo.height)
    end
end

-- Pin the focused client on the right while the left side continues using its
-- own layout. Invoking this again restores the original full-screen layout.
function M.toggle_pin(c)
    if pin_state then
        restore_usable_region()
        return
    end

    c = c or client.focus
    if not c or screen.count() ~= 1 then return end

    local parent_screen = c.screen
    local pinned_screen, original_geometry = create_pinned_region(parent_screen)

    pin_state = {
        client = c,
        parent_screen = parent_screen,
        pinned_screen = pinned_screen,
        original_geometry = original_geometry,
        tag = c.first_tag,
        sticky = c.sticky,
        ontop = c.ontop,
        floating = c.floating,
        fullscreen = c.fullscreen,
        maximized = c.maximized,
    }

    c.fullscreen = false
    c.maximized = false
    c.floating = false
    c.ontop = false
    c.sticky = true
    c.screen = pinned_screen
    if pinned_screen.selected_tag then
        c:tags({ pinned_screen.selected_tag })
    end
    c:emit_signal("request::activate", "screenlayout.pin", { raise = true })
end

return M
