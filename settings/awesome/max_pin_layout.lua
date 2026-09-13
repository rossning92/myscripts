-- Max layout with an optional client pinned in a right-hand pane.
local awful = require("awful")

local M = {}

local PINNED_PANE_RATIO = 1 / 2
local STANDARD_ASPECT_RATIO = 16 / 9

local pin_state = nil

-- This is the max layout with one optional exception: the pinned client gets
-- the right pane and every other tiled client shares the left pane. Giving all
-- regular clients the same geometry preserves max-layout stacking semantics.
M.layout = {
    name = "max + pin",
}

-- Match awful.layout.suit.max: do not introduce a useless gap merely because
-- pinning makes two tiled clients visible at once.
function M.layout.skip_gap()
    return true
end

local function is_layout_client(p, target)
    for _, c in ipairs(p.clients) do
        if c == target then return true end
    end
    return false
end

local function set_geometry(p, c, geometry)
    -- Terminals commonly request character-cell resize increments. Honoring
    -- those hints leaves unused strips at the right and bottom, which is not
    -- desirable for a max-style tiled layout.
    c.size_hints_honor = false
    -- Awesome adjusts the assigned table in place to account for the client
    -- border. Each client therefore needs its own copy; sharing one table makes
    -- the border subtraction accumulate across all maximized clients.
    p.geometries[c] = {
        x = geometry.x,
        y = geometry.y,
        width = geometry.width,
        height = geometry.height,
    }
end

function M.layout.arrange(p)
    local area = p.workarea
    local pinned = pin_state and pin_state.client or nil
    local sixteen_nine_width = math.floor(p.geometry.height * STANDARD_ASPECT_RATIO + 0.5)
    local standard_width = math.min(area.width, sixteen_nine_width)

    if not pinned or not pinned.valid or not is_layout_client(p, pinned) then
        local geometry = {
            x = area.x,
            y = area.y,
            width = standard_width,
            height = area.height,
        }
        for _, c in ipairs(p.clients) do
            set_geometry(p, c, geometry)
        end
        return
    end

    local main_width = math.floor(area.width * (1 - PINNED_PANE_RATIO) + 0.5)
    local pinned_width = area.width - main_width
    local main_geometry = {
        x = area.x,
        y = area.y,
        width = main_width,
        height = area.height,
    }
    local pinned_geometry = {
        x = area.x + main_width,
        y = area.y,
        width = pinned_width,
        height = area.height,
    }

    for _, c in ipairs(p.clients) do
        set_geometry(p, c, c == pinned and pinned_geometry or main_geometry)
    end
end

local function unpin(focus_client)
    local state = pin_state
    if not state then return end
    pin_state = nil

    local c = state.client
    if c and c.valid then
        c.fullscreen = state.fullscreen
        c.maximized = state.maximized
        c.floating = state.floating
        awful.layout.arrange(c.screen)
    end
    if focus_client and focus_client.valid then
        focus_client:emit_signal("request::activate", "max_pin_layout.unpin", { raise = true })
    end
end

-- Pin the focused client on the right. Invoking this again restores the
-- client's previous state and the normal full-width max layout.
function M.toggle_pin(c)
    if pin_state then
        if pin_state.client and pin_state.client.valid then
            unpin(c)
            return
        end
        pin_state = nil
    end

    c = c or client.focus
    if not c or not c.valid then return end

    pin_state = {
        client = c,
        floating = c.floating,
        fullscreen = c.fullscreen,
        maximized = c.maximized,
    }

    c.fullscreen = false
    c.maximized = false
    c.floating = false
    c:emit_signal("request::activate", "max_pin_layout.pin", { raise = true })
    awful.layout.arrange(c.screen)
end

return M
