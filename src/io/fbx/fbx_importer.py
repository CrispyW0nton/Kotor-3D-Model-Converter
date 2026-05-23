"""FBX import through Autodesk Python FBX SDK."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.core.geometry.model_data import GameVersion, KotorModel, ModelNode, NodeFlags

from .fbx_scene_adapter import FbxImportSummary, euler_degrees_to_quat_xyz, fbx_mesh_to_gr_mesh, sdk_class
from .fbx_sdk_loader import get_fbx_modules, get_fbx_sdk_status

log = logging.getLogger(__name__)


class FbxSdkUnavailableError(RuntimeError):
    """Raised when Autodesk FBX SDK bindings are not available."""


class FbxImportError(RuntimeError):
    """Raised when an FBX file cannot be imported."""


def import_fbx(path: str, options: dict[str, Any] | None = None) -> KotorModel:
    """Import an FBX file into a GhostRigger ``KotorModel``.

    Phase 1 imports static mesh hierarchy, local transforms, materials, diffuse
    texture references, normals, UVs, and material slots. Phase 2 areas such as
    skeleton skinning and animation are detected but intentionally not consumed
    until GhostRigger has a clean architecture path for them.
    """
    source = _validate_fbx_path(path)
    modules = get_fbx_modules()
    if modules.fbx is None:
        raise FbxSdkUnavailableError(get_fbx_sdk_status())
    fbx = modules.fbx
    manager = None
    importer = None
    try:
        manager, scene = _create_sdk_scene(fbx, modules.FbxCommon, source.stem[:32] or "fbx_scene")
        importer_cls = sdk_class(fbx, "FbxImporter", "KFbxImporter")
        importer = importer_cls.Create(manager, "")
        if not importer.Initialize(str(source), -1, manager.GetIOSettings()):
            raise FbxImportError(_sdk_error(importer, f"Could not initialize FBX importer for {source}"))
        if not importer.Import(scene):
            raise FbxImportError(_sdk_error(importer, f"Could not import FBX scene {source}"))

        _triangulate_scene_if_possible(fbx, manager, scene)
        model, summary = _scene_to_model(fbx, scene, source, options or {})
        model.metadata = getattr(model, "metadata", {})
        setattr(model, "fbx_import_summary", summary)
        log.info("FBX import summary for %s: %s", source.name, summary.log_line())
        return model
    except FbxSdkUnavailableError:
        raise
    except FbxImportError:
        raise
    except Exception as exc:
        raise FbxImportError(f"FBX import failed for {source}: {exc}") from exc
    finally:
        if importer is not None:
            _destroy(importer)
        if manager is not None:
            _destroy(manager)


def _validate_fbx_path(path: str) -> Path:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(str(source))
    if source.suffix.lower() != ".fbx":
        raise ValueError(f"FBX import expects a .fbx file, got: {source}")
    return source


def _create_sdk_scene(fbx: Any, common: Any, name: str):
    if common is not None and hasattr(common, "InitializeSdkObjects"):
        manager, scene = common.InitializeSdkObjects()
        return manager, scene
    manager_cls = sdk_class(fbx, "FbxManager", "KFbxSdkManager")
    scene_cls = sdk_class(fbx, "FbxScene", "KFbxScene")
    ios_cls = sdk_class(fbx, "FbxIOSettings", "KFbxIOSettings")
    manager = manager_cls.Create()
    if ios_cls is not None and hasattr(fbx, "IOSROOT"):
        manager.SetIOSettings(ios_cls.Create(manager, fbx.IOSROOT))
    scene = scene_cls.Create(manager, name)
    return manager, scene


def _triangulate_scene_if_possible(fbx: Any, manager: Any, scene: Any) -> None:
    geometry_converter_cls = sdk_class(fbx, "FbxGeometryConverter", "KFbxGeometryConverter")
    if geometry_converter_cls is None:
        return
    try:
        converter = geometry_converter_cls(manager)
        converter.Triangulate(scene, True)
    except Exception:
        log.debug("FBX triangulation pass skipped", exc_info=True)


def _scene_to_model(fbx: Any, scene: Any, source: Path, options: dict[str, Any]) -> tuple[KotorModel, FbxImportSummary]:
    game_version = options.get("game_version", GameVersion.K1)
    if isinstance(game_version, str):
        game_version = GameVersion.K2 if game_version.upper() == "K2" else GameVersion.K1
    model = KotorModel(
        name=(options.get("model_name") or source.stem or "fbx_scene")[:32],
        supermodel="NULL",
        game_version=game_version,
        classification=str(options.get("classification") or "character"),
    )
    model.mdl_path = str(source)
    root = ModelNode(name=model.name, flags=int(NodeFlags.HEADER))
    model.root_node = root
    summary = FbxImportSummary()
    root_fbx = scene.GetRootNode()
    if root_fbx is not None:
        for index in range(root_fbx.GetChildCount()):
            child = root_fbx.GetChild(index)
            converted = _convert_node_recursive(fbx, child, summary)
            if converted is not None:
                converted.parent = root
                root.children.append(converted)
    summary.bones = _count_skeleton_nodes(fbx, root_fbx)
    model.compute_bounds()
    return model, summary


def _convert_node_recursive(fbx: Any, fbx_node: Any, summary: FbxImportSummary) -> ModelNode | None:
    attr = fbx_node.GetNodeAttribute()
    gr_node: ModelNode | None = None
    if _is_mesh_attribute(fbx, attr):
        gr_node = fbx_mesh_to_gr_mesh(fbx, fbx_node, attr, summary)
    else:
        gr_node = ModelNode(name=_safe_node_name(fbx_node), flags=int(NodeFlags.HEADER))
        _apply_local_transform(fbx_node, gr_node)
    for index in range(fbx_node.GetChildCount()):
        child = _convert_node_recursive(fbx, fbx_node.GetChild(index), summary)
        if child is not None:
            child.parent = gr_node
            gr_node.children.append(child)
    if gr_node is not None and not gr_node.vertices and not gr_node.children and gr_node.parent is not None:
        return None
    return gr_node


def _safe_node_name(fbx_node: Any) -> str:
    try:
        name = fbx_node.GetName()
    except Exception:
        name = "node"
    clean = "".join(ch for ch in str(name or "node") if 32 <= ord(ch) < 127).strip()
    return (clean or "node")[:32]


def _apply_local_transform(fbx_node: Any, gr_node: ModelNode) -> None:
    try:
        gr_node.position = tuple(float(fbx_node.LclTranslation.Get()[i]) for i in range(3))
    except Exception:
        pass
    try:
        rot = tuple(float(fbx_node.LclRotation.Get()[i]) for i in range(3))
        gr_node.rotation = euler_degrees_to_quat_xyz(rot)
    except Exception:
        pass


def _is_mesh_attribute(fbx: Any, attr: Any) -> bool:
    if attr is None:
        return False
    mesh_cls = sdk_class(fbx, "FbxMesh", "KFbxMesh")
    if mesh_cls is not None and isinstance(attr, mesh_cls):
        return True
    try:
        attr_type = attr.GetAttributeType()
        node_attr_cls = sdk_class(fbx, "FbxNodeAttribute", "KFbxNodeAttribute")
        mesh_values = [
            getattr(node_attr_cls, "eMesh", None),
            getattr(node_attr_cls, "eMESH", None),
        ]
        return attr_type in mesh_values or "mesh" in str(attr_type).lower()
    except Exception:
        return hasattr(attr, "GetPolygonCount") and hasattr(attr, "GetControlPointsCount")


def _count_skeleton_nodes(fbx: Any, root_fbx: Any) -> int:
    if root_fbx is None:
        return 0
    count = 0
    stack = [root_fbx]
    skeleton_cls = sdk_class(fbx, "FbxSkeleton", "KFbxSkeleton")
    while stack:
        node = stack.pop()
        attr = node.GetNodeAttribute()
        if skeleton_cls is not None and isinstance(attr, skeleton_cls):
            count += 1
        for index in range(node.GetChildCount()):
            stack.append(node.GetChild(index))
    return count


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

