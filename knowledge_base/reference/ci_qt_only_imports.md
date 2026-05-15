# CI guard — Qt-only imports (M3/T305)

This note documents the CI hook added in milestone M3, task T305. It
enforces that the Qt subtree (`src/gui/qt_*.py` + `viewport_core.py` +
the rest of `src/gui/*.py` after M3/T302) never imports `tkinter` and
that the eight legacy Tk modules deleted in M3/T302 never reappear on
disk.

## Local / shell entry point

Run the guard at any time from a developer shell:

```bash
bash scripts/ci_qt_only_imports.sh
```

The script installs `pytest` (if missing) and runs
`tests/test_qt_only_imports.py` with verbose output. Exit code is
non-zero on the first regression so it composes naturally with `git
pre-push` hooks, `make check`-style targets, or any CI runner.

## GitHub Actions snippet

The bot that landed M3 was authenticated with a GitHub App token that
lacked the `workflows` permission, so `.github/workflows/*.yml` had to
be added separately by a maintainer with a personal access token.
Copy the YAML below into `.github/workflows/qt-only-imports.yml` to
wire the script up to push + pull-request events:

```yaml
name: Qt-only imports guard

on:
  push:
    branches: [main, qt-ghostrigger]
  pull_request:
    branches: [main, qt-ghostrigger]
  workflow_dispatch: {}

jobs:
  qt-only-imports:
    name: Qt-only AST scan (T005 / T305)
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: bash scripts/ci_qt_only_imports.sh
```

## Why two layers

`tests/test_qt_only_imports.py` runs two layers in order of strictness:

1. **Static AST scan** — needs only the stdlib `ast` module + pytest.
   Walks every `ast.Import` / `ast.ImportFrom` under `src/gui/` and
   rejects any reference to `tkinter` (or any submodule). This layer
   is what gates the CI build because it works on the slim CI image
   without PySide6 / pykotor / moderngl / numpy / PIL installed.

2. **Live import probe** — when the full toolchain is installed, the
   test additionally sets `sys.modules['tkinter'] = None` and tries to
   `importlib.import_module` every Qt module, which raises
   `ImportError` the instant any code hits `import tkinter`. Skipped
   automatically when third-party runtime deps are missing.

## What the test guards

After M3 the assertions are:

- `test_qt_subtree_has_no_tkinter_imports` — original M0/T005 check on
  every `qt_*.py` file.
- `test_viewport_core_has_no_tkinter_imports` — Tk-free rendering
  core stays Tk-free.
- `test_frozen_tk_files_are_correctly_classified` — the
  frozen-Tk roster is empty (after M3/T302) and any future addition
  must be explicit.
- `test_legacy_tk_modules_are_deleted` — the eight files deleted in
  M3/T302 must NOT exist on disk: `main_window.py`,
  `character_builder_window.py`, `blueprint_editor.py`,
  `modular_panel.py`, `matrix_background.py`, `icon_manager.py`,
  `viewport_tk.py`, `viewport.py`.
- `test_no_gui_module_imports_tkinter` — AST-scans every `src/gui/*.py`
  (not just `qt_*.py`) and rejects any `tkinter` import.

The total test count for the Qt-only imports module is 5 + N
parametrised entries (one per `qt_*.py` file). Local runs against the
M3 tree report **56 passed, 3 skipped** for the full
`tests/test_qt_only_imports.py tests/test_character_mode.py` set; the
3 skips are the auto-skipped Layer-2 live probes when PySide6 et al.
are missing.

## Roadmap reference

`knowledge_base/roadmap/02_roadmap_2026_05.md` — M3/T305.
