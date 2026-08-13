import os
import re
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Union

from utils.termux import is_in_termux


def prepare_termux_proot(
    config: Dict[str, Union[str, bool, None]],
) -> Optional[str]:
    if not is_in_termux():
        return None

    # proot-distro refuses to start from inside another PRoot. This can happen
    # when a script configured with "termux.proot" calls run_script again.
    try:
        process_root = os.readlink("/proc/self/root")
    except OSError:
        process_root = ""
    if re.search(
        r"/com\.termux/files/usr/var/lib/proot-distro/containers/[^/]+/rootfs/?$",
        process_root,
    ):
        return None

    proot = config["termux.proot"]
    if isinstance(proot, bool):
        distro = "debian" if proot else None
    elif isinstance(proot, str):
        proot = proot.strip()
        if not proot:
            distro = None
        elif proot.lower() in ("1", "true", "yes"):
            distro = "debian"
        elif proot.lower() in ("0", "false", "no"):
            distro = None
        else:
            distro = proot
    else:
        distro = None

    if distro is None:
        return None

    if not shutil.which("proot-distro"):
        subprocess.check_call(["pkg", "install", "-y", "proot-distro"])

    prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
    container_dir = os.path.join(
        prefix, "var", "lib", "proot-distro", "containers", distro
    )
    if os.path.isdir(container_dir):
        return distro

    subprocess.check_call(["proot-distro", "install", distro])
    return distro


def wrap_proot(
    commands: List[str],
    env: Optional[Dict[str, str]],
    distro: str = "debian",
    cwd: Optional[str] = None,
) -> List[str]:
    if sys.platform != "android":
        raise RuntimeError("PRoot script config is only supported on Termux/Android")
    if not shutil.which("proot-distro"):
        raise FileNotFoundError("proot-distro is not installed")

    args = ["proot-distro", "login"]
    if cwd:
        args += ["-w", cwd]
    if env is not None:
        for key, value in env.items():
            if key == "PATH" or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
                continue
            args += ["-e", f"{key}={value}"]
    return args + [distro, "--"] + commands
