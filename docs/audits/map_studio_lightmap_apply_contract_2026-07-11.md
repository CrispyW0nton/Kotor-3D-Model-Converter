# Map Studio Applied-Lightmap Contract Audit

Date: 2026-07-11

Owner: LordVaderCW

Roadmap: T2908 / T3103

Status: historical pre-implementation audit, with implemented-slice update

## Implemented Slice Update

The gap analysis below records the state that existed when this audit was
written. The selected-surface transaction is now implemented: Map Studio can
generate seam-correct UV2 with the xatlas vertex remap, bake authored room
lights plus optional ARE ambient, encode a project-owned RGBA TPC with the
vanilla lightmap TXI trailer, assign the surface's lightmap/UV2/texture-count
contract, include it in the MOD resource inventory, and undo both the KMAP
change and sidecar. The generated 64x64 TPC path matched installed K2
`001ebo1_lm0` and `001ebo1_lm1` byte-for-byte, and focused tests proved package
readback, collision rejection, and rollback.

This does not make the entire audit complete. Bake Selected Room/Bake All,
multi-atlas management, automatic staleness for every downstream topology or
lighting edit, complete raw MDL mutation coverage, and manual K1/K2 warp proof
remain open. Read the subsequent "Where The Current Chain Stops" and
"Critical Blockers" sections as the historical design baseline; resolved
items are superseded by this update and the active environment roadmap.

## Conclusion

GhostStudio's current MDL/MDX writer can encode the core KOTOR lightmap channel
shape when it receives a real lightmap resref and one UV2 value per exported
vertex. The missing product is the persistent, atomic Map Studio transaction
that turns a preview bake into a KMAP binding, seam-correct vertex stream,
packaged texture resource, validated room model, and honest proof state.

The existing general lightmap baker and main-viewport Apply action did not do
that. They remain separate from the implemented Map Studio selected-surface
transaction, which must still be described as an applied-lightmap candidate
until manual game proof exists.

## Vanilla Structural Oracles

### K2 `001ebo1`

- 60 total model nodes and 19 render meshes;
- 13 of the 19 render meshes are lightmapped;
- every lightmapped mesh has equal vertex, UV0, and UV2 counts;
- `texture_count=2` and `has_lightmap=1`;
- texture slot 2 is `001ebo1_lm0` or `001ebo1_lm1`;
- MDX stride is 40 bytes, bitmap is `0x27`, and offsets are position 0,
  normal 12, UV0 24, UV2 32;
- both lightmaps are 64x64 RGBA TPC resources, 16,572 bytes each;
- embedded TXI contains `islightmap 1`, `compresstexture 0`, `mipmap 0`, and
  `downsamplemax 0`;
- sampled lightmapped surfaces use `has_shadow=False`. Preserve source flags;
  do not generalize that observation to every room without more vanilla data.

### `tst_light/r00_test` Negative Control

- MDL 25,533 bytes and MDX 7,136 bytes;
- seven render meshes plus WALK;
- no lightmapped surface;
- `texture_count=1`, `has_lightmap=0`, stride 32, bitmap `0x23`, and lightmap
  offset `0xFFFFFFFF`.

A synthetic authored room passed through current `_make_room_model_bytes` and
Core.IO `mdl_writer` matches the core positive fingerprint when its
`PrimitiveMesh` already carries the correct resref and UV2. Do not rewrite the
writer slot without a new vanilla mismatch.

## Where The Current Chain Stops

1. Core.Rendering `lightmap_baker.py` writes preview image files and assigns a
   transient `_gr_baked_lightmap_path`; it intentionally does not update the
   source model lightmap slot.
2. The main-window viewport Apply action mutates loaded viewport nodes only.
   It does not update KMAP or authored export state.
3. `authored_module_export.py::_primitive_mesh_to_node` can preserve imported
   `metadata.lightmap` and `metadata.uvs_lm`, but newly baked data never reaches
   them.
4. Existing texture-sidecar packaging has no lightmap binding. Current bake
   output permits PNG/JPG, non-power-of-two sizes, unbounded filenames, RGB
   output, and no required lightmap TXI.
5. Readiness accepts a status string plus any manifest path. It does not prove
   the manifest exists, topology revision matches, UV2 is valid, the MDL slot
   exists, the package contains the resource, or TXI marks it as a lightmap.
6. The raw KOTOR module engine-contract validator has no lightmap checks.
7. Imported KMAP surfaces preserve lightmap name and per-vertex UV2 but not all
   source render flags such as `has_shadow`.

## Critical Blockers

### UV Topology

The xatlas path discards `vmapping` and stores independent `uvs_lm` plus
dynamic `face_uvs_lm`. KOTOR MDX serializes UV2 strictly by vertex index and
the writer has no `face_uvs_lm` channel. A seam that assigns two atlas UVs to
one geometry vertex can preview correctly but export incorrectly.

Apply must retain xatlas's remap, duplicate/remap the complete output vertex
stream (position, normal, UV0, material/face identity), and attach exactly one
UV2 to each output vertex.

### Stable Identity

Assignments currently key by node name, but vanilla rooms can repeat names;
`r00_test` repeats `Cube` and `Diffuse`. Bind by room resref plus stable surface
role/index, never node name alone.

### Transaction And Adapter Gaps

- `LightmapBakeResult.ok` can be true when an individual target has errors.
  Apply requires every requested target to succeed.
- The current baker mutates transient assignments after each file write, so a
  late failure can leave partial state. Preview must be immutable/in-memory;
  only Apply may mutate KMAP or files.
- Authored light property names do not fully match the solver's adapter names.
  Add one explicit bake-light adapter; do not silently default ambient/spot
  properties.
- Fullbright plus applied lightmaps needs an explicit policy or blocking rule.
- Topology edits can leave UV2 counts valid while creating overlapping islands.
  Geometry changes must stale the binding and require validation/rebake.

## KMAP Binding

Add a project-level `AuthoredLightmapBinding` overlay keyed by stable room and
surface identity. Suggested version-1 fields:

- binding ID, room resref, surface role/index, target game;
- topology hash and bake-input hash (topology, room transform, world lighting,
  placed lights, and settings);
- <=16-character collision-checked lightmap resref and channel 1;
- xatlas remap, remapped faces, UV2, output vertex/face counts;
- project-relative image/resource path, SHA-256, dimensions, format, alpha;
- TXI proof including `islightmap 1` and bake settings/source-light summary;
- state: applied, stale, structurally verified, or game tested, plus proof link.

Pixels remain sidecars under `<kmap>_assets/lightmaps`; KMAP stores references,
hashes, and the compact remap, not image blobs. Export applies the overlay only
when its topology hash matches, then injects lightmap resref, UV2, two texture
channels, and `tex_count=2` into the compiled surface.

Use a content-addressed new resref on every Apply. A crash may then leave an
unreferenced orphan but cannot corrupt the currently referenced lightmap.

## Atomic Apply Sequence

Preview does not write files or history. It compiles final target geometry,
computes stable identities/hashes, preserves valid stock UV2 or creates the
xatlas remap in memory, performs a low-resolution memory bake, and installs a
viewport override only.

Apply is one undoable transaction:

1. Recheck project revision, topology hash, and bake-input hash.
2. Bake every target to memory/staging; abort unless all succeed.
3. Validate power-of-two dimensions, RGBA/finite pixels, UV2 bounds/overlap/
   degeneracy, <=65,535 output vertices, and unique <=16-character resrefs.
4. Encode candidate TPC with embedded vanilla-style TXI (or use TGA+TXI only
   after game proof), decode/read it back, and compare dimensions/hash/TXI.
5. Build a candidate authored project with bindings/assets and build the module
   in memory before committing.
6. Raw-parse each candidate MDL/MDX and require slot 2, texture count 2,
   `has_lightmap=1`, bitmap lightmap bit, valid lightmap offset, and vertex/UV2
   parity. Require matching packaged bytes and `islightmap 1`.
7. Capture KMAP and sidecar before-state; atomically promote sidecars, install
   candidate KMAP, mark MDL/MDX/TPC/MOD/proof stale, and record one command.
   Restore files and KMAP on any exception. Undo/redo restores both together.
8. Geometry, transform, world-light, placed-light, or bake-setting changes
   immediately compare hashes and mark the binding stale/block export.

Applied resources join the authored module's merged extra-resource inventory.
Until manual proof establishes TPC-in-MOD behavior for both games, stage an
explicit Override lightmap resource manifest alongside the module rather than
assuming the MOD alone is sufficient.

## Owners

- Bake/atlas/output: Core.Rendering lighting baker, UV atlas, bake job,
  manifest, output, and solver modules.
- Binding/compiler/apply: a focused Core.Scene module integrated with KMAP
  bridge, preview, exporter, controller, texture assets, and sidecar journal;
  keep Scene/Tools mirrors identical.
- Writer: Core.IO `mdl_writer`; add guards only unless vanilla proves a writer
  mismatch.
- Validation: Core.Validation raw module contract plus authored readiness.
- UI: Map Studio Environment/lightmap panel only; do not route through the
  general main-window viewport Apply action.

## Focused Proof Gates

- xatlas seam fixture proves full vertex-stream remap and preserves UV0/normals;
- duplicate-name fixture proves stable target identity;
- KMAP binding round-trip and hash-based staleness;
- partial-target failure and second-sidecar-write failure remain atomic;
- one undo/redo restores KMAP plus files;
- raw MDL mutation tests for every missing/invalid lightmap field;
- resource/TXI/hash/dimension/resref rejection tests;
- `001ebo1` editable export preserves all 13 lightmap recipes, UV2, and source
  flags against the base BIF;
- `r00_test` remains the negative control, then receives one diagnostic
  gradient lightmap structurally compared with `001ebo1`;
- targeted baker/import/export/readiness/payload tests, round-trip checks,
  K2 gameplay matrix, and package readback inventory;
- real Debug-app Preview/Apply/Undo/stale proof;
- manual K1 and K2 warp with live log and screenshot/video proving orientation
  and seam behavior.

Parser, archive, or viewport success alone is not full lightmap support.
