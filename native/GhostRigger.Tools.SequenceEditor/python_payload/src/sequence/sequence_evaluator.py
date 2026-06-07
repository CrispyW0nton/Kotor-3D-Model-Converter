"""Deterministic frame evaluator for GhostRigger Level Sequences."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.math.camera_math import euler_degrees_to_quat, quat_to_euler_degrees

from .sequence_binding import SequenceBinding, SequenceTargetType
from .sequence_manager import ensure_sequence_object_id
from .sequence_model import GhostRiggerLevelSequence
from .tracks.camera_cut_track import CameraCutTrack
from .tracks.camera_property_track import CameraPropertyTrack
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

    def __init__(self, viewport=None) -> None:
        self.viewport = viewport

    def all_objects(self) -> list[object]:
        objects: list[object] = []
        model = getattr(self.viewport, "model", None)
        if model is not None:
            try:
                objects.extend(list(model.all_nodes()) if hasattr(model, "all_nodes") else [])
            except Exception:
                pass
        camera_manager = getattr(self.viewport, "camera_manager", None)
        if camera_manager is not None:
            for camera in camera_manager.get_all_cameras():
                if camera.original_ref is not None:
                    objects.append(camera.original_ref)
        light_manager = getattr(getattr(self.viewport, "parent", lambda: None)(), "lighting_panel", None)
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
    def __init__(self, viewport=None) -> None:
        self.viewport = viewport
        self.resolver = SceneObjectResolver(viewport)
        self._captured: dict[str, ObjectState] = {}
        self.restore_mode = "restore"
        self.last_warning = ""
        self.event_log: list[dict[str, Any]] = []

    def set_viewport(self, viewport) -> None:
        self.viewport = viewport
        self.resolver = SceneObjectResolver(viewport)

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
                dirty.update(self._apply_track(binding, obj, track, frame))
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

    def _apply_track(self, binding: SequenceBinding, obj: object, track, frame: int) -> set[str]:
        value = track.evaluate(frame)
        if value is None:
            return set()
        if isinstance(track, TransformTrack):
            self._apply_transform(obj, value)
            return {"transforms"}
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
        if dirty.intersection({"transforms", "visibility", "materials"}):
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
                    scene=bool(dirty.intersection({"transforms", "visibility", "materials"})),
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
