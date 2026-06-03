"""KOTOR Character Builder constants and evidence anchors.

The constants here are deliberately modest: they capture verified fixture facts
and documentation anchors that Character Builder export validation can cite
without pretending the pending MDL-loader Ghidra work is complete.
"""

from __future__ import annotations

KOTOR_ENGINE_FINDINGS_DOC = "docs/ghidra_findings.md"
KOTOR_ENGINE_EVIDENCE_STATUS = "fixture_verified_function_addresses_pending"
KOTOR_ENGINE_SOCKET_STRING_EVIDENCE_STATUS = "selected_hook_string_refs_verified_parser_pending"

KOTOR_NATIVE_RESREF_MAX_LEN = 16
KOTOR_SKIN_MAX_INFLUENCES_PER_VERTEX = 4

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

ENGINE_VERIFIED_SOCKET_STRING_REFS: tuple[dict[str, object], ...] = (
    {
        "game": "k1",
        "string": "rhand",
        "string_address": "0074f334",
        "representative_refs": (
            "SwitchWeaponEvent@00610f40",
            "ApplyLightsaberThrow@006a30e0",
            "LoadVisualEffect@006a1880",
            "HideWieldedItems@0069a6b0",
        ),
    },
    {
        "game": "k1",
        "string": "lhand",
        "string_address": "0074f4b8",
        "representative_refs": (
            "SwitchWeaponEvent@00610f40",
            "LoadVisualEffect@006a1880",
            "HideWieldedItems@0069a6b0",
        ),
    },
    {
        "game": "k1",
        "string": "camerahook",
        "string_address": "0074f42c",
        "representative_refs": (
            "SetAnimatedCamera@00641010",
            "SetCamera@00671670",
            "Setup3DScene@006100f0",
        ),
    },
    {
        "game": "k1",
        "string": "handconjure",
        "string_address": "00751d74",
        "representative_refs": (
            "LoadVisualEffect@006a1880",
            "ApplySpellVisual@006a2e10",
            "LoadConjureVisual@00695f30",
        ),
    },
    {
        "game": "k1",
        "string": "impact_bolt",
        "string_address": "00751d40",
        "representative_refs": ("HandleServerToPlayerSafeProjectileProjectile@006501b0",),
    },
    {
        "game": "k1",
        "string": "FreeLookHook",
        "string_address": "0075164c",
        "representative_refs": ("Control@00639d00",),
    },
    {
        "game": "k2",
        "string": "rhand",
        "string_address": "00985e94",
        "representative_refs": (
            "SwitchWeaponEvent@0040f4a0",
            "ApplyLightsaberThrow@004fec40",
            "LoadVisualEffect@004fae10",
            "HideWieldedItems@004f5d80",
        ),
    },
    {
        "game": "k2",
        "string": "lhand",
        "string_address": "00985e8c",
        "representative_refs": (
            "SwitchWeaponEvent@0040f4a0",
            "LoadVisualEffect@004fae10",
            "HideWieldedItems@004f5d80",
        ),
    },
    {
        "game": "k2",
        "string": "handconjure",
        "string_address": "00988b6c",
        "representative_refs": (
            "LoadVisualEffect@004fae10",
            "ApplySpellVisual@004fe950",
            "LoadConjureVisual@004895b0",
        ),
    },
    {
        "game": "k2",
        "string": "impact_bolt",
        "string_address": "009892c8",
        "representative_refs": ("HandleServerToPlayerSafeProjectileProjectile@004bd180",),
    },
    {
        "game": "k2",
        "string": "FreeLookHook",
        "string_address": "0098b10c",
        "representative_refs": ("Control@004e8350",),
    },
)

CHARACTER_EXPORT_EVIDENCE: dict[str, object] = {
    "findings_doc": KOTOR_ENGINE_FINDINGS_DOC,
    "status": KOTOR_ENGINE_EVIDENCE_STATUS,
    "engine_string_evidence_status": KOTOR_ENGINE_SOCKET_STRING_EVIDENCE_STATUS,
    "verified_fixture": "pmbam",
    "verified_sources": (
        "mcp:ghostrigger_model_info:k1:pmbam",
        "mcp:ghostrigger_model_info:k2:pmbam",
        "mcp:ghostrigger_list_retarget_animations:k1:pmbam",
        "mcp:ghostrigger_list_retarget_animations:k2:pmbam",
        "mcp:kotor_engine_script:k1:selected_hook_string_refs",
        "mcp:kotor_engine_script:k2:selected_hook_string_refs",
    ),
    "engine_string_refs": ENGINE_VERIFIED_SOCKET_STRING_REFS,
    "verified_native_contract": (
        "selected_native_base_owns_final_dag",
        "imported_mesh_is_payload_guest",
        "preserve_exact_node_names_and_parent_paths",
        "preserve_native_supermodel_inheritance",
        "preserve_native_socket_helper_nodes",
    ),
    "writer_format_contract": (
        "MDLBinaryWriter writes four skin weights and four bone refs per skin vertex",
    ),
    "pending_ghidra": (
        "mdl_loader_function_addresses",
        "engine_weight_normalization_behavior",
        "full_socket_attachment_routine_semantics",
        "headhook_lightsaber_deflect_exact_engine_string_refs",
    ),
}
