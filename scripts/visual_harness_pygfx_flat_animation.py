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


def _seed_paths() -> None:
    try:
        from kotormcp.tools.ghostrigger_tools import _load_local_game_paths

        _load_local_game_paths()
    except Exception:
        pass


def _make_resource_manager():
    from src.core.assets.resource_manager import ResourceManager

    _seed_paths()
    manager = ResourceManager()
    if os.environ.get("K1_PATH"):
        manager.set_k1_dir(os.environ["K1_PATH"])
    if os.environ.get("K2_PATH"):
        manager.set_k2_dir(os.environ["K2_PATH"])
    return manager


def _process_events(app, seconds: float = 0.2) -> None:
    deadline = time.perf_counter() + max(0.0, float(seconds))
    while time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.01)


def _force_render(viewport, app, reason: str = "harness", **dirty_flags: bool) -> None:
    if not dirty_flags:
        dirty_flags = {"animation": True, "overlay": True, "hud": True}
    viewport._request_render(fast=True, reason=reason, **dirty_flags)
    for _ in range(6):
        _process_events(app, 0.08)
        try:
            viewport._render_now()
        except Exception:
            pass
        _process_events(app, 0.08)


def _grab_widget(widget, path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap = widget.grab()
    ok = pixmap.save(str(path))
    metrics = {"path": str(path), "saved": bool(ok), "width": int(pixmap.width()), "height": int(pixmap.height())}
    try:
        with Image.open(path) as img:
            rgba = img.convert("RGBA")
            alpha = np.asarray(rgba.getchannel("A"), dtype=np.uint8)
            rgb = np.asarray(rgba.convert("RGB"), dtype=np.uint8)
            metrics["nontransparent_pixels"] = int(np.count_nonzero(alpha))
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
                return {"checked": False, "reason": "size_mismatch", "left": left.size, "right": right.size}
            diff = ImageChops.difference(left, right)
            arr = np.asarray(diff, dtype=np.uint8)
            changed = np.any(arr > 10, axis=2)
            bbox = diff.getbbox()
            return {
                "checked": True,
                "changed_pixels": int(np.count_nonzero(changed)),
                "mean_abs_delta": round(float(arr.mean()), 4),
                "max_delta": int(arr.max()),
                "bbox": list(bbox) if bbox else None,
                "visible_delta": bool(np.count_nonzero(changed) > 250),
            }
    except Exception as exc:
        return {"checked": False, "reason": str(exc)}


def _mesh_cache_metrics(viewport) -> dict[str, Any]:
    renderer = getattr(viewport, "_gpu_renderer", None)
    records = list(getattr(getattr(renderer, "mesh_cache", None), "records", {}).values()) if renderer is not None else []
    skinned = [record for record in records if bool(getattr(record, "is_skinned", False))]
    native = [record for record in skinned if type(getattr(record, "mesh", None)).__name__ == "SkinnedMesh"]
    with_skin_buffers = []
    with_diffuse_maps = []
    skeleton_updates = 0
    palette_non_identity = 0
    for record in skinned:
        if getattr(record, "diffuse_map", None) is not None:
            with_diffuse_maps.append(record)
        geometry = getattr(record, "geometry", None)
        has_indices = getattr(geometry, "skin_indices", None) is not None
        has_weights = getattr(geometry, "skin_weights", None) is not None
        if has_indices and has_weights:
            with_skin_buffers.append(record)
        skeleton = getattr(record, "skeleton", None)
        data = getattr(getattr(skeleton, "bone_matrices_buffer", None), "data", None)
        if data is not None:
            try:
                skeleton_updates += 1
                matrices = np.asarray(data["bone_matrices"], dtype=np.float32)
                identity = np.eye(4, dtype=np.float32)
                if any(float(np.max(np.abs(m - identity))) > 1e-4 for m in matrices[: min(len(matrices), 32)]):
                    palette_non_identity += 1
            except Exception:
                pass
    diag = renderer.get_diagnostics() if renderer is not None and hasattr(renderer, "get_diagnostics") else {}
    return {
        "backend": str(getattr(renderer, "backend_id", "")) if renderer is not None else "",
        "mesh_records": len(records),
        "skinned_records": len(skinned),
        "native_skinned_mesh_records": len(native),
        "skinned_records_with_skin_buffers": len(with_skin_buffers),
        "skinned_records_with_diffuse_maps": len(with_diffuse_maps),
        "skeleton_buffers_seen": skeleton_updates,
        "non_identity_skin_palettes": palette_non_identity,
        "diagnostics": diag,
    }


def _choose_animation(model, preferred: list[str], game: str, *, inherited: bool | None = None) -> str:
    from src.core.animation.animation_engine import AnimationEngine

    engine = AnimationEngine(model)
    entries = engine.list_all_animations()
    by_name = {str(entry.get("name") or "").lower(): entry for entry in entries}
    for name in preferred:
        entry = by_name.get(name.lower())
        if entry is None:
            continue
        if inherited is None or bool(entry.get("inherited")) == inherited:
            return str(entry.get("name") or name)
    for entry in entries:
        if inherited is None or bool(entry.get("inherited")) == inherited:
            return str(entry.get("name") or "")
    return ""


def _pose_delta(pose0, pose1) -> dict[str, Any]:
    best = {"node": "", "score": 0.0, "position_delta": 0.0, "rotation_delta": 0.0}
    nodes0 = getattr(pose0, "nodes", {}) or {}
    nodes1 = getattr(pose1, "nodes", {}) or {}
    total = 0.0
    count = 0
    for name, node1 in nodes1.items():
        node0 = nodes0.get(name)
        if node0 is None:
            continue
        try:
            pd = sum(abs(float(a) - float(b)) for a, b in zip(node1.position, node0.position))
            rd = sum(abs(float(a) - float(b)) for a, b in zip(node1.rotation, node0.rotation))
        except Exception:
            continue
        score = float(pd + rd)
        total += score
        count += 1
        if score > best["score"]:
            best = {"node": str(name), "score": round(score, 6), "position_delta": round(float(pd), 6), "rotation_delta": round(float(rd), 6)}
    return {"max": best, "total_score": round(total, 6), "node_count": count}


def _best_sample_time(engine, pose0, length: float) -> tuple[float, dict[str, Any]]:
    if length <= 0.0:
        return 0.35, {"max": {"score": 0.0}}
    best_t = max(0.08, min(length * 0.45, 0.75))
    best_delta = {"max": {"score": -1.0}}
    for idx in range(1, 10):
        t = float(length) * idx / 10.0
        delta = _pose_delta(pose0, engine.evaluate(t))
        if float(delta.get("max", {}).get("score", 0.0) or 0.0) > float(best_delta.get("max", {}).get("score", -1.0) or -1.0):
            best_delta = delta
            best_t = t
    return best_t, best_delta


def _focus_camera_on_node(viewport, node, *, distance: float = 1.35) -> None:
    if node is None:
        return
    try:
        pos = tuple(float(v) for v in node.world_position()[:3])
    except Exception:
        try:
            pos = tuple(float(v) for v in getattr(node, "position", (0.0, 0.0, 0.0))[:3])
        except Exception:
            return
    viewport.camera.target = [pos[0], pos[1], pos[2]]
    viewport.camera.distance = float(distance)
    viewport.camera.azimuth = 90.0
    viewport.camera.elevation = 10.0
    try:
        viewport.camera._sync_close_clip_plane()
    except Exception:
        pass


def _drive_animation(
    viewport,
    app,
    viewport_model,
    animation: str,
    game: str,
    output_dir: Path,
    label: str,
    *,
    animation_model=None,
    focus_node=None,
) -> dict[str, Any]:
    from src.core.animation.animation_engine import AnimationEngine

    source_model = animation_model or viewport_model
    engine = AnimationEngine(source_model)
    if not engine.play(animation, loop=True, blend=False):
        return {"label": label, "animation": animation, "status": "failed_to_play"}
    pose0 = engine.evaluate(0.0)
    length = float(getattr(engine.current_animation, "length", 0.0) or 0.0)
    sample_t, best_delta = _best_sample_time(engine, pose0, length)
    pose1 = engine.evaluate(sample_t)
    pose_delta = _pose_delta(pose0, pose1)
    if focus_node is not None:
        _focus_camera_on_node(viewport, focus_node)
    viewport.set_anim_base_pose(pose0)
    viewport.set_animation_playback_active(True, f"{label} playback")
    shader_shots: dict[str, Any] = {}
    viewport.set_animation_pose(pose0, name=animation, time=0.0, length=length)
    _force_render(viewport, app, f"{label} pose0", animation=True, overlay=True, hud=True)
    still_path = output_dir / f"{label}_flat_pose0.png"
    still = _grab_widget(viewport, still_path)
    viewport.set_animation_pose(pose1, name=animation, time=sample_t, length=length)
    render_times: list[float] = []
    for _ in range(12):
        _force_render(viewport, app, f"{label} animated", animation=True, overlay=True, hud=True)
        render_ms = float(getattr(viewport, "_last_render_ms", 0.0) or 0.0)
        if render_ms > 0:
            render_times.append(render_ms)
    for shader in ("realistic", "shaded", "flat"):
        viewport.set_render_mode(shader)
        viewport.toggle_texture(True)
        _force_render(viewport, app, f"{label} {shader}", style=True, animation=True, overlay=True, hud=True)
        shader_shots[shader] = _grab_widget(viewport, output_dir / f"{label}_{shader}_textured_pose1.png")
    viewport.set_render_mode("flat")
    viewport.toggle_texture(True)
    _force_render(viewport, app, f"{label} flat final", style=True, animation=True, overlay=True, hud=True)
    anim_path = output_dir / f"{label}_flat_pose1.png"
    anim = _grab_widget(viewport, anim_path)
    viewport.set_animation_playback_active(False)
    delta = _image_delta(still_path, anim_path)
    avg = float(sum(render_times) / len(render_times)) if render_times else 0.0
    p95 = float(np.percentile(np.asarray(render_times, dtype=np.float32), 95)) if render_times else 0.0
    return {
        "label": label,
        "game": game,
        "model": str(getattr(viewport_model, "name", "")),
        "animation_source_model": str(getattr(source_model, "name", "")),
        "animation": animation,
        "length": length,
        "sample_time": sample_t,
        "pose_delta": pose_delta,
        "best_pose_delta": best_delta,
        "status": "OK",
        "flat_shader": True,
        "texture_button": True,
        "shader_cycle": tuple(shader_shots.keys()),
        "screenshots": {"pose0": still, "pose1": anim, "shader_cycle": shader_shots},
        "image_delta": delta,
        "render_times_ms": [round(v, 3) for v in render_times],
        "avg_render_ms": round(avg, 3) if avg else None,
        "p95_render_ms": round(p95, 3) if p95 else None,
        "render_budget_fps": round(1000.0 / avg, 2) if avg > 0 else None,
        "mesh_cache": _mesh_cache_metrics(viewport),
    }


def run(output_dir: Path) -> dict[str, Any]:
    from PySide6 import QtWidgets

    from src.core.animation.animation_engine import SuperModelResolver
    from src.core.rendering.renderer_backend import RendererBackend
    from src.core.rendering.renderer_settings import RendererSettings
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget
    from src.systems.bas.preview_composer import build_bas_preview_model

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    manager = _make_resource_manager()
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(manager)

    viewport = QtViewportWidget()
    viewport.resize(1280, 820)
    viewport.set_renderer_settings(
        RendererSettings(
            backend=RendererBackend.PYGFX_WGPU,
            preferred_windows_backend=RendererBackend.WGPU_D3D12,
            allow_fallback=False,
            target_fps=60,
            idle_render_mode="continuous",
            show_renderer_diagnostics=True,
        )
    )
    viewport.set_resource_manager(manager, "K1")
    viewport.set_render_mode("flat")
    viewport.toggle_texture(True)
    viewport.toggle_bones(False)
    viewport.toggle_grid(True)
    viewport.show()
    _process_events(app, 0.5)

    fixtures = [
        ("K2", "n_darthmalak", "n_malak_alias", ["walk", "pause1", "g2r1"], None),
        ("K1", "p_carthbb", "p_carthbb_inherited_walk", ["walk"], True),
        ("K1", "p_carthbb", "p_carthbb_local_pause2", ["pause2"], False),
        ("K1", "n_bith", "n_bith_local_walk", ["walk"], False),
        ("K1", "n_bith", "n_bith_inherited_pause3", ["pause3", "pause4"], True),
    ]
    results: list[dict[str, Any]] = []
    for game, resref, label, preferred, inherited in fixtures:
        model = manager.load_model(resref, game)
        if model is None:
            results.append({"label": label, "game": game, "resref": resref, "status": "model_not_found"})
            continue
        viewport.set_resource_manager(manager, game)
        viewport.load_model(model)
        viewport.set_render_mode("flat")
        viewport.toggle_texture(True)
        viewport.toggle_bones(False)
        _force_render(viewport, app, f"{label} load", scene=True, resources=True, style=True, overlay=True, hud=True)
        animation = _choose_animation(model, preferred, game, inherited=inherited)
        if not animation:
            results.append({"label": label, "game": game, "resref": resref, "status": "animation_not_found"})
            continue
        results.append(_drive_animation(viewport, app, model, animation, game, output_dir, label))

    body = manager.load_model("p_carthbb", "K1")
    head = manager.load_model("p_carthbbh", "K1")
    if body is not None and head is not None:
        bas_model = build_bas_preview_model(
            body_model=body,
            attachment_models={"head": head},
            name="p_carthbb_bas_p_carthbbh",
        )
        viewport.set_resource_manager(manager, "K1")
        viewport.load_model(bas_model)
        viewport.set_render_mode("flat")
        viewport.toggle_texture(True)
        viewport.toggle_bones(False)
        _force_render(viewport, app, "bas load", scene=True, resources=True, style=True, overlay=True, hud=True)
        body_anim = _choose_animation(body, ["walk"], "K1", inherited=True)
        if body_anim:
            results.append(_drive_animation(viewport, app, bas_model, body_anim, "K1", output_dir, "bas_p_carthbb_head_body_walk", animation_model=body))
        head_anim = _choose_animation(head, ["talk", "walk", "pause1"], "K1", inherited=False)
        if head_anim:
            focus_node = next(
                (
                    node
                    for node in bas_model.all_nodes()
                    if bool(getattr(node, "_gr_bas_attachment_root", False))
                    and str(getattr(node, "_gr_bas_attachment_slot", "") or "").lower() == "head"
                ),
                None,
            )
            results.append(
                _drive_animation(
                    viewport,
                    app,
                    bas_model,
                    head_anim,
                    "K1",
                    output_dir,
                    "bas_p_carthbbh_head_local_talk",
                    animation_model=head,
                    focus_node=focus_node,
                )
            )
    else:
        results.append({"label": "bas_p_carthbb_head", "status": "model_not_found"})

    summary = []
    for item in results:
        cache = item.get("mesh_cache") or {}
        summary.append(
            {
                "label": item.get("label"),
                "status": item.get("status"),
                "animation": item.get("animation"),
                "flat_shader": item.get("flat_shader"),
                "shader_cycle": item.get("shader_cycle"),
                "texture_button": item.get("texture_button"),
                "visible_delta": (item.get("image_delta") or {}).get("visible_delta"),
                "changed_pixels": (item.get("image_delta") or {}).get("changed_pixels"),
                "pose_delta": item.get("pose_delta"),
                "render_budget_fps": item.get("render_budget_fps"),
                "skinned_records": cache.get("skinned_records"),
                "native_skinned_mesh_records": cache.get("native_skinned_mesh_records"),
                "skinned_records_with_diffuse_maps": cache.get("skinned_records_with_diffuse_maps"),
                "non_identity_skin_palettes": cache.get("non_identity_skin_palettes"),
            }
        )
    payload = {
        "output_dir": str(output_dir),
        "backend": "pygfx_wgpu",
        "render_modes": ["realistic", "shaded", "flat"],
        "bones_visible": False,
        "texture_visible": True,
        "fixtures": results,
        "summary": summary,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "flat_animation_harness_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (output_dir / "flat_animation_harness_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    viewport.close()
    _process_events(app, 0.1)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Visible flat-shader pygfx animation harness.")
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "artifacts" / "visual_harness_pygfx_flat_animation"),
        help="Directory for screenshots and JSON reports.",
    )
    args = parser.parse_args()
    payload = run(Path(args.output_dir))
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
