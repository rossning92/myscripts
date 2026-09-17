import os
import re
import signal
import subprocess

from _shutil import cd, get_cur_time_str
from r.video.to_gif import convert_to_gif
from utils.android import get_active_pkg_and_activity


def get_scaled_size(width=1280):
    out = subprocess.check_output(
        ["adb", "shell", "wm", "size"], universal_newlines=True
    )
    w, h = (int(x) for x in re.search(r"Physical size: (\d+)x(\d+)", out).groups())
    # Keep the native aspect ratio, otherwise a stereo (side-by-side) panel gets squashed.
    return "%dx%d" % (width, round(width * h / w / 2) * 2)


def screen_record(out_file=None, max_secs=10, bit_rate="2M", size=None):
    """
    adb shell screenrecord /sdcard/screenrecord.mp4 --time-limit 5 --bit-rate 2M --size 1280x608
    """

    TMP_RECORD_FILE = "/data/local/tmp/screenrecord.mp4"

    print("Press Ctrl-C to stop recording...")

    signal.signal(signal.SIGINT, lambda a, b: None)

    active_package = get_active_pkg_and_activity()[0]

    if out_file is None:
        out_file = "screenrecord_%s_%s.mp4" % (active_package, get_cur_time_str())

    args = ["adb", "shell", "screenrecord", TMP_RECORD_FILE]
    args += ["--time-limit", "{}".format(max_secs), "--bit-rate", "{}".format(bit_rate)]
    args += ["--size", size if size else get_scaled_size()]
    subprocess.call(args, shell=True)

    subprocess.check_call(["adb", "pull", TMP_RECORD_FILE, out_file])

    return out_file


if __name__ == "__main__":
    cd("~/Desktop")

    out_file = screen_record(
        max_secs=int(os.environ["_MAX_SECS"]) if os.environ.get("_MAX_SECS") else 10,
        bit_rate=os.environ["_BIT_RATE"] if os.environ.get("_BIT_RATE") else "2M",
        size=os.environ.get("_SIZE"),
    )

    if os.environ.get("_TO_GIF"):
        convert_to_gif(out_file, out_file=os.path.splitext(out_file)[0] + ".gif")
        os.remove(out_file)
