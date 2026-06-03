"""KOTOR Character Builder constants and evidence anchors.

The constants here are deliberately modest: they capture verified fixture facts
and documentation anchors that Character Builder export validation can cite
without pretending the pending MDL-loader Ghidra work is complete.
"""

from __future__ import annotations

KOTOR_ENGINE_FINDINGS_DOC = "docs/ghidra_findings.md"
KOTOR_ENGINE_EVIDENCE_STATUS = "fixture_verified_function_addresses_pending"

KOTOR_NATIVE_RESREF_MAX_LEN = 16

VERIFIED_PMBAM_STRUCTURAL_NODES: tuple[str, ...] = (
    "PMBAM",
    "cutscenedummy",
    "rootdummy",
    "rcollar_dum",
    "rhand",
    "lcollar_dum",
    "lforearm",
    "lhand",
    "headhook",
    "Impact",
    "FreeLookHook",
    "camerahook",
    "headconjure",
    "LightsaberHook",
    "DeflectHook",
    "handconjure",
    "impact_bolt",
)

CHARACTER_EXPORT_EVIDENCE: dict[str, object] = {
    "findings_doc": KOTOR_ENGINE_FINDINGS_DOC,
    "status": KOTOR_ENGINE_EVIDENCE_STATUS,
    "verified_fixture": "pmbam",
    "verified_sources": (
        "mcp:ghostrigger_model_info:k1:pmbam",
        "mcp:ghostrigger_model_info:k2:pmbam",
        "mcp:ghostrigger_list_retarget_animations:k1:pmbam",
        "mcp:ghostrigger_list_retarget_animations:k2:pmbam",
    ),
    "verified_native_contract": (
        "selected_native_base_owns_final_dag",
        "imported_mesh_is_payload_guest",
        "preserve_exact_node_names_and_parent_paths",
        "preserve_native_supermodel_inheritance",
        "preserve_native_socket_helper_nodes",
    ),
    "pending_ghidra": (
        "mdl_loader_function_addresses",
        "skin_weight_influence_limit",
        "engine_weight_normalization_behavior",
        "socket_attachment_function_addresses",
    ),
}
