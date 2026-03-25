# AGENTS.md

## Cursor Cloud specific instructions

### Overview

PyKotor is a pure-Python monorepo for modding Knights of the Old Republic I & II. It uses **uv** as the package manager with a workspace defined in the root `pyproject.toml`. Minimum supported Python is 3.8; local development may use 3.13 (per `.python-version`). See `README.md` and `CONTRIBUTING.md` for standard commands.

### Running commands

Always use `uv run` to execute commands (per `.cursorrules`), e.g. `uv run pytest`, `uv run ruff check .`, `uv run pykotor --help`.

### Lint

```
uv run ruff check .
uv run ruff format --check .
```

Pre-existing lint violations exist; 259 ruff findings are normal on the current codebase.

### Tests

```
QT_QPA_PLATFORM=offscreen uv run pytest --import-mode=importlib -m "not gui and not slow" --timeout=120 \
  --ignore=Libraries/PyKotor/tests/resource/formats/test_mdl_ascii.py \
  --ignore=Libraries/PyKotor/tests/test_utility/test_registry_strict_typing.py
```

**Gotchas:**
- **`--import-mode=importlib` is required on Linux**: Without it, pytest fails with `ModuleNotFoundError: No module named 'resource.formats'` because the test directory `Libraries/PyKotor/tests/resource/` collides with Python's stdlib `resource` module.
- `test_mdl_ascii.py` must be `--ignore`d: it tries to open KotOR game files from a hardcoded Windows path at *collection* time and will fail with `FileNotFoundError` if `K1_PATH`/`K2_PATH` env vars are not set to valid game directories.
- `test_registry_strict_typing.py` must be `--ignore`d on Linux: it imports the Windows-only `winreg` module unconditionally.
- Set `QT_QPA_PLATFORM=offscreen` for headless Qt test execution; `xvfb` is available but `offscreen` is simpler.
- The pytest process may crash (exit 134 / SIGABRT) during teardown due to PyQt6 thread cleanup. This is a known upstream issue and does not affect test results. Check the output for pass/fail counts before the crash.
- Many test failures are expected without KotOR game files installed (the `K1_PATH` and `K2_PATH` environment variables point to Windows paths by default in `.env`).
- Several HolocronToolset test files fail during collection due to a `requires_connection()` signature issue in `toolset/blender/commands.py`. This is a pre-existing codebase issue, not an environment problem.

### Building / running the application

- **PyKotor CLI**: `uv run pykotor --help` — format conversions, archive operations, diffing, etc.
- **HolocronToolset GUI**: `QT_QPA_PLATFORM=offscreen uv run holocrontoolset` — requires display or offscreen mode.
- **HoloPatcher**: `uv run holopatcher --help`
- **KotorDiff**: `uv run kotordiff --help`

### Dependency sync

Run `CXX=g++ uv sync --all-packages --all-extras` (not bare `uv sync`) to install all workspace members (HolocronToolset, HoloPatcher, etc.) and dev extras (ruff, pytest plugins, type stubs). Bare `uv sync` only installs the root meta-package.

### System dependencies (already in snapshot)

Python 3.8–3.13, uv, g++/gfortran (for numpy build), and Qt6/OpenGL/xcb system libraries are pre-installed. The `CXX=g++` env var may be needed when `uv sync` rebuilds numpy from source.

### Known codebase issues

- **HolocronToolset startup fails**: `toolset/blender/commands.py` uses `@requires_connection(return_value=False)` but the decorator does not accept that keyword argument. This prevents `uv run holocrontoolset` from launching. This is a pre-existing code bug, not an environment issue.
