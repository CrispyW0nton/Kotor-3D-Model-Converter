"""Vanilla KOTOR head-component inventory and compatibility contracts.

The Custom Head Builder can reuse stock rendered payloads without replacing
the carrier donor's native DAG.  This module performs the read-only inspection
needed to describe face, eye, eyelid/lash, hair, mouth, and accessory payloads.
It deliberately does not resolve game files, mutate models, render previews,
or import Qt.

Compatibility is capability-driven.  A resource is not considered a modular
head merely because its name sounds like one, and a full-body alien is never
silently treated as a player-head donor.  Ithorians are an explicit unsupported
body-replacement family for this workflow.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field, replace
from enum import Enum
import hashlib
import json
from typing import Any, Iterable

from src.core.characters.head_donor_snapshot import (
    HeadDonorSnapshot,
    compare_head_donor_contract,
)
from src.math.head_component_transform import (
    build_head_component_rebase,
    rebase_head_component_channels,
)


HEAD_COMPONENT_CATALOG_SCHEMA = "ghostrigger.head_component_inventory"
HEAD_COMPONENT_CATALOG_VERSION = 1


class HeadComponentRole(str, Enum):
    FACE = "face"
    EYES = "eyes"
    EYELASHES = "eyelashes"
    HAIR = "hair"
    MOUTH = "mouth"
    ACCESSORY = "accessory"
    OTHER = "other"


class HeadComponentSourceKind(str, Enum):
    STANDARD_MODULAR_HEAD = "standard_modular_head"
    ALIEN_MODULAR_HEAD = "alien_modular_head"
    FULL_BODY_ALIEN = "full_body_alien"
    UNSUPPORTED_ITHORIAN = "unsupported_ithorian"
    NON_HEAD_MODEL = "non_head_model"


@dataclass(frozen=True, slots=True)
class HeadComponentNode:
    ordinal: int
    name: str
    parent_name: str
    flags: int
    is_skin: bool
    is_dangly: bool
    render: bool
    vertex_count: int
    face_count: int
    texture: str
    palette_names: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class HeadComponentGroup:
    role: HeadComponentRole
    nodes: tuple[HeadComponentNode, ...]

    @property
    def vertex_count(self) -> int:
        return sum(row.vertex_count for row in self.nodes)

    @property
    def face_count(self) -> int:
        return sum(row.face_count for row in self.nodes)

    @property
    def textures(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                row.texture
                for row in self.nodes
                if row.texture.casefold() not in {"", "null", "none"}
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "nodes": [row.to_dict() for row in self.nodes],
            "vertex_count": self.vertex_count,
            "face_count": self.face_count,
            "textures": list(self.textures),
        }


@dataclass(frozen=True, slots=True)
class HeadComponentInventory:
    game: str
    resref: str
    model_name: str
    supermodel: str
    source_kind: HeadComponentSourceKind
    node_count: int
    attachment_target_name: str
    facial_control_names: tuple[str, ...]
    groups: tuple[HeadComponentGroup, ...]
    compatibility_signature: str
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def accepted_as_component_source(self) -> bool:
        return (
            self.source_kind
            in {
                HeadComponentSourceKind.STANDARD_MODULAR_HEAD,
                HeadComponentSourceKind.ALIEN_MODULAR_HEAD,
            }
            and bool(self.group(HeadComponentRole.FACE).nodes)
            and not self.errors
        )

    def group(self, role: HeadComponentRole | str) -> HeadComponentGroup:
        wanted = HeadComponentRole(role)
        for group in self.groups:
            if group.role is wanted:
                return group
        return HeadComponentGroup(wanted, ())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": HEAD_COMPONENT_CATALOG_SCHEMA,
            "version": HEAD_COMPONENT_CATALOG_VERSION,
            "game": self.game,
            "resref": self.resref,
            "model_name": self.model_name,
            "supermodel": self.supermodel,
            "source_kind": self.source_kind.value,
            "accepted_as_component_source": self.accepted_as_component_source,
            "node_count": self.node_count,
            "attachment_target_name": self.attachment_target_name,
            "facial_control_names": list(self.facial_control_names),
            "groups": [row.to_dict() for row in self.groups],
            "compatibility_signature": self.compatibility_signature,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


@dataclass(frozen=True, slots=True)
class HeadComponentCompatibilityIssue:
    check_id: str
    severity: str
    message: str
    facts: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class HeadComponentCompatibilityReport:
    role: HeadComponentRole
    carrier_resref: str
    source_resref: str
    issues: tuple[HeadComponentCompatibilityIssue, ...] = ()

    @property
    def compatible(self) -> bool:
        return not any(row.severity == "error" for row in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "carrier_resref": self.carrier_resref,
            "source_resref": self.source_resref,
            "compatible": self.compatible,
            "issues": [row.to_dict() for row in self.issues],
        }


@dataclass(frozen=True, slots=True)
class HeadComponentAssemblyReport:
    carrier_resref: str
    source_resrefs: dict[str, str]
    target_node_ordinals: tuple[int, ...]
    face_node_ordinal: int
    component_payload_sha256: str
    compatibility_reports: tuple[HeadComponentCompatibilityReport, ...]
    blocking_difference_paths: tuple[str, ...] = ()
    allowed_difference_paths: tuple[str, ...] = ()

    @property
    def accepted(self) -> bool:
        return (
            self.face_node_ordinal >= 0
            and not self.blocking_difference_paths
            and all(row.compatible for row in self.compatibility_reports)
        )

    @property
    def mutable_node_ordinal(self) -> int:
        """Compatibility with the existing texture/material result contract."""

        return self.face_node_ordinal

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ghostrigger.head_component_assembly",
            "version": 1,
            "accepted": self.accepted,
            "carrier_resref": self.carrier_resref,
            "source_resrefs": dict(self.source_resrefs),
            "target_node_ordinals": list(self.target_node_ordinals),
            "face_node_ordinal": self.face_node_ordinal,
            "component_payload_sha256": self.component_payload_sha256,
            "compatibility_reports": [
                row.to_dict() for row in self.compatibility_reports
            ],
            "blocking_difference_paths": list(
                self.blocking_difference_paths
            ),
            "allowed_difference_paths": list(
                self.allowed_difference_paths
            ),
        }


@dataclass(frozen=True, slots=True)
class HeadComponentAssemblyResult:
    model: Any = field(repr=False, compare=False)
    donor_snapshot: HeadDonorSnapshot
    report: HeadComponentAssemblyReport


class HeadComponentAssemblyError(RuntimeError):
    """Raised when a recipe cannot preserve the selected carrier DAG."""


def inspect_head_component_inventory(
    model: Any,
    *,
    game: str,
    resref: str,
) -> HeadComponentInventory:
    """Describe stock component payloads without changing the loaded model."""

    nodes = _model_nodes(model)
    rows = tuple(
        _component_node(node, ordinal)
        for ordinal, node in enumerate(nodes)
        if _is_render_payload(node)
    )
    node_names = {
        str(getattr(node, "name", "") or "").casefold()
        for node in nodes
    }
    facial_controls = tuple(
        sorted(
            name
            for name in node_names
            if name.startswith("f_") or name == "talkdummy"
        )
    )
    attachment = "neck_g" if "neck_g" in node_names else ""
    has_body_skeleton = bool(
        node_names
        & {
            "pelvis_g",
            "lthigh_g",
            "rthigh_g",
            "lshin_g",
            "rshin_g",
            "lhand_g",
            "rhand_g",
            "headhook",
        }
    )
    clean_resref = str(resref or "").strip()
    lowered_identity = " ".join(
        (
            clean_resref,
            str(getattr(model, "name", "") or ""),
            str(getattr(model, "supermodel", "") or ""),
        )
    ).casefold()
    face_nodes = tuple(row for row in rows if _is_face_payload(row))
    groups = tuple(
        HeadComponentGroup(role, _nodes_for_role(rows, role, face_nodes))
        for role in HeadComponentRole
    )
    has_head_contract = bool(
        attachment
        and facial_controls
        and face_nodes
        and not has_body_skeleton
    )
    if "ithor" in lowered_identity:
        source_kind = HeadComponentSourceKind.UNSUPPORTED_ITHORIAN
    elif has_head_contract:
        source_kind = (
            HeadComponentSourceKind.ALIEN_MODULAR_HEAD
            if _looks_alien_modular(lowered_identity)
            else HeadComponentSourceKind.STANDARD_MODULAR_HEAD
        )
    elif face_nodes and has_body_skeleton:
        source_kind = HeadComponentSourceKind.FULL_BODY_ALIEN
    else:
        source_kind = HeadComponentSourceKind.NON_HEAD_MODEL

    warnings: list[str] = []
    errors: list[str] = []
    if source_kind is HeadComponentSourceKind.UNSUPPORTED_ITHORIAN:
        errors.append(
            "Ithorian geometry is a full-body replacement and is excluded "
            "from player-body Head Builder recipes."
        )
    elif source_kind is HeadComponentSourceKind.FULL_BODY_ALIEN:
        warnings.append(
            "This alien resource is a full-body model. Its head requires an "
            "explicit extraction and neck-retarget workflow before it can be "
            "used as a modular player head."
        )
    elif source_kind is HeadComponentSourceKind.NON_HEAD_MODEL:
        errors.append(
            "The resource does not expose a modular neck/facial/head payload contract."
        )
    if not _group_from(groups, HeadComponentRole.EYES).nodes:
        warnings.append("No separately swappable eye meshes were detected.")
    if not _group_from(groups, HeadComponentRole.EYELASHES).nodes:
        warnings.append("No separately swappable eyelid/lash meshes were detected.")
    if not _group_from(groups, HeadComponentRole.HAIR).nodes:
        warnings.append("No separately swappable hair payload was detected.")

    signature_payload = {
        "game": str(game or "").upper(),
        "supermodel": str(getattr(model, "supermodel", "") or "").casefold(),
        "attachment": attachment,
        "facial_controls": list(facial_controls),
        "source_kind": source_kind.value,
    }
    signature = hashlib.sha256(
        json.dumps(
            signature_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return HeadComponentInventory(
        game=str(game or "").upper(),
        resref=clean_resref,
        model_name=str(getattr(model, "name", "") or ""),
        supermodel=str(getattr(model, "supermodel", "") or ""),
        source_kind=source_kind,
        node_count=len(nodes),
        attachment_target_name=attachment,
        facial_control_names=facial_controls,
        groups=groups,
        compatibility_signature=signature,
        warnings=tuple(warnings),
        errors=tuple(errors),
    )


def compare_head_component_compatibility(
    carrier: HeadComponentInventory,
    source: HeadComponentInventory,
    role: HeadComponentRole | str,
) -> HeadComponentCompatibilityReport:
    """Check whether ``source`` can fill one existing carrier payload slot."""

    selected_role = HeadComponentRole(role)
    issues: list[HeadComponentCompatibilityIssue] = []

    def issue(
        check_id: str,
        severity: str,
        message: str,
        **facts: Any,
    ) -> None:
        issues.append(
            HeadComponentCompatibilityIssue(
                check_id=check_id,
                severity=severity,
                message=message,
                facts=dict(facts),
            )
        )

    if carrier.game.casefold() != source.game.casefold():
        issue(
            "head.components.game",
            "error",
            "K1 and K2 component payloads cannot be mixed.",
            carrier_game=carrier.game,
            source_game=source.game,
        )
    if not carrier.accepted_as_component_source:
        issue(
            "head.components.carrier",
            "error",
            "The selected carrier is not a verified modular-head component source.",
            carrier_kind=carrier.source_kind.value,
        )
    if not source.accepted_as_component_source:
        issue(
            "head.components.source",
            "error",
            "The selected source is not a verified modular-head component source.",
            source_kind=source.source_kind.value,
        )
    source_group = source.group(selected_role)
    carrier_group = carrier.group(selected_role)
    if not source_group.nodes:
        issue(
            "head.components.source_slot",
            "error",
            f"The source has no {selected_role.value} payload.",
        )
    if not carrier_group.nodes:
        issue(
            "head.components.carrier_slot",
            "error",
            f"The carrier has no existing {selected_role.value} payload slot.",
        )
    if (
        selected_role is HeadComponentRole.HAIR
        and len(source_group.nodes) > len(carrier_group.nodes)
    ):
        issue(
            "head.components.hair_slots",
            "error",
            "The carrier does not have enough existing hair payload nodes to "
            "preserve its native DAG.",
            carrier_slots=len(carrier_group.nodes),
            source_nodes=len(source_group.nodes),
        )
    if (
        selected_role
        in {
            HeadComponentRole.FACE,
            HeadComponentRole.EYES,
            HeadComponentRole.EYELASHES,
            HeadComponentRole.MOUTH,
        }
        and carrier.supermodel.casefold() != source.supermodel.casefold()
    ):
        issue(
            "head.components.supermodel_family",
            "error",
            "Facial components must remain inside one supermodel family.",
            carrier_supermodel=carrier.supermodel,
            source_supermodel=source.supermodel,
        )
    if (
        selected_role is HeadComponentRole.FACE
        and carrier.facial_control_names != source.facial_control_names
    ):
        issue(
            "head.components.facial_controls",
            "error",
            "The face source does not expose the carrier's exact facial-control set.",
            carrier_controls=list(carrier.facial_control_names),
            source_controls=list(source.facial_control_names),
        )
    if (
        carrier.source_kind is HeadComponentSourceKind.ALIEN_MODULAR_HEAD
        or source.source_kind is HeadComponentSourceKind.ALIEN_MODULAR_HEAD
    ) and carrier.compatibility_signature != source.compatibility_signature:
        issue(
            "head.components.alien_family",
            "error",
            "Alien components must stay within the same verified modular alien family.",
            carrier_kind=carrier.source_kind.value,
            source_kind=source.source_kind.value,
        )
    for row in source_group.nodes:
        if selected_role in {
            HeadComponentRole.EYES,
            HeadComponentRole.EYELASHES,
            HeadComponentRole.HAIR,
        } and row.parent_name.casefold() != "head_g":
            issue(
                "head.components.parent_space",
                "error",
                "The component is not stored in the carrier head_g local space.",
                node=row.name,
                parent=row.parent_name,
            )
    if not any(row.severity == "error" for row in issues):
        issue(
            "head.components.preview_required",
            "warning",
            "Geometry is structurally swappable, but eye fit, hair clipping, "
            "neck seam, and animation still require editor and retail proof.",
        )
    return HeadComponentCompatibilityReport(
        role=selected_role,
        carrier_resref=carrier.resref,
        source_resref=source.resref,
        issues=tuple(issues),
    )


def assemble_head_components(
    *,
    carrier_model: Any,
    carrier_snapshot: HeadDonorSnapshot,
    carrier_inventory: HeadComponentInventory,
    sources: dict[
        HeadComponentRole | str,
        tuple[Any, HeadComponentInventory],
    ],
) -> HeadComponentAssemblyResult:
    """Replace existing carrier render payloads with compatible stock parts.

    Node identity, name, flags, parent/child order, transforms, palette order,
    bind arrays, and raw retail bounds remain carrier-owned.  Face/hair skin
    influences are remapped by bone name into the carrier palette.
    """

    if carrier_model is None:
        raise HeadComponentAssemblyError("No carrier model is loaded")
    if not isinstance(carrier_snapshot, HeadDonorSnapshot):
        raise TypeError("carrier_snapshot must be HeadDonorSnapshot")
    if not isinstance(carrier_inventory, HeadComponentInventory):
        raise TypeError("carrier_inventory must be HeadComponentInventory")
    if (
        carrier_inventory.resref.casefold()
        != carrier_snapshot.resref.casefold()
    ):
        raise HeadComponentAssemblyError(
            "Carrier inventory belongs to a different donor snapshot"
        )
    initial = compare_head_donor_contract(carrier_snapshot, carrier_model)
    if initial.blocking or initial.allowed_payload_changes:
        raise HeadComponentAssemblyError(
            "Stock component assembly requires the pristine selected carrier"
        )

    normalized_sources: dict[
        HeadComponentRole,
        tuple[Any, HeadComponentInventory],
    ] = {}
    for raw_role, value in dict(sources or {}).items():
        role = HeadComponentRole(raw_role)
        if role in {
            HeadComponentRole.ACCESSORY,
            HeadComponentRole.OTHER,
        }:
            raise HeadComponentAssemblyError(
                f"Unsupported stock component role: {role.value}"
            )
        try:
            source_model, source_inventory = value
        except Exception as exc:
            raise HeadComponentAssemblyError(
                f"Invalid source payload for {role.value}"
            ) from exc
        if not isinstance(source_inventory, HeadComponentInventory):
            raise TypeError(
                f"{role.value} source inventory is not HeadComponentInventory"
            )
        normalized_sources[role] = (source_model, source_inventory)
    if HeadComponentRole.FACE not in normalized_sources:
        normalized_sources[HeadComponentRole.FACE] = (
            carrier_model,
            carrier_inventory,
        )
    face_source = normalized_sources[HeadComponentRole.FACE]
    normalized_sources.setdefault(HeadComponentRole.MOUTH, face_source)
    for role in (
        HeadComponentRole.EYES,
        HeadComponentRole.EYELASHES,
        HeadComponentRole.HAIR,
    ):
        normalized_sources.setdefault(
            role,
            (carrier_model, carrier_inventory),
        )

    reports = tuple(
        compare_head_component_compatibility(
            carrier_inventory,
            source_inventory,
            role,
        )
        for role, (_source_model, source_inventory)
        in normalized_sources.items()
    )
    blocking_reports = [
        report for report in reports if not report.compatible
    ]
    if blocking_reports:
        messages = [
            issue.message
            for report in blocking_reports
            for issue in report.issues
            if issue.severity == "error"
        ]
        raise HeadComponentAssemblyError(
            "Stock component recipe is incompatible: "
            + "; ".join(messages[:6])
        )

    candidate = deepcopy(carrier_model)
    candidate_nodes = _model_nodes(candidate)
    changed_ordinals: list[int] = []
    source_resrefs: dict[str, str] = {}
    for role in (
        HeadComponentRole.FACE,
        HeadComponentRole.MOUTH,
        HeadComponentRole.EYES,
        HeadComponentRole.EYELASHES,
        HeadComponentRole.HAIR,
    ):
        source_model, source_inventory = normalized_sources[role]
        source_resrefs[role.value] = source_inventory.resref
        source_nodes = _model_nodes(source_model)
        target_group = carrier_inventory.group(role)
        source_group = source_inventory.group(role)
        pairs, unused_targets = _component_pairs(
            role,
            target_group.nodes,
            source_group.nodes,
        )
        for target_row, source_row in pairs:
            target_node = candidate_nodes[target_row.ordinal]
            source_node = source_nodes[source_row.ordinal]
            _copy_component_payload(
                target_node,
                source_node,
                role=role,
            )
            changed_ordinals.append(target_row.ordinal)
        for target_row in unused_targets:
            _clear_component_payload(candidate_nodes[target_row.ordinal])
            changed_ordinals.append(target_row.ordinal)

    allowed_ordinals = tuple(sorted(set(changed_ordinals)))
    compatibility = deepcopy(dict(carrier_snapshot.compatibility or {}))
    compatibility["component_payload_node_ordinals"] = list(
        allowed_ordinals
    )
    compatibility["component_source_resrefs"] = dict(source_resrefs)
    derived_snapshot = replace(
        carrier_snapshot,
        compatibility=compatibility,
    )
    diff = compare_head_donor_contract(derived_snapshot, candidate)
    blocking = tuple(row.path for row in diff.blocking)
    if blocking:
        raise HeadComponentAssemblyError(
            "Component assembly changed the carrier DAG or immutable bind "
            "contract: " + ", ".join(blocking[:8])
        )
    face_group = carrier_inventory.group(HeadComponentRole.FACE)
    face_ordinal = (
        face_group.nodes[0].ordinal if len(face_group.nodes) == 1 else -1
    )
    payload = {
        "carrier": carrier_snapshot.structural_sha256,
        "sources": source_resrefs,
        "targets": [
            _component_payload_facts(candidate_nodes[ordinal], ordinal)
            for ordinal in allowed_ordinals
        ],
    }
    payload_sha = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    report = HeadComponentAssemblyReport(
        carrier_resref=carrier_inventory.resref,
        source_resrefs=source_resrefs,
        target_node_ordinals=allowed_ordinals,
        face_node_ordinal=face_ordinal,
        component_payload_sha256=payload_sha,
        compatibility_reports=reports,
        blocking_difference_paths=blocking,
        allowed_difference_paths=tuple(
            row.path for row in diff.allowed_payload_changes
        ),
    )
    metadata = getattr(candidate, "metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
        setattr(candidate, "metadata", metadata)
    metadata["head_builder_components"] = report.to_dict()
    return HeadComponentAssemblyResult(
        model=candidate,
        donor_snapshot=derived_snapshot,
        report=report,
    )


_MESH_PAYLOAD_FIELDS = (
    "vertices",
    "normals",
    "tangents",
    "uvs",
    "uvs_lm",
    "uvs_2",
    "uvs_3",
    "faces",
    "face_mats",
    "face_uvs",
    "texture",
    "lightmap",
    "bump_map",
    "diffuse",
    "ambient",
    "specular",
    "shininess",
    "alpha",
    "has_shadow",
    "selfillum",
    "transparency_hint",
    "has_lightmap",
    "beaming",
    "background_geometry",
    "rotate_texture",
    "animate_uv",
    "uv_dir_x",
    "uv_dir_y",
    "uv_jitter",
    "uv_jitter_speed",
    "tex_count",
    "texture_names",
    "txi_blending",
    "txi_cube",
    "txi_proceduretype",
    "txi_numx",
    "txi_numy",
    "txi_fps",
    "txi_envmaptexture",
    "txi_bumpmaptexture",
    "txi_bumpmapscaling",
    "txi_rotate",
    "txi_loop",
    "txi_clamp_s",
    "txi_clamp_t",
    "txi_wateralpha",
    "txi_decal",
    "txi_isbumpmap",
    "txi_islightmap",
    "txi_specularcolour",
    "txi_alpha_test",
    "dirt_enabled",
    "dirt_texture",
    "dirt_coord_space",
    "hide_in_holograms",
    "mesh_average_point",
    "mesh_unknown0",
)


def _copy_component_payload(
    target: Any,
    source: Any,
    *,
    role: HeadComponentRole,
) -> None:
    if bool(getattr(target, "is_skin", False)) != bool(
        getattr(source, "is_skin", False)
    ):
        raise HeadComponentAssemblyError(
            f"{role.value} source and carrier slots disagree on skin type"
        )
    if int(getattr(target, "vertex_space", 0)) != int(
        getattr(source, "vertex_space", 0)
    ):
        raise HeadComponentAssemblyError(
            f"{role.value} source and carrier use different vertex spaces"
        )
    rebase = build_head_component_rebase(
        source,
        target,
        skin_translation_only=bool(getattr(source, "is_skin", False)),
    )
    for field_name in _MESH_PAYLOAD_FIELDS:
        if hasattr(source, field_name) and hasattr(target, field_name):
            setattr(target, field_name, deepcopy(getattr(source, field_name)))
    (
        rebased_vertices,
        rebased_normals,
        rebased_tangents,
    ) = rebase_head_component_channels(
        vertices=list(getattr(source, "vertices", ()) or ()),
        normals=list(getattr(source, "normals", ()) or ()),
        tangents=list(getattr(source, "tangents", ()) or ()),
        rebase=rebase,
    )
    target.vertices = list(rebased_vertices)
    target.normals = list(rebased_normals)
    target.tangents = list(rebased_tangents)
    if bool(getattr(target, "is_skin", False)):
        _remap_skin_payload(target, source)
    if bool(getattr(target, "is_dangly", False)):
        # Stock mesh mixing establishes a rigid, reviewable baseline.  Native
        # dangly constraints are topology/order-specific and are re-authored
        # only in the separate opt-in physics phase.
        target.dangly_constraints = [0.0] * len(target.vertices)


def _remap_skin_payload(target: Any, source: Any) -> None:
    try:
        from src.core.geometry.model_data import BoneWeight, VertexSkinData
    except Exception as exc:  # pragma: no cover - packaging failure
        raise HeadComponentAssemblyError(
            "The canonical model-data payload is unavailable"
        ) from exc
    source_palette = [
        str(value) for value in list(getattr(source, "bone_map", ()) or ())
    ]
    target_palette = [
        str(value) for value in list(getattr(target, "bone_map", ()) or ())
    ]
    target_by_name: dict[str, int] = {}
    for index, name in enumerate(target_palette):
        key = name.casefold()
        if key and key not in target_by_name:
            target_by_name[key] = index
    rows: list[Any] = []
    for source_row in list(getattr(source, "skin_data", ()) or ()):
        influences: list[Any] = []
        for influence in list(
            getattr(source_row, "influences", ()) or ()
        ):
            source_slot = int(getattr(influence, "bone_index", -1))
            if not 0 <= source_slot < len(source_palette):
                raise HeadComponentAssemblyError(
                    "Source component contains an out-of-range skin palette slot"
                )
            bone_name = source_palette[source_slot]
            target_slot = target_by_name.get(bone_name.casefold())
            if target_slot is None:
                raise HeadComponentAssemblyError(
                    f"Carrier palette has no {bone_name!r} influence required "
                    "by the source component"
                )
            influences.append(
                BoneWeight(
                    target_slot,
                    float(getattr(influence, "weight", 0.0)),
                )
            )
        row = VertexSkinData(influences)
        row.normalize()
        rows.append(row)
    target.skin_data = rows
    target.bone_weights = [
        [float(influence.weight) for influence in row.influences]
        for row in rows
    ]
    target.bone_indices = [
        [int(influence.bone_index) for influence in row.influences]
        for row in rows
    ]


def _clear_component_payload(node: Any) -> None:
    for field_name in (
        "vertices",
        "normals",
        "tangents",
        "uvs",
        "uvs_lm",
        "uvs_2",
        "uvs_3",
        "faces",
        "face_mats",
        "face_uvs",
        "skin_data",
        "bone_weights",
        "bone_indices",
        "dangly_constraints",
    ):
        if hasattr(node, field_name):
            setattr(node, field_name, [])
    if hasattr(node, "texture"):
        node.texture = "NULL"
    if hasattr(node, "texture_names"):
        node.texture_names = ["NULL"]
    if hasattr(node, "tex_count"):
        node.tex_count = 1


def _component_pairs(
    role: HeadComponentRole,
    targets: tuple[HeadComponentNode, ...],
    sources: tuple[HeadComponentNode, ...],
) -> tuple[
    tuple[tuple[HeadComponentNode, HeadComponentNode], ...],
    tuple[HeadComponentNode, ...],
]:
    if not targets or not sources:
        raise HeadComponentAssemblyError(
            f"Both carrier and source require a {role.value} payload"
        )
    if role in {HeadComponentRole.FACE}:
        if len(targets) != 1 or len(sources) != 1:
            raise HeadComponentAssemblyError(
                "Face assembly requires exactly one carrier and source skin"
            )
        return ((targets[0], sources[0]),), ()
    if role in {HeadComponentRole.EYES, HeadComponentRole.EYELASHES}:
        target_by_side = {_side_key(row.name): row for row in targets}
        source_by_side = {_side_key(row.name): row for row in sources}
        if set(target_by_side) != {"left", "right"} or set(
            source_by_side
        ) != {"left", "right"}:
            raise HeadComponentAssemblyError(
                f"{role.value} assembly requires one left and one right node"
            )
        return (
            tuple(
                (target_by_side[side], source_by_side[side])
                for side in ("left", "right")
            ),
            (),
        )
    if role is HeadComponentRole.MOUTH:
        target_by_kind = {_mouth_key(row.name): row for row in targets}
        source_by_kind = {_mouth_key(row.name): row for row in sources}
        common = [
            key
            for key in ("upper", "lower", "tongue")
            if key in target_by_kind and key in source_by_kind
        ]
        if "upper" not in common or "lower" not in common:
            raise HeadComponentAssemblyError(
                "Mouth assembly requires upper and lower carrier/source nodes"
            )
        pairs = tuple(
            (target_by_kind[key], source_by_kind[key]) for key in common
        )
        unused = tuple(
            row for key, row in target_by_kind.items() if key not in common
        )
        return pairs, unused
    if len(sources) > len(targets):
        raise HeadComponentAssemblyError(
            "The carrier has fewer existing payload nodes than the source"
        )
    return (
        tuple(zip(targets, sources)),
        tuple(targets[len(sources) :]),
    )


def _side_key(name: str) -> str:
    text = str(name or "").casefold()
    if text.startswith(("eyel", "l_eye")):
        return "left"
    if text.startswith(("eyer", "r_eye")):
        return "right"
    return ""


def _mouth_key(name: str) -> str:
    text = str(name or "").casefold()
    if "tong" in text:
        return "tongue"
    if "teeth" in text or "tooth" in text:
        if text.endswith(("u", "upper")):
            return "upper"
        if text.endswith(("l", "lower")):
            return "lower"
    if "upper" in text or "up" in text or text.endswith(("ua", "upr")):
        return "upper"
    if "lower" in text or "low" in text or text.endswith(("la", "lwr")):
        return "lower"
    return text


def _component_payload_facts(node: Any, ordinal: int) -> dict[str, Any]:
    return {
        "ordinal": int(ordinal),
        "name": str(getattr(node, "name", "") or ""),
        "vertices": [
            [float(value) for value in row]
            for row in list(getattr(node, "vertices", ()) or ())
        ],
        "faces": [
            [int(value) for value in row]
            for row in list(getattr(node, "faces", ()) or ())
        ],
        "uvs": [
            [float(value) for value in row]
            for row in list(getattr(node, "uvs", ()) or ())
        ],
        "texture": str(getattr(node, "texture", "") or ""),
        "skin": [
            [
                [
                    int(getattr(influence, "bone_index", -1)),
                    float(getattr(influence, "weight", 0.0)),
                ]
                for influence in list(
                    getattr(row, "influences", ()) or ()
                )
            ]
            for row in list(getattr(node, "skin_data", ()) or ())
        ],
    }


def _component_node(node: Any, ordinal: int) -> HeadComponentNode:
    return HeadComponentNode(
        ordinal=ordinal,
        name=str(getattr(node, "name", "") or ""),
        parent_name=str(
            getattr(getattr(node, "parent", None), "name", "") or ""
        ),
        flags=int(getattr(node, "flags", 0) or 0),
        is_skin=bool(getattr(node, "is_skin", False)),
        is_dangly=bool(getattr(node, "is_dangly", False)),
        render=bool(getattr(node, "render", True)),
        vertex_count=len(list(getattr(node, "vertices", ()) or ())),
        face_count=len(list(getattr(node, "faces", ()) or ())),
        texture=str(getattr(node, "texture", "") or ""),
        palette_names=tuple(
            str(value)
            for value in list(getattr(node, "bone_map", ()) or ())
        ),
    )


def _nodes_for_role(
    rows: Iterable[HeadComponentNode],
    role: HeadComponentRole,
    face_nodes: tuple[HeadComponentNode, ...],
) -> tuple[HeadComponentNode, ...]:
    values = tuple(rows)
    face_ordinals = {row.ordinal for row in face_nodes}
    classified: dict[int, HeadComponentRole] = {}
    for row in values:
        if row.ordinal in face_ordinals:
            classified[row.ordinal] = HeadComponentRole.FACE
            continue
        name = row.name.casefold()
        if "lid" in name or "lash" in name:
            classified[row.ordinal] = HeadComponentRole.EYELASHES
        elif _is_eye_name(name):
            classified[row.ordinal] = HeadComponentRole.EYES
        elif "teeth" in name or "tooth" in name or "tong" in name:
            classified[row.ordinal] = HeadComponentRole.MOUTH
        elif (
            "hair" in name
            or "strand" in name
            or "bang" in name
            or "ponytail" in name
            or row.is_dangly
        ):
            classified[row.ordinal] = HeadComponentRole.HAIR
        elif row.parent_name.casefold() == "head_g":
            classified[row.ordinal] = HeadComponentRole.ACCESSORY
        else:
            classified[row.ordinal] = HeadComponentRole.OTHER
    return tuple(
        row for row in values if classified.get(row.ordinal) is role
    )


def _is_face_payload(row: HeadComponentNode) -> bool:
    if not row.is_skin:
        return False
    name = row.name.casefold()
    palette = {value.casefold() for value in row.palette_names}
    facial_influences = {
        "head_g",
        "f_jaw_g",
        "f_um_g",
        "f_lmc_g",
        "f_rmc_g",
        "neck_g",
    }
    return (
        name == "head"
        or name.startswith("head0")
        or (
            row.parent_name
            and len(palette & facial_influences) >= 3
        )
    )


def _is_eye_name(name: str) -> bool:
    lowered = str(name or "").casefold()
    if "lid" in lowered or "lash" in lowered:
        return False
    return (
        lowered in {"eyela", "eyera", "eye_l", "eye_r", "l_eye", "r_eye"}
        or lowered.startswith(("eyel", "eyer"))
    )


def _is_render_payload(node: Any) -> bool:
    return bool(
        (getattr(node, "is_mesh", False) or getattr(node, "is_skin", False))
        and getattr(node, "render", True)
        and list(getattr(node, "vertices", ()) or ())
        and list(getattr(node, "faces", ()) or ())
    )


def _looks_alien_modular(identity: str) -> bool:
    return any(
        token in identity
        for token in (
            "twilek",
            "twi'lek",
            "rodian",
            "duros",
            "bith",
            "trandoshan",
            "selkath",
            "alien",
        )
    )


def _group_from(
    groups: tuple[HeadComponentGroup, ...],
    role: HeadComponentRole,
) -> HeadComponentGroup:
    for group in groups:
        if group.role is role:
            return group
    return HeadComponentGroup(role, ())


def _model_nodes(model: Any) -> list[Any]:
    iterator = getattr(model, "all_nodes", None)
    if callable(iterator):
        return list(iterator())
    root = getattr(model, "root_node", None)
    if root is None:
        return []
    rows: list[Any] = []

    def walk(node: Any) -> None:
        rows.append(node)
        for child in list(getattr(node, "children", ()) or ()):
            walk(child)

    walk(root)
    return rows


__all__ = [
    "HEAD_COMPONENT_CATALOG_SCHEMA",
    "HEAD_COMPONENT_CATALOG_VERSION",
    "HeadComponentAssemblyError",
    "HeadComponentAssemblyReport",
    "HeadComponentAssemblyResult",
    "HeadComponentCompatibilityIssue",
    "HeadComponentCompatibilityReport",
    "HeadComponentGroup",
    "HeadComponentInventory",
    "HeadComponentNode",
    "HeadComponentRole",
    "HeadComponentSourceKind",
    "assemble_head_components",
    "compare_head_component_compatibility",
    "inspect_head_component_inventory",
]
