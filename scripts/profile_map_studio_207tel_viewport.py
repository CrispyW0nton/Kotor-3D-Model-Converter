"""Profile Map Studio's resident K2 207tel viewport workload.

This is deliberately narrower than the stock-module import benchmarks.  It
loads the real module once, lets room/template models and textures become
resident, then profiles repeated ModernGL frames.  Import/hydration timings are
reported separately so a slow archive scan cannot be mistaken for orbit FPS.

The harness is headless evidence only.  It does not replace a visible run in
the Debug application on the user's GPU/display stack.
"""

from __future__ import annotations

import argparse
import cProfile
import json
import os
from pathlib import Path
import pstats
import statistics
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_K2 = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"
)


def _configure_python_roots() -> None:
    root_text = str(ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for path in reversed(_python_roots(ROOT)):
        text = str(path)
        if path.exists() and text not in sys.path:
            sys.path.insert(0, text)


def _texture_names(model) -> tuple[str, ...]:
    names: list[str] = []
    seen: set[str] = set()
    for node in model.all_nodes():
        if not getattr(node, "vertices", None):
            continue
        values = [
            getattr(node, "texture_clean", ""),
            getattr(node, "texture", ""),
            getattr(node, "lightmap", ""),
            getattr(node, "bump_map", ""),
            getattr(node, "txi_envmaptexture", ""),
            getattr(node, "txi_bumpmaptexture", ""),
        ]
        values.extend(getattr(node, "texture_names", ()) or ())
        for raw in values:
            clean = str(raw or "").strip().lower()
            if "." in clean:
                clean = clean.rsplit(".", 1)[0]
            if not clean or clean.upper() in {"NULL", "NONE", "****"} or clean in seen:
                continue
            seen.add(clean)
            names.append(clean)
    return tuple(names)


def _build_workload(k2_root: Path):
    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.module_editor_controller import ModuleEditorController

    phases: dict[str, float] = {}
    started = time.perf_counter()
    print("[207tel-profile] indexing K2 resources", file=sys.stderr, flush=True)
    resources = ResourceManager()
    if not resources.set_k2_dir(str(k2_root)):
        raise RuntimeError(f"Could not index K2 resources at {k2_root}")
    phases["resource_index_ms"] = (time.perf_counter() - started) * 1000.0
    started = time.perf_counter()
    print("[207tel-profile] importing module/GIT", file=sys.stderr, flush=True)
    controller = ModuleEditorController()
    controller.new_project(name="207tel", game="K2")
    ok, message = controller.import_stock_module_from_rim(
        module_resref="207tel",
        modules_dir=str(k2_root / "Modules"),
        game="K2",
        resource_manager=resources,
    )
    if not ok:
        raise RuntimeError(message)
    phases["module_import_ms"] = (time.perf_counter() - started) * 1000.0
    started = time.perf_counter()
    print("[207tel-profile] converting both rooms to editable mesh", file=sys.stderr, flush=True)
    converted, conversion_message = controller.convert_all_stock_rooms_to_imported_mesh(
        resource_manager=resources
    )
    if not converted:
        raise RuntimeError(f"207tel editable-room conversion failed: {conversion_message}")
    phases["editable_conversion_ms"] = (time.perf_counter() - started) * 1000.0
    started = time.perf_counter()
    print("[207tel-profile] building combined resident preview", file=sys.stderr, flush=True)
    model = controller.map_studio_viewport_preview_model(resources)
    if model is None:
        raise RuntimeError("207tel produced no viewport model")
    phases["combined_preview_ms"] = (time.perf_counter() - started) * 1000.0
    return resources, controller, model, phases


def _profile_qt_path(
    *,
    args: argparse.Namespace,
    resources,
    controller,
    model,
    frame_renderer,
    renderer,
    textures: dict,
) -> dict[str, object]:
    """Measure the real Qt viewport composition/presentation path.

    The ModernGL renderer is already resident before this function runs.  The
    timings therefore include lighting/gizmo packet construction, PIL overlays,
    PIL -> QImage -> QPixmap conversion, and CPU hover picking, but exclude
    module import, texture decode, and mesh upload.
    """

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtGui, QtWidgets
    from types import MethodType
    from src.adapters.rendering.renderer_factory import FallbackViewportRenderer
    from src.core.rendering.renderer_backend import RendererBackend
    from src.core.rendering.renderer_settings import RendererSettings
    from src.gui.viewports.viewport_core.widgets.viewport_widget import QtViewportWidget

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    viewport = QtViewportWidget(map_studio_authoring_chrome=True)
    viewport.resize(args.width, args.height)
    viewport.canvas.resize(args.width, args.height)
    viewport.model = model
    viewport._renderer.set_model(model)
    viewport.camera = frame_renderer.cam
    viewport._renderer.cam = viewport.camera
    viewport._renderer.tex_cache.set_resource_manager(resources, "K2")
    viewport._renderer.tex_cache._cache.update(textures)
    viewport._gpu_texture_snapshot_key = None
    viewport._gpu_texture_snapshot_cache = {}
    renderer_proxy = FallbackViewportRenderer(RendererSettings())
    object.__setattr__(renderer_proxy, "_active", renderer)
    object.__setattr__(renderer_proxy, "_active_backend", RendererBackend.MODERNGL_GL330)
    viewport._gpu_renderer = renderer_proxy
    viewport._owns_gpu_renderer = False
    viewport._renderer.show_texture = True
    viewport._renderer.show_diffuse_map = True
    viewport._renderer.show_lightmap_map = True
    viewport._renderer.lightmap_mode = "baked"
    viewport._map_studio_marker_geometry = controller.authored_gameplay_fallback_marker_geometry()
    viewport._map_studio_room_outline_geometry = controller.authored_room_outline_geometry()
    viewport._gpu_tex_preload_model_id = id(model)

    # Attribute the PIL overlay layer without putting permanent timers in the
    # interactive viewport.  These methods are intentionally wrapped only in
    # this focused profiler so the diagnostic overhead cannot affect users.
    overlay_method_samples: dict[str, list[float]] = {}
    overlay_method_names = (
        "_draw_camera_helpers",
        "_draw_map_studio_terrain_walkability",
        "_draw_map_studio_component_selection",
        "_draw_map_studio_component_extrude_gizmo",
        "_draw_map_studio_hover_highlight",
        "_draw_map_studio_terrain_brush_cursor",
        "_draw_map_studio_room_outlines",
        "_draw_map_studio_universal_transform_overlay",
        "_draw_map_studio_placement_markers",
        "_draw_wgpu_helper_markers",
        "_draw_transform_gizmo",
        "_draw_measurement_overlay",
        "_draw_selected_model_outline",
        "_draw_mesh_subobject_selection",
        "_draw_joint_marquee",
        "_draw_renderer_statistics_overlay",
        "_draw_active_camera_overlays",
    )
    for method_name in overlay_method_names:
        original = getattr(viewport, method_name, None)
        if not callable(original):
            continue
        overlay_method_samples[method_name] = []

        def _timed_overlay(self, *method_args, _name=method_name, _original=original, **method_kwargs):
            method_started = time.perf_counter()
            try:
                return _original(*method_args, **method_kwargs)
            finally:
                overlay_method_samples[_name].append((time.perf_counter() - method_started) * 1000.0)

        setattr(viewport, method_name, MethodType(_timed_overlay, viewport))

    renderer_overlay_samples: dict[str, list[float]] = {}
    for method_name in ("_draw_axes", "_draw_stats"):
        original = getattr(viewport._renderer, method_name, None)
        if not callable(original):
            continue
        renderer_overlay_samples[method_name] = []

        def _timed_renderer_overlay(*method_args, _name=method_name, _original=original, **method_kwargs):
            method_started = time.perf_counter()
            try:
                return _original(*method_args, **method_kwargs)
            finally:
                renderer_overlay_samples[_name].append((time.perf_counter() - method_started) * 1000.0)

        setattr(viewport._renderer, method_name, _timed_renderer_overlay)

    presentation_samples: dict[str, list[float]] = {
        "render_frame_ms": [],
        "pil_to_bytes_ms": [],
        "qimage_copy_ms": [],
        "qpixmap_ms": [],
        "canvas_present_ms": [],
    }

    def present_one() -> float:
        started = time.perf_counter()
        stage_started = time.perf_counter()
        image = viewport._render_frame(args.width, args.height)
        presentation_samples["render_frame_ms"].append((time.perf_counter() - stage_started) * 1000.0)
        if image is None:
            raise RuntimeError("Qt viewport returned no frame")
        if image.mode != "RGBA":
            image = image.convert("RGBA")
        stage_started = time.perf_counter()
        rgba_bytes = image.tobytes("raw", "RGBA")
        presentation_samples["pil_to_bytes_ms"].append((time.perf_counter() - stage_started) * 1000.0)
        stage_started = time.perf_counter()
        qimage = QtGui.QImage(
            rgba_bytes,
            image.width,
            image.height,
            image.width * 4,
            QtGui.QImage.Format_RGBA8888,
        ).copy()
        presentation_samples["qimage_copy_ms"].append((time.perf_counter() - stage_started) * 1000.0)
        stage_started = time.perf_counter()
        viewport._pixmap = QtGui.QPixmap.fromImage(qimage)
        presentation_samples["qpixmap_ms"].append((time.perf_counter() - stage_started) * 1000.0)
        stage_started = time.perf_counter()
        viewport.canvas.setPixmap(viewport._pixmap)
        app.processEvents()
        presentation_samples["canvas_present_ms"].append((time.perf_counter() - stage_started) * 1000.0)
        return (time.perf_counter() - started) * 1000.0

    viewport._nav_dragging = "orbit"
    viewport._fast_frame_until = time.perf_counter() + 3600.0
    qt_samples = [present_one() for _ in range(args.frames)]
    viewport._nav_dragging = ""
    viewport._fast_frame_until = 0.0

    # CPU hover is intentionally sampled away from active navigation; the
    # event filter suppresses it while orbit/pan/zoom is dragging.
    hover_points = () if args.skip_hover else (
        (args.width // 2, args.height // 2),
        (args.width // 3, args.height // 2),
        ((args.width * 2) // 3, args.height // 2),
        (args.width // 2, args.height // 3),
        (args.width // 2, (args.height * 2) // 3),
    )
    hover_samples = []
    hover_diagnostics = []
    for x, y in hover_points:
        started = time.perf_counter()
        viewport._mesh_hit_test_detail(x, y, allow_gpu=False)
        hover_samples.append((time.perf_counter() - started) * 1000.0)
        hover_diagnostics.append(dict(getattr(viewport, "_last_pick_diagnostics", {}) or {}))

    from types import SimpleNamespace
    from src.core.modules.map_studio_hover_context import pick_map_studio_hover_context
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    panel_hover_owner = SimpleNamespace(
        viewport=SimpleNamespace(_renderer=viewport._renderer, camera=viewport.camera),
        _room_preview_model=model,
        _terrain_walkability_overlay=None,
        _hover_component_mode="face",
        _viewport_canvas_size=lambda: (args.width, args.height),
        _HOVER_GRID_CELL=ModuleEditorViewportPanel._HOVER_GRID_CELL,
    )
    panel_hover_owner._map_studio_face_normal = ModuleEditorViewportPanel._map_studio_face_normal
    panel_hover_owner._map_studio_face_uv_points = ModuleEditorViewportPanel._map_studio_face_uv_points
    panel_hover_owner._map_studio_projected_candidate = MethodType(
        ModuleEditorViewportPanel._map_studio_projected_candidate,
        panel_hover_owner,
    )
    candidate_profiler = cProfile.Profile()
    candidate_profiler.enable()
    profiled_panel_hover_candidates = ModuleEditorViewportPanel._map_studio_hover_candidates(panel_hover_owner)
    candidate_profiler.disable()
    candidate_stream = __import__("io").StringIO()
    pstats.Stats(candidate_profiler, stream=candidate_stream).strip_dirs().sort_stats("cumulative").print_stats(18)
    candidate_started = time.perf_counter()
    panel_hover_candidates = ModuleEditorViewportPanel._map_studio_hover_candidates(panel_hover_owner)
    candidate_ms = (time.perf_counter() - candidate_started) * 1000.0
    if len(profiled_panel_hover_candidates) != len(panel_hover_candidates):
        raise RuntimeError("profiled and unprofiled Map Studio hover candidate counts diverged")
    center_cell = (
        int((args.width * 0.5) // ModuleEditorViewportPanel._HOVER_GRID_CELL),
        int((args.height * 0.5) // ModuleEditorViewportPanel._HOVER_GRID_CELL),
    )
    cell_candidate_started = time.perf_counter()
    cell_hover_candidates = ModuleEditorViewportPanel._map_studio_hover_candidates(
        panel_hover_owner,
        screen_cell=center_cell,
    )
    cell_candidate_ms = (time.perf_counter() - cell_candidate_started) * 1000.0
    grid_started = time.perf_counter()
    panel_hover_grid = ModuleEditorViewportPanel._build_map_studio_hover_grid(
        panel_hover_owner,
        panel_hover_candidates,
    )
    grid_ms = (time.perf_counter() - grid_started) * 1000.0
    cached_cell_samples: list[float] = []
    for grid_x, grid_y in sorted(panel_hover_grid):
        candidates_in_cell = panel_hover_grid[(grid_x, grid_y)]
        sample_x = (float(grid_x) + 0.5) * ModuleEditorViewportPanel._HOVER_GRID_CELL
        sample_y = (float(grid_y) + 0.5) * ModuleEditorViewportPanel._HOVER_GRID_CELL
        sample_started = time.perf_counter()
        pick_map_studio_hover_context(
            candidates_in_cell,
            sample_x,
            sample_y,
            tolerance_px=5.0,
        )
        cached_cell_samples.append((time.perf_counter() - sample_started) * 1000.0)
    cached_cell_sorted = sorted(cached_cell_samples)
    cached_cell_p95 = (
        cached_cell_sorted[max(0, int(len(cached_cell_sorted) * 0.95) - 1)]
        if cached_cell_sorted
        else 0.0
    )
    panel_hover_report = {
        "candidate_build_ms": candidate_ms,
        "candidate_count": len(panel_hover_candidates),
        "center_cell_candidate_build_ms": cell_candidate_ms,
        "center_cell_candidate_count": len(cell_hover_candidates),
        "grid_build_ms": grid_ms,
        "grid_cell_count": len(panel_hover_grid),
        "cached_cell_pick_median_ms": statistics.median(cached_cell_samples) if cached_cell_samples else 0.0,
        "cached_cell_pick_p95_ms": cached_cell_p95,
        "cached_cell_pick_max_ms": max(cached_cell_samples) if cached_cell_samples else 0.0,
        "cache_signature_is_stable": ModuleEditorViewportPanel._map_studio_hover_cache_signature(panel_hover_owner) is not None,
        "profile_top": candidate_stream.getvalue(),
    }

    def _sample_report(samples_by_name: dict[str, list[float]]) -> dict[str, dict[str, float]]:
        return {
            name: {
                "median_ms": statistics.median(samples),
                "mean_ms": statistics.fmean(samples),
                "max_ms": max(samples),
                "calls": len(samples),
            }
            for name, samples in samples_by_name.items()
            if samples
        }

    overlay_method_report = _sample_report(overlay_method_samples)
    overlay_method_report.update(_sample_report(renderer_overlay_samples))
    presentation_report = _sample_report(presentation_samples)
    viewport.close()
    hover_payload = {
        "cpu_hover_median_ms": statistics.median(hover_samples),
        "cpu_hover_max_ms": max(hover_samples),
    } if hover_samples else {
        "cpu_hover_median_ms": 0.0,
        "cpu_hover_max_ms": 0.0,
    }
    return {
        "qt_orbit_present_median_ms": statistics.median(qt_samples),
        "qt_orbit_present_mean_ms": statistics.fmean(qt_samples),
        "qt_orbit_present_p95_ms": sorted(qt_samples)[max(0, int(len(qt_samples) * 0.95) - 1)],
        "qt_orbit_present_estimated_fps": 1000.0 / max(0.001, statistics.median(qt_samples)),
        "qt_orbit_samples_ms": qt_samples,
        **hover_payload,
        "cpu_hover_samples_ms": hover_samples,
        "cpu_hover_diagnostics": hover_diagnostics,
        "map_studio_component_hover": panel_hover_report,
        "overlay_diagnostics": viewport._overlay_diagnostics(),
        "presentation_stages": presentation_report,
        "overlay_methods": overlay_method_report,
    }


def _profile(args: argparse.Namespace) -> dict[str, object]:
    from src.adapters.rendering.moderngl_renderer import ModernGLRenderer
    from src.core.camera.arcball_camera import ArcBallCamera
    from src.core.rendering.frame_core.renderer import FrameRenderer

    build_started = time.perf_counter()
    resources, controller, model, build_phases = _build_workload(args.k2_root)
    build_ms = (time.perf_counter() - build_started) * 1000.0

    all_texture_names = _texture_names(model)
    if args.names_only:
        nodes = list(model.all_nodes())
        meshes = [node for node in nodes if getattr(node, "vertices", None) and getattr(node, "faces", None)]
        return {
            "fixture": "K2:207tel",
            "headless_only": True,
            "node_count": len(nodes),
            "mesh_count": len(meshes),
            "triangle_count": sum(len(getattr(node, "faces", ()) or ()) for node in meshes),
            "texture_names": list(all_texture_names),
            "module_build_ms": build_ms,
            "build_phases": build_phases,
        }

    frame_renderer = FrameRenderer(ArcBallCamera())
    frame_renderer.set_model(model)
    frame_renderer.tex_cache.set_resource_manager(resources, "K2")
    try:
        model.compute_bounds()
        frame_renderer.cam.frame_bounds(model.bb_min, model.bb_max, reset_view=True)
    except Exception:
        pass

    texture_names = () if args.skip_textures else all_texture_names
    if args.max_textures > 0:
        texture_names = texture_names[: args.max_textures]
    print(
        f"[207tel-profile] decoding {len(texture_names)} texture/lightmap resources",
        file=sys.stderr,
        flush=True,
    )
    residency_started = time.perf_counter()
    texture_decode_samples: list[tuple[str, float]] = []
    for index, name in enumerate(texture_names, start=1):
        texture_started = time.perf_counter()
        frame_renderer.tex_cache.get(name)
        texture_decode_samples.append((name, (time.perf_counter() - texture_started) * 1000.0))
        if index == len(texture_names) or index % 10 == 0:
            print(
                f"[207tel-profile] texture residency {index}/{len(texture_names)}",
                file=sys.stderr,
                flush=True,
            )
    residency_ms = (time.perf_counter() - residency_started) * 1000.0
    textures = {
        key: value
        for key, value in getattr(frame_renderer.tex_cache, "_cache", {}).items()
        if value is not None
    }

    renderer = ModernGLRenderer()
    renderer.show_texture = True
    renderer.show_diffuse_map = True
    renderer.show_lightmap_map = True
    renderer.lightmap_mode = "baked"
    renderer.cull_faces = False  # matches the current Qt viewport contract

    def draw(*, interactive: bool, scale: float) -> float:
        renderer.interactive = interactive
        renderer.interactive_render_scale = scale
        started = time.perf_counter()
        image = renderer.render(
            model,
            frame_renderer.cam,
            args.width,
            args.height,
            textures=textures,
        )
        if image is None:
            raise RuntimeError("ModernGL returned no frame")
        return (time.perf_counter() - started) * 1000.0

    # Uploads/context/FBO construction are not steady-state costs.  ModernGL
    # intentionally stages at most 64 new meshes per frame, so a fixed three
    # frames is insufficient for 207tel's 200+ meshes.  Warm until the backend
    # explicitly reports no deferred uploads (while retaining a hard bound).
    warmup_frames = 0
    while warmup_frames < max(1, args.warmup, 64):
        draw(interactive=True, scale=1.0)
        warmup_frames += 1
        if not bool(getattr(renderer, "deferred_mesh_uploads", False)):
            break

    variants = (
        ("interactive_full", True, 1.0),
        ("interactive_75pct", True, 0.75),
        ("interactive_half", True, 0.5),
        ("idle_hq", False, 1.0),
    )
    timing: dict[str, object] = {}
    for label, interactive, scale in variants:
        samples = [draw(interactive=interactive, scale=scale) for _ in range(args.frames)]
        timing[label] = {
            "median_ms": statistics.median(samples),
            "mean_ms": statistics.fmean(samples),
            "min_ms": min(samples),
            "max_ms": max(samples),
            "estimated_fps_from_median": 1000.0 / max(0.001, statistics.median(samples)),
            "renderer_perf": dict(renderer.perf),
        }

    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(args.profile_frames):
        draw(interactive=True, scale=1.0)
    profiler.disable()
    profile_path = args.profile_output.resolve()
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profiler.dump_stats(str(profile_path))

    stream = __import__("io").StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(30)

    qt_path = {}
    if not args.skip_qt_path:
        qt_path = _profile_qt_path(
            args=args,
            resources=resources,
            controller=controller,
            model=model,
            frame_renderer=frame_renderer,
            renderer=renderer,
            textures=textures,
        )

    nodes = list(model.all_nodes())
    meshes = [node for node in nodes if getattr(node, "vertices", None) and getattr(node, "faces", None)]
    report = {
        "fixture": "K2:207tel",
        "headless_only": True,
        "canvas": [args.width, args.height],
        "node_count": len(nodes),
        "mesh_count": len(meshes),
        "triangle_count": sum(len(getattr(node, "faces", ()) or ()) for node in meshes),
        "texture_names": len(texture_names),
        "resident_textures": len(textures),
        "warmup_frames_until_mesh_resident": warmup_frames,
        "module_build_ms": build_ms,
        "build_phases": build_phases,
        "texture_residency_ms": residency_ms,
        "slowest_texture_decodes_ms": sorted(
            texture_decode_samples, key=lambda item: item[1], reverse=True
        )[:20],
        "controller_preview_ms": float(getattr(controller, "last_map_studio_preview_elapsed_ms", 0.0)),
        "timing": timing,
        "qt_path": qt_path,
        "profile_path": str(profile_path),
        "profile_top": stream.getvalue(),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k2-root", type=Path, default=DEFAULT_K2)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--frames", type=int, default=12)
    parser.add_argument("--profile-frames", type=int, default=12)
    parser.add_argument("--names-only", action="store_true")
    parser.add_argument("--skip-qt-path", action="store_true")
    parser.add_argument("--skip-hover", action="store_true")
    parser.add_argument(
        "--max-textures",
        type=int,
        default=0,
        help="Decode only this many textures for diagnostics; 0 means the full resident fixture.",
    )
    parser.add_argument(
        "--skip-textures",
        action="store_true",
        help="Profile full room geometry/Qt overhead with fallback materials and no texture decode.",
    )
    parser.add_argument(
        "--profile-output",
        type=Path,
        default=ROOT / "Saved" / "Profiles" / "map_studio_207tel_steady_state.prof",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=ROOT / "Saved" / "Profiles" / "map_studio_207tel_steady_state.json",
    )
    args = parser.parse_args()
    if not args.k2_root.exists():
        parser.error(f"K2 install not found: {args.k2_root}")
    _configure_python_roots()
    report = _profile(args)
    payload = json.dumps(report, indent=2, default=str)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
