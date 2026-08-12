import os
import shutil
import subprocess
from typing import Optional

from _pkgmanager import find_executable, require_package


def unzip(src, dest=None):
    require_package("7z")
    seven_zip = find_executable("7z")
    if seven_zip is None:
        raise FileNotFoundError("7-Zip executable not found")

    for file in src:
        if dest:
            out_dir = dest
        else:
            out_dir = os.path.splitext(file)[0]

        subprocess.check_call(
            [
                seven_zip,
                "x",  # extract with full paths
                "-aoa",  # overwrite all existing files
                "-o" + out_dir,
                file,
            ]
        )

    return out_dir


def create_zip_file(path: str, out_file: Optional[str]):
    if out_file is None:
        out_file = path + ".zip"
    shutil.make_archive(out_file.rstrip(".zip"), "zip", path)
