import argparse
import math
import subprocess
import time

from utils.menu import Menu
from utils.textutil import truncate_text


AGENTS = {
    "coder": "r/ai/coder.py",
    "codex": "r/codex.sh",
}
PROMPT_OPTIONS = {
    "coder": ["--prompt"],
    "codex": [],
}
AUTO_SELECT_TIMEOUT_SEC = 1.0


class AgentSelectorMenu(Menu):
    """Auto-select only when the user has not interacted with the menu."""

    def __init__(self, prompt: str, **kwargs):
        self.__prompt = prompt
        auto_select_timeout_sec = kwargs.get("timeout_sec", AUTO_SELECT_TIMEOUT_SEC)
        self.__auto_select_deadline = time.monotonic() + auto_select_timeout_sec
        timeout = math.ceil(auto_select_timeout_sec)
        prompt = self.__get_countdown_prompt(timeout)
        kwargs["timeout_sec"] = min(1.0, auto_select_timeout_sec)
        super().__init__(prompt=prompt, **kwargs)

    def __get_countdown_prompt(self, seconds_remaining: int) -> str:
        return (
            f"{self.__prompt} "
            f"\033[33m(auto-select in {seconds_remaining}s)\033[0m"
        )

    def on_char(self, ch):
        self.timeout_sec = -1.0
        self.set_prompt(self.__prompt)
        return super().on_char(ch)

    def on_timeout(self) -> None:
        seconds_remaining = math.ceil(
            self.__auto_select_deadline - time.monotonic()
        )
        if seconds_remaining <= 0:
            self.on_enter_pressed()
        else:
            self.set_prompt(self.__get_countdown_prompt(seconds_remaining))


def _get_prompt(
    context: str | None,
) -> str:
    prompt = "select agent"
    if context:
        context_preview = truncate_text(context)
        prompt += f" \033[34m(context: {context_preview})\033[0m"
    return prompt


def main() -> int:
    parser = argparse.ArgumentParser(description="Choose and launch a coding agent")
    parser.add_argument("--context", help="plain-text context")
    parser.add_argument("-p", "--prompt", help="initial user prompt")
    args = parser.parse_args()

    menu = AgentSelectorMenu(
        prompt=_get_prompt(args.context),
        items=list(AGENTS),
        enable_command_palette=False,
        history="select_agent",
        quick_select=True,
        timeout_sec=AUTO_SELECT_TIMEOUT_SEC,
    )
    menu.exec()
    agent = menu.get_selected_item()
    if agent is None:
        return 0

    command = ["run_script", AGENTS[agent]]
    if args.context:
        command.extend(["--context", args.context])
    if args.prompt:
        command.extend([*PROMPT_OPTIONS[agent], args.prompt])
    return subprocess.run(command).returncode


if __name__ == "__main__":
    raise SystemExit(main())
