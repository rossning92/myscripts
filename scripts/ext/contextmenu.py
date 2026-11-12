import argparse

from utils.menu.contextmenu import ContextMenu

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("param", type=str)
    args = parser.parse_args()

    ContextMenu(param=args.param).exec()
