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
    build_file: str, gradle_args: Optional[List[str]] = None
) -> List[str]:
    gradle_wrapper = os.path.join(os.path.dirname(build_file), "gradlew")
    executable = "./gradlew" if os.path.isfile(gradle_wrapper) else "gradle"
    return [executable] + (gradle_args or ["assembleDebug"])
