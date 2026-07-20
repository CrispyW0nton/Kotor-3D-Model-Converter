# Legacy NWMax / KOTORMax Room-Recovery Skill

Use this skill when a KOTOR room survives primarily as an old Autodesk `.max`
scene, an NWMax ASCII fragment, or historical NWMax sanity reports. It captures
the Vul803 recovery contract and is not a general license to infer missing room
partitions.

## Truth order

1. Preserve and hash the original archive, `.max` scene, ASCII files, ARE/GIT/IFO,
   and sanity reports.
2. Establish the authoring version from embedded `.max` metadata.
3. Load the original scripted-plugin family before opening the scene. Saved
   plugin class identity includes both numeric class ID and superclass.
4. Export ASCII non-destructively into a new directory. Never save the source
   scene during recovery.
5. Compile through Ghost Studio, compare against vanilla byte structure, reopen
   through Map Studio, package separately, and require a manual retail warp.

Parser acceptance, MDLOps compilation, and KMAP reopen are intermediate gates;
none proves that KOTOR loads or navigates the result.

## NWMax and KOTORMax isolation

NWMax 0.8 b60 is the preferred first opener for Max 9 scenes. KOTORMax reuses
several permanent class IDs but is not lossless:

- `AuroraDLight` is a helper/Dummy; KOTORMax's corresponding Odyssey class is a
  light/omniLight.
- `AuroraReference` is a helper; the Odyssey replacement is geometry.
- The walkmesh modifier drops legacy `ig_boxes`, `ig_multimode`, and
  `ig_recalc` fields.

Never load NWMax and KOTORMax in the same 3ds Max process. Load the selected
toolset before the old scene so scripted classes exist during deserialization.
Use KOTORMax only as a visual-geometry fallback or second-stage cleanup unless
the saved-class table proves exact compatibility.

## Safe scene mutation contract

A recovery bridge may temporarily create an Aurora/Odyssey base and reparent a
manifest partition, but it must:

- preserve duplicate-name occurrence counts from the sanity report;
- require the number of scene matches to equal the manifest count;
- preserve internal parent hierarchy;
- reject animated top-level nodes rather than insert transform keys;
- snapshot frame-0 world transforms and use `with animate off`;
- restore parents/transforms in reverse order;
- restore frozen state and exporter globals;
- suppress `copy_tga`, `tga2dds`, WOK, PWK, and DWK side effects;
- reject pre-existing outputs and empty exports;
- delete the temporary base and restore any temporarily renamed saved root;
- never call `saveMaxFile`, `loadMaxFile`, or `mergeMaxFile`.

When a pinned legacy sanity report identifies non-unit-scale static nodes, an
isolated batch recipe may explicitly list those exact node names for an
in-memory `resetXForm` repair. Refuse ambiguous names, keyed or unknown/
procedural transform controllers, non-leaf nodes, and shared object pipelines.
Snapshot the evaluated world-state TriMesh—not a second application of the
node transform—including vertices, topology, material IDs, smoothing groups,
edge visibility, and every supported map channel. Require all export channels,
unit post-reset scale, independently recomputed world bounds, and every
non-target room node to remain unchanged. Publish and hash-validate the exact
ordered normalization report, then exit the run-owned Max process without
saving the staged scene. Never make this an unbounded whole-scene cleanup.

The source `.max` hash before and after a batch run is mandatory evidence.

## Vul803 evidence map

- Max sources were saved by 3ds Max 9.0 build M114.
- Surviving ARE roster: `Vul803_01a`, `Vul803_01b`, `Vul803_01c`.
- Original `01a` ASCII: 292 visual trimeshes, 11,362 vertices, 17,301
  faces, four lights, and 11 non-null textures.
- Original `01b` ASCII: one dummy plus one 254-vertex/399-face AABB. It is the
  collision source, not proof of a second visible room.
- Late `01a` and `01b` manifests overlap on 354/356 names. Shipping both late
  visual exports would duplicate/z-fight almost the whole map.
- `01c` has 34 preserved non-root manifest entries and is listed by the ARE.
- `01d` and `01e` are optional recovery artifacts because the ARE does not list
  them.
- Reconstructed base offsets are unknown. Preserve each node's world placement
  and keep the provisional LYT base at the origin until source evidence says
  otherwise.

Use `scripts/kotormax/README.md` for the exact operator sequence and guarded
MaxScript calls. Inspect the shared `W_Pilllar` node before packaging multiple
historical partitions.

## Compile contract

Use `scripts/compile_nwmax_room_candidate.py`; do not promote raw MDLOps output.
For the surviving Vul803 proof, MDLOps 1.0.2 creates 606 synthetic static
controllers, while the Ghost Studio writer creates zero.

The compiler must prove:

- visual mesh/vertex/face/texture counts survive binary readback;
- exactly one embedded AABB exists;
- node-header `+8` is zero;
- static controller count is zero;
- external WOK and embedded AABB have matching vertex/face counts and bounds;
- the WOK contains upward floor geometry only, with valid adjacency, complete
  AABB coverage, and closed perimeter loops;
- explicit AABB sources and their ancestor transforms are unambiguous;
- stacked ceiling-like non-walk components are removed, while ambiguous stacked
  walkable layers block compilation.

Live 3ds Max 2019/NWMax recovery now exists. The final run-owned compatibility
profile patches exactly three Max-2019-incompatible NWMax statements in the
staged copy while leaving the pinned original tree unchanged. Its final staged
tree hash is
`808977a31868f202cf38778a3a4f9b1c23477bbc89a75a03465f99d09136147f`.
The four typed `vul803_01a`, `vul803_01c`, `vul801_01a`, and `vul801_01c`
exports passed real `3dsmaxbatch.exe` execution, NWMax sanity, post-run input
integrity, and immutable publication.

Current merged Vul803 K1/K2 structural proof (`01a + 01c` visual shells plus
authoritative collision-only `01b`): 370 visual meshes, 17,113 visual vertices,
27,792 visual faces, 17 textures, 127 WOK vertices, 145 walkable floor faces,
11 closed perimeter loops, zero controllers, and zero nonzero node `+8` values.
Current merged Vul801 proof is 287 visual meshes, 12,754 vertices, 18,010 faces,
17 textures, 314 WOK vertices, 336 walkable faces, three closed perimeter
loops, zero controllers, and zero nonzero node `+8` values. Retail game proof
remains outstanding. Vul801's three loops are also three disconnected walkable
components; do not confuse closed/perimeter-valid structure with proof that the
intended playable regions connect or that AI can traverse them in retail.

Treat the WOK writer and the arbitrary-geometry auto-generator as separate
readiness claims. The writer has multi-loop, adjacency, AABB, and perimeter
proof. The render-derived generator has floor/wall/ceiling, slope, alignment,
and transition-edge tests, but imported/terrain hole derivation, disconnected-
island policy, and floor/ramp seam welding remain explicit gaps.
