# Character Builder Rigging And Skinning Notes

Date: 2026-06-04

Purpose: add rigging and automatic-skinning research to the GhostRigger
knowledge base, focused specifically on Character Builder decisions for the
Bendak-to-`n_mandalorian` fixture and future native KOTOR character exports.

This note is not a copy of the books or paper. It records durable principles,
page anchors, and GhostRigger-specific applications.

## Sources Studied

| Source | Local Path | Notes |
|--------|------------|-------|
| Tina O'Hailey, *Rig it Right! Maya Animation Rigging Concepts*, 3rd ed. | `C:\Users\NewAdmin\Documents\Academy of Art University\Books\_OceanofPDF.com_Rig_it_Right_Maya_Animation_Rigging_Concepts_-_Tina_OHailey.pdf` | 324 pages. Relevant anchors: rigging rules around joint placement/orientation and skinning quality; pages around 18, 99-100, 142-146, 153-165, and 305-313. |
| Junjun Pan et al., "Automatic skinning and weight retargeting of articulated characters using extended position-based dynamics" | `C:\Users\NewAdmin\Documents\Academy of Art University\Books\2017-tvc-automatic-skinning-weight-retargeting.pdf` | 13-page paper, *The Visual Computer*, DOI `10.1007/s00371-017-1413-6`. Relevant anchors: automatic skinning limits, skeleton-topology assumptions, weight retargeting through geometric correspondence, bi-harmonic distance, joint-area deformation cleanup. |

## Main Takeaway

The books reinforce the current Character Builder direction:

```text
KOTOR native skeleton/node DAG = authority
Imported FBX mesh = payload guest
Fit/bind/weights = explicit, inspectable transfer steps
Export = blocked unless the bind evidence and deformation checks are credible
```

The biggest practical adjustment is that Character Builder should not treat
"auto-rig succeeded" as a single binary event. It should expose separate
confidence for:

- front/up orientation and root placement;
- scale fit to the native base;
- joint/guide placement;
- bind pose stability;
- skin-weight completeness;
- deformation quality during inherited animation preview.

## 2026-06-04 Confirmation Pass

The local PDFs were rechecked with a metadata and keyword pass so future agents
know why these sources matter to the Character Builder roadmap:

- *Rig it Right!* is directly relevant to guide placement because it repeatedly
  covers joint orientation, bind pose, deformation testing, skinning, weights,
  and geodesic/bind concepts. It supports treating front/up orientation,
  root/pivot placement, symmetry, and freeze-transform actions as explicit
  authoring steps rather than hidden viewport conveniences.
- Pan et al. is directly relevant to GhostRigger's donor-weight path because
  it focuses on automatic skinning, weight retargeting, deformation quality,
  correspondence, geodesic distance, and bi-harmonic distance. It supports the
  current choice to prefer native-template/donor weight transfer over
  nearest-bone fallback for Bendak-style custom body imports.

Do not use either source to override KOTOR facts. Use them to improve the
tooling workflow around the real Odyssey contract confirmed by MCP, PyKotor,
MDLOps, KotorBlender, xoreos, and Ghidra.

## Character Builder Action Checklist

For the Bendak-to-`n_mandalorian` fixture and similar character imports,
Character Builder should make these stages visible and separately validated:

1. **Fit evidence before bind**
   Record the solved front axis, up axis, root/pivot placement, scale, and any
   manual correction. A mesh that is merely visible beside the native skeleton
   is not fitted.
2. **Bind evidence before export**
   Build/Confirm must create a named bind-pose snapshot and state whether the
   imported payload is bound to the preserved native KOTOR DAG.
3. **Weight evidence before launch claims**
   Prefer donor/native-template weights when a comparable KOTOR body exists.
   Report fallback weighting separately and keep it below launch-quality until
   deformation preview proves otherwise.
4. **Animation evidence before game-ready language**
   Preview inherited supermodel clips from the selected base model's chain.
   At minimum, record idle, walk/run if available, and one gesture/combat clip.
5. **Correction evidence after manual edits**
   Symmetry, guide movement, center-pivot, and freeze-transform operations must
   be explicit, undoable, and captured in session/export reports.

## Added Pass: Fit, Bind, And Weight Are Separate Evidence

The second scan of the two sources reinforced a distinction that matters a lot
for Character Builder:

```text
mesh appears lined up
!=
mesh has a trustworthy bind pose
!=
mesh has safe KOTOR skin weights
```

This is the most important Character Builder lesson from the new sources. A
custom body can look acceptable in the viewport and still fail inherited KOTOR
animations if its solved fit transform, bind snapshot, or donor-weight
correspondence is weak.

Product rule:

- **Fit** answers: does the imported mesh face the native KOTOR skeleton's
  front direction, match its up axis, stand at the correct root height, and
  scale to the selected base?
- **Bind** answers: has Build/Confirm attached the imported payload to the
  preserved native KOTOR node DAG with a stable bind-pose snapshot?
- **Weight** answers: do all vertices have normalized, valid influences from
  allowed native deform nodes, preferably transferred from a comparable donor
  body rather than guessed by nearest bone?

The UI should report those as separate readiness states. A single green
"built" state is too vague for a modder trying to diagnose why Bendak animates
badly on the `n_mandalorian` skeleton.

## Applicable Rigging Principles

### Joint Placement And Orientation Are First-Class Gates

*Rig it Right!* repeatedly treats joint placement, preferred axes, and local
orientation as work that must be correct before skinning. That maps directly to
Character Builder's current auto-fit problem: if Bendak is not oriented,
scaled, and placed against the `n_mandalorian` frame before Build/Confirm, the
later MDL can reload but still deform poorly.

GhostRigger rule:

- Auto-fit must solve front axis, up axis, side axis, scale, and root/pivot
  placement before bind.
- The fit report should record the solved transform and the landmarks used.
- Manual adjustments after auto-fit should be recorded as authoring state, not
  hidden viewport transforms.
- "Freeze transforms" is useful only if it preserves visible geometry and
  writes a clear bind-pose transform into the Character Builder session.

Roadmap impact:

- T1205/T2102 should keep "Mesh Fit" separate from "Native Node Edit".
- T2203 export evidence should include the final fit transform and whether it
  was auto-solved or manually changed.

### Freeze Transform Is A Bind-Pose Operation, Not A Visual Shortcut

The rigging book's transform cleanup guidance is Maya-specific, but the
principle maps cleanly to GhostRigger: the editor may offer Center Pivot and
Freeze Transform actions, but they must not silently move the actual exported
native node DAG or hide a bad fit.

GhostRigger rule:

- Center Pivot should modify the editable scene/payload pivot while preserving
  visible geometry.
- Freeze Transform should bake the current mesh-fit correction into the
  Character Builder session and create or update explicit bind evidence.
- Freeze Transform must be undoable and should report before/after position,
  rotation, scale, and affected payload nodes.
- It must not rename nodes, collapse native KOTOR pivots, or rewrite the base
  snapshot without a structural diff.

Roadmap impact:

- T2102 needs tests that prove freeze keeps the custom mesh visually stable
  while changing only the intended authored fit/bind state.
- T2203/T2204 reports should include whether the exported candidate used a
  frozen fit transform.

### Symmetry Is Useful, But KOTOR Names Still Win

The rigging book treats mirrored limbs as a speed tool, not as a reason to
forget local orientation differences. For GhostRigger, symmetry must be a guide
editing convenience only. It must never rename KOTOR nodes or infer that left
and right local axes are identical.

GhostRigger rule:

- Symmetry toggle affects paired guide edits and mesh-fit helpers.
- Native KOTOR node names/casing and parent links remain unchanged.
- The UI should report symmetry on/off clearly and show which pair was updated.
- If a guide pair cannot be mirrored safely, emit a warning instead of moving
  an unrelated node.

Roadmap impact:

- T2103 should test both "symmetry on" and "symmetry off" paths.
- Left/right guide maps should live in core data, not be inferred in the Qt
  paint/event layer.

Important nuance:

- Mirrored limbs may intentionally have different local axes while still
  behaving symmetrically. Character Builder should mirror desired guide motion
  in the native model's body space, not blindly copy local Euler channels from
  one side to the other.

### Skinning Quality Is Not Optional Polish

The rigging book's skinning sections treat weights as the difference between a
working rig and a bad one. The automatic-skinning paper says the same thing
from the algorithmic side: professional-quality skin weights usually need
correspondence, deformation-area awareness, and validation around joints.

GhostRigger rule:

- Nearest-bone weighting is a fallback, not the preferred final mode.
- Native-template weight transfer should become the preferred mode when the
  selected KOTOR base has comparable skin payloads.
- Export preflight should block zero-weight vertices, unnormalized weights, and
  invalid bone-map rows.
- Preview should warn when elbows, knees, wrists, ankles, shoulders, or hips
  show high deformation risk.

Roadmap impact:

- T1803 should be promoted in priority: "Library Rig transfer from selected base
  model" is not a luxury feature; it is the path to fewer twisted wrists,
  ankles, and shoulders.
- T1804 nearest-bone auto-rig should remain available but labeled as first-pass
  quality.

### Weight Retargeting Needs Correspondence, Not Just Name Matching

Pan et al. assume compatible skeleton topology before retargeting weights, then
use surface/geometric correspondence concepts to move useful weights from one
character to another. That fits GhostRigger's native-template model: KOTOR's
node DAG stays fixed, but Bendak's surface needs a credible correspondence to
the selected native body or a curated donor.

GhostRigger rule:

- For Bendak-to-`n_mandalorian`, the donor skeleton is the native KOTOR DAG.
- The imported mesh should receive weights by correspondence to a native/donor
  body surface when available.
- Distance-only approaches should be constrained by body-region labels so a
  hand vertex cannot borrow from the wrong side or from a hook.
- Future advanced modes can explore geodesic/bi-harmonic distance or
  volumetric proxy fields, but the first product slice should focus on a
  deterministic donor-weight transfer with clear failure reports.

Roadmap impact:

- Add a Character Builder "skin donor" concept separate from the native DAG.
  The donor may be the selected base render payload or a curated humanoid
  template, but the final exported DAG remains the selected native KOTOR DAG.
- Add tests that intentionally catch left/right crossed limb weights and
  wrist/ankle twist artifacts.

Practical implementation ladder:

1. **Native donor transfer**: preferred when the selected KOTOR base has a
   comparable body surface. Use the base/donor skin as the source of truth.
2. **Region-constrained nearest surface/vertex transfer**: acceptable when a
   donor mesh exists but the surface shapes differ. Search only inside matching
   body regions so hands, feet, shoulders, hips, and centerline vertices cannot
   borrow from the wrong side.
3. **Region-constrained nearest bone**: fallback quality. It should be labeled
   "first pass" and must require inherited-animation preview before export
   confidence increases.

The paper's topology and normalization assumptions are a direct warning for
GhostRigger: donor-weight transfer should only be trusted after the mesh has
been normalized to the native skeleton's scale/orientation and the body-region
landmarks are plausible.

Suggested correspondence landmarks for the first Character Builder product
slice:

- root / pelvis center;
- head or helmet center;
- left and right hands;
- left and right knees;
- left and right feet or ankles;
- optional shoulders and elbows for armor-heavy meshes.

These landmarks can be auto-solved where possible, but the UI should let a
modder correct them before Build/Confirm.

### Bind Pose And Deformation Preview Must Be Evidence

The rigging book emphasizes testing skin by rotating joints and returning to
bind pose. For KOTOR, this means Character Builder should preview inherited
supermodel clips before export, and the preview should not be treated as a
purely visual nicety.

GhostRigger rule:

- Build/Confirm should create a named bind-pose snapshot.
- Preview inherited animations from the selected supermodel chain as a
  validation step.
- Export reports should state which animations were previewed, not merely that
  the MDL/MDX reloaded.
- Until in-game Override/Patch testing happens, the label remains "export
  candidate", not "game-ready".

Roadmap impact:

- T1901/T1902 should unblock the Animation Library dropdown for selected
  supermodels.
- T2205 should keep the in-game manual checklist attached to packaged outputs.

Minimum deformation-risk preview set:

- idle or ready stance, to catch bind-pose drift;
- walk/run, to catch crossed legs, hip drift, and foot twist;
- one attack/gesture/cast clip, to catch shoulder, elbow, wrist, and hand
  influence problems;
- one head/attachment preview if the model uses `headhook`, weapons, masks, or
  goggles.

The output should name the sampled supermodel animation, source supermodel, and
the risky regions observed by validation. This supports honest labels such as
"reload-verified export candidate" instead of "game-ready".

### Performance Belongs In The Pipeline Design

The rigging book's performance/profiler section is Maya-specific, but the
principle carries over: rigs and deformers need observable evaluation costs.
Character Builder's fit, weight transfer, deformation preview, and export
verification should stay headless and measurable, with Qt only orchestrating
progress and display.

GhostRigger rule:

- Heavy fit/weight operations should be core services with deterministic
  inputs/outputs.
- The Qt panel should present reports and progress; it should not own the math.
- Add timing fields to future fit/weight/deformation reports before optimizing.

## Character Builder Design Rules To Carry Forward

1. Keep `NativeSkeletonSnapshot` as the final DAG contract authority.
2. Treat imported FBX skeletons as fit/mapping evidence only, never as the final
   exported skeleton.
3. Store auto-fit transform, manual correction, and bind-pose evidence in the
   Character Builder session.
4. Prefer native-template/donor weight transfer over nearest-bone weighting when
   a comparable KOTOR body exists.
5. Keep symmetry and pivot/freeze tools undoable and explicit.
6. Preview inherited supermodel animations before export, especially idle, walk,
   and one combat/gesture clip when available.
7. Export only through staged transactions and keep the capability label honest:
   reload-verified export candidate until KOTOR in-game testing passes.
8. Treat fit confidence, bind confidence, and weight confidence as separate
   report fields.
9. Require donor-weight correspondence landmarks before trusting automatic
   weight transfer on armor-heavy custom meshes like Bendak.
10. Keep every fit/bind/weight operation headless and report-producing; Qt
    controls should orchestrate those services, not own their math.

## Suggested Tests And Reports

Add or extend tests around these future slices:

- Bendak auto-fit records front/up/scale/root confidence against
  `n_mandalorian`.
- Bendak auto-fit requires plausible root, head, hand, knee, and foot landmark
  correspondence before donor weights are considered trusted.
- Build/Confirm cannot proceed if fit confidence is below a strict threshold
  unless the user has explicitly accepted manual correction.
- Build/Confirm writes a bind snapshot and distinguishes mesh-fit transform
  from native KOTOR node transforms.
- Symmetry-on guide edits update only paired compatible nodes.
- Symmetry-off guide edits affect only the selected node.
- Donor weight transfer blocks zero-weight and wrong-side vertices.
- Donor weight transfer is rejected or downgraded when the imported mesh has not
  been normalized to the selected native base's scale/orientation.
- Previewing an inherited supermodel animation writes an audit record with
  sampled animation name, source supermodel, and deformation-risk warnings.
- Export report includes bind-pose snapshot, fit transform, donor-weight mode,
  and previewed animation evidence.

## What This Does Not Change

These sources do not override KOTOR/Odyssey facts. If Maya/academic rigging
advice conflicts with MCP, PyKotor, MDLOps, KotorBlender, xoreos, or Ghidra
evidence about KOTOR MDL/MDX behavior, KOTOR evidence wins.

These sources also do not justify turning GhostRigger into a full DCC app. They
support a tighter modder workflow:

```text
choose native KOTOR base
import custom mesh
auto-fit and inspect
bind to native DAG
transfer/validate weights
preview inherited animations
stage export candidate
test in game
```
