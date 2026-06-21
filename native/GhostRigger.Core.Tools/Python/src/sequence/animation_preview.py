"""Object-scoped animation preview helpers shared by browser and sequences."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable


RuntimeModelResolver = Callable[[object], object | None]


@dataclass(frozen=True)
class AnimationPreviewTarget:
    """Resolved scene object and runtime model used for preview/playback."""

    scene_object: object | None
    model: object | None
    object_id: str = ""
    object_name: str = ""
    model_name: str = ""
    scene_import_id: str = ""
    character_instance_id: str = ""
    game: str = ""
    supermodel: str = ""

    @property
    def valid(self) -> bool:
        return self.model is not None

    def to_choice(self) -> dict[str, str]:
        label = self.object_name or self.model_name or self.object_id or "Model"
        model_label = self.model_name
        if model_label and model_label.lower() != label.lower():
            label = f"{label} ({model_label})"
        return {
            "id": self.object_id,
            "label": label,
            "name": self.object_name,
            "model": self.model_name,
            "game": self.game,
        }


def build_preview_target(
    scene_object: object | None,
    *,
    model: object | None = None,
    runtime_model_resolver: RuntimeModelResolver | None = None,
    fallback_model: object | None = None,
    fallback_object_id: str = "",
    fallback_name: str = "",
    fallback_game: str = "",
    fallback_supermodel: str = "",
) -> AnimationPreviewTarget:
    """Build a stable renderer-facing target for a scene object/model pair."""

    resolved_model = model
    if resolved_model is None and scene_object is not None and runtime_model_resolver is not None:
        try:
            resolved_model = runtime_model_resolver(scene_object)
        except Exception:
            resolved_model = None
    if resolved_model is None and scene_object is not None:
        metadata = _metadata(scene_object)
        resolved_model = metadata.get("_runtime_model")
    if resolved_model is None:
        resolved_model = fallback_model

    metadata = _metadata(scene_object)
    object_id = _clean(getattr(scene_object, "id", "") if scene_object is not None else "") or _clean(fallback_object_id)
    object_name = _clean(getattr(scene_object, "name", "") if scene_object is not None else "") or _clean(fallback_name)
    model_name = _clean(getattr(resolved_model, "name", "") if resolved_model is not None else "")
    scene_import_id = _clean(metadata.get("scene_import_id") or object_id)
    character_id = _clean(metadata.get("character_instance_id") or object_id)
    game = _game_for(scene_object, resolved_model, fallback_game)
    supermodel = _clean(fallback_supermodel or getattr(resolved_model, "supermodel", "") if resolved_model is not None else fallback_supermodel)
    return AnimationPreviewTarget(
        scene_object=scene_object,
        model=resolved_model,
        object_id=object_id,
        object_name=object_name,
        model_name=model_name,
        scene_import_id=scene_import_id,
        character_instance_id=character_id,
        game=game,
        supermodel=supermodel,
    )


def iter_scene_preview_targets(
    scene_objects: Iterable[object],
    *,
    runtime_model_resolver: RuntimeModelResolver | None = None,
    model_filter: Callable[[object], bool] | None = None,
    fallback_game: str = "",
) -> list[AnimationPreviewTarget]:
    targets: list[AnimationPreviewTarget] = []
    seen: set[str] = set()
    for obj in scene_objects:
        target = build_preview_target(
            obj,
            runtime_model_resolver=runtime_model_resolver,
            fallback_game=fallback_game,
        )
        if not target.valid:
            continue
        if model_filter is not None:
            try:
                if not model_filter(target.model):
                    continue
            except Exception:
                continue
        stable = target.object_id or f"model-{id(target.model)}"
        if stable in seen:
            continue
        seen.add(stable)
        targets.append(target)
    return targets


def tag_pose_for_preview_target(
    pose,
    target: AnimationPreviewTarget | None,
    *,
    anim_name: str = "",
    game: str = "",
) -> object:
    """Attach renderer-scoping metadata to a sampled animation pose."""

    if pose is None or target is None:
        return pose
    try:
        model = target.model
        setattr(pose, "_gr_animation_source_model_id", id(model) if model is not None else 0)
        setattr(pose, "_gr_animation_source_model_name", target.model_name)
        if target.object_id:
            setattr(pose, "_gr_animation_scene_object_id", target.object_id)
        if target.scene_import_id:
            setattr(pose, "_gr_animation_scene_import_id", target.scene_import_id)
        if target.character_instance_id:
            setattr(pose, "_gr_animation_character_instance_id", target.character_instance_id)
        if anim_name:
            setattr(pose, "_gr_animation_name", str(anim_name))
        pose_game = str(game or target.game or "").upper()
        if pose_game:
            setattr(pose, "_gr_animation_game", pose_game)
    except Exception:
        pass
    return pose


def _metadata(obj: object | None) -> dict[str, Any]:
    value = getattr(obj, "metadata", None) if obj is not None else None
    return value if isinstance(value, dict) else {}


def _game_for(scene_object: object | None, model: object | None, fallback: str = "") -> str:
    ref = getattr(scene_object, "source_ref", None) if scene_object is not None else None
    for value in (
        getattr(ref, "game", ""),
        getattr(model, "_gr_source_game", "") if model is not None else "",
        getattr(model, "game", "") if model is not None else "",
        getattr(model, "game_tag", "") if model is not None else "",
        getattr(model, "game_version", "") if model is not None else "",
        fallback,
    ):
        if hasattr(value, "value"):
            value = value.value
        text = str(value or "").upper()
        if "K2" in text or "KOTOR2" in text or "2" == text:
            return "K2"
        if "K1" in text or "KOTOR" in text or "1" == text:
            return "K1"
    return ""


def _clean(value: object) -> str:
    return str(value or "").strip()
