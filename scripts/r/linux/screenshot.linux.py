import subprocess
import tkinter as tk
from datetime import datetime
from pathlib import Path

from PIL import ImageGrab, ImageTk


def pick_region(image):
    window = tk.Tk()
    window.withdraw()
    window.title("Region Capture")
    window.overrideredirect(True)
    window.geometry(f"{image.width}x{image.height}+0+0")
    canvas = tk.Canvas(window, highlightthickness=0, cursor="crosshair")
    canvas.pack(fill="both", expand=True)
    background = ImageTk.PhotoImage(image)
    canvas.create_image(0, 0, anchor="nw", image=background)
    box = canvas.create_rectangle(0, 0, 0, 0, outline="#ff9800", width=2)
    start = None
    region = None

    def press(event):
        nonlocal start
        start = (event.x, event.y)
        canvas.coords(box, *start, *start)

    def drag(event):
        if start is not None:
            canvas.coords(box, *start, event.x, event.y)

    def release(event):
        nonlocal region
        if start is None:
            return
        left, right = sorted((start[0], event.x))
        top, bottom = sorted((start[1], event.y))
        left, top = max(0, left), max(0, top)
        right, bottom = min(image.width, right), min(image.height, bottom)
        if right > left and bottom > top:
            region = (left, top, right, bottom)
        window.quit()

    canvas.bind("<ButtonPress-1>", press)
    canvas.bind("<B1-Motion>", drag)
    canvas.bind("<ButtonRelease-1>", release)
    window.bind("<Escape>", lambda _: window.quit())
    canvas.bind("<ButtonPress-3>", lambda _: window.quit())
    try:
        window.deiconify()
        window.lift()
        window.update()
        canvas.focus_force()
        canvas.grab_set_global()
        window.mainloop()
    finally:
        window.destroy()
    return region


def main():
    image = ImageGrab.grab()
    region = pick_region(image)
    if region is None:
        return
    folder = Path.home() / "screenshots"
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / f"Screenshot-{datetime.now():%Y%m%d-%H%M%S-%f}.png"
    image.crop(region).save(destination)
    subprocess.run(
        ["xclip", "-selection", "clipboard"],
        input=str(destination), text=True, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


if __name__ == "__main__":
    main()
