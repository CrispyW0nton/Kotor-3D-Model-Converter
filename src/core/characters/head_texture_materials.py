"""Donor-safe UV, material, and texture application for Head Builder."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any

from src.core.characters.head_donor_snapshot import (
    HeadDonorSnapshot,
    compare_head_donor_contract,
)
from src.core.characters.head_geometry_transplant import (
    HeadGeometryTransplantResult,
)
from src.io.head_texture_asset import (
    HeadTextureAsset,
    HeadTextureOutputPolicy,
)
from src.math.head_uv import (
    HeadUvOrientationContract,
    head_uvs_sha256,
)


class HeadTextureMaterialError(RuntimeError):
    """Raised when material authoring would diverge from saved/output truth."""


@dataclass(frozen=True, slots=True)
class HeadTextureMaterialReport:
    mutable_node_ordinal: int
    mutable_node_name: str
    texture_resref: str
    source_texture_sha256: str
    source_decoded_rgba_sha256: str
    imported_uv_sha256: str
    serialized_uv_sha256: str
    preview_uv_sha256: str
    preview_matches_serialized: bool
    source_v_flip_applied: bool
    serialized_transform: str
    preview_transform: str
    packaged_files: tuple[str, ...]
    txi_delivery: str
    material_payload_sha256: str
    uv_warnings: tuple[str, ...] = ()
    texture_warnings: tuple[str, ...] = ()
    blocking_difference_paths: tuple[str, ...] = ()
    allowed_difference_paths: tuple[str, ...] = ()

    @property
    def accepted(self) -> bool:
        return (
            bool(self.texture_resref)
            and bool(self.source_texture_sha256)
            and self.preview_matches_serialized
            and not self.blocking_difference_paths
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ghostrigger.head_texture_material_report",
            "version": 1,
            "accepted": self.accepted,
            "mutable_node_ordinal": self.mutable_node_ordinal,
            "mutable_node_name": self.mutable_node_name,
            "texture_resref": self.texture_resref,
            "source_texture_sha256": self.source_texture_sha256,
            "source_decoded_rgba_sha256": (
                self.source_decoded_rgba_sha256
            ),
            "imported_uv_sha256": self.imported_uv_sha256,
            "serialized_uv_sha256": self.serialized_uv_sha256,
            "preview_uv_sha256": self.preview_uv_sha256,
            "preview_matches_serialized": self.preview_matches_serialized,
            "source_v_flip_applied": self.source_v_flip_applied,
            "serialized_transform": self.serialized_transform,
            "preview_transform": self.preview_transform,
            "packaged_files": list(self.packaged_files),
            "txi_delivery": self.txi_delivery,
            "material_payload_sha256": self.material_payload_sha256,
            "uv_warnings": list(self.uv_warnings),
            "texture_warnings": list(self.texture_warnings),
            "blocking_difference_paths": list(
                self.blocking_difference_paths
            ),
            "allowed_difference_paths": list(
                self.allowed_difference_paths
            ),
        }


@dataclass(frozen=True, slots=True)
class HeadTextureMaterialResult:
    model: Any = field(repr=False, compare=False)
    asset: HeadTextureAsset
    output_policy: HeadTextureOutputPolicy
    uv_contract: HeadUvOrientationContract
    report: HeadTextureMaterialReport


def apply_head_texture_materials(
    transplant: Any,
    *,
    donor_snapshot: HeadDonorSnapshot,
    asset: HeadTextureAsset,
    output_policy: HeadTextureOutputPolicy,
    uv_contract: HeadUvOrientationContract,
) -> HeadTextureMaterialResult:
    """Apply an explicit texture/UV policy to the mutable donor skin only."""

    if not isinstance(transplant, HeadGeometryTransplantResult) and not (
        getattr(transplant, "model", None) is not None
        and hasattr(getattr(transplant, "report", None), "mutable_node_ordinal")
    ):
        raise TypeError(
            "transplant must expose a model and mutable payload report"
        )
    if not isinstance(donor_snapshot, HeadDonorSnapshot):
        raise TypeError("donor_snapshot must be HeadDonorSnapshot")
    if not isinstance(asset, HeadTextureAsset) or not asset.accepted:
        raise HeadTextureMaterialError(
            "Texture source has not passed its IO contract"
        )
    if (
        not isinstance(output_policy, HeadTextureOutputPolicy)
        or not output_policy.accepted
    ):
        raise HeadTextureMaterialError(
            "Texture output policy has not passed its package contract"
        )
    if output_policy.source_sha256 != asset.source_sha256:
        raise HeadTextureMaterialError(
            "Texture output policy belongs to different source bytes"
        )
    if (
        not isinstance(uv_contract, HeadUvOrientationContract)
        or not uv_contract.audit.accepted
    ):
        raise HeadTextureMaterialError(
            "UV channel has not passed its structural audit"
        )
    if not uv_contract.preview_matches_serialized:
        raise HeadTextureMaterialError(
            "Preview UV orientation differs from serialized MDX orientation"
        )

    ordinal = transplant.report.mutable_node_ordinal
    candidate = deepcopy(transplant.model)
    nodes = _model_nodes(candidate)
    if ordinal < 0 or ordinal >= len(nodes):
        raise HeadTextureMaterialError(
            "The saved mutable donor node is unavailable"
        )
    node = nodes[ordinal]
    current_uv_sha = head_uvs_sha256(
        list(getattr(node, "uvs", ()) or ())
    )
    if current_uv_sha != uv_contract.imported_uv_sha256:
        raise HeadTextureMaterialError(
            "The candidate UV channel changed after its orientation audit"
        )
    node.texture = output_policy.output_resref
    node.uv_v_flip = uv_contract.preview_transform == "flip_v"
    setattr(
        node,
        "_gr_mdx_uv_transform",
        uv_contract.serialized_transform,
    )
    setattr(
        node,
        "_gr_head_builder_preview_uv_transform",
        uv_contract.preview_transform,
    )
    metadata = getattr(candidate, "metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
        setattr(candidate, "metadata", metadata)

    diff = compare_head_donor_contract(donor_snapshot, candidate)
    blocking = tuple(row.path for row in diff.blocking)
    if blocking:
        raise HeadTextureMaterialError(
            "Texture/material policy violated the immutable donor contract: "
            + ", ".join(blocking[:8])
        )
    payload_sha = _payload_sha256(
        asset=asset,
        output_policy=output_policy,
        uv_contract=uv_contract,
    )
    report = HeadTextureMaterialReport(
        mutable_node_ordinal=ordinal,
        mutable_node_name=str(getattr(node, "name", "") or ""),
        texture_resref=output_policy.output_resref,
        source_texture_sha256=asset.source_sha256,
        source_decoded_rgba_sha256=asset.decoded_rgba_sha256,
        imported_uv_sha256=uv_contract.imported_uv_sha256,
        serialized_uv_sha256=uv_contract.serialized_uv_sha256,
        preview_uv_sha256=uv_contract.preview_uv_sha256,
        preview_matches_serialized=(
            uv_contract.preview_matches_serialized
        ),
        source_v_flip_applied=uv_contract.source_v_flip_applied,
        serialized_transform=uv_contract.serialized_transform,
        preview_transform=uv_contract.preview_transform,
        packaged_files=output_policy.packaged_files,
        txi_delivery=output_policy.txi_delivery,
        material_payload_sha256=payload_sha,
        uv_warnings=uv_contract.audit.warnings,
        texture_warnings=(
            tuple(asset.warnings) + tuple(output_policy.warnings)
        ),
        blocking_difference_paths=blocking,
        allowed_difference_paths=tuple(
            row.path for row in diff.allowed_payload_changes
        ),
    )
    metadata["head_builder_texture_materials"] = report.to_dict()
    return HeadTextureMaterialResult(
        model=candidate,
        asset=asset,
        output_policy=output_policy,
        uv_contract=uv_contract,
        report=report,
    )


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


def _payload_sha256(
    *,
    asset: HeadTextureAsset,
    output_policy: HeadTextureOutputPolicy,
    uv_contract: HeadUvOrientationContract,
) -> str:
    payload = {
        "source_texture_sha256": asset.source_sha256,
        "decoded_rgba_sha256": asset.decoded_rgba_sha256,
        "output_policy": output_policy.to_dict(),
        "uv_contract": uv_contract.to_dict(),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "HeadTextureMaterialError",
    "HeadTextureMaterialReport",
    "HeadTextureMaterialResult",
    "apply_head_texture_materials",
]
