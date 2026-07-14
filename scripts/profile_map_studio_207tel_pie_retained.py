"""Profile the exact retained-character K2 207TEL PIE render workload.

This harness differs from ``profile_map_studio_207tel_viewport.py`` by replacing
the stock flattened creature previews with the same independently animated BAS
actor hierarchies used by Play in Editor.  It also attaches the default PIE
player and derives the retail-style follow camera from the module entry point.

The result is headless renderer evidence.  It does not replace a visible Debug
application run on the user's active display stack.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
import time

from profile_map_studio_207tel_viewport import (
    DEFAULT_K2,
    ROOT,
    _build_workload,
    _configure_python_roots,
    _texture_names,
)


def _attach_retained_actors(resources, controller, model):
    from src.core.animation.animation_engine import AnimationEngine, SuperModelResolver
    from src.core.modules.map_studio_pie import (
        attach_map_studio_pie_actor,
        prepare_map_studio_pie_actor_hierarchy,
        resolve_map_studio_pie_actor_grounding,
    )
    from src.core.modules.map_studio_pie_creatures import (
        build_map_studio_pie_creature_plan,
        prepare_map_studio_pie_creature_actor_artifacts,
    )
    from src.core.modules.map_studio_stock_content_preview import (
        RES_UTC,
        TemplateModelResolver,
        load_kotor_model_from_bytes,
    )
    from src.core.rendering.mesh_render_data import ScopedAnimationPoseSet
    from src.systems.bas.preview_composer import build_bas_preview_model

    placements = controller.map_studio_authored_placements_snapshot()
    template_resources = tuple(
        getattr(controller, "_authored_creature_resources", ()) or ()
    )
    resolver = TemplateModelResolver(
        resources,
        "K2",
        template_resources=template_resources,
    )
    plan = build_map_studio_pie_creature_plan(
        placements,
        resolver,
        game="K2",
        utc_reader=lambda resref, _game: resolver._template_bytes(resref, RES_UTC),
        template_resources=template_resources,
    )
    prepared_started = time.perf_counter()
    result = prepare_map_studio_pie_creature_actor_artifacts(
        plan,
        resources,
        resolver,
        "K2",
        dict(getattr(controller, "_map_studio_stock_model_cache", None) or {}),
        {},
        model_bytes_loader=load_kotor_model_from_bytes,
        model_composer=build_bas_preview_model,
        animation_engine_factory=AnimationEngine,
        hierarchy_preparer=prepare_map_studio_pie_actor_hierarchy,
        supermodel_configurer=SuperModelResolver.configure,
    )
    prepare_ms = (time.perf_counter() - prepared_started) * 1000.0

    pie_build = controller.create_map_studio_pie_session(preview_model=model)
    session = pie_build.session
    if session is None:
        raise RuntimeError("207TEL did not produce a PIE session")

    root = model.root_node
    original_children = tuple(root.children or ())
    flattened_creatures = {
        str(getattr(node, "_gr_map_studio_placement_id", "") or ""): node
        for node in original_children
        if str(getattr(node, "_gr_map_studio_placement_kind", "") or "").lower()
        == "creature"
    }
    hidden_node_ids: set[int] = set()
    wrappers = []
    poses: dict[str, object] = {}
    creature_runtime = []
    for prepared in result.entries:
        spec = prepared.spec
        grounding = resolve_map_studio_pie_actor_grounding(
            session.walkmesh,
            prepared.actor_model,
            spec.position,
            radius=0.0,
            max_step_up=float(session.config.max_step_up),
            max_step_down=float(session.config.max_step_down),
        )
        actor = attach_map_studio_pie_actor(
            model,
            prepared.actor_model,
            position=grounding.surface_position,
            facing_radians=float(spec.facing_radians),
            actor_id=spec.render.actor_id,
            recompute_bounds=False,
            prepared_root=prepared.prepared_root,
            append_to_preview=False,
            support_plane_z=grounding.support_plane_z,
        )
        if actor is None:
            continue
        actor.root_node.parent = root
        wrappers.append(actor.root_node)
        flattened = flattened_creatures.get(spec.placement_id)
        if flattened is not None:
            hidden_node_ids.add(id(flattened))
        pose = prepared.initial_pose
        setattr(pose, "_gr_animation_scene_object_id", actor.actor_id)
        setattr(pose, "_gr_animation_source_model_id", id(actor.source_model))
        poses[actor.actor_id] = pose
        creature_runtime.append(
            {
                "actor": actor,
                "engine": prepared.animation_engine,
                "pose": pose,
                "elapsed": 0.0,
            }
        )

    # Attach the same PMBAM + PMHC01 player used by Map Studio PIE.
    body = resources.load_model_strict("pmbam", "K2")
    head = resources.load_model_strict("pmhc01", "K2")
    player_model = build_bas_preview_model(
        body_model=body,
        attachment_models={"head": head},
        name="pmbam_pmhc01_pie_player_profile",
    )
    player = attach_map_studio_pie_actor(
        model,
        player_model,
        position=tuple(session.state.position),
        facing_radians=float(session.state.facing_radians),
        actor_id="__map_studio_pie_player__",
        recompute_bounds=False,
        append_to_preview=False,
    )
    if player is None:
        raise RuntimeError("Default PIE player could not be attached")
    player.root_node.parent = root
    wrappers.append(player.root_node)
    player_engine = AnimationEngine(player_model)
    if not player_engine.play("pause1", loop=True, blend=False):
        player_engine.play("idlepose", loop=True, blend=False)
    player_pose = player_engine.evaluate()
    setattr(player_pose, "_gr_animation_scene_object_id", player.actor_id)
    setattr(player_pose, "_gr_animation_source_model_id", id(player.source_model))
    poses[player.actor_id] = player_pose

    root.children = [
        node for node in original_children if id(node) not in hidden_node_ids
    ] + wrappers
    model.compute_bounds()
    runtime = {
        "poses": poses,
        "creatures": creature_runtime,
        "player_actor": player,
        "player_engine": player_engine,
        "player_pose": player_pose,
        "creature_cursor": 0,
        "creature_budget": 0.0,
    }
    return (
        ScopedAnimationPoseSet(poses),
        session,
        {
            "planned_creatures": len(plan.specs),
            "retained_creatures": len(result.entries),
            "preparation_failures": list(result.failures),
            "actor_preparation_ms": prepare_ms,
            "pose_count_including_player": len(poses),
        },
        runtime,
    )


def _summary(values) -> dict[str, float | list[float]]:
    samples = [float(value) for value in values]
    if not samples:
        return {
            "median": 0.0,
            "mean": 0.0,
            "min": 0.0,
            "max": 0.0,
            "samples": [],
        }
    return {
        "median": statistics.median(samples),
        "mean": statistics.fmean(samples),
        "min": min(samples),
        "max": max(samples),
        "samples": samples,
    }


class _RendererWorkProbe:
    """Temporary counters for renderer-internal transform/palette work."""

    def __init__(self, renderer):
        import src.adapters.rendering.moderngl_renderer_impl as implementation
        import src.core.rendering.mesh_render_data as mesh_render_data

        self.renderer = renderer
        self.implementation = implementation
        self.mesh_render_data = mesh_render_data
        self.original_palette = renderer._skin_palette_bytes_for_draw
        self.original_animated_world = implementation._animated_node_world_transform
        self.original_compose = implementation._compose_world_transform_np
        self.original_mat4 = implementation._mat4_from_pos_quat_scale
        self.pose_set_class = mesh_render_data.ScopedAnimationPoseSet
        self.original_pose_for_node = self.pose_set_class.pose_for_node
        self.reset()

    def reset(self) -> None:
        self.counts = {
            "palette_calls": 0,
            "palette_hits": 0,
            "palette_misses": 0,
            "palette_total_ms": 0.0,
            "palette_hit_ms": 0.0,
            "palette_miss_ms": 0.0,
            "animated_world_calls": 0,
            "animated_world_cache_hits": 0,
            "animated_world_cache_misses": 0,
            "animated_world_ms": 0.0,
            "world_compose_calls": 0,
            "world_compose_ms": 0.0,
            "mat4_calls": 0,
            "mat4_ms": 0.0,
            "scoped_pose_lookups": 0,
            "scoped_pose_lookup_ms": 0.0,
        }

    def install(self) -> None:
        probe = self

        def palette(**kwargs):
            started = time.perf_counter()
            result = probe.original_palette(**kwargs)
            elapsed = (time.perf_counter() - started) * 1000.0
            cached = bool(result[2])
            probe.counts["palette_calls"] += 1
            probe.counts["palette_total_ms"] += elapsed
            if cached:
                probe.counts["palette_hits"] += 1
                probe.counts["palette_hit_ms"] += elapsed
            else:
                probe.counts["palette_misses"] += 1
                probe.counts["palette_miss_ms"] += elapsed
            return result

        def animated_world(node, anim_pose):
            cache = getattr(anim_pose, "_gr_mesh_world_cache", None)
            before = len(cache) if isinstance(cache, dict) else 0
            started = time.perf_counter()
            result = probe.original_animated_world(node, anim_pose)
            elapsed = (time.perf_counter() - started) * 1000.0
            cache = getattr(anim_pose, "_gr_mesh_world_cache", None)
            after = len(cache) if isinstance(cache, dict) else 0
            probe.counts["animated_world_calls"] += 1
            probe.counts["animated_world_ms"] += elapsed
            if after > before:
                probe.counts["animated_world_cache_misses"] += 1
            else:
                probe.counts["animated_world_cache_hits"] += 1
            return result

        def compose(*args, **kwargs):
            started = time.perf_counter()
            result = probe.original_compose(*args, **kwargs)
            probe.counts["world_compose_calls"] += 1
            probe.counts["world_compose_ms"] += (
                time.perf_counter() - started
            ) * 1000.0
            return result

        def mat4(*args, **kwargs):
            started = time.perf_counter()
            result = probe.original_mat4(*args, **kwargs)
            probe.counts["mat4_calls"] += 1
            probe.counts["mat4_ms"] += (time.perf_counter() - started) * 1000.0
            return result

        def pose_for_node(instance, node):
            started = time.perf_counter()
            result = probe.original_pose_for_node(instance, node)
            probe.counts["scoped_pose_lookups"] += 1
            probe.counts["scoped_pose_lookup_ms"] += (
                time.perf_counter() - started
            ) * 1000.0
            return result

        self.renderer._skin_palette_bytes_for_draw = palette
        self.implementation._animated_node_world_transform = animated_world
        self.implementation._compose_world_transform_np = compose
        self.implementation._mat4_from_pos_quat_scale = mat4
        self.pose_set_class.pose_for_node = pose_for_node

    def uninstall(self) -> None:
        self.renderer._skin_palette_bytes_for_draw = self.original_palette
        self.implementation._animated_node_world_transform = self.original_animated_world
        self.implementation._compose_world_transform_np = self.original_compose
        self.implementation._mat4_from_pos_quat_scale = self.original_mat4
        self.pose_set_class.pose_for_node = self.original_pose_for_node

    def snapshot(self) -> dict[str, float | int]:
        result = dict(self.counts)
        result["palette_cache_entries"] = len(
            getattr(self.renderer, "_skin_palette_bytes_cache", {}) or {}
        )
        result["world_transform_cache_entries"] = len(
            getattr(self.renderer, "_wt_cache", {}) or {}
        )
        return result


def _advance_runtime_poses(runtime, delta_time: float, *, npc_hz: float = 12.0):
    """Mirror Map Studio's player + staggered NPC pose publication policy."""

    from src.core.rendering.mesh_render_data import ScopedAnimationPoseSet

    started = time.perf_counter()
    poses = runtime["poses"]
    player_engine = runtime["player_engine"]
    player_actor = runtime["player_actor"]
    player_engine.advance(delta_time)
    player_pose = player_engine.evaluate()
    setattr(player_pose, "_gr_animation_scene_object_id", player_actor.actor_id)
    setattr(player_pose, "_gr_animation_source_model_id", id(player_actor.source_model))
    poses[player_actor.actor_id] = player_pose

    entries = runtime["creatures"]
    elapsed = max(0.0, min(float(delta_time), 0.25))
    for entry in entries:
        entry["elapsed"] = min(0.25, float(entry.get("elapsed", 0.0)) + elapsed)
    actor_count = len(entries)
    budget = min(
        float(actor_count),
        float(runtime.get("creature_budget", 0.0))
        + actor_count * elapsed * float(npc_hz),
    )
    update_count = min(actor_count, int(budget))
    runtime["creature_budget"] = budget - update_count
    cursor = int(runtime.get("creature_cursor", 0)) % max(1, actor_count)
    for offset in range(update_count):
        entry = entries[(cursor + offset) % actor_count]
        engine = entry["engine"]
        step = min(0.25, float(entry.get("elapsed", elapsed) or elapsed))
        entry["elapsed"] = 0.0
        engine.advance(step)
        pose = engine.evaluate()
        actor = entry["actor"]
        setattr(pose, "_gr_animation_scene_object_id", actor.actor_id)
        setattr(pose, "_gr_animation_source_model_id", id(actor.source_model))
        entry["pose"] = pose
        poses[actor.actor_id] = pose
    runtime["creature_cursor"] = (
        (cursor + update_count) % actor_count if actor_count else 0
    )
    pose_set = ScopedAnimationPoseSet(poses)
    return (
        pose_set,
        update_count,
        (time.perf_counter() - started) * 1000.0,
    )


def _image_delta(left, right) -> dict[str, float | int]:
    import numpy as np

    a = np.asarray(left.convert("RGB"), dtype=np.int16)
    b = np.asarray(right.convert("RGB"), dtype=np.int16)
    delta = np.abs(a - b)
    changed = np.any(delta != 0, axis=2)
    return {
        "changed_pixels": int(changed.sum()),
        "changed_fraction": float(changed.mean()),
        "mean_absolute_channel_delta": float(delta.mean()),
        "max_channel_delta": int(delta.max()),
    }


def _profile(args: argparse.Namespace) -> dict[str, object]:
    from src.adapters.rendering.moderngl_renderer import ModernGLRenderer
    from src.core.camera.arcball_camera import ArcBallCamera
    from src.core.rendering.frame_core.renderer import FrameRenderer

    resources, controller, model, build_phases = _build_workload(args.k2_root)
    pose_set, session, actor_report, pose_runtime = _attach_retained_actors(
        resources,
        controller,
        model,
    )
    frame_renderer = FrameRenderer(ArcBallCamera())
    frame_renderer.set_model(model)
    frame_renderer.tex_cache.set_resource_manager(resources, "K2")
    camera = frame_renderer.cam
    camera.target = list(session.player_eye_target())
    camera.azimuth = (
        math.degrees(float(session.state.facing_radians)) + 180.0
    ) % 360.0
    camera.elevation = 7.0
    camera.distance = 3.2
    camera.fov = 55.0
    camera._near = 0.01
    camera._far = 1000.0

    texture_started = time.perf_counter()
    names = _texture_names(model)
    for name in names:
        frame_renderer.tex_cache.get(name)
    textures = {
        key: value
        for key, value in frame_renderer.tex_cache._cache.items()
        if value is not None
    }
    texture_ms = (time.perf_counter() - texture_started) * 1000.0

    renderer = ModernGLRenderer()
    renderer.show_texture = True
    renderer.show_diffuse_map = True
    renderer.show_lightmap_map = True
    renderer.lightmap_mode = "baked"
    renderer.show_light_gizmos = False
    renderer.show_light_radius_volumes = False

    def draw(
        *,
        interactive: bool,
        cull_faces: bool,
        frustum_culling: bool = True,
        lighting_mode: str = "scene",
        pose_override=None,
    ):
        renderer.interactive = interactive
        renderer.cull_faces = cull_faces
        renderer.enable_frustum_culling = frustum_culling
        renderer.lighting_mode = lighting_mode
        started = time.perf_counter()
        image = renderer.render(
            model,
            camera,
            args.width,
            args.height,
            textures=textures,
            anim_pose=pose_set if pose_override is None else pose_override,
        )
        if image is None:
            raise RuntimeError("ModernGL returned no retained PIE frame")
        return (time.perf_counter() - started) * 1000.0, dict(renderer.perf), image

    # One first frame normally uploads this fixture's complete retained set.
    upload_frames = 0
    while upload_frames < 64:
        draw(interactive=True, cull_faces=False)
        upload_frames += 1
        if not renderer.deferred_mesh_uploads:
            break

    def variant(
        label: str,
        *,
        interactive: bool,
        cull_faces: bool,
        frustum_culling: bool = True,
        lighting_mode: str = "scene",
    ):
        for _ in range(args.warmup):
            draw(
                interactive=interactive,
                cull_faces=cull_faces,
                frustum_culling=frustum_culling,
                lighting_mode=lighting_mode,
            )
        rows = [
            draw(
                interactive=interactive,
                cull_faces=cull_faces,
                frustum_culling=frustum_culling,
                lighting_mode=lighting_mode,
            )
            for _ in range(args.frames)
        ]
        values = [row[0] for row in rows]
        return {
            "label": label,
            "interactive": interactive,
            "cull_faces": cull_faces,
            "frustum_culling": frustum_culling,
            "lighting_mode": lighting_mode,
            "median_ms": statistics.median(values),
            "mean_ms": statistics.fmean(values),
            "min_ms": min(values),
            "max_ms": max(values),
            "samples_ms": values,
            "renderer_perf": rows[-1][1],
            "image": rows[-1][2],
        }

    fast = variant("pie_fast_no_cull", interactive=True, cull_faces=False)
    hq = variant("pie_hq_msaa_no_cull", interactive=False, cull_faces=False)
    culled = variant("pie_fast_cw_backface_cull", interactive=True, cull_faces=True)
    no_frustum = variant(
        "pie_fast_no_frustum_culling",
        interactive=True,
        cull_faces=False,
        frustum_culling=False,
    )
    unlit = variant(
        "pie_fast_unlit",
        interactive=True,
        cull_faces=False,
        lighting_mode="unlit",
    )
    lightmap_preview = variant(
        "pie_fast_lightmap_preview",
        interactive=True,
        cull_faces=False,
        lighting_mode="lightmap_preview",
    )

    pose_churn_report = None
    if args.diagnose_pose_churn:
        from src.core.rendering.mesh_render_data import ScopedAnimationPoseSet

        probe = _RendererWorkProbe(renderer)
        probe.install()
        try:
            def run_pose_case(label, update, *, warmup=None, frames=None):
                case_rows = []
                warmup_count = args.pose_churn_warmup if warmup is None else int(warmup)
                frame_count = args.pose_churn_frames if frames is None else int(frames)
                for _ in range(max(0, warmup_count)):
                    next_pose, _updated, _update_ms, _delta = update(None)
                    draw(
                        interactive=True,
                        cull_faces=False,
                        pose_override=next_pose,
                    )
                previous_wall_ms = None
                for _ in range(max(1, frame_count)):
                    probe.reset()
                    next_pose, updated, update_ms, delta_time = update(previous_wall_ms)
                    wall_ms, perf, _image = draw(
                        interactive=True,
                        cull_faces=False,
                        pose_override=next_pose,
                    )
                    previous_wall_ms = wall_ms + update_ms
                    case_rows.append(
                        {
                            "delta_time": float(delta_time),
                            "npc_poses_updated": int(updated),
                            "pose_update_ms": float(update_ms),
                            "render_wall_ms": float(wall_ms),
                            "total_tick_ms": float(wall_ms + update_ms),
                            "renderer_perf": perf,
                            "work": probe.snapshot(),
                        }
                    )

                def perf_samples(name):
                    return [
                        float(row["renderer_perf"].get(name, 0.0) or 0.0)
                        for row in case_rows
                    ]

                def work_samples(name):
                    return [float(row["work"].get(name, 0.0) or 0.0) for row in case_rows]

                return {
                    "label": label,
                    "frame_count": len(case_rows),
                    "npc_pose_updates": _summary(
                        row["npc_poses_updated"] for row in case_rows
                    ),
                    "pose_update_ms": _summary(
                        row["pose_update_ms"] for row in case_rows
                    ),
                    "render_wall_ms": _summary(
                        row["render_wall_ms"] for row in case_rows
                    ),
                    "total_tick_ms": _summary(
                        row["total_tick_ms"] for row in case_rows
                    ),
                    "renderer_stage_ms": {
                        "last_frame": _summary(perf_samples("last_frame_ms")),
                        "gpu_upload": _summary(perf_samples("gpu_upload_ms")),
                        "draw": _summary(perf_samples("draw_ms")),
                        "readback": _summary(perf_samples("readback_ms")),
                    },
                    "renderer_counts": {
                        "draw_calls": _summary(perf_samples("draw_calls")),
                        "triangles": _summary(perf_samples("tri_count")),
                        "visible_meshes": _summary(perf_samples("visible_meshes")),
                        "culled_meshes": _summary(perf_samples("culled_meshes")),
                    },
                    "work_per_frame": {
                        name: _summary(work_samples(name))
                        for name in (
                            "palette_calls",
                            "palette_hits",
                            "palette_misses",
                            "palette_total_ms",
                            "palette_hit_ms",
                            "palette_miss_ms",
                            "animated_world_calls",
                            "animated_world_cache_hits",
                            "animated_world_cache_misses",
                            "animated_world_ms",
                            "world_compose_calls",
                            "world_compose_ms",
                            "mat4_calls",
                            "mat4_ms",
                            "scoped_pose_lookups",
                            "scoped_pose_lookup_ms",
                            "palette_cache_entries",
                            "world_transform_cache_entries",
                        )
                    },
                    "frames": case_rows,
                }

            def reused_pose(_previous_wall_ms):
                return pose_set, 0, 0.0, 0.0

            def new_wrapper_same_poses(_previous_wall_ms):
                started = time.perf_counter()
                wrapper = ScopedAnimationPoseSet(pose_runtime["poses"])
                elapsed = (time.perf_counter() - started) * 1000.0
                return wrapper, 0, elapsed, 0.0

            def fixed_60hz(_previous_wall_ms):
                wrapper, updated, elapsed = _advance_runtime_poses(
                    pose_runtime,
                    1.0 / 60.0,
                )
                return wrapper, updated, elapsed, 1.0 / 60.0

            self_paced_delta = {"value": 1.0 / 60.0}

            def self_paced(previous_wall_ms):
                if previous_wall_ms is not None:
                    self_paced_delta["value"] = max(
                        1.0 / 60.0,
                        min(0.25, float(previous_wall_ms) / 1000.0),
                    )
                delta = self_paced_delta["value"]
                wrapper, updated, elapsed = _advance_runtime_poses(
                    pose_runtime,
                    delta,
                )
                return wrapper, updated, elapsed, delta

            pose_churn_report = {
                "contract": (
                    "Player advances/evaluates every tick; 32 NPCs use the same "
                    "12 Hz fractional round-robin budget as Map Studio; every "
                    "publication constructs a fresh ScopedAnimationPoseSet."
                ),
                "static_reused_scoped_pose": run_pose_case(
                    "static_reused_scoped_pose",
                    reused_pose,
                ),
                "new_scoped_wrapper_same_actor_poses": run_pose_case(
                    "new_scoped_wrapper_same_actor_poses",
                    new_wrapper_same_poses,
                ),
                "production_policy_at_60hz": run_pose_case(
                    "production_policy_at_60hz",
                    fixed_60hz,
                ),
                "production_policy_self_paced": run_pose_case(
                    "production_policy_self_paced",
                    self_paced,
                ),
            }
        finally:
            probe.uninstall()

    normal_cache_report = None
    if args.diagnose_normal_cache:
        import src.adapters.rendering.moderngl_renderer_impl as implementation

        original_normal = implementation._mat3_normal
        cache: dict[bytes, object] = {}
        counts = {"hits": 0, "misses": 0}

        def cached_normal(matrix):
            key = matrix.tobytes()
            value = cache.get(key)
            if value is None:
                counts["misses"] += 1
                value = original_normal(matrix)
                cache[key] = value
            else:
                counts["hits"] += 1
            return value

        implementation._mat3_normal = cached_normal
        try:
            cached = variant(
                "pie_fast_persistent_normal_cache",
                interactive=True,
                cull_faces=False,
            )
        finally:
            implementation._mat3_normal = original_normal
        normal_cache_report = {
            "cache_entries": len(cache),
            **counts,
            **{key: value for key, value in cached.items() if key != "image"},
        }

    nodes = list(model.all_nodes())
    meshes = [
        node
        for node in nodes
        if getattr(node, "vertices", None) and getattr(node, "faces", None)
    ]
    active_lights = [
        node
        for node in nodes
        if bool(getattr(node, "is_light", False))
        and bool(getattr(node, "light_enabled", True))
        and not bool(getattr(node, "_gr_light_hidden", False))
        and not bool(getattr(node, "_gr_light_deleted", False))
    ]
    context = getattr(renderer, "_ctx", None)
    context_info = dict(getattr(context, "info", {}) or {}) if context is not None else {}
    gl_diagnostics = {
        "context_created": context is not None,
        "context_version_code": int(getattr(context, "version_code", 0) or 0)
        if context is not None
        else 0,
        "vendor": str(context_info.get("GL_VENDOR", "") or ""),
        "renderer": str(context_info.get("GL_RENDERER", "") or ""),
        "version": str(context_info.get("GL_VERSION", "") or ""),
        "shading_language": str(
            context_info.get("GL_SHADING_LANGUAGE_VERSION", "") or ""
        ),
        "max_texture_size": int(context_info.get("GL_MAX_TEXTURE_SIZE", 0) or 0),
        "max_vertex_uniform_components": int(
            context_info.get("GL_MAX_VERTEX_UNIFORM_COMPONENTS", 0) or 0
        ),
        "extension_count": len(getattr(context, "extensions", ()) or ())
        if context is not None
        else 0,
        "gpu_skinning_enabled": bool(
            getattr(__import__(
                "src.adapters.rendering.moderngl_renderer_impl",
                fromlist=["_GPU_SKINNING"],
            ), "_GPU_SKINNING", False)
        ),
    }
    args.image_dir.mkdir(parents=True, exist_ok=True)
    images = {
        "fast_two_sided_scene": fast["image"],
        "fast_cw_backface_cull_scene": culled["image"],
        "fast_no_frustum_scene": no_frustum["image"],
        "fast_unlit": unlit["image"],
        "fast_lightmap_preview": lightmap_preview["image"],
    }
    image_paths = {}
    for label, image in images.items():
        path = args.image_dir / f"{label}.png"
        image.save(path)
        image_paths[label] = str(path.resolve())

    return {
        "fixture": "K2:207tel retained PIE",
        "headless_only": True,
        "canvas": [args.width, args.height],
        "camera": {
            "target": list(camera.target),
            "azimuth": camera.azimuth,
            "elevation": camera.elevation,
            "distance": camera.distance,
            "fov": camera.fov,
        },
        "node_count": len(nodes),
        "mesh_count": len(meshes),
        "triangle_count": sum(len(node.faces or ()) for node in meshes),
        "texture_name_count": len(names),
        "resident_texture_count": len(textures),
        "active_scene_light_count": len(active_lights),
        "shader_scene_light_count": min(16, len(active_lights)),
        "texture_residency_ms": texture_ms,
        "mesh_upload_frames": upload_frames,
        "gl_diagnostics": gl_diagnostics,
        "build_phases": build_phases,
        "actors": actor_report,
        "variants": {
            "fast_no_cull": {key: value for key, value in fast.items() if key != "image"},
            "hq_msaa_no_cull": {key: value for key, value in hq.items() if key != "image"},
            "fast_cw_backface_cull": {
                key: value for key, value in culled.items() if key != "image"
            },
            "fast_no_frustum_culling": {
                key: value for key, value in no_frustum.items() if key != "image"
            },
            "fast_unlit": {
                key: value for key, value in unlit.items() if key != "image"
            },
            "fast_lightmap_preview": {
                key: value for key, value in lightmap_preview.items() if key != "image"
            },
            "normal_cache": normal_cache_report,
        },
        "pose_churn_diagnosis": pose_churn_report,
        "cw_backface_cull_image_delta": _image_delta(fast["image"], culled["image"]),
        "unlit_image_delta": _image_delta(fast["image"], unlit["image"]),
        "lightmap_preview_image_delta": _image_delta(
            fast["image"], lightmap_preview["image"]
        ),
        "image_paths": image_paths,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k2-root", type=Path, default=DEFAULT_K2)
    parser.add_argument("--width", type=int, default=1032)
    parser.add_argument("--height", type=int, default=357)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--frames", type=int, default=6)
    parser.add_argument("--diagnose-normal-cache", action="store_true")
    parser.add_argument("--diagnose-pose-churn", action="store_true")
    parser.add_argument("--pose-churn-warmup", type=int, default=2)
    parser.add_argument("--pose-churn-frames", type=int, default=8)
    parser.add_argument(
        "--image-dir",
        type=Path,
        default=ROOT / "Saved" / "Profiles" / "map_studio_207tel_pie_retained_frames",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=ROOT / "Saved" / "Profiles" / "map_studio_207tel_pie_retained.json",
    )
    args = parser.parse_args()
    _configure_python_roots()
    report = _profile(args)
    payload = json.dumps(report, indent=2, default=str)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
