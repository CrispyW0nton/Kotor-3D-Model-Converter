"""FBX export through Autodesk Python FBX SDK."""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

from src.core.geometry.model_data import KotorModel, ModelNode
from src.core.scene.kmax_scene import KMaxScene

from .fbx_scene_adapter import (
    FbxExportSummary,
    gr_material_to_fbx_material,
    gr_mesh_to_fbx_mesh,
    iter_renderable_mesh_nodes,
    quat_xyzw_to_euler_degrees,
    sdk_class,
)
from .fbx_sdk_loader import get_fbx_modules, get_fbx_sdk_status

log = logging.getLogger(__name__)


class FbxExportError(RuntimeError):
    """Raised when FBX export fails."""


class FbxSdkUnavailableError(RuntimeError):
    """Raised when Autodesk FBX SDK bindings are unavailable."""


DEFAULT_EXPORT_OPTIONS: dict[str, Any] = {
    "export_selection_only": False,
    "export_ascii": False,
    "embed_media": False,
    "apply_unit_conversion": True,
    "bake_transforms": False,
    "triangulate": True,
}


def export_fbx(scene_or_selection: Any, path: str, options: dict[str, Any] | None = None) -> bool:
    """Export a GhostRigger model/scene/selection to FBX using Autodesk SDK."""
    opts = {**DEFAULT_EXPORT_OPTIONS, **(options or {})}
    target = _validate_output_path(path)
    modules = get_fbx_modules()
    if modules.fbx is None:
        raise FbxSdkUnavailableError(get_fbx_sdk_status())
    fbx = modules.fbx
    manager = None
    exporter = None
    try:
        manager, scene = _create_sdk_scene(fbx, modules.FbxCommon, target.stem or "GhostRiggerScene")
        _configure_scene(fbx, manager, scene, opts)
        summary = FbxExportSummary()
        _add_payload_to_scene(fbx, manager, scene, scene_or_selection, opts, summary)
        exporter_cls = sdk_class(fbx, "FbxExporter", "KFbxExporter")
        exporter = exporter_cls.Create(manager, "")
        file_format = _choose_writer_format(manager, opts)
        if not exporter.Initialize(str(target), file_format, manager.GetIOSettings()):
            raise FbxExportError(_sdk_error(exporter, f"Could not initialize FBX exporter for {target}"))
        if not exporter.Export(scene):
            raise FbxExportError(_sdk_error(exporter, f"Could not export FBX scene to {target}"))
        log.info("FBX export summary for %s: %s", target.name, summary.log_line())
        return True
    except FbxSdkUnavailableError:
        raise
    except FbxExportError:
        raise
    except Exception as exc:
        raise FbxExportError(f"FBX export failed for {target}: {exc}") from exc
    finally:
        if exporter is not None:
            _destroy(exporter)
        if manager is not None:
            _destroy(manager)


def _validate_output_path(path: str) -> Path:
    target = Path(path)
    if target.suffix.lower() != ".fbx":
        target = target.with_suffix(".fbx")
    if target.parent:
        target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _create_sdk_scene(fbx: Any, common: Any, name: str):
    if common is not None and hasattr(common, "InitializeSdkObjects"):
        manager, scene = common.InitializeSdkObjects()
        scene.SetName(name)
        return manager, scene
    manager_cls = sdk_class(fbx, "FbxManager", "KFbxSdkManager")
    scene_cls = sdk_class(fbx, "FbxScene", "KFbxScene")
    ios_cls = sdk_class(fbx, "FbxIOSettings", "KFbxIOSettings")
    manager = manager_cls.Create()
    if ios_cls is not None and hasattr(fbx, "IOSROOT"):
        manager.SetIOSettings(ios_cls.Create(manager, fbx.IOSROOT))
    return manager, scene_cls.Create(manager, name)


def _configure_scene(fbx: Any, manager: Any, scene: Any, options: dict[str, Any]) -> None:
    info_cls = sdk_class(fbx, "FbxDocumentInfo", "KFbxDocumentInfo")
    if info_cls is not None:
        info = info_cls.Create(manager, "GhostRiggerExportInfo")
        info.mTitle = scene.GetName()
        info.mSubject = "GhostRigger FBX export"
        scene.SetSceneInfo(info)
    try:
        axis_cls = sdk_class(fbx, "FbxAxisSystem", "KFbxAxisSystem")
        axis = axis_cls(axis_cls.eZAxis, axis_cls.eParityOdd, axis_cls.eRightHanded)
        scene.GetGlobalSettings().SetAxisSystem(axis)
    except Exception:
        log.debug("Could not set FBX axis system", exc_info=True)
    try:
        units_cls = sdk_class(fbx, "FbxSystemUnit", "KFbxSystemUnit")
        scene.GetGlobalSettings().SetSystemUnit(units_cls.cm)
    except Exception:
        log.debug("Could not set FBX system unit", exc_info=True)
    _set_io_bool(fbx, manager, "EXP_FBX_MATERIAL", True)
    _set_io_bool(fbx, manager, "EXP_FBX_TEXTURE", True)
    _set_io_bool(fbx, manager, "EXP_FBX_EMBEDDED", bool(options.get("embed_media")))


def _add_payload_to_scene(fbx: Any, manager: Any, scene: Any, payload: Any, options: dict[str, Any], summary: FbxExportSummary) -> None:
    root = scene.GetRootNode()
    for model, prefix in _models_from_payload(payload, options):
        parent = _new_node(fbx, manager, prefix or getattr(model, "name", "Model"))
        root.AddChild(parent)
        for node in iter_renderable_mesh_nodes(model):
            fbx_node = _create_mesh_node(fbx, manager, node, options, summary)
            parent.AddChild(fbx_node)
        if getattr(model, "animations", None):
            warning = "Phase 2 TODO: animation export is not implemented in Autodesk SDK bridge."
            summary.warnings.append(warning)
            log.warning(warning)


def _models_from_payload(payload: Any, options: dict[str, Any]) -> list[tuple[KotorModel, str]]:
    if isinstance(payload, KotorModel):
        return [(payload, payload.name)]
    if isinstance(payload, KMaxScene):
        objects = list(payload.objects)
        if options.get("export_selection_only"):
            objects = [obj for obj in objects if getattr(obj, "selected", False)]
        result = []
        for obj in objects:
            model = (getattr(obj, "metadata", {}) or {}).get("_runtime_model")
            if isinstance(model, KotorModel):
                transformed = _copy_model_with_instance_transform(model, obj)
                result.append((transformed, getattr(obj, "name", model.name)))
        if not result:
            raise FbxExportError("Scene export has no runtime mesh objects to export.")
        return result
    if isinstance(payload, (list, tuple)):
        result = []
        for item in payload:
            if isinstance(item, KotorModel):
                result.append((item, item.name))
            else:
                model = (getattr(item, "metadata", {}) or {}).get("_runtime_model")
                if isinstance(model, KotorModel):
                    result.append((_copy_model_with_instance_transform(model, item), getattr(item, "name", model.name)))
        if result:
            return result
    raise FbxExportError("FBX export expects a KotorModel, KMaxScene, or selected scene objects with runtime models.")


def _copy_model_with_instance_transform(model: KotorModel, instance: Any) -> KotorModel:
    clone = copy.deepcopy(model)
    transform = getattr(instance, "transform", None)
    if clone.root_node is not None and transform is not None:
        clone.root_node.position = tuple(float(v) for v in getattr(transform, "position", (0.0, 0.0, 0.0))[:3])
        # KMAX stores Euler degrees, while KotorModel nodes use quaternions. Keep
        # scale as Phase 2 unless bake_transforms becomes necessary for KMAX.
    return clone


def _create_mesh_node(fbx: Any, manager: Any, node: ModelNode, options: dict[str, Any], summary: FbxExportSummary) -> Any:
    fbx_node = _new_node(fbx, manager, node.name)
    fbx_mesh = gr_mesh_to_fbx_mesh(fbx, manager, node, triangulate=bool(options.get("triangulate", True)))
    fbx_node.SetNodeAttribute(fbx_mesh)
    _set_node_transform(fbx, fbx_node, node)
    material = gr_material_to_fbx_material(fbx, manager, node)
    if material is not None:
        fbx_node.AddMaterial(material)
        summary.materials += 1
        if node.texture:
            summary.textures += 1
    summary.meshes += 1
    summary.vertices += len(node.vertices)
    summary.faces += len(node.faces)
    return fbx_node


def _new_node(fbx: Any, manager: Any, name: str) -> Any:
    node_cls = sdk_class(fbx, "FbxNode", "KFbxNode")
    return node_cls.Create(manager, str(name or "Node")[:64])


def _set_node_transform(fbx: Any, fbx_node: Any, node: ModelNode) -> None:
    double3_cls = sdk_class(fbx, "FbxDouble3", "KFbxDouble3")
    try:
        fbx_node.LclTranslation.Set(double3_cls(*tuple(float(v) for v in node.position[:3])))
    except Exception:
        pass
    try:
        fbx_node.LclRotation.Set(double3_cls(*quat_xyzw_to_euler_degrees(node.rotation)))
    except Exception:
        pass


def _choose_writer_format(manager: Any, options: dict[str, Any]) -> int:
    if not options.get("export_ascii"):
        return -1
    try:
        registry = manager.GetIOPluginRegistry()
        count = registry.GetWriterFormatCount()
        for index in range(count):
            desc = str(registry.GetWriterFormatDescription(index)).lower()
            if "fbx ascii" in desc:
                return index
    except Exception:
        pass
    return -1


def _set_io_bool(fbx: Any, manager: Any, prop_name: str, value: bool) -> None:
    try:
        ios = manager.GetIOSettings()
        prop = getattr(fbx, prop_name, prop_name)
        ios.SetBoolProp(prop, bool(value))
    except Exception:
        pass


def _sdk_error(sdk_object: Any, fallback: str) -> str:
    try:
        status = sdk_object.GetStatus()
        error = status.GetErrorString()
        return f"{fallback}: {error}" if error else fallback
    except Exception:
        return fallback


def _destroy(obj: Any) -> None:
    destroy = getattr(obj, "Destroy", None)
    if callable(destroy):
        destroy()

