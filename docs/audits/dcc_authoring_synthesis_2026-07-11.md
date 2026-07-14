# DCC authoring synthesis for GhostStudio

Date: 2026-07-11

Owner: LordVaderCW

Scope: Maya/ZBrush/Blender modeling, AccuRIG character setup, Substance Painter
texture authoring, and the KOTOR-facing proof boundary

## Status in one sentence

GhostStudio now has a usable, test-backed manual authoring core—depth-correct
component picking, live resident extrude/bevel previews, real mesh
combine/separate, dirty-buffer terrain sculpting, flattened diffuse painting,
persistent rig-stage state, and reloadable animation injection—but it does not
yet have full Maya/ZBrush/AccuRIG/Substance parity or final in-game proof for
the latest map and animation outputs.

## Evidence boundary

The clean-room studies used Ghidra 12.1.2 symbols, types, strings, xrefs, direct
call relationships, bounded product vocabulary, and documented runtime checks.
They did not copy proprietary source, algorithms, shaders, file schemas, or
assets. Static evidence establishes product boundaries and responsibilities;
it does not establish exact math, frame timing, numerical behavior, or KOTOR
compatibility.

Primary reports:

- Maya 2025.3.1:
  `C:/Users/NewAdmin/Documents/GDeveloper/Workspaces/Ghidra/projects/active/maya-2025-modeling/findings.md`
  and `topology-engine-deep-dive.md`.
- ZBrush 2026.0.1 and Blender 5.0.1:
  `docs/audits/zbrush_blender_ghidra_clean_room_2026-07-11.md`.
- AccuRIG 2.1.0.584:
  `docs/audits/accurig_native_workflow_clean_room_2026-07-11.md`.
- Substance Painter 11.1.1:
  `docs/audits/substance_painter_workflow_boundary_clean_room_2026-07-11.md`
  and `substance_painter_texture_paint_clean_room_2026-07-11.md`.

## Evidence translated into GhostStudio contracts

| Source | Evidence-supported product contract | What the evidence does not prove |
| --- | --- | --- |
| Maya | A gesture is one begin/update/commit-or-cancel transaction; editable connectivity, component remaps, attribute propagation, preview overrides, dirty caches, selection, and undo describe the same edit. Bevel is parameterized; Combine/Separate operate on polygon shells. | Autodesk's private algorithms, exact data structures, or a requirement to copy Maya's wing-edge implementation. |
| Blender | BMesh operators propagate loop/custom data; sculpt updates and undo can be node-local/grouped; picking owns depth/nearest resolution; dependency tags distinguish position and topology changes. | Complete control flow from the timed-out full analysis, or exact runtime scheduling and performance. |
| ZBrush | ZModeler's teachable vocabulary is context → action → target → modifiers. Shipped remesh/unwrap/noise/bevel modules expose channel-rich inputs, staged outputs, parameters, progress, and failure boundaries. | That BevelPro implements ZModeler, that NoiseMaker is the sculpt kernel, or that any private DLL is a supported redistributable SDK. |
| AccuRIG | Import, body landmarks, fingers, skeleton, correspondence, weights, bind bake, validation, and export are distinct revisioned stages with editable state, progress, failure, and cancellation boundaries. | Landmark detection, correspondence, voxel, weighting, smoothing, or threshold algorithms; "heat diffusion" is specifically unsupported by the evidence. |
| Substance Painter | Authored layer state, global transaction history, evaluation/bake jobs, and backend texture residency are separate owners. A stroke should be one transaction with dirty-region feedback. | Painter's dab kernel, layer schema, blend equations, tile size/eviction, shaders, bake math, or thread policy. |

## Implemented and verified in the current worktree

### Modeling, terrain, and map authoring

- Map Studio chooses the closest visible face/edge/vertex using depth- and
  perspective-correct picking, including per-corner KOTOR UV seams.
- Extrude and the imported-room bevel update one resident preview mesh during
  the gesture and avoid `load_model()`; bevel exposes width, segments, profile,
  miter, smoothing, UV policy, overlap clamping, and manifold validation.
- Multi-object transforms preserve the selection; Combine Meshes produces one
  editable polygon mesh with shells, and Separate Shells partitions real
  disconnected geometry with provenance.
- Terrain strokes use a mutable flat height buffer, dirty rectangle plus halo,
  partial normal updates, and one commit. Plane → sculpt → floor-only WOK
  generation/export is covered, including a perimeter record.
- Focused proof recorded in the worktree includes GModeler core 27/27,
  GModeler/Map Studio UI 53/53, terrain/WOK/export 16/16, and the K2 `plcaa`
  vanilla-derived structural/gameplay matrix 18/18. A visible Debug-app Map
  Studio pass is recorded separately in `CHANGES.md`.

### Texture authoring

- The first diffuse-paint slice has closest-visible UV projection, pressure,
  opacity/flow/hardness/spacing, image stamps, linear-light RGB composition,
  64-pixel dirty tiles, targeted renderer updates, project-owned TGA/TXI
  sidecars, and one chronological command per stroke.
- K1/K2 package readback verifies the authored texture pair and room material
  reference. Stock resources remain read-only.
- This is intentionally a flattened diffuse-UV0 workflow, not a claim of
  Substance parity.

### Character and animation authoring

- `RigSession` persists the source/body-landmark/finger/skeleton/
  correspondence/weights/bind/export stage graph with stable IDs, revisions,
  transitive stale invalidation, JSON-safe artifacts, interrupted-job recovery,
  and preservation of the last valid output after failure or cancellation.
- Character Builder wires only stages backed by real current operations; it
  does not falsely mark correspondence or bind complete.
- Retarget POSITION controllers now serialize Odyssey rest-local deltas, while
  FK continues to use absolute local transforms. Resource-manager propagation
  resolves valid animation slots inherited through a target supermodel chain.
- A real UE mannequin FBX (87 source bones) retargeted to K1 PMBAM (61 target
  bones), mapped 40, dropped 44, collapsed 3, left 0 unmapped, and wrote a
  302-frame/30 fps `victory` local override. Independent MDL/MDX reload found
  one 10.0667-second animation with 61 animated nodes. Writer roundtrip
  verification was enabled.
- The proof artifacts are under
  `Saved/RetargetProof/ue5_idle_pmbam_cli_full_injection_2026-07-11/`.
  This is writer/readback proof, not in-game animation playback proof.

### Onboarding, UI, and packaged host

- Help/F1 and first run expose a theme/layout-aware ten-pillar tutorial that
  routes into the real Resource, Scene, GModeler, Map, Terrain, Texture,
  Module, Character, Retarget, and game-proof workspaces.
- Retarget Workbench has labeled output fields, theme-aware icons, clearer
  action names/status tips, and inherited-slot guidance.
- The renderer compatibility export table is restored for the embedded package
  layout. The root native post-build now copies all 18 payload DLLs beside
  `GhostStudio.exe`; `--help` reports 18/18 DLLs and 18/18 manifests.
- Focused overlapping suites recorded for this slice include 97 passed / 1
  skipped across payload, tutorial, RigSession, retarget/export, controller,
  and animation-injector cases; the broader retarget battery passed 155 with 1
  skipped and 1 deselected.

## Remaining gaps, in priority order

1. **One operator kernel and real change sets.** General Mesh Tools still trails
   Map Studio's bevel. Make `TopologyChangeSet` the actual result of every
   operator and route stable component remaps, dirty ranges, selection,
   readiness, WOK staleness, renderer updates, and undo through it.
2. **Central attribute propagation.** Define one channel registry for UV0,
   lightmap UV, normals/tangents, smoothing/crease, materials, provenance,
   WOK ownership, vertex colors, and normalized/capped skin weights.
3. **Range-aware renderer updates.** Keep the safe full-node fallback, but use
   position-only range uploads when topology is stable and edited-mesh-only
   reallocation when it changes. Add an optional ID+depth pick cache only after
   visible parity at large module scale.
4. **Editable operator/evaluation state.** Preserve immutable input revisions
   plus re-editable bevel, extrude, remesh, unwrap, and procedural-terrain
   parameters; evaluate a preview and bake deterministic Odyssey arrays only at
   commit/export.
5. **Domain-delta history.** Replace remaining full-KMAP modeling snapshots
   with mesh/terrain/texture deltas plus periodic recovery checkpoints and
   explicit group begin/end for compound gestures.
6. **Non-destructive texture documents.** Add paint/fill/group/mask layers,
   channel sets, reorder/merge, projection and clone/heal tools, immutable bake
   jobs, stale-result rejection, and renderer-parity tests. Flatten only for
   KOTOR preview/export.
7. **Complete Character Studio's real stages.** Implement cancellable body and
   finger detection, editable joint diagnostics, correspondence confidence,
   weight review, explicit bind bake, and the exact donor Odyssey DAG lock.
   `RigSession` is the state contract, not those missing algorithms.
8. **Finish external proof gates.** Record visible Debug-app workflows for the
   new tutorial, Retarget, and Character paths; then manually trigger the
   exported animation in KOTOR and manually warp the exact latest edited map.

## Honest completion boundary

Headless tests, viewport success, MDL/MDX reload, archive readback, and Ghidra
evidence are necessary but not sufficient. Map completion still requires a
vanilla-structural MDL/MDX/WOK comparison followed by a manual KOTOR 2 warp/log
session that proves load, render, movement, lighting, textures, transitions,
and gameplay. Animation completion similarly requires an in-game trigger and
visual deformation proof for the exact written MDL/MDX. Those manual gates
remain outstanding as of this report.
