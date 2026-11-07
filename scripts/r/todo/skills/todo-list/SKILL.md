---
name: todo-list
description: Manages tasks through the todo_list CLI. Use when the user asks to add, list, search, update, complete, reopen, reschedule, or delete a task or reminder.
---

# To-do list

Use `todo_list` to manage tasks. Run `todo_list --help` or
`todo_list <command> --help` for command details.

The app lives at `../../todo_list.py` beside its launcher config. Use
`run_script r/todo/todo_list.py` if the `todo_list` command is unavailable.

Data comes from `TODO_DATA_FILE`. To select a different file, pass
`todo_list --data-file /path/to/tasks.json <command>`. Its parent directory must
exist. If neither is configured, ask which file to use.

Find tasks with `list` (active), `list --all` (including closed), or
`search "report"` (description search, including closed tasks). Use the returned
IDs for changes; ask when multiple tasks match the request.

```bash
todo_list add --desc "Finish report" --due "tomorrow"
todo_list edit 1 --desc "Finish monthly report"
todo_list edit 1 --status in_progress
todo_list edit 1 --status closed
todo_list edit 1 --status none                 # Reopen
todo_list edit 1 --status blocked
todo_list edit 1 --due "next monday"           # Reschedule
todo_list delete 1
```

Replace example IDs with actual IDs. Adding without `--due` defaults to today.
Due dates do not schedule notifications.
