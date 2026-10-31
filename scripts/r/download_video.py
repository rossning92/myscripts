import argparse
import logging
import os
import re
from urllib.parse import urlparse

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
        d = os.environ.get("VIDEO_DOWNLOAD_DIR")
        if not d:
            d = os.path.join(os.path.expanduser("~"), "Desktop")
    else:
        d = base
    if not os.path.exists(d):
        os.makedirs(d)
    return d


def get_redirected_url(url):
    return requests.get(url).url


def download_bilibili(url, download_dir=None, audio_only=False, save_url=True):
    args = [
        "yt-dlp",
        "--no-playlist",
        "--no-mtime",
        "--add-header",
        "Range:bytes=0-",
        "--retries",
        "3",
        "--fragment-retries",
        "3",
    ]
    cookie = os.environ.get("BILIBILI_COOKIE_FILE") or os.path.join(
        root, "..", "..", "repos", "private_scripts", "bili", "tmp",
        "bilibili-cookies.txt",
    )
    if os.path.isfile(cookie):
        args.extend(["--cookies", cookie])
    elif os.environ.get("BILIBILI_COOKIE_FILE"):
        raise FileNotFoundError(cookie)
    if audio_only:
        args.extend(["-f", "bestaudio"])
    if save_url:
        args.append("--write-url-link")
    args.append(url)
    call_echo(args, cwd=download_dir)


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
    hostname = urlparse(url).hostname or ""
    if hostname == "bilibili.com" or hostname.endswith(".bilibili.com"):
        ddir = get_download_dir(base=download_dir)
        download_bilibili(
            url,
            download_dir=ddir,
            audio_only=audio_only,
            save_url=save_url,
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
