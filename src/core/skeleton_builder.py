"""Build KOTOR skin bindings for Character Builder imports.

KOTOR character deformation is name-driven: the body mesh references a local
bone map, each bone-map slot names a node in the same Odyssey DAG, and each
vertex stores up to four weights plus four local bone-map indices.  This module
fills those fields for imported meshes after the chosen base skeleton has been
cloned into the model.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Any, Iterable, List, Sequence, Tuple

try:
    from .hooks import is_attachment_hook
    from .model_data import BoneWeight, NodeFlags, VertexSkinData
except ImportError:  # pragma: no cover
    from hooks import is_attachment_hook  # type: ignore
    from model_data import BoneWeight, NodeFlags, VertexSkinData  # type: ignore

Vec3 = Tuple[float, float, float]

_WEIGHTABLE_HOOKS = {"rhand", "lhand"}


@dataclass
class SkinBindingReport:
    ok: bool = False
    skinned_meshes: int = 0
    weighted_vertices: int = 0
    bone_count: int = 0
    message: str = ""
    warnings: List[str] | None = None


def bind_imported_meshes_to_skeleton(
    model: Any,
    *,
    mesh_nodes: Sequence[Any] | None = None,
    max_influences: int = 4,
) -> SkinBindingReport:
    """Populate KOTOR skin fields on imported mesh payloads.

    The weighting is intentionally conservative: use the nearest helper-bone
    segments from the cloned KOTOR DAG, keep at most four influences per
    vertex, and normalize every row to sum to 1.0.  This gives modders a
    functional first bind that can later be improved by library weight transfer
    or manual paint tools.
    """

    if model is None or getattr(model, "root_node", None) is None:
        return SkinBindingReport(message="No model skeleton is available.", warnings=[])

    nodes = list(model.all_nodes() if hasattr(model, "all_nodes") else [])
    if not nodes:
        return SkinBindingReport(message="Model has no nodes to bind.", warnings=[])

    candidates = _candidate_bones(nodes)
    if not candidates:
        return SkinBindingReport(message="No usable KOTOR skeleton bones found.", warnings=[])

    selected_meshes = list(mesh_nodes or _imported_mesh_payloads(nodes))
    if not selected_meshes:
        return SkinBindingReport(message="No imported mesh payloads found to skin.", warnings=[])

    dfs_index = {id(node): idx for idx, node in enumerate(nodes)}
    bone_slots = _bone_slots(candidates, dfs_index)
    if not bone_slots:
        return SkinBindingReport(message="No valid bone-map slots could be built.", warnings=[])

    warnings: List[str] = []
    skinned_meshes = 0
    weighted_vertices = 0
    for mesh in selected_meshes:
        verts = list(getattr(mesh, "vertices", []) or [])
        if not verts:
            continue
        _make_skin_node(mesh)
        mesh.bone_map = [slot[0] for slot in bone_slots]
        mesh.bone_map_floats = [float(slot[1]) for slot in bone_slots]
        mesh.qbone_list = [slot[2] for slot in bone_slots]
        mesh.tbone_list = [slot[3] for slot in bone_slots]
        mesh.skin_data = [
            _weights_for_vertex(_vec3(v), bone_slots, max_influences=max_influences)
            for v in verts
        ]
        mesh.bone_weights = [
            [bw.weight for bw in sd.influences]
            for sd in mesh.skin_data
        ]
        mesh.bone_indices = [
            [bw.bone_index for bw in sd.influences]
            for sd in mesh.skin_data
        ]
        weighted_vertices += len(mesh.skin_data)
        skinned_meshes += 1

    if skinned_meshes == 0:
        warnings.append("Imported mesh payloads had no vertices to weight.")

    return SkinBindingReport(
        ok=skinned_meshes > 0,
        skinned_meshes=skinned_meshes,
        weighted_vertices=weighted_vertices,
        bone_count=len(bone_slots),
        warnings=warnings,
        message=(
            f"Skinned {skinned_meshes} mesh(es), {weighted_vertices} vertices, "
            f"{len(bone_slots)} KOTOR bone-map slots."
        ),
    )


def _candidate_bones(nodes: Sequence[Any]) -> List[Any]:
    bones = [
        node for node in nodes
        if _is_deform_candidate(node)
    ]
    if bones:
        return bones
    return [
        node for node in nodes
        if node is not None
        and not _has_vertices(node)
        and not _is_non_deform_hook(getattr(node, "name", ""))
    ]


def _is_deform_candidate(node: Any) -> bool:
    name = str(getattr(node, "name", "") or "").strip().lower()
    if not name or _is_non_deform_hook(name):
        return False
    if getattr(node, "_external_imported", False):
        return False
    if name.endswith(("_g", "_dum")):
        return True
    return name in {
        "rootdummy",
        "cutscenedummy",
        "talkdummy",
        "lforearm",
        "rforearm",
        "lhand",
        "rhand",
    }


def _imported_mesh_payloads(nodes: Sequence[Any]) -> List[Any]:
    return [
        node for node in nodes
        if _has_vertices(node)
        and (
            getattr(node, "_external_imported", False)
            or getattr(node, "is_skin", False)
            or getattr(node, "is_mesh", False)
        )
        and not _is_deform_candidate(node)
    ]


def _bone_slots(nodes: Sequence[Any], dfs_index: dict[int, int]):
    slots = []
    for node in nodes:
        name = str(getattr(node, "name", "") or "").strip()
        if not name:
            continue
        idx = dfs_index.get(id(node))
        if idx is None:
            continue
        pos, rot = _node_world(node)
        slots.append((name, idx, rot, pos, node, _child_positions(node)))
    return slots


def _weights_for_vertex(vertex: Vec3, slots: Sequence[Any], *, max_influences: int) -> VertexSkinData:
    distances = []
    for local_idx, slot in enumerate(slots):
        origin = slot[3]
        children = slot[5]
        dist = min((_distance_point_segment(vertex, origin, child) for child in children), default=_distance(vertex, origin))
        distances.append((max(dist, 1.0e-5), local_idx))
    distances.sort(key=lambda item: item[0])
    chosen = distances[: max(1, min(4, int(max_influences or 4)))]
    raw = [(idx, 1.0 / (dist * dist)) for dist, idx in chosen]
    total = sum(weight for _idx, weight in raw)
    if not isfinite(total) or total <= 1.0e-12:
        return VertexSkinData([BoneWeight(chosen[0][1], 1.0)])
    influences = [
        BoneWeight(idx, weight / total)
        for idx, weight in raw
        if weight > 0.0
    ]
    sd = VertexSkinData(influences[:4])
    sd.normalize()
    return sd


def _make_skin_node(node: Any) -> None:
    flags = int(getattr(node, "flags", 0))
    node.flags = int((flags | int(NodeFlags.HEADER) | int(NodeFlags.MESH) | int(NodeFlags.SKIN)))
    node.render = True
    setattr(node, "_external_imported", True)


def _child_positions(node: Any) -> List[Vec3]:
    children = []
    for child in list(getattr(node, "children", []) or []):
        if child is None or _is_non_deform_hook(getattr(child, "name", "")):
            continue
        try:
            children.append(child.bone_world_position())
        except Exception:
            try:
                children.append(child.world_transform()[0])
            except Exception:
                pass
    return children


def _node_world(node: Any) -> Tuple[Vec3, Tuple[float, float, float, float]]:
    try:
        pos = node.bone_world_position()
    except Exception:
        try:
            pos = node.world_transform()[0]
        except Exception:
            pos = tuple(getattr(node, "position", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0))
    try:
        _wp, rot = node.world_transform()
    except Exception:
        rot = tuple(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0)) or (0.0, 0.0, 0.0, 1.0))
    return _vec3(pos), _quat(rot)


def _has_vertices(node: Any) -> bool:
    return bool(getattr(node, "vertices", None))


def _is_non_deform_hook(name: str) -> bool:
    clean = str(name or "").strip().lower()
    return is_attachment_hook(clean) and clean not in _WEIGHTABLE_HOOKS


def _vec3(value: Iterable[Any]) -> Vec3:
    vals = list(value)
    return (float(vals[0]), float(vals[1]), float(vals[2]))


def _quat(value: Iterable[Any]) -> Tuple[float, float, float, float]:
    vals = list(value)
    if len(vals) < 4:
        return (0.0, 0.0, 0.0, 1.0)
    return (float(vals[0]), float(vals[1]), float(vals[2]), float(vals[3]))


def _distance(a: Vec3, b: Vec3) -> float:
    return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _distance_point_segment(p: Vec3, a: Vec3, b: Vec3) -> float:
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ap = (p[0] - a[0], p[1] - a[1], p[2] - a[2])
    denom = ab[0] * ab[0] + ab[1] * ab[1] + ab[2] * ab[2]
    if denom <= 1.0e-12:
        return _distance(p, a)
    t = max(0.0, min(1.0, (ap[0] * ab[0] + ap[1] * ab[1] + ap[2] * ab[2]) / denom))
    q = (a[0] + ab[0] * t, a[1] + ab[1] * t, a[2] + ab[2] * t)
    return _distance(p, q)
