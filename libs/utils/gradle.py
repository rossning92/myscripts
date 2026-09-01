import os
from typing import List, Optional


COMMON_GRADLE_TASKS = [
    "assembleDebug",
    "installDebug",
    "assembleRelease",
    "bundleDebug",
    "bundleRelease",
    "build",
    "test",
    "connectedAndroidTest",
    "lint",
    "clean",
    "tasks",
]


def is_gradle_build_file(path: str) -> bool:
    return os.path.basename(path).lower() == "build.gradle"


def get_gradle_command(
    _build_file: str, gradle_args: Optional[List[str]] = None
) -> List[str]:
    return [
        "run_script",
        "r/android/gradle.sh",
    ] + (gradle_args or [])
