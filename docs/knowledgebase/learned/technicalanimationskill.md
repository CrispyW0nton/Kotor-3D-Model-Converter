# Technical Animation Skill

Use this skill for **technical animation pipeline decisions**: MoCap data
handling, the skeleton/skin export pipeline, animation state machines,
retargeting pipeline architecture, LOD strategies, animation performance
profiling, and the native Odyssey DAG lock in GhostRigger's Character Studio
(T2501-T2505). For joint/rig/weight workflow load `learned/riggingskill.md`;
for the UE5 retarget lane specifically load `learned/unrealcharacterpipelineskill.md`.

## Book Grounding

- `Technical Animation in Video Games` (Lake): the technical-animator role
  (rigging, engine integration, tools, MoCap, pipeline R&D), mesh **topology for
  deformation**, **bind-pose** rigor, joint orientation, FK/IK & space switching,
  corrective joints/blendshapes, the UE skeleton-vs-skeletal-mesh-vs-physics-asset
  split, Retarget Source / Compatible Skeletons, animation-blueprint **state
  machines**, blendspaces, layered-blend-per-bone, **inertialization**, and Ch17
  **optimisation** (LOD, AnimGraph LODs, tick, reference/cast cost, profiling).
- `3D Mesh Processing and Character Animation` (Mukundan): scene graph = node
  hierarchy + mesh array + material array, the offset/bind matrix, per-vertex
  transform (`J_k = L_k · F_k`), linear blend skinning (LBS), normal handling,
  candy-wrapper / collapsing-elbow artefacts, **quaternion algebra + SLERP +
  derivatives**, **vertex blending**, MoCap pipeline, skeleton animation, and
  inverse kinematics: **CCD** and **FABRIK**.
- `Unreal Engine 5 Character Creation, Animation and Cinematics` (Venter): the
  Blender→UE **FBX export pipeline**, **MoCap import via Mixamo retarget**, the UE
  **Control Rig Blueprint** (forward-solving authoring rig with FK/IK/spaces), and
  **Sequencer** cinematic capture/animation. (The UE *retarget* IK Rig/Retargeter
  detail lives in `learned/unrealcharacterpipelineskill.md` — do not duplicate.)

## Why Exact Nodes Matter (the Native Odyssey DAG lock)

A joint is a position + orientation; a bone adds length. In every real engine
**joints are where animation data is stored and transferred** from DCC to
runtime. Two consequences drive GhostRigger's critical-path blocker:

1. The native Odyssey DAG is a node hierarchy (nodes, parent chains, flags,
   **hooks**, bind data) that animation is bound to by **exact name and order**.
   This is the "native Odyssey DAG lock" behind T2501-T2505.
2. A hinge (elbow/knee) mis-oriented across three axes serializes three rotation
   curves instead of one — bloats the file and invites gimbal singularities.

KOTOR's **supermodel** inheritance is the same idea as Unreal's **Skeleton
asset**: a skeleton is a metadata parent holding the hierarchy structure *and how
animation data applies to it*. Skeletons are shared between skeletal meshes
**only if the hierarchy matches** — joints may be absent on one mesh, but the
**order of the hierarchy cannot change** (if B is a child of A in one model, A
cannot become a child of C in another). This is exactly why GhostRigger must
snapshot the exact node DAG (T2501), clone it preserving order (T2502), bind
imported skin to it (T2503), emit a structural diff (T2504), and round-trip
(T2505) **before** any binding.

### Joint orientation discipline (feeds T2501 snapshot)

- `Joint Orient` is a second rotation layer stacked on `Rotate XYZ`; a joint's
  true rotation combines both. Stacked rotations are the most common "looks fine
  but exports garbage" bug. Pick **one store** — either `Rotate XYZ` **or**
  `Joint Orient XYZ`, never both. Freeze transforms to move values into joint
  orient; re-parenting silently writes into `Joint Orient`, so treat any
  reparented node as suspect and re-zero.
- The T2501 snapshot must capture **local rotation axis / joint orient** of every
  node, not just translation. Bind data that omits orientation is untrustworthy.

### Coordinate-space compensation (the `x, z, -y` conversion)

Maya is RH Y-up; Unreal is LH Z-up; KOTOR object space is its own convention. The
rule from the books: **the offset must exist once, at the root of the pipeline**
— never per-node — so runtime orientation calculations never inherit a baked-in
90°. GhostRigger's Blender FBX importer converts Blender world axes to KOTOR
object space via **`x, z, -y`** at import root
(`native/GhostRigger.Core.IO/Python/src/converters/blender_fbx_mesh_importer.py`).
After conversion, verify the root deform bone has a clean, zeroed orientation in
KOTOR object space. (The full Blender bone model lives in
`learned/blenderpipelineskill.md`.)

## Hook Validation (head_g / Lhand_g / Rhand_g / camerahook)

Odyssey skeletons carry named **hook nodes** — attachment sockets the game uses
for composable content. GhostRigger must validate them as part of the DAG
snapshot (T2501) and after any bind/clone (T2502), because losing or renaming a
hook silently breaks in-game composition:

- **`head_g`** — head attachment (PC heads, helmets swap here).
- **`Lhand_g` / `Rhand_g`** — weapon/equipment grip sockets.
- **`camerahook`** — the third-person camera anchor.

Rules:
- Hooks are nodes with names; T2501 must record them as first-class DAG entries
  (name + parent chain + flag), and the T2504 structural diff must flag a missing
  hook as a break, not a cosmetic rename.
- Retarget imports express hooks as their target: the Mixamo→Aurora adapter
  (`mixamo_source_adapter.py`) maps `mixamorig:LeftHand`→`Lhand_g`,
  `RightHand`→`Rhand_g`, `Hips`→`pelvis_g`, `Spine2`→`torsoupr_g`, etc. A
  retargeted clip that drops the hand hooks leaves weapons floating — verify the
  hook chain survived the Map-JN.
- Non-deform rigid attachments (hair, cap, weapon mesh) bind to a hook as a DAG
  child, **not** as a skin influence (see `learned/blenderpipelineskill.md`).

## Skinning Math (the bind/skin table contract)

Character Studio binding (T2503) and writer/loader round-trip truth (T3501)
reduce to one model; load `learned/skinningdeformationskill.md` and
`learned/animationruntimeskill.md` for the full picture. Essentials:

- **Offset (bind) matrix** `F` moves a vertex from mesh space into joint space
  (`F = translate(-(xJ,yJ,zJ))` plus optional axis-align rotation). KOTOR's
  **`qbone` / `tbone`** influence lists and per-vertex skin rows encode exactly
  this: a vertex, its bones, their weights, and the bind transform that lets the
  runtime re-express the vertex in each bone's space.
- **Per-vertex transform**: `L_k = L_{k-1}·T_k·R_k` (root→bone hierarchy product),
  `J_k = L_k·F_k`, `v' = J_k·v`. The runtime only re-evaluates `L_k` per frame.
  **Normals need `J_k^{-T}` (inverse-transpose)**, never `J_k` directly —
  mandatory under non-uniform scale (AGENTS.md).
- **LBS**: `v' = (w_i·J_i + w_k·J_k)·v`, weights in `[0,1]` summing to 1. The
  normal matrix is `(w_i·J_i + w_k·J_k)^{-T}` — combine first, invert-transpose
  after. Dual-quaternion skinning (DQS) avoids LBS volume loss but is **not**
  supported for KOTOR export; author Classic Linear, treat DQS preview as
  diagnostic only.
- **Influence caps & normalisation**: engines cull influences above a cap. For
  T3501 verify the MDL skin rows respect KOTOR's actual influence limit, weights
  sum to 1, and **bone order** matches across bind table, qbone/tbone lists, and
  the writer/loader round-trip.

## ROM Tests — The Deformation Proof

You only see skinning fail when joints leave bind pose. A ROM test animates each
joint through min/max rotation/translation on each operational axis and keys
every extreme. Use it to verify deformation at high-bend joints, catch
**candy-wrapper** collapse (180° axial twist — fix with twist links spreading the
rotation), catch **collapsing-elbow** (over-large bone overlap — minimise it),
and validate corrective/twist joints. GhostRigger deformation preview (T2505)
should drive an automated ROM + extreme-bend sweep on the default fixture
**`N_DarthMalak`** with `walk` looped before export may succeed.

**Bind-pose choice**: A-pose (~45° arms) for binding — closer to rest, better
rest deformation. Reserve T-pose as the **retarget calibration baseline**. A
pose mismatch is the #1 cause of a retarget "looking wrong" with a correct map.

## Rotation: Euler vs Quaternions (and interpolation)

- **Euler** is the curve-editing interface but suffers **gimbal lock** (axis lost
  at 90° on the middle axis) and **singularity flips** (middle axis spins 180°).
  Set rotation order *before* animating; changing it mid-animation destroys poses.
- **Quaternions** `(x,y,z,w)` have no gimbal lock and blend reliably, so they are
  the runtime/cross-character storage format. KOTOR stores animation rotations as
  quaternions; convert at the boundary and verify rotation order (ZXY/ZYX) — a
  wrong order rotates joints correctly in isolation but produces flipped poses in
  chain.
- **SLERP** interpolates rotation keys along the shortest great-circle arc;
  **position keys interpolate linearly** (`factor = (t-t1)/(t2-t1)`). Quaternion
  derivatives feed velocity/impulse when needed. Non-uniform key distribution
  (e.g. 56 ticks, 23-25 keys per channel) is normal — interpolation makes it
  smooth. A sign flip in a quaternion key (q and −q are the same rotation) causes
  a full 360° spin during SLERP — normalise dot-sign across the channel.

## Inverse Kinematics: CCD and FABRIK

IK solves "given an end-effector target, what are the joint rotations?" — needed
for foot/hand planting, weapon-grip alignment, and any procedural pose
GhostRigger's preview or Control Rig may apply. Two iterative solvers
(Mukundan Ch8):

- **CCD (Cyclic Coordinate Descent)**: iterate from tip to root; at each joint,
  rotate it so the end-effector vector aligns with the target vector. Simple,
  cheap, but tends to curl chains and ignores bone length constraints unless
  clamped per-joint. Good for low-DOF chains (a 3-bone arm).
- **FABRIK (Forward And Backward Reaching Inverse Kinematics)**: forward pass
  moves the end-effector to the target and walks each joint toward its parent by
  its fixed bone length; backward pass re-roots the chain at the base. Produces
  smooth, believable chains, respects bone lengths natively, converges fast.
  Preferred for full-limb / spine IK; constrain with pole vectors for elbow/knee
  direction.

Both are iterative; cap iteration count and residual tolerance. For retarget,
FABRIK onto a target skeleton's hook nodes (Lhand_g/Rhand_g/foot_g) is a robust
way to plant feet/hands after a base-pose mismatch. KOTOR itself does not ship an
IK solver — these are GhostRigger-side tools for preview alignment and for
fixing retarget foot-slide (see Failure Patterns).

## MoCap Data Handling

MoCap arrives as dense per-frame rotation data on a source skeleton. Pipeline
discipline (Lake Ch1, Mukundan Ch7, Venter Part 4):

- **Source skeleton reconciliation first.** MoCap is bound to a capture skeleton
  (often Mixamo/Aurora). Resolve the joint-name map (Map-JN) before touching
  curves; an unmapped joint freezes at bind pose. The `mixamo_source_adapter.py`
  is GhostRigger's Map-JN for the Mixamo→Aurora lane.
- **Base-pose alignment.** MoCap is captured in a known pose (Mixamo is T-pose).
  Reconcile to the target bind/base pose or the delta lands wrong — same rule as
  retarget (see below).
- **Key reduction, not loss.** MoCap is one key per frame; for KOTOR, reduce keys
  (drop static channels, merge near-identical neighbours) but keep the motion
  fidelity within a tolerance — drive a golden round-trip (T2505) so reduction
  never silently alters a pose.
- **Root motion.** Capture the root node's global translation separately so foot
  planting and locomotion survive; losing root motion makes a walk look like
  moonwalking.
- **Cleanup passes**: foot-skim (contacts passing through floor), jitter (high-
  frequency noise — smooth with a small temporal filter), and limb pop at clip
  boundaries (match first/last frame for looping clips).

## Runtime Pose Evaluation, Blending, State Machines

These are the constructs behind KOTOR supermodel inheritance and GhostRigger's
preview; the *discipline* transfers even though KOTOR is simpler:

- **Local vs component/world space**: a bone transform may be relative to its
  parent (local) or to the root (component). Skeletal-control/constraint nodes
  operate in component space, so the runtime converts local↔component at the
  boundary. KOTOR node flags encode which space a node's data lives in — T2501
  must capture these flags.
- **Layered blend per bone**: overlay animation on specific bones (upper body on
  a locomotion lower body), with **blend depth** controlling hierarchy falloff.
  This is the conceptual basis for KOTOR animation inheritance/override across
  supermodel chains.
- **Additive animation**: a delta from a base pose added on top of another anim
  (a wave added to a walk). Requires a matching base/retarget pose or it adds
  garbage.
- **State machines & inertialization**: state machines define which animations
  can transition to which, with boolean transition rules and blend durations.
  **Inertialization** stops evaluating the source and uses pose momentum to glide
  to the target — cheaper than a crossfade, useful for compression/footprint.
- **Curves/notifies**: per-frame float curves and frame events. GhostRigger does
  not need these for KOTOR, but *track-name discipline* matters: more tracks =
  larger footprint and higher per-frame cost. Drop joints/tracks that contribute
  nothing before export.

## Retargeting — The Three-Direction Model (Retarget Studio)

GhostRigger's Retarget Studio ships three explicit modes
(`native/GhostRigger.Core.Workflow/Python/src/core/retargeting/retarget_modes.py`):

1. **`KOTOR_TO_KOTOR`** — sample a source animation through the evaluator and
   attach it as a local override on a target KOTOR model. Output:
   `kotor_mdl_mdx_animation_override`. This is the supermodel-inheritance lane;
   hierarchy **order** and node flags (the Bone Translation Retargeting Mode
   analogue) must survive.
2. **`KOTOR_TO_UNREAL`** — sample a KOTOR animation, retarget onto a UE-compatible
   skeleton, export a baked UE FBX animation clip. (Full UE5 IK Rig/Retargeter
   detail lives in `learned/unrealcharacterpipelineskill.md`.)
3. **`UNREAL_TO_KOTOR`** (also covers **Mixamo→KOTOR**) — import a UE/Mixamo FBX
   source clip and apply the verified FBX→KOTOR pipeline, producing a KOTOR
   animation override. The Mixamo adapter strips the `mixamorig:` namespace,
   normalises names, and maps each bone to an Aurora bone + `_g` hook.

The shared algorithm (Mukundan, reused by all three): keep the target's
**skeleton parameters** (joint offsets = bind shape) fixed; transfer only
**animation parameters** (joint rotations + root global position/orientation).
Two maps: **Map-JN** (joint-name hashmap; unmapped joints stay put; root may need
height scaling) and **Map-EA** (per-joint Euler-axis remap — a source Z rotation
may need to land on `-X`; derive by applying 90° about each principal axis per
joint and observing response). A retarget that "looks wrong" with a correct map
is almost always a **base-pose (T vs A) mismatch**, not a mapping bug.

## LOD Strategies And Animation Performance Profiling (Lake Ch17)

KOTOR has no built-in animation LOD, but GhostRigger's Character Studio preview
and any export budget need the same discipline:

- **Skeletal-mesh LOD**: lower triangle-count meshes swap in at distance; on a
  deforming mesh each LOD must re-bind and re-bake ROM (subdivision/decimation
  changes weight neighbourhoods — see `learned/meshprocessingskill.md`).
- **Animation LOD / tick gating**: reduce update frequency, drop tracks, or
  collapse to additive blends at distance. Cheapest wins first: skip ticks on
  distant actors, then strip finger/face tracks, then full anim skip.
- **Compression/footprint**: drop every-other frame, remove tracks from static
  joints, merge adjacent identical keys, strip static channels. Keep a T2505
  golden round-trip so compression never silently alters a pose.
- **Profile before optimising**: measure per-frame pose-evaluation cost, the
  count of active animatables, and the cost of reference/cast lookups per tick
  (the classic silent perf killer in tooling loops). The qbone renderer parity
  dump (`scripts/dump_qbone_renderer_parity_3j4.py`, fixtures `c_drexlf` /
  `c_brith` / `c_bomabeast`) is the in-renderer truth check — use it to confirm
  an optimisation did not change the deformed pose.

## GhostRigger Checks

- **T2501 (snapshot)**: capture node names, parent chains, flags, **hooks**
  (head_g/Lhand_g/Rhand_g/camerahook), **joint orient / local rotation axes**, and
  bind transforms. Do not trust bind data that omits orientation.
- **T2502 (clone)**: preserve hierarchy **order** — supermodel inheritance breaks
  on reordering even when names survive. Re-validate hooks after clone.
- **T2503 (bind imported skin)**: respect KOTOR's influence cap, produce
  normalised weights; qbone/tbone lists and per-vertex skin rows must round-trip
  (T3501).
- **T2504 (structural diff)**: diff on name, parent chain, flag, hook presence,
  and bind transform — not just topology.
- **T2505 (golden)**: automated ROM + extreme-bend sweep on `N_DarthMalak`/`walk`;
  assert deformation stays within tolerance after load→bind→export→reload; gate
  export on it.
- Apply `x, z, -y` at import root; verify root bone orientation is clean.
- For MoCap/Mixamo imports, run the Map-JN through `mixamo_source_adapter.py` and
  verify hook nodes survived before accepting the clip.
- Cross-load `learned/riggingskill.md` (rig/weights), `learned/skinningdeforma
  tionskill.md` (deformation cleanup), `learned/animationruntimeskill.md`
  (runtime eval), `learned/blenderpipelineskill.md` (FBX import), and
  `learned/unrealcharacterpipelineskill.md` (UE retarget lane).

## Failure Patterns

- **Inherited animation missing/jittery**: hierarchy **order** changed, a node
  renamed, or a flag/hook dropped in the clone — re-run T2504.
- **Weapon/helmet floats or camera clips**: a hook node (head_g/Lhand_g/Rhand_g/
  camerahook) was lost or remapped during clone/retarget — re-validate hooks.
- **Joint deforms across three axes**: joint orient stacked on rotate XYZ, or
  wrong rotation order — freeze transforms, pick one store.
- **DCC and runtime deform differently at a joint**: influence count exceeds the
  cap (culling) or weights not normalised — check the T3501 round-trip.
- **Candy-wrapper / collapsing elbow at large bends**: too few twist links or
  excessive bone overlap — add twist joints, reduce overlap, re-bake ROM.
- **Retarget correct but pose wrong / feet slide**: base-pose (T vs A) mismatch,
  or root motion / retarget root not set — align poses first, scale root for
  height delta, FABRIK-plant feet onto foot_g hooks.
- **MoCap clip jitters/pops**: high-frequency noise (temporal-smooth) or un-
  matched first/last frame for a loop (match endpoints).
- **Quaternion key spins 360° mid-SLERP**: sign discontinuity across the channel
  — normalise dot-sign between consecutive keys.
- **Root has an unexpected 90° offset**: axis correction applied per-node or after
  binding — move the `x, z, -y` conversion up to import root.
- **Animation file bloated**: static joints still carrying tracks, or a hinge
  exporting three rotation curves — drop redundant tracks, fix orientation.
