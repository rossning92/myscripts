---
name: todo-list
description: Manages tasks through the todo_list CLI. Use when the user asks to add, list, search, update, complete, reopen, reschedule, or delete a task or reminder.
compatibility: Requires the todo_list command on PATH.
---

# To-do list

Use the `todo_list` command for to-do list and task management.

## Add a new task

```bash
todo_list add --desc "Finish report" --due "tomorrow"
```

## List active tasks

```bash
todo_list list
```

## List all tasks (including closed ones)

```bash
todo_list list --all
```

## Search for a task

```bash
todo_list search "report"
```

## Edit a task (change status, description, or due date)

_Replace `1` with the actual ID from the list._

```bash
# Mark as in progress
todo_list edit 1 --status in_progress

# Mark as closed (done)
todo_list edit 1 --status closed

# Change description
todo_list edit 1 --desc "Finish monthly report"
```

## Delete a task

```bash
todo_list delete 1
```
