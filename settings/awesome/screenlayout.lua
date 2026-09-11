local M = {}

local USABLE_ASPECT_RATIO = 16 / 9

-- Resize Awesome's screen object to the leftmost 16:9 portion of an
-- ultrawide display. The remaining physical pixels stay unmanaged.
function M.apply_usable_region(s)
    if screen.count() ~= 1 then return end

    s = s or screen[1]
    if not s then return end

    local geometry = s.geometry
    local target_width = math.floor(geometry.height * USABLE_ASPECT_RATIO + 0.5)
    if geometry.width > target_width then
        s:fake_resize(geometry.x, geometry.y, target_width, geometry.height)
    end
end

return M
