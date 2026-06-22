import subprocess
from typing import List, Optional

_RECENT_COMMIT_COUNT = 3


def run_vcs(cwd: Optional[str], cmd: str, *args: str) -> Optional[str]:
    try:
        r = subprocess.run(
            [cmd, *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def get_git_recent_commits(cwd: Optional[str] = None) -> List[str]:
    log = run_vcs(cwd, "git", "log", f"-{_RECENT_COMMIT_COUNT}", "--format=%h %as %s")
    return log.splitlines() if log else []


def get_hg_recent_commits(cwd: Optional[str] = None) -> List[str]:
    log = run_vcs(
        cwd,
        "sl",
        "log",
        "-T",
        "{node|short} {date|shortdate} {pad(phabdiff, 12)} {desc|firstline}\n",
        "-r",
        "reverse(draft() & (::. + .::))",
    )
    return log.splitlines() if log else []


def prepend_recent_commits(status: str, recent_commits: List[str]) -> str:
    # Prepend recent commits on top of the default status bar text.
    if not recent_commits:
        return status
    log = "\n".join(f"• {c}" for c in recent_commits)
    return f"{log}\n{status}"
