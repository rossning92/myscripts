import argparse
import glob
import os

from _image import combine_images
from utils.shutil import shell_open


def _expand_globs(patterns):
    files = []
    for pattern in patterns:
        matches = sorted(
            f for f in glob.glob(pattern, recursive=True) if os.path.isfile(f)
        )
        files.extend(matches or [pattern])
    return files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Combine multiple images into a single image (atlas/grid).",
        epilog=(
            "Examples:\n"
            "  combine_imgs.py a.png b.png c.png -o out.png\n"
            '  combine_imgs.py "shots/*.png" -o out.png        # wildcard (one folder)\n'
            '  combine_imgs.py "shots/**/screenshot.png" -o out.png  # recurse subfolders'
        ),
    )
    parser.add_argument(
        "image_files",
        nargs="+",
        help=(
            "Input images. Accepts explicit paths and/or glob patterns. "
            "Quote patterns so the script (not the shell) expands them; "
            "`*` matches within a folder and `**` recurses into subfolders."
        ),
    )
    parser.add_argument("-o", "--out-file", default="out/out.png")
    parser.add_argument(
        "-s",
        "--scale",
        type=float,
        default=1.0,
        help="Scale each image by this factor before combining (e.g. 0.25).",
    )
    args = parser.parse_args()

    args.image_files = _expand_globs(args.image_files)

    cols = int("{{_NUM_COLS}}") if "{{_NUM_COLS}}" else None
    col_major_order = True if "{{_COL_MAJOR_ORDER}}" else False
    draw_label = True if "{{_DRAW_LABEL}}" else False
    label_align = "{{_LABEL_ALIGN}}" if "{{_LABEL_ALIGN}}" else "bottom"
    gif_duration = int("{{_GIF_DURA}}") if "{{_GIF_DURA}}" else 500
    font_scale = float("{{_FONT_SCALE}}") if "{{_FONT_SCALE}}" else 1.0
    font_color = "{{_FONT_COLOR}}" if "{{_FONT_COLOR}}" else "white"

    combine_images(
        image_files=args.image_files,
        out_file=args.out_file,
        scale=args.scale,
        cols=cols,
        col_major_order=col_major_order,
        draw_label=draw_label,
        label_align=label_align,
        generate_gif=True if "{{_GEN_GIF}}" else False,
        generate_vid=True if "{{_GEN_VID}}" else False,
        generate_atlas=True if "{{_GEN_ATLAS}}" else False,
        gif_duration=gif_duration,
        font_scale=font_scale,
        font_color=font_color,
    )

    out_gif = os.path.splitext(args.out_file)[0] + ".gif"
    shell_open(os.path.abspath(out_gif if "{{_GEN_GIF}}" else args.out_file))
