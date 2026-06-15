"""Deterministic frame evaluator for GhostRigger Level Sequences."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from src.math.camera_math import euler_degrees_to_quat, quat_to_euler_degrees

from .sequence_binding import SequenceBinding, SequenceTargetType
from .sequence_manager import ensure_sequence_object_id
from .sequence_model import GhostRiggerLevelSequence
from .tracks.camera_cut_track import CameraCutTrack
from .tracks.camera_property_track import CameraPropertyTrack
from .tracks.character_track import CharacterTrack
from .tracks.event_track import EventTrack
from .tracks.light_property_track import LightPropertyTrack
from .tracks.material_track import MaterialTrack
from .tracks.sub_sequence_track import SubSequenceTrack
from .tracks.transform_property_track import TransformPropertyTrack
from .tracks.transform_track import TransformTrack
from .tracks.visibility_track import VisibilityTrack


def _vec3(value, fallback=(0.0, 0.0, 0.0)) -> tuple[float, float, float]:
    try:
        seq = list(value)
        return (float(seq[0]), float(seq[1]), float(seq[2]))
    except Exception:
        return fallback


def _quat(value, fallback=(0.0, 0.0, 0.0, 1.0)) -> tuple[float, float, float, float]:
    try:
        seq = list(value)
        return (float(seq[0]), float(seq[1]), float(seq[2]), float(seq[3]))
    except Exception:
        return fallback


@dataclass
class ObjectState:
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)
    hidden: bool = False
    attrs: dict[str, Any] = field(default_factory=dict)


class SceneObjectResolver:
    """Resolve sequence bindings against the current GhostRigger viewport/model."""

    def __init__(self, viewport=None, owner=None) -> None:
        self.viewport = viewport
        self.owner = owner

    def all_objects(self) -> list[object]:
        objects: list[object] = []
        parent = getattr(self.viewport, "parent", lambda: None)()
        scene_manager = getattr(self.owner, "scene_manager", None) or getattr(parent, "scene_manager", None)
        if scene_manager is not None:
            try:
                objects.extend(list(scene_manager.get_scene_objects()))
            except Exception:
                active_scene = getattr(scene_manager, "active_scene", None)
                objects.extend(list(getattr(active_scene, "objects", []) or []))
        model = getattr(self.viewport, "model", None)
        if model is not None:
            objects.append(model)
            try:
                objects.extend(list(model.all_nodes()) if hasattr(model, "all_nodes") else [])
            except Exception:
                pass
        camera_manager = getattr(self.viewport, "camera_manager", None)
        if camera_manager is not None:
            for camera in camera_manager.get_all_cameras():
                if camera.original_ref is not None:
                    objects.append(camera.original_ref)
        light_manager = getattr(parent, "lighting_panel", None)
        manager = getattr(light_manager, "manager", None)
        if manager is not None:
            for light in manager.all_lights():
                if light.original_ref is not None:
                    objects.append(light.original_ref)
        seen: set[int] = set()
        unique: list[object] = []
        for obj in objects:
            if obj is None or id(obj) in seen:
                continue
            seen.add(id(obj))
            unique.append(obj)
        return unique

    def resolve(self, binding: SequenceBinding) -> object | None:
        target_id = str(binding.target_object_id or "")
        if not target_id:
            return None
        for obj in self.all_objects():
            if ensure_sequence_object_id(obj) == target_id:
                return obj
        return None

    def camera_for_binding(self, binding: SequenceBinding):
        obj = self.resolve(binding)
        camera_manager = getattr(self.viewport, "camera_manager", None)
        if obj is not None and camera_manager is not None:
            camera = camera_manager.find_by_original(obj)
            if camera is not None:
                return camera
        return None


class SequenceEvaluator:
    def __init__(self, viewport=None, owner=None) -> None:
        self.viewport = viewport
        self.owner = owner
        self.resolver = SceneObjectResolver(viewport, owner)
        self._captured: dict[str, ObjectState] = {}
        self._character_engines: dict[tuple[int, str], Any] = {}
        self.restore_mode = "restore"
        self.last_warning = ""
        self.event_log: list[dict[str, Any]] = []

    def set_viewport(self, viewport, owner=None) -> None:
        self.viewport = viewport
        if owner is not None:
            self.owner = owner
        self.resolver = SceneObjectResolver(viewport, self.owner)

    def capture_original_state(self, sequence: GhostRiggerLevelSequence) -> None:
        for binding in sequence.bindings:
            obj = self.resolver.resolve(binding)
            if obj is None or binding.binding_id in self._captured:
                continue
            self._captured[binding.binding_id] = self._snapshot(obj)

    def restore_original_state(self, sequence: GhostRiggerLevelSequence) -> None:
        for binding in sequence.bindings:
            obj = self.resolver.resolve(binding)
            state = self._captured.get(binding.binding_id)
            if obj is not None and state is not None:
                self._apply_snapshot(obj, state)
        self._captured.clear()
        self._refresh_viewport({"transforms", "visibility", "cameras", "lighting", "materials"})

    def evaluate(
        self,
        sequence: GhostRiggerLevelSequence,
        frame: int | None = None,
        *,
        scrubbing: bool = True,
        previous_frame: int | None = None,
        fire_events: bool = False,
    ) -> None:
        frame = sequence.set_current_frame(sequence.current_frame if frame is None else int(frame))
        self.capture_original_state(sequence)
        self.last_warning = ""
        dirty: set[str] = set()
        for binding in sequence.bindings:
            obj = self.resolver.resolve(binding)
            binding.metadata["missing"] = obj is None
            if obj is None or not binding.active:
                continue
            self._prepare_binding_transform_eval(binding, obj, frame)
            for track in binding.tracks:
                if track.locked or not track.enabled or track.muted:
                    continue
                dirty.update(self._apply_track(sequence, binding, obj, track, frame))
        if self._apply_master_tracks(sequence, frame):
            dirty.add("cameras")
        if fire_events and previous_frame is not None:
            self._fire_events(sequence, previous_frame, frame, scrubbing=scrubbing)
        self._refresh_viewport(dirty)

    def active_camera_binding(self, sequence: GhostRiggerLevelSequence, frame: int | None = None) -> SequenceBinding | None:
        frame = sequence.current_frame if frame is None else int(frame)
        for track in sequence.master_tracks:
            if isinstance(track, CameraCutTrack):
                cut = track.active_cut(frame)
                if cut is not None:
                    return sequence.binding_by_id(cut.camera_binding_id)
        return None

    def _apply_track(self, sequence: GhostRiggerLevelSequence, binding: SequenceBinding, obj: object, track, frame: int) -> set[str]:
        value = track.evaluate(frame)
        if value is None:
            return set()
        if isinstance(track, TransformTrack):
            self._apply_transform(obj, value)
            return {"transforms"}
        elif isinstance(track, CharacterTrack):
            return self._apply_character_track(sequence, binding, obj, track, frame)
        elif isinstance(track, TransformPropertyTrack):
            self._apply_transform_property(obj, track.property_name, value)
            return {"transforms"}
        elif isinstance(track, VisibilityTrack):
            self._apply_visibility(obj, bool(value), binding)
            return {"visibility"}
        elif isinstance(track, CameraPropertyTrack):
            self._apply_camera_property(obj, track.property_name, value)
            return {"cameras"}
        elif isinstance(track, LightPropertyTrack):
            self._apply_light_property(obj, track.property_name, value)
            return {"lighting"}
        elif isinstance(track, MaterialTrack):
            self._apply_material_property(obj, track.property_name, value)
            return {"materials"}
        return set()

    def _apply_character_track(
        self,
        sequence: GhostRiggerLevelSequence,
        binding: SequenceBinding,
        obj: object,
        track: CharacterTrack,
        frame: int,
    ) -> set[str]:
        keys = track.active_animation_keys(frame) if hasattr(track, "active_animation_keys") else []
        active_keys = [key for key in keys if isinstance(getattr(key, "value", None), dict) and str(key.value.get("animation") or "").strip()]
        if not active_keys:
            if self.viewport is not None and hasattr(self.viewport, "set_animation_pose"):
                self.viewport.set_animation_pose(None)
                return {"animation"}
            return set()
        viewport = self.viewport
        if viewport is None or not hasattr(viewport, "set_animation_pose"):
            return set()
        model = self._character_animation_model(obj, binding=binding, key=active_keys[0])
        if model is None:
            self.last_warning = f"No animated model available for {binding.display_name}."
            return set()
        try:
            from src.core.animation.animation_engine import AnimationEngine, SuperModelResolver

            manager = self._resource_manager()
            if manager is not None:
                SuperModelResolver.configure(manager)
            inheritance_game = self._animation_inheritance_game(model)
            inheritance_supermodel = self._animation_inheritance_supermodel(model)
            evaluated: list[dict[str, Any]] = []
            with self._animation_resolution_context(model, inheritance_game, inheritance_supermodel):
                for key in active_keys:
                    anim_name = str(key.value.get("animation") or "").strip()
                    engine_key = (id(model), anim_name.lower(), inheritance_game, inheritance_supermodel)
                    engine = self._character_engines.get(engine_key)
                    if engine is None or getattr(engine, "model", None) is not model:
                        engine = AnimationEngine(model)
                        self._character_engines[engine_key] = engine
                    loop = bool(key.value.get("loop", True))
                    if getattr(getattr(engine, "current_animation", None), "name", "").lower() != anim_name.lower():
                        if not engine.play(anim_name, loop=loop, blend=False):
                            self.last_warning = f"Animation '{anim_name}' is not available for {binding.display_name}."
                            return set()
                        engine.stop()
                    seconds = self._animation_clip_seconds(sequence, key, frame)
                    engine.seek(seconds)
                    pose = engine.evaluate()
                    current = engine.current_animation
                    evaluated.append(
                        {
                            "key": key,
                            "name": anim_name,
                            "pose": pose,
                            "time": float(getattr(engine, "current_time", seconds) or 0.0),
                            "length": float(getattr(current, "length", key.value.get("length", 0.0)) or 0.0),
                        }
                    )
            if not evaluated:
                return set()
            pose = self._compose_animation_poses(model, evaluated, frame)
            names = [item["name"] for item in evaluated]
            length = max((float(item.get("length", 0.0) or 0.0) for item in evaluated), default=0.0)
            time_value = float(evaluated[0].get("time", 0.0) or 0.0)
            self._tag_animation_pose(pose, model, " + ".join(names))
            viewport.set_animation_pose(pose, name=" + ".join(names), time=time_value, length=length)
            return {"animation"}
        except Exception as exc:
            self.last_warning = f"Animation track failed for {binding.display_name}: {exc}"
            return set()

    def _animation_clip_seconds(self, sequence: GhostRiggerLevelSequence, key, frame: int) -> float:
        elapsed_frames = max(0.0, float(frame) - float(key.frame))
        length = float(key.value.get("length", 0.0) or 0.0)
        duration_frames = float(key.value.get("duration_frames", 0.0) or 0.0)
        if length > 0.0 and duration_frames > 0.0:
            return min(length, (elapsed_frames / max(0.001, duration_frames)) * length)
        return elapsed_frames / max(0.001, float(sequence.frame_rate or 24.0))

    def _compose_animation_poses(self, model, evaluated: list[dict[str, Any]], frame: int):
        ordered = sorted(
            evaluated,
            key=lambda item: (
                float(item["key"].frame),
                int(item["key"].value.get("priority", 0) or 0),
            ),
        )
        base_item = next((item for item in ordered if self._clip_blend_mode(item["key"], item["name"], 0) == "base"), ordered[0])
        base_pose = base_item["pose"]
        for item in ordered:
            if item is base_item:
                continue
            key = item["key"]
            mode = self._clip_blend_mode(key, item["name"], 1)
            weight = self._clip_blend_weight(key, frame)
            if weight <= 0.0:
                continue
            mask = self._clip_mask_nodes(model, key, item["name"], item["pose"], mode)
            base_pose = self._blend_animation_pose(base_pose, item["pose"], weight, mask)
        return base_pose

    def _clip_blend_mode(self, key, anim_name: str, index: int) -> str:
        mode = str(key.value.get("blend_mode", "auto") or "auto").strip().lower()
        if mode in {"base", "replace", "overlay", "additive"}:
            return "base" if mode == "replace" else mode
        if index == 0 and not self._is_partial_animation_name(anim_name):
            return "base"
        return "overlay" if self._is_partial_animation_name(anim_name) else "base"

    def _clip_blend_weight(self, key, frame: int) -> float:
        value = key.value
        base_weight = max(0.0, min(1.0, float(value.get("weight", 1.0) if value.get("weight", 1.0) is not None else 1.0)))
        duration = float(value.get("duration_frames", 0.0) or 0.0)
        if duration <= 0.0:
            return base_weight
        elapsed = max(0.0, float(frame) - float(key.frame))
        fade_in = max(0.0, min(float(value.get("fade_in_frames", 0.0) or 0.0), duration))
        fade_out = max(0.0, min(float(value.get("fade_out_frames", 0.0) or 0.0), duration))
        factor = 1.0
        if fade_in > 0.0:
            factor = min(factor, elapsed / fade_in)
        if fade_out > 0.0:
            factor = min(factor, max(0.0, (duration - elapsed) / fade_out))
        return max(0.0, min(1.0, base_weight * factor))

    def _clip_mask_nodes(self, model, key, anim_name: str, pose, mode: str) -> set[str] | None:
        raw_mask = str(key.value.get("mask", "auto") or "auto").strip().lower()
        if raw_mask in {"", "full", "all", "none"} or mode == "base":
            return None
        custom = key.value.get("nodes") or key.value.get("mask_nodes")
        if isinstance(custom, (list, tuple, set)):
            return {str(item).lower() for item in custom if str(item).strip()}
        if raw_mask == "auto":
            raw_mask = "head" if self._is_head_animation_name(anim_name) else "upper"
        hints = self._node_mask_hints(raw_mask)
        if not hints:
            return None
        nodes = {
            name
            for name in getattr(pose, "nodes", {})
            if any(hint in str(name).lower() for hint in hints)
        }
        return nodes or None

    @staticmethod
    def _is_partial_animation_name(anim_name: str) -> bool:
        name = str(anim_name or "").lower()
        return any(token in name for token in ("turn", "thurn", "hturn", "look", "talk", "listen", "head", "pause", "gesture", "point", "nod", "shake"))

    @staticmethod
    def _is_head_animation_name(anim_name: str) -> bool:
        name = str(anim_name or "").lower()
        return any(token in name for token in ("turn", "thurn", "hturn", "look", "talk", "listen", "head", "nod", "shake"))

    @staticmethod
    def _node_mask_hints(mask: str) -> tuple[str, ...]:
        if mask == "head":
            return ("head", "neck", "face", "jaw", "mouth", "lip", "eye", "brow", "tongue", "ear", "horn", "snout")
        if mask == "upper":
            return ("head", "neck", "face", "jaw", "mouth", "eye", "horn", "spine", "chest", "torso", "clav", "shldr", "shoulder", "arm", "fore", "hand", "wrist")
        return tuple(str(mask or "").split())

    def _blend_animation_pose(self, base_pose, overlay_pose, weight: float, mask: set[str] | None):
        if base_pose is None:
            return overlay_pose
        if overlay_pose is None:
            return base_pose
        alpha = max(0.0, min(1.0, float(weight)))
        if alpha <= 0.0:
            return base_pose
        for name, overlay_node in list(getattr(overlay_pose, "nodes", {}).items()):
            node_key = str(name).lower()
            if mask is not None and node_key not in mask:
                continue
            base_node = base_pose.nodes.get(node_key) if hasattr(base_pose, "nodes") else None
            if base_node is None:
                base_pose.nodes[node_key] = overlay_node
                continue
            base_pose.nodes[node_key] = self._blend_node_pose(base_node, overlay_node, alpha)
        return base_pose

    @staticmethod
    def _blend_node_pose(base_node, overlay_node, alpha: float):
        node_type = type(overlay_node)
        bp = tuple(float(value) for value in getattr(base_node, "position", (0.0, 0.0, 0.0)))
        op = tuple(float(value) for value in getattr(overlay_node, "position", bp))
        position = (
            bp[0] + (op[0] - bp[0]) * alpha,
            bp[1] + (op[1] - bp[1]) * alpha,
            bp[2] + (op[2] - bp[2]) * alpha,
        )
        rotation = SequenceEvaluator._slerp_quat(
            tuple(float(value) for value in getattr(base_node, "rotation", (0.0, 0.0, 0.0, 1.0))),
            tuple(float(value) for value in getattr(overlay_node, "rotation", (0.0, 0.0, 0.0, 1.0))),
            alpha,
        )
        scale = float(getattr(base_node, "scale", 1.0) or 1.0) + (float(getattr(overlay_node, "scale", 1.0) or 1.0) - float(getattr(base_node, "scale", 1.0) or 1.0)) * alpha
        alpha_value = getattr(overlay_node, "alpha", None) if getattr(overlay_node, "alpha", None) is not None else getattr(base_node, "alpha", None)
        selfillum = getattr(overlay_node, "selfillum", None) if getattr(overlay_node, "selfillum", None) is not None else getattr(base_node, "selfillum", None)
        return node_type(
            name=getattr(overlay_node, "name", getattr(base_node, "name", "")),
            position=position,
            rotation=rotation,
            scale=scale,
            alpha=alpha_value,
            selfillum=selfillum,
        )

    @staticmethod
    def _slerp_quat(q1, q2, t: float) -> tuple[float, float, float, float]:
        import math

        x1, y1, z1, w1 = q1
        x2, y2, z2, w2 = q2
        dot = x1 * x2 + y1 * y2 + z1 * z2 + w1 * w2
        if dot < 0.0:
            x2, y2, z2, w2 = -x2, -y2, -z2, -w2
            dot = -dot
        if dot > 0.9995:
            result = (
                x1 + (x2 - x1) * t,
                y1 + (y2 - y1) * t,
                z1 + (z2 - z1) * t,
                w1 + (w2 - w1) * t,
            )
        else:
            theta_0 = math.acos(max(-1.0, min(1.0, dot)))
            sin_theta_0 = math.sin(theta_0)
            theta = theta_0 * t
            sin_theta = math.sin(theta)
            s0 = math.cos(theta) - dot * sin_theta / max(1e-9, sin_theta_0)
            s1 = sin_theta / max(1e-9, sin_theta_0)
            result = (
                s0 * x1 + s1 * x2,
                s0 * y1 + s1 * y2,
                s0 * z1 + s1 * z2,
                s0 * w1 + s1 * w2,
            )
        mag = math.sqrt(sum(value * value for value in result))
        if mag <= 1e-9:
            return (0.0, 0.0, 0.0, 1.0)
        return tuple(value / mag for value in result)

    def _character_animation_model(self, obj: object | None, *, binding: SequenceBinding | None = None, key=None):
        source_names = self._animation_source_names(binding, key)
        named = self._find_named_animation_model(source_names)
        if named is not None:
            return named
        metadata = getattr(obj, "metadata", None)
        runtime_model = metadata.get("_runtime_model") if isinstance(metadata, dict) else None
        candidates = [
            runtime_model,
            obj,
            getattr(obj, "model", None) if obj is not None else None,
            getattr(obj, "mdl_model", None) if obj is not None else None,
            getattr(obj, "source_model", None) if obj is not None else None,
        ]
        for candidate in candidates:
            if self._is_animation_model(candidate):
                return candidate
        return None

    def _animation_source_names(self, binding: SequenceBinding | None, key) -> set[str]:
        names: set[str] = set()
        if binding is not None:
            for value in (binding.display_name, binding.target_object_name):
                clean = str(value or "").strip()
                if clean:
                    names.add(clean.lower())
        value = getattr(key, "value", None)
        if isinstance(value, dict):
            for field in ("source_model", "source_model_name", "source", "model", "model_name"):
                clean = str(value.get(field) or "").strip()
                if clean and clean.lower() not in {"local", "body", "head", "attachment", "inherited"}:
                    names.add(clean.lower())
        return names

    def _find_named_animation_model(self, names: set[str]):
        if not names:
            return None
        for obj in self.resolver.all_objects():
            metadata = getattr(obj, "metadata", None)
            runtime_model = metadata.get("_runtime_model") if isinstance(metadata, dict) else None
            for candidate in (runtime_model, obj, getattr(obj, "model", None), getattr(obj, "mdl_model", None), getattr(obj, "source_model", None)):
                if candidate is None:
                    continue
                candidate_name = str(getattr(candidate, "name", "") or getattr(obj, "name", "") or "").strip().lower()
                if candidate_name in names and self._is_animation_model(candidate):
                    return candidate
        return None

    @staticmethod
    def _is_animation_model(candidate) -> bool:
        if candidate is None:
            return False
        if bool(getattr(candidate, "_gr_scene_composite", False)):
            return False
        name = str(getattr(candidate, "name", "") or "")
        if name.lower() == "untitled scene":
            return False
        return any(hasattr(candidate, attr) for attr in ("animations", "supermodel", "all_nodes", "root_node"))

    def _resource_manager(self):
        for owner in (self.viewport, self.owner, getattr(self.viewport, "parent", lambda: None)()):
            if owner is None:
                continue
            getter = getattr(owner, "_get_resource_manager", None)
            if callable(getter):
                try:
                    manager = getter()
                    if manager is not None:
                        return manager
                except Exception:
                    pass
            manager = getattr(owner, "resource_manager", None)
            if manager is not None:
                return manager
        return None

    def _animation_inheritance_game(self, model) -> str:
        owner = self.owner or getattr(self.viewport, "parent", lambda: None)()
        getter = getattr(owner, "_animation_inheritance_game", None)
        if callable(getter):
            try:
                value = str(getter(model) or "").upper()
                if value:
                    return value
            except Exception:
                pass
        game = getattr(model, "game_version", None)
        try:
            value = game.value if hasattr(game, "value") else str(game or "")
        except Exception:
            value = ""
        value = str(value or "").upper()
        return "K2" if "K2" in value else "K1"

    def _animation_inheritance_supermodel(self, model) -> str:
        owner = self.owner or getattr(self.viewport, "parent", lambda: None)()
        getter = getattr(owner, "_animation_inheritance_supermodel", None)
        if callable(getter):
            try:
                return str(getter(model) or "").strip()
            except Exception:
                pass
        return str(getattr(model, "supermodel", "") or "").strip()

    @contextmanager
    def _animation_resolution_context(self, model, game: str, supermodel: str = ""):
        if model is None:
            yield
            return
        owner = self.owner or getattr(self.viewport, "parent", lambda: None)()
        owner_context = getattr(owner, "_animation_resolution_context", None)
        if callable(owner_context):
            with owner_context(model, game, supermodel):
                yield
            return

        had_game_version = hasattr(model, "game_version")
        original_game_version = getattr(model, "game_version", None)
        original_supermodel = getattr(model, "supermodel", None)
        try:
            game = str(game or "").upper()
            if game in {"K1", "K2"}:
                try:
                    from src.core.geometry.model_data import GameVersion

                    model.game_version = GameVersion.K2 if game == "K2" else GameVersion.K1
                except Exception:
                    pass
            if supermodel:
                model.supermodel = supermodel
            yield
        finally:
            if original_supermodel is not None or hasattr(model, "supermodel"):
                model.supermodel = original_supermodel
            if had_game_version:
                model.game_version = original_game_version

    def _tag_animation_pose(self, pose, model, anim_name: str) -> None:
        if pose is None:
            return
        try:
            setattr(pose, "_gr_animation_source_model_id", id(model) if model is not None else 0)
            setattr(pose, "_gr_animation_source_model_name", str(getattr(model, "name", "") or ""))
            setattr(pose, "_gr_animation_name", str(anim_name or ""))
        except Exception:
            pass

    def _apply_master_tracks(self, sequence: GhostRiggerLevelSequence, frame: int) -> bool:
        dirty = False
        active_binding = self.active_camera_binding(sequence, frame)
        if active_binding is not None and self.viewport is not None:
            camera = self.resolver.camera_for_binding(active_binding)
            if camera is not None and hasattr(self.viewport, "switch_to_camera"):
                self.viewport.switch_to_camera(camera.id)
                dirty = True
        elif any(isinstance(track, CameraCutTrack) for track in sequence.master_tracks):
            self.last_warning = "No camera cut track active."
        for track in sequence.master_tracks:
            if isinstance(track, SubSequenceTrack):
                for section in track.sections:
                    if section.contains(frame) and not section.muted:
                        sequence.metadata["active_sub_sequence"] = section.serialize()
        return dirty

    def _fire_events(self, sequence: GhostRiggerLevelSequence, previous_frame: int, frame: int, *, scrubbing: bool) -> None:
        for track in sequence.all_tracks():
            if isinstance(track, EventTrack) and track.enabled and not track.muted:
                for event in track.events_between(previous_frame, frame, scrubbing=scrubbing):
                    safe_event = {
                        "event_name": str(event.get("event_name") or "Event"),
                        "frame": int(event.get("frame", frame) or frame),
                        "parameters": dict(event.get("parameters", {}) or {}),
                    }
                    self.event_log.append(safe_event)

    def _apply_transform(self, obj: object, value: dict[str, Any]) -> None:
        location = value.get("location", getattr(obj, "position", (0.0, 0.0, 0.0)))
        rotation = value.get("rotation", quat_to_euler_degrees(getattr(obj, "rotation", (0.0, 0.0, 0.0, 1.0))))
        scale = value.get("scale", getattr(obj, "_gr_scale", getattr(obj, "scale", (1.0, 1.0, 1.0))))
        try:
            setattr(obj, "position", _vec3(location))
            setattr(obj, "rotation", euler_degrees_to_quat(rotation))
            setattr(obj, "_gr_scale", _vec3(scale, (1.0, 1.0, 1.0)))
            setattr(obj, "_gr_sequence_eval_rotation_euler", _vec3(rotation))
            self._sync_object_transform_model(obj)
        except Exception:
            pass

    def _prepare_binding_transform_eval(self, binding: SequenceBinding, obj: object, frame: int) -> None:
        state = self._captured.get(binding.binding_id)
        has_transform_animation = any(
            isinstance(track, (TransformTrack, TransformPropertyTrack))
            and not track.locked
            and track.enabled
            and not track.muted
            for track in binding.tracks
        )
        if state is not None and has_transform_animation:
            try:
                setattr(obj, "position", tuple(state.position))
                setattr(obj, "rotation", tuple(state.rotation))
                setattr(obj, "_gr_scale", tuple(state.scale))
                self._sync_helper_pivot(obj)
            except Exception:
                pass
        rotation = getattr(obj, "rotation", (0.0, 0.0, 0.0, 1.0))
        try:
            setattr(obj, "_gr_sequence_eval_rotation_frame", int(frame))
            setattr(obj, "_gr_sequence_eval_rotation_euler", quat_to_euler_degrees(rotation))
        except Exception:
            pass

    def _apply_transform_property(self, obj: object, property_name: str, value: Any) -> None:
        prop = str(property_name or "")
        if prop == "position":
            setattr(obj, "position", _vec3(value, getattr(obj, "position", (0.0, 0.0, 0.0))))
            self._sync_object_transform_model(obj)
            return
        if prop == "rotation":
            setattr(obj, "rotation", euler_degrees_to_quat(value))
            setattr(obj, "_gr_sequence_eval_rotation_euler", _vec3(value))
            self._sync_object_transform_model(obj)
            return
        if prop == "scale":
            fallback = _vec3(getattr(obj, "_gr_scale", getattr(obj, "scale", (1.0, 1.0, 1.0))), (1.0, 1.0, 1.0))
            setattr(obj, "_gr_scale", _vec3(value, fallback))
            self._sync_object_transform_model(obj)
            return
        component_map = {
            "position_x": ("position", 0, (0.0, 0.0, 0.0)),
            "position_y": ("position", 1, (0.0, 0.0, 0.0)),
            "position_z": ("position", 2, (0.0, 0.0, 0.0)),
            "rotation_x": ("rotation", 0, (0.0, 0.0, 0.0)),
            "rotation_y": ("rotation", 1, (0.0, 0.0, 0.0)),
            "rotation_z": ("rotation", 2, (0.0, 0.0, 0.0)),
            "scale_x": ("_gr_scale", 0, (1.0, 1.0, 1.0)),
            "scale_y": ("_gr_scale", 1, (1.0, 1.0, 1.0)),
            "scale_z": ("_gr_scale", 2, (1.0, 1.0, 1.0)),
        }
        target = component_map.get(prop)
        if target is None:
            return
        attr, index, fallback = target
        if attr == "rotation":
            current = list(
                _vec3(
                    getattr(obj, "_gr_sequence_eval_rotation_euler", None),
                    quat_to_euler_degrees(getattr(obj, "rotation", (0.0, 0.0, 0.0, 1.0))),
                )
            )
            component = float(value)
            if abs(float(current[index]) - component) <= 1e-6:
                return
            current[index] = component
            setattr(obj, "rotation", euler_degrees_to_quat(current))
            setattr(obj, "_gr_sequence_eval_rotation_euler", tuple(current))
            self._sync_object_transform_model(obj)
            return
        raw = getattr(obj, attr, getattr(obj, "scale", fallback) if attr == "_gr_scale" else fallback)
        current = list(_vec3(raw, fallback))
        current[index] = float(value)
        setattr(obj, attr, tuple(current))
        self._sync_object_transform_model(obj)

    def _sync_object_transform_model(self, obj: object) -> None:
        self._sync_helper_pivot(obj)
        camera_manager = getattr(self.viewport, "camera_manager", None)
        camera = camera_manager.find_by_original(obj) if camera_manager is not None else None
        if camera is not None:
            camera.position = _vec3(getattr(obj, "position", camera.position), camera.position)
            camera.rotation = _quat(getattr(obj, "rotation", camera.rotation), camera.rotation)
            camera.apply_to_original()
        light_manager = getattr(getattr(getattr(self.viewport, "parent", lambda: None)(), "lighting_panel", None), "manager", None)
        light = light_manager.find_by_original(obj) if light_manager is not None else None
        if light is not None:
            light.position = _vec3(getattr(obj, "position", light.position), light.position)
            light.rotation = _quat(getattr(obj, "rotation", light.rotation), light.rotation)
            light.apply_to_original()

    def _sync_helper_pivot(self, obj: object) -> None:
        if not (bool(getattr(obj, "is_camera", False)) or bool(getattr(obj, "is_light", False))):
            return
        if str(getattr(obj, "_gr_pivot_edit_mode", "") or "") == "affect_pivot_only":
            return
        position = _vec3(getattr(obj, "position", (0.0, 0.0, 0.0)))
        for attr in ("_gr_pivot_world", "_gr_gizmo_world_position"):
            try:
                setattr(obj, attr, position)
            except Exception:
                pass
        try:
            setattr(obj, "_gr_pivot_world_dirty", True)
        except Exception:
            pass

    def _apply_visibility(self, obj: object, visible: bool, binding: SequenceBinding) -> None:
        target_type = binding.target_type.value if hasattr(binding.target_type, "value") else str(binding.target_type)
        if target_type == "Camera":
            setattr(obj, "_gr_camera_hidden", not bool(visible))
        elif target_type == "Light":
            setattr(obj, "_gr_light_hidden", not bool(visible))
        else:
            setattr(obj, "_gr_hidden", not bool(visible))

    def _apply_camera_property(self, obj: object, property_name: str, value: Any) -> None:
        camera_manager = getattr(self.viewport, "camera_manager", None)
        camera = camera_manager.find_by_original(obj) if camera_manager is not None else None
        target = camera if camera is not None else obj
        if property_name == "field_of_view_degrees" and camera is not None:
            camera.set_field_of_view(float(value))
        elif property_name == "focal_length_mm" and camera is not None:
            camera.set_focal_length(float(value))
        elif property_name == "target_position":
            setattr(target, property_name, _vec3(value, getattr(target, property_name, (0.0, 0.0, 1.0))))
        elif hasattr(target, property_name):
            setattr(target, property_name, value)
        if camera is not None:
            camera.apply_to_original()

    def _apply_light_property(self, obj: object, property_name: str, value: Any) -> None:
        attr_map = {
            "enabled": "light_enabled",
            "visible": "_gr_light_hidden",
            "color": "light_color",
            "intensity": "light_multiplier",
            "radius": "light_radius",
            "cone_angle": "light_cone_degrees",
            "area_size": "light_area_size",
            "ambient_only": "light_ambient_only",
            "casts_shadows": "light_shadow",
            "affects_diffuse": "light_affects_diffuse",
            "affects_specular": "light_affects_specular",
            "affects_lightmap": "light_affects_lightmap",
            "affects_environment": "light_affects_environment",
        }
        attr = attr_map.get(property_name, property_name)
        if property_name == "visible":
            setattr(obj, attr, not bool(value))
        else:
            setattr(obj, attr, value)

    def _apply_material_property(self, obj: object, property_name: str, value: Any) -> None:
        attr_map = {
            "material_color": "diffuse",
            "opacity": "alpha",
            "emissive_strength": "_gr_emissive_strength",
            "lightmap_intensity": "_gr_lightmap_intensity",
            "diffuse_enabled": "_gr_diffuse_enabled",
            "normal_enabled": "_gr_normal_enabled",
            "specular_enabled": "_gr_specular_enabled",
            "environment_enabled": "_gr_environment_enabled",
            "lightmap_enabled": "_gr_lightmap_enabled",
        }
        setattr(obj, attr_map.get(property_name, property_name), value)

    def _snapshot(self, obj: object) -> ObjectState:
        attrs = {}
        for attr in (
            "_gr_hidden",
            "_gr_camera_hidden",
            "_gr_light_hidden",
            "light_enabled",
            "light_color",
            "light_multiplier",
            "light_radius",
            "light_cone_degrees",
            "alpha",
            "diffuse",
        ):
            if hasattr(obj, attr):
                attrs[attr] = getattr(obj, attr)
        return ObjectState(
            position=_vec3(getattr(obj, "position", (0.0, 0.0, 0.0))),
            rotation=_quat(getattr(obj, "rotation", (0.0, 0.0, 0.0, 1.0))),
            scale=_vec3(getattr(obj, "_gr_scale", getattr(obj, "scale", (1.0, 1.0, 1.0))), (1.0, 1.0, 1.0)),
            hidden=bool(getattr(obj, "_gr_hidden", False)),
            attrs=attrs,
        )

    def _apply_snapshot(self, obj: object, state: ObjectState) -> None:
        setattr(obj, "position", tuple(state.position))
        setattr(obj, "rotation", tuple(state.rotation))
        setattr(obj, "_gr_scale", tuple(state.scale))
        for attr, value in state.attrs.items():
            setattr(obj, attr, value)

    def _refresh_viewport(self, dirty: set[str] | None = None) -> None:
        viewport = self.viewport
        if viewport is None:
            return
        dirty = set(dirty or {"transforms", "visibility", "cameras", "lighting", "materials"})
        refreshed = False
        refresh_names: list[str] = []
        if "lighting" in dirty:
            refresh_names.append("refresh_lighting")
        if "cameras" in dirty:
            refresh_names.append("refresh_cameras")
        if dirty.intersection({"transforms", "visibility", "materials", "animation"}):
            if hasattr(viewport, "refresh_scene_transforms"):
                refresh_names.append("refresh_scene_transforms")
            else:
                refresh_names.append("refresh_view")
        for name in refresh_names:
            method = getattr(viewport, name, None)
            if callable(method):
                try:
                    if name == "refresh_scene_transforms":
                        method("sequence evaluation")
                    else:
                        method()
                    refreshed = True
                except Exception:
                    continue
        request = getattr(viewport, "_request_render", None)
        if callable(request):
            try:
                request(
                    fast=True,
                    reason="sequence evaluation",
                    scene=bool(dirty.intersection({"transforms", "visibility", "materials", "animation"})),
                    camera=bool("cameras" in dirty),
                    overlay=True,
                    lighting=bool("lighting" in dirty),
                    gizmo=bool(dirty.intersection({"transforms", "cameras", "lighting"})),
                )
                return
            except Exception:
                pass
        if refreshed:
            return
