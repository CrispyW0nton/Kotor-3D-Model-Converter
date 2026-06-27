"""Editability and preservation policy for stock module archive resources."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ModuleResourceSafety:
    restype: str
    edit_status: str
    editable_scope: str
    workflow: str
    safety_policy: str
    export_policy: str


TEXTURE_RESTYPES = {"tga", "tpc", "txi"}
GAMEPLAY_RESTYPES = {"utc", "utp", "utd", "utt", "uts", "ute", "utw", "utm", "uti"}
METADATA_RESTYPES = {"are", "ifo"}
AUDIO_MOVIE_RESTYPES = {"wav", "bik", "ssf"}
UI_TABLE_RESTYPES = {"2da", "gui", "itp", "jrl", "tlk"}
IMAGE_RESTYPES = {"bmp", "dds", "plt"}


def classify_module_resource(resource: object) -> ModuleResourceSafety:
    """Return the current Module Editor edit/safety policy for one resource."""

    restype = str(getattr(resource, "restype", resource) or "").lower().lstrip(".")
    if restype in {"tga", "tpc"}:
        return ModuleResourceSafety(
            restype,
            "editable now",
            "texture_preview_replacement",
            "thumbnail preview, import, material assignment, and copied-export bundling",
            "source texture bytes stay unchanged unless bundled into an exported module copy",
            "can bundle replacement payloads and patch MDL texture references",
        )
    if restype == "txi":
        return ModuleResourceSafety(
            restype,
            "editable now",
            "texture_sidecar_text",
            "TXI sidecar text authoring for selected replacement textures",
            "authored TXI text is session-local until copied export",
            "can bundle TXI sidecars next to replacement TGA/TPC resources",
        )
    if restype == "mdl":
        return ModuleResourceSafety(
            restype,
            "editable now",
            "room_mdl_material_refs",
            "room model material-slot inspection and texture-reference patching",
            "first version changes mesh-node material references, not one-off face splits",
            "can patch fixed MDL texture fields in a copied module archive",
        )
    if restype == "mdx":
        return ModuleResourceSafety(
            restype,
            "inspect/list-only",
            "room_mdx_binary_pair",
            "paired room model payload preserved while MDL texture references are edited",
            "MDX binary payload is byte-preserved until a validated serializer exists",
            "preserved byte-for-byte unless a future MDX-safe edit is added",
        )
    if restype == "wok":
        return ModuleResourceSafety(
            restype,
            "editable now",
            "walkmesh_surface_faces",
            "walkmesh face inspection and surface material painting",
            "WOK edits validate through the BWM serializer before copied export",
            "can write validated WOK payloads into a copied module archive",
        )
    if restype in {"lyt", "vis"}:
        return ModuleResourceSafety(
            restype,
            "editable now",
            "layout_visibility_text",
            "room coordinate and visibility graph editing",
            "layout edits round-trip through text serializers before copied export",
            "can write validated LYT/VIS payloads into a copied module archive",
        )
    if restype == "git":
        return ModuleResourceSafety(
            restype,
            "editable now",
            "placed_object_forms",
            "placed object form and template-reference editing",
            "GIT edits round-trip through the typed GFF writer before copied export",
            "can write validated GIT payloads into a copied module archive",
        )
    if restype in GAMEPLAY_RESTYPES:
        return ModuleResourceSafety(
            restype,
            "editable now",
            "gameplay_template_form",
            "creature, placeable, door, trigger, sound, encounter, waypoint, merchant, or item template fields",
            "template edits round-trip through the typed GFF writer before copied export",
            "can write validated template payloads into a copied module archive",
        )
    if restype in METADATA_RESTYPES:
        return ModuleResourceSafety(
            restype,
            "editable now",
            "area_module_metadata",
            "area and module metadata field editing",
            "metadata edits round-trip through the typed GFF writer before copied export",
            "can write validated ARE/IFO payloads into a copied module archive",
        )
    if restype == "dlg":
        return ModuleResourceSafety(
            restype,
            "partial editor",
            "dlg_top_level_fields",
            "dialogue reference inspection and top-level primitive field edits",
            "nested dialogue trees stay list-preserving until a tree editor exists",
            "can write validated top-level DLG field edits into a copied module archive",
        )
    if restype in {"pth", "nss", "ncs"}:
        return ModuleResourceSafety(
            restype,
            "inspect/list-only",
            f"{restype}_dependency_audit",
            "path/script listing and dependency checks",
            "payload is preserved until path editing or script compile/decompile validation exists",
            "preserved byte-for-byte in copied exports unless another validated edit targets it",
        )
    if restype in AUDIO_MOVIE_RESTYPES:
        return ModuleResourceSafety(
            restype,
            "preserve-only",
            "audio_movie_payload",
            "audio/movie resource identification only",
            "media payloads are intentionally not edited by the Module Editor yet",
            "preserved byte-for-byte in copied exports",
        )
    if restype in UI_TABLE_RESTYPES or restype in IMAGE_RESTYPES:
        return ModuleResourceSafety(
            restype,
            "inspect/list-only",
            "supporting_game_resource",
            "supporting table, UI, journal, or image resource audit",
            "payload is listed and preserved until a focused safe editor exists",
            "preserved byte-for-byte in copied exports",
        )
    return ModuleResourceSafety(
        restype or "unknown",
        "preserve-only",
        "unknown_binary_preserved",
        "unknown or unsupported resource audit",
        "unsupported payloads are preserved and cannot be edited until GhostRigger has a safe parser/writer",
        "preserved byte-for-byte in copied exports",
    )


def summarize_resource_safety(resources: Iterable[object]) -> dict[str, int]:
    """Count resources by current editability status."""

    return dict(Counter(classify_module_resource(resource).edit_status for resource in resources))


def summarize_resource_safety_scopes(resources: Iterable[object]) -> dict[str, int]:
    """Count resources by the concrete editor/preservation scope used in audits."""

    return dict(Counter(classify_module_resource(resource).editable_scope for resource in resources))


__all__ = [
    "ModuleResourceSafety",
    "classify_module_resource",
    "summarize_resource_safety",
    "summarize_resource_safety_scopes",
]
