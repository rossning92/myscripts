# myscripts

Cross-platform script launcher (Windows + Linux/WSL + macOS).

## Run scripts

Use the launcher, never exec script files directly (it sets PATH, venv, env, config, templating):

```bash
run_script <script_path> [args...]   # bin/run_script.py
```

Interactive TUI: `myscripts.py` (alias `bin/s`).

## Per-script config

Sibling JSON drives behavior (window mode, cwd, env):
- `<script>.config.json` - per script.
- `.default.config.json` - dir-level fallback.

Edit the `.config.json`, not the script body, for runtime behavior.

## Python scripts

- Bare imports (`from _shutil import ...`) work because launcher adds `libs/`, `bin/`, `scripts/`, `scripts/r/` to `sys.path`. Standalone runs need `PYTHONPATH=libs`.
- `mypy`/`ruff`/`pytest` NOT installed (default python or `~/.venv/myscripts`) - install before use.

## Tests

```bash
PYTHONPATH=libs python3 -m unittest discover -s tests -v
```
