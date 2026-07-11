import argparse
import logging
import os
import re
import subprocess

import requests
from _shutil import (
    call_echo,
    get_newest_file,
)
from utils.logger import setup_logger
from utils.retry import retry

root = os.path.dirname(os.path.realpath(__file__))


def get_download_dir(base=None):
    if base is None:
        d = os.environ["VIDEO_DOWNLOAD_DIR"]
        if not d:
            d = os.path.join(os.path.expanduser("~"), "Desktop")
    else:
        d = base
    if not os.path.exists(d):
        os.makedirs(d)
    return d


def get_redirected_url(url):
    return requests.get(url).url


def download_bilibili(url, download_dir=None):
    subprocess.check_call(
        ["run_script", "r/download_video_lux.sh", url], cwd=download_dir
    )


def download_youtube(url, download_dir=None, audio_only=False, download_playlist=False):
    if audio_only:
        format = "bestaudio"
    else:
        format = "bestvideo+bestaudio"
    args = [
        "yt-dlp",
        "-f",
        format,
        "--no-mtime",
        url,
    ]
    # check for cookie in environment variable
    cookie = os.environ.get("YOUTUBE_COOKIE")
    if cookie:
        args.extend(
            [
                "--cookies",
                cookie,
                "--js-runtimes",
                "node",
                "--remote-components",
                "ejs:github",
            ]
        )
    if not download_playlist:
        args.append("--no-playlist")
    call_echo(args, cwd=download_dir)


@retry()
def download_video(url, audio_only=False, download_dir=None, save_url=True):
    url = get_redirected_url(url)
    if "bilibili.com" in url:
        ddir = get_download_dir(base=download_dir)
        download_bilibili(
            url,
            download_dir=ddir,
        )
    elif "youtube.com" in url:
        ddir = get_download_dir(base=download_dir)
        download_youtube(
            url,
            download_dir=ddir,
            audio_only=audio_only,
        )

        # Save url
        if save_url:
            # Remove anything after "&":
            # https://www.youtube.com/watch?v=xxxxxxxx&list=yyyyyyyy&start_radio=1
            url = re.sub(r"(\?(?!v)|&).*$", "", url)
            url_file = get_newest_file(os.path.join(ddir, "*.*")) + ".url"
            logging.info("Save url to: %s" % url_file)
            with open(url_file, "w", encoding="utf-8") as f:
                f.write(url)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio_only", default=False, action="store_true")
    parser.add_argument("--download_dir", default=None, type=str)
    parser.add_argument("url", type=str)
    args = parser.parse_args()

    setup_logger()

    download_video(
        url=args.url, audio_only=args.audio_only, download_dir=args.download_dir
    )
