import glob
import math
import os
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def crop_image_file(file_name, rect=None, rect_normalized=None):
    im = Image.open(file_name)
    im = crop_image(im, rect, rect_normalized)
    im.save(file_name)


def load_im(file):
    im = Image.open(file)
    return np.array(im)


def to_pil_image(im):
    from PIL import Image

    if type(im) != Image.Image:
        im = Image.fromarray(im)
    return im


def save_im(im, f):
    im = to_pil_image(im)
    im.save(f)


def crop_image(im, rect=None, rect_normalized=None):
    import numpy as np

    if type(im) == np.ndarray:
        h, w = im.shape[0:2]
    else:
        w, h = im.width, im.height

    if rect_normalized:
        rect = [
            rect_normalized[0] * w,
            rect_normalized[1] * h,
            rect_normalized[2] * w,
            rect_normalized[3] * h,
        ]
        rect = [int(x) for x in rect]

    if type(im) == np.ndarray:
        im = im[rect[1] : rect[1] + rect[3], rect[0] : rect[0] + rect[2]]
    else:
        im = im.crop((rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3]))

    return im


def crop_image_interactive(file: str):
    rect = None
    im = Image.open(file)

    out_dir = os.path.join(os.path.dirname(file), "out")
    os.makedirs(out_dir, exist_ok=True)

    rect = select_roi(file)
    if rect is None:
        return

    im = crop_image(im, rect=rect)

    im.save(file, quality=90)


def scale_image(im, sx, sy):
    if type(im) == str:
        f = im
        im = Image.open(f)
    else:
        f = None

    im = im.resize((int(sx * im.size[0]), int(sy * im.size[1])), Image.LANCZOS)

    if f is not None:
        im.save(f)
        return f
    else:
        return im


def resize_image(im, w, h):
    if type(im) == str:
        f = im
        im = Image.open(f)
    else:
        f = None

    im = im.resize((w, h), Image.LANCZOS)

    if f is not None:
        im.save(f)
        return f
    else:
        return im


def show_im(
    *imgs,
    format="rgb",
    out_image_name=None,
    origin="upper",
    text=None,
    norm=False,
    split_channels=False
):
    import matplotlib.pyplot as plt
    import numpy as np

    if split_channels:
        imgs = [imgs[0][:, :, i] for i in range(imgs[0].shape[-1])]
        print(imgs)

    # plt.style.use("dark_background")

    fig = plt.figure(figsize=(len(imgs) * 4, 1 * 4))
    for i, im in enumerate(imgs):
        if not isinstance(im, (np.ndarray)):
            im = np.array(im)
        if len(im.shape) == 3 and im.shape[2] == 3 and format == "bgr":
            im = im[..., ::-1]

        # Visualize two channel image (e.g. optical flow, vector)
        if len(im.shape) == 3 and im.shape[2] == 2:
            import cv2

            hsv = np.zeros([im.shape[0], im.shape[1], 3])
            hsv[..., 1] = 255
            mag, ang = cv2.cartToPolar(im[..., 0], im[..., 1])
            hsv[..., 0] = ang * 180 / np.pi / 2
            hsv[..., 2] = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
            hsv = hsv.astype(np.uint8)
            im = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

        ax = fig.add_subplot(1, len(imgs), i + 1)

        if text:
            ax.title.set_text(text[i])

        # if norm:
        #     im = np.mean(im.astype(float), axis=2)

        plt.imshow(im, origin=origin)

    plt.tight_layout()

    if out_image_name:
        plt.savefig(out_image_name, dpi=200)
    else:
        plt.show()

    plt.close(fig)


def _get_text_margin(height, font_scale):
    return int(height / 16 * font_scale * 2.0)


def draw_text(
    im, text, text_outline=2, font_color="white", align="center", font_scale=1.0
):
    box = (0, 0, im.width, im.height)
    PADDING = 4

    draw = ImageDraw.Draw(im)
    font = ImageFont.truetype("arial.ttf", int(box[3] / 16 * font_scale))
    _, _, w, h = draw.multiline_textbbox((0, 0), text, font=font)

    if align == "top":
        x = box[0] + (box[2] - w) / 2
        y = box[1] + PADDING
    elif align == "topLeft":
        x = box[0] + PADDING
        y = box[1] + PADDING
    elif align == "bottom":
        x = box[0] + (box[2] - w) / 2
        y = box[1] + box[3] - h * 1.2
    else:  # center
        x = box[0] + (box[2] - w) / 2
        y = box[1] + (box[3] - h) / 2

    t = text_outline
    for dx, dy in [[0, t], [t, 0], [-t, 0], [0, -t]]:
        draw.multiline_text(
            (x + dx, y + dy), text, font=font, fill="black", align="center"
        )
    draw.multiline_text((x, y), text, font=font, fill=font_color, align="center")

    del draw


def _add_margin(im, top=0, right=0, bottom=0, left=0, color="black"):
    width, height = im.size
    new_width = width + right + left
    new_height = height + top + bottom
    result = Image.new(im.mode, (new_width, new_height), color)
    result.paste(im, (left, top))
    return result


def _labels_from_files(file_list, parse_file_name=None):
    names = [os.path.splitext(os.path.basename(f))[0] for f in file_list]
    if parse_file_name is not None:
        return [parse_file_name(n) for n in names]
    if len(set(names)) < len(names):
        names = [
            os.path.basename(os.path.dirname(f)) + "/" + n
            for f, n in zip(file_list, names)
        ]
    return [n.replace("_", " ") for n in names]


def combine_images(
    image_files=None,
    images=None,
    out_file=None,
    parse_file_name=None,
    cols=4,
    spacing=0.01,
    scale=1.0,
    text_outline=2,
    gif_duration=500,
    generate_atlas=False,
    generate_gif=False,
    generate_vid=False,
    draw_label=True,
    labels=None,
    label_align="top",
    title=None,
    title_align="top",
    title_color="white",
    font_color="white",
    col_major_order=False,
    font_scale=1.0,
):
    file_list = None
    if image_files:
        if type(image_files) == list:
            file_list = image_files
        else:
            file_list = glob.glob(image_files)
            file_list = [x for x in file_list if os.path.isfile(x)]

        if len(file_list) == 0:
            raise Exception("No image files has been found: %s" % image_files)

        imgs = [Image.open(f) for f in file_list]
        if scale != 1.0:
            print("Scaling image by %g" % scale)
            imgs = [
                im.resize(
                    (int(im.width * scale), int(im.height * scale)), Image.LANCZOS
                )
                for im in imgs
            ]

    elif images:
        # Convert to PIL image
        imgs = [Image.fromarray(x, "RGB") for x in images]

    else:
        raise Exception("`image_files` and `images` cannot be None at the same time.")

    # Add margins
    if draw_label and label_align == "bottom":
        imgs = [
            _add_margin(im, bottom=_get_text_margin(im.height, font_scale))
            for im in imgs
        ]

    if not cols:
        cols = 1

    # Adjust column size if it's smaller than the number of files
    if len(imgs) < cols:
        cols = len(imgs)

    # Add text
    if draw_label:
        if labels is None and file_list is not None:
            labels = _labels_from_files(file_list, parse_file_name)

        if labels is None:
            draw_label = False
        else:
            for im, text in zip(imgs, labels):
                draw_text(
                    im,
                    text,
                    text_outline,
                    font_color,
                    align=label_align,
                    font_scale=font_scale,
                )

    if generate_atlas:
        width = max([im.width for im in imgs])
        height = max([im.height for im in imgs])

        # Convert spacing from percentage to pixels
        spacing = int(spacing * width)

        num_imgs = len(imgs)
        rows = int(math.ceil(num_imgs / cols))
        if col_major_order:  # Swap rows and cols
            t = rows
            rows = cols
            cols = t

        im_combined = Image.new(
            "RGB",
            (
                width * cols + spacing * (cols - 1),
                height * rows + spacing * (rows - 1),
            ),
            "black",
        )

        for c in range(len(imgs)):
            if not col_major_order:
                i = c // cols
                j = c % cols
            else:
                j = c // rows
                i = c % rows

            x = j * width + j * spacing
            y = i * height + i * spacing
            im_combined.paste(imgs[c], (x, y))
            c += 1

        if title is not None:
            if title_align == "bottom":
                im_combined = _add_margin(
                    im_combined,
                    bottom=_get_text_margin(im_combined.height, font_scale),
                    color="black",
                )
            draw_text(
                im_combined,
                title,
                text_outline,
                title_color,
                align=title_align,
                font_scale=font_scale,
            )

    if out_file:
        out_file = os.path.splitext(out_file)[0]  # Remove file extension
        dir_name = os.path.dirname(out_file)
        if dir_name:
            os.makedirs(os.path.dirname(out_file), exist_ok=True)

        if generate_atlas:
            im_combined.save(out_file + ".png")

        if generate_gif:
            imgs[0].save(
                out_file + ".gif",
                save_all=True,
                append_images=imgs[1:],
                duration=gif_duration,
                quality=100,
                loop=0,
            )  # Repeat forever

        if generate_vid:
            from _video import make_video

            imgs = [np.array(x.convert("RGB")) for x in imgs]
            make_video(
                imgs,
                fps=1000 / gif_duration,
                out_file=out_file + ".mp4",
                format="rgb24",
            )

    if generate_atlas:
        return np.array(im_combined)
    else:
        return None


def parse_file_name(s):
    gain_x = re.findall("GainX\((.*?)\)", s)[0].replace(".00", "")
    gain_y = re.findall("GainY\((.*?)\)", s)[0].replace(".00", "")
    s = "GainX: %s\nGainY: %s" % (gain_x, gain_y)
    return s


def select_roi2(image_file):
    import cv2

    im = cv2.imread(image_file)

    # Select ROI
    cv2.namedWindow("Select ROI", cv2.WINDOW_KEEPRATIO)
    box = cv2.selectROI("Select ROI", im, True, False)
    cv2.destroyAllWindows()

    return box


def to_ndarray(im):
    if type(im) == str:
        im = Image.open(im)

    if not isinstance(im, (np.ndarray)):
        im = np.array(im)
    return im


def select_roi(im):
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.backend_bases import MouseButton
    from matplotlib.widgets import RectangleSelector

    im = to_ndarray(im)

    roi = None

    def line_select_callback(eclick, erelease):
        x1, y1 = eclick.xdata, eclick.ydata
        x2, y2 = erelease.xdata, erelease.ydata

        nonlocal roi
        roi = [min(x1, x2), min(y1, y2), np.abs(x1 - x2), np.abs(y1 - y2)]
        roi = [int(round(x)) for x in roi]

    _, ax = plt.subplots()
    __ = RectangleSelector(
        ax,
        line_select_callback,
        useblit=False,
        button=[MouseButton.LEFT],
        minspanx=5,
        minspany=5,
        spancoords="pixels",
        interactive=True,
    )

    plt.imshow(im, origin="upper")

    manager = plt.get_current_fig_manager()
    manager.window.showMaximized()

    plt.connect(
        "key_press_event",
        lambda event: plt.close() if event.key in ["enter", "escape"] else None,
    )

    plt.show()

    return roi


def screenshot_image():
    import numpy as np
    from mss import mss
    from PIL import Image

    with mss() as sct:
        sct_img = sct.grab(sct.monitors[1])
        im = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

    return np.array(im)
