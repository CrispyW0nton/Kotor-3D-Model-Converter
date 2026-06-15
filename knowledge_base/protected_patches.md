# Protected Patches

This file records fixes that must be preserved unless the user explicitly
authorizes a replacement with equal or stronger verification.

## 2026-06-02 - BAS Head Attachment Animation Contract

Status: PROTECTED PATCH.

This patch fixes the Body Attachment System head animation failure for
`K1:P_CarthBB` with attached heads such as `pmha01` and `pmhc01`.

The protected contract:

- BAS head selections must resolve to the actual head model resref before load.
  UI labels such as `Player Male Head A 01 - pmha01` must load `pmha01`.
- Attached head roots must retain `_gr_bas_attachment_source_model_ref` so the
  renderer can evaluate the original head model's matching animation slot.
- The body animation owns socket placement through `headhook`.
- The attached head may use only head-local animation tracks:
  `necklwr_g`, `neck_g`, `Hturn_g`, `head_g`, `talkdummy`, eyes, teeth,
  tongue, and facial `f_*` nodes.
- Source head body-chain tracks must not be applied to the BAS head attachment:
  `PMHA01`, `cutscenedummy`, `rootdummy`, `torso_g`, and `torsoUpr_g`.
- BAS attached-head skinning must stay isolated from the body skin palette.
- Pygfx wire overlays must continue to follow animated skinned body/head meshes.

Protected verification artifacts:

- `artifacts/bas_pmha01_animation_sweep_after_filter_20260602.json`
  sampled all 267 common `P_CarthBB + pmha01` animation slots at start/mid/end
  with `failure_count: 0`.
- `artifacts/actual_app_pygfx_carth_pmha01_head_resolve_20260602/`
  passed the visible actual-app BAS workflow using only `P_CarthBB + pmha01`.

Protected regression tests:

- `tests/test_core_contracts.py::test_bas_head_resolution_normalizes_ui_labels_and_body_candidates`
- `tests/test_core_contracts.py::test_bas_attach_head_loads_normalized_resolved_head_resref`
- `tests/test_core_contracts.py::test_bas_attachment_preview_parents_item_to_body_socket`
- `tests/test_pygfx_renderer_backend.py::test_carth_pmha01_bas_head_stays_socket_local_for_pause2`
- `tests/test_pygfx_renderer_backend.py::test_carth_pmha01_bas_head_uses_standalone_head_local_tracks_for_pause2`
- `tests/test_pygfx_renderer_backend.py::test_bas_head_attachment_inherited_pose_includes_head_parent_chain`

Do not remove, bypass, or weaken these checks while changing BAS, animation
source tagging, renderer mesh extraction, attachment skinning, or head resource
resolution.
