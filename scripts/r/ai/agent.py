import argparse
import subprocess

from utils.menu import Menu
from utils.textutil import truncate_text


AGENTS = {
    "coder": "r/ai/coder.py",
    "codex": "r/codex.sh",
}
AUTO_SELECT_TIMEOUT_SEC = 1.0


class AgentSelectorMenu(Menu):
    """Auto-select only when the user has not interacted with the menu."""

    def __init__(self, prompt_after_input: str, **kwargs):
        super().__init__(**kwargs)
        self.__prompt_after_input = prompt_after_input

    def on_char(self, ch):
        self.timeout_sec = -1.0
        self.set_prompt(self.__prompt_after_input)
        return super().on_char(ch)

    def on_timeout(self) -> None:
        self.on_enter_pressed()


def _get_prompt(context: str | None, show_auto_select: bool = True) -> str:
    prompt = "select agent"
    if show_auto_select:
        timeout = f"{AUTO_SELECT_TIMEOUT_SEC:g}"
        prompt += f" \033[33m(auto-select in {timeout}s)\033[0m"
    if context:
        context_preview = truncate_text(context)
        prompt += f" \033[34m(context: {context_preview})\033[0m"
    return prompt


def main() -> int:
    parser = argparse.ArgumentParser(description="Choose and launch a coding agent")
    parser.add_argument("--context", help="plain-text context")
    args = parser.parse_args()

    menu = AgentSelectorMenu(
        prompt_after_input=_get_prompt(args.context, show_auto_select=False),
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
    return subprocess.run(command).returncode


if __name__ == "__main__":
    raise SystemExit(main())
