# custom_mixamo_a1 Forensics

Date: 2026-05-20

## Summary

`custom_mixamo_a1` is a real animation in the active K1 `S_Male01` resource
resolution path. It is not a transient GhostRigger cache artifact.

The clip comes from the local KOTOR install's `Override\s_male01.mdl`, not from
the stock/core `S_Male01` in `chitin.key`. The same install also contains
`patches\custom-animation-smoke-test.dll`, which embeds the string
`custom_mixamo_a1` and references `custom-animation-core.dll`. No matching
GhostRigger source, export log, or tracked repo artifact was found that explains
how the clip was authored or injected.

Per the Sprint 1 stop condition, this is an unknown/non-GhostRigger provenance
finding. Do not use `custom_mixamo_a1` as Test Case 0 without a human design
call.

## MCP Ground Truth Checked

MCP calls:

- `ghostrigger_list_retarget_animations(game="k1", resref="S_Male01")`
- `kotor_find_resource(game="k1", query="s_male01", all_locations=true)`
- `ghostrigger_model_info(game="k1", resref="S_Male01")`
- `kotor_extract_resource(game="k1", resref="s_male01", restype="mdl/mdx", source="OVERRIDE")`
- `kotor_extract_resource(game="k1", resref="s_male01", restype="mdl/mdx", source="CHITIN")`

Resolved locations:

| Source | MDL bytes | MDX bytes | Animation count |
|---|---:|---:|---:|
| `OVERRIDE\s_male01` | 336,824 | 40,448 | 13 |
| `CHITIN/core s_male01` | 325,037 | 42,424 | 12 |

The only added animation in the override resource is `custom_mixamo_a1`.

## Local Search Results

Search target:

- `Logs/`
- `Override/` under the repo when present
- `exports/`
- `diagnostics/`
- `knowledge_base/`
- `src/`
- `tests/`
- `scripts/`
- `C:\Program Files (x86)\Steam\steamapps\common\swkotor`

Relevant hits:

- `C:\Program Files (x86)\Steam\steamapps\common\swkotor\Override\s_male01.mdl`
- `C:\Program Files (x86)\Steam\steamapps\common\swkotor\patches\custom-animation-smoke-test.dll`

The smoke-test DLL contains these embedded strings:

- `custom_mixamo_a1`
- `custom-animation-core.dll`
- `RegisterAnimationWithId`
- `MapResolverAnimation`
- `LookupAnimationId`
- `LookupAnimationNameById`
- `[CustomAnimationSmokeTest] Installed wildcard mapping family=any keys=(*,*) -> %s / id %u`

No GhostRigger Python source or log explains this clip's creation.

## File Metadata

Installed override files:

| File | Last write time |
|---|---|
| `swkotor\Override\s_male01.mdl` | 2026-05-20 11:16:48 |
| `swkotor\Override\s_male01.mdx` | 2026-05-20 11:16:48 |
| `swkotor\patches\custom-animation-core.dll` | 2026-05-20 11:20:04 |
| `swkotor\patches\custom-animation-smoke-test.dll` | 2026-05-20 11:20:04 |

Extracted resource hashes:

| Extract | SHA-256 |
|---|---|
| `diagnostics/retargeting/custom_mixamo_a1/override_s_male01.mdl` | `EE696EEF42375EA8CC32A99DBD3BBDA96E0647DE6877F3EF6615229FD0E641FF` |
| `diagnostics/retargeting/custom_mixamo_a1/override_s_male01.mdx` | `BCB1F54BAC41F0C15FEEAEBE00A08065641C51E56FA00D6D0350B55F23E7C233` |
| `diagnostics/retargeting/custom_mixamo_a1/core_s_male01.mdl` | `80C8DBCF5CDD7F1259F3BF164A95A60199B44ECD09BE5B37DDB2DF261A2565DF` |
| `diagnostics/retargeting/custom_mixamo_a1/core_s_male01.mdx` | `A219744E0443EFCCB82974675DEB340719E3679D92EBA5B1567C18627E89D8D1` |

## Animation Block Summary

`custom_mixamo_a1` facts from GhostRigger's loader:

| Field | Value |
|---|---|
| Length | `1.0` seconds |
| Transition time | `0.15000000596046448` seconds |
| Animation root | `S_Male01` |
| Events | `0` |
| Animated nodes | `30` |
| Total controller key rows | `670` |
| Controller types | `30` orientation controllers, `1` position controller |

The clip is a compact full-body humanoid animation, not a hook-only or partial
facial clip. It animates pelvis translation plus orientation on spine, neck,
head, arms, legs, feet, and simple finger/thumb nodes.

Animated node coverage:

| Node | Controllers |
|---|---|
| `pelvis_g` | position `26`, orientation `26` |
| `torso_g` | orientation `26` |
| `torsoupr_g` | orientation `26` |
| `necklwr_g` | orientation `26` |
| `neck_g` | orientation `26` |
| `head_g` | orientation `26` |
| `rcollar_g` | orientation `26` |
| `rbicep_g` | orientation `26` |
| `rforearm_g` | orientation `90` |
| `rhand_g` | orientation `26` |
| `lcollar_g` | orientation `26` |
| `lbicep_g` | orientation `26` |
| `lforearm_g` | orientation `26` |
| `lhand_g` | orientation `26` |
| `rthigh_g` | orientation `26` |
| `rshin_g` | orientation `26` |
| `rfoot_g` | orientation `26` |
| `rfoott_g` | orientation `26` |
| `lthigh_g` | orientation `26` |
| `lshin_g` | orientation `26` |
| `lfoot_g` | orientation `26` |
| `lfoott_g` | orientation `26` |
| `rafngrb_g`, `rafngrt_g`, `rthumbb_g`, `rthumbt_g` | orientation `1` each |
| `lafngrb_g`, `lafngrt_g`, `lthumbb_g`, `lthumbt_g` | orientation `1` each |

Core skeleton coverage:

- Existing checked core nodes: `23`
- Existing checked core nodes animated by `custom_mixamo_a1`: `17`
- Hooks such as `headhook`, `rhand`, `lhand`, `handconjure`, and `impact_bolt`
  exist in the model but are not directly animated, which is normal for
  attachment nodes that inherit from animated parents.

## Artifacts Written

Diagnostic artifacts:

- `diagnostics/retargeting/custom_mixamo_a1/S_Male01_inspection_game_dir.json`
- `diagnostics/retargeting/custom_mixamo_a1/S_Male01_inspection.json`
- `diagnostics/retargeting/custom_mixamo_a1/S_Male01_core_inspection.json`
- `diagnostics/retargeting/custom_mixamo_a1/custom_mixamo_a1_summary.json`
- `diagnostics/retargeting/custom_mixamo_a1/override_s_male01.mdl`
- `diagnostics/retargeting/custom_mixamo_a1/override_s_male01.mdx`
- `diagnostics/retargeting/custom_mixamo_a1/core_s_male01.mdl`
- `diagnostics/retargeting/custom_mixamo_a1/core_s_male01.mdx`

Legacy binary extracts that had accidentally landed under
`knowledge_base/retargeting/audits/` were moved to:

- `diagnostics/retargeting/custom_mixamo_a1/legacy_audit_extracts/`

## Conclusion

`custom_mixamo_a1` is on disk in the active KOTOR Override resource. It was not
found in the stock/core `S_Male01`, and it is accompanied by custom animation
resolver DLLs in the KOTOR install's `patches` directory. The best current
provenance read is "external smoke-test/custom-animation patch artifact," not
"known GhostRigger-authored retarget output."

Sprint 1 should halt before Day 2 until one of these decisions is made:

1. Treat `custom_mixamo_a1` as an external reference only, remove it from the
   Day 1 test-case path, and proceed with a clean GhostRigger-authored clip.
2. Bless the installed override and smoke-test DLL as intentional local test
   fixtures, document their owner/source, and keep them as Test Case 0.
3. Restore a clean KOTOR `Override` state before sampling supermodel chains so
   Sprint 1 starts from unmodified stock resources.

## Resolution (2026-05-20, design call)

Classification: External Patch Manager artifact. Not GhostRigger's concern.

Decision: Isolate, do not sanitize. The live KOTOR install belongs to other
projects, including the Patch Manager. GhostRigger does not modify it.

Action taken:

1. Stood up a private test corpus at `tests/fixtures/kotor_stock/`, populated
   directly from KOTOR BIF archives and bypassing `Override/` entirely.
2. Added `scripts/extract_stock_corpus.py` for reproducibility.
3. Redirected Sprint 1 Day 2-8 test planning to the corpus instead of the live
   install.
4. Added `EXTERNAL_ANIMATION_PATTERNS` and `filter_stock_animations()` for tests
   that legitimately need to probe the live install, so `custom_mixamo_a1` and
   future external artifacts are tolerated, not asserted-absent.
5. Left the live KOTOR install completely untouched.

Day 1 verdict: NOT Test Case 0. Sprint 1 proceeds with the isolated stock corpus
as ground truth. The live install is observed but never modified by GhostRigger.

Future-proofing: When the Patch Manager dev tests GhostRigger's reverse-path
output in the live install, that is their decision about their install.
GhostRigger ships a candidate MDL pair; the consumer decides how to deploy it.
