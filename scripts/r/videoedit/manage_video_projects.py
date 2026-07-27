#!/usr/bin/env python3
import glob
import os
from pprint import pprint

from _shutil import (
    getch,
    menu_item,
    menu_loop,
    to_valid_file_name,
)
from export_video import load_config
from utils.editor import open_code_editor
from utils.menu import Menu
from utils.yaml import (
    load_yaml,
    save_yaml,
    update_yaml,
)

vproject_root = r"{{VPROJECT_ROOT}}"


def get_all_project_dirs():
    files = glob.glob(os.path.join(vproject_root, "*", "config.yaml"))
    files.sort(key=os.path.getmtime, reverse=True)
    return [os.path.dirname(x) for x in files]


all_projects = get_all_project_dirs()
cur_index = 0


@menu_item(key="l")
def list_all_videos():
    for i, f in enumerate(all_projects):
        print_project_info(i)


def print_project_info(i):
    d = all_projects[i]

    config = load_config(os.path.join(d, "config.yaml"))
    name = os.path.basename(d)
    print(f"{i+1}. {name}", end="")
    if "title" in config:
        print(" | " + config["title"], end="")

    print()


@menu_item(key="w")
def prev():
    global cur_index
    cur_index = max(cur_index - 1, 0)
    print_project_info(cur_index)


@menu_item(key="s")
def next():
    global cur_index
    cur_index = min(cur_index + 1, len(all_projects))
    print_project_info(cur_index)


@menu_item(key="\r")
def search_project():
    global cur_index
    i = Menu(items=all_projects).exec()
    if i >= 0:
        cur_index = i
        print("Project set to:")
        print_project_info(cur_index)


@menu_item(key="t")
def set_title():
    global cur_index
    title = input("new title: ")
    if title:
        update_yaml(
            os.path.join(all_projects[cur_index], "config.yaml"), {"title": title}
        )


def bulk_edit():
    tmp_file = os.path.expanduser("~/Desktop/videos.yml")

    # Update existing configs
    if os.path.exists(tmp_file):
        videos = load_yaml(tmp_file)
        for name, video2 in videos.items():
            project_file = os.path.join(vproject_root, name, "config.yaml")
            video = load_yaml(project_file)
            if video2 != video:
                pprint(video2)
                print("press y to continue...")
                if getch() == "y":
                    videos[name] = video2
                    save_yaml(video2, project_file)

    # Export all configs to a single yaml file.
    videos = {}
    for f in glob.glob(os.path.join(vproject_root, "*", "config.yaml")):
        name = os.path.basename(os.path.dirname(f))

        config = load_config(f)
        title = config["title"]

        # Try to rename the video file
        if True:
            exported_files_found = list(
                glob.glob(os.path.join(os.path.dirname(f), "export", "*.mp4"))
            )
            if len(exported_files_found) > 1:
                exported_file = None
            elif len(exported_files_found) == 1:
                exported_file = os.path.basename(exported_files_found[0])
            else:
                exported_file = None

            if exported_file is not None:
                new_file = to_valid_file_name(title) + ".mp4"
                os.rename(
                    os.path.join(os.path.dirname(f), "export", exported_file),
                    os.path.join(os.path.dirname(f), "export", new_file),
                )

            videos[name] = config

    save_yaml(videos, tmp_file)

    open_code_editor(tmp_file)


if __name__ == "__main__":
    menu_loop()
