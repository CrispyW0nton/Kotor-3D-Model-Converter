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
    from ..special.hooks import is_attachment_hook
    from ..geometry.model_data import BoneWeight, NodeFlags, VertexSkinData
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
    weighting_method: str = "nearest_kotor_bone_segment"
    quality_stage: str = "fallback_first_pass"
    donor_weight_transfer: bool = False
    mesh_reports: List[dict] | None = None


def bind_imported_meshes_to_skeleton(
    model: Any,
    *,
    mesh_nodes: Sequence[Any] | None = None,
    donor_model: Any | None = None,
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
    mesh_reports: List[dict] = []
    donor_index = _build_donor_vertex_index(
        donor_model,
        bone_slots,
        max_influences=max_influences,
    )
    donor_vertices_used = 0
    fallback_vertices_used = 0
    skinned_meshes = 0
    weighted_vertices = 0
    generated_bone_slot_counts: List[int] = []
    for mesh in selected_meshes:
        verts = list(getattr(mesh, "vertices", []) or [])
        if not verts:
            continue
        _make_skin_node(mesh)
        mesh.bone_map = [slot[0] for slot in bone_slots]
        mesh.bone_map_floats = [float(slot[1]) for slot in bone_slots]
        mesh.qbone_list = [slot[2] for slot in bone_slots]
        mesh.tbone_list = [slot[3] for slot in bone_slots]
        mesh.skin_data = []
        mesh_donor_vertices = 0
        mesh_fallback_vertices = 0
        for vertex in verts:
            skin_row, used_donor = _weights_for_vertex_with_donor(
                _vec3(vertex),
                bone_slots,
                donor_index,
                max_influences=max_influences,
            )
            mesh.skin_data.append(skin_row)
            if used_donor:
                mesh_donor_vertices += 1
            else:
                mesh_fallback_vertices += 1
        compact_report = _compact_skin_bone_map_to_used_influences(mesh)
        mesh.bone_weights = [
            [bw.weight for bw in sd.influences]
            for sd in mesh.skin_data
        ]
        mesh.bone_indices = [
            [bw.bone_index for bw in sd.influences]
            for sd in mesh.skin_data
        ]
        mesh_report = _mesh_binding_report(
            mesh,
            weighting_method=(
                "native_template_nearest_vertex_donor"
                if mesh_donor_vertices and not mesh_fallback_vertices else
                "native_template_nearest_vertex_donor_with_fallback"
                if mesh_donor_vertices else
                "nearest_kotor_bone_segment"
            ),
            quality_stage=(
                "donor_transfer_first_pass"
                if mesh_donor_vertices and not mesh_fallback_vertices else
                "donor_transfer_partial"
                if mesh_donor_vertices else
                "fallback_first_pass"
            ),
            max_influences=max_influences,
            donor_weight_transfer=bool(mesh_donor_vertices),
            donor_vertices=mesh_donor_vertices,
            fallback_vertices=mesh_fallback_vertices,
            donor_vertex_count=len(donor_index),
            compact_report=compact_report,
        )
        mesh_reports.append(mesh_report)
        setattr(mesh, "_gr_skin_binding_report", mesh_report)
        donor_vertices_used += mesh_donor_vertices
        fallback_vertices_used += mesh_fallback_vertices
        generated_bone_slot_counts.append(len(list(getattr(mesh, "bone_map", []) or [])))
        weighted_vertices += len(mesh.skin_data)
        skinned_meshes += 1

    if skinned_meshes == 0:
        warnings.append("Imported mesh payloads had no vertices to weight.")
    elif donor_vertices_used and not fallback_vertices_used:
        warnings.append(
            "Transferred skin weights from the selected native KOTOR template "
            "by nearest donor surface vertex."
        )
    elif donor_vertices_used:
        warnings.append(
            "Partially transferred skin weights from the selected native KOTOR "
            "template; remaining vertices used nearest bone-segment fallback."
        )
    else:
        warnings.append(
            "Using nearest KOTOR bone-segment fallback weights. "
            "Use native-template/donor weight transfer for launch-quality deformation."
        )
    weighting_method = (
        "native_template_nearest_vertex_donor"
        if donor_vertices_used and not fallback_vertices_used else
        "native_template_nearest_vertex_donor_with_fallback"
        if donor_vertices_used else
        "nearest_kotor_bone_segment"
    )
    quality_stage = (
        "donor_transfer_first_pass"
        if donor_vertices_used and not fallback_vertices_used else
        "donor_transfer_partial"
        if donor_vertices_used else
        "fallback_first_pass"
    )
    max_generated_bone_slots = max(generated_bone_slot_counts, default=0)

    return SkinBindingReport(
        ok=skinned_meshes > 0,
        skinned_meshes=skinned_meshes,
        weighted_vertices=weighted_vertices,
        bone_count=max_generated_bone_slots,
        warnings=warnings,
        weighting_method=weighting_method,
        quality_stage=quality_stage,
        donor_weight_transfer=bool(donor_vertices_used),
        mesh_reports=mesh_reports,
        message=(
            f"Skinned {skinned_meshes} mesh(es), {weighted_vertices} vertices, "
            f"{max_generated_bone_slots} generated KOTOR bone-map slots "
            f"from {len(bone_slots)} native candidates."
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


def _weights_for_vertex_with_donor(
    vertex: Vec3,
    slots: Sequence[Any],
    donor_index: Sequence[Any],
    *,
    max_influences: int,
) -> tuple[VertexSkinData, bool]:
    donor = _nearest_donor_vertex(vertex, donor_index)
    if donor is not None:
        influences = _normalize_influences(
            donor[1],
            max_influences=max_influences,
        )
        if influences:
            return VertexSkinData(influences), True
    return _weights_for_vertex(vertex, slots, max_influences=max_influences), False


def _build_donor_vertex_index(
    donor_model: Any | None,
    slots: Sequence[Any],
    *,
    max_influences: int,
) -> List[tuple[Vec3, List[BoneWeight], str]]:
    if donor_model is None:
        return []
    all_nodes = getattr(donor_model, "all_nodes", None)
    if not callable(all_nodes):
        return []
    slot_by_name = {
        str(slot[0] or ""): index
        for index, slot in enumerate(slots)
        if str(slot[0] or "").strip()
    }
    donor_vertices: List[tuple[Vec3, List[BoneWeight], str]] = []
    for node in list(all_nodes()):
        if not bool(getattr(node, "is_skin", False)):
            continue
        verts = list(getattr(node, "vertices", []) or [])
        skin_rows = list(getattr(node, "skin_data", []) or [])
        bone_map = list(getattr(node, "bone_map", []) or [])
        if not verts or not skin_rows or not bone_map:
            continue
        origin, rot = _node_world(node)
        for vertex_index, vertex in enumerate(verts[:len(skin_rows)]):
            donor_weights = _map_donor_influences_to_slots(
                skin_rows[vertex_index],
                bone_map,
                slot_by_name,
                max_influences=max_influences,
            )
            if not donor_weights:
                continue
            donor_vertices.append((
                _transform_point(_vec3(vertex), origin, rot),
                donor_weights,
                str(getattr(node, "name", "") or ""),
            ))
    return donor_vertices


def _map_donor_influences_to_slots(
    skin_row: Any,
    donor_bone_map: Sequence[Any],
    slot_by_name: dict[str, int],
    *,
    max_influences: int,
) -> List[BoneWeight]:
    merged: dict[int, float] = {}
    for influence in list(getattr(skin_row, "influences", []) or []):
        try:
            donor_index = int(getattr(influence, "bone_index", -1))
            weight = float(getattr(influence, "weight", 0.0))
        except (TypeError, ValueError, OverflowError):
            continue
        if donor_index < 0 or donor_index >= len(donor_bone_map) or weight <= 0.0:
            continue
        bone_name = str(donor_bone_map[donor_index] or "").strip()
        if not bone_name:
            continue
        target_index = slot_by_name.get(bone_name)
        if target_index is None:
            continue
        merged[target_index] = merged.get(target_index, 0.0) + weight
    return _normalize_influences(
        [BoneWeight(index, weight) for index, weight in merged.items()],
        max_influences=max_influences,
    )


def _nearest_donor_vertex(
    vertex: Vec3,
    donor_index: Sequence[tuple[Vec3, List[BoneWeight], str]],
) -> tuple[Vec3, List[BoneWeight], str] | None:
    nearest = None
    nearest_dist = float("inf")
    for donor in donor_index:
        dist = _distance(vertex, donor[0])
        if dist < nearest_dist:
            nearest = donor
            nearest_dist = dist
    return nearest


def _normalize_influences(
    influences: Sequence[BoneWeight],
    *,
    max_influences: int,
) -> List[BoneWeight]:
    merged: dict[int, float] = {}
    for influence in influences:
        try:
            index = int(getattr(influence, "bone_index", -1))
            weight = float(getattr(influence, "weight", 0.0))
        except (TypeError, ValueError, OverflowError):
            continue
        if index < 0 or weight <= 0.0:
            continue
        merged[index] = merged.get(index, 0.0) + weight
    ordered = sorted(merged.items(), key=lambda item: item[1], reverse=True)
    ordered = ordered[:max(1, min(4, int(max_influences or 4)))]
    total = sum(weight for _index, weight in ordered)
    if not isfinite(total) or total <= 1.0e-12:
        return []
    return [
        BoneWeight(index, weight / total)
        for index, weight in ordered
    ]


def _compact_skin_bone_map_to_used_influences(mesh: Any) -> dict:
    """Drop unused skin bone-map slots and remap vertex influences.

    KOTOR skin rows index into the mesh-local bone map. Character Builder first
    builds the full candidate list from the native skeleton so donor/fallback
    weighting has the entire DAG available. After weighting, only referenced
    slots need to survive into MDL/MDX export; keeping the map compact also
    keeps qBone/tBone metadata aligned after writer/readback verification.
    """

    bone_map = list(getattr(mesh, "bone_map", []) or [])
    skin_rows = list(getattr(mesh, "skin_data", []) or [])
    original_count = len(bone_map)
    if not bone_map or not skin_rows:
        return {
            "bone_slots_compacted": False,
            "original_bone_map_count": original_count,
            "compacted_bone_map_count": original_count,
            "used_bone_map_count": 0,
        }

    used_indices = _used_influence_indices(skin_rows, original_count)
    if not used_indices:
        used_indices = [0]

    remap = {old_index: new_index for new_index, old_index in enumerate(used_indices)}
    for row in skin_rows:
        remapped: List[BoneWeight] = []
        for influence in list(getattr(row, "influences", []) or []):
            try:
                old_index = int(getattr(influence, "bone_index", -1))
                weight = float(getattr(influence, "weight", 0.0))
            except (TypeError, ValueError, OverflowError):
                continue
            new_index = remap.get(old_index)
            if new_index is None:
                continue
            if weight <= 0.0:
                continue
            remapped.append(BoneWeight(new_index, weight))
        if not remapped:
            remapped = [BoneWeight(0, 1.0)]
        row.influences = _normalize_influences(remapped, max_influences=4)

    mesh.bone_map = [bone_map[index] for index in used_indices]
    mesh.bone_map_floats = _filter_parallel_list(
        getattr(mesh, "bone_map_floats", []) or [],
        used_indices,
        default=0.0,
    )
    mesh.qbone_list = _filter_parallel_list(
        getattr(mesh, "qbone_list", []) or [],
        used_indices,
        default=(0.0, 0.0, 0.0, 1.0),
    )
    mesh.tbone_list = _filter_parallel_list(
        getattr(mesh, "tbone_list", []) or [],
        used_indices,
        default=(0.0, 0.0, 0.0),
    )
    return {
        "bone_slots_compacted": len(used_indices) != original_count,
        "original_bone_map_count": original_count,
        "compacted_bone_map_count": len(used_indices),
        "used_bone_map_count": len(used_indices),
    }


def _used_influence_indices(
    skin_rows: Sequence[Any],
    bone_map_count: int,
) -> List[int]:
    used: set[int] = set()
    for row in skin_rows:
        for influence in list(getattr(row, "influences", []) or []):
            try:
                index = int(getattr(influence, "bone_index", -1))
                weight = float(getattr(influence, "weight", 0.0))
            except (TypeError, ValueError, OverflowError):
                continue
            if 0 <= index < bone_map_count and weight > 0.0:
                used.add(index)
    return sorted(used)


def _filter_parallel_list(
    values: Sequence[Any],
    indices: Sequence[int],
    *,
    default: Any,
) -> list:
    filtered = []
    for index in indices:
        filtered.append(values[index] if 0 <= index < len(values) else default)
    return filtered


def _mesh_binding_report(
    mesh: Any,
    *,
    weighting_method: str,
    quality_stage: str,
    max_influences: int,
    donor_weight_transfer: bool = False,
    donor_vertices: int = 0,
    fallback_vertices: int = 0,
    donor_vertex_count: int = 0,
    compact_report: dict | None = None,
) -> dict:
    skin_rows = list(getattr(mesh, "skin_data", []) or [])
    influence_counts: List[int] = []
    weight_sums: List[float] = []
    zero_weight_vertices = 0
    for row in skin_rows:
        influences = list(getattr(row, "influences", []) or [])
        influence_counts.append(len(influences))
        total = 0.0
        for influence in influences:
            try:
                total += float(getattr(influence, "weight", 0.0))
            except (TypeError, ValueError, OverflowError):
                total += 0.0
        weight_sums.append(total)
        if total <= 0.0:
            zero_weight_vertices += 1
    vertex_count = len(list(getattr(mesh, "vertices", []) or []))
    average_count = (
        sum(influence_counts) / len(influence_counts)
        if influence_counts else
        0.0
    )
    compact_report = dict(compact_report or {})
    return {
        "mesh_name": str(getattr(mesh, "name", "") or ""),
        "weighting_method": weighting_method,
        "quality_stage": quality_stage,
        "vertex_count": vertex_count,
        "skin_rows": len(skin_rows),
        "weighted_vertices": max(0, len(skin_rows) - zero_weight_vertices),
        "zero_weight_vertices": zero_weight_vertices,
        "bone_map_count": len(list(getattr(mesh, "bone_map", []) or [])),
        "max_influences_per_vertex": max(influence_counts, default=0),
        "average_influences_per_vertex": average_count,
        "weight_sum_min": min(weight_sums, default=0.0),
        "weight_sum_max": max(weight_sums, default=0.0),
        "normalization": "normalized_rows",
        "max_influences_requested": max(1, min(4, int(max_influences or 4))),
        "donor_weight_transfer": bool(donor_weight_transfer),
        "donor_vertices": int(donor_vertices),
        "fallback_vertices": int(fallback_vertices),
        "donor_vertex_count": int(donor_vertex_count),
        **compact_report,
    }


def _transform_point(
    point: Vec3,
    origin: Vec3,
    rotation: Tuple[float, float, float, float],
) -> Vec3:
    rotated = _quat_rotate_vec(rotation, point)
    return (
        rotated[0] + origin[0],
        rotated[1] + origin[1],
        rotated[2] + origin[2],
    )


def _quat_rotate_vec(
    q: Tuple[float, float, float, float],
    v: Vec3,
) -> Vec3:
    try:
        x, y, z, w = (float(q[0]), float(q[1]), float(q[2]), float(q[3]))
        vx, vy, vz = (float(v[0]), float(v[1]), float(v[2]))
    except Exception:
        return v
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    )


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
