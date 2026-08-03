#!/usr/bin/env python3

import base64
import json
import re
import sys
import tempfile
from pathlib import Path


if len(sys.argv) < 2 or not sys.argv[1]:
    raise SystemExit(2)

status = sys.argv[1]

try:
    hook_input = json.load(sys.stdin)
except (json.JSONDecodeError, OSError):
    raise SystemExit(0)

session_id = hook_input.get("session_id")
if not isinstance(session_id, str):
    raise SystemExit(0)

encoded_session_id = base64.urlsafe_b64encode(session_id.encode()).decode().rstrip("=")
state_dir = Path(tempfile.gettempdir()) / "codex-terminal-title-v2"
state_file = state_dir / encoded_session_id
state_dir.mkdir(parents=True, exist_ok=True)

try:
    title = state_file.read_text()
except OSError:
    prompt = hook_input.get("prompt")
    if not isinstance(prompt, str):
        raise SystemExit(0)

    title = re.sub(r"[\x00-\x1f\x7f]", " ", prompt)
    title = re.sub(r"\s+", " ", title).strip()[:120]
    if not title:
        raise SystemExit(0)

    try:
        with state_file.open("x") as file:
            file.write(title)
    except FileExistsError:
        title = state_file.read_text()

try:
    with open("/dev/tty", "w") as tty:
        tty.write(f"\033]0;Codex {status} {title}\007")
except OSError:
    # Some non-interactive terminals do not expose /dev/tty.
    pass

# Hooks should not add their output to the model context.
sys.stdout.write("{}")
