---
name: browsercli
description: Drives a browser through the browsercli CLI. Use when the user asks to open, read, click, fill, or screenshot a web page.
---

# browsercli

Use `browsercli --help` or `browsercli help <command>` only when you need syntax or command options.

Start with `browsercli open <url>` without calling `connect` or setting up a session.

- Call `connect extension` or `connect browser --headed` only when the user explicitly requests that mode.
- Run `screencast` only when the user explicitly requests it.
- Set `BROWSERCLI_SESSION` only when separate browser instances are needed.

Use snapshot refs for actions, then snapshot again after the page changes. Prefer clicking links in the current page; use `open` for the initial page or a destination with no clickable link.

```bash
browsercli open https://example.com
browsercli snapshot
browsercli click --ref @e0
browsercli fill --ref @e1 "search terms"
browsercli press Enter
browsercli snapshot
```

For a separate browser instance:

```bash
export BROWSERCLI_SESSION=session-1
browsercli open https://example.com
browsercli snapshot
```
