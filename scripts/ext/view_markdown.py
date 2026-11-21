"""View a text or Markdown file in TextMenu."""

import argparse
from pathlib import Path

from utils.menu.textmenu import TextMenu


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", help="Text or Markdown file to open")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--markdown", dest="markdown", action="store_true")
    mode.add_argument("--plain", dest="markdown", action="store_false")
    parser.set_defaults(markdown=True)
    args = parser.parse_args()

    TextMenu(
        file=args.file,
        markdown=args.markdown,
        line_number=not args.markdown,
        prompt=Path(args.file).name,
    ).exec()
