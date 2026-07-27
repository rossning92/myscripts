import argparse

from _pkgmanager import get_all_available_packages, require_package
from utils.menu import Menu

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=str, nargs="?", default=None)
    parser.add_argument("-f", "--force", action="store_true")
    parser.add_argument("--winget", action="store_true", default=True)
    args = parser.parse_args()

    pkg = args.package
    force_install = args.force
    upgrade = False

    if not pkg:
        # Show all available packages in a menu.
        packages = get_all_available_packages()
        i = Menu(items=packages).exec()
        if i >= 0:
            pkg = packages[i]
            force_install = True
            upgrade = True

    if pkg:
        require_package(
            pkg=pkg,
            force_install=force_install,
            upgrade=upgrade,
            win_package_manager=["winget" if args.winget else "choco"],
        )
