#!/usr/bin/env python3

import json
import os
import re
import sys
import tempfile
from pathlib import Path

from utils.term.title import set_terminal_title

if len(sys.argv) < 2 or not sys.argv[1]:
    raise SystemExit(2)

status = sys.argv[1]

try:
    hook_input = json.load(sys.stdin)
except (json.JSONDecodeError, OSError):
    raise SystemExit(0)

session_id = hook_input.get("session_id")
# Codex's own title-generation thread fires hooks too, without a transcript. Its prompt is not ours.
if not isinstance(session_id, str) or not hook_input.get("transcript_path"):
    raise SystemExit(0)

state_file = Path(tempfile.gettempdir()) / "codex-terminal-title-v2" / session_id
state_file.parent.mkdir(parents=True, exist_ok=True)

try:
    title = state_file.read_text(encoding="utf-8")
except OSError:
    title = hook_input.get("prompt")
    if not isinstance(title, str) or not title.strip():
        raise SystemExit(0)
    state_file.write_text(title, encoding="utf-8")

# Prefer the title Codex summarized for this session, once it exists.
try:
    with open(Path.home() / ".codex" / "session_index.jsonl", encoding="utf-8") as index:
        for line in index:
            entry = json.loads(line)
            if entry.get("id") == session_id and entry.get("thread_name"):
                title = entry["thread_name"]
except (OSError, json.JSONDecodeError):
    pass

title = re.sub(r"[\s\x00-\x1f\x7f]+", " ", title).strip()[:120]
terminal_title = f"Codex {status} {title}"
if "--print-title" in sys.argv[2:]:
    # Keep the transport ASCII so Windows pipe encodings preserve Unicode.
    sys.stdout.write(json.dumps({"terminal_title": terminal_title}))
    raise SystemExit(0)

try:
    set_terminal_title(terminal_title, tty=os.environ.get("CODEX_TERMINAL_TTY") or "/dev/tty")
except OSError:
    # Non-interactive launches may not have a terminal, or it may have closed.
    pass

# Hooks should not add their output to the model context.
sys.stdout.write("{}")
