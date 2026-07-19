"""Capture the Peragus uniforms in the actual main-window BAS workflow.

The proof deliberately uses the ModernGL backend shown in the reported video,
adds each custom body as a KMAX scene object, attaches a stock K2 head through
the main-window Body Attachment System, and samples inherited ``b11a3`` motion.
No game Override files are written.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.mcp.start_kotormcp_stdio import _python_roots  # noqa: E402

for item in reversed(list(_python_roots(ROOT))):
    if item.exists() and str(item) not in sys.path:
        sys.path.insert(0, str(item))

os.environ.setdefault("QT_QPA_PLATFORM", "windows")


DEFAULT_PROOF_DIR = Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\MyMods\BetterArmor\Redesigns"
    r"\PeragusMiningUniform\CharacterBuilderProof"
)
DEFAULT_K2_DIR = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"
)
FIXTURES = (
    ("pfbc09", "PFHC01", "PFBC09_basecolor.tga"),
    ("pmbc09", "PMHC01", "PMBC09_basecolor.tga"),
)


def _process_events(app: Any, seconds: float) -> None:
    deadline = time.perf_counter() + max(0.0, float(seconds))
    while time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.01)


def _force_render(window: Any, app: Any, reason: str) -> None:
    viewport = window.viewport
    viewport._request_render(
        fast=True,
        reason=reason,
        animation=True,
        scene=True,
        resources=True,
        style=True,
        overlay=True,
        hud=True,
    )
    for _ in range(8):
        app.processEvents()
        try:
            viewport._render_now()
        except Exception:
            pass
        time.sleep(0.04)


def _screen_grab(app: Any, window: Any, path: Path) -> dict[str, Any]:
    window.raise_()
    window.activateWindow()
    _process_events(app, 0.15)
    screen = app.primaryScreen()
    pixmap = screen.grabWindow(int(window.winId())) if screen is not None else window.grab()
    path.parent.mkdir(parents=True, exist_ok=True)
    saved = bool(pixmap.save(str(path), "PNG"))
    return {
        "path": str(path),
        "saved": saved,
        "width": int(pixmap.width()),
        "height": int(pixmap.height()),
    }


def _tagged_pose(window: Any, body: Any, engine: Any, animation: str, sample_time: float):
    pose = engine.evaluate(sample_time)
    return window._tag_animation_pose_source(pose, body, animation, "K2")


def _capture_fixture(
    app: Any,
    window: Any,
    body: Any,
    body_path: Path,
    head_resref: str,
    output_dir: Path,
) -> dict[str, Any]:
    from src.core.rendering.mesh_render_data import (
        _animated_node_world_transform,
        _bas_attachment_world_transform,
        _effective_animation_pose_for_node,
    )

    artifact = body_path.stem.lower()
    window._animation_timer.stop()
    window.scene_manager.clear_scene()
    scene_object = window._add_loaded_model_to_scene(body, str(body_path), clear_scene=False)
    window._current_model = body
    window._current_game = "K2"
    window._model_path = str(body_path)
    window._bas_body_model = body
    window._bas_preview_model = None
    window._bas_attachments = {}
    window._bas_attachment_resrefs = {}
    window._bas_attachment_transforms = {}
    window._animation_preview_object_id = ""
    window.body_attachment_panel.set_mode("headless_body")
    window.body_attachment_panel.set_body_model(body, resref=artifact, game="K2")
    window.animations_panel.set_animation_source("body")
    window._refresh_scene_view()
    window._handle_bas_attach_requested("head", head_resref)
    preview = window._bas_preview_model
    if preview is None:
        raise RuntimeError(f"{artifact}: main-window BAS preview was not created")

    window._animation_preview_object_id = ""
    window._load_animation_panel_model(body, select_name="b11a3")
    if not window.animations_panel.select_animation("b11a3"):
        raise RuntimeError(f"{artifact}: inherited b11a3 was not listed in the main window")
    window._handle_animation_action("Play", "b11a3")
    _process_events(app, 0.45)
    engine = window._animation_engine
    if engine is None or engine.current_animation is None:
        raise RuntimeError(f"{artifact}: main-window animation playback did not start")
    length = float(engine.current_animation.length or 0.0)
    sample_time = length * 0.5
    window._animation_timer.stop()
    engine.seek(sample_time)
    pose0 = _tagged_pose(window, body, engine, "b11a3", 0.0)
    pose = _tagged_pose(window, body, engine, "b11a3", sample_time)
    window.viewport.set_anim_base_pose(pose0)
    window._apply_viewport_animation_pose(
        pose,
        name="b11a3",
        time=sample_time,
        length=length,
        reason="Peragus main viewport BAS proof",
    )
    window.viewport.set_animation_playback_active(True, "Peragus main viewport BAS proof")
    window.viewport.frame_all()
    window.viewport.camera.azimuth = 0.0
    window.viewport.camera.elevation = 4.0
    _force_render(window, app, f"{artifact} main viewport BAS b11a3")

    scene_preview = window.viewport.model
    headhook = next(
        node
        for node in scene_preview.all_nodes()
        if str(getattr(node, "name", "") or "").lower() == "headhook"
        and not bool(getattr(node, "_gr_bas_attachment_layer", False))
    )
    head_root = next(
        node
        for node in scene_preview.all_nodes()
        if bool(getattr(node, "_gr_bas_attachment_root", False))
        and str(getattr(node, "_gr_bas_attachment_slot", "") or "").lower() == "head"
    )
    head_pose = _effective_animation_pose_for_node(head_root, pose)
    hook_position = _animated_node_world_transform(headhook, pose)[0]
    root_position = _bas_attachment_world_transform(
        head_root,
        head_root,
        anim_pose=head_pose,
    )[0]
    socket_delta = max(abs(float(a) - float(b)) for a, b in zip(hook_position, root_position))
    screenshot = _screen_grab(
        app,
        window,
        output_dir / f"{artifact}_{head_resref.lower()}_main_viewport_moderngl_b11a3_side.png",
    )
    renderer = getattr(window.viewport, "_gpu_renderer", None)
    active_backend = str(getattr(getattr(renderer, "active_backend", None), "value", "") or "")
    head_source_name = str(getattr(head_pose, "_gr_animation_source_model_name", "") or "")
    head_source_id = int(getattr(head_pose, "_gr_animation_source_model_id", 0) or 0)
    expected_source_id = int(getattr(head_root, "_gr_bas_attachment_source_model_id", 0) or 0)
    status = "pass" if (
        screenshot["saved"]
        and active_backend == "modern_gl"
        and head_pose is not None
        and getattr(head_pose, "_gr_bas_socket_pose", None) is pose
        and head_source_id == expected_source_id
        and socket_delta <= 1.0e-6
    ) else "fail"
    window.viewport.set_animation_playback_active(False)
    scene_object.metadata.setdefault("body_attachment_system", {})["proof_status"] = status
    return {
        "status": status,
        "body": artifact,
        "head": head_resref,
        "animation": "b11a3",
        "sample_time": sample_time,
        "renderer": active_backend,
        "headhook_world": [float(value) for value in hook_position],
        "head_root_world": [float(value) for value in root_position],
        "socket_delta_max_abs_m": socket_delta,
        "head_pose_source": head_source_name,
        "head_pose_animation": str(getattr(head_pose, "_gr_animation_name", "") or ""),
        "head_pose_has_body_socket": getattr(head_pose, "_gr_bas_socket_pose", None) is pose,
        "head_pose_source_id_matches_layer": head_source_id == expected_source_id,
        "screenshot": screenshot,
    }


def run(proof_dir: Path, k2_dir: Path) -> dict[str, Any]:
    from PySide6 import QtWidgets

    from src.core.animation.animation_engine import SuperModelResolver
    from src.core.assets.resource_manager import RES_TGA, ResourceManager, _key
    from src.core.game.kotor_loader import load_model_from_file
    from src.core.geometry.model_data import GameVersion
    from src.core.rendering.renderer_backend import RendererBackend
    from src.core.rendering.renderer_settings import RendererSettings
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    manager = ResourceManager()
    if not manager.set_k2_dir(str(k2_dir)):
        raise RuntimeError(f"K2 installation could not be indexed: {k2_dir}")
    for _artifact, _head, texture_name in FIXTURES:
        texture_path = proof_dir / texture_name
        manager._k2._override[_key(texture_path.stem, RES_TGA)] = str(texture_path)
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(manager)

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    startup_input = {
        "preloaded_library": {
            "k1_dir": "",
            "k2_dir": str(k2_dir),
            "rows": [],
            "_resource_manager": manager,
            "autoscan": False,
            "detection_attempted": True,
            "detected": True,
            "error": "",
        }
    }
    window = QtGhostRiggerMainWindow(app_root=ROOT, startup_input=startup_input)
    window._resource_manager = manager
    window._resource_manager_dirs = ("", str(k2_dir))
    # The sprite-material panel is unrelated to this proof.  A selected scene
    # object is still loaded and rendered normally; suppress only that panel's
    # secondary context refresh so this focused BAS gate is not coupled to
    # concurrent sprite-material work in the shared development tree.
    window.sprite_materials_panel = None
    window.resize(1500, 950)
    window.show()
    _process_events(app, 1.0)
    window.viewport.set_renderer_settings(
        RendererSettings(
            backend=RendererBackend.MODERNGL_GL330,
            allow_fallback=False,
            target_fps=60,
            idle_render_mode="continuous",
            show_renderer_diagnostics=True,
        )
    )
    window.viewport.set_resource_manager(manager, "K2")
    window.viewport.set_render_mode("realistic")
    window.viewport.toggle_texture(True)
    window.viewport.toggle_bones(False)
    window.viewport.toggle_grid(True)
    _process_events(app, 0.5)

    output_dir = proof_dir / "VisualProof"
    rows = []
    for artifact, head_resref, _texture_name in FIXTURES:
        mdl_path = proof_dir / f"{artifact}.mdl"
        body = load_model_from_file(
            str(mdl_path),
            str(mdl_path.with_suffix(".mdx")),
            game_version=GameVersion.K2,
        )
        if body is None:
            raise RuntimeError(f"could not load {mdl_path}")
        rows.append(_capture_fixture(app, window, body, mdl_path, head_resref, output_dir))

    window._animation_timer.stop()
    window.scene_manager.active_scene.mark_clean()
    window.close()
    _process_events(app, 0.25)
    payload = {
        "status": "pass" if rows and all(row["status"] == "pass" for row in rows) else "fail",
        "actual_main_window": True,
        "game": "K2",
        "backend": "modern_gl",
        "body_attachment_system": "head -> animated headhook",
        "override_modified": False,
        "fixtures": rows,
    }
    report_path = output_dir / "peragus_uniform_main_viewport_bas_animation_proof.json"
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    payload["report"] = str(report_path)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof-dir", type=Path, default=DEFAULT_PROOF_DIR)
    parser.add_argument("--k2-dir", type=Path, default=DEFAULT_K2_DIR)
    args = parser.parse_args()
    result = run(args.proof_dir.resolve(), args.k2_dir.resolve())
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
