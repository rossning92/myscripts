#!/usr/bin/env python3

import argparse
import datetime
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Combine PDF files in the order they are provided."
    )
    parser.add_argument(
        "files",
        nargs="+",
        type=Path,
        metavar="PDF",
        help="input PDF files, in output page order",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output path (default: combined_YYYYMMDD_HHMMSS.pdf)",
    )
    return parser.parse_args()


def combine_pdfs(files: list[Path], output: Path) -> None:
    subprocess.run(
        ["pdftk", *(str(file) for file in files), "cat", "output", str(output)],
        check=True,
    )


def main() -> int:
    args = parse_args()
    output = args.output or Path(
        f"combined_{datetime.datetime.now():%Y%m%d_%H%M%S}.pdf"
    )

    try:
        combine_pdfs(args.files, output)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Input files (in page order):")
    for file in args.files:
        print(f" - {file}")
    print(f"Output: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
