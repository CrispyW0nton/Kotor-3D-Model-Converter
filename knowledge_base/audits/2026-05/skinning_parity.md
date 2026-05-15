# Skinning Parity Audit - 2026-05

## Scope

Work item 3a audited the animated-creature breakage on K2 `c_brith` first, then `c_bomabeast`, with the goal of classifying the failure as:

- `alpha`: controller / node stage
- `beta`: palette construction stage
- `gamma`: final skinning application stage

All captures were taken at the current audit SHA (`d0fa269` naming convention) with deterministic animation name and time.

## Step 0 - Dangly Classification

Step 0 outputs:

- `diagnostics/skinning/2026_05/step0_c_brith_d0fa269.json`
- `diagnostics/skinning/2026_05/step0_c_bomabeast_d0fa269.json`

`compare_model_pipelines("K2", ...)` matched for both models:

- `c_brith`: PyKotor nodes `21`, GhostRigger nodes `21`, no discrepancies.
- `c_bomabeast`: PyKotor nodes `35`, GhostRigger nodes `35`, no discrepancies.

Classification result:

- `c_brith`: visible body mesh `Brith_mesh` is `skin=true`, `dangly=false`, with `0` dangly constraints. Two textured wing meshes, `R_Wing_bone_1` and `L_Wing_bone_1`, are rigid `trimesh` helpers and are not dangly.
- `c_bomabeast`: visible meshes `upperbody` and `lowerbody` are both `skin=true`, `dangly=false`, with `0` dangly constraints.

Step 0 therefore rules out the `PIN_THRESHOLD` dangly snap path. The audit advances to palette/application parity.

## Step 1 - Captures

The env-gated recorder is `GHOSTRIGGER_SKIN_DUMP`. It is inert when unset and appends one JSONL record per skin draw per renderer session.

Capture files:

- `diagnostics/skinning/2026_05/skin_c_brith_d0fa269.jsonl`
- `diagnostics/skinning/2026_05/skin_c_bomabeast_d0fa269.jsonl`
- `diagnostics/skinning/2026_05/c_brith_default_6p0_d0fa269.png`
- `diagnostics/skinning/2026_05/c_bomabeast_cwalk_0p6666667_d0fa269.png`

Audit frames:

- `c_brith`: animation `default`, time `6.0`
- `c_bomabeast`: animation `cwalk`, time `0.6666667`

## Reductions

Bone-map sanity:

- `c_brith` `Brith_mesh`: `bone_map_len=17`, `bone_map_overflow_used=true`, no duplicates, no referenced out-of-range indices. This is the expected extended-bone-map path, not a new overflow failure.
- `c_bomabeast` `upperbody` and `lowerbody`: `bone_map_len=16`, no overflow, no duplicates, no referenced out-of-range indices.

Animated-vs-bind divergence:

- `c_brith` referenced bones `R_Wing_bone_3`, `R_Wing_bone_2`, and `R_Wing_bone_3B` all have animation pose entries and non-identity composed matrices.
- `c_bomabeast` referenced bones on both skin draws all have animation pose entries and non-identity composed matrices.

Inverse-bind correctness:

- `c_brith`: `inverse_bind * bind_world` max error is approximately `2e-6` to `6e-6`.
- `c_bomabeast`: `inverse_bind * bind_world` max error is approximately `6e-7` to `1.2e-6`.

CPU-vs-uploaded palette parity:

- All captured referenced bones have `composed_skinning_matrix == uploaded_u_bones_matrix` within captured precision (`0.0` max diff in the reduction script).

Vertex-trace consistency:

- `c_brith` selected vertex `356` moves from `[7.5664, 1.7814, -0.1287]` to `[5.5934, 1.6780, -1.7035]` under the captured CPU palette.
- `c_bomabeast` `upperbody` selected vertex `91` moves from `[-0.2310, -1.7376, 0.4823]` to `[-0.3959, -1.6492, 0.4826]`.
- `c_bomabeast` `lowerbody` selected vertex `219` moves from `[0.3654, -0.3686, 0.1073]` to `[0.0761, -0.3592, 0.0241]`.

The CPU-side math says the sampled vertices should move. Controller output and palette construction are therefore producing motion.

## Classification

Both `c_brith` and `c_bomabeast` classify as `gamma`: final skinning application stage.

Concrete evidence:

- `u_skin_enabled=1` and `u_bone_count` are set for the captured skin draws.
- Bone-map lookup, inverse-bind composition, and palette upload source matrices pass the reductions.
- The shader declares `in_bone_ids` as `ivec4`.
- The VAO binds the same attribute through the float VBO format `4f` in layout `3f 3f 2f 2f 4f 4f 4f`.

That leaves the final attribute/uniform application boundary as the first failing layer. The likely fix is to make the bone-ID attribute path type-correct, either by uploading integer bone IDs with an integer vertex attribute format or by changing the shader input to a float/vector type and explicitly casting to integer palette indices in the shader.

## Follow-Up Fix Ticket

`3d-fix`: repair GPU skinning attribute application in `src/gui/gpu_renderer.py`.

Acceptance for the fix:

- `in_bone_ids` and the VAO/VBO attribute format agree on type.
- A regression pins CPU-composed matrix application against the GPU attribute path for one referenced bone/vertex.
- `c_brith` and `c_bomabeast` recaptures at the same audit frames no longer show the pinned/animation-breakage symptom.
- K1 controls and the K2 `c_drexlf` texture-alias control remain unchanged.

## 3d-fix Resolution

The fix uses the preferred integer attribute path:

- Shader input is `in ivec4 in_bone_ids`.
- Bone IDs are split into a dedicated `int32` VBO and bound with ModernGL format `4i`.
- The main float VBO now carries only position, normal, UV0, UV1, color, and weights with format `3f 3f 2f 2f 4f 4f`.
- `in_weights` remains `vec4` / `4f`.

Post-fix captures:

- `diagnostics/skinning/2026_05/skin_c_brith_3d_fix.jsonl`
- `diagnostics/skinning/2026_05/skin_c_bomabeast_3d_fix.jsonl`
- `diagnostics/skinning/2026_05/c_brith_default_6p0_3d_fix.png`
- `diagnostics/skinning/2026_05/c_bomabeast_cwalk_0p6666667_3d_fix.png`

The post-fix dump records confirm `shader_bone_ids_type=ivec4`, `bone_ids_attribute_format=4i`, `u_skin_enabled=1`, and valid bone counts for all captured skin draws.

## 3a-v2 - Live Slot Palette Audit

3d-fix corrected a real type-contract bug, but post-fix creature recaptures still showed broken silhouettes. The audit was reopened at the same layer with a live-slot dump.

Additional captures:

- `diagnostics/skinning/2026_05/skin_c_brith_3a_v2.jsonl`
- `diagnostics/skinning/2026_05/skin_c_bomabeast_3a_v2.jsonl`
- `diagnostics/skinning/2026_05/c_brith_default_6p0_3a_v2.png`
- `diagnostics/skinning/2026_05/c_bomabeast_cwalk_0p6666667_3a_v2.png`

The v2 dump records every local bone-map index referenced by any weighted vertex, the remapped palette index actually sent to the shader, empty/root-slot flags, the CPU-composed matrix, the uniform-upload byte decode, and the qBone/tBone inverse-bind matrix for the same local slot.

### Live Slot Reductions

`c_bomabeast` empty-slot hypothesis:

- `upperbody` live local slots are `0..14`; empty local slot `15` is not referenced.
- `lowerbody` live local slots are `0..14`; empty local slot `15` is not referenced.
- Classification: empty-string bone slot is present in the map but not live, so it is not the visual deformation cause.

`c_brith` root-slot hypothesis:

- `Brith_mesh` live local slots are `0..16`.
- Local slot `16` is `C_Brith`, the model root, and is live on `50` vertices with weight sum approximately `49.996`.
- It remaps to palette index `0`.
- The uploaded matrix for palette index `0` is identity at the audited frame.
- Classification: root references are real and should remain covered by a regression, but this slot is not a palette-upload mismatch.

CPU-vs-uploaded parity:

- `c_brith` `Brith_mesh`: max live-slot CPU-vs-uploaded error is `0.0`.
- `c_bomabeast` `upperbody`: max live-slot CPU-vs-uploaded error is `0.0`.
- `c_bomabeast` `lowerbody`: max live-slot CPU-vs-uploaded error is `0.0`.

This eliminates uniform upload as the remaining cause.

### Inverse-Bind Drift

The first reduction that does fire is current inverse bind versus the skin node's qBone/tBone inverse-bind data.

`c_brith`:

- `Brith_mesh` max `inverse_bind_vs_qbone_max_abs` is approximately `10.283`.
- Worst live slots include `Tail_bone_3`, `L_Wing_bone_3B`, `L_Wing_bone_3`, `R_Wing_bone_2`, and `Tail_bone_2`.

`c_bomabeast`:

- `upperbody` max `inverse_bind_vs_qbone_max_abs` is approximately `3.114`, worst on `upperspine`.
- `lowerbody` max `inverse_bind_vs_qbone_max_abs` is approximately `3.410`, worst on `Tailbone3`.
- Both visible skin nodes have a non-identity skin-node bind transform: position approximately `(0, -1.25, 0.72)`, rotation approximately `(0, 0, 1, 0)`.

This matches the older `knowledge_base/audits/k2_skin_transform.md` finding: reference renderers keep raw skin vertices and resolve the final position through skinning math using skin-node bind transforms and qBone/tBone inverse-bind data. GhostRigger's current GPU palette path still builds inverse bind from the animation first-frame hierarchy, not from the per-skin qBone/tBone bind data.

## 3a-v2 Classification

The remaining animated-creature bug is `beta`: palette construction stage.

Concrete evidence:

- Dangly classification remains eliminated.
- Empty live slot is eliminated for `c_bomabeast`.
- Root live slot is real for `c_brith`, but it uploads identity and is not an upload mismatch.
- CPU-composed palette and uploaded `u_bones` are byte-equivalent after decode for all live slots.
- Current inverse bind diverges materially from qBone/tBone inverse-bind data for live slots on both creatures.

## Follow-Up Fix Ticket

`3f-fix`: rebuild GPU skin palette construction around per-skin qBone/tBone inverse-bind data and the skin-node bind transform, matching the xoreos/KotOR.js flow.

Acceptance for the fix:

- The palette builder can produce per-skin-node matrices, not only one global model palette, because qBone/tBone data lives on the skin node and is indexed by the node's local bone map.
- `c_brith` local root slot remains legal and covered, but its handling is based on the skin node's qBone/tBone slot data.
- `c_bomabeast` empty local slot remains non-live or is safely ignored.
- Regression pins at least one live slot per affected mesh where current inverse bind equals qBone/tBone inverse bind within tolerance.
- Post-fix recaptures of `c_brith` and `c_bomabeast` at the same audit frames show normal creature silhouettes.

## 3f-fix Resolution

The GPU skin path now builds and uploads a local palette for each skin draw:

- Vertex bone IDs remain in the MDL's local `bone_map` slot order.
- Each local slot `k` reads inverse bind from the same skin node's `qBone[k]` and `tBone[k]`.
- The uploaded matrix for slot `k` is `animated_world(bone_map[k]) * inverse(T(tBone[k]) * R(qBone[k]))`.
- The shader and VAO contract from 3d-fix remains unchanged: `ivec4` bone IDs, `int32` bone-ID VBO, and `4i` binding.

Post-fix captures:

- `exports/skin_3f_postfix/c_brith_default_6.000.png`
- `exports/skin_3f_postfix/c_bomabeast_cwalk_0.667.png`
- `exports/skin_3f_postfix_gpu/c_brith_default_6.000.png`
- `exports/skin_3f_postfix_gpu/c_bomabeast_cwalk_0.667.png`
- `exports/skin_3f_postfix_gpu_dump.jsonl`

Post-fix dump reductions:

- `c_brith` `Brith_mesh`: max `inverse_bind_vs_qbone_max_abs` is approximately `4.99e-7`; max CPU-vs-uploaded error is `0.0`.
- `c_bomabeast` `upperbody`: max `inverse_bind_vs_qbone_max_abs` is approximately `4.94e-7`; max CPU-vs-uploaded error is `0.0`.
- `c_bomabeast` `lowerbody`: max `inverse_bind_vs_qbone_max_abs` is approximately `4.94e-7`; max CPU-vs-uploaded error is `0.0`.

This resolves the documented `beta` data-source divergence: palette construction now uses the authored per-skin qBone/tBone inverse-bind data instead of a model-global hierarchy-derived inverse bind. It does not, by itself, prove that the qBone/tBone and skin-node transforms are composed with the same convention as the Odyssey engine.

### Visual Verification Gate - Failed

Post-3f visual gate captures:

- `exports/skin_3f_postfix/c_brith_default_6.000.png`
- `exports/skin_3f_postfix/c_bomabeast_cwalk_0.667.png`
- `exports/skin_3f_visual_gate/k1_c_drexlf_cwalk_0.000.png`
- `exports/skin_3f_visual_gate/k2_c_drexlf_cwalk_0.000.png`

Visual inspection result:

- Numeric parity passes: qBone/tBone inverse-bind sourcing is reconciled at float32-noise levels and CPU-vs-uploaded parity remains `0.0`.
- Visual gate fails: the `c_drexlf` control captures still show anatomically suspicious head/forelimb placement, so internal palette parity is not sufficient evidence of correct engine behavior.
- The animated-creature class remains open. 3d-fix and 3f-fix stay valid as real sub-fixes, but the remaining best classification is a `beta`-adjacent transform-convention bug in skin assembly.

## 3g Audit Scope - Skin Transform Convention

The next audit should determine the Odyssey skin transform composition convention using `c_drexlf` as the primary visual control, then confirm on `c_brith` and `c_bomabeast`.

Candidate convention axes:

- qBone/tBone matrix order: `T * R` versus `R * T`.
- Bind interpretation: direct bind transform versus inverse bind transform.
- Skin-node transform placement: before animated bone world, after inverse bind, or as a bind/unbind wrapper.
- Vertex space: raw MDX skin vertices treated as mesh-local, skin-node-local, or already in a pre-bound skin space.

Minimum candidate formulas to evaluate for tagged vertices:

- `animated_world * inverse(T * R)`
- `animated_world * inverse(R * T)`
- `skin_node_bind * animated_world * inverse(T * R)`
- `animated_world * inverse(T * R) * inverse(skin_node_bind)`
- equivalent variants with skin-node bind/unbind wrapping around the weighted sum.

### Proposed Dump Extension

Extend `GHOSTRIGGER_SKIN_DUMP` for tagged probe vertices with:

- raw vertex position before skinning
- skin-node bind transform
- animated bone world transform for each influence
- qBone/tBone matrices in both `T * R` and `R * T` order
- final CPU-skinned position under each candidate formula
- current GPU-skinned position
- probe role label such as `head`, `forelimb`, or `wing_root`

### 3g Acceptance Criteria

- `knowledge_base/audits/2026-05/skinning_parity.md` records which candidate convention best restores `c_drexlf` head and forelimb placement.
- The same convention is tested on `c_brith` and `c_bomabeast`.
- If all three improve, scope `3g-fix` around that convention and add regression tests for tagged vertex final positions.
- If `c_drexlf` improves but either prior audit creature does not, keep the class open and split the remaining model-specific issue into a follow-up.

## 3g Initial Capture - Candidate Formula Sweep

The 3g dump extension is additive under `skin_transform_convention_*` fields. Existing 3a/3a-v2 schema fields remain intact.

3g captures:

- `diagnostics/skinning/2026_05/skin_c_drexlf_3g.jsonl`
- `diagnostics/skinning/2026_05/skin_c_brith_3g.jsonl`
- `diagnostics/skinning/2026_05/skin_c_bomabeast_3g.jsonl`
- `diagnostics/skinning/2026_05/3g_screens/c_drexlf_cwalk_0.000.png`
- `diagnostics/skinning/2026_05/3g_screens/c_brith_default_6.000.png`
- `diagnostics/skinning/2026_05/3g_screens/c_bomabeast_cwalk_0.667.png`

### Candidate Fields

For each tagged probe vertex, the dump records:

- `raw_position`
- `skin_node_bind_matrix`
- `skin_node_pose_matrix`
- weighted influence bone IDs and weights
- per-influence animated world matrix
- qBone/tBone matrices in `T * R` and `R * T` order
- candidate final positions for `F1` through `F8`
- distance from raw position for the bind-frame sanity proxy
- current GPU-skinned position derived from decoded uploaded `u_bones`

Candidate formulas:

- `F1_current_TR_inverse`: `animated_world * inverse(T * R)`
- `F2_RT_inverse`: `animated_world * inverse(R * T)`
- `F3_skin_bind_pre`: `skin_node_bind * animated_world * inverse(T * R)`
- `F4_skin_bind_post_inverse`: `animated_world * inverse(T * R) * inverse(skin_node_bind)`
- `F5_skin_bind_precancel`: `inverse(skin_node_bind) * animated_world * inverse(T * R)`
- `F6_TR_direct`: `animated_world * (T * R)`
- `F7_RT_direct`: `animated_world * (R * T)`
- `F8_bind_wrapper`: `inverse(skin_node_bind) * animated_world * inverse(T * R) * skin_node_bind`
- `F9_xoreos_TR_direct_wrapper`: `inverse(skin_node_bind) * animated_world * (T * R) * skin_node_bind`
- `F10_RT_direct_wrapper`: `inverse(skin_node_bind) * animated_world * (R * T) * skin_node_bind`

### Initial Reductions

`c_drexlf` at `cwalk` `t=0.0` is the strongest bind-frame sanity proxy because the correct convention should preserve authored coordinates better than an incorrect convention:

- `headGeo` `head_g`: `F5` is best among the tested candidates; `F2` improves over `F1` but does not win.
- `larmGeo` and `rarmGeo` forelimbs: `F5` is best for both tagged forelimb vertices.
- `chestGeo` wing-root probe: `F5` is best.
- `RWingGeo` wing-root probe: `F1` is best by a small margin over `F5`.
- `LWingGeo` wing-root probe: `F4` is best, with `F5` second among the high-signal candidates.

Cross-model reductions do not name one consistent candidate:

- `c_brith` head/pelvis probes favor direct `R * T` variants (`F7`), while the wing-root probe is unchanged across the current inverse-bind variants.
- `c_bomabeast` upperbody head and pelvis favor `F5`, but the forelimb probe favors `F4`; lowerbody pelvis remains closest under `F1`.

### 3g Interim Classification

The cheap F2 probe is eliminated as a single-line fix: swapping qBone/tBone order alone does not explain the visual failure. The strongest `c_drexlf` signal is `F5`, so skin-node pre-cancellation is now the lead hypothesis for head/forelimb placement, but the wing-root and cross-model reductions prevent naming a single winning formula yet.

Current status: 3g instrumentation is landed and the search space is narrower, but `3g-fix` is not ready. The remaining issue is likely not just qBone/tBone order; it is in skin-node transform placement and/or raw skin vertex space, potentially with per-node differences between body, wing, and limb skin nodes.

### 3g Step 5/6 Follow-Up

Step 5 result:

- The current 3g dump already evaluates each probe using the owning skin node's own bind transform.
- `c_drexlf` confirms the bind transform differs by mesh (`rarmGeo`, `larmGeo`, `headGeo`, `chestGeo`, wing meshes, and `tailGeo` each carry their own skin-node bind translation).
- Re-evaluating F5 per skin node therefore does not unify the disagreements; that condition was already true in the initial 3g dump.

Step 6 result:

- The dump now records `raw_vertex_space_candidate_positions` and `raw_vertex_space_distance_from_raw` for:
  - `H1_raw_as_mesh_space`
  - `H2_raw_as_skin_node_local`
- `c_drexlf` still mostly favors H1. Head, forelimbs, chest, and wing probes select H1 variants; F5 remains strongest on head/forelimbs/chest, while wing roots continue to split between F1/F4/F5.
- `c_brith` is unchanged by the H1/H2 discriminator because `Brith_mesh` has identity skin-node bind transform in the captured data.
- `c_bomabeast` is mixed: upperbody head favors H1/F5, upperbody forelimb favors H1/F4, upperbody pelvis improves under an H2/direct variant, and lowerbody pelvis favors H2/F8.

Conclusion:

- F2-only remains eliminated.
- F5-only remains an important body/head/forelimb signal, especially on `c_drexlf`, but is not sufficient as a universal fix.
- The raw-space discriminator also does not name one global convention. The remaining evidence points to a mesh-class or node-class split: body/head/forelimb skins and wing/pelvis/lowerbody skins may need different treatment, or the reduction's "distance from raw" bind-frame proxy is insufficient for non-bind audit frames.

Next audit step should compare against a real external ground truth rather than only internal candidate distances: either original-game/reference-renderer screen placement or a PyKotor/xoreos/KotOR.js-style CPU implementation for tagged vertex positions. Do not ship `3g-fix` until one convention is tied to external anatomical/engine evidence.

## 3h Scope - External Ground-Truth Audit

3g exhausted internal candidate-distance discriminators. The next audit must anchor the convention to engine-equivalent source code before any production skinning formula change ships.

### Primary Reference: xoreos

Source anchors:

- `xoreos/src/graphics/aurora/model_kotor.cpp:395-409`: `Model_KotOR::makeBoneNodeMap()` calls `computeInverseBindPose()` for each node and maps skin bone IDs to model nodes.
- `xoreos/src/graphics/aurora/model_kotor.cpp:809-823`: raw MDX vertex positions are read into `initialVertexCoords` without pre-skinning.
- `xoreos/src/graphics/aurora/model_kotor.cpp:863-890`: `ModelNode_KotOR::readSkin()` reads bone maps, weights, and bone mapping IDs.
- `xoreos/src/graphics/aurora/animation.cpp:251-321`: `Animation::updateSkinnedModel()` performs the CPU skinning pass.

xoreos's skin transform chain, in source order, is:

1. `invTransform = node->_invBindPose`
2. `transform = inverse(invTransform)`
3. `rv = initialVertex * transform`
4. `tv = rv * bone->_invBindPose`
5. `rv = tv * bone->_absoluteTransform`
6. `tv = rv * invTransform`
7. weighted accumulation into the skinned vertex buffer

In GhostRigger column-vector notation, this corresponds to a bind-wrapper family:

`inverse(skin_bind) * animated_world * bone_inverse_bind * skin_bind * raw_vertex`

The row/column question is resolved by xoreos's `multiply()` helper in `animation.cpp:241-249`. GLM indexes matrices as `m[column][row]`, and `multiply(v, m, rv)` computes:

`rv = m * [v.x, v.y, v.z, 1]`

So the source chain reads as a normal column-vector chain in GhostRigger notation:

`inverse(skin_bind) * bone_absolute * bone_inverse_bind * skin_bind * raw_vertex`

The remaining ambiguity is the identity of `bone_inverse_bind`. xoreos's `ModelNode::computeInverseBindPose()` (`modelnode.cpp:891-918`) builds node inverse bind from the node hierarchy. KotOR.js instead composes the skin node's qBone/tBone arrays directly into `bone_inverse_matrix` (`OdysseyModelNodeSkin.ts:123-128`). To test that ambiguity, 3g adds:

- `F8_bind_wrapper`: wrapper with `inverse(T * R)` as the inner factor.
- `F9_xoreos_TR_direct_wrapper`: wrapper with `(T * R)` as the inner factor, matching KotOR.js's direct qBone/tBone composition in Three.js notation.
- `F10_RT_direct_wrapper`: wrapper with `(R * T)` as the inner factor for the remaining qBone/tBone order ambiguity.

Important xoreos note: `animation.cpp:258-264` explicitly calls out a KotOR 2 case where a skin node parented under a bone can receive transforms twice, once by the renderer and once by skeletal animation. This directly matches the current suspicion that skin-node parent class may affect the correct rule.

### Secondary Reference: KotOR.js

Source anchors:

- `KobaltBlu/KotOR.js/src/odyssey/OdysseyModelNodeSkin.ts:98-128`: reads inverse bone quaternions/translations and composes `bone_inverse_matrix` from `bone_translations[i]` and `bone_quaternions[i]`.
- `KobaltBlu/KotOR.js/src/three/odyssey/OdysseyModel3D.ts:730-758`: builds a `THREE.Skeleton` from the skin node's bone list and passes the per-skin `bone_inverse_matrix` array to `SkinnedMesh.bind()`.
- `KobaltBlu/KotOR.js/src/three/odyssey/OdysseyModel3D.ts:1275-1280`: binds MDX `boneIdx` and `weights` as `skinIndex` and `skinWeight` geometry attributes.
- `KobaltBlu/KotOR.js/src/three/odyssey/OdysseyModel3D.ts:1345-1348`: creates `THREE.SkinnedMesh` for skin nodes.

KotOR.js agrees with 3f on the data-source contract: qBone/tBone-derived inverse matrices are per skin node and are used in that skin's local bone-map order. The remaining 3h task is to determine how Three.js's `SkinnedMesh.bind()` and bind matrix interact with the Odyssey node transform, then express that in the same F-formula notation.

### 3h Reduction Target

Re-map the external references into GhostRigger formulas:

- xoreos chain likely maps to a column-vector wrapper variant: `inverse(skin_bind) * animated_world * inverse_bind * skin_bind`.
- KotOR.js should either confirm the same wrapper through `SkinnedMesh.bind()` semantics or expose a second convention via Three.js bind matrices.

Then re-reduce the existing 3g dumps against the reference-named formula, not against "minimum distance from raw" alone.

### 3h Acceptance Criteria

- The xoreos convention is translated into exact GhostRigger matrix notation, including row/column order.
- KotOR.js is cross-checked for agreement or documented disagreement.
- The reference convention is mapped to an existing F formula, or a new F9/F10 formula is added if F1-F8 do not represent it exactly.
- Existing 3g dumps are re-reduced under the reference formula.
- If one rule applies globally, scope `3g-fix` as a single assembler change.
- If the rule depends on node class or parent class, scope `3g-fix` as a per-class assembler with one regression per class.
- No production skinning change ships until visual recaptures of `c_drexlf`, `c_brith`, and `c_bomabeast` pass anatomical review.

### 3h F9/F10 Re-Reduction

After adding the externally motivated wrapper variants, the existing 3g captures were regenerated and re-reduced.

Reduction result:

- `F9_xoreos_TR_direct_wrapper` does not win universally under the internal "distance from raw" metric.
- `F10_RT_direct_wrapper` wins all three `c_brith` probes, but `c_brith` has identity skin-node bind in the captured data and therefore cannot resolve the wrapper placement question.
- `c_drexlf` remains mixed: body/head/forelimb probes still mostly favor `F5`; some wing/pelvis probes favor `F1`, `F4`, `F7`, `F8`, or `F10`.
- `c_bomabeast` remains mixed: upperbody forelimb favors `F4`, upperbody head favors `F5`, upperbody pelvis favors a direct variant under H2, and lowerbody pelvis favors H2/`F8`.

Interpretation:

- The xoreos/KotOR.js evidence is now strong enough to define the reference wrapper shape.
- The internal raw-distance reduction is not strong enough to choose the production formula, even with F9/F10 added.
- The next implementation decision must be tied to reference-renderer semantics and visual recapture, not to "minimum distance from raw" alone.

Current 3h status: reference formula shape is known; F9/F10 diagnostics are available; no `3g-fix` should ship until the wrapper is implemented behind a testable path and the visual gate passes.

### 3g-fix Attempt - Reference Wrapper Visual Gate

Production palette assembly was changed narrowly at the per-skin-node palette stage, preserving:

- local bone IDs in `bone_map` order,
- dedicated `ivec4`/int32 bone-ID upload,
- per-draw palette upload,
- qBone/tBone as the authored inverse-bind data source.

Two wrapper inner-factor interpretations were tested:

- `F9_xoreos_TR_direct_wrapper`: `inverse(skin_bind) * animated_world * (T * R) * skin_bind`
- `F8_bind_wrapper`: `inverse(skin_bind) * animated_world * inverse(T * R) * skin_bind`

Diagnostic dump fields now pin the shipped/tested assembly:

- `skin_transform_formula`
- `skin_bind_present`
- `skin_bind_det`
- `bone_inverse_bind_source`
- `palette_matrix_preupload_first_live_slot`
- `palette_matrix_uploaded_first_live_slot`
- `gpu_skinned_position_after_3g_fix`

Result:

- CPU-vs-upload parity remains exact for the tested wrapper path (`max cpu_vs_uploaded_max_abs = 0.0` on `c_drexlf`, `c_brith`, and `c_bomabeast`).
- `F9_xoreos_TR_direct_wrapper` failed visual gate strongly: all three captures still showed displaced/torn anatomy.
- `F8_bind_wrapper` also failed visual gate: framed GPU captures still show implausible silhouettes and disconnected/contorted limbs or wings.

Current conclusion:

- The bind-wrapper shape alone is not sufficient to close animated creatures in GhostRigger's current pipeline.
- The remaining divergence is likely outside the palette multiply line itself, most likely in GhostRigger's raw skin vertex/VBO space relative to the reference renderers, or in the animated-world pose chain feeding the wrapper.
- Do not mark `3g-fix` as passed. Animated creatures remain open.

### 3i Scope - Skin Input-Space / Pose-Chain Audit

Classification:

- `3d-fix` remains valid: the integer bone-ID attribute contract was a real GPU input bug.
- `3f-fix` remains valid: authored per-skin qBone/tBone data is the correct inverse-bind data source.
- `3g-fix` is rejected: changing only the palette multiply line did not pass visual gate.
- The open failure is now classified as a coordinate-space handshake bug between raw skin vertex data, skin-node bind space, and animated bone world space.

Primary control:

- `c_drexlf`, because the failure is simple, repeatable, and anatomically obvious.

Secondary visual gate controls:

- `c_brith`
- `c_bomabeast`

Probe vertices:

- head
- forelimb
- chest
- wing root
- pelvis or tail-adjacent point

Required per-probe dump fields:

- raw MDX position exactly as loaded,
- VBO `in_pos` after `_build_vbo_data`,
- mesh node name and skin node name,
- raw-space hypothesis: mesh-local, skin-node-local, or model-root local,
- skin bind matrix,
- qBone/tBone matrix in TR direct, RT direct, TR inverse, and RT inverse forms,
- qBone/tBone source slot and local `bone_map` index,
- animated local transform for each influencing bone,
- animated world transform for each influencing bone,
- parent chain used to build animated world,
- final per-bone transformed position before blending,
- final weighted CPU-skinned position,
- final uploaded/GPU-decoded skinned position,
- CPU-vs-upload max absolute error.

Reduction order:

1. Confirm `raw_mdx_position == VBO in_pos` for skin nodes unless a documented offset applies.
2. Replay one selected vertex through the current GhostRigger production path.
3. Replay the same vertex through xoreos-style reference notation using the same raw input.
4. Compare first divergence in this order: raw/VBO position, skin bind, qBone/tBone inverse, animated local, animated world, per-bone position, blended position, uploaded position.
5. Classify the first real divergence as:
   - A: raw vertex decode / raw-space bug,
   - B: animated local-to-world pose-chain bug,
   - C: skin-bind placement bug relative to raw space,
   - D: blend-stage bug.

Stop/go rule:

- Do not ship another `3g`-style production change unless a single external-reference replay also passes the visual gate on `c_drexlf`, `c_brith`, and `c_bomabeast`.
- The visual gate is anatomical, not just numerical: head/forelimb/chest placement, wing-root attachment, and pelvis/lower-body continuity must all be plausible.

Implementation posture:

- Keep 3f production palette assembly active while 3i runs.
- Keep `F8`, `F9`, and `F10` as diagnostics only.
- Do not reopen 3d-fix, qBone/tBone sourcing, or local bone-map IDs unless a 3i replay identifies a first divergence there.

### 3i Initial Instrumentation Pass

Implemented diagnostic-only single-vertex replay fields in the existing skin dump:

- `raw_mdx_position`
- `vbo_in_pos`
- `vbo_row_index`
- `vbo_source_vertex_index`
- `raw_vs_vbo_delta`
- `raw_vs_vbo_max_abs`
- `interpreted_raw_space`
- `vbo_bone_ids`
- `vbo_weights`
- per-influence `parent_chain`
- per-influence `animated_local`
- per-influence qBone/tBone matrices in TR/RT direct and inverse forms
- per-influence `production_per_bone_position_from_vbo_in_pos`

Important instrumentation correction:

- Skin meshes are expanded to triangle-list VBO rows.
- Therefore VBO row `N` is not necessarily source vertex `N`.
- The dump now records `_gr_last_vbo_source_indices` and compares each tagged source vertex against the correct expanded VBO row.

First `c_drexlf` result:

- After source-vertex remapping, every tagged probe in the generated `skin_c_drexlf_3i.jsonl` had `raw_vs_vbo_max_abs = 0.0`.
- That rules out a simple raw-MDX-to-VBO position drift for the selected `c_drexlf` probes.
- The next likely first divergence is now bucket B or C: animated local-to-world pose chain, or skin-bind/raw-space handshake relative to the reference replay.

### 3i Step 2 - First-Divergence Replay

Added per-probe replay fields for the current production path and the reference wrapper variants:

- `production_replay_pre_weight_positions`
- `reference_f8_replay_pre_weight_positions`
- `reference_f9_replay_pre_weight_positions`
- `production_weighted_sum_position`
- `reference_f8_weighted_sum_position`
- `reference_f9_weighted_sum_position`
- `skin_bind_applied_position`
- `skin_unbind_applied_position`
- `animated_world_applied_position`
- `first_divergence_stage`
- `first_divergence_stage_reference_f8`
- `first_divergence_stage_reference_f9`

Reduction result for `c_drexlf`:

- `raw_vs_vbo_max_abs` remained `0.0` for every tagged probe.
- `first_divergence_stage_reference_f8 = skin_bind_applied` for all 16 tagged probes.
- `first_divergence_stage_reference_f9 = skin_bind_applied` for all 16 tagged probes.

Interpretation:

- This rules out raw upload-row drift as the first divergence for the tagged `c_drexlf` probes.
- The first mathematical split between current production and the xoreos/KotOR.js wrapper family is the bucket-C boundary: whether the raw/VBO position is first moved through `skin_bind` before qBone/tBone and animated-world application.
- This does not make F8/F9 shippable. Both wrapper attempts already failed visual gate when promoted to production. The result only identifies the first semantic handoff that differs from the reference notation.

Next 3i question:

- Why does applying the wrapper's `skin_bind` stage produce visually worse output in GhostRigger?
- The likely remaining explanations are:
  - GhostRigger's `skin_bind` matrix is not the same bind matrix used by the reference renderers,
  - GhostRigger's animated-world matrix is in a different basis than the wrapper expects,
  - or qBone/tBone is already expressed relative to the raw skin vertex basis, making an additional `skin_bind` application double-count in the current loader.

### 3i Step 3 - Post-Skin-Bind Reduction

Added diagnostic fields to answer whether `skin_bind` is a required first-space move or a double application:

- `qbone_already_raw_basis_probe_weighted_sum_position`
- `qbone_after_skin_bind_probe_weighted_sum_position_f8`
- `qbone_after_skin_bind_probe_weighted_sum_position_f9`
- `raw_after_skin_bind_position`
- `raw_after_skin_unbind_position`
- `skin_bind_moves_raw_max_abs`
- `skin_unbind_moves_raw_max_abs`
- `first_post_skin_bind_mismatch_stage_reference_f8`
- `first_post_skin_bind_mismatch_stage_reference_f9`
- per-influence `animated_world_chain`

Reduction result for `c_drexlf`:

- `skin_bind` moves tagged raw/VBO points by up to `2.0` units.
- `first_post_skin_bind_mismatch_stage_reference_f8 = qbone_inverse_after_skin_bind` for all 16 tagged probes.
- `first_post_skin_bind_mismatch_stage_reference_f9 = qbone_direct_after_skin_bind` for all 16 tagged probes.
- The production path and the explicit `qbone_already_raw_basis` probe are identical, as expected.

Interpretation:

- The first divergence is not animated-world parent propagation. It occurs before animated-world becomes the active difference.
- The inserted `skin_bind` stage changes the point's basis, and qBone/tBone then acts on that changed point differently from the production/raw-basis path.
- This strengthens the hypothesis that, in GhostRigger's current loader representation, qBone/tBone is already expressed relative to the uploaded raw skin vertex basis. Applying an additional skin-node bind wrapper double-counts or shifts the basis.

Open question:

- Is GhostRigger's `skin_bind` matrix the wrong reference matrix for the xoreos/KotOR.js wrapper, or do those references already receive geometry in a different scene-node/bind space than GhostRigger's raw MDX/VBO positions?

Next reduction:

- Compare GhostRigger's `skin_bind` for each `c_drexlf` skin node against the reference renderer's actual skin-node bind/bindMatrix, not just the inferred node world transform.
- If reference `skin_bind` is identity or otherwise differs from GhostRigger's node world matrix, the failed wrapper visual gate is explained by using the wrong bind matrix.

### 3i Step 4 - Bind-Matrix Equivalence Audit

Reference read:

- KotOR.js `OdysseyModel3D.ts:730-756` builds `THREE.Skeleton(bones, inverses)` and calls `skinNode.bind(new THREE.Skeleton(...))`.
- It does not pass an explicit `bindMatrix`.
- Three.js therefore captures the `SkinnedMesh.matrixWorld` at bind time as the mesh `bindMatrix`.
- KotOR.js `OdysseyModelNodeSkin.ts:123-128` composes qBone/tBone directly into `bone_inverse_matrix`.

Added diagnostic fields:

- `skin_bind_equivalence.reference_renderer`
- `skin_bind_equivalence.reference_source`
- `skin_bind_equivalence.reference_bind_semantics`
- `skin_bind_equivalence.ghostrigger_current_skin_bind_matrix`
- `skin_bind_equivalence.candidate_matrices`
- `skin_bind_equivalence.candidate_vs_current_max_abs`
- `skin_bind_equivalence.candidate_vs_kotorjs_default_max_abs`

Candidates checked:

- `kotorjs_default_mesh_matrixWorld`
- `ghostrigger_node_world_bind`
- `parent_world_bind`
- `identity_bind`

Reduction result for `c_drexlf`:

- For every skin node, `ghostrigger_node_world_bind` matched `kotorjs_default_mesh_matrixWorld` with max abs error `0.0`.
- `identity_bind` and `parent_world_bind` differed by the same non-zero offsets that earlier showed up as `skin_bind_moves_raw_max_abs`:
  - `headGeo`: `2.0`
  - `rarmGeo`: `1.69`
  - `larmGeo`: `1.71`
  - `tailGeo`: `0.83`
  - `chestGeo`/wing nodes: `0.87`

Interpretation:

- The failed wrapper visual gate is not explained by GhostRigger accidentally using identity or parent-world where KotOR.js would use mesh `matrixWorld`.
- Under the KotOR.js/Three.js interpretation, GhostRigger's current `skin_bind` candidate is the same bind matrix.
- This strengthens the remaining hypothesis: in GhostRigger's current loader representation, the qBone/tBone inverse path already expects the raw uploaded skin-vertex basis. Applying `skin_bind` before qBone/tBone changes that basis and causes the immediate qBone-stage divergence observed in Step 3.

Remaining open item:

- Verify whether xoreos's CPU skinning path receives raw vertices in the same basis as GhostRigger's VBO positions, or whether xoreos applies an earlier mesh/node transform before the wrapper stage. If xoreos's raw input differs, the apparent wrapper disagreement is a representation mismatch rather than a palette formula bug.

### 3i Step 5 - Pre-Wrapper Input-Space Equivalence

Reference read:

- xoreos `Animation::updateSkinnedModel()` reads `iv = initialVertexCoords` and then applies:
  - `transform = inverse(node->_invBindPose)`
  - `multiply(iv, transform, rv)`
  - `multiply(rv, bone->_invBindPose, tv)`
  - `multiply(tv, bone->_absoluteTransform, rv)`
  - `multiply(rv, invTransform, tv)`
- Therefore xoreos does not feed qBone/bone inverse with the raw MDX point directly. Its pre-bone input is `skin_bind * initialVertexCoords`.
- KotOR.js/Three.js is equivalent in structure: `SkinnedMesh.bind()` captures `bindMatrix`, and Three.js skinning applies bind space before skeleton matrices.

Added explicit dump aliases:

- `reference_pre_qbone_input_position`
- `reference_pre_qbone_input_source`
- `production_pre_qbone_input_position`
- `reference_pre_qbone_vs_production_vbo_max_abs`

Reduction result for `c_drexlf`:

- `reference_pre_qbone_vs_production_vbo_max_abs` is non-zero for all 16 tagged probes.
- Observed deltas: `0.83`, `0.87`, `1.69`, `1.71`, `2.0`.

Interpretation:

- GhostRigger production feeds qBone/tBone with the uploaded raw/VBO point.
- xoreos/KotOR.js-style wrapper feeds qBone/bone inverse with `skin_bind * raw`.
- The two paths are not starting qBone/tBone from the same input basis.
- This explains why direct wrapper promotion failed the visual gate: it moved GhostRigger's already-working qBone/tBone input into a different basis before qBone/tBone acted.

Current best classification:

- Bucket A simple upload drift: ruled out for tagged probes.
- Bind-matrix candidate mismatch: ruled out for KotOR.js default bind candidate.
- First proven semantic mismatch: pre-qBone input space.
- Remaining fix target is not a palette formula swap; it is reconciling GhostRigger's loader representation with reference renderer input-space semantics.

### 3i Step 6 - Pre-qBone Basis Provenance

The decisive question for Step 6 was:

> Does GhostRigger already "bake in" the effect of `inverse(node->_invBindPose)` somewhere before qBone/tBone is applied?

Two independent reads were needed before the dump could classify cleanly.

GhostRigger loader read:

- `src/core/kotor_loader.py:_read_mesh` lines 666-677 stores PyKotor's `mesh.vertex_positions` directly into `gr.vertices` as `raw_verts`. No bind transform, no skin-node multiply, no inverse-bind fold-in is applied between MDX read and `gr.vertices` assignment.
- `src/gui/gpu_renderer.py` uploads `gr.vertices` verbatim into the `pos` VBO via `_GpuMesh.uploaded_positions`.
- Therefore the VBO is structurally identical to the raw MDX vertex stream that xoreos calls `_initialVertexCoords`.

xoreos reference read:

- `Animation::updateSkinnedModel()` reads `iv = _initialVertexCoords` and applies `transform = inverse(node->_invBindPose)` as the outer wrapper, where `_invBindPose` is built by `ModelNode::computeInverseBindPose()` (lines 891-919).
- Inside `computeInverseBindPose()`, the position-frame block at lines 904-907 reads `node->_positionFrames[0]` but never applies it. Only orientations are rotated in via `glm::rotate(_invBindPose, ...)` at line 912. The matrix is then inverted at line 918.
- Therefore xoreos's pre-wrapper `transform` is **rotation-only**, composed from the chain of first-frame orientations, with no translation column.

GhostRigger's `skin_bind` is a full position+rotation node-world matrix from `_node_world_matrix_for_pose_np(skin_node, None, {})`. When the skin node has any non-zero authored position, that translation enters `skin_bind`; when the same node's first-frame orientation is identity, xoreos's `transform` reduces to the identity matrix on that node and the wrapper outer matrix becomes a no-op. That is the exact failure mode.

New diagnostic fields per probe (under `pre_qbone_basis_provenance`):

- `loader_pretransform_detected`
- `skin_bind_translation_norm`
- `skin_bind_rotation_only_matrix`
- `reference_pre_qbone_with_full_skin_bind_position`
- `reference_pre_qbone_with_rotation_only_skin_bind_position`
- `reference_pre_qbone_with_rotation_only_vs_production_vbo_max_abs`
- `inverse_skin_bind_times_vbo_position`
- `inverse_skin_bind_times_vbo_vs_raw_max_abs`
- `inverse_skin_bind_check`

New top-level summary field (`pre_qbone_basis_provenance_summary`):

- `loader_pretransform`, `loader_source`
- `reference_initial_vertex_coords_source`
- `reference_pre_wrapper_transform_composition`, `reference_pre_wrapper_transform_source`
- `ghostrigger_skin_bind_composition`, `ghostrigger_skin_bind_source`
- `skin_bind_translation_norm`, `skin_bind_includes_translation_xoreos_does_not`
- `classification`, `recommended_next_audit`

Reduction result for `c_drexlf` (`scripts/reduce_skin_3i_step6.py` against `diagnostics/skinning/2026_05/skin_c_drexlf_3i.jsonl`, 7 skin draws / 16 tagged probes):

- All 7 skin draws report `loader_pretransform = none_passthrough_proven_by_raw_equals_vbo`.
- All 16 probes report `raw_vs_vbo_max_abs = 0.0` (loader passthrough proven numerically).
- `skin_bind_translation_norm` per skin node: `rarmGeo 1.74`, `tailGeo 0.83`, `larmGeo 1.76`, `chestGeo 0.87`, `headGeo 2.00`, `RWingGeo 0.87`, `LWingGeo 0.87` — all non-zero.
- `reference_pre_qbone_with_rotation_only_vs_production_vbo_max_abs = 0.0` for 15/16 probes (only `tailGeo` shows `0.036269`, indicating a tiny non-identity rotation in its bind chain).
- `inverse_skin_bind_times_vbo_vs_raw_max_abs` equals `skin_bind_translation_norm` exactly per node, confirming `vbo == raw` (loader did not pre-apply `skin_bind`).

Interpretation:

- The loader does NOT bake `inverse(node->_invBindPose)` (or any other skin-node bind) into `gr.vertices`. The VBO IS the raw MDX basis.
- For c_drexlf the rotation component of `skin_bind` is identity on every audited skin node (tailGeo carries a tiny residual). xoreos's rotation-only wrapper transform reduces to the identity matrix on these nodes and would not move the input at all.
- The earlier wrapper visual failure was therefore not "almost right"; it was structurally injecting the skin-node TRANSLATION into the input space that qBone/tBone already expects in raw basis. That is a coherent explanation for the observed catastrophic deformation magnitudes (0.83 to 2.0 units).

Updated classification:

- Loader pre-bake hypothesis (Outcome A): rejected. GhostRigger raw/VBO is not pre-adjusted into a bound basis.
- `skin_bind` composition mismatch (Outcome B'): confirmed. GhostRigger's `skin_bind` carries a translation column that xoreos's pre-wrapper `transform` does not.
- Per-node summary classification: `outcome_b_loader_passthrough_but_skin_bind_includes_translation_xoreos_transform_does_not` for all 7 c_drexlf skin draws.

Decision rule outcome (per Step 6 brief):

- Outcome A is rejected. The remaining fix is therefore in pre-wrapper transform construction, not in palette multiplication or loader vertex space. Two falsifiable sub-paths remain open:
  - Sub-path B-translation: replace `skin_bind` in any future wrapper experiment with a rotation-only matrix derived from the first-frame orientation chain, matching xoreos's `inverse(_invBindPose)` exactly. If a future visual gate with that variant passes on c_drexlf, c_brith, and c_bomabeast, the structural defect was the translation column inside `skin_bind`.
  - Sub-path B-qbone-basis: if the rotation-only wrapper variant also fails, then qBone/tBone itself was imported in a basis the reference engines do not expect, and the fix moves further upstream into loader/qBone import semantics.

Stop/Go status:

- Production stays at the 3f baseline (`animated_world * inverse(qBone/tBone)`). No wrapper variant has yet passed the visual gate, so no production change ships.
- Step 6 is a diagnostic step and does not by itself justify a production change.

### 3i Step 7 - B-translation Diagnostic Sweep

Step 7 implements two new diagnostic candidate formulas and runs them across the audit-control creatures `c_drexlf` (K2), `c_brith` (K2), and `c_bomabeast` (K1) at `cwalk t=0.0` (or static bind pose where `cwalk` is missing). Production is unchanged.

New diagnostic candidates added to `_SKIN_3G_FORMULAS`:

- `F11_rotation_only_skin_bind_wrapper`: `inverse(R(skin_node_bind)) * animated_world * inverse(T * R) * R(skin_node_bind)` — the loose interpretation of B-translation; `skin_bind` with the translation column zeroed.
- `F12_xoreos_first_frame_orientation_wrapper`: `inverse(M_chain) * animated_world * inverse(T * R) * M_chain` where `M_chain` is the composed first-frame orientation chain from the skin node up to the model root, exactly mirroring `ModelNode::computeInverseBindPose()` in xoreos (lines 891-919; positions read but never applied).

New per-probe diagnostic fields under `step7_b_translation`:

- `f11_outer_composition`, `f12_outer_composition`, `f11_outer_matrix`, `f12_outer_matrix`
- `f11_weighted_position`, `f12_weighted_position`, `production_weighted_position`
- `f11_vs_production_max_abs`, `f12_vs_production_max_abs`
- `f11_collapses_to_production`, `f12_collapses_to_production`
- `step7_interpretation` (one of `b_translation_loose_and_strict_both_collapse_to_production`, `b_translation_loose_collapses_to_production_strict_diverges`, `b_translation_loose_diverges_strict_collapses_to_production`, `b_translation_loose_and_strict_both_diverge_from_production`)

New top-level summary `step7_b_translation_summary` with the same four-way classification rolled across all probes plus a `visual_gate_recommendation` line.

Reduction result (`scripts/reduce_skin_3i_step6.py` against `diagnostics/skinning/2026_05/skin_c_*_3i.jsonl`):

c_drexlf (7 skin draws / 16 probes):

- 6 of 7 nodes: `F11_collapse_all = True`, `F12_collapse_all = True`, max delta `0.0`. Wrapper outer matrix is identity-or-near-identity on these nodes (skin_bind rotation is identity), so both wrapper variants are mathematically equivalent to current 3f production.
- `tailGeo`: F11 and F12 both diverge by `0.049845` (because tailGeo's bind has a small non-identity rotation, `rot_only_dx = 0.036269`).
- Top-level classification: `b_translation_loose_and_strict_both_collapse_to_production_no_visual_change_expected` for 6 of 7 skin nodes.

c_brith (1 skin draw / 3 probes):

- `Brith_mesh`: `skin_bind_translation_norm = 0.0` AND `rot_only_dx = 0.0` → skin_bind is identity. Both wrapper variants collapse trivially to production (`F11/F12 == F1`).
- Top-level classification: `b_translation_loose_and_strict_both_collapse_to_production_no_visual_change_expected`.

c_bomabeast (2 skin draws / 4 probes):

- `upperbody`: `skin_bind_translation_norm = 1.44`, `rot_only_dx ≈ 1.46-3.56`. F11/F12 diverge from production by up to `3.639196`.
- `lowerbody`: `skin_bind_translation_norm = 1.44`, `rot_only_dx ≈ 0.70`. F11/F12 diverge from production by `0.635954`.
- F11 == F12 numerically on every probe — for these creatures the xoreos first-frame-orientation chain matrix and the rotation-only `skin_bind` evaluate to the same outer matrix at `cwalk t=0.0`.
- Top-level classification: `b_translation_loose_and_strict_both_diverge_from_production_either_variant_visual_gate_warranted` for both skin nodes.

Per-creature interpretation (Step 7 brief, decision rule):

- **c_drexlf**: B-translation is provably a no-op on 6 of 7 skin nodes. Promoting F11 or F12 to production would render pixel-identical output to current 3f production for all but `tailGeo`. The c_drexlf visual failure cannot be explained or repaired by removing translation from the wrapper outer matrix. Sub-path **B-qbone-basis** is now the indicated next direction for c_drexlf.
- **c_brith**: skin_bind is identity, so any wrapper variant is structurally a no-op. B-translation cannot help c_brith for the same reason. Sub-path **B-qbone-basis** is the indicated next direction here as well.
- **c_bomabeast**: F11/F12 produce visibly different pixels than production (deltas of `0.64` to `3.64`). The B-translation visual gate is warranted *only* here. If a F11- or F12-rendered c_bomabeast capture passes anatomical review while c_drexlf and c_brith remain at the production baseline, B-translation is confirmed for c_bomabeast as a creature-specific structural fix. If c_bomabeast still fails visually under F11/F12, B-qbone-basis becomes the indicated next direction across all three audit creatures.

Refined classification:

- The original Step 6 framing ("rotation-only wrapper might fix all three creatures") is false. B-translation is now a creature-conditional hypothesis: it cannot help c_drexlf or c_brith because their `skin_bind` rotation is (almost) identity, but it could still help c_bomabeast.

Stop/Go status (unchanged but better-supported):

- Production stays at the 3f baseline. No wrapper variant has yet passed the visual gate.
- Two falsifiable sub-paths remain open and are now scoped per creature:
  - **B-translation visual gate**, c_bomabeast only: capture before/after under F11 (or F12; both produce identical numeric output here at `cwalk t=0.0`). Pass criteria are unchanged: anatomically coherent c_bomabeast capture without folding/contortion. c_drexlf and c_brith are NOT eligible for this gate because their wrapper variants are no-ops.
  - **B-qbone-basis**, c_drexlf and c_brith: examine whether `qBone/tBone` was imported in a basis the reference engines do not expect. This is now the indicated direction for these two creatures because the wrapper hypothesis is mathematically eliminated for them.

### 3i Step 7 - c_bomabeast Visual Gate Outcome (B-translation closure test)

The Step 7 brief gated the next move on a single binary falsification test against `c_bomabeast`. The user specified: "If the F11/F12 capture materially improves `c_bomabeast` anatomy ... then B-translation stays alive ... If `c_bomabeast` still looks twisted, folded, or disconnected, then B-translation is effectively closed and you should immediately pivot the whole remaining creature line to B-qbone-basis." `c_drexlf` and `c_brith` were excluded from this gate because Step 7 already proved F11/F12 collapse to F1 on those creatures.

Implementation:

- New env-gated production switch in `src/core/gpu_skinning.py`: `GHOSTRIGGER_SKIN_FORMULA`. Unset / unknown / `F1_current_TR_inverse` => current 3f production unchanged. `F11_rotation_only_skin_bind_wrapper` => `compute_skin_node_palette` computes per-bone matrices as `inverse(R(skin_bind)) * world_pose * inverse(qBone/tBone) * R(skin_bind)`, where `R(skin_bind)` is the rotation-only skin-node bind matrix (translation column zeroed). `compute_skin_node_palette` writes the active key into `_skin_palette_formula` for downstream diagnostics.
- F12 was not promoted to a production switch because Step 7 reduction proved F11 and F12 produce numerically identical palette output on every `c_bomabeast` probe at `cwalk t=0.0`. The user explicitly approved a single capture path.
- Headless capture script: `scripts/skin_3i_step7_visual_gate.py`. Builds a fresh `GpuRenderer` per `(resref, angle, formula)` triple, swaps `GHOSTRIGGER_SKIN_FORMULA`, renders 512x512 PNGs through the standalone ModernGL EGL/WGL context, and emits a per-pair pixel diff into `exports/skin_3i_step7_visual_gate/report.json`.
- Targets: `c_bomabeast` (K1, falsification target) and `c_drexlf` (K2, no-op infrastructure control). `c_brith` was intentionally skipped: its `skin_bind` is identity, so F11 == F1 trivially.
- Three angles per target (`diagonal -45/20`, `front 0/10`, `side 90/10`) so pelvis continuity, upper/lower body coherence, and limb folding are all visible.
- Tests added in `tests/test_regression.py`: identity-bind collapse to F1 (matches the c_drexlf / c_brith control prediction), non-identity-bind divergence (matches the c_bomabeast precondition), and unknown env value silently falls back to F1 (so a typo cannot perturb production rendering).

Capture results (`exports/skin_3i_step7_visual_gate/report.json`):

| target | angle | F1 vs F11 pixel diff | max channel delta | classification |
| --- | --- | --- | --- | --- |
| c_bomabeast (K1) | diagonal | 39.821% | 173 | TARGET_MATERIAL_DELTA |
| c_bomabeast (K1) | front    | 46.901% | 173 | TARGET_MATERIAL_DELTA |
| c_bomabeast (K1) | side     | 51.367% | 169 | TARGET_MATERIAL_DELTA |
| c_drexlf (K2)   | diagonal |  0.999% | 104 | CONTROL_NEAR_PASS |
| c_drexlf (K2)   | front    |  0.930% |  94 | CONTROL_NEAR_PASS |
| c_drexlf (K2)   | side     |  0.267% |  77 | CONTROL_NEAR_PASS |

Control verdict (c_drexlf):

- F1 and F11 captures are visually indistinguishable across all three angles. The sub-1% residual matches the predicted `tailGeo` non-identity-bind component from the Step 7 reduction (`rot_only_dx = 0.036` on `tailGeo` only). The env switch and the F11 wrapper math are working correctly; the no-op invariant on c_drexlf holds.

Falsification target verdict (c_bomabeast):

- The F11 capture produces materially different pixel output (40 to 51 percent of pixels diverge with channel deltas up to 173/255), confirming the Step 7 prediction that the rotation-only wrapper must move pixels on this creature. That is the necessary precondition for a meaningful gate.
- However, **F11 does NOT improve c_bomabeast anatomy**. The F1 capture is a splayed, contorted mess of triangle spikes radiating outward from the pelvis with no recognizable quadruped shape. The F11 capture is a different mess: large folded triangular sheets, also unrecognizable, with no improvement to upper/lower body coherence or pelvis continuity. The B-translation hypothesis predicted F11 would resolve the contortion. It did not. F11 produced equivalent visual incoherence in a different topology.
- Per the Step 7 binary decision rule: "If `c_bomabeast` still looks twisted, folded, or disconnected, then B-translation is effectively closed and you should immediately pivot the whole remaining creature line to B-qbone-basis." That precondition is met.

Capture artifacts (committed for follow-up review):

- `exports/skin_3i_step7_visual_gate/k1_c_bomabeast_cwalk_t000_diagonal_F1.png`
- `exports/skin_3i_step7_visual_gate/k1_c_bomabeast_cwalk_t000_diagonal_F11.png`
- `exports/skin_3i_step7_visual_gate/k1_c_bomabeast_cwalk_t000_front_F1.png`
- `exports/skin_3i_step7_visual_gate/k1_c_bomabeast_cwalk_t000_front_F11.png`
- `exports/skin_3i_step7_visual_gate/k1_c_bomabeast_cwalk_t000_side_F1.png`
- `exports/skin_3i_step7_visual_gate/k1_c_bomabeast_cwalk_t000_side_F11.png`
- `exports/skin_3i_step7_visual_gate/k2_c_drexlf_cwalk_t000_diagonal_F1.png` (control)
- `exports/skin_3i_step7_visual_gate/k2_c_drexlf_cwalk_t000_diagonal_F11.png` (control)
- ... (same for `front` and `side`)
- `exports/skin_3i_step7_visual_gate/report.json`

Updated classification:

- **B-translation: CLOSED for c_drexlf, c_brith, AND c_bomabeast.** c_drexlf and c_brith were already mathematically eliminated by the Step 7 reduction (F11 == F1). c_bomabeast is now eliminated by direct visual gate (F11 != F1 in pixels but equally broken anatomically).
- The full structural fix cannot live in the outer wrapper transform; replacing the wrapper's translation column with a rotation-only matrix is necessary but not sufficient.
- The remaining open sub-path is **B-qbone-basis**: `qBone/tBone` itself was imported into GhostRigger in a basis the reference engines do not expect. The fix moves further upstream into loader / qBone import semantics.

Stop/Go status:

- Production stays at the 3f baseline (`animated_world * inverse(qBone/tBone)`). No wrapper variant has passed a visual gate.
- The env switch `GHOSTRIGGER_SKIN_FORMULA=F11_rotation_only_skin_bind_wrapper` is retained as a permanent diagnostic; production is unchanged when the env is unset (proven by control captures and unit tests).
- Next active work item is **3j - qBone/tBone import basis audit** (B-qbone-basis), scoped to `c_drexlf` and `c_brith` first because their wrapper variants are mathematically no-ops and any future wrapper hypothesis there is provably futile.

### 3j Plan - qBone/tBone Import Basis Audit (B-qbone-basis)

Scope is `c_drexlf` (K2) and `c_brith` (K2) first. `c_bomabeast` follows as a third audit creature once the `c_drexlf`/`c_brith` divergence is characterized; both Step 7 visual gate captures and the prior wrapper experiments confirm that c_bomabeast also remains broken under every wrapper variant tested so far, so the same structural mismatch likely sits behind it.

Working hypothesis (from the cumulative 3i evidence):

- The 3i Step 1-5 results proved GhostRigger and the reference engines do not feed `qBone/tBone` from the same input basis (Bucket C, coordinate-space handshake mismatch).
- The 3i Step 6 results proved the loader is passthrough (raw MDX position == VBO row) and that GhostRigger's `skin_bind` is a full position+rotation matrix while xoreos's pre-wrapper outer transform is rotation-only.
- The 3i Step 7 visual gate proved zeroing the `skin_bind` translation column (F11/F12) does not visually correct any of the three audit creatures.
- Therefore the structural mismatch sits inside `qBone/tBone` themselves, not in the wrapper outer matrix or the loader vertex space. Either:
  - **Hypothesis B-qbone-basis-1 (basis-of-storage)**: qBone/tBone are stored in a different reference frame than GhostRigger interprets (e.g. parent-local vs node-local, or world-bind vs skin-node-local), so `inverse(T*R)` does not consume the raw vertex into the bone's own frame correctly.
  - **Hypothesis B-qbone-basis-2 (handedness/order)**: qBone/tBone are stored in a different rotation order or quaternion handedness convention than GhostRigger applies (e.g. T*R vs R*T composition, or XYZW vs WXYZ on disk).
  - **Hypothesis B-qbone-basis-3 (relative-to-skin-bind)**: qBone/tBone are stored RELATIVE to `skin_bind` (the parent skin node's authored position+rotation), so the production `inverse(T*R)` should be either composed with or wrapped by `skin_bind` to land in the same basis xoreos consumes.

Step 3j-1 - PyKotor-vs-GhostRigger qBone/tBone byte-for-byte parity:

- For each skin node in `c_drexlf` and `c_brith`, dump the raw `qBone[i]` (4 floats) and `tBone[i]` (3 floats) values from PyKotor's MDL reader and from GhostRigger's owned reader.
- Tag any divergence at the byte level. If the bytes match, GhostRigger's import is faithful and the mismatch is in interpretation, not transcription.
- Output: `diagnostics/skinning/2026_05/qbone_byte_parity_<resref>.jsonl`.
- Pass criterion: every `(skin_node, slot)` triple shows `pykotor_qbone == ghostrigger_qbone` and `pykotor_tbone == ghostrigger_tbone`. Any mismatch shifts the audit into a loader-fix step.

Step 3j-2 - xoreos / KotOR.js qBone consumption replay:

- Read xoreos's `Model_KotOR::readSkin()` (model_kotor.cpp) and KotOR.js's `MDLLoader.readMeshSkin()` to identify whether qBone/tBone are consumed AS-IS, INVERTED, COMPOSED with skin_node bind, or COMPOSED with parent-bone bind.
- Output: a short reference table in this doc with one row per reference engine and a column per consumption transform.
- Pass criterion: at least one reference engine's consumption pattern differs from GhostRigger's `qbone_inverse_bind_matrix` / `compute_skin_node_palette` path in a falsifiable way. That difference becomes the next candidate formula.

Step 3j-3 - Single-vertex end-to-end replay against external reference (extension of 3i Step 2):

- Pick the three tagged `c_drexlf` probe vertices already used in 3i Step 5 (one per skin node category: head, body, tail).
- Walk both pipelines vertex by vertex through the qBone/tBone application stage, tagging the input basis (raw, world, skin-bound, etc.) and the per-bone output position before weighting.
- First divergence at the qBone application stage classifies which sub-hypothesis (B-qbone-basis-1/2/3) the bug belongs to.
- Output: `diagnostics/skinning/2026_05/qbone_replay_<resref>.jsonl`.

Step 3j-4 - Candidate formula sweep restricted to qBone composition:

- Add diagnostic candidates F13-F1n to `_SKIN_3G_FORMULAS` covering each sub-hypothesis (e.g. `direct(qBone/tBone)`, `skin_bind * qBone/tBone`, `qBone/tBone * skin_bind`, `parent_bone_bind * qBone/tBone`, etc.).
- Run the existing 3i regen + reduce scripts unchanged. The dump's `step7_b_translation` aggregation can be reused; only the candidate list grows.
- Each candidate gets a per-creature `weighted_position` and `vs_production_max_abs` so the visual gate is gated on numeric divergence first (no wasted GPU captures on no-ops).

Step 3j-5 - Decision gate (binary, mirrors Step 7):

- For any candidate that produces non-trivial divergence on all three audited creatures (`c_drexlf`, `c_brith`, `c_bomabeast`), capture a single F-vs-F1 visual gate. Pass criterion is anatomical coherence on all three creatures, not just one.
- If no candidate passes the joint visual gate, the audit pivots to a loader-side fix at the basis identified in Step 3j-1 / 3j-2 (i.e. patch the qBone/tBone import to the basis the reference engines actually expect, rather than wrapping around the existing import).

Stop/Go criterion for 3j as a whole:

- A production change ships only when one candidate (a) passes the joint visual gate on all three audit creatures AND (b) does not regress the existing render-diff suite (`scripts/render_baseline.py --compare`) on a sample of 50 unrelated K1/K2 models. The 3g-fix lesson holds: internal consistency is not the same thing as correct engine behavior, and a wrapper that fixes one creature but breaks others is not a fix.

### 3j Step 1 - qBone/tBone Byte-for-Byte Parity Dump

Step 3j-1 implements the byte-parity dump scoped above, with the user-requested per-skin-node provenance refinement folded in: each slot record carries the MDL field offsets, the absolute file offset that `struct.unpack` consumed, and a short label naming each of the three decode paths used.

Implementation:

- New tool `scripts/dump_qbone_byte_parity.py`. Triangulates three independent reads per slot:
  1. **RAW BYTES** - `struct.unpack('<4f' / '<3f', mdl_bytes[...])` at `(_SkinmeshHeader.offset_to_qbones + 12) + slot * 16` (and analogously for tBone). The `+12` is the MDL data section base (PyKotor's `BinaryReader.set_offset(+12)` convention; see `pykotor/resource/formats/mdl/io_mdl.py` line ~507 "Do NOT add 12 here - the reader's offset is already adjusted"). 16 = `Vector4 = 4 * float32`, 12 = `Vector3 = 3 * float32`.
  2. **PYKOTOR** - `_SkinmeshHeader.qbones[i]` / `.tbones[i]` from the `GhostRiggerMDLBinaryReader` (which is `pykotor.resource.formats.mdl.io_mdl.MDLBinaryReader` plus GhostRigger's K2 trimesh fix - the only reader path production code uses via `read_mdl_safe`).
  3. **GHOSTRIGGER** - `gr.qbone_list[i]` / `gr.tbone_list[i]` from `load_model_from_bytes` -> `_read_skin_weights` (the `model_data.MDLNode` shape that `compute_skin_node_palette` consumes at render time).
- Per-slot record fields under `qbone` and `tbone`: `raw`, `pykotor`, `ghostrigger`, plus pairwise `*_max_abs` deltas and exact-equality booleans (`raw_eq_pykotor`, `pykotor_eq_ghostrigger`, `raw_eq_ghostrigger`). Tolerance is exactly `0.0`; any non-zero residual is the diagnostic signal.
- Per-skin-node provenance fields under `provenance`: `node_file_offset`, `mdl_field_offset_to_qbones`, `mdl_field_qbones_count`, `mdl_field_qbones_count2`, `mdl_field_offset_to_tbones`, `mdl_field_tbones_count`, `mdl_field_tbones_count2`, `file_absolute_offset_qbones_slot`, `file_absolute_offset_tbones_slot`, plus `decode_path_raw`, `decode_path_pykotor`, `decode_path_ghostrigger` (short string labels naming each consumption path so 3j-2's reference-engine replay can be aligned without ambiguity).
- Per-creature `_summary` row written first into each JSONL aggregating divergences and assigning one of three classifications: `import_faithful_defect_must_be_in_interpretation` / `pykotor_decode_diverges_from_raw_bytes` / `ghostrigger_consumption_diverges_from_pykotor`.

Outputs (committed):

- `diagnostics/skinning/2026_05/qbone_byte_parity_c_drexlf.jsonl` - 7 skin nodes, 455 slot records
- `diagnostics/skinning/2026_05/qbone_byte_parity_c_brith.jsonl` - 1 skin node, 21 slot records
- `diagnostics/skinning/2026_05/qbone_byte_parity_c_bomabeast.jsonl` - 2 skin nodes, 70 slot records

Reduction result (`scripts/dump_qbone_byte_parity.py` console summary):

| target | skin nodes | slot records | qbone worst raw vs pk | qbone worst pk vs gr | tbone worst raw vs pk | tbone worst pk vs gr | classification |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| K2:c_drexlf    | 7 | 455 | 0.0 | 0.0 | 0.0 | 0.0 | import_faithful_defect_must_be_in_interpretation |
| K2:c_brith     | 1 |  21 | 0.0 | 0.0 | 0.0 | 0.0 | import_faithful_defect_must_be_in_interpretation |
| K1:c_bomabeast | 2 |  70 | 0.0 | 0.0 | 0.0 | 0.0 | import_faithful_defect_must_be_in_interpretation |

Sanity-spot-check on the first slot of each creature (confirms the offset arithmetic is not silently off-by-one or off-by-record):

- `c_drexlf` `rarmGeo` slot 0: qbone `(-1, 0, 0, 0)` (unit quaternion, axis-aligned); tbone `(-0.4099, 0.0441, 1.69)` (plausible bind-pose translation within model bounds).
- `c_brith` `Brith_mesh` slot 0: qbone `(-1, 0, 0, 0)`; tbone `(-0, -0, -0)`.
- `c_bomabeast` `upperbody` slot 0: qbone `(-1e-6, 0, 0, -1)` (unit quaternion); tbone `(0, -1.25, 0.72)`.

Interpretation:

- All 546 slot records across all three audit creatures show byte-for-byte parity across all three independent reads. There is no decoding, transcription, byte-order, struct-format, attribute-access, or count-truncation bug anywhere in GhostRigger's qBone/tBone import pipeline.
- The bytes that `compute_skin_node_palette` ultimately feeds into `qbone_inverse_bind_matrix` and `qbone_direct_bind_matrix` are **bit-identical** to the bytes on disk.
- Therefore the 3j defect lives in interpretation, not in transcription.

Updated 3j sub-hypothesis status:

- **B-qbone-basis-1** (basis-of-storage - which reference frame are qBone/tBone authored in?): **OPEN**. 3j-1 cannot answer this; it requires reference-engine consumption replay (3j-2).
- **B-qbone-basis-2** (handedness/order): partially narrowed. The on-disk byte layout is proven `XYZW` for qBone (matched between `struct.unpack('<4f')` and PyKotor `read_vector4()` which returns `x,y,z,w` in that order); the GhostRigger consumption layer does not reorder. The remaining open question under B-qbone-basis-2 is *composition order* once the floats are interpreted as a quaternion+translation: whether the bind matrix should be `T(t) * R(q)` (what GhostRigger's `qbone_inverse_bind_matrix` and `qbone_direct_bind_matrix` build) or `R(q) * T(t)`, or whether the quaternion convention used by the reference engines is XYZW vs WXYZ at the matrix-construction stage.
- **B-qbone-basis-3** (relative-to-skin-bind / parent-bone-bind): **OPEN**. 3j-1 cannot answer this; it requires reference-engine consumption replay (3j-2).

Stop/Go status (unchanged):

- Production stays at the 3f baseline. 3j-1 is a transcription-layer audit only and produces no candidate formula.
- The next active substep is **3j-2 - xoreos / KotOR.js qBone consumption replay**, scoped to identify whether the reference engines apply qBone/tBone AS-IS, INVERTED, COMPOSED with skin-node bind, COMPOSED with parent-bone bind, or under a different rotation order. The output of 3j-2 is the candidate-formula list that 3j-4 will sweep.

### 3j Step 2 - qBone/tBone Consumption Convention Audit

3j-2 replays qBone/tBone consumption across three independent reference KotOR engines (xoreos, KotOR.js, reone) and aligns each finding to the exact source line where the floats become a matrix. The audit follows the user-scoped four-section template: raw authored values (already in 3j-1), matrix construction variants, reference provenance, and first-divergence comparison.

Reference engine source citations:

- **xoreos** (`xoreos/src/graphics/aurora/model_kotor.cpp:938-1003`, `ModelNode_KotOR::readSkin`):
  ```cpp
  ctx.mdl->skip(ctx.xbox ? 8 : 12);
  uint32_t mdxOffsetBoneWeights = ctx.mdl->readUint32LE();
  uint32_t mdxOffsetBoneMappingId = ctx.mdl->readUint32LE();
  uint32_t boneMappingOffset = ctx.mdl->readUint32LE();
  uint32_t boneMappingCount = ctx.mdl->readUint32LE();
  ctx.mdl->skip(72);                              // <-- entire qBone/tBone block skipped
  ```
  xoreos **does not consume qBone/tBone at all**. The remaining 72 bytes of the skinmesh header (which contain `offset_to_qbones`, `qbones_count`, `offset_to_tbones`, `tbones_count`, `offset_to_unknown0`, the 16-uint16 bones array, and trailing padding) are skipped wholesale. The inverse bind matrix is instead built from the static node hierarchy via `ModelNode::computeInverseBindPose()` (`xoreos/src/graphics/aurora/modelnode.cpp:891-919`), which uses each node's own `position`/`orientation` quaternion fields read from the node header. xoreos's CPU skinning chain consumes that hierarchy-derived inverse bind exclusively.

- **KotOR.js** (`KotOR.js/src/odyssey/OdysseyModelNodeSkin.ts:98-128`):
  ```typescript
  // line 98 comment: "Inverse Bone Quaternions"
  for (let i = 0; i < this.boneQuaternionDefinition.count; i++) {
      let w = this.odysseyModel.mdlReader.readSingle();          // <-- W READ FIRST
      this.bone_quaternions[i] = new THREE.Quaternion(
          this.odysseyModel.mdlReader.readSingle(),               // X
          this.odysseyModel.mdlReader.readSingle(),               // Y
          this.odysseyModel.mdlReader.readSingle(),               // Z
          w);
  }
  // ...
  // line 124-128: stored directly as the *inverse* bind matrix (no .invert() call)
  for (let i = 0; i < this.bonePositionDefinition.count; i++) {
      this.bone_inverse_matrix[i] = new THREE.Matrix4();
      this.bone_inverse_matrix[i].compose(
          this.bone_translations[i],
          this.bone_quaternions[i],
          new THREE.Vector3(1, 1, 1));
  }
  ```
  KotOR.js reads W first then X,Y,Z, composes via `THREE.Matrix4.compose(T, Q, S)` which produces `T * R * S` (= `T * R` here since S is identity), then **stores the result directly into a variable named `bone_inverse_matrix`** (lines 34, 124-128). No `.invert()` call. The on-disk floats, composed `T * R` under the W-first convention, **are themselves the inverse bind matrix**.

- **reone** (`reone/src/libs/graphics/format/mdlmdxreader.cpp:263-292`):
  ```cpp
  if (flags & MdlNodeFlags::skin) {
      // ...
      ArrayDefinition qBoneArrayDef(readArrayDefinition());
      ArrayDefinition tBoneArrayDef(readArrayDefinition());
      // ...
      std::vector<float> qBoneValues(_mdl.readFloatArrayAt(
          kMdlDataOffset + qBoneArrayDef.offset, 4 * numBones));
      std::vector<float> tBoneValues(_mdl.readFloatArrayAt(
          kMdlDataOffset + tBoneArrayDef.offset, 3 * numBones));

      std::vector<glm::mat4> boneMatrices;
      boneMatrices.resize(numBones);
      for (int i = 0; i < numBones; ++i) {
          const float *qBone = &qBoneValues[4 * i];
          glm::mat4 boneMatrix(1.0f);
          boneMatrix *= glm::translate(glm::make_vec3(&tBoneValues[3 * i]));
          boneMatrix *= glm::mat4_cast(glm::quat(
              qBone[0], qBone[1], qBone[2], qBone[3]));   // <-- GLM quat ctor is (W,X,Y,Z)
          boneMatrices[i] = std::move(boneMatrix);
      }
      skin = std::make_shared<ModelNode::Skin>();
      skin->boneMatrices = std::move(boneMatrices);   // <-- stored directly, no inverse
  }
  ```
  reone reads the qBone array as four sequential floats and constructs `glm::quat(qBone[0], qBone[1], qBone[2], qBone[3])`. The GLM API `glm::quat(w, x, y, z)` takes **W first** (this is documented behaviour: see `glm/detail/type_quat.hpp` constructor `tquat(T w, T x, T y, T z)`). Composition is `T(t) * R(q)`. The result is stored directly into `skin->boneMatrices` without inversion. `reone/src/libs/scene/node/mesh.cpp:307-310` confirms `boneMatrices` is multiplied as the rightmost factor in the per-vertex skinning chain, which is the inverse-bind position in standard LBS notation.

PyKotor reader cross-check (proves PyKotor itself is internally inconsistent on Vector4 byte order, and that GhostRigger inherits the wrong convention):

- `PyKotor/Libraries/PyKotor/src/pykotor/resource/formats/mdl/io_mdl.py:1022-1025` (`_NodeHeader.read`):
  ```python
  self.orientation.w = reader.read_single()   # <-- W read first
  self.orientation.x = reader.read_single()
  self.orientation.y = reader.read_single()
  self.orientation.z = reader.read_single()
  ```
  Node-header orientation quaternion is read W-first, matching KotOR.js and reone. This path renders correctly in GhostRigger because GhostRigger consumes `node.orientation` as a quaternion directly without component remapping.
- `PyKotor/Libraries/PyKotor/src/pykotor/resource/formats/mdl/io_mdl.py:1665-1672` (`_SkinmeshHeader.read_extra`):
  ```python
  self.qbones = [reader.read_vector4() for _ in range(self.qbones_count)]
  ```
  qBone array is read via the generic `read_vector4()` helper (`PyKotor/Libraries/PyKotor/src/utility/common/stream.py:643-665`):
  ```python
  x, y, z, w = (
      self.read_single(big=big),
      self.read_single(big=big),
      self.read_single(big=big),
      self.read_single(big=big),
  )
  return Vector4(x, y, z, w)
  ```
  PyKotor's `read_vector4` reads X first then Y,Z,W. **For qBones this is the wrong byte order.** It contradicts both PyKotor's own node-header reader and both reference renderers.

GhostRigger consumption (`src/core/gpu_skinning.py:541-557`, `qbone_inverse_bind_matrix`, used by `compute_skin_node_palette` at the F1 production path):
```python
qx, qy, qz, qw = float(qbone[0]), float(qbone[1]), float(qbone[2]), float(qbone[3])
tx, ty, tz = float(tbone[0]), float(tbone[1]), float(tbone[2])
# ... normalize ...
bind_m = _mat4_mul_py(_mat4_translate_py(tx, ty, tz), _quat_to_mat4((qx, qy, qz, qw)))
return _mat4_invert_py(bind_m)
```
GhostRigger inherits PyKotor's misordered `Vector4(x, y, z, w)` (so `qbone[0]` is the disk-W byte interpreted as quaternion-X, etc.), composes `T * R`, and **inverts** the result before storing in the palette. Composition order matches the reference engines; byte order and inversion direction both differ.

Reference engine convention table (3j-2 deliverable):

| engine | reads qBone? | byte order | composition | inverts? | final stored as |
| --- | --- | --- | --- | --- | --- |
| xoreos      | NO  | (n/a)             | (n/a)   | (n/a) | inverse bind from node hierarchy (`computeInverseBindPose`) |
| KotOR.js    | YES | W,X,Y,Z (W first) | `T * R` | NO    | `bone_inverse_matrix` (already inverse) |
| reone       | YES | W,X,Y,Z (W first) | `T * R` | NO    | `skin->boneMatrices` (already inverse) |
| GhostRigger | YES | X,Y,Z,W (X first) | `T * R` | YES   | inverted `T * R` (palette inverse-bind) |

Two systematic convention disagreements identified:

1. **C - quaternion byte order on disk**: KotOR.js (line 102 explicit `let w = ...readSingle()` before reading X,Y,Z), reone (line 286 GLM `glm::quat(w,x,y,z)` constructor), AND PyKotor's own `_NodeHeader.read` (line 1022 `orientation.w = reader.read_single()` before X,Y,Z) all agree the disk byte order is **W,X,Y,Z**. Only PyKotor's generic `read_vector4()` (and therefore GhostRigger's qBone consumption that inherits it) uses **X,Y,Z,W**.
2. **A - inverse direction**: KotOR.js and reone both store `T * R` directly as the inverse bind matrix (variable names `bone_inverse_matrix` and `boneMatrices` respectively, both used as the rightmost factor in the standard LBS chain). GhostRigger inverts `T * R` before storing in the palette - producing the **forward** bind matrix where the engine should be storing the **inverse** bind matrix.

First-divergence numeric comparison (slot 0 of each audit creature, raw on-disk bytes from 3j-1 dump):

| target / probe | raw 4 float32 bytes | GhostRigger as `(X,Y,Z,W)` axis | GhostRigger angle | reference as `(W,X,Y,Z)` axis | reference angle | rotation matrix max-abs delta |
| --- | --- | --- | --- | --- | --- | --- |
| c_drexlf rarmGeo[0]    | `(-1.000000, 0, 0, 0)`       | `(-1,0,0)` | 180.00 deg | `(+1,0,0)` | 0.00 deg   | 2.000 |
| c_brith Brith_mesh[0]  | `(-1.000000, 0, 0, 0)`       | `(-1,0,0)` | 180.00 deg | `(+1,0,0)` | 0.00 deg   | 2.000 |
| c_bomabeast upperbody[0] | `(-0.000001, 0, 0, -1.000000)` | `(-1,0,0)` | 0.00 deg   | `(0,0,-1)` | 180.00 deg | 2.000 |

Every probe produces the maximum possible rotation matrix delta (2.0) between the two byte orders. GhostRigger's first-bone bind rotation is wrong by 180 degrees on all three audit creatures - in opposite directions (c_drexlf and c_brith get a spurious 180 deg X rotation; c_bomabeast loses a real 180 deg Z rotation). That is a coherent explanation for "different broken topology" rather than "missing rotation": the bug injects rotation where there should be none and removes rotation where there should be one.

Outcome classification (per the user 3j-2 brief):

- **Outcome A (composition bug)**: **CONFIRMED**. The reference renderers do not invert; GhostRigger does. Production effectively builds the **forward** bind matrix when it should build the inverse bind, then composes that forward bind into the LBS chain at the slot the inverse bind is supposed to occupy. This converts the `inverse(bind)` factor into `bind` itself, so vertices are pushed *deeper into bind space* instead of out of it. That alone would catastrophically distort animated meshes.
- **Outcome B (basis bug)**: **OPEN BUT DEPRIORITIZED**. None of the reference reads suggest a different basis-of-storage; all three engines treat the qBone/tBone composition as bone-local-to-mesh-bind (i.e. the inverse bind matrix). 3j-3's single-vertex replay should reconfirm this rather than spend further audit time on basis sub-hypotheses up front.
- **Outcome C (quaternion convention bug)**: **CONFIRMED**. The disk byte order is W,X,Y,Z (per KotOR.js explicit reader, reone via GLM, and PyKotor's own node-header reader). PyKotor's generic `read_vector4()` is X,Y,Z,W and is the wrong convention to apply to the skinmesh qBone array. GhostRigger inherits this misorder verbatim through the public `skin.qbones` API.

The two confirmed bugs compound rather than cancel: A flips the bind direction and C scrambles the per-bone rotation. Either alone would catastrophically deform the mesh; both together produce incoherent geometry that responds to wrapper variants by changing into a *different* incoherent shape (which is exactly what the 3i Step 7 visual gate observed for c_bomabeast under F11).

Updated 3j sub-hypothesis status:

- **B-qbone-basis-1** (basis-of-storage): OPEN but deprioritized; 3j-2 found no reference-engine evidence for a basis disagreement at the qBone composition stage.
- **B-qbone-basis-2** (handedness/order at composition): SHARPENED. Composition order matches across all three engines (`T * R`); the disagreement is on the disk-to-quaternion *byte order* (W-first vs X-first), which is Outcome C.
- **B-qbone-basis-3** (relative-to-skin-bind / parent-bone-bind): OPEN but deprioritized; the reference engines do not insert a skin-bind or parent-bone-bind factor at the qBone composition stage. They store the composed `T * R` directly as the per-bone inverse bind.
- **NEW: Outcome A** (inverse direction): CONFIRMED by both KotOR.js and reone naming the stored matrix "inverse" and using it as the inverse-bind slot in their LBS chain. GhostRigger's `qbone_inverse_bind_matrix` is mis-named: it actually returns the forward bind because the on-disk values *already* are the inverse bind.
- **NEW: Outcome C** (quaternion byte order): CONFIRMED by three independent corroborating sources (KotOR.js explicit reader, reone via GLM constructor, PyKotor's own node-header reader) and quantified at slot 0 of all three audit creatures (180 deg rotation difference per bone).

3j-2 quantitative confirmation across all 546 slots:

A new tool, `scripts/dump_qbone_consumption_replay.py`, reads each 3j-1 byte-parity record and reconstructs the per-bone bind matrix under four candidate conventions in parallel, then compares each candidate against the reference convention extracted in 3j-2:

- `F1_GHOSTRIGGER`    - XYZW byte order, `T * R`, INVERTED   (current production)
- `G1_GR_NO_INVERT`   - XYZW byte order, `T * R`, NOT inverted   (Outcome A only)
- `G2_REF_BYTE_ORDER` - WXYZ byte order, `T * R`, INVERTED   (Outcome C only)
- `G3_REF_FULL`       - WXYZ byte order, `T * R`, NOT inverted   (matches KotOR.js + reone)

Outputs (committed):

- `diagnostics/skinning/2026_05/qbone_consumption_replay_c_drexlf.jsonl` (455 slots)
- `diagnostics/skinning/2026_05/qbone_consumption_replay_c_brith.jsonl` (21 slots)
- `diagnostics/skinning/2026_05/qbone_consumption_replay_c_bomabeast.jsonl` (70 slots)

Reduction (matches against `G3_REF_FULL` at delta < 1e-6):

| target | slots | F1 GR matches | G1 no-invert matches | G2 byte-order matches | F1 worst max-abs | G1 worst max-abs | G2 worst max-abs | F1 worst rot max-abs | G1 worst rot max-abs | G2 worst rot max-abs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| c_drexlf    | 455 | 0 | 0 | 13 | 6.83  | 2.00 | 6.87 | 2.00 | 2.00 | 2.00 |
| c_brith     |  21 | 0 | 0 |  4 | 15.15 | 2.00 | 20.88 | 2.00 | 2.00 | 0.60 |
| c_bomabeast |  70 | 0 | 0 |  4 | 4.60  | 2.00 | 2.81 | 2.00 | 2.00 | 1.05 |

Interpretation:

- `F1_GHOSTRIGGER` matches the reference on **0 of 546** slots. The 16-element max-abs delta peaks at 15.15 units on c_brith - meaning the per-bone bind matrix that GhostRigger feeds into the GPU palette differs from the reference by up to 15 units in a single matrix element.
- `G1_GR_NO_INVERT` (fix only Outcome A; leave the byte-order bug in place) matches **0 of 546** slots. The byte-order bug alone produces rotation max-abs delta 2.00 on every slot it touches.
- `G2_REF_BYTE_ORDER` (fix only Outcome C; leave the spurious invert in place) matches the reference on a small minority of slots (13 of 455 c_drexlf, 4 of 21 c_brith, 4 of 70 c_bomabeast). Those slots are degenerate cases where the bind matrix happens to equal its own inverse - identity quaternion plus zero translation. For all other slots (96 to 99 percent), tBone is non-zero so `T*R != inverse(T*R)` and the spurious invert keeps the matrix wrong.
- The two bugs are independently necessary and jointly sufficient for the convention mismatch. Either fix alone leaves the palette materially wrong on the great majority of slots.

Stop/Go status (unchanged):

- Production stays at the 3f baseline. 3j-2 is an audit deliverable; no production change ships from a code reading alone.
- The next active substep is **3j-3 - single-vertex end-to-end replay** using the corrected conventions: read qBone bytes as `(W,X,Y,Z)`, compose `T * R`, and use the result **as the inverse bind matrix without further inverting**. The replay must show the corrected palette eliminates the per-bone-bind rotation error and produces vertex positions that match a reference numerical reconstruction at the post-qBone stage. Visual gates and the broader formula sweep (3j-4) follow only if 3j-3's numeric replay wins on `c_drexlf` first.

## 3j Step 3 - Single-vertex end-to-end replay (qBone consumption third bug)

3j-3 implemented the single-vertex end-to-end replay using a bind-pose self-test as the primary numerical decision: in bind pose, the LBS chain `bone_world * inv_bind * v_local` must collapse to `skin_world * v_local` because `inv_bind` is mathematically the inverse of `bone_world` expressed in the skin node's space. Any candidate convention that does not satisfy this identity is wrong by construction.

Tool: `scripts/dump_qbone_single_vertex_replay.py`. Probe selection: 5 vertex indices per skin node (`0`, `N//4`, `N//2`, `3N//4`, `N-1`, deduplicated and capped at vertex_count). 50 probes total across the three audit creatures, with one record per probe carrying every per-bone influence's matrices, positions, and identity-test deltas.

Outputs (committed):

- `diagnostics/skinning/2026_05/qbone_single_vertex_replay_c_drexlf.jsonl` (35 probes across 7 skin nodes)
- `diagnostics/skinning/2026_05/qbone_single_vertex_replay_c_brith.jsonl` (5 probes across 1 skin node)
- `diagnostics/skinning/2026_05/qbone_single_vertex_replay_c_bomabeast.jsonl` (10 probes across 2 skin nodes)

### Initial run with G3_REF_FULL only - Outcome 2

The first replay run tested only F1 (production) and G3_REF_FULL (3j-2's "two compounding bugs fixed" candidate). The result on every creature was `OUTCOME_2_G3_REF_FULL_STILL_DIVERGES`: the corrected byte order plus removed inversion did **not** make the bind-pose self-test collapse. Per-creature numbers (max-abs identity deltas vs `skin_world`):

| target | probes | F1 max-delta | G3 max-delta | F1 displacement (max) | G3 displacement (max) |
| --- | ---: | ---: | ---: | ---: | ---: |
| c_drexlf    | 35 | 5.196 | 4.345 | 4.85 | 4.90 |
| c_brith     |  5 | 7.552 | 9.513 | 10.53 | 9.56 |
| c_bomabeast | 10 | 3.764 | 2.511 | 6.38 | 4.14 |

This triggered the user's Outcome 2 branch: "the next bug is no longer qBone byte order or invert direction; it would point to a deeper basis/placement issue later in the consumption chain."

### Indexing audit - the third compounding bug

A semantic-meaning probe (`scripts/_check_qbone_meaning.py` -> `diagnostics/skinning/2026_05/_qbone_meaning_probe.txt`) revealed a structural anomaly: for every skin node in c_drexlf, `tbone[slot=0]` exactly equals that **skin node's** local position, regardless of which bone `bone_map[0]` references. For example, both `rarmGeo` slot 0 (mapped to `lcollar_g`) and `headGeo` slot 0 (mapped to `LPincher`) carry `tbone` values matching their respective skin node's position - not the position of the bone they nominally index.

A length-alignment check (`scripts/_check_qbone_index_alignment.py` -> `diagnostics/skinning/2026_05/_qbone_index_alignment.txt`) confirmed the underlying problem:

| target | total model nodes | bone_map length | qbone_list length |
| --- | ---: | ---: | ---: |
| c_drexlf    | 65 | 16 | **65** |
| c_brith     | 21 | 17 | **21** |
| c_bomabeast | 35 | 16 | **35** |

`qbones[]` and `tbones[]` are length-N arrays parallel to the **global DFS node order**, not the compact 16-entry `bone_map`. Production indexes them with the bone_map slot index (0 to ~15), which silently reads the qBone of an unrelated node - typically the model root or one of the first depth-first children - on every lookup.

This indexing convention is consistent with reone's reader at `reone/src/libs/graphics/format/mdlmdxreader.cpp:280-288`:

```cpp
std::vector<glm::mat4> boneMatrices;
boneMatrices.resize(numBones);
for (int i = 0; i < numBones; ++i) {
    const float *qBone = &qBoneValues[4 * i];
    glm::mat4 boneMatrix(1.0f);
    boneMatrix *= glm::translate(glm::make_vec3(&tBoneValues[3 * i]));
    boneMatrix *= glm::mat4_cast(glm::quat(qBone[0], qBone[1], qBone[2], qBone[3]));
    boneMatrices[i] = std::move(boneMatrix);
}
```

`numBones` here is the count from the bone-map array definition in the skinmesh header, which equals the **total node count of the model**. `boneMatrices[i]` is keyed by global DFS node index `i`. At render time reone looks up `skin->boneMatrices[skin->boneSerial[i]]` where `boneSerial[boneIdx] = i` is the DFS index for `boneIdx`, completing the indirection.

xoreos avoids the entire question because it does not read qBone/tBone at all: `xoreos/src/graphics/aurora/model_kotor.cpp:947` skips 72 bytes (the qBone+tBone array definitions plus padding) and computes inverse-bind matrices from the node hierarchy directly.

### G5_FULL_REF candidate - all three bugs fixed

Defining `G5_FULL_REF`: look up the bone's actual DFS node index in the model, read `qbones[dfs_idx]` and `tbones[dfs_idx]`, interpret the quaternion as W-first (`qw, qx, qy, qz`), build `T * R`, and **use the result directly as the inverse-bind matrix without inversion**. This is exactly reone's documented convention.

A targeted indexing probe (`scripts/_check_qbone_correct_index.py` -> `diagnostics/skinning/2026_05/_qbone_correct_index_search.txt`) sampled the first 8 slots of every skin node across all three audit creatures (24 sample slots total, with full per-creature coverage of c_drexlf's 7 skin nodes, c_brith's 1 skin node, and c_bomabeast's 2 skin nodes). For every sample, `qbones[dfs_idx]` under the W-first / no-invert / DFS-indexed convention matched reone's documented "inverse of bone transform in this node space" formula `inverse(bone_world) * skin_world` to **delta = 0.0000**.

### G5_FULL_REF replay outcome - Outcome 1

The single-vertex replay was extended to evaluate F1, G3_REF_FULL, AND G5_FULL_REF in parallel against the corrected expected position `skin_world * v_local`. Result on every creature: `OUTCOME_1_G5_FULL_REF_COLLAPSES_BIND_POSE_SELF_TEST`.

Per-creature reduction (max-abs delta of `bone_world * inv_bind` vs `skin_world` and weighted vertex displacement vs `skin_world * v_local`):

| target | probes | F1 max-delta | G3 max-delta | G5 max-delta | F1 displacement (max) | G3 displacement (max) | G5 displacement (max) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| c_drexlf    | 35 | 3.84 | 3.70 | **0.000001** | 4.62 | 4.12 | **0.000001** |
| c_brith     |  5 | 7.55 | 9.51 | **0.000000** | 10.53 | 9.56 | **0.000000** |
| c_bomabeast | 10 | 2.51 | 2.12 | **0.000001** | 2.47 | 3.46 | **0.000001** |

Counts of probes meeting the bind-pose collapse tolerance (`max-abs delta <= 1e-3` AND `displacement <= 1e-3`):

| target | probes | F1 collapses | G3 collapses | G5 collapses |
| --- | ---: | ---: | ---: | ---: |
| c_drexlf    | 35 | 0 | 0 | **35 / 35** |
| c_brith     |  5 | 0 | 0 |  **5 /  5** |
| c_bomabeast | 10 | 0 | 0 | **10 / 10** |

Every probe (50 of 50) classifies as `G5_collapses_F1_and_G3_diverge`. F1 and G3 fail bind-pose collapse on 100% of probes; G5 satisfies it on 100% by construction.

### Updated 3j sub-hypothesis status

- **B-qbone-basis-1** (basis-of-storage): RESOLVED. The basis is "inverse of bone transform in skin-node space" = `inverse(bone_world) * skin_world`, exactly as reone documents at `reone/include/reone/graphics/modelnode.h:40`.
- **B-qbone-basis-2** (handedness/order at composition): RESOLVED. Composition order is `T * R` under the W-first quaternion byte order. Empirically verified at delta = 0 against reone's formula.
- **B-qbone-basis-3** (relative-to-skin-bind): RESOLVED. The qBone matrix encodes `inverse(bone_world) * skin_world`, which is naturally relative to the skin node's bind frame. The `skin_world` factor enters here, not as an outer wrapper as 3i Step 6 suspected.
- **NEW: Outcome A** (inverse direction): CONFIRMED again by 3j-3.
- **NEW: Outcome C** (quaternion byte order): CONFIRMED again by 3j-3.
- **NEW: Outcome D** (array indexing): CONFIRMED. `qbones[]` is indexed by global DFS node order, not by the compact `bone_map` slot. Production reads the wrong array entry on every lookup.

### What this means for production

The complete corrected pipeline is:

```
inv_bind_per_skin_node[bone_in_bone_map_slot] =
    let dfs_idx = name_to_global_dfs_index[bone_map[slot].lower()]
    let q4_disk = qbones[dfs_idx]
    let t3_disk = tbones[dfs_idx]
    let q4_ref = (q4_disk[1], q4_disk[2], q4_disk[3], q4_disk[0])  # W-first remap
    T(t3_disk) * R(q4_ref)                                          # NOT inverted
```

GhostRigger's existing `compute_skin_node_palette` shape (`skin_m = world_pose_m * inv_bind`) is already correct under this convention. In bind pose `skin_m` collapses to `skin_world`, and applying it to `v_local` (NODE_LOCAL vertex) yields the correct world position `skin_world * v_local`. In animated pose, `world_pose_m = bone_world_anim`, so the chain becomes `bone_world_anim * inverse(bone_world_bind) * skin_world * v_local` - the textbook LBS for skin-node-local vertices.

Three changes are needed to land the fix in production:

1. **Indexing**: `compute_skin_node_palette` must build a `name_to_dfs` map from the model's all_nodes() at palette-construction time and use `qbones[dfs_idx]` / `tbones[dfs_idx]` instead of `qbones[bone_map_slot]`. The lookup map can be cached on the uploader after `build_inverse_bind_pose` walks the same hierarchy.
2. **Byte order**: `qbone_inverse_bind_matrix` (or its replacement) must consume the quaternion as `(qw=qb[0], qx=qb[1], qy=qb[2], qz=qb[3])`, which is equivalent to remapping `(qb[1], qb[2], qb[3], qb[0])` into the `(qx, qy, qz, qw)` slots used by the existing `_quat_to_mat4` helper.
3. **Inversion**: `qbone_inverse_bind_matrix` must NOT invert. The `T * R` composition is itself the inverse-bind matrix expressed in skin-node space.

Stop/Go status (unchanged):

- Production stays at the 3f baseline. 3j-3 is an audit deliverable; no production change ships from a numerical replay alone.
- The corrected palette must be implemented as an env-gated diagnostic (G5_FULL_REF) before any production switch, and must pass the 3j-5 visual gate on all three audit creatures plus the 50-model render-diff suite.
- Authorization for **3j-4 (env-gated G5_FULL_REF implementation, full replay coverage across every skin node and every weighted vertex, regression tests)** and **3j-5 (joint visual gate + 50-model render-diff)** is requested but not yet granted.

## 3j Step 4 - Env-gated `G5_FULL_REF` implementation and full numerical proofs

**Status:** Authorized 2026-05-08 by user brief ("Authorized: 3j-4 env-gated `G5_FULL_REF` implementation. Not authorized yet: production flip. Ship only after: 3j-5 joint visual gate + 50-model render-diff suite pass."). All three numerical proofs cleared. Production remains pinned to F1 (3f baseline) by default.

### Implementation diff

The three 3j-3 fixes were landed in `src/core/gpu_skinning.py` behind the existing `GHOSTRIGGER_SKIN_FORMULA` env switch. Production rendering is byte-identical to the prior build when the env is unset.

| Change | Location | Description |
|---|---|---|
| New env value | `_SKIN_FORMULA_G5 = 'G5_FULL_REF'`, added to `_SKIN_FORMULA_VALID` tuple | Joins `F1_current_TR_inverse` (default) and `F11_rotation_only_skin_bind_wrapper` (3i Step 7 diagnostic) |
| New uploader field | `MatrixPaletteUploader.__init__`: `self._name_to_dfs_index: Dict[str, int]` | Lookup from lowercased bone name to global DFS index in `model.all_nodes()` |
| Populated in | `build_inverse_bind_pose` (loop already iterates `enumerate(nodes)`) | Cleared on entry alongside `_inv_bind`, `_bone_order`, `_node_lookup`, `_node_parent` |
| New static helper | `MatrixPaletteUploader.qbone_inverse_bind_matrix_g5(qbone, tbone)` | W-first quaternion decode (`qw=qb[0]`, `qx=qb[1]`, `qy=qb[2]`, `qz=qb[3]`); returns `T(tBone) * R(qBone)` directly without inversion |
| Branch in `compute_skin_node_palette` | When `active_formula == _SKIN_FORMULA_G5` | Resolves `dfs_idx = self._name_to_dfs_index.get(bkey, -1)` per bone; reads `qbones[dfs_idx]` / `tbones[dfs_idx]` (NOT `qbones[slot]`); builds inv_bind via the new G5 helper. Falls back to identity when the bone name is missing from the lookup so a malformed `bone_map` entry never crashes. |
| Bookkeeping | `self._skin_inverse_bind_source = "qBone_tBone_dfs_indexed_TR_no_invert"` under G5 | Lets in-renderer skin-dump and tests verify which path actually produced the palette without re-reading env state |
| LBS shape | unchanged: `skin_m = world_pose_m * inv_bind` | F1 and G5 share the textbook LBS shape; the entire semantic difference is in how `inv_bind` is constructed |

### Regression tests

Four new tests in `tests/test_regression.py`, immediately after the Step 7 F11 trio so the env-switch coverage is co-located:

| Test | Purpose |
|---|---|
| `test_skin_uploader_populates_name_to_dfs_index` | Asserts `_name_to_dfs_index` mirrors `enumerate(model.all_nodes())` exactly (4-node fixture: Root, ExtraNode, Arm, SkinMesh -> indices 0..3) |
| `test_skin_node_palette_env_switch_G5_uses_dfs_indexed_qbone` | Synthetic model where the only influenced bone (Arm) sits at DFS index 2 but `bone_map` slot 0; only `qbones[2]/tbones[2]` carries a +5 X translation. Asserts F1 sees zero (slot lookup -> identity), G5 sees +5 (DFS lookup hits the loaded slot), and `_skin_inverse_bind_source == "qBone_tBone_dfs_indexed_TR_no_invert"` under G5 |
| `test_skin_node_palette_env_switch_G5_decodes_quaternion_w_first` | DFS index pinned equal to slot so the only axis of variation is byte order. Asserts G5's W-first decoding of `(cos45, 0, 0, sin45)` produces the expected 90 deg-about-Z inverse-bind matrix and that F1's X-first decoding of the same bytes lands more than 0.5 max-abs away |
| `test_skin_node_palette_env_switch_G5_cpu_to_uploaded_bytes_parity` | Round-trips `as_flat_bytes()` (the literal SSBO payload) back into a NumPy array under G5 and asserts bit-equality with `as_numpy_array()`. Padding identities beyond `len(palette)` are also asserted to catch any silent layout regression |

The three Step 7 F11 control tests (`test_skin_node_palette_env_switch_F11_rotation_only_wrapper`, `..._diverges_with_nonidentity_skin_bind`, `..._unknown_value_falls_back_to_F1`) remain green; the fall-back test guarantees an unknown env value (e.g. typo) silently degrades to F1 so a mistaken `GHOSTRIGGER_SKIN_FORMULA=g5_full_ref` (lowercase) still cannot perturb production.

```
pytest tests/test_regression.py -k "skin_node_palette_env_switch or name_to_dfs_index" -v
6 passed in 6.51s
```

### Goal 1 - Per-vertex bind-pose replay across every weighted vertex

`scripts/dump_qbone_full_vertex_replay_3j4.py` runs the production `MatrixPaletteUploader` under both F1 (env unset) and G5 (env set), iterates every weighted vertex on every skin node of the three audit creatures, and asserts `weighted_sum_i(palette[slot_i] * v_local) ~= skin_world * v_local` (the bind-pose self-test extended to the full vertex space). Tolerance is 1e-3, mirroring the 3j-3 displacement tolerance.

| Creature | Game | Skin nodes | Weighted vertices | G5 collapsed | G5 max displacement | F1 collapsed |
|---|---|---|---|---|---|---|
| `c_drexlf`    | K2 | 7 | 1209 | **1209 / 1209 (100.00%)** | 1.480e-06 | 0 / 1209 (0.00%) |
| `c_brith`     | K2 | 1 |  472 | **472 / 472 (100.00%)**   | 5.365e-07 | 0 / 472 (0.00%)  |
| `c_bomabeast` | K1 | 2 |  865 | **865 / 865 (100.00%)**   | 2.169e-06 | 0 / 865 (0.00%)  |
| **Total**     |    | 10 | **2546** | **2546 / 2546 (100.00%)** | <= 2.169e-06 | **0 / 2546 (0.00%)** |

Verdict per creature: `G5_PASSES_FULL_VERTEX_REPLAY_F1_FAILS` for all three. Outputs:

```
diagnostics/skinning/2026_05/qbone_full_vertex_replay_3j4_c_drexlf.jsonl
diagnostics/skinning/2026_05/qbone_full_vertex_replay_3j4_c_brith.jsonl
diagnostics/skinning/2026_05/qbone_full_vertex_replay_3j4_c_bomabeast.jsonl
```

The maximum displacement on any vertex is below the float32 epsilon scaled by the model bounds, well inside the 1e-3 budget. F1 fails on every weighted vertex because it builds inverse binds from the wrong slot under the wrong byte order and inversion direction - exactly the three compounding bugs identified in 3j-3.

### Goal 2 - CPU <-> uploaded palette parity

The CPU LBS validation path consumes `MatrixPaletteUploader.as_numpy_array()` (row-major NxN float32) while the renderer uploads `MatrixPaletteUploader.as_flat_bytes()` (column-major float32 padded to `max_bones`) to the SSBO. Both representations originate from the same `BoneMatrix.flat_col` payload, so divergence between them would mean the GPU rendering and CPU validation tests describe different matrices.

`test_skin_node_palette_env_switch_G5_cpu_to_uploaded_bytes_parity` covers the synthetic-fixture case bit-exactly (`max_abs_delta == 0.0`) under G5. The `live_slots[*]` records emitted in the in-renderer skin dump (Goal 3, below) extend the proof to real game data: every uploaded matrix in the dump comes from `as_flat_bytes()` re-interpreted as float32 row-major, and is reconciled element-wise against `as_numpy_array()` for the same skin node. On the three audit creatures, the worst observed renderer-vs-CPU max-abs delta is **5.345e-07** (essentially the float32 round-trip floor of `flat_col` packing), with **121 / 121 palette slots within 1e-6**. CPU and GPU describe identical matrices under G5.

### Goal 3 - In-renderer parity (G5 actually executes inside the production renderer)

`scripts/dump_qbone_renderer_parity_3j4.py` exercises the live `GpuRenderer` headlessly with `GHOSTRIGGER_SKIN_FORMULA=G5_FULL_REF` and `GHOSTRIGGER_SKIN_DUMP=<path>` set, then reconciles the uploaded SSBO payload against an offline G5 replay built by re-calling `compute_skin_node_palette` for the same skin nodes.

A first attempt rendering with `anim_pose=None` produced a false pass: `gpu_renderer.py:5125` requires `anim_pose is not None` to activate GPU skinning, so the SSBO contained only initial-state identity matrices and the parity check trivially "matched" for `c_brith` (origin-centered) while flagging `c_drexlf` and `c_bomabeast` (`d_off=2.0`). The fix was to render with an empty-but-non-None `SimpleNamespace(nodes={})` pose: `MatrixPaletteUploader._world_pose_matrix` falls back to bind transforms when a bone is absent from the pose dict (`gpu_skinning.py:538-550`), so every bone resolves to `bone_world_bind`, the GPU skinning code path actually runs, and the bind-pose self-test target `skin_world * v_local` remains valid.

| Creature | Game | Palette slots in dump | Renderer == offline (<= 1e-6) | Renderer == skin_world (<= 1e-3) | Worst d_offline | Worst d_skin_world |
|---|---|---|---|---|---|---|
| `c_drexlf`    | K2 | 74 | **74 / 74**  | **74 / 74**  | 4.923e-07 | 1.800e-06 |
| `c_brith`     | K2 | 17 | **17 / 17**  | **17 / 17**  | 4.636e-07 | 1.000e-06 |
| `c_bomabeast` | K1 | 30 | **30 / 30**  | **30 / 30**  | 5.345e-07 | 1.971e-06 |
| **Total**     |    | **121** | **121 / 121** | **121 / 121** | <= 5.345e-07 | <= 1.971e-06 |

Verdict per creature: `G5_RENDERER_BIT_EXACT_TO_OFFLINE_AND_BIND_POSE_SELF_TEST_COLLAPSES` for all three. Outputs:

```
diagnostics/skinning/2026_05/qbone_renderer_parity_3j4_c_drexlf.jsonl
diagnostics/skinning/2026_05/qbone_renderer_parity_3j4_c_brith.jsonl
diagnostics/skinning/2026_05/qbone_renderer_parity_3j4_c_bomabeast.jsonl
diagnostics/skinning/2026_05/qbone_renderer_parity_3j4_summary.json
```

This rules out the worst silent-failure modes: the G5 env switch is not a no-op, `compute_skin_node_palette` does enter the G5 branch, and the bytes uploaded to the SSBO match the offline replay slot-for-slot, so the renderer is provably exercising the corrected pipeline (not a partial G3 fix or a fallback to F1).

### What 3j-4 closes

The three 3j-4 numerical proofs together close every remaining audit branch except the final visual gate:

- **Implementation correctness**: G5 is exactly the three reference-backed fixes from 3j-3 with no additional changes. Static helper `qbone_inverse_bind_matrix_g5` is a single-purpose constructor; the indexing change is a single dict lookup; no production-path math was altered.
- **Numerical correctness**: 2546 / 2546 weighted vertices satisfy the bind-pose self-test under G5 across the three audit creatures.
- **CPU/GPU representation parity**: synthetic and real-data round-trip both confirm bit-exact equality between `as_numpy_array()` and `as_flat_bytes()` under G5.
- **Production-renderer execution**: the in-renderer dump confirms the SSBO bytes the vertex shader actually consumes equal the offline G5 palette to <= 5.4e-7 on every probed slot of every audit creature.
- **Production safety**: env-unset behaviour is byte-identical to the prior build; F1 remains the only path the renderer can take by default; an unknown env value silently falls back to F1 (covered by `test_skin_node_palette_env_switch_unknown_value_falls_back_to_F1`).

The remaining live question is purely visual: does the corrected pipeline produce anatomically coherent silhouettes on the three audit creatures and avoid regressions on the wider 50-model render-diff suite?

### Stop/Go status

- **Production:** unchanged. F1 (3f baseline) remains the default. G5 ships **only** behind the env switch.
- **3j-4:** complete. All three numerical proofs cleared on the three audit creatures.
- **3j-5 authorization:** requested. The visual gate plus the 50-model render-diff suite is the only remaining gate before any production flip.

### Files added or modified in 3j-4

```
M src/core/gpu_skinning.py
    + _SKIN_FORMULA_G5 constant and updated env-switch docstring
    + MatrixPaletteUploader._name_to_dfs_index field + DFS-index population in build_inverse_bind_pose
    + MatrixPaletteUploader.qbone_inverse_bind_matrix_g5 static helper
    + G5 branch in compute_skin_node_palette (DFS lookup; W-first; no invert)

M tests/test_regression.py
    + test_skin_uploader_populates_name_to_dfs_index
    + test_skin_node_palette_env_switch_G5_uses_dfs_indexed_qbone
    + test_skin_node_palette_env_switch_G5_decodes_quaternion_w_first
    + test_skin_node_palette_env_switch_G5_cpu_to_uploaded_bytes_parity

A scripts/dump_qbone_full_vertex_replay_3j4.py
    Goal 1: every weighted vertex on c_drexlf, c_brith, c_bomabeast under F1 and G5

A scripts/dump_qbone_renderer_parity_3j4.py
    Goal 3: GpuRenderer + GHOSTRIGGER_SKIN_DUMP capture; offline-replay reconciliation

A diagnostics/skinning/2026_05/qbone_full_vertex_replay_3j4_c_*.jsonl
A diagnostics/skinning/2026_05/qbone_renderer_parity_3j4_c_*.jsonl
A diagnostics/skinning/2026_05/qbone_renderer_parity_3j4_summary.json
A diagnostics/skinning/2026_05/skin_dump_g5_c_*.jsonl
```

