"""Audit and capture the Peragus custom-uniform Character Builder proof.

This focused harness reloads the exported K2 MDL/MDX pairs, verifies the
Odyssey skin-palette contracts, evaluates the inherited walk animation, grafts
stock heads through the Body Attachment System, and captures the live WGPU
D3D12 viewport.  It never writes to the game's Override directory; the two
custom texture paths are registered with the in-memory resource index.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(list(_python_roots(ROOT))):
        text = str(item)
        if Path(text).exists() and text not in sys.path:
            sys.path.insert(0, text)
except Exception:  # pragma: no cover - standalone fallback
    for relative in (
        "native/GhostRigger.Core.Workflow/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Resources/Python",
        "native/GhostRigger.Core.IO/Python",
        "native/GhostRigger.Core.Rendering/Python",
        "native/GhostRigger.Core.GUI.Display/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Tools/Python",
    ):
        path = str(ROOT / relative)
        if path not in sys.path:
            sys.path.insert(0, path)


DEFAULT_PROOF_DIR = Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\MyMods\BetterArmor\Redesigns"
    r"\PeragusMiningUniform\CharacterBuilderProof"
)
DEFAULT_K2_DIR = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"
)

FIXTURES = (
    {
        "artifact": "pfbc09",
        "stock": "PFBCM",
        "head": "PFHC01",
        "texture": "PFBC09_basecolor.tga",
        "supermodel": "S_Female03",
        "headhook_lowering_m": 0.035,
        "headhook_forward_m": 0.010,
    },
    {
        "artifact": "pmbc09",
        "stock": "PMBCM",
        "head": "PMHC01",
        "texture": "PMBC09_basecolor.tga",
        "supermodel": "S_Female02",
        "headhook_lowering_m": 0.035,
        "headhook_forward_m": 0.020,
    },
)


def _round_vector(values: Any) -> list[float]:
    return [round(float(value), 8) for value in values]


def _bounds(points: list[np.ndarray]) -> dict[str, Any]:
    if not points:
        return {"min": [], "max": [], "extent": [], "center": [], "vertex_rows": 0}
    array = np.concatenate(points, axis=0)
    low = np.min(array, axis=0)
    high = np.max(array, axis=0)
    return {
        "min": _round_vector(low),
        "max": _round_vector(high),
        "extent": _round_vector(high - low),
        "center": _round_vector((low + high) * 0.5),
        "vertex_rows": int(array.shape[0]),
    }


def _skin_nodes(model: Any) -> list[Any]:
    return [
        node
        for node in model.all_nodes()
        if bool(getattr(node, "is_skin", False))
        and bool(getattr(node, "vertices", None))
        and bool(getattr(node, "skin_data", None))
        and bool(getattr(node, "bone_map", None))
    ]


def _weight_audit(parts: list[Any]) -> dict[str, Any]:
    checked = 0
    unnormalized = 0
    too_many = 0
    invalid_indices = 0
    zero_weight = 0
    max_sum_error = 0.0
    max_influences = 0
    for part in parts:
        palette_size = len(list(getattr(part, "bone_map", []) or []))
        for row in list(getattr(part, "skin_data", []) or []):
            influences = list(getattr(row, "influences", []) or [])
            positive = [
                influence
                for influence in influences
                if float(getattr(influence, "weight", 0.0) or 0.0) > 1.0e-9
            ]
            total = sum(float(getattr(item, "weight", 0.0) or 0.0) for item in positive)
            checked += 1
            max_influences = max(max_influences, len(positive))
            max_sum_error = max(max_sum_error, abs(1.0 - total))
            if not positive:
                zero_weight += 1
            if abs(1.0 - total) > 1.0e-5:
                unnormalized += 1
            if len(positive) > 4:
                too_many += 1
            if any(
                int(getattr(item, "bone_index", -1)) < 0
                or int(getattr(item, "bone_index", -1)) >= palette_size
                for item in positive
            ):
                invalid_indices += 1
    return {
        "checked_vertices": checked,
        "max_influences": max_influences,
        "max_weight_sum_error": max_sum_error,
        "unnormalized_vertices": unnormalized,
        "too_many_influences": too_many,
        "invalid_palette_indices": invalid_indices,
        "zero_weight_vertices": zero_weight,
        "status": "pass"
        if not (unnormalized or too_many or invalid_indices or zero_weight)
        else "fail",
    }


def _bind_collapse_audit(model: Any, parts: list[Any]) -> dict[str, Any]:
    from src.core.animation.gpu_skinning import MatrixPaletteUploader
    from src.core.characters import headless_body_workflow as workflow
    from src.math.gpu_math import _matrix_from_pos_quat_np

    nodes = list(model.all_nodes())
    last_id_by_name = {
        str(getattr(node, "name", "") or "").strip().lower(): index
        for index, node in enumerate(nodes)
        if str(getattr(node, "name", "") or "").strip()
    }
    checked = 0
    max_error = 0.0
    failures: list[dict[str, Any]] = []
    for part in parts:
        skin_position, skin_rotation = workflow._node_skin_palette_world_transform(part)
        skin_world = _matrix_from_pos_quat_np(skin_position, skin_rotation)
        qbones = list(getattr(part, "qbone_list", []) or [])
        tbones = list(getattr(part, "tbone_list", []) or [])
        recorded_ids = list(getattr(part, "bone_node_indices", []) or [])
        compact_rows = len(qbones) == len(list(getattr(part, "bone_map", []) or []))
        for slot, raw_name in enumerate(list(getattr(part, "bone_map", []) or [])):
            name = str(raw_name or "").strip()
            node_id = -1
            if slot < len(recorded_ids):
                try:
                    node_id = int(recorded_ids[slot])
                except (TypeError, ValueError):
                    node_id = -1
            if not (0 <= node_id < len(nodes)):
                node_id = int(last_id_by_name.get(name.lower(), -1))
            if not (0 <= node_id < len(nodes)):
                failures.append({"skin": part.name, "bone": name, "error": "missing node"})
                continue
            row = slot if compact_rows else node_id
            if not (0 <= row < len(qbones) and row < len(tbones)):
                failures.append({"skin": part.name, "bone": name, "error": "missing q/t row"})
                continue
            bone_position, bone_rotation = workflow._node_skin_palette_world_transform(nodes[node_id])
            bone_world = _matrix_from_pos_quat_np(bone_position, bone_rotation)
            inverse_bind = np.asarray(
                MatrixPaletteUploader.qbone_inverse_bind_matrix_g5(qbones[row], tbones[row]),
                dtype=np.float64,
            )
            error = float(np.max(np.abs((bone_world @ inverse_bind) - skin_world)))
            checked += 1
            max_error = max(max_error, error)
            if error > 1.0e-4:
                failures.append({"skin": part.name, "bone": name, "node_id": node_id, "error": error})
    return {
        "checked": checked,
        "max_abs": max_error,
        "failures": failures,
        "status": "pass" if checked and not failures else "fail",
    }


def _deformed_bounds(model: Any, engine: Any, sample_time: float, base_pose: Any) -> dict[str, Any]:
    from src.core.animation.gpu_skinning import MAX_BONES, MatrixPaletteUploader
    from src.core.characters.animation_deformation_validator import (
        _skin_rows_to_arrays,
        _skin_vertices_with_palette,
    )

    pose = engine.evaluate(sample_time)
    points: list[np.ndarray] = []
    for part in _skin_nodes(model):
        vertices = np.asarray(
            [tuple(float(component) for component in vertex[:3]) for vertex in part.vertices],
            dtype=np.float64,
        )
        palette_size = len(list(getattr(part, "bone_map", []) or []))
        weights, indices = _skin_rows_to_arrays(
            list(getattr(part, "skin_data", []) or []),
            int(vertices.shape[0]),
            palette_size,
        )
        uploader = MatrixPaletteUploader(max_bones=max(int(MAX_BONES), palette_size))
        uploader.build_inverse_bind_pose(model)
        points.append(
            _skin_vertices_with_palette(
                uploader=uploader,
                mesh=part,
                pose=pose,
                anim_base_pose=base_pose,
                verts=vertices,
                weights=weights,
                indices=indices,
            )
        )
    return _bounds(points)


def _audit_model(
    model: Any,
    stock: Any,
    *,
    expected_headhook_lowering_m: float = 0.0,
    expected_headhook_forward_m: float = 0.0,
) -> dict[str, Any]:
    from src.core.animation.animation_engine import AnimationEngine

    parts = _skin_nodes(model)
    stock_parts = _skin_nodes(stock)
    engine = AnimationEngine(model)
    stock_engine = AnimationEngine(stock)
    if not engine.play("walk", loop=True, blend=False):
        raise RuntimeError(f"{model.name}: inherited walk did not resolve")
    if not stock_engine.play("walk", loop=True, blend=False):
        raise RuntimeError(f"{stock.name}: stock walk did not resolve")
    length = float(getattr(engine.current_animation, "length", 0.0) or 0.0)
    stock_length = float(getattr(stock_engine.current_animation, "length", 0.0) or 0.0)
    base_pose = engine.evaluate(0.0)
    stock_base_pose = stock_engine.evaluate(0.0)
    sample_fractions = (0.0, 0.25, 0.5, 0.75, 0.9999)
    samples = []
    for fraction in sample_fractions:
        custom_time = min(length, max(0.0, length * fraction))
        stock_time = min(stock_length, max(0.0, stock_length * fraction))
        samples.append(
            {
                "fraction": fraction,
                "custom_time": custom_time,
                "stock_time": stock_time,
                "custom": _deformed_bounds(model, engine, custom_time, base_pose),
                "stock": _deformed_bounds(stock, stock_engine, stock_time, stock_base_pose),
            }
        )
    bind_points = [
        np.asarray([tuple(float(value) for value in vertex[:3]) for vertex in part.vertices], dtype=np.float64)
        for part in parts
    ]
    collapse = _bind_collapse_audit(model, parts)
    weights = _weight_audit(parts)
    hooks = {
        name: any(str(getattr(node, "name", "") or "").lower() == name.lower() for node in model.all_nodes())
        for name in ("headhook", "Lhand", "Rhand", "Lhand_g", "Rhand_g", "camerahook")
    }
    custom_headhook = next(
        (node for node in model.all_nodes() if str(getattr(node, "name", "") or "").lower() == "headhook"),
        None,
    )
    stock_headhook = next(
        (node for node in stock.all_nodes() if str(getattr(node, "name", "") or "").lower() == "headhook"),
        None,
    )
    hook_parity_error = float("inf")
    hook_world_delta: tuple[float, float, float] | None = None
    hook_adjustment_error = float("inf")
    if custom_headhook is not None and stock_headhook is not None:
        custom_hook_values = tuple(float(value) for value in custom_headhook.world_position()[:3])
        stock_hook_values = tuple(float(value) for value in stock_headhook.world_position()[:3])
        hook_world_delta = tuple(
            custom_hook_values[index] - stock_hook_values[index]
            for index in range(3)
        )
        hook_parity_error = max(
            abs(hook_world_delta[index])
            for index in range(3)
        )
        expected_delta = (
            0.0,
            float(expected_headhook_forward_m),
            -float(expected_headhook_lowering_m),
        )
        hook_adjustment_error = max(
            abs(hook_world_delta[index] - expected_delta[index])
            for index in range(3)
        )
    max_palette = max((len(list(getattr(part, "bone_map", []) or [])) for part in parts), default=0)
    extents_pass = all(
        max(sample["custom"]["extent"], default=0.0) < 2.5
        and sample["custom"]["vertex_rows"] > 0
        for sample in samples
    )
    status = (
        "pass"
        if collapse["status"] == "pass"
        and weights["status"] == "pass"
        and max_palette <= 16
        and all(hooks.values())
        and hook_adjustment_error <= 1.0e-5
        and extents_pass
        else "fail"
    )
    return {
        "status": status,
        "model_name": str(getattr(model, "name", "") or ""),
        "supermodel": str(getattr(model, "supermodel", "") or ""),
        "nodes": len(list(model.all_nodes())),
        "skin_nodes": [
            {
                "name": str(getattr(part, "name", "") or ""),
                "palette": len(list(getattr(part, "bone_map", []) or [])),
                "vertices": len(list(getattr(part, "vertices", []) or [])),
                "bone_node_indices": list(getattr(part, "bone_node_indices", []) or []),
            }
            for part in parts
        ],
        "max_palette": max_palette,
        "animation_count": len(engine.list_all_animations()),
        "walk_length": length,
        "bind_collapse": collapse,
        "weights": weights,
        "bind_bounds": _bounds(bind_points),
        "walk_samples": samples,
        "walk_extents_bounded": extents_pass,
        "hooks": hooks,
        "headhook_stock_world_parity_max_abs": hook_parity_error,
        "headhook_expected_lowering_m": float(expected_headhook_lowering_m),
        "headhook_expected_forward_m": float(expected_headhook_forward_m),
        "headhook_world_delta_from_stock": list(hook_world_delta) if hook_world_delta is not None else None,
        "headhook_adjustment_max_abs_error": hook_adjustment_error,
        "stock_reference": {
            "model": str(getattr(stock, "name", "") or ""),
            "supermodel": str(getattr(stock, "supermodel", "") or ""),
            "skin_nodes": [str(getattr(part, "name", "") or "") for part in stock_parts],
        },
    }


def _grab(viewport: Any, path: Path) -> dict[str, Any]:
    from PIL import Image

    pixmap = viewport.grab()
    if not pixmap.save(str(path)):
        raise RuntimeError(f"failed to save viewport screenshot: {path}")
    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    unique = int(np.unique(rgb.reshape(-1, 3), axis=0).shape[0])
    return {
        "path": str(path),
        "width": int(pixmap.width()),
        "height": int(pixmap.height()),
        "unique_rgb_colors": unique,
        "nonblank": unique > 64,
    }


def _renderer_diagnostics(viewport: Any) -> dict[str, Any]:
    renderer = getattr(viewport, "_gpu_renderer", None)
    active = getattr(renderer, "active_backend", None)
    try:
        diagnostics = dict(renderer.get_diagnostics() or {}) if renderer is not None else {}
    except Exception as exc:
        diagnostics = {"error": str(exc)}
    return {
        "active_backend": str(getattr(active, "value", active) or ""),
        "reported_backend": str(
            diagnostics.get("backend_id")
            or diagnostics.get("name")
            or diagnostics.get("api")
            or ""
        ),
        "diagnostics": diagnostics,
    }


def _capture_fixture(app: Any, manager: Any, model: Any, head: Any, fixture: dict[str, str], output: Path) -> dict[str, Any]:
    from src.core.animation.animation_engine import AnimationEngine
    from src.core.rendering.renderer_backend import RendererBackend
    from src.core.rendering.renderer_settings import RendererSettings
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget
    from src.systems.bas.preview_composer import build_bas_preview_model, find_model_node
    from scripts.visual_harness_pygfx_flat_animation import (
        _focus_camera_on_node,
        _force_render,
        _process_events,
    )

    artifact = fixture["artifact"]
    head_resref = fixture["head"].lower()
    composed = build_bas_preview_model(
        body_model=model,
        attachment_models={"head": head},
        name=f"{artifact}_{head_resref}_bas_proof",
    )
    headhook = find_model_node(composed, "headhook")
    attachment_root = next(
        (
            node
            for node in composed.all_nodes()
            if bool(getattr(node, "_gr_bas_attachment_root", False))
            and str(getattr(node, "_gr_bas_attachment_slot", "") or "").lower() == "head"
        ),
        None,
    )
    attachment_head_mesh = next(
        (
            node
            for node in composed.all_nodes()
            if bool(getattr(node, "_gr_bas_attachment_layer", False))
            and bool(getattr(node, "is_skin", False))
            and str(getattr(node, "name", "") or "").lower() == "head"
        ),
        None,
    )
    if headhook is None or attachment_root is None or getattr(attachment_root, "parent", None) is not headhook:
        raise RuntimeError(f"{artifact}: BAS head did not attach directly under headhook")

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
    viewport.set_resource_manager(manager, "K2")
    viewport.load_model(composed)
    # The source texture is deliberately near-black.  A flat, untextured
    # proof makes silhouette continuity, joint deformation, and the neck seam
    # objectively visible instead of hiding them in black-on-black albedo.
    viewport.set_render_mode("flat")
    viewport.toggle_texture(False)
    viewport.toggle_bones(False)
    viewport.toggle_grid(True)
    viewport.show()
    _process_events(app, 0.8)
    gpu_renderer = getattr(viewport, "_gpu_renderer", None)
    if gpu_renderer is not None and hasattr(gpu_renderer, "set_native_palette_colors"):
        gpu_renderer.set_native_palette_colors(
            base=(20, 23, 28),
            text=(220, 225, 232),
            highlight=(0, 185, 255),
        )

    engine = AnimationEngine(composed)
    if not engine.play("walk", loop=True, blend=False):
        raise RuntimeError(f"{artifact}: BAS preview could not play inherited walk")
    length = float(getattr(engine.current_animation, "length", 0.0) or 0.0)
    pose0 = engine.evaluate(0.0)
    pose1_time = length * 0.25
    pose1 = engine.evaluate(pose1_time)
    for pose in (pose0, pose1):
        setattr(pose, "_gr_animation_source_model_id", id(composed))
        setattr(pose, "_gr_animation_source_model_name", str(getattr(composed, "name", "") or ""))
        setattr(pose, "_gr_animation_name", "walk")
        setattr(pose, "_gr_animation_game", "K2")
    viewport.set_anim_base_pose(pose0)
    viewport.set_animation_playback_active(True, f"{artifact} BAS proof")
    viewport.set_animation_pose(pose0, name="walk", time=0.0, length=length)
    _force_render(viewport, app, f"{artifact} load", animation=True, scene=True, resources=True, style=True, overlay=True, hud=True)
    viewport.frame_all()
    viewport.camera.distance = float(getattr(viewport.camera, "distance", 3.0) or 3.0) * 1.22
    viewport.camera.azimuth = 90.0
    viewport.camera.elevation = 7.0
    _force_render(viewport, app, f"{artifact} full pose0", camera=True, animation=True, scene=True, overlay=True, hud=True)
    screenshots = {
        "full_pose0": _grab(viewport, output / f"{artifact}_{head_resref}_bas_walk_full_pose0.png")
    }
    viewport.set_animation_pose(pose1, name="walk", time=pose1_time, length=length)
    for _ in range(8):
        _force_render(viewport, app, f"{artifact} full pose1", animation=True, overlay=True, hud=True)
    screenshots["full_pose1"] = _grab(viewport, output / f"{artifact}_{head_resref}_bas_walk_full_pose1.png")
    viewport.camera.azimuth = 0.0
    viewport.camera.elevation = 5.0
    _force_render(viewport, app, f"{artifact} full pose1 true side", camera=True, animation=True, overlay=True, hud=True)
    screenshots["full_pose1_true_side"] = _grab(
        viewport,
        output / f"{artifact}_{head_resref}_bas_walk_full_pose1_side.png",
    )
    viewport.camera.azimuth = 90.0
    viewport.camera.elevation = 7.0

    viewport.set_shade_mode("solid")
    viewport.set_render_mode("realistic")
    viewport.toggle_texture(True)
    _force_render(viewport, app, f"{artifact} textured orientation", style=True, animation=True, overlay=True, hud=True)
    screenshots["textured_orientation_pose1"] = _grab(
        viewport,
        output / f"{artifact}_{head_resref}_bas_textured_orientation_pose1.png",
    )

    if attachment_head_mesh is not None:
        viewport.set_selected_node(attachment_head_mesh)
    viewport.set_render_mode("flat")
    viewport.toggle_texture(False)
    viewport.set_shade_mode("wire")
    _focus_camera_on_node(viewport, attachment_head_mesh or attachment_root, distance=0.55)
    viewport.camera.azimuth = 90.0
    viewport.camera.elevation = 5.0
    _force_render(viewport, app, f"{artifact} head front", camera=True, animation=True, overlay=True, hud=True)
    screenshots["head_front"] = _grab(viewport, output / f"{artifact}_{head_resref}_bas_head_front_walk.png")
    viewport.camera.azimuth = 125.0
    viewport.camera.elevation = 8.0
    _force_render(viewport, app, f"{artifact} head three-quarter", camera=True, animation=True, overlay=True, hud=True)
    screenshots["head_three_quarter"] = _grab(viewport, output / f"{artifact}_{head_resref}_bas_head_3q_walk.png")
    viewport.camera.azimuth = 0.0
    viewport.camera.elevation = 3.0
    _force_render(viewport, app, f"{artifact} head true side", camera=True, animation=True, overlay=True, hud=True)
    screenshots["head_true_side"] = _grab(
        viewport,
        output / f"{artifact}_{head_resref}_bas_head_side_walk.png",
    )

    renderer = _renderer_diagnostics(viewport)
    viewport.set_animation_playback_active(False)
    viewport.close()
    _process_events(app, 0.2)
    nonblank = all(record["nonblank"] for record in screenshots.values())
    diagnostics = renderer.get("diagnostics", {}) or {}
    adapter = diagnostics.get("adapter", {}) or {}
    backend_text = " ".join(
        str(value or "")
        for value in (
            renderer["active_backend"],
            renderer["reported_backend"],
            diagnostics.get("backend"),
            diagnostics.get("api"),
            adapter.get("backend_type"),
        )
    ).lower()
    backend_ok = (
        "d3d12" in backend_text
        or "direct3d" in backend_text
        or bool(diagnostics.get("d3d12_selected", False))
    )
    return {
        "status": "pass" if nonblank and backend_ok else "fail",
        "body": artifact,
        "head": fixture["head"],
        "socket": str(getattr(headhook, "name", "") or ""),
        "attachment_parent": str(getattr(getattr(attachment_root, "parent", None), "name", "") or ""),
        "head_mesh_selected_for_seam_proof": str(getattr(attachment_head_mesh, "name", "") or ""),
        "walk_length": length,
        "sample_time": pose1_time,
        "display_mode": {
            "full_body": "flat_untextured",
            "head_seam": "wireframe",
        },
        "renderer": renderer,
        "screenshots": screenshots,
    }


def run(proof_dir: Path, k2_dir: Path, *, skip_render: bool = False) -> dict[str, Any]:
    from src.core.animation.animation_engine import SuperModelResolver
    from src.core.assets.resource_manager import RES_TGA, ResourceManager, _key
    from src.core.game.kotor_loader import load_model_from_file
    from src.core.geometry.model_data import GameVersion

    output = proof_dir / "VisualProof"
    output.mkdir(parents=True, exist_ok=True)
    manager = ResourceManager()
    if not manager.set_k2_dir(str(k2_dir)):
        raise RuntimeError(f"K2 installation could not be indexed: {k2_dir}")
    # Register only in the process-local loose-resource index.  This proves
    # textured rendering without altering a real game installation.
    for fixture in FIXTURES:
        texture_path = proof_dir / fixture["texture"]
        if not texture_path.is_file():
            raise FileNotFoundError(texture_path)
        manager._k2._override[_key(texture_path.stem, RES_TGA)] = str(texture_path)
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(manager)

    models: dict[str, Any] = {}
    audits: dict[str, Any] = {}
    for fixture in FIXTURES:
        artifact = fixture["artifact"]
        model = load_model_from_file(
            str(proof_dir / f"{artifact}.mdl"),
            str(proof_dir / f"{artifact}.mdx"),
            game_version=GameVersion.K2,
        )
        stock = manager.load_model(fixture["stock"], "K2", prefer_base_archive=True)
        if model is None or stock is None:
            raise RuntimeError(f"failed to load {artifact} or stock {fixture['stock']}")
        if str(getattr(model, "supermodel", "") or "").lower() != fixture["supermodel"].lower():
            raise RuntimeError(f"{artifact}: unexpected supermodel {model.supermodel!r}")
        models[artifact] = model
        audits[artifact] = _audit_model(
            model,
            stock,
            expected_headhook_lowering_m=float(fixture.get("headhook_lowering_m", 0.0) or 0.0),
            expected_headhook_forward_m=float(fixture.get("headhook_forward_m", 0.0) or 0.0),
        )

    audit_status = "pass" if all(record["status"] == "pass" for record in audits.values()) else "fail"
    deformation_report = {
        "status": audit_status,
        "game": "K2",
        "proof_dir": str(proof_dir),
        "palette_limit": 16,
        "fixtures": audits,
    }
    audit_path = output / "peragus_uniform_deformation_audit.json"
    audit_path.write_text(json.dumps(deformation_report, indent=2), encoding="utf-8")

    render_results: dict[str, Any] = {}
    if not skip_render:
        from PySide6 import QtWidgets

        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        for fixture in FIXTURES:
            head = manager.load_model(fixture["head"], "K2", prefer_base_archive=True)
            if head is None:
                raise RuntimeError(f"stock head not found: {fixture['head']}")
            render_results[fixture["artifact"]] = _capture_fixture(
                app,
                manager,
                models[fixture["artifact"]],
                head,
                fixture,
                output,
            )
    render_status = (
        "not_run"
        if skip_render
        else "pass" if all(record["status"] == "pass" for record in render_results.values()) else "fail"
    )
    renderer_report = {
        "status": render_status,
        "game": "K2",
        "body_attachment_system": "head -> headhook",
        "override_modified": False,
        "fixtures": render_results,
    }
    renderer_path = output / "peragus_uniform_bas_renderer_visual_proof.json"
    renderer_path.write_text(json.dumps(renderer_report, indent=2, default=str), encoding="utf-8")
    return {
        "deformation_report": str(audit_path),
        "deformation_status": audit_status,
        "renderer_report": str(renderer_path),
        "renderer_status": render_status,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof-dir", type=Path, default=DEFAULT_PROOF_DIR)
    parser.add_argument("--k2-dir", type=Path, default=DEFAULT_K2_DIR)
    parser.add_argument("--skip-render", action="store_true")
    args = parser.parse_args()
    result = run(args.proof_dir.resolve(), args.k2_dir.resolve(), skip_render=args.skip_render)
    print(json.dumps(result, indent=2))
    return 0 if result["deformation_status"] == "pass" and result["renderer_status"] in {"pass", "not_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
