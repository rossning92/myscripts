import argparse
import glob
import os

from _image import combine_images
from utils.shutil import shell_open


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value in (None, ""):
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def _env_number(name, convert, default=None):
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    try:
        return convert(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid {convert.__name__}") from exc


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
    parser.add_argument(
        "-o",
        "--out-file",
        help="Output path. Defaults to <input names>_combined.png beside the first image.",
    )
    parser.add_argument(
        "-s",
        "--scale",
        type=float,
        default=1.0,
        help="Scale each image by this factor before combining (e.g. 0.25).",
    )
    args = parser.parse_args()

    args.image_files = _expand_globs(args.image_files)

    if args.out_file is None:
        input_names = [
            os.path.splitext(os.path.basename(path))[0] for path in args.image_files
        ]
        args.out_file = os.path.join(
            os.path.dirname(args.image_files[0]),
            "_".join(input_names) + "_combined.png",
        )

    generate_gif = _env_bool("CI_GENERATE_GIF")

    combine_images(
        image_files=args.image_files,
        out_file=args.out_file,
        scale=args.scale,
        cols=_env_number("CI_NUM_COLS", int),
        col_major_order=_env_bool("CI_COLUMN_MAJOR_ORDER"),
        draw_label=_env_bool("CI_DRAW_LABEL"),
        label_align=os.environ.get("CI_LABEL_ALIGN") or "bottom",
        generate_gif=generate_gif,
        generate_vid=_env_bool("CI_GENERATE_VIDEO"),
        generate_atlas=True,
        gif_duration=_env_number("CI_GIF_DURATION", int, 500),
        font_scale=_env_number("CI_FONT_SCALE", float, 1.0),
        font_color=os.environ.get("CI_FONT_COLOR") or "white",
    )

    out_gif = os.path.splitext(args.out_file)[0] + ".gif"
    shell_open(os.path.abspath(out_gif if generate_gif else args.out_file))
