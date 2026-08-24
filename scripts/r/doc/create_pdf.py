"""Create a JPEG-compressed PDF from one or more images.

Settings are read from environment variables:
    PDF_DPI         Output resolution (default: 300)
    JPEG_QUALITY    JPEG quality from 1 to 95 (default: 50)
    OUTPUT_FILE     Destination PDF (default: first image with a .pdf suffix)
"""

import os
import sys
from pathlib import Path

from PIL import Image, ImageOps


def load_rgb_image(path: Path) -> Image.Image:
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source)
        image.load()

    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background

    return image.convert("RGB")


def create_pdf(image_paths: list[Path], output: Path, dpi: float, quality: int) -> None:
    pages = [load_rgb_image(path) for path in image_paths]
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        pages[0].save(
            output,
            "PDF",
            save_all=True,
            append_images=pages[1:],
            resolution=dpi,
            quality=quality,
            optimize=True,
        )
    finally:
        for page in pages:
            page.close()


def main() -> int:
    if len(sys.argv) < 2:
        print(f"Usage: run_script {Path(__file__)} IMAGE [IMAGE ...]", file=sys.stderr)
        return 2

    try:
        dpi = float(os.environ.get("PDF_DPI", 300))
        quality = int(os.environ.get("JPEG_QUALITY", 50))
    except ValueError as error:
        print(f"Error: PDF_DPI and JPEG_QUALITY must be numbers: {error}", file=sys.stderr)
        return 2

    if dpi <= 0 or not 1 <= quality <= 95:
        print("Error: PDF_DPI must be positive and JPEG_QUALITY must be 1-95", file=sys.stderr)
        return 2

    image_paths = [Path(value).expanduser() for value in sys.argv[1:]]
    for path in image_paths:
        if not path.is_file():
            print(f"Error: File not found: {path}", file=sys.stderr)
            return 2

    output = Path(
        os.environ.get("OUTPUT_FILE", image_paths[0].with_suffix(".pdf"))
    ).expanduser()
    if output.suffix.lower() != ".pdf":
        output = output.with_suffix(".pdf")

    try:
        create_pdf(image_paths, output, dpi, quality)
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Created: {output}")
    print(f"Pages: {len(image_paths)}, DPI: {dpi:g}, JPEG quality: {quality}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
