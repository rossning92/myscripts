from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from ai.utils.env import get_global_config_path
from utils.git import get_git_root
from utils.markdown import parse_front_matter


@dataclass
class Skill:
    name: str
    description: str
    file_path: str
    metadata: Dict
    content: str


def _find_skills_roots() -> List[Path]:
    roots = [Path(__file__).resolve().parent.parent / "skills"]

    if config_path := get_global_config_path():
        skills_path = config_path / "skills"
        if skills_path.is_dir():
            roots.append(skills_path)

    cwd = Path.cwd().resolve()
    git_root = get_git_root()
    if git_root:
        curr = cwd
        while True:
            roots.append(curr / ".agents" / "skills")
            if curr == git_root:
                break
            curr = curr.parent
    return roots


def _find_skill_files() -> List[tuple[str, Path]]:
    skill_files: Dict[str, Path] = {}

    for skills_root in _find_skills_roots():
        if skills_root.is_dir():
            for skill_dir in sorted(skills_root.iterdir()):
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.is_file():
                        skill_files[skill_dir.name] = skill_file

    return list(skill_files.items())


def _load_skill(name: str, file: Path) -> Skill:
    metadata, content = parse_front_matter(file.read_text(encoding="utf-8"))
    if metadata is None:
        raise ValueError(f"Skill {name} missing front matter")

    description = metadata.get("description", "").strip()
    if not description:
        raise ValueError(f"Skill {name} description cannot be empty")

    return Skill(
        name=name,
        description=description,
        file_path=str(file),
        metadata=metadata,
        content=content,
    )


@lru_cache(maxsize=None)
def get_skills() -> List[Skill]:
    return [_load_skill(name, file) for name, file in _find_skill_files()]


def get_skill_prompt() -> Optional[str]:
    if not (skills := get_skills()):
        return None

    skill_lines = "\n".join(f"`{s.file_path}`: {s.description}" for s in skills)

    prompt_file = Path(__file__).resolve().parent.parent / "prompts" / "skill.txt"
    if prompt_file.exists():
        header = prompt_file.read_text(encoding="utf-8").strip()
    else:
        header = (
            "# Task-Specific Instructions\n\n"
            "You should read the following Markdown file for detailed, task-specific, step-by-step instructions when a task matches the description:"
        )

    return f"{header}\n\n{skill_lines}\n"
