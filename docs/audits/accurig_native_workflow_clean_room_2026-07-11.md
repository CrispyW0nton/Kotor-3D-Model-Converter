# AccuRIG clean-room deep pass for Character Studio

Date: 2026-07-11  
Owner: LordVaderCW  
Scope: Character Builder landmark workflow, donor-skeleton fitting, skinning,
bind-pose bake, and retarget/export readiness

## Evidence and limitations

AccuRIG 2.1.0.584 (`AccuRIG.exe` SHA-256
`c291e32944a24dcaa322c5dba1fec13a5b21b8171d7cc69a953792c429376e2b`)
and its native rigging DLLs were analyzed with Ghidra 12.1.2. The exact binary
hashes, representative addresses, function-shape metrics, and raw report paths
are recorded in
`C:/Users/NewAdmin/Documents/GDeveloper/Workspaces/Ghidra/projects/active/AccuRIG/findings/01_native_workflow_deep_pass.md`.

The pass used exports, imports, strings, xrefs, direct call relationships, and
control-flow counts only. It did not recover or copy proprietary source.

## Product contract learned from the evidence

The useful lesson is not an AccuRIG algorithm. It is the separation of an
editable rigging workflow into explicit artifacts:

1. Import and validate the source mesh.
2. Detect body landmarks into a saved, editable joint state.
3. Let the user move/rotate/mask joints and apply symmetry.
4. Detect and correct fingers independently.
5. Construct and validate a skeleton profile.
6. Build correspondence to the target mesh.
7. Calculate, smooth, normalize, and review skin weights.
8. Bake the bind pose explicitly.
9. Characterize/export only after structural and deformation gates pass.

Ghidra evidence directly supports separate APIs for all of those boundaries,
including joint get/set/save/mask operations, body/finger evaluators, skeleton
creation/cleanup, skin application/conversion, bind-basis baking, mesh wrapping,
progress metadata, worker threads, and task cancellation.

## Required GhostStudio behavior

- Character Builder should persist a `RigSession`; switching tools or closing a
  panel must not throw away detected/corrected landmarks.
- Each stage owns an input revision and output artifact. Editing landmarks
  invalidates correspondence/weights/bind/export, but does not re-import the
  source or reset the viewport.
- Body and finger detection must be independently rerunnable, cancellable jobs.
  Progress labels must name the stage and preserve the last valid result on
  cancellation or failure.
- Joint correction needs clear translate/rotate handles, bilateral pairing,
  per-joint mask/lock, save/restore, and an error list for out-of-volume,
  crossed, or implausibly ordered landmarks.
- Correspondence belongs in a headless geometry service returning confidence,
  unmapped regions, and distance/error diagnostics. Character Builder only
  presents and edits the result.
- Skinning must be reviewable before bake: normalized sums, influence cap,
  unweighted vertices, seam discontinuity, twist-joint behavior, and visible
  high-bend tests.
- Bind pose is an explicit command with before/after skeleton-space validation,
  never an incidental side effect of export.

## KOTOR-specific constraint

GhostStudio must **not** adopt AccuRIG's CC skeleton hierarchy. The pattern to
adopt is profile specialization; the KOTOR target profile is an exact donor
Odyssey DAG snapshot. Node names, order, parents, flags, transforms, supermodel
semantics, and hooks (`head_g`, `Lhand_g`, `Rhand_g`, `camerahook`) remain
locked. Every export must also prove qbone/tbone data, normalized/capped
weights, structural diff, MDL/MDX reload, and visible animation before in-game
claims.

For retargeting, source-to-target correspondence and motion mapping are separate
from skin fitting. Unreal T/A-pose alignment, root-motion policy, source event
mapping, KOTOR controller generation, hook survival, and in-game animation proof
remain GhostStudio-owned contracts.

## Explicitly unsupported

The Ghidra pass does not prove AccuRIG's detector, exact embedding/weighting
math, correspondence solver, voxel settings, thresholds, file formats, thread
counts, or performance. In particular, the earlier phrase "heat diffusion
smoothing" is not supported by this native evidence; only a named
`Smooth Body SkinWeight` stage is observed.

