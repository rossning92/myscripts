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

- Bare imports work because the launcher adds `libs/`, `scripts/`, `scripts/r/` to `sys.path` (and `bin/` to `PATH`, not `sys.path`). Standalone runs need `PYTHONPATH=libs:scripts:scripts/r` - `libs` alone only resolves `libs/` modules (e.g. `from _shutil import ...`), not `scripts/r/` ones (e.g. `ai.*`).
- `mypy`/`ruff`/`pytest` NOT installed (default python or `~/.venv/myscripts`) - install before use.

## Tests

Tests mirror the source path under `tests/` (e.g. `ai/utils/menu/confirmcommandmenu.py` -> `tests/ai/utils/menu/test_confirmcommandmenu.py`). `discover` only collects top-level `tests/*.py`; tests in subdirs are not auto-discovered, so run those by file path.

```bash
PYTHONPATH=libs:scripts:scripts/r python3 -m unittest discover -s tests -v   # top-level only
PYTHONPATH=libs:scripts:scripts/r python3 -m unittest tests.ai.utils.menu.test_confirmcommandmenu -v   # a subdir test
```

## External repositories

- Clone external repositories under the ignored `repos/` directory.
