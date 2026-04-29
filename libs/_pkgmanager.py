import glob
import logging
import os
import shutil
import subprocess
import sys
from functools import lru_cache
from typing import Dict, List, Literal, Optional

from _shutil import (
    check_output,
    get_home_path,
    prepend_to_path,
    refresh_env_vars,
    run_elevated,
)
from utils import wingetutils
from utils.jsonutil import load_json
from utils.termux import is_in_termux

_cached_packages = None
_cached_mtime = None


def _call_without_output(args) -> bool:
    return (
        subprocess.call(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        == 0
    )


def get_packages():
    global _cached_packages
    global _cached_mtime

    file_path = os.path.abspath(
        os.path.dirname(os.path.abspath(__file__)) + "/../settings/packages.json"
    )
    mtime = os.path.getmtime(file_path)
    if _cached_packages is None or _cached_mtime != mtime:
        _cached_packages = load_json(file_path)
        _cached_mtime = mtime

    return _cached_packages


def find_executable(pkg, install=False):
    # If pkg is an executable and exists
    exe_path = shutil.which(pkg)
    if exe_path:
        return exe_path

    packages = get_packages()
    executables = []
    if pkg in packages:
        if "executables" in packages[pkg]:
            executables = packages[pkg]["executables"]

    for executable in executables:
        executable = os.path.expandvars(executable)
        match = list(glob.glob(executable))
        if len(match) > 0:
            return match[0]

        exe_path = shutil.which(executable)
        if exe_path:
            return exe_path

    if install and executables is None:
        require_package(pkg)
        return find_executable(pkg)

    return None


def get_all_available_packages() -> List[str]:
    packages = get_packages()
    return [name for name in packages.keys()]


def has_executable(executables: List[str]) -> bool:
    for executable in executables:
        if shutil.which(executable):
            return True
    return False


def require_package(
    pkg: str,
    wsl=False,
    env: Optional[Dict[str, str]] = None,
    force_install=False,
    upgrade=False,
    win_package_manager: List[Literal["choco", "winget"]] = ["winget", "choco"],
):
    wsl = wsl and sys.platform == "win32"
    packages = get_packages()

    if "dependantPackages" in packages:
        for pkg in packages["dependantPackages"]:
            require_package(pkg)

    package_matched = False
    if pkg in packages:
        # Whether or not a package has just been installed.
        newly_installed = False
        if "executables" in packages[pkg] and has_executable(
            packages[pkg]["executables"]
        ):
            package_matched = True

        elif "golang" in packages[pkg]:
            require_package("golang")
            if "packagePath" in packages[pkg]["golang"]:
                go_pkg_path = packages[pkg]["golang"]["packagePath"]
                if not _is_go_package_installed(go_pkg_path) or force_install:
                    logging.info(f"Installing go package: {go_pkg_path}...")
                    subprocess.check_call(["go", "install", go_pkg_path])
                    newly_installed = True
                package_matched = True

        elif "npm" in packages[pkg]:
            require_package("npm")
            for p in packages[pkg]["npm"]["packages"]:
                if not is_npm_global_package_installed(p) or force_install:
                    logging.info(f"Installing package using npm: {p}")
                    subprocess.check_call(
                        (["sudo"] if sys.platform == "linux" else [])
                        + ["npm", "install", "-g", p],
                        # On Windows, `npm` command is a batch script and needs to be executed in a shell.
                        shell=sys.platform == "win32",
                    )
                    newly_installed = True
            package_matched = True

        elif "yarn" in packages[pkg]:
            require_package("node")
            require_package("yarn")
            for p in packages[pkg]["yarn"]["packages"]:
                logging.info(f"Installing package using npm: {p}")
                subprocess.check_call(
                    ["yarn", "global", "add", p],
                    # On Windows, `yarn` command is a batch script and needs to be executed in a shell.
                    shell=sys.platform == "win32",
                )
                yarn_global_bin_path = subprocess.check_output(
                    ["yarn", "global", "bin"],
                    universal_newlines=True,
                    shell=sys.platform == "win32",
                ).strip()
                prepend_to_path(
                    yarn_global_bin_path,
                    env=env,
                )
                newly_installed = True
            package_matched = True

        elif is_in_termux() and "termux" in packages[pkg]:
            for p in packages[pkg]["termux"]["packages"]:
                if not _call_without_output(["dpkg", "-s", p]) or force_install:
                    logging.warning(f'Package "{p}" was not found, installing...')
                    subprocess.check_call(["pkg", "install", p, "-y"])
                    newly_installed = True
            package_matched = True

        elif "apt" in packages[pkg] and (shutil.which("apt") or wsl):
            wsl_cmd = ["wsl"] if wsl else []
            for p in packages[pkg]["apt"]["packages"]:
                if (
                    not _call_without_output(wsl_cmd + ["dpkg", "-s", p])
                    or force_install
                ):
                    if "ppa" in packages[pkg]["apt"]:
                        ppa = packages[pkg]["apt"]["ppa"]
                        assert isinstance(ppa, str)
                        subprocess.check_call(
                            wsl_cmd + ["sudo", "add-apt-repository", f"ppa:{ppa}", "-y"]
                        )
                        subprocess.check_call(wsl_cmd + ["sudo", "apt-get", "update"])

                    logging.info(f"Installing package using apt: {pkg}...")
                    subprocess.check_call(wsl_cmd + ["sudo", "apt", "install", "-y", p])
                    newly_installed = True
            package_matched = True

        elif (
            sys.platform == "linux"
            and "pacman" in packages[pkg]
            and shutil.which("pacman")
        ):
            for p in packages[pkg]["pacman"]["packages"]:
                if not _call_without_output(["pacman", "-Q", p]) or force_install:
                    logging.info(f"Installing package using pacman: {p}")
                    subprocess.check_call(["sudo", "pacman", "-S", "--noconfirm", p])
                    newly_installed = True
            package_matched = True

        elif "brew" in packages[pkg] and shutil.which("brew"):
            for p in packages[pkg]["pacman"]["packages"]:
                if not _call_without_output(["brew", "list", p]) or force_install:
                    logging.info(f"Installing package using pacman: {p}")
                    subprocess.check_call(["brew", "install", p])
                    newly_installed = True
            package_matched = True

        elif "dnf" in packages[pkg] and shutil.which("dnf"):
            for p in packages[pkg]["dnf"]["packages"]:
                if (
                    not _call_without_output(["dnf", "list", "installed", p])
                    or force_install
                ):
                    logging.info(f"Installing package using dnf: {p}")
                    subprocess.check_call(["sudo", "dnf", "install", "-y", p])
                    newly_installed = True
            package_matched = True

        elif "yay" in packages[pkg] and shutil.which("pacman"):
            yay_packages = packages[pkg]["yay"]["packages"]
            for p in yay_packages:
                if not _call_without_output(["yay", "-Q", p]) or force_install:
                    logging.info(f"Installing package using yay: {p}")
                    subprocess.check_call(["yay", "-S", "--noconfirm", "--rebuild", p])
                    newly_installed = True
            package_matched = True

        elif "dotnet" in packages[pkg]:
            for p in packages[pkg]["dotnet"]["packages"]:
                if (
                    not _call_without_output(["dotnet", "tool", "list", "--global", p])
                    or force_install
                ):
                    logging.info(f"Installing dotnet package package: {p}...")
                    subprocess.check_call(["dotnet", "tool", "install", "--global", p])
                    newly_installed = True
            if sys.platform == "win32":
                prepend_to_path(
                    os.path.expandvars("%USERPROFILE%\\.dotnet\\tools"), env=env
                )
            else:
                prepend_to_path(os.path.expandvars("$HOME/.dotnet/tools"), env=env)
            package_matched = True

        elif "pip" in packages[pkg]:
            for p in packages[pkg]["pip"]["packages"]:
                # Check if pip package is installed
                if (
                    not _call_without_output([sys.executable, "-m", "pip", "show", p])
                    or force_install
                ):
                    logging.info(f"Installing pip package: {p}...")
                    subprocess.check_call(
                        [sys.executable, "-m", "pip", "install", "--upgrade", p]
                    )
                    newly_installed = True
            package_matched = True

        elif sys.platform == "win32" and not wsl:
            for pm in win_package_manager:
                if pm == "choco" and "choco" in packages[pkg]:
                    _choco_install(pkg, force_install=force_install, upgrade=upgrade)
                    package_matched = True
                    break
                elif pm == "winget" and "winget" in packages[pkg]:
                    for p in packages[pkg]["winget"]["packages"]:
                        if not wingetutils.is_package_installed(p) or force_install:
                            wingetutils.install_package(p, upgrade=upgrade)
                        newly_installed = True
                        break
                    package_matched = True
                    break

        if newly_installed and "post_install" in packages[pkg]:
            post_install = packages[pkg]["post_install"]
            for cmd in post_install:
                subprocess.check_call(cmd, shell=True)

        if sys.platform == "linux" and "flatpak" in packages[pkg]:
            _flatpak_install(pkg, force_install=force_install, upgrade=upgrade)
            package_matched = True

    if not package_matched:
        raise Exception(f"{pkg} is not found")


@lru_cache(maxsize=None)
def is_npm_global_package_installed(p):
    return (
        subprocess.call(
            ["npm", "list", "-g", p],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            shell=sys.platform == "win32",
            creationflags=(
                subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
            ),  # prevent title change
        )
        == 0
    )


def install_package(pkg, wsl=False):
    logging.info(f"Install package: {pkg}")
    require_package(pkg, wsl=wsl)


def _is_go_package_installed(go_pkg_path):
    executable_path = go_pkg_path.split("/")[-1].split("@")[0]
    if sys.platform == "win32":
        executable_path += ".exe"

    return os.path.exists(
        os.path.join(
            get_home_path(),
            "go",
            "bin",
            executable_path,
        )
    )


def _choco_is_package_installed(pkg: str) -> bool:
    logging.debug(f"Checking if choco package {pkg} is installed")
    use_builtin_choco_command = False
    if use_builtin_choco_command:
        # Note that the "--localonly" option has been removed in Chocolatey 2.0 and higher.
        out = check_output(["choco", "list", "--exact", "--localonly", pkg])
        return "0 packages installed" not in out
    else:
        path = shutil.which("choco")
        if path:
            lib_path = os.path.abspath(os.path.dirname(path) + f"\\..\\lib\\{pkg}")
            return os.path.exists(lib_path)
        else:
            raise Exception("choco is not installed.")


def _choco_install(pkg, upgrade=False, force_install=True):
    packages = get_packages()
    for p in packages[pkg]["choco"]["packages"]:
        if not _choco_is_package_installed(p) or force_install:
            logging.info("Install `%s`..." % p)
            args = ["choco", "install", p, "-y", "-s", "https://chocolatey.org/api/v2/"]
            if force_install:
                args.append("-f")
            run_elevated(args)

        elif upgrade or force_install:
            logging.info("Upgrade `%s`..." % p)
            args = ["choco", "upgrade", p, "-y", "-s", "https://chocolatey.org/api/v2/"]
            if force_install:
                args.append("-f")
            run_elevated(args)

        else:
            logging.debug(f"Package {p} already exists, skip installation.")

    refresh_env_vars()


def _flatpak_is_package_installed(pkg: str):
    logging.debug(f"Checking if flatpak package {pkg} is installed")
    return _call_without_output(["flatpak", "info", pkg])


def _flatpak_install(pkg: str, upgrade=False, force_install=True):
    require_package("flatpak")
    packages = get_packages()
    for p in packages[pkg]["flatpak"]["packages"]:
        is_installed = _flatpak_is_package_installed(p)
        if not is_installed or upgrade or force_install:
            if upgrade and is_installed:
                logging.info(f"Upgrading flatpak package: {p}...")
            elif is_installed and force_install:
                logging.info(f"Reinstalling flatpak package: {p}...")
            else:
                logging.info(f"Installing flatpak package: {p}...")

            args = ["flatpak", "install", "-y"]
            if upgrade:
                args.append("--or-update")
            elif force_install and is_installed:
                args.append("--reinstall")
            args.append(p)
            subprocess.check_call(args)
