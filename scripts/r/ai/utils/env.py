import os
from datetime import date
from pathlib import Path
from platform import platform
from typing import Optional


def get_global_config_path() -> Optional[Path]:
    if path := os.getenv("AI_CONFIG_ROOT"):
        return Path(path).expanduser().resolve()
    return None


def get_env_info() -> str:
    return f"""# Environment Information

Platform: {platform()}
Current working directory: {os.getcwd()}
Today's date: {date.today().isoformat()}
"""
