"""Stable command service shared by Mesh Tools UI and IPC."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from importlib import util
from pathlib import Path
import sys
from typing import Any

from .mesh_edit_types import MeshOperationResult, MeshSelectionMode
from .mesh_editing import bevel_selected, boolean_cut_selected, boolean_difference_selected, boolean_union_selected, extrude_selected, inset_selected
from .mesh_primitives import PrimitiveMeshData, build_primitive_mesh
from .mesh_selection_state import MeshSelectionState
from .mesh_validation import validate_mesh


CREATE_COMMANDS = {
    "create_floor": "floor",
    "create_wall": "wall",
    "create_cube": "cube",
    "create_cylinder": "cylinder",
    "create_arch": "arch",
    "create_ramp": "ramp",
    "create_stairs": "stairs",
}


@dataclass(slots=True)
class MeshToolResponse:
    status: str
    command: str
    message: str = ""
    result: dict[str, Any] = field(default_factory=dict)
    changed_object_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def execute_mesh_tool_command(context: Any, payload: dict[str, Any] | None) -> dict[str, Any]:
    """Execute one mesh tool command against a main-window or viewport context."""

    data = dict(payload or {})
    command = _normalise_command(data.get("command", data.get("cmd", "")))
    options = data.get("options") if isinstance(data.get("options"), dict) else {}
    if command in CREATE_COMMANDS:
        return _create_primitive(context, command, {**dict(options), **_target_options(data)})
    if command in {"extrude", "bevel", "inset", "boolean_cut", "boolean_union", "boolean_difference"}:
        return _viewport_operation(context, data, command, options)
    if command == "snap_to_grid":
        return _snap_to_grid(context, data, options).to_dict()
    if command == "set_grid":
        return _set_grid(context, options).to_dict()
    if command == "set_transform":
        return _set_transform(context, data, options).to_dict()
    if command == "set_pivot":
        return _set_pivot(context, data, options).to_dict()
    if command == "assign_material":
        return _assign_material(context, data, options).to_dict()
    if command == "validate_mesh":
        return _validate_active_mesh(context, data, command).to_dict()
    return MeshToolResponse("error", command or "", f"Unknown mesh tool command: {command}", errors=[f"Unknown mesh tool command: {command}"]).to_dict()


def _normalise_command(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def _target_options(data: dict[str, Any]) -> dict[str, Any]:
    target = data.get("target")
    return target if isinstance(target, dict) else {}


def _viewport(context: Any):
    return getattr(context, "viewport", context)


def _scene_manager(context: Any):
    return getattr(context, "scene_manager", None)


def _create_primitive(context: Any, command: str, options: dict[str, Any]) -> dict[str, Any]:
    mesh = build_primitive_mesh(CREATE_COMMANDS[command], options)
    viewport = _viewport(context)
    scene_manager = _scene_manager(context)
    if scene_manager is None:
        return MeshToolResponse("error", command, "Mesh primitive creation requires a scene manager.", errors=["scene_manager unavailable"]).to_dict()
    model = _runtime_model_from_mesh(mesh, str(options.get("game") or getattr(context, "_current_game", "") or "K1"))
    transform = {
        "position": _vec3(options.get("position"), (0.0, 0.0, 0.0), snap=bool(options.get("grid_snap", False)), grid=float(options.get("grid_size", 1.0) or 1.0), axes=tuple(options.get("snap_axes", ("x", "y", "z")))),
        "rotation": _vec3(options.get("rotation"), (0.0, 0.0, 0.0)),
        "scale": _vec3(options.get("scale"), (1.0, 1.0, 1.0)),
    }
    ref = _scene_resource_ref(mesh, command, options)
    instance = scene_manager.add_model_instance(ref, transform, name=mesh.name, runtime_model=model, select=True)
    _apply_pivot_preset(instance, str(options.get("pivot_preset") or "center"), mesh, options)
    instance.material_overrides["slot_0"] = {"material": mesh.material, "texture": mesh.material}
    instance.metadata["mesh_tool"] = {"command": command, "primitive": mesh.primitive, "mesh": mesh.metadata}
    if hasattr(scene_manager, "mark_dirty"):
        scene_manager.mark_dirty()
    appended = False
    if viewport is not None:
        append = getattr(viewport, "append_scene_instance", None)
        if callable(append):
            appended = bool(append(instance, scene_name=getattr(scene_manager.active_scene, "display_name", "Untitled Scene")))
        if not appended and hasattr(viewport, "load_scene_instances"):
            viewport.load_scene_instances(scene_manager.get_scene_objects(), scene_name=getattr(scene_manager.active_scene, "display_name", "Untitled Scene"))
        if hasattr(viewport, "set_mesh_selection_mode"):
            viewport.set_mesh_selection_mode("object")
    _refresh_panels(context, model)
    return MeshToolResponse(
        "ok",
        command,
        f"Created {mesh.primitive} primitive.",
        result={"object_id": instance.id, "name": instance.name, "vertex_count": len(mesh.vertices), "face_count": len(mesh.faces)},
        changed_object_ids=[instance.id],
        warnings=list(mesh.warnings),
        validation_summary=_validation_dict(validate_mesh(model.root_node.children[0])),
    ).to_dict()


def _runtime_model_from_mesh(mesh: PrimitiveMeshData, game: str):
    md = _import_model_data()
    GameVersion, KotorModel, ModelClassification, ModelNode, NodeFlags = (
        md.GameVersion,
        md.KotorModel,
        md.ModelClassification,
        md.ModelNode,
        md.NodeFlags,
    )

    root = ModelNode(name=f"{mesh.name}_root", flags=int(NodeFlags.HEADER))
    node = ModelNode(
        name=mesh.name,
        flags=int(NodeFlags.HEADER | NodeFlags.MESH),
        vertices=list(mesh.vertices),
        normals=list(mesh.normals),
        uvs=list(mesh.uvs),
        faces=list(mesh.faces),
        face_mats=list(mesh.face_mats),
        texture=str(mesh.material or ""),
        texture_names=[str(mesh.material or "")],
        tex_count=1,
        render=True,
    )
    node.parent = root
    root.children.append(node)
    node.compute_bounds()
    model = KotorModel(
        name=mesh.name,
        supermodel="NULL",
        classification="area",
        game_version=GameVersion.K2 if str(game).upper() == "K2" else GameVersion.K1,
        model_type=int(ModelClassification.EFFECT),
        root_node=root,
    )
    model.compute_bounds()
    setattr(model, "_gr_mesh_tool_generated", True)
    return model


def _scene_resource_ref(mesh: PrimitiveMeshData, command: str, options: dict[str, Any]):
    try:
        from src.core.scene.scene_resource_ref import SceneResourceRef
    except Exception:
        SceneResourceRef = _import_scene_resource_ref()

    return SceneResourceRef(
        resource_type="generated_mesh",
        game=str(options.get("game") or "K1").upper(),
        resref=str(options.get("resref") or mesh.name).lower()[:16],
        original_name=mesh.name,
        metadata={"source": "mesh_tools", "command": command, "primitive": mesh.primitive},
    )


def _repo_root() -> Path:
    return next((parent for parent in Path(__file__).resolve().parents if (parent / "native").exists()), Path(__file__).resolve().parents[2])


def _load_module(name: str, path: Path):
    spec = util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(str(path))
    module = util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _import_model_data():
    try:
        from src.core.geometry import model_data as md

        return md
    except Exception:
        return _load_module(
            "src.core.geometry.model_data",
            _repo_root() / "native" / "GhostRigger.Core.Math" / "Python" / "src" / "core" / "geometry" / "model_data.py",
        )


def _import_scene_resource_ref():
    try:
        module = _load_module(
            "src.core.scene.scene_resource_ref",
            _repo_root() / "native" / "GhostRigger.Core.Scene" / "Python" / "src" / "core" / "scene" / "scene_resource_ref.py",
        )
        return module.SceneResourceRef
    except Exception:
        @dataclass
        class SceneResourceRef:  # type: ignore[no-redef]
            resource_type: str = "model"
            game: str = "K1"
            resref: str = ""
            source_path: str = ""
            source_module: str = ""
            source_archive: str = ""
            original_name: str = ""
            metadata: dict[str, Any] = field(default_factory=dict)

        return SceneResourceRef


def _viewport_operation(context: Any, data: dict[str, Any], command: str, options: dict[str, Any]) -> dict[str, Any]:
    viewport = _viewport(context)
    if viewport is not None and hasattr(viewport, "mesh_tool_operation"):
        result = viewport.mesh_tool_operation(command, dict(options or {}))
        if getattr(result, "success", False):
            return _operation_response(command, result).to_dict()
        if "No active mesh selected." not in getattr(result, "errors", []):
            return _operation_response(command, result).to_dict()
    return _scene_mesh_operation(context, data, command, options).to_dict()


def _scene_mesh_operation(context: Any, data: dict[str, Any], command: str, options: dict[str, Any]) -> MeshToolResponse:
    scene_manager = _scene_manager(context)
    obj = _target_object(scene_manager, data)
    mesh = _mesh_node_for_object(obj)
    if obj is None or mesh is None:
        return MeshToolResponse("error", command, "No editable scene mesh target found.", errors=["target mesh missing"])
    selection = _selection_state(data)
    if command == "boolean_union":
        result = _scene_boolean_union(scene_manager, obj, mesh)
        response = _operation_response(command, result)
        response.changed_object_ids = [obj.id] if result.success else []
        response.validation_summary = _validation_dict(validate_mesh(mesh))
        return response
    operations = {
        "extrude": lambda: extrude_selected(mesh, selection, distance=float(options.get("distance", options.get("amount", 0.25)) or 0.25)),
        "bevel": lambda: bevel_selected(mesh, selection, amount=float(options.get("amount", 0.1) or 0.1), segments=int(options.get("segments", 1) or 1)),
        "inset": lambda: inset_selected(mesh, selection, amount=float(options.get("amount", 0.1) or 0.1)),
        "boolean_cut": lambda: boolean_cut_selected(mesh, selection),
        "boolean_difference": lambda: boolean_difference_selected(mesh, selection),
    }
    result = operations[command]()
    if result.success:
        try:
            mesh.compute_bounds()
            runtime = (obj.metadata or {}).get("_runtime_model")
            if runtime is not None:
                runtime.compute_bounds()
        except Exception:
            pass
        if scene_manager is not None and hasattr(scene_manager, "mark_dirty"):
            scene_manager.mark_dirty()
        _refresh_scene(context, f"mesh {command}")
        _refresh_panels(context, (obj.metadata or {}).get("_runtime_model"))
    response = _operation_response(command, result)
    response.changed_object_ids = [obj.id] if result.success else []
    response.validation_summary = _validation_dict(validate_mesh(mesh))
    if result.success and "Viewport edit history was unavailable; scene mesh was edited through the Mesh Tools command service." not in response.warnings:
        response.warnings.append("Viewport edit history was unavailable; scene mesh was edited through the Mesh Tools command service.")
    return response


def _scene_boolean_union(scene_manager: Any, target_obj: Any, target_mesh: Any) -> MeshOperationResult:
    selected = list(scene_manager.get_selected_objects() if scene_manager is not None else [])
    meshes = [_mesh_node_for_object(obj) for obj in selected]
    meshes = [mesh for mesh in meshes if mesh is not None]
    result, combined = boolean_union_selected(meshes)
    if not result.success or combined is None:
        return result
    for attr in ("vertices", "normals", "uvs", "faces", "face_mats"):
        if hasattr(combined, attr):
            setattr(target_mesh, attr, list(getattr(combined, attr)))
    try:
        target_mesh.compute_bounds()
        runtime = (target_obj.metadata or {}).get("_runtime_model")
        if runtime is not None:
            runtime.compute_bounds()
    except Exception:
        pass
    if scene_manager is not None and hasattr(scene_manager, "mark_dirty"):
        scene_manager.mark_dirty()
    result.warnings.append("Scene-object fallback union merged geometry into the target object and preserved source objects.")
    return result


def _snap_to_grid(context: Any, data: dict[str, Any], options: dict[str, Any]) -> MeshToolResponse:
    grid = float(options.get("grid_size", getattr(context, "_mesh_tool_grid_size", 1.0)) or 1.0)
    axes = tuple(str(axis).lower() for axis in options.get("axes", options.get("snap_axes", ("x", "y", "z"))))
    scene_manager = _scene_manager(context)
    target = _target_object(scene_manager, data)
    selected = [target] if target is not None and data.get("target") else list(scene_manager.get_selected_objects() if scene_manager is not None else [])
    changed = []
    for obj in selected:
        pos = _snap_vec3(tuple(getattr(obj.transform, "position", (0.0, 0.0, 0.0))), grid, axes)
        if scene_manager.update_object_transform(obj.id, position=pos):
            changed.append(obj.id)
    _refresh_scene(context, "mesh grid snap")
    return MeshToolResponse("ok", "snap_to_grid", f"Snapped {len(changed)} object(s) to grid.", changed_object_ids=changed)


def _set_grid(context: Any, options: dict[str, Any]) -> MeshToolResponse:
    setattr(context, "_mesh_tool_grid_enabled", bool(options.get("enabled", True)))
    setattr(context, "_mesh_tool_grid_size", float(options.get("grid_size", 1.0) or 1.0))
    setattr(context, "_mesh_tool_snap_axes", tuple(options.get("axes", options.get("snap_axes", ("x", "y", "z")))))
    return MeshToolResponse("ok", "set_grid", "Updated Mesh Tools grid settings.", result={"enabled": getattr(context, "_mesh_tool_grid_enabled"), "grid_size": getattr(context, "_mesh_tool_grid_size"), "axes": list(getattr(context, "_mesh_tool_snap_axes"))})


def _set_transform(context: Any, data: dict[str, Any], options: dict[str, Any]) -> MeshToolResponse:
    scene_manager = _scene_manager(context)
    obj = _target_object(scene_manager, data)
    if obj is None:
        return MeshToolResponse("error", "set_transform", "No scene object target found.", errors=["target missing"])
    changed = scene_manager.update_object_transform(obj.id, position=_optional_vec3(options.get("position")), rotation=_optional_vec3(options.get("rotation")), scale=_optional_vec3(options.get("scale")))
    _refresh_scene(context, "mesh transform command")
    return MeshToolResponse("ok" if changed else "error", "set_transform", "Updated transform." if changed else "Transform update failed.", changed_object_ids=[obj.id] if changed else [])


def _set_pivot(context: Any, data: dict[str, Any], options: dict[str, Any]) -> MeshToolResponse:
    scene_manager = _scene_manager(context)
    obj = _target_object(scene_manager, data)
    if obj is None:
        return MeshToolResponse("error", "set_pivot", "No scene object target found.", errors=["target missing"])
    preset = str(options.get("preset") or options.get("pivot_preset") or "").strip().lower()
    if preset:
        runtime = (obj.metadata or {}).get("_runtime_model")
        mesh = None
        try:
            mesh = next((n for n in runtime.all_nodes() if getattr(n, "is_mesh", False)), None)
        except Exception:
            mesh = None
        _apply_pivot_preset(obj, preset, mesh, options)
        changed = True
    else:
        changed = scene_manager.update_object_pivot(obj.id, position_local=_optional_vec3(options.get("position", options.get("position_local"))), rotation_local=_optional_vec3(options.get("rotation", options.get("rotation_local"))), enabled=options.get("enabled", True))
    _refresh_scene(context, "mesh pivot command")
    return MeshToolResponse("ok" if changed else "error", "set_pivot", "Updated pivot." if changed else "Pivot update failed.", changed_object_ids=[obj.id] if changed else [])


def _assign_material(context: Any, data: dict[str, Any], options: dict[str, Any]) -> MeshToolResponse:
    scene_manager = _scene_manager(context)
    obj = _target_object(scene_manager, data)
    material = str(options.get("material") or options.get("texture") or data.get("material") or "").strip()
    if obj is None:
        return MeshToolResponse("error", "assign_material", "No scene object target found.", errors=["target missing"])
    if not material:
        return MeshToolResponse("error", "assign_material", "No material or texture was supplied.", errors=["material missing"])
    slot = int(options.get("slot", options.get("material_slot", 0)) or 0)
    obj.material_overrides[f"slot_{slot}"] = {"material": material, "texture": material, "source": "mesh_tools"}
    runtime = (obj.metadata or {}).get("_runtime_model")
    nodes = []
    try:
        nodes = [n for n in runtime.all_nodes() if getattr(n, "is_mesh", False)]
    except Exception:
        nodes = []
    for node in nodes:
        node.texture = material
        node.texture_names = [material]
        node.tex_count = 1
    if scene_manager is not None:
        scene_manager.mark_dirty()
    _refresh_scene(context, "mesh material assignment")
    _refresh_panels(context, runtime)
    return MeshToolResponse("ok", "assign_material", f"Assigned material '{material}'.", changed_object_ids=[obj.id], result={"slot": slot, "material": material, "material_slot_count": 1})


def _validate_active_mesh(context: Any, data: dict[str, Any], command: str) -> MeshToolResponse:
    viewport = _viewport(context)
    mesh = viewport._active_edit_mesh() if viewport is not None and hasattr(viewport, "_active_edit_mesh") else None
    if mesh is None:
        mesh = _mesh_node_for_object(_target_object(_scene_manager(context), data))
    if mesh is None:
        return MeshToolResponse("error", command, "No active mesh selected.", errors=["active mesh missing"])
    summary = _validation_dict(validate_mesh(mesh))
    return MeshToolResponse("ok" if not summary["errors"] else "error", command, "Mesh validation complete.", validation_summary=summary)


def _selection_state(data: dict[str, Any]) -> MeshSelectionState:
    selection = data.get("selection") if isinstance(data.get("selection"), dict) else {}
    ids = {int(value) for value in selection.get("ids", []) if str(value).lstrip("-").isdigit()}
    mode = str(selection.get("mode") or "face").strip().lower()
    if mode == "vertex":
        return MeshSelectionState(mode=MeshSelectionMode.VERTEX, selected_vertices=ids)
    if mode == "edge":
        edges = {tuple(edge) for edge in selection.get("edges", []) if isinstance(edge, (list, tuple)) and len(edge) == 2}
        return MeshSelectionState(mode=MeshSelectionMode.EDGE, selected_edges=edges)
    return MeshSelectionState(mode=MeshSelectionMode.FACE, selected_faces=ids)


def _operation_response(command: str, result: MeshOperationResult) -> MeshToolResponse:
    return MeshToolResponse(
        "ok" if result.success else "error",
        command,
        result.message,
        changed_object_ids=list(result.changed_mesh_ids),
        warnings=list(result.warnings),
        errors=list(result.errors),
    )


def _validation_dict(report: Any) -> dict[str, Any]:
    errors = []
    warnings = []
    if getattr(report, "non_manifold_edges", None):
        errors.append(f"{len(report.non_manifold_edges)} nonmanifold edge(s)")
    if getattr(report, "degenerate_faces", None):
        errors.append(f"{len(report.degenerate_faces)} degenerate face(s)")
    for key, label in (("border_edges", "border edge(s)"), ("isolated_vertices", "isolated vertex/vertices"), ("duplicate_vertices", "duplicate vertex/vertices"), ("inverted_faces", "inverted face(s)")):
        values = getattr(report, key, None) or []
        if values:
            warnings.append(f"{len(values)} {label}")
    warnings.extend(str(note) for note in getattr(report, "notes", []) or [])
    return {"errors": errors, "warnings": warnings, "has_errors": bool(errors), "has_warnings": bool(warnings)}


def _target_object(scene_manager: Any, data: dict[str, Any]):
    if scene_manager is None:
        return None
    target = data.get("target") if isinstance(data.get("target"), dict) else {}
    object_id = str(target.get("id") or target.get("object_id") or data.get("id") or data.get("object_id") or "").strip()
    name = str(target.get("name") or data.get("name") or "").strip()
    objects = scene_manager.get_scene_objects()
    if object_id:
        return next((obj for obj in objects if obj.id == object_id), None)
    if name:
        return next((obj for obj in objects if obj.name == name), None)
    selected = list(scene_manager.get_selected_objects() or [])
    return selected[-1] if selected else None


def _mesh_node_for_object(obj: Any):
    if obj is None:
        return None
    runtime = (getattr(obj, "metadata", {}) or {}).get("_runtime_model")
    try:
        return next((node for node in runtime.all_nodes() if getattr(node, "is_mesh", False)), None)
    except Exception:
        return None


def _apply_pivot_preset(instance: Any, preset: str, mesh: Any, options: dict[str, Any]) -> None:
    preset = preset.strip().lower().replace(" ", "_")
    if preset == "custom":
        instance.pivot.position_local = _vec3(options.get("pivot", options.get("pivot_position")), (0.0, 0.0, 0.0))
    elif preset == "base":
        bb_min = getattr(mesh, "bb_min", (0.0, 0.0, 0.0))
        instance.pivot.position_local = (0.0, 0.0, float(bb_min[2]))
    elif preset in {"origin", "world_origin"}:
        instance.pivot.position_local = (0.0, 0.0, 0.0)
    elif preset in {"selected_element", "selected_face", "selected_vertex"}:
        instance.pivot.position_local = (0.0, 0.0, 0.0)
        instance.pivot.metadata["warning"] = f"{preset} pivot needs an active subobject selection; used origin."
    else:
        instance.pivot.position_local = (0.0, 0.0, 0.0)
    instance.pivot.enabled = True


def _vec3(value: Any, default: tuple[float, float, float], *, snap: bool = False, grid: float = 1.0, axes: tuple[str, ...] = ("x", "y", "z")) -> tuple[float, float, float]:
    parsed = _optional_vec3(value) or default
    return _snap_vec3(parsed, grid, axes) if snap else parsed


def _optional_vec3(value: Any) -> tuple[float, float, float] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        raw = (value.get("x", 0.0), value.get("y", 0.0), value.get("z", 0.0))
    else:
        raw = value
    try:
        seq = list(raw)
        return (float(seq[0]), float(seq[1]), float(seq[2]))
    except Exception:
        return None


def _snap_vec3(value: tuple[float, float, float], grid: float, axes: tuple[str, ...]) -> tuple[float, float, float]:
    grid = max(1.0e-6, float(grid or 1.0))
    enabled = {str(axis).lower() for axis in axes}
    return tuple(round(v / grid) * grid if axis in enabled else v for v, axis in zip(value, ("x", "y", "z")))  # type: ignore[return-value]


def _refresh_scene(context: Any, reason: str) -> None:
    viewport = _viewport(context)
    if viewport is not None:
        refresh = getattr(viewport, "refresh_scene_transforms", None) or getattr(viewport, "refresh_view", None)
        if callable(refresh):
            try:
                refresh(reason=reason)
            except TypeError:
                refresh()
    update_chrome = getattr(context, "_update_scene_chrome", None)
    if callable(update_chrome):
        update_chrome()


def _refresh_panels(context: Any, model: Any) -> None:
    for name, method in (("scene_outliner_panel", "set_scene"), ("module_geometry_panel", "show_model"), ("sprite_materials_panel", "set_model")):
        panel = getattr(context, name, None)
        callback = getattr(panel, method, None)
        if not callable(callback):
            continue
        try:
            callback(getattr(context.scene_manager, "active_scene", None) if method == "set_scene" else model)
        except Exception:
            pass
