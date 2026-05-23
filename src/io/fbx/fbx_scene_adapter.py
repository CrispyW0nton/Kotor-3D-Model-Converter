"""Conversion helpers between Autodesk FBX SDK objects and GhostRigger models."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
from typing import Any, Iterable

from src.core.geometry.model_data import GameVersion, KotorModel, ModelNode, NodeFlags


@dataclass
class FbxImportSummary:
    meshes: int = 0
    vertices: int = 0
    faces: int = 0
    materials: int = 0
    textures: int = 0
    bones: int = 0
    warnings: list[str] = field(default_factory=list)

    def log_line(self) -> str:
        return (
            f"meshes={self.meshes}, vertices={self.vertices}, faces={self.faces}, "
            f"materials={self.materials}, textures={self.textures}, bones={self.bones}"
        )


@dataclass
class FbxExportSummary:
    meshes: int = 0
    vertices: int = 0
    faces: int = 0
    materials: int = 0
    textures: int = 0
    warnings: list[str] = field(default_factory=list)

    def log_line(self) -> str:
        return (
            f"meshes={self.meshes}, vertices={self.vertices}, faces={self.faces}, "
            f"materials={self.materials}, textures={self.textures}"
        )


def sdk_class(fbx: Any, new_name: str, old_name: str | None = None) -> Any:
    """Return a modern ``Fbx*`` class or its legacy ``KFbx*`` equivalent."""
    return getattr(fbx, new_name, getattr(fbx, old_name or f"K{new_name}", None))


def _triple_from_fbx(value: Any, default: tuple[float, float, float]) -> tuple[float, float, float]:
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except Exception:
        return default


def _name(obj: Any, fallback: str) -> str:
    try:
        value = obj.GetName()
    except Exception:
        value = ""
    return str(value or fallback)


def _clean_name(value: str, fallback: str = "node") -> str:
    clean = "".join(ch for ch in str(value or "") if 32 <= ord(ch) < 127).strip()
    return (clean or fallback)[:32]


def euler_degrees_to_quat_xyz(rot: Iterable[float]) -> tuple[float, float, float, float]:
    rx, ry, rz = [math.radians(float(v)) * 0.5 for v in list(rot)[:3]]
    sx, cx = math.sin(rx), math.cos(rx)
    sy, cy = math.sin(ry), math.cos(ry)
    sz, cz = math.sin(rz), math.cos(rz)
    qx = sx * cy * cz + cx * sy * sz
    qy = cx * sy * cz - sx * cy * sz
    qz = cx * cy * sz + sx * sy * cz
    qw = cx * cy * cz - sx * sy * sz
    return (qx, qy, qz, qw)


def quat_xyzw_to_euler_degrees(quat: Iterable[float]) -> tuple[float, float, float]:
    x, y, z, w = [float(v) for v in list(quat)[:4]]
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)
    sinp = 2.0 * (w * y - z * x)
    pitch = math.copysign(math.pi / 2.0, sinp) if abs(sinp) >= 1.0 else math.asin(sinp)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    return (math.degrees(roll), math.degrees(pitch), math.degrees(yaw))


def fbx_matrix_to_gr_matrix(matrix: Any) -> list[list[float]]:
    """Convert an FBX matrix-like object to a plain 4x4 float matrix."""
    result: list[list[float]] = []
    for row in range(4):
        result.append([float(matrix.Get(row, col) if hasattr(matrix, "Get") else matrix[row][col]) for col in range(4)])
    return result


def gr_transform_to_fbx_matrix(fbx: Any, position: tuple[float, float, float], rotation: tuple[float, float, float, float]):
    """Build an FBX matrix when the SDK exposes ``FbxAMatrix``/``KFbxXMatrix``."""
    matrix_cls = sdk_class(fbx, "FbxAMatrix", "KFbxXMatrix")
    vector4_cls = sdk_class(fbx, "FbxVector4", "KFbxVector4")
    if matrix_cls is None or vector4_cls is None:
        return None
    matrix = matrix_cls()
    set_t = getattr(matrix, "SetT", None)
    set_r = getattr(matrix, "SetR", None)
    if callable(set_t):
        set_t(vector4_cls(*position))
    if callable(set_r):
        set_r(vector4_cls(*quat_xyzw_to_euler_degrees(rotation)))
    return matrix


def fbx_material_to_gr_material(fbx: Any, material: Any) -> dict[str, Any]:
    name = _name(material, "material")
    diffuse = (0.8, 0.8, 0.8)
    texture = ""
    try:
        prop = material.FindProperty(getattr(fbx.FbxSurfaceMaterial, "sDiffuse", "DiffuseColor"))
        if prop and prop.IsValid():
            value = prop.Get()
            diffuse = _triple_from_fbx(value, diffuse)
            file_texture_cls = sdk_class(fbx, "FbxFileTexture", "KFbxFileTexture")
            count = prop.GetSrcObjectCount(file_texture_cls.ClassId) if file_texture_cls is not None else prop.GetSrcObjectCount()
            if count:
                tex = prop.GetSrcObject(file_texture_cls.ClassId, 0) if file_texture_cls is not None else prop.GetSrcObject(0)
                filename = getattr(tex, "GetFileName", lambda: "")()
                texture = Path(str(filename)).stem[:32]
    except Exception:
        pass
    return {"name": name, "diffuse": diffuse, "texture": texture}


def fbx_mesh_to_gr_mesh(fbx: Any, fbx_node: Any, fbx_mesh: Any, summary: FbxImportSummary | None = None) -> ModelNode:
    """Convert an FBX mesh node to a renderable GhostRigger ``ModelNode``."""
    node = ModelNode(name=_clean_name(_name(fbx_node, _name(fbx_mesh, "mesh")), "mesh"), flags=int(NodeFlags.HEADER | NodeFlags.MESH))
    node.render = True
    node._imported = True
    lcl_t = getattr(fbx_node, "LclTranslation", None)
    lcl_r = getattr(fbx_node, "LclRotation", None)
    if lcl_t is not None:
        node.position = _triple_from_fbx(lcl_t.Get(), (0.0, 0.0, 0.0))
    if lcl_r is not None:
        node.rotation = euler_degrees_to_quat_xyz(_triple_from_fbx(lcl_r.Get(), (0.0, 0.0, 0.0)))

    materials = [fbx_material_to_gr_material(fbx, fbx_node.GetMaterial(i)) for i in range(getattr(fbx_node, "GetMaterialCount", lambda: 0)())]
    if materials:
        node.texture = str(materials[0].get("texture") or materials[0].get("name") or "")[:32]
        node.diffuse = tuple(materials[0].get("diffuse") or node.diffuse)  # type: ignore[assignment]
        node.texture_names = [str(mat.get("texture") or mat.get("name") or "")[:32] for mat in materials]
        node.tex_count = max(1, len(node.texture_names))

    uv_set_names = []
    try:
        names = fbx.FbxStringList()
        fbx_mesh.GetUVSetNames(names)
        uv_set_names = [str(names.GetStringAt(i)) for i in range(names.GetCount())]
    except Exception:
        uv_set_names = ["UVMap"]
    uv_set_name = uv_set_names[0] if uv_set_names else ""

    vertex_map: dict[tuple[Any, ...], int] = {}
    faces: list[tuple[int, int, int]] = []
    face_mats: list[int] = []

    def add_poly_vertex(poly_index: int, corner: int) -> int:
        cp_index = int(fbx_mesh.GetPolygonVertex(poly_index, corner))
        cp = fbx_mesh.GetControlPointAt(cp_index)
        pos = (float(cp[0]), float(cp[1]), float(cp[2]))
        normal = (0.0, 0.0, 1.0)
        try:
            vec4 = sdk_class(fbx, "FbxVector4", "KFbxVector4")()
            if fbx_mesh.GetPolygonVertexNormal(poly_index, corner, vec4):
                normal = (float(vec4[0]), float(vec4[1]), float(vec4[2]))
        except Exception:
            pass
        uv = (0.0, 0.0)
        try:
            vec2 = sdk_class(fbx, "FbxVector2", "KFbxVector2")()
            unmapped = False
            ok = fbx_mesh.GetPolygonVertexUV(poly_index, corner, uv_set_name, vec2, unmapped)
            if ok:
                uv = (float(vec2[0]), float(vec2[1]))
        except Exception:
            pass
        key = (cp_index, pos, normal, uv)
        if key in vertex_map:
            return vertex_map[key]
        index = len(node.vertices)
        vertex_map[key] = index
        node.vertices.append(pos)
        node.normals.append(normal)
        node.uvs.append(uv)
        return index

    polygon_count = int(fbx_mesh.GetPolygonCount())
    for poly_index in range(polygon_count):
        corners = int(fbx_mesh.GetPolygonSize(poly_index))
        if corners < 3:
            continue
        indices = [add_poly_vertex(poly_index, corner) for corner in range(corners)]
        mat_index = _polygon_material_index(fbx_mesh, poly_index)
        for i in range(1, len(indices) - 1):
            faces.append((indices[0], indices[i], indices[i + 1]))
            face_mats.append(mat_index)

    node.faces = faces
    node.face_mats = face_mats
    node.compute_bounds()
    if summary is not None:
        summary.meshes += 1
        summary.vertices += len(node.vertices)
        summary.faces += len(node.faces)
        summary.materials += len(materials)
        summary.textures += sum(1 for mat in materials if mat.get("texture"))
    return node


def _polygon_material_index(fbx_mesh: Any, poly_index: int) -> int:
    try:
        layer = fbx_mesh.GetLayer(0)
        mats = layer.GetMaterials() if layer else None
        if mats:
            mode_name = str(mats.GetMappingMode())
            array = mats.GetIndexArray()
            if "ByPolygon" in mode_name and array.GetCount() > poly_index:
                return int(array.GetAt(poly_index))
            if array.GetCount() > 0:
                return int(array.GetAt(0))
    except Exception:
        pass
    return 0


def gr_material_to_fbx_material(fbx: Any, manager: Any, node: ModelNode) -> Any:
    material_cls = sdk_class(fbx, "FbxSurfacePhong", "KFbxSurfacePhong")
    double3_cls = sdk_class(fbx, "FbxDouble3", "KFbxDouble3")
    material = material_cls.Create(manager, (_clean_name(node.texture or node.name, "material"))) if material_cls else None
    if material is None:
        return None
    try:
        material.Diffuse.Set(double3_cls(*tuple(float(v) for v in node.diffuse[:3])))
        material.Ambient.Set(double3_cls(*tuple(float(v) for v in node.ambient[:3])))
        material.Specular.Set(double3_cls(*tuple(float(v) for v in node.specular[:3])))
        material.TransparencyFactor.Set(max(0.0, min(1.0, 1.0 - float(node.alpha))))
    except Exception:
        pass
    # Texture references are stored as file names only. Embedding media is an
    # exporter option, but GhostRigger does not own Autodesk SDK binary media
    # plumbing here.
    tex_name = str(getattr(node, "texture_clean", "") or node.texture or "").strip()
    if tex_name and tex_name.upper() not in {"NULL", "BLACK"}:
        texture_cls = sdk_class(fbx, "FbxFileTexture", "KFbxFileTexture")
        try:
            texture = texture_cls.Create(manager, tex_name)
            texture.SetFileName(f"{tex_name}.tga")
            texture.SetTextureUse(texture.eStandard)
            texture.SetMappingType(texture.eUV)
            texture.SetMaterialUse(texture.eModelMaterial)
            material.Diffuse.ConnectSrcObject(texture)
        except Exception:
            pass
    return material


def gr_mesh_to_fbx_mesh(fbx: Any, manager: Any, node: ModelNode, *, triangulate: bool = True) -> Any:
    mesh_cls = sdk_class(fbx, "FbxMesh", "KFbxMesh")
    vector4_cls = sdk_class(fbx, "FbxVector4", "KFbxVector4")
    vector2_cls = sdk_class(fbx, "FbxVector2", "KFbxVector2")
    mesh = mesh_cls.Create(manager, _clean_name(node.name, "mesh"))
    mesh.InitControlPoints(len(node.vertices))
    for index, (x, y, z) in enumerate(node.vertices):
        mesh.SetControlPointAt(vector4_cls(float(x), float(y), float(z), 0.0), index)

    if mesh.GetLayer(0) is None:
        mesh.CreateLayer()

    normal_layer = None
    if node.normals:
        normal_cls = getattr(fbx, "FbxLayerElementNormal", getattr(fbx, "KFbxLayerElementNormal", None))
        layer_elem_cls = getattr(fbx, "FbxLayerElement", getattr(fbx, "KFbxLayerElement", None))
        normal_layer = normal_cls.Create(mesh, "Normals")
        normal_layer.SetMappingMode(layer_elem_cls.eByControlPoint)
        normal_layer.SetReferenceMode(layer_elem_cls.eDirect)
        for nx, ny, nz in node.normals:
            normal_layer.GetDirectArray().Add(vector4_cls(float(nx), float(ny), float(nz), 0.0))
        mesh.GetLayer(0).SetNormals(normal_layer)

    if node.uvs:
        uv_cls = getattr(fbx, "FbxLayerElementUV", getattr(fbx, "KFbxLayerElementUV", None))
        layer_elem_cls = getattr(fbx, "FbxLayerElement", getattr(fbx, "KFbxLayerElement", None))
        uv_layer = uv_cls.Create(mesh, "UVMap")
        uv_layer.SetMappingMode(layer_elem_cls.eByControlPoint)
        uv_layer.SetReferenceMode(layer_elem_cls.eDirect)
        for u, v in node.uvs:
            uv_layer.GetDirectArray().Add(vector2_cls(float(u), float(v)))
        mesh.GetLayer(0).SetUVs(uv_layer)

    for face in node.faces:
        if len(face) != 3 and triangulate:
            continue
        mesh.BeginPolygon(0 if (node.texture or node.texture_names) else -1, -1, False)
        for vertex_index in face:
            mesh.AddPolygon(int(vertex_index))
        mesh.EndPolygon()
    return mesh


def iter_renderable_mesh_nodes(model: KotorModel) -> list[ModelNode]:
    return [
        node
        for node in model.mesh_nodes()
        if getattr(node, "vertices", None) and getattr(node, "faces", None) and bool(getattr(node, "render", True))
    ]


def count_bone_like_nodes(model: KotorModel) -> int:
    return sum(1 for node in model.all_nodes() if node.type_label == "dummy")

