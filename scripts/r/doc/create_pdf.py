"""Create a JPEG-compressed PDF from one or more images.

Settings are read from environment variables:
    CREATE_PDF_DPI              Output resolution (default: 300)
    CREATE_PDF_JPEG_QUALITY     JPEG quality from 1 to 95 (default: 50)
    CREATE_PDF_OUTPUT_FILE      Destination PDF (default: first image with a
                                .pdf suffix)
    CREATE_PDF_BLACK_AND_WHITE  Convert images to 1-bit black and white when
                                non-empty
"""

import os
import sys
from pathlib import Path

from PIL import Image, ImageOps


def load_image(path: Path, black_and_white: bool = False) -> Image.Image:
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source)
        image.load()

    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        image = background
    else:
        image = image.convert("RGB")

    if black_and_white:
        grayscale = ImageOps.grayscale(image)
        return grayscale.point(lambda value: 255 if value >= 128 else 0, "1")
    return image


def create_pdf(
    image_paths: list[Path],
    output: Path,
    dpi: float,
    quality: int,
    black_and_white: bool = False,
) -> None:
    pages = [load_image(path, black_and_white) for path in image_paths]
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        save_options = {
            "save_all": True,
            "append_images": pages[1:],
            "resolution": dpi,
            "optimize": True,
        }
        if not black_and_white:
            save_options["quality"] = quality
        pages[0].save(output, "PDF", **save_options)
    finally:
        for page in pages:
            page.close()


def main() -> int:
    if len(sys.argv) < 2:
        print(f"Usage: run_script {Path(__file__)} IMAGE [IMAGE ...]", file=sys.stderr)
        return 2

    try:
        dpi = float(os.environ.get("CREATE_PDF_DPI", 300))
        quality = int(os.environ.get("CREATE_PDF_JPEG_QUALITY", 50))
    except ValueError as error:
        print(
            "Error: CREATE_PDF_DPI and CREATE_PDF_JPEG_QUALITY must be "
            f"numbers: {error}",
            file=sys.stderr,
        )
        return 2

    if dpi <= 0 or not 1 <= quality <= 95:
        print(
            "Error: CREATE_PDF_DPI must be positive and "
            "CREATE_PDF_JPEG_QUALITY must be 1-95",
            file=sys.stderr,
        )
        return 2

    image_paths = [Path(value).expanduser() for value in sys.argv[1:]]
    for path in image_paths:
        if not path.is_file():
            print(f"Error: File not found: {path}", file=sys.stderr)
            return 2

    output = Path(
        os.environ.get(
            "CREATE_PDF_OUTPUT_FILE", image_paths[0].with_suffix(".pdf")
        )
    ).expanduser()
    if output.suffix.lower() != ".pdf":
        output = output.with_suffix(".pdf")

    black_and_white = bool(os.environ.get("CREATE_PDF_BLACK_AND_WHITE"))

    try:
        create_pdf(image_paths, output, dpi, quality, black_and_white)
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Created: {output}")
    if black_and_white:
        print(
            f"Pages: {len(image_paths)}, DPI: {dpi:g}, "
            "black and white: yes, compression: CCITT Group 4"
        )
    else:
        print(
            f"Pages: {len(image_paths)}, DPI: {dpi:g}, "
            f"JPEG quality: {quality}, black and white: no"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
