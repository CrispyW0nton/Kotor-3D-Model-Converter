from __future__ import annotations

import ast
import os
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
CONSTRUCTION_PATH = (
    ROOT
    / "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/construction.py"
)
ICON_HELPERS_PATH = (
    ROOT
    / "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/shared/icons.py"
)
SOURCE_ICON_DIR = ROOT / "src/gui/icons"
RUNTIME_ICON_DIR = ROOT / "native/GhostRigger.Native.Core.Host/RuntimePayload/src/gui/icons"


FIXED_TOOLBAR_ICON_MAPPING = {
    "GPU": "viewport_gpu",
    "Solid": "viewport_solid",
    "Wire  W": "viewport_wire",
    "Solid + Wire": "viewport_solid_wire",
    "Mesh Hover": "viewport_mesh_hover",
    "Dummy Helpers": "viewport_helpers",
    "Light Helpers + Volumes": "viewport_light_helpers",
    "Bones  B": "viewport_bones",
    "Texture  T": "viewport_texture",
    "Grid": "viewport_grid",
    "Dots": "viewport_dots",
    "Locomotion": "viewport_locomotion_disc",
    "Heat": "viewport_heat",
    "Realistic": "viewport_render_realistic",
    "Shaded": "viewport_render_shaded",
    "Flat": "viewport_render_flat",
    "Frame  F": "viewport_frame",
    "Center Pivot": "viewport_center_pivot",
    "Freeze Transforms": "viewport_freeze_transform",
    "WalkMesh": "viewport_walkmesh",
    "Gimbal  G": "viewport_gimbal",
    "Measure": "viewport_measure",
    "UV View": "viewport_uv",
    "Lock View To Camera": "viewport_lock_camera",
}

DYNAMIC_TOOLBAR_ICON_KEYS = {
    "viewport_translate",
    "viewport_rotate",
    "viewport_scale",
    "viewport_select_object",
    "viewport_select_mesh",
    "viewport_select_helpers",
    "viewport_select_lights",
    "viewport_select_cameras",
    "viewport_navigation",
}

REQUIRED_TOOLBAR_ICON_KEYS = set(FIXED_TOOLBAR_ICON_MAPPING.values()) | DYNAMIC_TOOLBAR_ICON_KEYS


def _literal_icon_button_mapping() -> dict[str, str]:
    tree = ast.parse(CONSTRUCTION_PATH.read_text(encoding="utf-8"))
    mapping: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or len(node.args) < 3:
            continue
        function = node.func
        if not isinstance(function, ast.Attribute) or function.attr != "_icon_button":
            continue
        label = node.args[0]
        icon_key = node.args[2]
        if (
            isinstance(label, ast.Constant)
            and isinstance(label.value, str)
            and isinstance(icon_key, ast.Constant)
            and isinstance(icon_key.value, str)
        ):
            mapping[label.value] = icon_key.value
    return mapping


def test_viewport_toolbar_wires_each_fixed_action_to_a_semantic_icon() -> None:
    mapping = _literal_icon_button_mapping()
    for label, icon_key in FIXED_TOOLBAR_ICON_MAPPING.items():
        assert mapping.get(label) == icon_key, f"{label!r} should use {icon_key}.svg"

    icon_helpers_tree = ast.parse(ICON_HELPERS_PATH.read_text(encoding="utf-8"))
    navigation_function = next(
        node
        for node in icon_helpers_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_navigation_profile_icon"
    )
    navigation_source = ast.unparse(navigation_function)
    assert "_icon('viewport_navigation')" in navigation_source
    assert "_branded_control_icon" not in navigation_source


def test_viewport_toolbar_graphics_are_distinct_mirrored_svg_assets() -> None:
    hashes: dict[bytes, str] = {}
    for icon_key in sorted(REQUIRED_TOOLBAR_ICON_KEYS):
        source = SOURCE_ICON_DIR / f"{icon_key}.svg"
        runtime = RUNTIME_ICON_DIR / f"{icon_key}.svg"
        assert source.exists(), f"Missing source SVG for viewport action: {icon_key}"
        assert runtime.exists(), f"Missing deployed SVG for viewport action: {icon_key}"
        data = source.read_bytes()
        assert data == runtime.read_bytes(), f"RuntimePayload icon drift: {icon_key}"
        lowered = data.lower()
        assert b"<svg" in lowered[:512]
        assert b"<text" not in lowered, f"{icon_key} must be a graphic, not a letter badge"
        assert any(
            marker in lowered
            for marker in (b"<path", b"<circle", b"<rect", b"<polyline", b"<polygon", b"<line", b"<ellipse")
        ), f"{icon_key} contains no recognizable vector graphic"
        assert data not in hashes, f"{icon_key} duplicates the graphic for {hashes.get(data)}"
        hashes[data] = icon_key


def test_viewport_toolbar_icon_resolver_uses_source_and_deployed_assets_without_fallback(monkeypatch) -> None:
    from PySide6 import QtWidgets

    from src.gui.viewports.viewport_core.shared import icons

    _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    resolved_dirs = icons._icon_dirs()
    assert SOURCE_ICON_DIR in resolved_dirs
    assert RUNTIME_ICON_DIR in resolved_dirs

    def _fail_fallback(name: str, size: int = 22):  # pragma: no cover - failure path
        raise AssertionError(f"Generated two-letter fallback used for viewport icon: {name}")

    monkeypatch.setattr(icons, "_generated_fallback_icon", _fail_fallback)
    for icon_dir in (SOURCE_ICON_DIR, RUNTIME_ICON_DIR):
        monkeypatch.setattr(icons, "_icon_dirs", lambda directory=icon_dir: (directory,))
        for icon_key in sorted(REQUIRED_TOOLBAR_ICON_KEYS):
            assert not icons._icon(icon_key).isNull(), icon_key
        for profile in ("3dsmax", "blender", "maya"):
            assert not icons._navigation_profile_icon(profile).isNull(), profile
