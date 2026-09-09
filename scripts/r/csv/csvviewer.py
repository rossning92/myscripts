import argparse

from utils.menu.csvmenu import CsvMenu


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=str)
    args = parser.parse_args()

    csv_file = args.file
    CsvMenu(csv_file=csv_file).exec()


if __name__ == "__main__":
    main()
