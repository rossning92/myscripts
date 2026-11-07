import argparse
import os
from pathlib import Path

from utils.script.path import get_data_dir


def install_skills(source_dir: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)

    for manifest in sorted(source_dir.resolve().glob("*/SKILL.md")):
        source = manifest.parent
        target = target_dir / source.name

        if os.path.lexists(target):
            if target.is_symlink() and target.resolve() == source:
                continue
            if target.is_symlink() and not target.exists():
                target.unlink()
            else:
                raise FileExistsError(f"Skill already installed: {target}")

        target.symlink_to(source, target_is_directory=True)
        print(f"Linked: {target} -> {source}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    args = parser.parse_args()

    for target_dir in [
        Path(get_data_dir()) / "skills",
        Path.home() / ".claude" / "skills",
        Path.home() / ".codex" / "skills",
    ]:
        install_skills(args.source, target_dir)


if __name__ == "__main__":
    main()
