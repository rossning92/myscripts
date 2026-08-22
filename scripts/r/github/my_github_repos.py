#!/usr/bin/env python

"""Select and clone one of the authenticated user's GitHub repositories."""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from utils.menu import Menu


PRIVATE_REPOSITORY_SYMBOL = "🔒"


@dataclass(frozen=True)
class Repository:
    name: str
    visibility: str
    stargazerCount: int

    def __str__(self) -> str:
        if self.visibility == "PRIVATE":
            return f"{self.name} {PRIVATE_REPOSITORY_SYMBOL} ★{self.stargazerCount}"
        return f"{self.name} ★{self.stargazerCount}"


class GithubRepoMenu(Menu[Repository]):
    def __init__(self, repositories: list[Repository]) -> None:
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

    def __clone(self) -> None:
        repository = self.get_selected_item()
        if repository is None:
            return

        projects_dir = Path.home() / "Projects"
        projects_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["gh", "repo", "clone", repository.name],
            cwd=projects_dir,
            check=True,
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
