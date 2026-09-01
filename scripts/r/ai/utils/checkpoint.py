import logging
import shutil
from pathlib import Path


class Checkpoint:
    def __init__(self, checkpoint_root: Path, project_root: Path):
        self.checkpoint_root = checkpoint_root
        self.project_root = project_root.resolve()

    def save(self, message_index: int, file: str):
        target = Path(file).resolve()
        try:
            relative = target.relative_to(self.project_root)
        except ValueError:
            logging.warning('Cannot checkpoint file outside project root: "%s"', file)
            return

        if not target.exists():
            return

        snapshot = self.checkpoint_root / f"{message_index:06d}" / relative
        if snapshot.exists():
            return

        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, snapshot)

    def restore(self, from_message_index: int):
        if not self.checkpoint_root.exists():
            return

        message_dirs = sorted(
            (
                path
                for path in self.checkpoint_root.iterdir()
                if path.is_dir()
                and path.name.isdigit()
                and int(path.name) >= from_message_index
            ),
            key=lambda path: int(path.name),
            reverse=True,
        )
        for message_dir in message_dirs:
            for snapshot in message_dir.rglob("*"):
                if not snapshot.is_file():
                    continue
                relative = snapshot.relative_to(message_dir)
                target = self.project_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(snapshot, target)
            shutil.rmtree(message_dir)
