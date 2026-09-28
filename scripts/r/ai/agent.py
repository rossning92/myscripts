import argparse
import os
import subprocess
import sys
from typing import Collection

from _script import get_agents
from utils.jsonutil import load_json
from utils.script.path import get_bin_dir, get_data_dir


PROMPT_OPTIONS = {
    "coder": ["--prompt"],
}
DEFAULT_AGENT = "coder"
DEFAULT_AGENT_FILE = os.path.join(get_data_dir(), "default_agent.json")


def get_default_agent(agents: Collection[str]) -> str:
    agent = load_json(DEFAULT_AGENT_FILE, {"agent": DEFAULT_AGENT}).get("agent")
    return agent if agent in agents else DEFAULT_AGENT


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch the default coding agent")
    parser.add_argument("--context", help="plain-text context")
    parser.add_argument("-p", "--prompt", help="initial user prompt")
    args = parser.parse_args()

    agents = get_agents()
    agent = get_default_agent(agents)
    # A bare invocation comes from the global hotkey: activate the default
    # agent's idle window when it exists, otherwise launch it. Invocations that
    # carry work must still create a session to receive that work.
    command = (
        ["start_script", "--instance-mode=activate", agents[agent]]
        if not args.context and not args.prompt
        else [sys.executable, os.path.join(get_bin_dir(), "run_script.py"), agents[agent]]
    )
    if args.context:
        command.extend(["--context", args.context])
    if args.prompt:
        command.extend([*PROMPT_OPTIONS.get(agent, []), args.prompt])
    return subprocess.run(command).returncode


if __name__ == "__main__":
    raise SystemExit(main())
