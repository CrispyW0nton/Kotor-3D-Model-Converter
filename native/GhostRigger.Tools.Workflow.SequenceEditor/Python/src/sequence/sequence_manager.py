"""Sequence asset lifecycle and binding helpers."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from .sequence_asset import SequenceAssetInfo, inspect_sequence_asset
from .sequence_binding import SequenceBinding, SequenceBindingType, SequenceTargetType
from .sequence_model import GhostRiggerLevelSequence
from .sequence_serialization import SEQUENCE_EXTENSION, load_sequence_file, save_sequence_file


def ensure_sequence_object_id(obj: object | None) -> str:
    if obj is None:
        return ""
    object_type = str(getattr(obj, "object_type", "") or "").lower()
    if object_type in {"camera", "light", "model", "helper"}:
        value = str(getattr(obj, "id", "") or "")
        if value:
            return value
    for attr in ("_gr_scene_object_id", "_gr_camera_id", "_gr_light_id", "_gr_sequence_id"):
        value = str(getattr(obj, attr, "") or "")
        if value:
            return value
    value = f"object-{uuid4().hex}"
    try:
        setattr(obj, "_gr_sequence_id", value)
    except Exception:
        pass
    return value


def _classify_model_target(obj: object | None) -> SequenceTargetType | None:
    if obj is None:
        return None

    for attr in ("sequence_target_type", "_gr_sequence_target_type", "target_type"):
        value = str(getattr(obj, attr, "") or "").strip()
        if not value:
            continue
        try:
            return SequenceTargetType(value)
        except ValueError:
            lowered = value.lower()
            if lowered in {"character", "humanoid", "headless_body", "head", "supermodel"}:
                return SequenceTargetType.CHARACTER
            if lowered == "creature":
                return SequenceTargetType.CREATURE
            if lowered == "droid":
                return SequenceTargetType.DROID

    looks_like_model = any(
        hasattr(obj, attr)
        for attr in ("animations", "supermodel", "model_type", "root_node", "all_nodes")
    )
    if looks_like_model:
        try:
            from src.core.geometry.model_data import classify_kotor_model

            category = classify_kotor_model(obj).category.name
            if category == "CREATURE":
                return SequenceTargetType.CREATURE
            if category == "DROID":
                return SequenceTargetType.DROID
            if category in {"FULL_BODY_CHARACTER", "MODULAR_BODY", "HEAD", "SUPERMODEL"}:
                return SequenceTargetType.CHARACTER
            if category in {"PLACEABLE", "DOOR", "WEAPON"}:
                return SequenceTargetType.PROP
            if category in {"AREA", "MODULE"}:
                return SequenceTargetType.GROUP
        except Exception:
            pass

    name = str(getattr(obj, "name", "") or "").lower()
    supermodel = str(getattr(obj, "supermodel", "") or "").lower()
    if name.startswith(("c_",)):
        return SequenceTargetType.CREATURE
    if name.startswith(("p_hk", "p_t3", "n_t3", "n_droid")) or "droid" in name:
        return SequenceTargetType.DROID
    if name.startswith(("p", "n_")) or supermodel.startswith(("s_", "p_", "c_", "n_")):
        return SequenceTargetType.CHARACTER
    return None


def infer_target_type(obj: object | None) -> SequenceTargetType:
    if obj is None:
        return SequenceTargetType.UNKNOWN
    object_type = str(getattr(obj, "object_type", "") or "").lower()
    if object_type == "camera":
        return SequenceTargetType.CAMERA
    if object_type == "light":
        return SequenceTargetType.LIGHT
    model_target = _classify_model_target(obj)
    if model_target is not None:
        return model_target
    if bool(getattr(obj, "is_camera", False)) or bool(getattr(obj, "_gr_camera_id", "")):
        return SequenceTargetType.CAMERA
    if bool(getattr(obj, "vertices", [])):
        return SequenceTargetType.MESH
    if bool(getattr(obj, "is_light", False)) or bool(getattr(obj, "_gr_light_id", "")):
        return SequenceTargetType.LIGHT
    if hasattr(obj, "light_multiplier") and not any(hasattr(obj, attr) for attr in ("vertices", "animations", "supermodel", "all_nodes")):
        return SequenceTargetType.LIGHT
    name = str(getattr(obj, "name", "") or "").lower()
    if any(token in name for token in ("rig", "skeleton", "bone", "pelvis", "spine")):
        return SequenceTargetType.RIG
    if bool(getattr(obj, "is_skin", False)) or bool(getattr(obj, "skin_data", [])):
        return SequenceTargetType.CHARACTER
    return SequenceTargetType.PROP if obj is not None else SequenceTargetType.UNKNOWN


class SequenceManager:
    def __init__(self, root: str | Path = "sequences") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.active_sequence: GhostRiggerLevelSequence | None = None
        self.recent_sequences: list[str] = []

    def new_sequence(self, name: str = "New Sequence", *, scene_module_name: str = "") -> GhostRiggerLevelSequence:
        sequence = GhostRiggerLevelSequence(name=name or "New Sequence", scene_module_name=scene_module_name)
        self.active_sequence = sequence
        return sequence

    def save(self, sequence: GhostRiggerLevelSequence | None = None, path: str | Path | None = None) -> Path:
        sequence = sequence or self.active_sequence
        if sequence is None:
            raise ValueError("No active sequence to save.")
        target = Path(path or sequence.asset_path or self.default_asset_path(sequence.name))
        output = save_sequence_file(sequence, target)
        self._remember(output)
        self.active_sequence = sequence
        return output

    def load(self, path: str | Path) -> GhostRiggerLevelSequence:
        sequence = load_sequence_file(path)
        self.active_sequence = sequence
        self._remember(Path(path))
        return sequence

    def duplicate(self, sequence: GhostRiggerLevelSequence, new_name: str | None = None) -> GhostRiggerLevelSequence:
        data = sequence.serialize()
        data["id"] = f"sequence-{uuid4().hex}"
        data["name"] = new_name or f"{sequence.name} Copy"
        data["asset_path"] = ""
        duplicate = GhostRiggerLevelSequence.deserialize(data)
        self.active_sequence = duplicate
        return duplicate

    def delete_asset(self, path: str | Path) -> None:
        source = Path(path)
        if source.exists() and source.suffix.lower() == SEQUENCE_EXTENSION:
            source.unlink()
        self.recent_sequences = [item for item in self.recent_sequences if Path(item) != source]

    def rename_asset(self, path: str | Path, new_name: str) -> Path:
        source = Path(path)
        target = source.with_name(self.safe_filename(new_name)).with_suffix(SEQUENCE_EXTENSION)
        source.rename(target)
        sequence = self.load(target)
        sequence.name = new_name
        self.save(sequence, target)
        return target

    def list_assets(self) -> list[SequenceAssetInfo]:
        infos: list[SequenceAssetInfo] = []
        for path in sorted(self.root.glob(f"*{SEQUENCE_EXTENSION}")):
            try:
                infos.append(inspect_sequence_asset(path))
            except Exception:
                continue
        return infos

    def default_asset_path(self, name: str) -> Path:
        return self.root / f"{self.safe_filename(name)}{SEQUENCE_EXTENSION}"

    def create_binding_for_object(self, obj: object, *, binding_type: SequenceBindingType = SequenceBindingType.POSSESSABLE) -> SequenceBinding:
        object_id = ensure_sequence_object_id(obj)
        display_name = str(getattr(obj, "name", "") or object_id or "Scene Object")
        target_type = infer_target_type(obj)
        return SequenceBinding(
            display_name=display_name,
            target_object_id=object_id,
            target_object_name=display_name,
            target_type=target_type,
            binding_type=binding_type,
            color={
                SequenceTargetType.CAMERA: "#3A96FF",
                SequenceTargetType.LIGHT: "#FFD400",
                SequenceTargetType.MESH: "#00D7B5",
                SequenceTargetType.CHARACTER: "#00FF7A",
                SequenceTargetType.CREATURE: "#7CFFB2",
                SequenceTargetType.DROID: "#65C8FF",
                SequenceTargetType.RIG: "#00FF7A",
            }.get(target_type, "#7A9A88"),
        )

    def add_object_binding(self, sequence: GhostRiggerLevelSequence, obj: object) -> SequenceBinding:
        object_id = ensure_sequence_object_id(obj)
        existing = next((binding for binding in sequence.bindings if binding.target_object_id == object_id), None)
        if existing is not None:
            existing.metadata["missing"] = False
            return existing
        return sequence.add_binding(self.create_binding_for_object(obj))

    def resolve_missing_bindings(self, sequence: GhostRiggerLevelSequence, objects: Iterable[object]) -> None:
        ids = {ensure_sequence_object_id(obj) for obj in objects if obj is not None}
        for binding in sequence.bindings:
            binding.metadata["missing"] = bool(binding.target_object_id and binding.target_object_id not in ids)

    def rebind(self, binding: SequenceBinding, obj: object) -> None:
        binding.target_object_id = ensure_sequence_object_id(obj)
        binding.target_object_name = str(getattr(obj, "name", "") or binding.target_object_id)
        binding.target_type = infer_target_type(obj)
        binding.metadata["missing"] = False

    def copy_asset_file(self, source: str | Path, target: str | Path) -> Path:
        src = Path(source)
        dst = Path(target).with_suffix(SEQUENCE_EXTENSION)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return dst

    def _remember(self, path: Path) -> None:
        value = str(path)
        self.recent_sequences = [item for item in self.recent_sequences if item != value]
        self.recent_sequences.insert(0, value)
        self.recent_sequences = self.recent_sequences[:12]

    @staticmethod
    def safe_filename(name: str) -> str:
        clean = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(name or "").strip())
        clean = clean.strip("._")
        return clean or "sequence"
