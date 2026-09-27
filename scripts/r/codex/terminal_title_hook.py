#!/usr/bin/env python3

import base64
import json
import os
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
    title = state_file.read_text(encoding="utf-8")
except OSError:
    prompt = hook_input.get("prompt")
    if not isinstance(prompt, str):
        raise SystemExit(0)

    title = re.sub(r"[\x00-\x1f\x7f]", " ", prompt)
    title = re.sub(r"\s+", " ", title).strip()[:120]
    if not title:
        raise SystemExit(0)

    try:
        with state_file.open("x", encoding="utf-8") as file:
            file.write(title)
    except FileExistsError:
        title = state_file.read_text(encoding="utf-8")

terminal_title = f"Codex {status} {title}"
if "--print-title" in sys.argv[2:]:
    # Keep the transport ASCII so Windows pipe encodings preserve Unicode.
    sys.stdout.write(json.dumps({"terminal_title": terminal_title}))
    raise SystemExit(0)

try:
    with open(
        os.environ.get("CODEX_TERMINAL_TTY") or "/dev/tty", "w", encoding="utf-8"
    ) as tty:
        tty.write(f"\033]0;{terminal_title}\007")
except OSError:
    # Non-interactive launches may not have a terminal, or it may have closed.
    pass

# Hooks should not add their output to the model context.
sys.stdout.write("{}")
