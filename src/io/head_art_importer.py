"""Deterministic OBJ/FBX ingestion contract for Custom Head Builder art.

Core IO owns file identity, decode selection, channel preservation, and
topology facts.  The returned document keeps runtime mesh arrays in memory but
its project representation stores only source references, hashes, settings,
and compact facts; ``.ghosthead.json`` never becomes a mesh-blob container.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Callable, Iterable, Sequence

from src.math.head_alignment import (
    Mat4,
    source_axis_to_imported_matrix,
    transform_point,
    transform_vector,
)


Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]
Face = tuple[int, int, int]

MAX_HEAD_ART_BYTES = 2 * 1024 * 1024 * 1024
SUPPORTED_HEAD_ART_EXTENSIONS = (".obj", ".fbx")


class HeadArtImportError(RuntimeError):
    """Raised when a source file cannot produce an inspectable mesh document."""


@dataclass(frozen=True, slots=True)
class HeadArtTopologyFacts:
    invalid_face_count: int = 0
    non_manifold_edge_count: int = 0
    border_edge_count: int = 0
    boundary_chain_count: int = 0
    isolated_vertex_count: int = 0
    degenerate_face_count: int = 0
    inconsistent_winding_edge_count: int = 0
    duplicate_vertex_count: int = 0
    duplicate_face_count: int = 0
    branched_boundary_vertex_count: int = 0
    component_count: int = 0
    nonfinite_value_count: int = 0
    channel_length_error_count: int = 0
    has_errors: bool = False
    has_warnings: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            name: getattr(self, name)
            for name in self.__dataclass_fields__
        }


@dataclass(frozen=True, slots=True)
class HeadArtPart:
    """One deterministic render part in imported KOTOR object space."""

    part_id: str
    name: str
    material_name: str
    vertices: tuple[Vec3, ...]
    faces: tuple[Face, ...]
    uvs: tuple[Vec2, ...] = ()
    normals: tuple[Vec3, ...] = ()
    source_vertex_indices: tuple[int, ...] = ()
    vertex_id_basis: str = "imported_compacted_index"
    authored_uvs: bool = False
    authored_normals: bool = False
    topology: HeadArtTopologyFacts = field(
        default_factory=HeadArtTopologyFacts
    )

    @property
    def bounds_min(self) -> Vec3:
        return _bounds(self.vertices)[0]

    @property
    def bounds_max(self) -> Vec3:
        return _bounds(self.vertices)[1]

    def project_facts(self) -> dict[str, Any]:
        """Return compact project-safe facts without mesh arrays."""

        return {
            "part_id": self.part_id,
            "name": self.name,
            "material_name": self.material_name,
            "vertex_count": len(self.vertices),
            "face_count": len(self.faces),
            "uv_count": len(self.uvs),
            "normal_count": len(self.normals),
            "source_vertex_index_count": len(self.source_vertex_indices),
            "vertex_id_basis": self.vertex_id_basis,
            "authored_uvs": self.authored_uvs,
            "authored_normals": self.authored_normals,
            "bounds_min": list(self.bounds_min),
            "bounds_max": list(self.bounds_max),
            "topology": self.topology.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class HeadArtValidationIssue:
    check_id: str
    severity: str
    message: str
    part_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "severity": self.severity,
            "message": self.message,
            "part_id": self.part_id,
        }


@dataclass(frozen=True, slots=True)
class HeadArtValidationReport:
    accepted: bool
    issues: tuple[HeadArtValidationIssue, ...]

    @property
    def errors(self) -> tuple[HeadArtValidationIssue, ...]:
        return tuple(row for row in self.issues if row.severity == "error")

    @property
    def warnings(self) -> tuple[HeadArtValidationIssue, ...]:
        return tuple(row for row in self.issues if row.severity == "warning")

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "issues": [row.to_dict() for row in self.issues],
        }


@dataclass(frozen=True, slots=True)
class HeadArtDocument:
    """Runtime custom-art document with a blob-free persistence projection."""

    source_path: str
    source_sha256: str
    source_size_bytes: int
    source_format: str
    source_axis: str
    imported_axis: str
    unit_scale_to_kotor: float
    source_to_imported: Mat4
    flip_v: bool
    parts: tuple[HeadArtPart, ...]
    warnings: tuple[str, ...] = ()
    structural_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.parts:
            raise HeadArtImportError("Custom head art contains no renderable mesh parts")
        if not self.structural_sha256:
            object.__setattr__(
                self,
                "structural_sha256",
                _document_structural_sha256(self),
            )

    @property
    def vertex_count(self) -> int:
        return sum(len(part.vertices) for part in self.parts)

    @property
    def face_count(self) -> int:
        return sum(len(part.faces) for part in self.parts)

    @property
    def bounds_min(self) -> Vec3:
        return tuple(
            min(part.bounds_min[axis] for part in self.parts)
            for axis in range(3)
        )

    @property
    def bounds_max(self) -> Vec3:
        return tuple(
            max(part.bounds_max[axis] for part in self.parts)
            for axis in range(3)
        )

    def project_facts(self) -> dict[str, Any]:
        """Return persistence facts with no vertex, face, or texture blobs."""

        return {
            "schema": "ghostrigger.head_art_document",
            "version": 1,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "source_size_bytes": self.source_size_bytes,
            "source_format": self.source_format,
            "source_axis": self.source_axis,
            "imported_axis": self.imported_axis,
            "unit_scale_to_kotor": self.unit_scale_to_kotor,
            "source_to_imported": [
                list(row) for row in self.source_to_imported
            ],
            "flip_v": self.flip_v,
            "part_count": len(self.parts),
            "vertex_count": self.vertex_count,
            "face_count": self.face_count,
            "bounds_min": list(self.bounds_min),
            "bounds_max": list(self.bounds_max),
            "parts": [part.project_facts() for part in self.parts],
            "warnings": list(self.warnings),
            "structural_sha256": self.structural_sha256,
        }


FbxMeshLoader = Callable[..., Any]


def import_head_art(
    path: str | Path,
    *,
    source_axis: str = "auto",
    unit_scale_to_kotor: float = 1.0,
    flip_v: bool = True,
    fbx_loader: FbxMeshLoader | None = None,
    maximum_bytes: int = MAX_HEAD_ART_BYTES,
) -> tuple[HeadArtDocument, HeadArtValidationReport]:
    """Import an OBJ or FBX into deterministic KOTOR-oriented runtime parts."""

    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise HeadArtImportError(f"Custom head art does not exist: {source}")
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_HEAD_ART_EXTENSIONS:
        raise HeadArtImportError(
            "Custom head art must be OBJ or FBX; "
            f"received {source.suffix or 'a file with no extension'}"
        )
    try:
        size = source.stat().st_size
    except OSError as exc:
        raise HeadArtImportError(f"Unable to inspect custom head art: {source}") from exc
    if size <= 0:
        raise HeadArtImportError("Custom head art is empty")
    if size > int(maximum_bytes):
        raise HeadArtImportError(
            f"Custom head art exceeds the {int(maximum_bytes)} byte safety limit"
        )

    selected_axis = str(source_axis or "auto").strip().lower()
    if selected_axis == "auto":
        selected_axis = (
            "kotor_z_up"
            if suffix == ".obj"
            else "blender_xyz_to_kotor_xz_minus_y"
        )
    source_to_imported = source_axis_to_imported_matrix(
        selected_axis,
        unit_scale_to_kotor=unit_scale_to_kotor,
    )
    if suffix == ".obj":
        parts, warnings = _import_obj(
            source,
            source_to_imported=source_to_imported,
            flip_v=flip_v,
        )
    else:
        parts, warnings = _import_fbx(
            source,
            source_axis=selected_axis,
            unit_scale_to_kotor=unit_scale_to_kotor,
            fbx_loader=fbx_loader,
        )
    audited = tuple(_with_topology(part) for part in parts)
    document = HeadArtDocument(
        source_path=str(source),
        source_sha256=_sha256_file(source),
        source_size_bytes=size,
        source_format=suffix[1:].upper(),
        source_axis=selected_axis,
        imported_axis="kotor_object",
        unit_scale_to_kotor=float(unit_scale_to_kotor),
        source_to_imported=source_to_imported,
        flip_v=bool(flip_v),
        parts=audited,
        warnings=tuple(dict.fromkeys(str(row) for row in warnings if str(row))),
    )
    return document, validate_head_art_document(document)


def validate_head_art_document(
    document: HeadArtDocument,
) -> HeadArtValidationReport:
    """Return blocking topology errors and explicit review warnings."""

    issues: list[HeadArtValidationIssue] = []
    for part in document.parts:
        facts = part.topology
        if facts.nonfinite_value_count:
            issues.append(
                HeadArtValidationIssue(
                    "head.art.finite_channels",
                    "error",
                    f"{facts.nonfinite_value_count} non-finite channel value(s)",
                    part.part_id,
                )
            )
        if facts.invalid_face_count:
            issues.append(
                HeadArtValidationIssue(
                    "head.art.face_indices",
                    "error",
                    f"{facts.invalid_face_count} face(s) have invalid indices",
                    part.part_id,
                )
            )
        if facts.channel_length_error_count:
            issues.append(
                HeadArtValidationIssue(
                    "head.art.vertex_channels",
                    "error",
                    f"{facts.channel_length_error_count} vertex channel(s) "
                    "do not align with the imported vertex array",
                    part.part_id,
                )
            )
        if facts.degenerate_face_count:
            issues.append(
                HeadArtValidationIssue(
                    "head.art.degenerate_faces",
                    "error",
                    f"{facts.degenerate_face_count} degenerate face(s)",
                    part.part_id,
                )
            )
        if facts.non_manifold_edge_count:
            issues.append(
                HeadArtValidationIssue(
                    "head.art.non_manifold",
                    "error",
                    f"{facts.non_manifold_edge_count} non-manifold edge(s)",
                    part.part_id,
                )
            )
        warning_rows = (
            (
                facts.border_edge_count,
                "head.art.open_boundaries",
                "open boundary edge(s); the intended neck seam must be selected later",
            ),
            (
                facts.isolated_vertex_count,
                "head.art.isolated_vertices",
                "isolated vertex/vertices",
            ),
            (
                facts.inconsistent_winding_edge_count,
                "head.art.inconsistent_winding",
                "inconsistently wound edge(s)",
            ),
            (
                facts.duplicate_face_count,
                "head.art.duplicate_faces",
                "duplicate face(s)",
            ),
            (
                facts.branched_boundary_vertex_count,
                "head.art.branched_boundaries",
                "branched boundary vertex/vertices",
            ),
        )
        for count, check_id, label in warning_rows:
            if count:
                issues.append(
                    HeadArtValidationIssue(
                        check_id,
                        "warning",
                        f"{count} {label}",
                        part.part_id,
                    )
                )
        if not part.authored_uvs:
            issues.append(
                HeadArtValidationIssue(
                    "head.art.missing_uvs",
                    "warning",
                    "No authored UV channel; UV authoring is required before export",
                    part.part_id,
                )
            )
        if not part.authored_normals:
            issues.append(
                HeadArtValidationIssue(
                    "head.art.generated_normals",
                    "warning",
                    "Source normals were absent; preview normals were generated",
                    part.part_id,
                )
            )
    for warning in document.warnings:
        issues.append(
            HeadArtValidationIssue(
                "head.art.import_warning",
                "warning",
                warning,
            )
        )
    accepted = not any(row.severity == "error" for row in issues)
    return HeadArtValidationReport(
        accepted=accepted,
        issues=tuple(issues),
    )


def _import_obj(
    source: Path,
    *,
    source_to_imported: Mat4,
    flip_v: bool,
) -> tuple[tuple[HeadArtPart, ...], tuple[str, ...]]:
    try:
        from src.io.obj_room_document import load_obj_room_document
    except ImportError as exc:
        raise HeadArtImportError(
            "The Core IO OBJ reader is unavailable in this Ghost Studio build"
        ) from exc
    try:
        parsed = load_obj_room_document(source, flip_v=flip_v)
    except Exception as exc:
        raise HeadArtImportError(f"Unable to import OBJ head art: {exc}") from exc
    parts: list[HeadArtPart] = []
    for ordinal, surface in enumerate(parsed.surfaces):
        vertices = tuple(
            transform_point(source_to_imported, vertex)
            for vertex in surface.vertices
        )
        normals = tuple(
            transform_vector(source_to_imported, normal, normalize=True)
            for normal in surface.normals
        )
        parts.append(
            HeadArtPart(
                part_id=_part_id(ordinal, surface.name),
                name=str(surface.name or f"part_{ordinal}"),
                material_name=str(surface.material_name or ""),
                vertices=vertices,
                faces=tuple(
                    tuple(int(value) for value in face)
                    for face in surface.faces
                ),
                uvs=tuple(
                    tuple(float(value) for value in uv)
                    for uv in surface.uvs
                ),
                normals=normals,
                source_vertex_indices=tuple(range(len(vertices))),
                vertex_id_basis="obj_compacted_position_uv_normal_index",
                authored_uvs=bool(surface.uvs),
                authored_normals=bool(
                    parsed.normals_read and surface.normals
                ),
            )
        )
    return tuple(parts), tuple(parsed.warnings)


def _import_fbx(
    source: Path,
    *,
    source_axis: str,
    unit_scale_to_kotor: float,
    fbx_loader: FbxMeshLoader | None,
) -> tuple[tuple[HeadArtPart, ...], tuple[str, ...]]:
    loader = fbx_loader or _default_fbx_loader
    axis_conversion = str(source_axis or "")
    if axis_conversion in {
        "kotor_z_up",
        "z_up_right_handed",
        "identity",
    }:
        axis_conversion = "identity_z_up"
    try:
        model = loader(
            source,
            axis_conversion=axis_conversion,
        )
    except Exception as exc:
        raise HeadArtImportError(f"Unable to import FBX head art: {exc}") from exc
    if model is None:
        raise HeadArtImportError("FBX importer returned no model")
    nodes = list(model.all_nodes()) if hasattr(model, "all_nodes") else []
    parts: list[HeadArtPart] = []
    scale = float(unit_scale_to_kotor)
    for node in nodes:
        raw_vertices = list(getattr(node, "vertices", ()) or ())
        raw_faces = list(getattr(node, "faces", ()) or ())
        if not raw_vertices or not raw_faces:
            continue
        ordinal = len(parts)
        name = str(getattr(node, "name", "") or f"part_{ordinal}")
        vertices = tuple(
            tuple(float(component) * scale for component in vertex[:3])
            for vertex in raw_vertices
        )
        normals = tuple(
            _normalized(normal)
            for normal in list(getattr(node, "normals", ()) or ())
        )
        source_indices = tuple(
            int(value)
            for value in (
                getattr(node, "_gr_source_vertex_indices", ()) or ()
            )
        )
        if len(source_indices) != len(vertices):
            source_indices = tuple(range(len(vertices)))
        parts.append(
            HeadArtPart(
                part_id=_part_id(ordinal, name),
                name=name,
                material_name=str(getattr(node, "texture", "") or ""),
                vertices=vertices,
                faces=tuple(
                    tuple(int(value) for value in face[:3])
                    for face in raw_faces
                ),
                uvs=tuple(
                    tuple(float(value) for value in uv[:2])
                    for uv in list(getattr(node, "uvs", ()) or ())
                ),
                normals=normals,
                source_vertex_indices=source_indices,
                vertex_id_basis="fbx_source_control_point_index",
                authored_uvs=bool(getattr(node, "uvs", ()) or ()),
                authored_normals=bool(getattr(node, "normals", ()) or ()),
            )
        )
    warnings: list[str] = []
    metadata = getattr(model, "metadata", None)
    if isinstance(metadata, dict):
        external = dict(metadata.get("external_import") or {})
        actual_axis = str(external.get("axis_conversion") or "")
        if actual_axis and actual_axis != axis_conversion:
            warnings.append(
                f"FBX importer used axis conversion {actual_axis!r}, "
                f"not requested {axis_conversion!r}."
            )
    if not parts:
        raise HeadArtImportError("FBX contains no renderable triangle mesh parts")
    return tuple(parts), tuple(warnings)


def _default_fbx_loader(path: Path, **kwargs: Any) -> Any:
    try:
        from src.converters.blender_fbx_mesh_importer import (
            import_fbx_mesh_with_blender,
        )
    except ImportError as exc:
        raise HeadArtImportError(
            "The Blender-backed Core IO FBX reader is unavailable"
        ) from exc
    return import_fbx_mesh_with_blender(path, **kwargs)


def _with_topology(part: HeadArtPart) -> HeadArtPart:
    nonfinite = sum(
        1
        for channel in (part.vertices, part.uvs, part.normals)
        for row in channel
        for value in row
        if not math.isfinite(float(value))
    )
    invalid_faces = sum(
        1
        for face in part.faces
        if len(face) != 3
        or any(index < 0 or index >= len(part.vertices) for index in face)
    )
    channel_length_errors = sum(
        1
        for channel in (part.uvs, part.normals)
        if channel and len(channel) != len(part.vertices)
    )
    if nonfinite or invalid_faces or channel_length_errors:
        facts = HeadArtTopologyFacts(
            invalid_face_count=invalid_faces,
            nonfinite_value_count=nonfinite,
            channel_length_error_count=channel_length_errors,
            has_errors=True,
        )
    else:
        try:
            from src.core.geometry.mesh_topology import MeshTopology
        except ImportError as exc:
            raise HeadArtImportError(
                "The Core Math topology audit is unavailable in this Ghost Studio build"
            ) from exc
        topology = MeshTopology.build(
            part.vertices,
            part.faces,
            weld_tolerance=1.0e-6,
        )
        audit = topology.validate_manifold_state()
        facts = HeadArtTopologyFacts(
            invalid_face_count=len(audit.invalid_faces),
            non_manifold_edge_count=len(audit.non_manifold_edges),
            border_edge_count=len(audit.border_edges),
            boundary_chain_count=len(topology.geometric_boundary_chains),
            isolated_vertex_count=len(audit.isolated_vertices),
            degenerate_face_count=len(audit.degenerate_faces),
            inconsistent_winding_edge_count=len(
                audit.inconsistent_winding_edges
            ),
            duplicate_vertex_count=len(audit.duplicate_vertices),
            duplicate_face_count=len(audit.duplicate_faces),
            branched_boundary_vertex_count=len(audit.branched_boundaries),
            component_count=len(audit.components),
            nonfinite_value_count=0,
            channel_length_error_count=0,
            has_errors=bool(audit.has_errors),
            has_warnings=bool(audit.has_warnings),
        )
    return HeadArtPart(
        part_id=part.part_id,
        name=part.name,
        material_name=part.material_name,
        vertices=part.vertices,
        faces=part.faces,
        uvs=part.uvs,
        normals=part.normals,
        source_vertex_indices=part.source_vertex_indices,
        vertex_id_basis=part.vertex_id_basis,
        authored_uvs=part.authored_uvs,
        authored_normals=part.authored_normals,
        topology=facts,
    )


def _part_id(ordinal: int, name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", str(name or "")).strip("_")
    return f"part:{int(ordinal)}:{safe[:48] or 'mesh'}"


def _bounds(vertices: Iterable[Sequence[float]]) -> tuple[Vec3, Vec3]:
    rows = tuple(tuple(float(value) for value in row[:3]) for row in vertices)
    finite_rows = tuple(
        row for row in rows if all(math.isfinite(value) for value in row)
    )
    if not finite_rows:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    return (
        tuple(min(row[axis] for row in finite_rows) for axis in range(3)),
        tuple(max(row[axis] for row in finite_rows) for axis in range(3)),
    )


def _normalized(value: Sequence[float]) -> Vec3:
    row = tuple(float(component) for component in value[:3])
    length = math.sqrt(sum(component * component for component in row))
    if length <= 1.0e-12:
        return (0.0, 0.0, 1.0)
    return tuple(component / length for component in row)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _document_structural_sha256(document: HeadArtDocument) -> str:
    payload = {
        "source_sha256": document.source_sha256,
        "source_format": document.source_format,
        "source_axis": document.source_axis,
        "unit_scale_to_kotor": document.unit_scale_to_kotor,
        "source_to_imported": document.source_to_imported,
        "flip_v": document.flip_v,
        "parts": [part.project_facts() for part in document.parts],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "HeadArtDocument",
    "HeadArtImportError",
    "HeadArtPart",
    "HeadArtTopologyFacts",
    "HeadArtValidationIssue",
    "HeadArtValidationReport",
    "MAX_HEAD_ART_BYTES",
    "SUPPORTED_HEAD_ART_EXTENSIONS",
    "import_head_art",
    "validate_head_art_document",
]
