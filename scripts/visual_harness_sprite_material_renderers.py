"""Drive Sprite Materials across renderer backends and save a visual report.

This is a visible Qt workflow harness, not a headless model-pipeline probe.
It loads lightsaber models through the normal main-window scene path, edits the
Sprite Materials panel, switches renderer/shade modes, captures screenshots, and
writes a JSON report with renderer diagnostics and material state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402

from src.core.rendering.renderer_backend import RendererBackend, renderer_backend_label  # noqa: E402
from src.core.rendering.renderer_settings import RendererSettings  # noqa: E402
from src.core.rendering.wgpu_shared import _WGPU_BACKENDS, _WGPU_BACKEND_ENV  # noqa: E402
from src.core.scene.scene_resource_ref import SceneResourceRef  # noqa: E402
from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow  # noqa: E402


_SETTINGS_OVERRIDE: dict[str, Any] | None = None


DEFAULT_BACKENDS = (
    RendererBackend.AUTOMATIC,
    RendererBackend.MODERNGL_GL330,
    RendererBackend.WGPU_AUTO,
    RendererBackend.WGPU_D3D12,
    RendererBackend.WGPU_VULKAN,
    RendererBackend.WGPU_OPENGL,
    RendererBackend.PYGFX_WGPU,
)

SHADE_MODES = ("realistic", "shaded", "flat")

DEFAULT_SPRITE_CASES = (
    {"name": "class_glow_blade", "class": "glow_blade", "mode": None},
    {"name": "class_hilt", "class": "hilt", "mode": None},
    {"name": "class_sprite", "class": "sprite", "mode": None},
    {"name": "mode_opaque", "class": "glow_blade", "mode": "opaque"},
    {"name": "mode_blend", "class": "glow_blade", "mode": "blend"},
    {"name": "mode_additive", "class": "glow_blade", "mode": "additive"},
    {"name": "mode_lighten", "class": "glow_blade", "mode": "lighten"},
)


class HarnessMainWindow(QtGhostRiggerMainWindow):
    def _load_settings(self) -> dict:
        data = super()._load_settings()
        if _SETTINGS_OVERRIDE:
            renderer = data.setdefault("renderer", {})
            renderer.update(dict(_SETTINGS_OVERRIDE.get("renderer", {})))
        return data


def pump(app: QtWidgets.QApplication, seconds: float = 0.15) -> None:
    deadline = time.monotonic() + max(0.0, seconds)
    while time.monotonic() < deadline:
        app.processEvents(QtCore.QEventLoop.AllEvents, 50)
        time.sleep(0.01)


def screenshot(widget: QtWidgets.QWidget, path: Path) -> dict[str, Any]:
    pixmap = widget.grab()
    image = pixmap.toImage().convertToFormat(QtGuiFormat.RGBA8888)
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(path))
    width = int(image.width())
    height = int(image.height())
    data = bytes(image.bits())
    digest = hashlib.sha256(data).hexdigest()[:16]
    non_dark = 0
    stride = 4
    for offset in range(0, len(data), stride):
        r, g, b, a = data[offset : offset + 4]
        if a and (int(r) + int(g) + int(b)) > 75:
            non_dark += 1
    return {
        "path": str(path),
        "width": width,
        "height": height,
        "sha256_16": digest,
        "non_dark_pixels": non_dark,
    }


class QtGuiFormat:
    RGBA8888 = None


def patch_qt_format() -> None:
    from PySide6 import QtGui

    QtGuiFormat.RGBA8888 = QtGui.QImage.Format_RGBA8888


def load_resref(window: QtGhostRiggerMainWindow, resref: str, game: str) -> None:
    ref = SceneResourceRef(resource_type="model", game=game, resref=resref, original_name=resref)
    model, texture_dir = window._load_model_for_resource_ref(ref)
    if model is None:
        raise RuntimeError(f"Could not load {game}:{resref}")
    window.scene_manager.clear_scene()
    if texture_dir and texture_dir not in window._scene_texture_dirs:
        window._scene_texture_dirs.append(texture_dir)
    instance = window.scene_manager.add_model_instance(ref, runtime_model=model, select=True)
    window._current_model = model
    window._model_path = f"{game}:{resref}"
    window._current_game = game
    window._refresh_scene_view()
    window._select_scene_object(instance.id)


def selected_blade_node(window: QtGhostRiggerMainWindow):
    panel = window.sprite_materials_panel
    nodes = panel._mesh_nodes()
    blades = [
        node
        for node in nodes
        if "Glow / Blade" in panel._category_label(node)
        and "hilt" not in panel._category_label(node).lower()
    ]
    if not blades:
        blades = [
            node
            for node in nodes
            if any(token in f"{getattr(node, 'name', '')} {getattr(node, 'texture', '')}".lower() for token in ("lsabre", "blade", "glow", "plane"))
            and not panel._is_saber_hilt(node)
        ]
    if not blades:
        raise RuntimeError("No lightsaber blade sprite row found")
    node = blades[0]
    panel.select_sprite(node)
    return node


def apply_sprite_case(window: QtGhostRiggerMainWindow, node, case: dict[str, Any]) -> None:
    panel = window.sprite_materials_panel
    panel.select_sprite(node)
    panel._reset_nodes([node])
    panel.select_sprite(node)
    if case.get("class"):
        panel._set_combo_value(panel.category_combo, str(case["class"]))
    if case.get("mode"):
        panel._set_combo_value(panel.mode_combo, str(case["mode"]))
    window._on_sprite_materials_changed([node])


def material_state(panel, node) -> dict[str, Any]:
    return {
        "mesh": str(getattr(node, "name", "")),
        "texture": panel._texture_name(node),
        "class": panel._category_label(node),
        "mode": panel._mode_label(panel._render_mode(node)),
        "flags": panel._flag_label(node),
        "txi_blending": int(getattr(node, "txi_blending", 0) or 0),
        "transparency_hint": int(getattr(node, "transparency_hint", 0) or 0),
        "alpha_cutoff": float(getattr(node, "txi_alpha_test", 0.0) or 0.0),
        "opacity": float(getattr(node, "alpha", 1.0) or 1.0),
        "wateralpha": float(getattr(node, "txi_wateralpha", 1.0) or 1.0),
        "decal": bool(getattr(node, "txi_decal", False)),
        "key_matte": str(getattr(node, "_gr_sprite_alpha_source", "") or ""),
        "glow": float(getattr(node, "_gr_sprite_glow", 0.0) or 0.0),
        "revision": int(getattr(node, "_gr_revision", 0) or 0),
    }


def renderer_diagnostics(window: QtGhostRiggerMainWindow) -> dict[str, Any]:
    renderer = getattr(window.viewport, "_gpu_renderer", None)
    get = getattr(renderer, "get_diagnostics", None)
    if callable(get):
        try:
            return dict(get() or {})
        except Exception as exc:
            return {"error": repr(exc)}
    return {}


def _select_backends(names: list[str]) -> tuple[RendererBackend, ...]:
    by_value = {backend.value: backend for backend in DEFAULT_BACKENDS}
    by_value.update({backend.name.lower(): backend for backend in DEFAULT_BACKENDS})
    by_value.update({
        "auto": RendererBackend.AUTOMATIC,
        "automatic": RendererBackend.AUTOMATIC,
        "moderngl": RendererBackend.MODERNGL_GL330,
        "modern_gl": RendererBackend.MODERNGL_GL330,
        "wgpu": RendererBackend.WGPU_AUTO,
        "wgpu_auto": RendererBackend.WGPU_AUTO,
        "d3d12": RendererBackend.WGPU_D3D12,
        "vulkan": RendererBackend.WGPU_VULKAN,
        "opengl": RendererBackend.WGPU_OPENGL,
        "pygfx": RendererBackend.PYGFX_WGPU,
    })
    selected = []
    for name in names:
        key = str(name or "").strip().lower()
        backend = by_value.get(key)
        if backend is None:
            raise ValueError(f"Unknown backend selector: {name}")
        selected.append(backend)
    return tuple(selected)


def _select_cases(names: list[str]) -> tuple[dict[str, Any], ...]:
    by_name = {case["name"]: case for case in DEFAULT_SPRITE_CASES}
    selected = []
    for name in names:
        case = by_name.get(str(name or "").strip())
        if case is None:
            raise ValueError(f"Unknown case selector: {name}")
        selected.append(case)
    return tuple(selected)


def run(args: argparse.Namespace) -> int:
    global _SETTINGS_OVERRIDE

    patch_qt_format()
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
    initial_backend = _select_backends([args.initial_backend or args.backends[0]])[0]
    initial_wgpu_backend = _WGPU_BACKENDS.get(initial_backend, "")
    if initial_wgpu_backend:
        os.environ[_WGPU_BACKEND_ENV] = initial_wgpu_backend
    elif initial_backend is RendererBackend.WGPU_AUTO:
        os.environ.pop(_WGPU_BACKEND_ENV, None)
    _SETTINGS_OVERRIDE = {
        "renderer": {
            "backend": initial_backend.value,
            "allow_fallback": initial_backend is RendererBackend.AUTOMATIC,
            "force_safe_mode": False,
            "idle_render_mode": "continuous",
            "show_renderer_diagnostics": True,
            "throttle_diagnostics": False,
        }
    }
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app.setApplicationName("GhostRigger")
    app.setStyle("Fusion")
    for family in ("Consolas", "Lucida Console", "Courier New"):
        if family in QtGui.QFontDatabase.families():
            app.setFont(QtGui.QFont(family, 9))
            break
    window = HarnessMainWindow(
        ROOT,
        startup_input={
            "preloaded_library": {"detection_attempted": True, "rows": []},
            "renderer_capabilities": [],
            "hardware_diagnostics": {},
        },
    )
    applied_theme = ""
    if args.theme:
        if args.theme == "active":
            theme = window.theme_manager.apply_current_theme(window)
        else:
            theme = window.theme_manager.select_theme(args.theme, target=window)
        applied_theme = str(getattr(theme, "id", "") or args.theme)
    window.resize(1500, 920)
    window.show()
    pump(app, 1.0)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base_settings = RendererSettings.from_settings(window.settings_data)
    backends = _select_backends(args.backends)
    sprite_cases = _select_cases(args.cases)
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    try:
        for resref in args.resrefs:
            load_resref(window, resref, args.game)
            pump(app, 0.8)
            blade = selected_blade_node(window)
            for backend in backends:
                requested = backend.value
                settings = replace(
                    base_settings,
                    backend=backend,
                    allow_fallback=backend is RendererBackend.AUTOMATIC,
                    force_safe_mode=False,
                    show_renderer_diagnostics=True,
                    idle_render_mode="continuous",
                    throttle_diagnostics=False,
                    target_fps=60,
                )
                window.viewport.set_renderer_settings(settings)
                pump(app, args.backend_wait)
                for shade in SHADE_MODES:
                    window.viewport.set_render_mode(shade)
                    pump(app, args.case_wait)
                    for case in sprite_cases:
                        try:
                            blade = selected_blade_node(window)
                            apply_sprite_case(window, blade, case)
                            pump(app, args.case_wait)
                            diag = renderer_diagnostics(window)
                            active = str(diag.get("backend_id") or getattr(window.viewport, "_active_renderer_backend")())
                            filename = f"{resref}_{requested}_{shade}_{case['name']}.png".replace("/", "_")
                            shot = screenshot(window.viewport, out_dir / filename)
                            row = {
                                "resref": resref,
                                "game": args.game,
                                "requested_backend": requested,
                                "requested_label": renderer_backend_label(backend),
                                "active_backend": active,
                                "shade_mode": shade,
                                "sprite_case": dict(case),
                                "material": material_state(window.sprite_materials_panel, blade),
                                "diagnostics": diag,
                                "screenshot": shot,
                            }
                            rows.append(row)
                            print(
                                f"OK {resref} {requested} active={active} shade={shade} "
                                f"case={case['name']} hash={shot['sha256_16']} pixels={shot['non_dark_pixels']}",
                                flush=True,
                            )
                        except Exception as exc:
                            failure = {
                                "resref": resref,
                                "requested_backend": requested,
                                "shade_mode": shade,
                                "sprite_case": dict(case),
                                "error": repr(exc),
                                "diagnostics": renderer_diagnostics(window),
                            }
                            failures.append(failure)
                            print(f"FAIL {failure}", flush=True)
    finally:
        report = {
            "game": args.game,
            "resrefs": args.resrefs,
            "backends": [backend.value for backend in backends],
            "shade_modes": list(SHADE_MODES),
            "sprite_cases": list(sprite_cases),
            "theme": applied_theme or str(getattr(window.theme_manager.get_theme(), "id", "")),
            "initial_backend": initial_backend.value,
            "rows": rows,
            "failures": failures,
        }
        (out_dir / "sprite_material_renderer_harness_report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        try:
            window.scene_manager.active_scene.mark_clean()
        except Exception:
            pass
        window._prompt_save_dirty_scene = lambda: True
        window.close()
        app.quit()
        app.processEvents()
    return 1 if failures else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", default="K1")
    parser.add_argument("--resrefs", nargs="+", default=["w_lghtsbr_001", "w_lghtsbr_002"])
    parser.add_argument("--backends", nargs="+", default=[backend.value for backend in DEFAULT_BACKENDS])
    parser.add_argument("--initial-backend", default="", help="Renderer backend to seed before the main window is built")
    parser.add_argument("--cases", nargs="+", default=[case["name"] for case in DEFAULT_SPRITE_CASES])
    parser.add_argument("--theme", default="default_dark", help="Theme id to apply before testing, or 'active' for settings.json")
    parser.add_argument("--out-dir", default=str(ROOT / "artifacts" / "sprite_material_renderer_harness"))
    parser.add_argument("--backend-wait", type=float, default=0.9)
    parser.add_argument("--case-wait", type=float, default=0.2)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
