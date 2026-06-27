# Unreal Character Pipeline Skill

Use this skill for the KOTOR-to-Unreal animation retarget lane (T2404): mapping
Odyssey bones to the UE5 humanoid skeleton, building IK retarget profiles,
exporting FBX for UE5, and auditing the skeleton-map manifest.

## Book Grounding

- `Unreal Engine 5 Character Creation, Animation and Cinematics` (Venter):
  importing skinned skeletons vs animation-only FBX, the UE5 retargeting system
  (IK Rig asset + IK Retargeter asset), retarget chains, chain mapping, retarget
  pose alignment, exporting retargeted animations, the legacy Retarget Source /
  Compatible Skeletons workflow, and UE5 material/texture import and the Base
  Material node.
- `Technical Animation in Video Games` (Lake): the Skeleton-vs-Skeletal-Mesh-vs
  -Physics-Asset split, Retarget Source (per-mesh bind pose + Bone Translation
  Retargeting Mode), Compatible Skeletons, animation additive/curves/notifies,
  and FBX import options (`Import Normals` vs `Compute Normals`, `Use T0 As Ref
  Pose`, `Update Skeleton Reference Pose`).
- `3D Mesh Processing` (Mukundan): the retarget algorithm — keep the target's
  skeleton parameters (offsets) fixed, transfer only animation parameters, with
  a joint-name map (Map-JN) and a per-joint Euler-axis remap (Map-EA).

Load `learned/unrealskill.md` for the standing UE integration notes and
`learned/technicalanimationskill.md` for the underlying skinning/retarget math.

## The Core Problem (T2404)

KOTOR animation is bound to a native Odyssey node DAG by exact name/parent/flag/
hook. UE5 animation is bound to a UE skeleton asset. The two skeletons have
different bones, bone names, joint counts, proportions, **and base poses**, yet
UE can "cleverly map and interpret" animation between them — provided you set it
up first. GhostRigger's job in the KOTOR-to-Unreal lane is to author that setup
deterministically and export it, rather than hand-doing it in the editor. The
existing Quinn-skeleton mapping and `GhostRigger.Core.Unreal` helpers are the
seed of this manifest.

## The UE5 Retargeting System (IK Rig + IK Retargeter)

UE5 replaced the old per-bone retarget mode with two asset types. Build both in
GhostRigger's exported manifest, not by hand:

1. **IK Rig asset** (one per skeleton). Open the IK Rig for a skeletal mesh and
   define **retarget chains** — one per body part you want to transfer. For a
   humanoid: `Head`, `Neck`, `Spine`, `Left_Arm`, `Right_Arm`, `Left_Leg`,
   `Right_Leg`, plus `Hips`/`pelvis` as the **retarget root**. A chain is an
   ordered bone selection (e.g. left arm = `clavicle_l, upperarm_l, lowerarm_l,
   hand_l`). Select the bones in order → *New Retarget Chain from Selected
   Bones* → name it.
2. **IK Retargeter asset**. Create it on the **source** IK Rig (the skeleton the
   animation is authored on), then set **Target IKRig Asset** to the destination
   rig. The Asset Browser lists the source animations; selecting one previews
   the retarget live on the target.

Critical property: **the two skeletons do not need the same bone count.** A
source with a 3-bone spine retargets fine onto a target with a 5-bone spine — UE
interpolates across the chain. What **must** match is the chain *identity and
order*, not the underlying joint list.

### Chain Mapping and the retarget pose

Two things break a retarget that has a correct map:

- **Chain Mapping** tab: UE matches chains by name. If the source and target
  chains were not named consistently, the drop-downs mis-pair; fix them here.
  GhostRigger's manifest should therefore emit identical chain names on both
  sides (canonical `Head`/`Spine`/`Left_Arm`/...).
- **Retarget (base) pose mismatch** — the #1 cause of "the map is right but the
  arms look wrong." If the source is T-pose and the target is A-pose (or vice
  versa), the delta UE computes is wrong. Fix by *Edit Pose* on the target rig
  to match the source's base arm pose, then re-preview. Iterate until the
  retarget looks correct, then *Export Selected Animations* to bake the result
  onto the target skeleton.

### The math this implements

This is the Mukundan retarget algorithm in engine clothing: keep the target's
**skeleton parameters** (joint offsets / relative positions = the bind shape)
fixed, transfer only **animation parameters** (joint rotations + root global
position/orientation), via a **joint-name map** (Map-JN = the chain mapping) and
a **per-joint Euler-axis remap** (Map-EA, folded into the IK solver). A bind-
pose/base-pose difference is exactly the "extra base rotation" that Map-EA must
account for.

## The Legacy Workflow (still relevant for KOTOR↔KOTOR)

For same-engine / shared-skeleton sharing, the older **Retarget Source** system
still applies (and maps cleanly onto KOTOR's supermodel inheritance):

- Add each skeletal mesh as a **Retarget Source** on the shared skeleton. This
  records each mesh's **bind pose** so the engine can compute the delta of joint
  transforms between meshes.
- Set **Bone Translation Retargeting Mode** per bone: `Animation` (use anim
  translation, no mapping), `Skeleton` (use bind translation), `Animation Scaled`
  (scale anim translation by proportion difference), `Animation Relative`
  (additive-style relative translation — fits most cases), `Orient and Scale`.
  Set it **recursively** down a subtree. Map names: `Animation` ≈ KOTOR "inherit
  as-is"; `Animation Scaled` ≈ KOTOR proportion-compensated inheritance.
- **Compatible Skeletons** links multiple *different* skeleton assets to share
  animation; it is one-directional, so add both directions for bidirectional
  sharing.

The KOTOR analogue: a supermodel chain is a Retarget Source chain where child
models inherit and (via flags) scale/orient relative to the parent's bind pose.
GhostRigger's T2501 DAG snapshot must capture the per-node data that corresponds
to Bone Translation Retargeting Mode so inheritance survives a round-trip.

## FBX Handoff For UE5

Two FBX files, cleanly separated:

- **Skinned skeleton mesh** (the reference rig, no animation). Import with
  `Import Mesh` on, `Import Animations` **off**. This creates the skeleton +
  skeletal mesh assets that all animations play on. One skinned file drives many
  animations.
- **Animation FBX** (skeleton + animation only, no skin). On import, UE detects
  the skinless file and asks for the target **Skeleton**; pick the one created
  above. Animations import as AnimSequence assets on that skeleton.

For KOTOR→UE5, GhostRigger should export two analogous artefacts: a skinned UE-
skeleton FBX built from the Odyssey DAG + remapped bones, and per-animation
FBX files that reference it. Mirror the Mixamo convention that makes this
bulletproof: **FBX for Animation = `Without Skin`**, a fixed FPS, and
**keyframe reduction = none** (so every Odyssey key lands 1:1 and nothing is
silently dropped).

### Import options that matter

- `Normal Import Method = Import Normals` (not `Compute Normals`) — preserve the
  artist's/authored normals; recomputing them changes shading and can fight the
  KOTOR-authored normals you round-tripped.
- `Use T0 As Ref Pose` + `Update Skeleton Reference Pose` — frame 0 is the
  reference/bind pose; keep these on so re-imports don't drift.
- `Import Morph Targets` only if you actually have blendshapes/morph targets.

## Materials And Texture Channels (cross-check before export)

UE5 expects a PBR **metallic-roughness** material. The texture-channel
discipline (see `learned/pbrtexturingskill.md` and `learned/renderingshaderskill.md`)
must be honoured in any UE-bound export:

- **Albedo / Base Color**: sRGB **on**, `Default (DXT1/5, BC1/3)` compression.
- **AO, Metallic, Roughness**: sRGB **off** (linear data), default compression.
- **Normal**: sRGB **off**, `Normalmap (DXT5, BC5)` compression, and check
  **Flip Green Channel** if the source normal map is OpenGL-style (`Y+`) — UE is
  DirectX-style (`Y−`). A wrong green-channel handedness inverts bumps to
  indentations.
- **Material slots**: UE splits a mesh into per-material **elements**; more
  elements = more draw cost, and per-element properties (cloth, visibility) must
  be set per slot. Keep KOTOR material-slot assignments 1:1 with the export so
  nothing silently recombines.

KOTOR itself is not fully PBR (it uses TGA/TPC/TXI with a Blinn-ish model), so
GhostRigger's UE export must **translate** KOTOR's diffuse+TXI hints into a PBR
metallic-roughness material (diffuse→albedo, derive roughness/metallic from TXI
flags or sensible defaults), not pass them through verbatim.

## GhostRigger Checks (T2404)

- Emit a **skeleton-map manifest** that lists, for each canonical chain
  (`Head`, `Neck`, `Spine`, `Left_Arm`, `Right_Arm`, `Left_Leg`, `Right_Leg`):
  the source Odyssey node(s), the target UE bone(s) in order, and the per-joint
  axis remap. Reuse the Quinn skeleton mapping as the baseline.
- Emit two FBX artefacts per character: a skinned UE-skeleton mesh (no anim) and
  per-animation skinless FBX at a fixed FPS with no key reduction.
- Normalise the **retarget/base pose** to a single canonical pose (recommend
  T-pose as the calibration baseline) on both source and target before computing
  the retarget; record the pose in the manifest so a drift is detectable.
- Reconcile the per-joint **Bone Translation Retargeting Mode** equivalent
  (inherit / scale / orient) from the Odyssey node flags so KOTOR↔KOTOR
  supermodel inheritance survives the round-trip.
- Set normal-map green-channel handedness and sRGB/compression flags correctly
  in the UE material; validate against `learned/renderingshaderskill.md`.
- Audit the manifest against `GhostRigger.Core.Unreal` helpers; keep the map
  deterministic and diffable rather than hand-edited in the editor.

## Failure Patterns

- Retarget maps correctly but arms/legs land wrong: **base-pose (T vs A)
  mismatch** — fix the retarget pose, not the chain map.
- Chains pair to the wrong body part: inconsistent chain names between source
  and target IK Rigs — fix in Chain Mapping and normalise names in the manifest.
- Animation jitters or drops frames: keyframe reduction on at export — set
  `none`, fixed FPS.
- Shading looks inverted/bumpy on the UE side: normal-map green channel not
  flipped for DirectX, or sRGB left on for a data map.
- Retargeted animation slides (feet don't plant): root motion / retarget-root
  not set, or root global position not scaled for the height delta (Map-JN root
  scaling).
- Skeleton-sharing breaks after a re-export: hierarchy order changed (a node
  reparented) even though names survived — re-diff the DAG (see
  `learned/technicalanimationskill.md`).
- UE mesh has unexpectedly many material elements: KOTOR material slots not kept
  1:1 at export — collapse/expand slots deliberately, not by accident.
