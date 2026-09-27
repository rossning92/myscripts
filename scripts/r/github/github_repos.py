#!/usr/bin/env python

"""Select and clone one of the authenticated user's GitHub repositories."""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from utils.menu import Menu
from utils.script.path import get_my_script_root


PRIVATE_REPOSITORY_SYMBOL = "🔒"


@dataclass(frozen=True)
class Repository:
    name: str
    visibility: str
    stargazerCount: int


class GithubRepoMenu(Menu[Repository]):
    def __init__(self, repositories: list[Repository]) -> None:
        self._name_width = max((len(repo.name) for repo in repositories), default=0)
        self._stars_width = max(
            (len(str(repo.stargazerCount)) for repo in repositories), default=1
        )
        super().__init__(
            items=repositories,
            prompt="repository",
            close_on_selection=False,
        )
        self.add_command(
            self.__clone,
            hotkey="alt+c",
            name="clone",
            pinned=True,
        )

    def get_item_text(self, item: Repository) -> str:
        # The lock occupies two terminal cells; reserve them for public repos too.
        visibility = PRIVATE_REPOSITORY_SYMBOL if item.visibility == "PRIVATE" else "  "
        return (
            f"{item.name:<{self._name_width}}  {visibility}  "
            f"{item.stargazerCount:>{self._stars_width}}"
        )

    def __clone(self) -> None:
        repository = self.get_selected_item()
        if repository is None:
            return

        repos_dir = Path(get_my_script_root()) / "repos"
        repos_dir.mkdir(parents=True, exist_ok=True)
        self.run_raw(
            lambda: subprocess.run(
                ["gh", "repo", "clone", repository.name],
                cwd=repos_dir,
                check=True,
            )
        )

    def on_enter_pressed(self) -> None:
        pass


def ensure_authenticated() -> None:
    if subprocess.run(["gh", "auth", "status"], check=False).returncode != 0:
        subprocess.run(["gh", "auth", "login"], check=True)


def get_repositories() -> list[Repository]:
    output = subprocess.check_output(
        ["gh", "repo", "list", "--json", "name,visibility,stargazerCount"],
        text=True,
    )
    return [Repository(**repository) for repository in json.loads(output)]


def main() -> None:
    ensure_authenticated()

    repositories = get_repositories()
    if not repositories:
        raise SystemExit("No GitHub repositories found.")

    GithubRepoMenu(repositories).exec()


if __name__ == "__main__":
    main()
