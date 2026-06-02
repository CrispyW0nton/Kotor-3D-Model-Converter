from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


from scripts.visual_harness_pygfx_flat_animation import (  # noqa: E402
    _best_sample_time,
    _choose_animation,
    _focus_camera_on_node,
    _make_resource_manager,
    _mesh_cache_metrics,
    _pose_delta,
    _process_events,
)


def _force_app_render(window, app, reason: str = "actual app harness", **dirty_flags: bool) -> None:
    viewport = window.viewport
    if not dirty_flags:
        dirty_flags = {"animation": True, "overlay": True, "hud": True}
    viewport._request_render(fast=True, reason=reason, **dirty_flags)
    for _ in range(5):
        _process_events(app, 0.08)
        try:
            viewport._render_now()
        except Exception:
            pass
        _process_events(app, 0.08)


def _screen_grab(app, window, path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    window.raise_()
    window.activateWindow()
    _process_events(app, 0.15)
    screen = app.primaryScreen()
    pixmap = screen.grabWindow(int(window.winId())) if screen is not None else window.grab()
    ok = pixmap.save(str(path))
    metrics = {"path": str(path), "saved": bool(ok), "width": int(pixmap.width()), "height": int(pixmap.height())}
    try:
        with Image.open(path) as img:
            rgb = np.asarray(img.convert("RGB"), dtype=np.uint8)
            metrics["nonblack_pixels"] = int(np.count_nonzero(np.any(rgb > 8, axis=2)))
    except Exception as exc:
        metrics["error"] = str(exc)
    return metrics


def _image_delta(before: Path, after: Path) -> dict[str, Any]:
    try:
        with Image.open(before) as left, Image.open(after) as right:
            left = left.convert("RGB")
            right = right.convert("RGB")
            if left.size != right.size:
                return {"checked": False, "reason": "size_mismatch"}
            arr = np.asarray(ImageChops.difference(left, right), dtype=np.uint8)
            changed = np.any(arr > 10, axis=2)
            return {
                "checked": True,
                "changed_pixels": int(np.count_nonzero(changed)),
                "mean_abs_delta": round(float(arr.mean()), 4),
                "max_delta": int(arr.max()),
                "visible_delta": bool(np.count_nonzero(changed) > 250),
            }
    except Exception as exc:
        return {"checked": False, "reason": str(exc)}


def _tag_pose_source(pose, model):
    if pose is None:
        return pose
    try:
        setattr(pose, "_gr_animation_source_model_id", id(model) if model is not None else 0)
        setattr(pose, "_gr_animation_source_model_name", str(getattr(model, "name", "") or ""))
    except Exception:
        pass
    return pose


def _head_attachment_root(model):
    if model is None:
        return None
    try:
        nodes = model.all_nodes()
    except Exception:
        nodes = []
    return next(
        (
            node
            for node in nodes
            if bool(getattr(node, "_gr_bas_attachment_root", False))
            and str(getattr(node, "_gr_bas_attachment_slot", "") or "").lower() == "head"
        ),
        None,
    )


def _has_node_named(model, name: str) -> bool:
    wanted = str(name or "").strip().lower()
    if not wanted or model is None:
        return False
    try:
        nodes = model.all_nodes()
    except Exception:
        nodes = []
    return any(str(getattr(node, "name", "") or "").strip().lower() == wanted for node in nodes)


def _orbit_delta_summary(item: dict[str, Any]) -> dict[str, Any]:
    orbit = (((item.get("screenshots") or {}).get("orbit")) or {})
    summary = {}
    for name, shots in orbit.items():
        delta = (shots or {}).get("delta") or {}
        summary[name] = {
            "visible_delta": delta.get("visible_delta"),
            "changed_pixels": delta.get("changed_pixels"),
            "mean_abs_delta": delta.get("mean_abs_delta"),
            "max_delta": delta.get("max_delta"),
        }
    return summary


def _load_window_model(window, model, game: str) -> None:
    window._current_model = model
    window._current_game = game
    window._bas_body_model = model
    window.viewport.set_resource_manager(window._get_resource_manager(), game)
    window.viewport.load_model(model)
    if hasattr(window, "animations_panel"):
        window._load_animation_panel_model(model)
    if hasattr(window, "body_attachment_panel"):
        window.body_attachment_panel.set_body_model(model)


def _wait_for_startup_idle(window, app, timeout: float = 30.0) -> dict[str, Any]:
    deadline = time.perf_counter() + max(0.0, float(timeout))
    while time.perf_counter() < deadline:
        _process_events(app, 0.1)
        busy = {
            "scan_worker": bool(getattr(window, "_scan_worker", None)),
            "auto_detect_worker": bool(getattr(window, "_auto_detect_worker", None)),
            "model_worker": bool(getattr(window, "_model_worker", None)),
            "theme_progress_suppressed": bool(getattr(window, "_suppress_theme_progress_toast", False)),
        }
        if not any(value for key, value in busy.items() if key != "theme_progress_suppressed"):
            _process_events(app, 0.75)
            return {"idle": True, **busy}
    return {
        "idle": False,
        "scan_worker": bool(getattr(window, "_scan_worker", None)),
        "auto_detect_worker": bool(getattr(window, "_auto_detect_worker", None)),
        "model_worker": bool(getattr(window, "_model_worker", None)),
    }


def _drive_window_animation(
    window,
    app,
    viewport_model,
    animation_model,
    animation: str,
    label: str,
    output_dir: Path,
    *,
    focus_node=None,
) -> dict[str, Any]:
    from src.core.animation.animation_engine import AnimationEngine

    viewport = window.viewport
    engine = AnimationEngine(animation_model)
    if not engine.play(animation, loop=True, blend=False):
        return {"label": label, "status": "failed_to_play", "animation": animation}
    pose0 = _tag_pose_source(engine.evaluate(0.0), animation_model)
    length = float(getattr(engine.current_animation, "length", 0.0) or 0.0)
    sample_t, best_delta = _best_sample_time(engine, pose0, length)
    pose1 = _tag_pose_source(engine.evaluate(sample_t), animation_model)
    if focus_node is not None:
        _set_camera_orbit(viewport, focus_node, model=viewport_model, anim_pose=pose0, fov=46.0, azimuth=90.0, elevation=8.0)
    viewport.set_render_mode("realistic")
    viewport.toggle_texture(True)
    viewport.set_anim_base_pose(pose0)
    viewport.set_animation_playback_active(True, f"{label} app playback")
    viewport.set_animation_pose(pose0, name=animation, time=0.0, length=length)
    _force_app_render(window, app, f"{label} pose0", animation=True, overlay=True, hud=True)
    pose0_path = output_dir / f"{label}_app_pose0.png"
    pose0_shot = _screen_grab(app, window, pose0_path)
    viewport.set_animation_pose(pose1, name=animation, time=sample_t, length=length)
    render_times: list[float] = []
    for _ in range(10):
        _force_app_render(window, app, f"{label} app pose1", animation=True)
        ms = float(getattr(viewport, "_last_render_ms", 0.0) or 0.0)
        if ms > 0.0:
            render_times.append(ms)
    pose1_path = output_dir / f"{label}_app_pose1.png"
    pose1_shot = _screen_grab(app, window, pose1_path)
    orbit_shots = {}
    if focus_node is not None:
        for orbit_name, azimuth, elevation in (
            ("front", 90.0, 6.0),
            ("left_3q", 135.0, 8.0),
            ("side", 180.0, 8.0),
            ("right_3q", 45.0, 8.0),
        ):
            _set_camera_orbit(viewport, focus_node, model=viewport_model, anim_pose=pose0, fov=46.0, azimuth=azimuth, elevation=elevation)
            viewport.set_animation_pose(pose0, name=animation, time=0.0, length=length)
            _force_app_render(window, app, f"{label} app orbit {orbit_name} pose0", camera=True, animation=True, overlay=True, hud=True)
            orbit0_path = output_dir / f"{label}_app_orbit_{orbit_name}_pose0.png"
            orbit0 = _screen_grab(app, window, orbit0_path)
            viewport.set_animation_pose(pose1, name=animation, time=sample_t, length=length)
            _force_app_render(window, app, f"{label} app orbit {orbit_name} pose1", camera=True, animation=True, overlay=True, hud=True)
            orbit1_path = output_dir / f"{label}_app_orbit_{orbit_name}_pose1.png"
            orbit1 = _screen_grab(app, window, orbit1_path)
            orbit_shots[orbit_name] = {
                "pose0": orbit0,
                "pose1": orbit1,
                "delta": _image_delta(orbit0_path, orbit1_path),
            }
    shader_shots = {}
    for shader in ("realistic", "shaded", "flat"):
        viewport.set_render_mode(shader)
        viewport.toggle_texture(True)
        _force_app_render(window, app, f"{label} app {shader}", style=True, animation=True, overlay=True, hud=True)
        shader_shots[shader] = _screen_grab(app, window, output_dir / f"{label}_app_{shader}_textured.png")
    viewport.set_animation_playback_active(False)
    avg = float(sum(render_times) / len(render_times)) if render_times else 0.0
    return {
        "label": label,
        "status": "OK",
        "model": str(getattr(viewport_model, "name", "")),
        "animation_source_model": str(getattr(animation_model, "name", "")),
        "animation": animation,
        "sample_time": sample_t,
        "pose_delta": _pose_delta(pose0, pose1),
        "best_pose_delta": best_delta,
        "screenshots": {"pose0": pose0_shot, "pose1": pose1_shot, "shader_cycle": shader_shots, "orbit": orbit_shots},
        "image_delta": _image_delta(pose0_path, pose1_path),
        "shader_cycle": ["realistic", "shaded", "flat"],
        "texture_button": True,
        "render_times_ms": [round(v, 3) for v in render_times],
        "avg_render_ms": round(avg, 3) if avg else None,
        "render_budget_fps": round(1000.0 / avg, 2) if avg > 0.0 else None,
        "mesh_cache": _mesh_cache_metrics(viewport),
        "face_part_deltas": _face_part_deltas(viewport_model, pose0, pose1, focus_node=focus_node),
        "render_state": window.viewport.render_state_status_text(),
    }


def _set_camera_orbit(viewport, node, *, model=None, anim_pose=None, fov: float, azimuth: float, elevation: float) -> None:
    center, radius = _visible_model_bounds(model, anim_pose=anim_pose)
    if center is None:
        center, radius = _visible_subtree_bounds(model, node, anim_pose=anim_pose)
    if center is None:
        _focus_camera_on_node(viewport, node, distance=1.35)
    else:
        viewport.camera.target = [float(center[0]), float(center[1]), float(center[2]) + float(radius) * 0.12]
        viewport.camera.distance = max(2.25, min(8.0, float(radius) * 5.1))
    try:
        viewport.camera.fov = float(fov)
    except Exception:
        pass
    viewport.camera.azimuth = float(azimuth)
    viewport.camera.elevation = float(elevation)
    try:
        viewport.camera._sync_close_clip_plane()
    except Exception:
        pass


def _visible_model_bounds(model, *, anim_pose=None):
    return _visible_subtree_bounds(model, None, anim_pose=anim_pose)


def _visible_subtree_bounds(model, root, *, anim_pose=None):
    if model is None:
        return None, 0.0
    descendants = set()
    if root is not None:
        stack = [root]
        while stack:
            current = stack.pop()
            if current is None or id(current) in descendants:
                continue
            descendants.add(id(current))
            stack.extend(list(getattr(current, "children", []) or []))
    points = []
    try:
        from src.core.rendering.mesh_render_data import iter_mesh_render_data

        for mesh_data in iter_mesh_render_data(model, anim_pose=anim_pose, allow_cpu_skinning=False):
            source = getattr(mesh_data, "source", None)
            if descendants and id(source) not in descendants:
                continue
            positions = getattr(mesh_data, "positions", None)
            if positions is None:
                continue
            pos = np.asarray(positions, dtype=np.float32).reshape((-1, 3))
            if pos.size == 0:
                continue
            matrix = np.asarray(getattr(mesh_data, "world_matrix", np.eye(4)), dtype=np.float32).reshape((4, 4))
            hom = np.concatenate([pos, np.ones((pos.shape[0], 1), dtype=np.float32)], axis=1)
            world = (hom @ matrix.T)[:, :3]
            finite = np.isfinite(world).all(axis=1)
            if np.any(finite):
                points.append(world[finite])
    except Exception:
        points = []
    if not points:
        return None, 0.0
    all_points = np.concatenate(points, axis=0)
    bb_min = all_points.min(axis=0)
    bb_max = all_points.max(axis=0)
    center = (bb_min + bb_max) * 0.5
    radius = float(np.linalg.norm(bb_max - bb_min) * 0.5)
    return center, radius


def _face_part_deltas(model, pose0, pose1, *, focus_node=None) -> list[dict[str, Any]]:
    if model is None or pose0 is None or pose1 is None:
        return []
    try:
        from src.core.rendering.mesh_render_data import mesh_model_matrix_for_node
    except Exception:
        return []
    tokens = ("eye", "teeth", "tooth", "tong", "lip", "jaw", "brow", "cheek")
    focus_ids = set()
    if focus_node is not None:
        stack = [focus_node]
        while stack:
            current = stack.pop()
            if current is None or id(current) in focus_ids:
                continue
            focus_ids.add(id(current))
            stack.extend(getattr(current, "children", []) or [])
    rows = []
    try:
        nodes = list(model.all_nodes())
    except Exception:
        nodes = []
    for node in nodes:
        if focus_ids and id(node) not in focus_ids:
            continue
        name = str(getattr(node, "name", "") or "")
        lower = name.lower()
        if not any(token in lower for token in tokens):
            continue
        if len(getattr(node, "vertices", getattr(node, "verts", [])) or []) <= 0:
            continue
        try:
            m0 = mesh_model_matrix_for_node(node, anim_pose=pose0)
            m1 = mesh_model_matrix_for_node(node, anim_pose=pose1)
            delta = float(np.max(np.abs(np.asarray(m1, dtype=np.float32) - np.asarray(m0, dtype=np.float32))))
            t_delta = float(np.sum(np.abs(np.asarray(m1[:3, 3], dtype=np.float32) - np.asarray(m0[:3, 3], dtype=np.float32))))
        except Exception:
            continue
        rows.append(
            {
                "name": name,
                "is_skin": bool(getattr(node, "is_skin", False)),
                "vertices": len(getattr(node, "vertices", getattr(node, "verts", [])) or []),
                "matrix_max_delta": round(delta, 6),
                "translation_delta": round(t_delta, 6),
            }
        )
    rows.sort(key=lambda item: (0 if item["matrix_max_delta"] > 1.0e-5 else 1, item["name"].lower()))
    return rows[:20]


def run(output_dir: Path, *, bas_only: bool = False) -> dict[str, Any]:
    from PySide6 import QtWidgets

    from src.core.animation.animation_engine import SuperModelResolver
    from src.core.rendering.renderer_backend import RendererBackend
    from src.core.rendering.renderer_settings import RendererSettings
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    manager = _make_resource_manager()
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(manager)
    startup_input = {
        "preloaded_library": {
            "k1_dir": os.environ.get("K1_PATH", ""),
            "k2_dir": os.environ.get("K2_PATH", ""),
            "rows": [],
            "_resource_manager": manager,
            "autoscan": False,
            "detection_attempted": True,
            "detected": False,
            "error": "",
        }
    }
    window = QtGhostRiggerMainWindow(app_root=ROOT, startup_input=startup_input)
    window._resource_manager = manager
    window._resource_manager_dirs = (os.environ.get("K1_PATH", ""), os.environ.get("K2_PATH", ""))
    window.resize(1500, 950)
    window.show()
    startup_state = _wait_for_startup_idle(window, app, timeout=45.0)
    window.viewport.set_renderer_settings(
        RendererSettings(
            backend=RendererBackend.PYGFX_WGPU,
            preferred_windows_backend=RendererBackend.WGPU_D3D12,
            allow_fallback=False,
            target_fps=60,
            idle_render_mode="continuous",
            show_renderer_diagnostics=False,
        )
    )
    window.viewport.set_render_mode("realistic")
    window.viewport.toggle_texture(True)
    window.viewport.toggle_bones(False)
    _process_events(app, 0.5)

    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    def write_progress() -> None:
        summary = []
        for item in results:
            cache = item.get("mesh_cache") or {}
            summary.append(
                {
                    "label": item.get("label"),
                    "status": item.get("status"),
                    "animation": item.get("animation"),
                    "shader_cycle": item.get("shader_cycle"),
                    "texture_button": item.get("texture_button"),
                    "visible_delta": (item.get("image_delta") or {}).get("visible_delta"),
                    "changed_pixels": (item.get("image_delta") or {}).get("changed_pixels"),
                    "pose_delta": item.get("pose_delta"),
                    "render_budget_fps": item.get("render_budget_fps"),
                    "backend": cache.get("backend"),
                    "skinned_records": cache.get("skinned_records"),
                    "native_skinned_mesh_records": cache.get("native_skinned_mesh_records"),
                    "skinned_records_with_diffuse_maps": cache.get("skinned_records_with_diffuse_maps"),
                    "moving_face_parts": sum(
                        1
                        for row in (item.get("face_part_deltas") or [])
                        if float(row.get("matrix_max_delta", 0.0) or 0.0) > 1.0e-5
                    ),
                    "orbit_deltas": _orbit_delta_summary(item),
                    "render_state": item.get("render_state"),
                }
            )
        (output_dir / "actual_app_pygfx_animation_results.partial.json").write_text(
            json.dumps(results, indent=2),
            encoding="utf-8",
        )
        (output_dir / "actual_app_pygfx_animation_summary.partial.json").write_text(
            json.dumps(summary, indent=2),
            encoding="utf-8",
        )

    if not bas_only:
        fixtures = [
            ("K2", "n_darthmalak", "n_malak_alias_app_walk", ["walk", "g2r1"], None),
            ("K1", "p_carthbb", "p_carthbb_app_inherited_walk", ["walk"], True),
            ("K1", "p_carthbb", "p_carthbb_app_local_pause2", ["pause2"], False),
            ("K1", "n_bith", "n_bith_app_local_walk", ["walk"], False),
            ("K1", "n_bith", "n_bith_app_inherited_pause3", ["pause3"], True),
        ]
        for game, resref, label, preferred, inherited in fixtures:
            model = manager.load_model(resref, game)
            if model is None:
                results.append({"label": label, "status": "model_not_found"})
                write_progress()
                continue
            _load_window_model(window, model, game)
            window.viewport.set_render_mode("realistic")
            window.viewport.toggle_texture(True)
            window.viewport.toggle_bones(False)
            _force_app_render(window, app, f"{label} load", scene=True, resources=True, style=True, overlay=True, hud=True)
            anim = _choose_animation(model, preferred, game, inherited=inherited)
            try:
                results.append(_drive_window_animation(window, app, model, model, anim, label, output_dir))
            except Exception as exc:
                results.append({"label": label, "status": "exception", "error": repr(exc)})
            write_progress()

    body = manager.load_model("p_carthbb", "K1")
    head = manager.load_model("p_carthbbh", "K1")
    if body is not None and head is not None:
        _load_window_model(window, body, "K1")
        window._bas_body_model = body
        window._bas_attachments = {}
        window._bas_attachment_resrefs = {}
        window._bas_attachment_transforms = {}
        window._handle_bas_attach_requested("head", "p_carthbbh")
        head = getattr(window, "_current_head_model", None) or head
        bas_model = window._bas_preview_model
        _force_app_render(window, app, "bas app load", scene=True, resources=True, style=True, overlay=True, hud=True)
        body_anim = _choose_animation(body, ["walk"], "K1", inherited=True)
        if body_anim:
            try:
                results.append(_drive_window_animation(window, app, bas_model, body, body_anim, "bas_app_p_carthbb_head_body_walk", output_dir))
            except Exception as exc:
                results.append({"label": "bas_app_p_carthbb_head_body_walk", "status": "exception", "error": repr(exc)})
            write_progress()
        head_anim = _choose_animation(head, ["talk"], "K1", inherited=False)
        focus_node = _head_attachment_root(bas_model)
        if head_anim:
            try:
                results.append(
                    _drive_window_animation(
                        window,
                        app,
                        bas_model,
                        head,
                        head_anim,
                        "bas_app_p_carthbbh_head_local_talk",
                        output_dir,
                        focus_node=focus_node,
                    )
                )
            except Exception as exc:
                results.append({"label": "bas_app_p_carthbbh_head_local_talk", "status": "exception", "error": repr(exc)})
            write_progress()

    extra_head_fixtures = [
        ("p_bastilah", [["talk", "tlknorm", "listen"], ["pause1", "pause2"]], {"right_weapon": "w_blstrrfl_001", "belt": "i_belt_001"}),
        ("p_missionh", [["talk", "tlknorm", "listen"], ["pause1", "pause2"]], {"left_weapon": "w_blstrpstl_001"}),
        ("p_candh", [["talk", "tlknorm", "listen"], ["pause1", "pause2"]], {"belt": "i_belt_001"}),
        ("p_juhanih", [["talk", "tlknorm", "listen"], ["pause1", "pause2"]], {"right_weapon": "w_vbroshort_001"}),
    ]
    for head_resref, animation_groups, extra_attachments in extra_head_fixtures:
        body = manager.load_model("p_carthbb", "K1")
        head = manager.load_model(head_resref, "K1")
        if body is None or head is None:
            results.append({"label": f"bas_app_p_carthbb_{head_resref}_head_cycle", "status": "model_not_found"})
            write_progress()
            continue
        try:
            _load_window_model(window, body, "K1")
            window._bas_body_model = body
            window._bas_attachments = {}
            window._bas_attachment_resrefs = {}
            window._bas_attachment_transforms = {}
            window._handle_bas_attach_requested("head", head_resref)
            head = getattr(window, "_current_head_model", None) or head
            for slot, resref in extra_attachments.items():
                if slot == "belt" and not _has_node_named(body, "pelvis_g"):
                    continue
                window._handle_bas_attach_requested(slot, resref)
            bas_model = window._bas_preview_model
            if hasattr(window, "animations_panel"):
                window.animations_panel.set_animation_source("head")
                window._load_animation_panel_model(body)
            _force_app_render(window, app, f"{head_resref} bas app load", scene=True, resources=True, style=True, overlay=True, hud=True)
            focus_node = _head_attachment_root(bas_model)
            seen_anims = set()
            for preferred in animation_groups:
                head_anim = _choose_animation(head, preferred, "K1", inherited=False)
                if not head_anim or head_anim in seen_anims:
                    continue
                seen_anims.add(head_anim)
                if hasattr(window, "animations_panel"):
                    window.animations_panel.select_animation(head_anim)
                results.append(
                    _drive_window_animation(
                        window,
                        app,
                        bas_model,
                        head,
                        head_anim,
                        f"bas_app_p_carthbb_{head_resref}_head_{head_anim}",
                        output_dir,
                        focus_node=focus_node,
                    )
                )
            if not seen_anims:
                results.append({"label": f"bas_app_p_carthbb_{head_resref}_head_cycle", "status": "animation_not_found"})
        except Exception as exc:
            results.append({"label": f"bas_app_p_carthbb_{head_resref}_head_cycle", "status": "exception", "error": repr(exc)})
        write_progress()

    summary = []
    for item in results:
        cache = item.get("mesh_cache") or {}
        summary.append(
            {
                "label": item.get("label"),
                "status": item.get("status"),
                "animation": item.get("animation"),
                "shader_cycle": item.get("shader_cycle"),
                "texture_button": item.get("texture_button"),
                "visible_delta": (item.get("image_delta") or {}).get("visible_delta"),
                "changed_pixels": (item.get("image_delta") or {}).get("changed_pixels"),
                "pose_delta": item.get("pose_delta"),
                "render_budget_fps": item.get("render_budget_fps"),
                "backend": cache.get("backend"),
                "skinned_records": cache.get("skinned_records"),
                "native_skinned_mesh_records": cache.get("native_skinned_mesh_records"),
                "skinned_records_with_diffuse_maps": cache.get("skinned_records_with_diffuse_maps"),
                "moving_face_parts": sum(
                    1
                    for row in (item.get("face_part_deltas") or [])
                    if float(row.get("matrix_max_delta", 0.0) or 0.0) > 1.0e-5
                ),
                "orbit_deltas": _orbit_delta_summary(item),
                "render_state": item.get("render_state"),
            }
        )
    payload = {
        "output_dir": str(output_dir),
        "actual_application": True,
        "startup_state": startup_state,
        "backend": "pygfx_wgpu",
        "render_modes": ["realistic", "shaded", "flat"],
        "texture_visible": True,
        "results": results,
        "summary": summary,
    }
    (output_dir / "actual_app_pygfx_animation_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (output_dir / "actual_app_pygfx_animation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    window.close()
    _process_events(app, 0.2)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Actual GhostRigger app pygfx animation visual harness.")
    parser.add_argument("--output-dir", default=str(ROOT / "artifacts" / "actual_app_pygfx_animation_20260602"))
    parser.add_argument("--bas-only", action="store_true", help="Skip standalone fixtures and run only BAS animation coverage.")
    args = parser.parse_args()
    payload = run(Path(args.output_dir), bas_only=bool(args.bas_only))
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
