# Blender Pipeline Skill

Use this skill for importing Blender-authored FBX/OBJ/glTF into GhostRigger's
Character Studio: extracting the armature, deform bones, vertex-group weights,
bone orientation, UVs, and shape keys, and applying the Blender→KOTOR axis
conversion.

## Book Grounding

- `Learning Blender` (Villar): the armature/bone model (deform vs control vs
  helper bones, head/tail direction, parenting `Connected` vs `Keep Offset`,
  bone roll/orientation via `Ctrl+R` / `Ctrl+N → Active Bone`, X-Axis Mirror),
  Object/Edit/Pose modes and the rest-pose rule, constraints (Track To, Copy
  Rotation, IK, Limit), the Armature modifier + Automatic Weights, vertex groups
  named after bones, weight painting (Add/Subtract/Draw/Blur, X-Mirror, Vertex
  Weights panel, copy/paste weights), non-deform object parenting, bendy bones
  for twist, and shape keys (blendshapes) driven by bones.
- `Technical Animation in Video Games` (Lake): coordinate-system compensation
  (put the axis offset at the root of the pipeline, not per-node) and the
  joint-vs-bone / joint-orientation data the runtime needs.
- `3D Mesh Processing` (Mukundan): the bone data structure (index, name, vertex
  set, offset matrix) the importer must reconstruct from Blender vertex groups.

Load `learned/unrealskill.md` (FBX/DCC handoff conventions are shared),
`learned/technicalanimationskill.md` (joint orient / offset matrix), and
`learned/meshprocessingskill.md` (imported-mesh cleanup).

## The Importer's Job

GhostRigger's Blender FBX importer lives in `src/io/fbx/` and
`native/GhostRigger.Core.IO/Python/src/converters/blender_fbx_mesh_importer.py`.
It was recently fixed to convert **Blender world axes to KOTOR object space via
`x, z, -y`**. The importer must reconstruct, from the FBX, the same data
structures a DCC uses internally — and Blender's conventions are specific enough
that getting them wrong produces classic "the mesh is there but won't bind" or
"the arm twists 90°" bugs.

## Armature And Bone Model

In Blender a rig is a single **armature** object containing **bones**. A bone
has a **head** and a **tail**; the bone's direction is head→tail, and that
direction defines the chain direction. A bone connected to another's tail is its
**child** and follows it.

Three bone roles — and only the first is export-relevant for skinning:

- **Deform bones** — actually deform the mesh. **Only these carry skin weights
  and must be extracted into the Odyssey DAG / qbone-tbone lists.** They are
  usually hidden and driven by control bones.
- **Control bones** — what the animator selects/moves. UI-only; **must not** be
  exported as deformers. The importer must filter them out (Blender marks deform
  bones via the bone's "Deform" flag — read that flag, do not assume by name).
- **Helper bones** — make constraints/IK work; hidden, never animated directly.
  Export-only as needed for any procedural behaviour KOTOR supports.

> The single most common Blender-import bug is exporting control/helper bones
> as deformers. Read the bone **Deform** flag and build the skin from deform
> bones only. This is the Blender analogue of the AGENTS.md rule "validate
> naming and side conventions before export."

### Hierarchy and parenting

- `Connected` parenting welds the child's head to the parent's tail; `Keep
  Offset` parents while leaving a gap. The importer must preserve the **parent
  chain and order** exactly — KOTOR animation inheritance (supermodel
  semantics) breaks on reordering even when names survive (see
  `learned/technicalanimationskill.md`, the Odyssey DAG lock).
- Blender's rest pose is the **Edit Mode** bone layout. Capture positions/
  parent chains in that mode as the bind pose.

### Bone orientation (roll / local axes)

- Bone **roll** (`Ctrl+R`) sets the rotation around the head→tail axis; `Ctrl+N
  → Active Bone` aligns the local axes of selected bones to the active bone
  (used to consistently orient finger/arm/leg chains).
- This is Blender's joint-orient. Capture each deform bone's **local rotation
  axis / roll** in the import — without it, a forearm that should twist on one
  axis will deform across three, and the exported animation carries 3× the
  rotation curves. This feeds the T2501 DAG snapshot's "hooks and bind data".

### Symmetry / side conventions

- `X-Axis Mirror` mirrors extrusions/transforms across the mirror plane; weight
  `X-Mirror` mirrors painted weights to the opposite-side bone. Both require
  consistent **L/R naming** (Blender suffixes `.L`/`.R`). GhostRigger must
  preserve these suffixes through import so mirroring, weight transfer, and
  retarget side-mapping stay correct (AGENTS.md: validate naming and side
  conventions).

## Skinning: Armature Modifier + Vertex Groups

Blender skinning = an **Armature modifier** on the mesh + **vertex groups** that
store weights. This maps directly onto KOTOR's per-vertex skin rows:

- Parenting a mesh to the armature with **Automatic Weights** adds the Armature
  modifier **and** creates one vertex group per bone, **named identically to the
  bone**, with distance-based weights. The importer must read these vertex
  groups: group name = bone name, per-vertex weight = influence. That is exactly
  the `(vertexId, boneName, weight)` triple a bone map / skin row needs.
- **Envelopes** are an alternative (proximity-based) weighting; if present,
  decide explicitly whether to bake them to vertex weights at import — do not
  silently drop them.
- **Modifier stack order matters**: the Armature modifier must sit **before**
  Subdivision Surface in the stack (subdiv should be last), otherwise weighting
  acts on subdivided geometry and is slow and wrong. If the source had subdiv,
  decide at import whether to keep the base cage (recommended for KOTOR's
  triangle budget).
- **Normalise and cap influences**: Blender weights can exceed KOTOR's influence
  cap. Validate that each vertex's influencing deform bones respect the cap and
  that weights sum to 1 (AGENTS.md skinning rule; see
  `learned/technicalanimationskill.md`).

### Weight tools the importer should honour

- Brushes: Add / Subtract / Draw / Blur. Blur softens weight borders at
  articulations — the importer should treat a cleanly-blurred weight set as
  trustworthy and a spiky one as suspect.
- **Vertex Weights panel** / copy-paste-weights: precise per-vertex values and
  weight copying between vertices (used to keep edge loops equally weighted).
- Mirror weights before painting (join sides, `X-Mirror`, then split) or after
  (duplicate, mirror geometry, rename `.L`→`.R` groups). Either way the imported
  data should be side-symmetric when the source was.

## Non-Deform Objects And Shape Keys

- **Non-deform objects** (hair, cap, teeth, eyes) are simply **parented to a
  bone** (`Ctrl+P → Bone`), with no Armature modifier and no weights. The
  importer must distinguish "parented rigid" from "skinned deformable" — rigid
  attachments become node-children in the DAG, not skin influences.
- **Shape keys** (blendshapes) store alternate vertex positions blended by a
  0→1 slider. If present and KOTOR-equivalent morph targets are needed, capture
  them; otherwise strip them. Drive them via bones in Blender, but for KOTOR
  export treat them as authored vertex deltas.
- **Bendy bones** subdivide one bone into segments to emulate twist/curve (e.g.
  forearm twist). If the source uses bendy bones, decide whether to bake them
  into a small twist-bone chain (matches the twist-link fix in
  `learned/technicalanimationskill.md`) at import.

## Axis Conversion (the `x, z, -y` fix)

Blender is Z-up right-handed; KOTOR object space is its own convention. The fix
that was recently applied: convert Blender world axes to KOTOR object space as
**`x, z, -y`** (Blender `(x, y, z)` → KOTOR `(x, z, -y)`). Rules from the
book that make this robust:

- Apply the conversion **once, at the root of the import pipeline**, not per-
  node. A per-node offset leaves every runtime orientation calculation fighting
  a baked-in rotation.
- Re-derive **normals/tangents via the inverse-transpose** of the conversion
  matrix, not by converting them as points (AGENTS.md).
- After conversion, verify the **root deform bone** has a clean, zeroed
  orientation in KOTOR object space. A residual 90° offset on the root means the
  conversion was applied at the wrong level.
- Re-validate the **bounding-box centroid** lands where expected relative to the
  target Odyssey node — a wildly off-centroid import is almost always an axis or
  unit-scale bug.

Blender unit scale also matters: FBX exports in centimetres by default. Confirm
the import scale so the mesh fits the native node rather than being 100× too
large/small.

## FBX / DCC Handoff Constraints For KOTOR

- Export **deform bones only** as the skinning skeleton; keep control/helper
  bones out of the export (or in a non-deform layer) so they don't pollute the
  qbone/tbone lists.
- Keep **vertex group names == deform bone names == target Odyssey node names**
  (or emit an explicit rename map). Name drift is the silent killer of weight
  transfer and retarget.
- Preserve **L/R suffixes** for mirroring and side-mapping.
- Decide **triangulation** deliberately (quads → triangles) before export so the
  split diagonals match intent; don't let the runtime auto-triangulate concave
  quads (see `learned/meshprocessingskill.md`).
- Keep **UV seams** and **material slots** 1:1 through export; KOTOR material
  slots must not silently recombine.
- Run the imported-mesh topology audit (winding, open edges, duplicates,
  isolated verts, missing/flipped UVs, degenerate tris) right after import,
  before bind — AGENTS.md treats mesh edits as topology contracts.

## GhostRigger Checks

- In the FBX importer (`blender_fbx_mesh_importer.py`), extract: deform bones
  (by Deform flag) with head/tail/roll/parent-chain, vertex groups → skin rows
  (group name = bone name), rigidly-parented non-deform objects as DAG children,
  and optional shape keys.
- Apply the `x, z, -y` axis conversion at import root; re-derive normals as
  `M^{-T}`; confirm root bone orientation is clean.
- Normalise and cap influences to KOTOR's limit; assert weights sum to 1.
- Preserve hierarchy order and L/R naming into the T2501 DAG snapshot.
- Feed the extracted deform skeleton + skin rows straight into T2503 (bind
  imported skin) and validate against writer/loader truth (T3501).
- Load `learned/technicalanimationskill.md`, `learned/meshprocessingskill.md`,
  and `learned/riggingskill.md` together for Character Studio import cases.

## Failure Patterns

- Mesh binds but a limb twists 90° / deforms on the wrong axis: bone **roll /
  local axis** not captured, or axis conversion applied per-node instead of at
  the root.
- Weights present but mesh won't deform: control/helper bones exported as
  deformers, or vertex-group names drifted from bone names — filter by Deform
  flag and assert name equality.
- Import is 100× wrong scale: FBX unit scale (cm) not reconciled with KOTOR
  units.
- Normals look inverted/shaded wrong after import: normals converted as points
  instead of via `M^{-T}`.
- One side deforms differently from the other: L/R suffixes lost or weights not
  mirrored — re-validate side naming.
- Subdivided mesh slow / wrongly weighted at bind: Armature modifier sat after
  Subdivision Surface in the source — bake to the base cage at import.
