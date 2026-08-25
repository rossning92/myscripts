import argparse
import os
import subprocess

from utils.jsonutil import load_json
from utils.script.path import get_data_dir


AGENTS = {
    "coder": "r/ai/coder.py",
    "codex": "r/codex.sh",
}
PROMPT_OPTIONS = {
    "coder": ["--prompt"],
    "codex": [],
}
DEFAULT_AGENT = "coder"
DEFAULT_AGENT_FILE = os.path.join(get_data_dir(), "default_agent.json")


def get_default_agent() -> str:
    agent = load_json(DEFAULT_AGENT_FILE, {"agent": DEFAULT_AGENT}).get("agent")
    return agent if agent in AGENTS else DEFAULT_AGENT


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch the default coding agent")
    parser.add_argument("--context", help="plain-text context")
    parser.add_argument("-p", "--prompt", help="initial user prompt")
    args = parser.parse_args()

    agent = get_default_agent()
    command = ["run_script", AGENTS[agent]]
    if args.context:
        command.extend(["--context", args.context])
    if args.prompt:
        command.extend([*PROMPT_OPTIONS[agent], args.prompt])
    return subprocess.run(command).returncode


if __name__ == "__main__":
    raise SystemExit(main())
