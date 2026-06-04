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

## Suggested Tests And Reports

Add or extend tests around these future slices:

- Bendak auto-fit records front/up/scale/root confidence against
  `n_mandalorian`.
- Build/Confirm cannot proceed if fit confidence is below a strict threshold
  unless the user has explicitly accepted manual correction.
- Symmetry-on guide edits update only paired compatible nodes.
- Symmetry-off guide edits affect only the selected node.
- Donor weight transfer blocks zero-weight and wrong-side vertices.
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
