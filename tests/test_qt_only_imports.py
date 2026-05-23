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
import os
import pathlib
import sys
from types import ModuleType

import pytest

# ── Paths ───────────────────────────────────────────────────────────────────
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_GUI_DIR = _REPO_ROOT / "src" / "gui"

# Files that MUST remain Tk-free.
#   * Every qt_*.py — the canonical Qt UI subtree.
#   * viewport_core.py — the Tk-free rendering split from T001.
_QT_FILES = sorted(_GUI_DIR.rglob("qt_*.py"))
_VIEWPORT_CORE = _GUI_DIR / "rendering" / "viewport_core.py"

# Files that are EXPECTED to import tkinter — empty after M3/T302.
#
# Pre-M3 this set listed the frozen Tk modules (viewport.py shim,
# viewport_tk.py, main_window.py, character_builder_window.py,
# blueprint_editor.py, modular_panel.py, matrix_background.py,
# icon_manager.py). All eight files were deleted in M3/T302 and the
# tree is now Qt-only, so the roster is empty and the cross-check tests
# below assert that nothing in src/gui/ imports tkinter any more.
_FROZEN_TK_FILES: set[pathlib.Path] = set()


def test_log_panel_embeds_python_terminal():
    """The bottom output area should split log output and a live Python console."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6 import QtWidgets
    from src.gui.qt_lib.panels.qt_log_panel import QtLogPanel, QtPythonTerminalPanel

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtLogPanel()
    try:
        assert panel.content_splitter.count() == 2
        assert isinstance(panel.terminal, QtPythonTerminalPanel)
        assert panel.save_button.parent().objectName() == "LogFooter"
        assert panel.terminal.run_button.parent().objectName() == "PythonTerminalFooter"
        panel.log("left side still logs", "info")
        assert "left side still logs" in panel.get_text()
        panel.terminal.input.setText("1 + 2")
        panel.terminal._execute_input()
        assert "3" in panel.terminal.output.toPlainText()
    finally:
        panel.deleteLater()


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
    for path in sorted(_GUI_DIR.rglob("*.py")):
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


def test_gui_root_only_keeps_central_qt_lib():
    """Root src/gui should not fill back up with compatibility shims."""
    allowed = {"__init__.py", "qt_lib.py"}
    extra = [
        path.name
        for path in sorted(_GUI_DIR.glob("*.py"))
        if path.name not in allowed
    ]
    assert not extra, (
        "Move GUI modules into category folders and route imports through "
        "src.gui.qt_lib instead of root src/gui shims: " + ", ".join(extra)
    )

# ──────────────────────────────────────────────────────────────────────────
#  Layer 2 — live import probe (skipped when third-party deps missing)
# ──────────────────────────────────────────────────────────────────────────
#
# The Qt modules pull in PySide6 plus the rest of the GhostRigger backend
# (pykotor, moderngl, numpy, PIL, ...). When any of those are unavailable
# (e.g. a slim CI image) we skip the live probe and rely on Layer 1.



def test_application_imports_use_central_qt_lib():
    """Runnable code should not import deleted root GUI modules."""
    old_roots = {
        "accel",
        "gpu_renderer",
        "qt_accel",
        "qt_animation_panel",
        "qt_blueprint_editor",
        "qt_bottom_strip",
        "qt_character_builder_panel",
        "qt_character_builder_window",
        "qt_common_panels",
        "qt_diagnostics_panel",
        "qt_dialogs",
        "qt_export_dialog",
        "qt_gpu_renderer",
        "qt_icon_manager",
        "qt_inspector_panel",
        "qt_library_panel",
        "qt_lighting_panel",
        "qt_log_panel",
        "qt_main_window",
        "qt_matrix_background",
        "qt_modular_panel",
        "qt_normal_map_panel",
        "qt_properties_panel",
        "qt_resource_panel",
        "qt_retarget_window",
        "qt_rig_panel",
        "qt_settings_dialog",
        "qt_tex_atlas",
        "qt_texture_panel",
        "qt_theme",
        "qt_tpc_render_utils",
        "qt_unreal_animator",
        "qt_uv_viewer",
        "qt_viewport",
        "qt_workflow_rail",
        "tex_atlas",
        "tpc_render_utils",
        "viewport",
        "viewport_core",
        "viewport_navigation",
    }
    scan_roots = [
        _REPO_ROOT / "main.py",
        _REPO_ROOT / "scripts",
        _REPO_ROOT / "src",
        _REPO_ROOT / "tests",
    ]
    offenders: list[tuple[pathlib.Path, int, str]] = []
    for root in scan_roots:
        paths = [root] if root.is_file() else sorted(root.rglob("*.py"))
        for path in paths:
            if any(part == "__pycache__" for part in path.parts):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    if mod == "qt_lib" or mod.startswith(("qt_lib.", "gui.")):
                        offenders.append((path, node.lineno, f"from {mod} import ..."))
                    if mod.startswith("src.gui."):
                        root_name = mod.removeprefix("src.gui.").split(".", 1)[0]
                        if root_name in old_roots:
                            offenders.append((path, node.lineno, f"from {mod} import ..."))
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.name
                        if name == "qt_lib" or name.startswith(("qt_lib.", "gui.")):
                            offenders.append((path, node.lineno, f"import {name}"))
                        if name.startswith("src.gui."):
                            root_name = name.removeprefix("src.gui.").split(".", 1)[0]
                            if root_name in old_roots:
                                offenders.append((path, node.lineno, f"import {name}"))
    assert not offenders, (
        "Use src.gui.qt_lib.<category>.<module> instead of deleted root GUI imports:\n  "
        + "\n  ".join(
            f"{path.relative_to(_REPO_ROOT)}:{lineno}: {stmt}"
            for path, lineno, stmt in offenders
        )
    )


def test_qt_icon_paths_resolve_after_gui_grouping():
    """Moved Qt modules should still point at shared src/gui/icons assets."""
    theme = importlib.import_module("src.gui.qt_lib.assets.qt_theme")
    icon_manager = importlib.import_module("src.gui.qt_lib.assets.qt_icon_manager")
    main_window = importlib.import_module("src.gui.qt_lib.windows.qt_main_window")

    expected = _GUI_DIR / "icons"
    assert pathlib.Path(theme._QT_ICON_DIR) == expected
    assert pathlib.Path(main_window._QT_ICON_DIR) == expected
    assert icon_manager.ICONS_DIR == expected
    assert (expected / "tab_left.svg").exists()
    assert (expected / "tab_right.svg").exists()


def test_matrix_background_uses_bundled_aurebesh_font_dir():
    """Matrix rain should load AurebeshAF from shared src/gui/fonts."""
    matrix = importlib.import_module("src.gui.qt_lib.assets.qt_matrix_background")

    expected = _GUI_DIR / "fonts" / "AurebeshAF"
    assert matrix._FONT_DIR == expected
    assert (expected / "AurebeshAF-CanonTech.otf").exists()
    assert (expected / "AurebeshAF-LegendsTech.otf").exists()


def test_grouped_gui_modules_use_qt_lib_imports():
    """Implementation files should cross-import through qt_lib, not root shims."""
    grouped_dirs = [
        _GUI_DIR / "assets",
        _GUI_DIR / "dialogs",
        _GUI_DIR / "panels",
        _GUI_DIR / "rendering",
        _GUI_DIR / "textures",
        _GUI_DIR / "viewports",
        _GUI_DIR / "windows",
    ]
    offenders: list[tuple[pathlib.Path, int, str]] = []
    for folder in grouped_dirs:
        for path in sorted(folder.glob("*.py")):
            if path.name == "__init__.py":
                continue
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                stripped = line.strip()
                if stripped.startswith(("from qt_lib.", "import qt_lib.", "from gui.", "import gui.")):
                    offenders.append((path, lineno, stripped))
    assert not offenders, (
        "Grouped GUI implementation modules should use src.gui.qt_lib.* imports:\n  "
        + "\n  ".join(
            f"{path.relative_to(_REPO_ROOT)}:{lineno}: {line}"
            for path, lineno, line in offenders
        )
    )


def test_qt_lib_facade_imports_grouped_modules():
    """The stable qt_lib facade supports category imports used by GUI modules."""
    common = importlib.import_module("src.gui.qt_lib.panels.qt_common_panels")
    viewport = importlib.import_module("src.gui.qt_lib.viewports.qt_viewport")
    renderer = importlib.import_module("src.gui.qt_lib.rendering.gpu_renderer")

    assert hasattr(common, "QtToolPanel")
    assert hasattr(viewport, "QtViewportWidget")
    assert hasattr(renderer, "GpuRenderer")


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
        if (mod_name.startswith("src.gui.qt_lib")
                or mod_name.startswith("src.gui.panels.")
                or mod_name.startswith("src.gui.windows.")
                or mod_name.startswith("src.gui.viewports.")
                or mod_name.startswith("src.gui.rendering.")
                or mod_name.startswith("src.gui.dialogs.")
                or mod_name.startswith("src.gui.assets.")
                or mod_name.startswith("src.gui.textures.")
                or mod_name == "src.gui.qt_lib"):
            sys.modules.pop(mod_name, None)

    # The actual probe — if any qt_*.py path imports tkinter this raises
    # ImportError("import of tkinter halted; None in sys.modules").
    importlib.import_module("src.gui.qt_lib.windows.qt_main_window")


@pytest.mark.skipif(
    not _runtime_deps_available(),
    reason="PySide6 / pykotor / moderngl / numpy / PIL not installed in this env",
)
def test_viewport_core_imports_without_tkinter(monkeypatch):
    """The Tk-free rendering core must import cleanly with tkinter banned."""
    monkeypatch.setitem(sys.modules, "tkinter", None)
    monkeypatch.setitem(sys.modules, "tkinter.ttk", None)
    for mod_name in list(sys.modules):
        if mod_name == "src.gui.qt_lib" or mod_name.startswith("src.gui.qt_lib."):
            sys.modules.pop(mod_name, None)
    sys.modules.pop("src.gui.rendering.viewport_core", None)
    importlib.import_module("src.gui.qt_lib.rendering.viewport_core")


def test_fbx_sdk_loader_reports_missing_without_import_crash(monkeypatch):
    from src.io.fbx import fbx_sdk_loader

    monkeypatch.setattr(fbx_sdk_loader, "_CACHE", None)

    def fake_import(name: str):
        return None, f"missing {name}"

    monkeypatch.setattr(fbx_sdk_loader, "_import_optional_module", fake_import)

    modules = fbx_sdk_loader.get_fbx_modules(refresh=True)

    assert modules.fbx is None
    assert modules.FbxCommon is None
    assert not fbx_sdk_loader.is_fbx_sdk_available()
    status = fbx_sdk_loader.get_fbx_sdk_status()
    assert "fbx module: missing" in status
    assert "Autodesk FBX Python SDK is not installed" in status


def test_fbx_sdk_loader_accepts_fbx_without_fbxcommon(monkeypatch):
    from src.io.fbx import fbx_sdk_loader

    monkeypatch.setattr(fbx_sdk_loader, "_CACHE", None)
    fake_fbx = ModuleType("fbx")

    def fake_import(name: str):
        if name == "fbx":
            return fake_fbx, ""
        return None, "missing FbxCommon"

    monkeypatch.setattr(fbx_sdk_loader, "_import_optional_module", fake_import)

    modules = fbx_sdk_loader.get_fbx_modules(refresh=True)

    assert modules.available
    assert modules.fbx is fake_fbx
    assert modules.FbxCommon is None


def test_main_window_routes_fbx_menu_to_optional_sdk_bridge():
    text = (_REPO_ROOT / "src/gui/windows/qt_main_window.py").read_text(encoding="utf-8")

    assert "from src.io.fbx.fbx_importer import FbxSdkUnavailableError, import_fbx" in text
    assert "from src.io.fbx.fbx_exporter import FbxSdkUnavailableError, export_fbx" in text
    assert "self.export_selected_fbx_action" in text
    assert "self.fbx_sdk_status_action" in text
    assert "_show_missing_fbx_sdk_dialog" in text
