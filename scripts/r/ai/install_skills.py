import argparse
import os
from pathlib import Path
from typing import Iterable

from utils.script.path import get_data_dir, get_my_script_root


def install_skills(source_dirs: Iterable[Path], target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)

    for source_dir in source_dirs:
        for manifest in sorted(source_dir.resolve().glob("*/SKILL.md")):
            source = manifest.parent
            target = target_dir / source.name

            if os.path.lexists(target):
                if target.is_symlink() and target.resolve() == source:
                    continue
                raise FileExistsError(f"Skill already installed: {target}")

            target.symlink_to(source, target_is_directory=True)
            print(f"Linked: {target} -> {source}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="*", type=Path)
    args = parser.parse_args()

    sources = args.source or [Path(get_my_script_root()) / ".agents" / "skills"]
    install_skills(sources, Path(get_data_dir()) / "skills")


if __name__ == "__main__":
    main()
