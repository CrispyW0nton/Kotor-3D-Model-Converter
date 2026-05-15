# Visual And Performance Audit - 2026-05-06

This is a diagnostic-only snapshot for the remaining K1/K2 visual and performance issues after the owned MDL reader migration. No production code changes were made during this audit.

## Scope

Target models:

- K2 creatures: `c_bomabeast`, `c_brith`, `c_drexlf`, `c_jawa`, `c_kath`
- Corrected K2 resrefs from local install: `c_condrdboss` for the wardroid boss, `c_ithorian` for Ithorian/Lthorian screenshots
- K2 module controls: `101perc`, `101perd`
- K1 module control: `m03aa_05a`

The originally named `c_condrdaboss` and `c_lthorian` were not present under those exact resrefs in the local K2 install.

## Pipeline Classification

`compare_model_pipelines()` classified all resolved target models as structurally clean where the model exists. The loadable models matched raw PyKotor node counts, geometry counts, transforms, texture names, and bone-map order.

Resolved structural status:

- `k2:c_bomabeast` - match, 0 discrepancies, 2 skin nodes, normalized weights, no out-of-range influences
- `k2:c_brith` - match, 0 discrepancies, 1 skin node, bonemap overflow resolved to 17 slots, no out-of-range influences
- `k2:c_drexlf` - match, 0 discrepancies, 7 skin nodes, no out-of-range influences, but diffuse texture `c_drex01` did not resolve
- `k2:c_jawa` - match, 0 discrepancies, 4 skin nodes, no out-of-range influences
- `k2:c_kath` - match, 0 discrepancies, 3 skin nodes, no out-of-range influences
- `k2:101perc` / `k2:101perd` - match, 0 discrepancies
- `k1:m03aa_05a` - match, 0 discrepancies

Conclusion: the current failures are not loader parity regressions. They are renderer, animation application, texture resolution, and throughput issues.

## Symptom 1 - Transparency / Missing Surfaces

Measured alpha metadata did not show a broad loader-side alpha leak. For the probed Peragus and creature nodes, opaque geometry had:

- `transparency_hint = 0`
- `alpha = 1.0`
- `txi_blending = 0`
- `txi_wateralpha = 1.0`

Examples:

- `101perc` / `101perd` module meshes are opaque and only carry `txi_alpha_test = 0.5`.
- `c_brith` textured body and wing proxy nodes are opaque in loaded metadata.

Likely classification: renderer-level.

Highest-probability next check: GPU pass classification and depth/OIT state, not loader metadata. The current node metadata does not explain semi-transparent walls or a semi-transparent `c_brith` body by itself.

## Symptom 2 - Texture Wrapping / Seams

No TXI clamp data was found for the primary creature textures in the probed set:

- `c_jawa01` - decoded, no TXI text
- `c_khounda01` / `c_khounda02` - decoded, no TXI text
- `c_ithorian01` - decoded, no TXI text

The more suspicious evidence is the presence of many null-textured, non-skin `_g` proxy meshes with extreme UV ranges on creature models. Examples:

- `c_jawa:torso_g` has UV range about `u=-12.86..12.86`, `v=-9.294..4.43`
- `c_jawa:head_g` has UV range about `u=-6.769..6.769`, `v=-4.809..9.422`
- `c_drexlf` has multiple null-textured proxy nodes with similarly large UV ranges

The GPU renderer contains an `_is_deform_helper()` filter that should skip non-skin `_g` nodes. If the screenshot artifacts show blocky seams or ghost geometry, verify that this filter is active in the exact render path used by the GUI and that cached node classification is invalidated correctly when models change.

Likely classification: render-filter or sampler-state path, not TXI parser loss for the probed textures.

## Symptom 3 - Broken Animation / Detached Rig

Skin metadata is clean for the probed animated creatures:

- `c_bomabeast`: `upperbody` and `lowerbody` both have qBone/tBone length 35, skin data matching vertex count, no zero-weight vertices
- `c_brith`: `Brith_mesh` has qBone/tBone length 21, skin data matching vertex count, no zero-weight vertices
- Weight sums are normalized to approximately 1.0 for both models

Transform diagnosis found the key behavioral difference:

- `c_bomabeast` skin nodes have a non-identity local transform: position `(0, -1.25, 0.72)`, rotation approximately `(0, 0, 1, 0)`
- The renderer intentionally treats skin VBO bind-pose vertices as raw model-root skin inputs and returns identity from `_node_world_transform()` for those skin nodes
- Bone/proxy trimesh nodes still use full parent-chain transforms

This can visually present as “green rig visible / mesh detached” if the debug skeleton/proxy overlay uses rigid node transforms while the skinned mesh uses raw skin coordinates and the live palette does not reconcile the skin-node bind transform.

Likely classification: animation/render skinning path, not bone-map overflow or raw weight corruption.

Next check: compare the GPU palette matrices for `c_bomabeast` against the xoreos/KotOR.js bind-pose formula, especially the skin-node bind transform and its inverse.

## Symptom 4 - Grey / Untextured K2 Creatures

This split into two cases:

- `c_condrdboss` resolves and decodes its texture `c_condrdboss` successfully at `1024x1024`. Its TXI includes `bumpmaptexture C_CONDRDBOSSB`, `bumpyshinytexture CM_baremetal`, and `clamp 1`.
- `c_drexlf` loads structurally, but its referenced diffuse texture `c_drex01` does not resolve through the current texture search path.

Likely classification:

- `c_drexlf`: texture resolution / resource alias issue. The model references `c_drex01`, while nearby installed model resrefs include `c_bosdrexl`, `c_drexl`, and `c_drexlf`; follow texture aliases or appearance rows.
- `c_condrdboss`: not a missing diffuse texture. If it renders grey, inspect env/bump/specular handling and fallback binding, because diffuse decode succeeds.

## Symptom 5 - K1 Module Performance

A headless CPU-render measurement did not reproduce a hard load failure, but it did show K1 module rendering is materially slower than the K2 controls in this small sample:

- `k1:m03aa_05a`: 24 nodes, 15 mesh nodes, load about 2181 ms on first install scan, mean 512px still render about 62 ms
- `k2:101perc`: 5 nodes, 3 mesh nodes, mean render about 12 ms
- `k2:101perd`: 7 nodes, 3 mesh nodes, mean render about 12 ms
- `k2:c_brith`: 21 nodes, 18 mesh nodes, mean render about 12 ms

The first K1 load includes install/resource indexing, so it should not be treated as pure model parse time. The render delta is still real for this path.

Likely classification: renderer throughput. The audit did not yet isolate whether the GUI performance crisis is GPU path VBO rebuild, transform traversal, texture lookup, or scene/UI overhead.

Next check: instrument the GUI/GPU render loop with per-frame counters for VBO build/reuse, transform cache hits, draw-call count, node classification cache hits, sort time, texture upload/cache hits, and GL state changes.

## Recommended Fix Order

1. Add targeted GPU render instrumentation first. The metadata is not enough to explain transparency or K1 throughput, so the next change should measure draw-pass classification and cache churn.
2. Fix `c_drexlf` texture resolution. It is a concrete missing diffuse texture case and should be straightforward to trace through texture lookup/aliases.
3. Audit skin palette math for `c_bomabeast`. The skin data is valid; the bug is likely in how the skin-node bind transform is incorporated into GPU/CPU animation output.
4. Verify `_g` proxy filtering in the live GUI render path. The proxy mesh evidence maps closely to the seam/block artifact family.
5. Only then adjust alpha/OIT behavior. Current loaded alpha metadata does not justify changing loader fields.

## Artifacts Generated

- Targeted pipeline classification was run via `kotormcp.tools.ghostrigger_tools`.
- Material/TXI/texture decode probes were run for the resolved target models.
- Transform diagnostics were run with `scripts/diagnose_transforms.py` for `c_bomabeast` and `c_brith`.
- Headless render timings were measured with `FrameRenderer.render_still()`.
