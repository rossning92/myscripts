import subprocess
import sys

from PIL import Image

# Open an idle right pane, then draw into its terminal directly.
pane = subprocess.check_output(["run_script", "ext/open_side_pane.sh", "read"], text=True).strip()
tty, cols, rows = subprocess.check_output(
    ["tmux", "display", "-p", "-t", pane, "#{pane_tty} #{pane_width} #{pane_height}"], text=True
).split()
img = Image.open(sys.argv[1]).convert("RGB")
# Each text cell shows two pixels (upper half block fg + bg), so double the rows.
img.thumbnail((int(cols), (int(rows) - 1) * 2))
w, h = img.size
px = img.load()
with open(tty, "w") as f:
    for y in range(0, h, 2):
        for x in range(w):
            t = px[x, y]
            b = px[x, y + 1] if y + 1 < h else (0, 0, 0)
            f.write(f"\033[38;2;{t[0]};{t[1]};{t[2]}m\033[48;2;{b[0]};{b[1]};{b[2]}m▀")
        f.write("\033[0m\n")
