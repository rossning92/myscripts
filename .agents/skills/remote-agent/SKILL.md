---
name: remote-agent
description: Delegates a task to an agent running on the remote server. Use when the user asks to run something on the remote agent, use the remote agent, or delegate work to the remote server.
---

# Remote agent

Pass the user's complete task as the first argument:

```bash
.agents/skills/remote-agent/scripts/launch_remote_agent.sh "<task>"
```

The script launches the agent on `ross@10.77.0.1:22` in tmux, then activates the local `remote_shell` tmux window.

Do not perform the delegated task locally. Report whether the command launched successfully; the remote agent continues in its tmux session.
