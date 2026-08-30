"""Render every page of one or more PDF files as a JPEG image.

Each image is written beside its PDF using the PDF name and page number. For
example, ``document.pdf`` produces ``document_01.jpg``, ``document_02.jpg``,
etc.

Set P2I_DPI to change the rendering resolution (default: 300).
Set P2I_JPEG_QUALITY to change JPEG quality (default: 85).
"""

import os
import sys
from pathlib import Path

import pymupdf


def convert_pdf(pdf_path: Path, dpi: int, jpeg_quality: int) -> int:
    with pymupdf.open(pdf_path) as document:
        if document.needs_pass:
            raise ValueError("PDF is password-protected")

        digits = max(2, len(str(document.page_count)))
        for page_number, page in enumerate(document, start=1):
            image_path = pdf_path.with_name(
                f"{pdf_path.stem}_{page_number:0{digits}d}.jpg"
            )
            page.get_pixmap(dpi=dpi, alpha=False).save(
                image_path, jpg_quality=jpeg_quality
            )

        return document.page_count


def main() -> int:
    if len(sys.argv) < 2:
        print(
            f"Usage: run_script {Path(__file__)} PDF [PDF ...]",
            file=sys.stderr,
        )
        return 2

    try:
        dpi = int(os.environ.get("P2I_DPI", 300))
        jpeg_quality = int(os.environ.get("P2I_JPEG_QUALITY", 85))
    except ValueError:
        print(
            "Error: P2I_DPI and P2I_JPEG_QUALITY must be integers",
            file=sys.stderr,
        )
        return 2

    if dpi <= 0 or not 1 <= jpeg_quality <= 100:
        print(
            "Error: P2I_DPI must be positive and "
            "P2I_JPEG_QUALITY must be 1-100",
            file=sys.stderr,
        )
        return 2

    pdf_paths = [Path(value).expanduser().resolve() for value in sys.argv[1:]]
    for path in pdf_paths:
        if not path.is_file():
            print(f"Error: File not found: {path}", file=sys.stderr)
            return 2
        if path.suffix.lower() != ".pdf":
            print(f"Error: Not a PDF file: {path}", file=sys.stderr)
            return 2

    failed = False
    for path in pdf_paths:
        try:
            page_count = convert_pdf(path, dpi, jpeg_quality)
        except (OSError, RuntimeError, ValueError) as error:
            print(f"Error converting {path}: {error}", file=sys.stderr)
            failed = True
            continue

        print(f"Created {page_count} image(s) beside: {path}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
