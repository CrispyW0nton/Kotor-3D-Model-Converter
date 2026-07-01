# PR C — Donor-Driven Anatomical Mesh Partitioner: Report

**Module:** `native/GhostRigger.Core.Math/Python/src/math/anatomical_partition.py`
**Tests:** `tests/test_anatomical_partition.py` (8, all pass)
**HEAD at start:** `cccbff8b` (PR B) on `qt-ghostrigger`
**Env:** Python 3.14.0, trimesh 4.11.5, numpy 2.4.2, scipy 1.17.1. No new native deps.

---

## 1. What PR C does

`partition_mesh_anatomically(imported_vertices, imported_faces, donor)` splits a
unified imported mesh into ≤16-bone anatomical regions using a donor's skin
weights as the anatomy prior, then transfers those regions to the imported mesh
by nearest-donor-face correspondence.

It does exactly one thing (split). It never calls `fit_skeleton_inside_mesh_v2`
and never wires the dispatch ladder. It hard-fails (`MissingDonorError`) when the
donor is absent/malformed, with no fallback splitter. Donor regions are
recomputed every call (stateless, no caching).

---

## 2. Design choices (with line-cited rationale in the module)

| Choice | Where | Rationale |
|---|---|---|
| GWN-free; pure NumPy/SciPy/trimesh | module header | Ships as RCDATA-embedded Python in native DLLs; new native deps are a build hazard. |
| **Seam-welded** face adjacency | `_face_adjacency_edges`, `WELD_DECIMALS=5` | Donor MDL verts are split at UV/smoothing seams and the donor is 7 separate skin meshes; raw-index adjacency under-connects and the partitioner over-fragments. Welding is used only to derive topology; returned indices are still into the original face array. |
| Ambiguous-seam-face deferral | `_dominant_and_ambiguous`, `AMBIGUOUS_WEIGHT_FRACTION=0.05` | A face whose top-1/top-2 accumulated bone weights are within 5% sits on a deformation boundary; assigning by argmax would spawn one-face seam regions. Deferred, then flood-filled to the nearest seed by graph distance. |
| Dust merge with centroid fallback | `_dust_merge`, `min_faces_per_region=8` | Sub-`min_faces` regions dissolve into the strongest-boundary neighbour; **isolated** islands (no adjacency — common because the donor is 7 disjoint meshes) fall back to nearest region by centroid. |
| **Palette-bounded Jaccard agglomeration** (added step) | `_agglomerate_to_palette`, `AGGLOMERATION_JACCARD_MIN=0.15` | Dominant-bone CCs over-segment fine skeletons (Drexl → ~46 regions after weld+dust). Merge adjacent regions whose bone-influence sets overlap (Jaccard ≥ 0.15) and whose merged palette ≤ 16. Overlap is the anatomy signal: successive appendage segments share bones; distinct limbs don't. |
| Greedy connected palette split | `_greedy_palette_split` | Any region still > 16 bones is split by ascending per-face bone-set size, then re-split into connected components so every output is one connected patch ≤ 16 bones. |
| **Aligned** nearest-face transfer (correctness fix) | `_align_and_transfer_regions`, `_best_alignment_rotation` | The literal spec's raw cKDTree assumes donor/import share a frame. They don't (see §5). Transfer runs in a shape-normalised frame with a 24-way axis-rotation search (octahedral group; identity is a member, so never worse than none). |

### Two implementation points beyond the literal PR C prompt (both required for real data)

1. **Transfer alignment (correctness fix, not a deviation).** Added
   shape-normalisation + best-of-24-axis-rotation before nearest-face. Without it,
   raw world-space lookup gives ~0 confidence because the OBJ is axis-permuted and
   rescaled relative to donor model space. The spec assumed donor and import share
   a frame; real OBJ imports do not, so a raw lookup silently transfers regions
   wrong. This is what the spec should have said — it is now a permanent part of
   the module (`_align_and_transfer_regions`).
2. **Jaccard agglomeration (kept, calibration documented).** The prompt's 4-step
   BIAGP only *splits* over-palette regions; it never *coarsens*. On Drexl that
   yields 46 raw regions and fails the prompt's own test 5 (4–12). The
   agglomeration step is what makes the ≤16-bone-region goal achievable as coarse
   anatomy. The threshold is a named constant `AGGLOMERATION_JACCARD_MIN = 0.15`
   with an in-module calibration comment (Drexl: 46 raw → 7 authored parts;
   humanoid data point is a TODO).

---

## 3. Drexl partition result (Phase 1 + 2)

Donor `c_drexlf` (K2) is 7 skin nodes concatenated into a unified donor:
1209 verts, 1526 faces, 55 global bones (53 with nonzero weight). The imported
`C_DrexlF_UV.obj` is the same topology re-UV'd: 2120 verts, 1526 faces.

**Diagnostics:**

```
final_region_count            7        (4–12 ✓)
max_bones_in_any_region       14       (≤16 ✓)
min_bones_in_any_region       8
donor_regions_dust_merged     48
donor_regions_agglomerated    39
ambiguous_faces_deferred      67
palette_splits_triggered      0        (agglomeration is 16-bounded, so nothing exceeds 16)
empty_transfer_regions        []
mean_transfer_confidence      0.846
regions_with_low_confidence   []
```

**The 7 regions (recovered from weights alone — they match the artist's 7 nodes):**

| region | dominant bone | bones | donor F | imported F | transfer conf |
|---|---|---:|---:|---:|---:|
| 0 | Lforearm_g | 12 | 270 | 227 | 0.850 |
| 1 | tail6_g | 10 | 186 | 178 | 0.817 |
| 2 | Rforearm_g | 12 | 270 | 279 | 0.835 |
| 3 | torso3_g | 14 | 191 | 285 | 0.888 |
| 4 | head_g | 8 | 353 | 301 | 0.882 |
| 5 | Rwing_02 | 8 | 128 | 128 | 0.784 |
| 6 | Lwing_02 | 8 | 128 | 128 | 0.788 |

### BIAGP edge cases that fired on Drexl

- **Ambiguous faces:** 67 seam faces deferred and flood-filled.
- **Dust merges:** 48 sub-8-face islands dissolved (dominant-bone CCs + the 7
  disjoint-mesh boundaries produce many slivers; several needed the isolated
  centroid fallback).
- **Agglomeration:** 39 merges — this is the heavy lifter, collapsing
  `tail1..tail6`, finger chains, and per-arm bands into single parts.
- **Palette splits:** 0 — agglomeration is 16-bounded, so no region ever exceeds
  16 to require a split. (Palette split is exercised by synthetic test 3.)

### Transfer confidence assessment

`mean_transfer_confidence = 0.846`, no low-confidence (<0.1) or empty regions.
This is high because the OBJ is the donor's topology re-UV'd — after
normalisation + axis alignment the correspondence is near-exact. If a real
custom mesh diverged more from the donor, this number would drop and surface in
`regions_with_low_transfer_confidence` (informational, non-fatal by design).

---

## 4. Test 7 — the load-bearing falsifier (FAILED / documented)

Harness (exactly per spec): for each ≥3-bone region, subset the imported mesh by
`imported_face_indices`, take `region.bone_positions`, call
`fit_skeleton_inside_mesh_v2(sub_v, sub_f, bones, use_v2=True, target_margin=0.3,
margin_relative_to="shell_diagonal")`, and compare `scale` to
`initial_scale_estimate = bone_diag / mesh_local_diag * 1.2`.

```
  R dominant_bone   nb  init_est    v2_scale     ratio  margin      status
------------------------------------------------------------------------------
  0 Lforearm_g      12     8.592     171.830     20.00   False  partial_fit
  1 tail6_g         10     8.832     176.639     20.00   False  partial_fit
  2 Rforearm_g      12     8.158     163.170     20.00   False  partial_fit
  3 torso3_g        14    16.655     333.100     20.00    True    converged
  4 head_g           8    10.724      34.676      3.23    True    converged
  5 Rwing_02         8     8.137     162.748     20.00   False  partial_fit
  6 Lwing_02         8     8.436     168.715     20.00   False  partial_fit

converged (<=1.5x): 0/7    ballooned (>1.5x): 7/7
```

**Every region violates `ratio ≤ 1.5`.** 6 balloon to the solver's 20× cap; the
head is the best case at 3.23× (still >1.5×). Test 7 asserts this documented
reality and prints the table (mirroring PR B's balloon-documenting test); invert
it to `ratio ≤ 1.5` once a different containment approach lands.

### Which regions ballooned, and by how much

All of them. Worst absolute scale: torso3 (333×), which *converged* by v2's own
containment definition but at ~20× its natural estimate. The two wings and both
arms and the tail all hit the 20× cap as `partial_fit` (i.e., true required scale
is even higher). Head and torso "converge" only because they are bulky enough to
eventually engulf their bone cluster; limbs/wings/tail are thin tubes/sheets.

### Hypothesis (do not fix here — diagnostic for the next PR)

This is **not** a segmentation bug and **not** a bad-transfer bug:

1. **Segmentation is correct.** The 7 regions match the artist's authored nodes,
   transfer confidence is 0.846, and the ideal 7-skin-node partition (bypassing
   the algorithm entirely) balloons identically.
2. **The containment target is the problem.** During development I ran v2 on the
   7 ideal regions with three different bone-position definitions — full palette,
   dominant-bones-only, and weighted-influence-centroids — and **all three
   balloon 5–6 of 7 regions**. The choice of which bones to contain does not
   rescue it.
3. **Root cause: shell-containing joint-anchored bones inside an open-shell
   region sub-mesh is geometrically the wrong ask.** A region cut from the body
   is an open surface patch (the full OBJ has 2046 boundary edges from UV-seam
   splitting alone; each region sub-patch has hundreds), and its bones are joint
   pivots that sit at region *boundaries* (a limb's proximal joint pivot lives
   outside the limb's surface). No similarity transform makes a thin open patch
   enclose bone anchors that live on its rim, so v2 inflates scale trying to wrap
   the patch around them.

**Implication:** anatomical splitting is *necessary* (it is the only way to keep
regions ≤16 bones and it does cluster anatomy correctly) but *not sufficient* for
per-region shell containment at natural scale. The next step is a containment
**target/objective** redesign — e.g. contain each bone's influence *region*
(its skinned vertices, which are on the mesh by construction) rather than its
joint pivot, or fit against a closed proxy volume per region — which is a PR D
diagnostic, not a parameter tweak to PR C.

---

## 5. Judgment calls where it could have gone another way

- **Unified donor vs per-node.** The donor is already 7 nodes ≤16 bones; I could
  have treated each node as a region directly. Instead the module takes a single
  unified `DonorSkinData` (per the spec's data structures) and *rediscovers* the
  regions from weights. This keeps the module general (works for any donor,
  including single-mesh donors) and validates BIAGP against a known-good answer.
- **Jaccard threshold 0.15.** Chosen so Drexl coarsens to its 7 parts while
  disjoint-palette limbs never merge (Jaccard 0). Higher (~0.3) risks leaving
  tail segments split; lower risks merging arm→torso via shared collar bones.
  0.15 is a tunable module constant, documented.
- **Transfer alignment in normalized space.** Confidence is reported in the
  normalised frame so the 0..1 metric is scale-meaningful; the alternative
  (world-space distances) makes the confidence number uninterpretable.
- **`random_seed` accepted but unused algorithmically.** The pipeline is
  deterministic; the seed is set globally for reproducibility/API stability and
  recorded in diagnostics.
- **Regions with 1–2 bones.** Drexl's clean partition has none (min 8), but such
  regions can arise on other creatures (leaf bones / finger tips). Test 7 skips
  them; the eventual fit pipeline (PR D) must decide how to treat degenerate
  1–2-bone regions.

---

## 6. Gate status

- test 1–6, 8: PASS. test 7: PASS (asserts the documented balloon; prints table).
- PR A (`test_winding_number.py`) + PR B (`test_containment_fit_v2.py`): 15 passed.
- `test_native_python_payloads.py`: 17 passed (count 1184 → 1185).
- **PR D (dispatch-ladder wiring) is on hold.** Test 7 falsified the "splitting
  alone → natural-scale containment" thesis. The next PR should be a containment
  **objective** diagnostic, not the ladder wiring.
