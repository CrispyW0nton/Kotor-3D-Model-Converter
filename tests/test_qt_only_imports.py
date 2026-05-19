"""
tests/test_qt_only_imports.py — Qt-only imports guard (M0/T005, M3/T305)

Guard rail: every module in the Qt subtree (``src/gui/qt_*.py``) and the
new Tk-free rendering core (``src/gui/viewport_core.py``) MUST import
without ``tkinter`` being available. After M3/T302 deleted the legacy
Tk modules this is extended to ``src/gui/*.py`` — no file under
``src/gui/`` may import tkinter — and to a guard that the eight deleted
files never reappear on disk.

The test runs in two layers, in order of strictness:

  1.  **Static AST scan** — the most reliable check, runs even without
      PySide6 installed. Walks every ``ast.Import`` / ``ast.ImportFrom``
      node under ``src/gui/`` and asserts none of them name ``tkinter``
      (or any submodule). This is what gates the CI build via the
      ``.github/workflows/qt-only-imports.yml`` workflow added in
      M3/T305.

  2.  **Live import probe** (best effort) — when PySide6 is installed,
      we additionally try to actually ``importlib.import_module`` each
      Qt module with ``sys.modules['tkinter'] = None`` installed first,
      which raises ``ImportError`` the instant any code hits
      ``import tkinter``. Skipped automatically when PySide6 (or any
      other third-party runtime dependency such as ``pykotor``) is not
      installed in the test environment.

CI wiring (M3/T305): ``.github/workflows/qt-only-imports.yml`` runs the
Layer-1 AST scan on every push and pull request targeting ``main`` or
``qt-ghostrigger``. Layer-2 is auto-skipped on the CI image because
PySide6 / pykotor / moderngl / numpy / PIL are not installed there;
local developer runs with those deps still execute the live probe.

Roadmap reference: knowledge_base/roadmap/02_roadmap_2026_05.md
M0/T005 + M3/T305.
"""

from __future__ import annotations

import ast
import importlib
import pathlib
import sys

import pytest

# ── Paths ───────────────────────────────────────────────────────────────────
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_GUI_DIR = _REPO_ROOT / "src" / "gui"

# Files that MUST remain Tk-free.
#   * Every qt_*.py — the canonical Qt UI subtree.
#   * viewport_core.py — the Tk-free rendering split from T001.
_QT_FILES = sorted(_GUI_DIR.glob("qt_*.py"))
_VIEWPORT_CORE = _GUI_DIR / "viewport_core.py"

# Files that are EXPECTED to import tkinter — empty after M3/T302.
#
# Pre-M3 this set listed the frozen Tk modules (viewport.py shim,
# viewport_tk.py, main_window.py, character_builder_window.py,
# blueprint_editor.py, modular_panel.py, matrix_background.py,
# icon_manager.py). All eight files were deleted in M3/T302 and the
# tree is now Qt-only, so the roster is empty and the cross-check tests
# below assert that nothing in src/gui/ imports tkinter any more.
_FROZEN_TK_FILES: set[pathlib.Path] = set()


def _collect_tkinter_imports(path: pathlib.Path) -> list[tuple[int, str]]:
    """Return [(lineno, statement-text)] for every tkinter import in *path*."""
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "tkinter" or alias.name.startswith("tkinter."):
                    hits.append((node.lineno, f"import {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "tkinter" or mod.startswith("tkinter."):
                hits.append((node.lineno, f"from {mod} import ..."))
    return hits


# ──────────────────────────────────────────────────────────────────────────
#  Layer 1 — static AST scan (always runs)
# ──────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", _QT_FILES, ids=lambda p: p.name)
def test_qt_subtree_has_no_tkinter_imports(path: pathlib.Path):
    """No qt_*.py file may statically import tkinter."""
    hits = _collect_tkinter_imports(path)
    assert hits == [], (
        f"{path.name} contains tkinter import(s) which violates the Qt-only "
        f"rule (M0/T005). Move Tk code to viewport_tk.py or one of the "
        f"frozen modules listed in AGENTS.md. Offending lines:\n  "
        + "\n  ".join(f"L{ln}: {stmt}" for ln, stmt in hits)
    )


def test_viewport_core_has_no_tkinter_imports():
    """src/gui/viewport_core.py is the Tk-free rendering split (T001)."""
    hits = _collect_tkinter_imports(_VIEWPORT_CORE)
    assert hits == [], (
        f"viewport_core.py must remain Tk-free; offending lines:\n  "
        + "\n  ".join(f"L{ln}: {stmt}" for ln, stmt in hits)
    )


def test_frozen_tk_files_are_correctly_classified():
    """Sanity: the frozen-Tk roster matches what is actually on disk.

    After M3/T302 the roster is empty (all eight legacy Tk modules were
    deleted). The assertion below still runs so a future re-introduction
    of a frozen Tk file is caught by an explicit set membership rather
    than silently slipping into the Qt subtree.
    """
    missing = [p for p in _FROZEN_TK_FILES if not p.exists()]
    assert not missing, (
        "Frozen-Tk roster references files that don't exist on disk: "
        + ", ".join(str(p.relative_to(_REPO_ROOT)) for p in missing)
    )


def test_legacy_tk_modules_are_deleted():
    """M3/T302 — the eight frozen Tk modules must NOT exist on disk."""
    deleted = [
        _GUI_DIR / "viewport.py",
        _GUI_DIR / "viewport_tk.py",
        _GUI_DIR / "main_window.py",
        _GUI_DIR / "character_builder_window.py",
        _GUI_DIR / "blueprint_editor.py",
        _GUI_DIR / "modular_panel.py",
        _GUI_DIR / "matrix_background.py",
        _GUI_DIR / "icon_manager.py",
    ]
    resurrected = [p for p in deleted if p.exists()]
    assert not resurrected, (
        "Frozen Tk modules deleted in M3/T302 were resurrected on disk: "
        + ", ".join(str(p.relative_to(_REPO_ROOT)) for p in resurrected)
    )


def test_no_gui_module_imports_tkinter():
    """Post-M3, no file under src/gui/ may import tkinter."""
    offenders: list[tuple[pathlib.Path, list[tuple[int, str]]]] = []
    for path in sorted(_GUI_DIR.glob("*.py")):
        hits = _collect_tkinter_imports(path)
        if hits:
            offenders.append((path, hits))
    assert not offenders, (
        "Post-M3 src/gui/ must be Tk-free. Offending files:\n  "
        + "\n  ".join(
            f"{p.relative_to(_REPO_ROOT)}: "
            + ", ".join(f"L{ln}:{stmt}" for ln, stmt in hits)
            for p, hits in offenders
        )
    )


# ──────────────────────────────────────────────────────────────────────────
#  Layer 2 — live import probe (skipped when third-party deps missing)
# ──────────────────────────────────────────────────────────────────────────
#
# The Qt modules pull in PySide6 plus the rest of the GhostRigger backend
# (pykotor, moderngl, numpy, PIL, ...). When any of those are unavailable
# (e.g. a slim CI image) we skip the live probe and rely on Layer 1.

def _runtime_deps_available() -> bool:
    for name in ("PySide6", "pykotor", "moderngl", "numpy", "PIL"):
        try:
            importlib.import_module(name)
        except Exception:
            return False
    return True


@pytest.mark.skipif(
    not _runtime_deps_available(),
    reason="PySide6 / pykotor / moderngl / numpy / PIL not installed in this env",
)
def test_qt_main_window_imports_without_tkinter(monkeypatch):
    """Importing the Qt entry point must not require tkinter at runtime."""
    # Force any 'import tkinter' to fail immediately.
    monkeypatch.setitem(sys.modules, "tkinter", None)
    monkeypatch.setitem(sys.modules, "tkinter.ttk", None)

    # Drop any previously-imported Qt / viewport modules so the import
    # chain re-runs from scratch under the tkinter ban.
    for mod_name in list(sys.modules):
        if (mod_name.startswith("src.gui.qt_")
                or mod_name == "src.gui.viewport_core"
                or mod_name == "src.gui.qt_main_window"):
            sys.modules.pop(mod_name, None)

    # The actual probe — if any qt_*.py path imports tkinter this raises
    # ImportError("import of tkinter halted; None in sys.modules").
    importlib.import_module("src.gui.qt_main_window")


@pytest.mark.skipif(
    not _runtime_deps_available(),
    reason="PySide6 / pykotor / moderngl / numpy / PIL not installed in this env",
)
def test_viewport_core_imports_without_tkinter(monkeypatch):
    """The Tk-free rendering core must import cleanly with tkinter banned."""
    monkeypatch.setitem(sys.modules, "tkinter", None)
    monkeypatch.setitem(sys.modules, "tkinter.ttk", None)
    sys.modules.pop("src.gui.viewport_core", None)
    sys.modules.pop("src.gui.viewport", None)
    sys.modules.pop("src.gui.viewport_tk", None)
    importlib.import_module("src.gui.viewport_core")
