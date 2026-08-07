import os
import shutil
import subprocess
import sys
from typing import Optional

from _pkgmanager import find_executable, require_package


def unzip(src, dest=None):
    extracted = False
    for file in src:
        gzip_extension = [".tar.gz", ".tgz", ".gz"]
        for ext in gzip_extension:
            if file.endswith(ext):
                if dest:
                    out_dir = dest
                else:
                    out_dir = file.rstrip(ext)
                    os.mkdir(out_dir)
                subprocess.check_call(["tar", "xzvf", file, "-C", out_dir])
                extracted = True
                break

        if not extracted:
            if dest:
                out_dir = dest
            else:
                out_dir = os.path.splitext(file)[0]

            if sys.platform == "win32":
                require_package("7z")
                _7z = find_executable("7z")
                args = [
                    _7z,
                    "x",  # extract
                    "-aoa",  # overwrite all existing files
                    "-o" + out_dir,  # out folder
                    file,
                ]
                subprocess.check_call(args)
            else:
                import zipfile

                with zipfile.ZipFile(file, "r") as zip_ref:
                    zip_ref.extractall(out_dir)

    return out_dir


def create_zip_file(path: str, out_file: Optional[str]):
    if out_file is None:
        out_file = path + ".zip"
    shutil.make_archive(out_file.rstrip(".zip"), "zip", path)
