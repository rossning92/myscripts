import functools
import os
import re
import shutil
import subprocess
import threading
import time
from typing import List, Optional, Set, Tuple, Union

from _script import start_script

from utils.git import get_git_root
from utils.strutil import strip_ansi

from .confirmmenu import confirm
from .textmenu import TextMenu


def _get_diff_line_info(diff_lines: List[str], index: int) -> Optional[Tuple[str, int]]:
    filename = None
    new_line_start = None
    chunk_header_index = -1

    for i in range(index, -1, -1):
        line = diff_lines[i]
        if line.startswith("@@ "):
            match = re.search(r"\+(\d+)", line)
            if match:
                new_line_start = int(match.group(1))
                chunk_header_index = i
                break

    if new_line_start is not None:
        for i in range(chunk_header_index, -1, -1):
            line = diff_lines[i]
            if line.startswith("+++ b/"):
                filename = line[6:]
                break
            elif line.startswith("+++ "):
                filename = line[4:]
                if filename == "/dev/null":
                    filename = None
                break

        if filename:
            current_line = new_line_start
            for i in range(chunk_header_index + 1, index):
                line = diff_lines[i]
                if not line.startswith("-"):
                    current_line += 1
            return filename, current_line
    return None


def _is_section_start(line: str) -> bool:
    # A new hunk ("@@ ...") or a new file ("diff --git ...") ends the current body.
    return line.startswith("@@ ") or line.startswith("diff --git")


def _build_stage_patch(diff_lines: List[str], selected: Set[int]) -> Optional[str]:
    """Build a git patch containing only the selected +/- lines.

    Unselected additions are dropped and unselected deletions become context
    lines. so applying the patch with `git apply --cached` stages only the
    changes the user picked. Returns None if the selection has no real change.
    """
    patch: List[str] = []
    file_header: Optional[List[str]] = None
    file_emitted = False
    n = len(diff_lines)
    i = 0
    while i < n:
        line = diff_lines[i]
        if line.startswith("diff --git"):
            file_header = [line]
            i += 1
            while i < n and not _is_section_start(diff_lines[i]):
                file_header.append(diff_lines[i])
                i += 1
            file_emitted = False
            continue
        if line.startswith("@@ "):
            hunk_header = line
            i += 1
            body: List[str] = []
            has_change = False
            while i < n and not _is_section_start(diff_lines[i]):
                cur = diff_lines[i]
                tag = cur[:1]
                if tag == "+":
                    if i in selected:
                        body.append(cur)
                        has_change = True
                    # Unselected addition. drop it.
                elif tag == "-":
                    if i in selected:
                        body.append(cur)
                        has_change = True
                    else:
                        # Unselected deletion stays as context.
                        body.append(" " + cur[1:])
                elif tag == "\\":
                    body.append(cur)  # "\ No newline at end of file" marker.
                else:
                    # Context line (leading space) or blank line.
                    body.append(cur if cur else " ")
                i += 1
            if has_change:
                if file_header is not None and not file_emitted:
                    patch.extend(file_header)
                    file_emitted = True
                patch.append(hunk_header)
                patch.extend(body)
            continue
        i += 1
    if not patch:
        return None
    return "\n".join(patch) + "\n"


@functools.lru_cache(maxsize=1)
def _find_diff_highlight() -> Optional[str]:
    # git ships `diff-highlight` in contrib/ for word-level highlighting, but it's
    # not a core command. use it when present, fall back to plain diff otherwise.
    found = shutil.which("diff-highlight")
    if found:
        return found
    for c in (
        "/usr/share/git-core/contrib/diff-highlight",
        "/usr/share/git-core/contrib/diff-highlight/diff-highlight",
        "/usr/share/doc/git/contrib/diff-highlight/diff-highlight",
    ):
        if os.access(c, os.X_OK):
            return c
    return None


def _run_diff_cmd(cmd: List[str]) -> List[str]:
    out = subprocess.run(cmd, capture_output=True).stdout
    diff_highlight = _find_diff_highlight()
    if diff_highlight:
        out = subprocess.run([diff_highlight], input=out, capture_output=True).stdout
    return out.decode("utf-8", errors="replace").replace("\r", "").splitlines()


def _build_git_diff_cmd(args: List[str]) -> List[str]:
    return [
        "git",
        "diff",
        "-U3",
        "--color",
        "--ignore-space-change",
        "--color-moved=zebra",
        "--color-moved-ws=allow-indentation-change",
    ] + args


class DiffMenu(TextMenu):
    def __init__(
        self,
        root: Optional[str] = None,
        files: Optional[List[Tuple[str, str]]] = None,
        git_args: Optional[List[str]] = None,
        diff_cmd: Optional[List[str]] = None,
        prompt_prefix: str = "",
        **kwargs,
    ):
        self.__root = root
        self.__files = files
        self.__git_args = git_args
        self.__diff_cmd = diff_cmd
        self.__last_refresh_time = time.monotonic()
        self.__refresh_thread: Optional[threading.Thread] = None

        lines = self.__generate_diff_lines()
        self.__diff_lines = [strip_ansi(line) for line in lines]

        prompt = f"{prompt_prefix} ❯ diff" if prompt_prefix else "diff"
        super().__init__(
            prompt=prompt,
            text="\n".join(lines) if lines else "(no diff)",
            wrap_text=False,
            line_number=False,
            **kwargs,
        )

        self.add_command(self.__edit_file, hotkey="ctrl+e")
        self.add_command(self.__stage_lines, hotkey="ctrl+s")
        self.add_command(self.__discard_lines, hotkey="ctrl+d")
        self.add_command(self.__refresh, hotkey="ctrl+r")

    def __generate_diff_lines(self) -> List[str]:
        if self.__diff_cmd:
            lines = _run_diff_cmd(self.__diff_cmd)
        elif self.__files:
            lines = []
            for f1, f2 in self.__files:
                lines.extend(_run_diff_cmd(_build_git_diff_cmd(["--no-index", f1, f2])))
        else:
            if not self.__root:
                git_root = get_git_root()
                if git_root:
                    self.__root = str(git_root)

            if self.__git_args is not None:
                args = self.__git_args
            else:
                args = []
                if subprocess.run(["git", "diff", "--quiet"]).returncode == 0:
                    args.extend(["HEAD~1", "HEAD"])

            lines = _run_diff_cmd(_build_git_diff_cmd(args))

        return lines

    def __refresh(self):
        if self.__refresh_thread and self.__refresh_thread.is_alive():
            return
        self.__last_refresh_time = time.monotonic()

        def worker():
            lines = self.__generate_diff_lines()
            self.post_event(lambda: self.__apply_refresh(lines))

        self.set_message("refreshing...")
        self.__refresh_thread = threading.Thread(target=worker, daemon=True)
        self.__refresh_thread.start()

    def __apply_refresh(self, lines: List[str]):
        self.__diff_lines = [strip_ansi(line) for line in lines]
        self.items[:] = lines
        self.set_message("refreshed")

    def on_idle(self):
        if time.monotonic() - self.__last_refresh_time >= 5:
            self.__refresh()


    def __is_working_tree_diff(self) -> bool:
        if self.__files is not None or self.__diff_cmd is not None:
            return False
        if self.__git_args is not None and any(
            a == "--no-index" or a.startswith("HEAD") for a in self.__git_args
        ):
            return False
        return True

    def __apply_patch(self, action: str, extra_args: List[str]) -> None:
        if not self.__is_working_tree_diff():
            self.set_message(f"{action} not supported for this diff")
            return

        selected = set(self.get_selected_indices())
        if not selected:
            return
        patch = _build_stage_patch(self.__diff_lines, selected)
        if patch is None:
            self.set_message(f"no changes in selection to {action}")
            return

        result = subprocess.run(
            ["git", "apply", "--recount", "--ignore-whitespace"] + extra_args,
            input=patch.encode("utf-8"),
            capture_output=True,
            cwd=self.__root,
        )
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace").strip()
            self.set_message(f"{action} failed: {err}")
            return
        self.set_message(f"{action}d selection")
        self.set_multi_select(False)
        self.__refresh()

    def __stage_lines(self):
        self.__apply_patch("stage", ["--cached"])

    def __discard_lines(self):
        if not confirm("Discard selected changes?", prompt_color="red"):
            return
        self.__apply_patch("discard", ["--reverse"])

    def __edit_file(self):
        index = self.get_selected_index()
        if index < 0 or index >= len(self.__diff_lines):
            return
        info = _get_diff_line_info(self.__diff_lines, index)
        if info:
            filename, line_number = info
            if self.__root and not os.path.isabs(filename):
                filename = os.path.join(self.__root, filename)

            self.run_raw(
                lambda: start_script(
                    "ext/edit.py",
                    args=[os.path.abspath(filename), "--line", str(line_number)],
                )
            )

    def get_item_color(self, item: str) -> Union[str, Tuple[str, str]]:
        stripped_item = strip_ansi(item)
        if stripped_item.startswith(("diff ", "index ")):
            return "brightblack"
        if stripped_item.startswith("---") or stripped_item.startswith("+++"):
            return ("black", "yellow")
        return super().get_item_color(item)

    def on_enter_pressed(self):
        self.__edit_file()
