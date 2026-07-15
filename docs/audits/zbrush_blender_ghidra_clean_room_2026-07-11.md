# ZBrush 2026.0.1 + Blender 5.0.1 clean-room Ghidra pass

Date: 2026-07-11  
Scope: topology editing, bevel/extrude, sculpt/brush organization, picking, undo, mesh data, modifier evaluation, and viewport update architecture.  
Method: Ghidra 12.1.2 symbol/type/string/xref/call-relationship inventories plus bounded plaintext product-vocabulary extraction. No instructions or proprietary decompiled source were exported. No licensing, encryption, or copy-protection mechanism was bypassed.

## Inputs and reproducibility

| Product/artifact | Version/build | SHA-256 |
| --- | --- | --- |
| `C:\Program Files\Maxon ZBrush 2026\ZBrush.exe` | 2026.0.1.2 | `FDE4F8988D0881B2A09C373DD0986A46193520B4540AF12FF17A842F17BBC45F` |
| `xremeshlib2.dll` | file 1.2.0.2883 / product 1.2.1 | `D5131FD058A06505AD6F783C6CC6D54B9EDA8B0DC5623578E1E7F5A9F967FE7A` |
| `QtNoiseEditor.dll` | no version resource | `A03A91D05EEFC51F9AB2896E9CE76A9D3B6F342783E482A26513AE7AD01F6F22` |
| `zunwrap.dll` | no version resource | `8DF56BC9C269EDE8FADFF943F2A79CC8BB722D1FD727B2554EE2B85E314F424B` |
| `BevelPro.exe` | no version resource | `A027078704BB657A1F38F008E4017F1048AF3FAE62B4F32ADD94BAB2C8B3FF9A` |
| `C:\Program Files\Blender Foundation\Blender 5.0\blender.exe` | Blender 5.0.1, build `a3db93c5b259` | `F81D3BCA0AF0D917E03FDF09255981B2ED0750D3A2815DA991EA5425A87F8F7C` |
| installed `blender.pdb` | PDB matched by Ghidra's GUID/age lookup | `8FF30507143DB1640133F7A6C7299698CCF26C03F9DD0DE9CCF144E1C1F43487` |

Ghidra projects and raw evidence are deliberately outside the Ghost-Studio repository:

- `C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\Ghidra\projects\active\Blender-5.0.1\ghidra_project\Blender501.gpr`
- `...\Blender-5.0.1\exports\blender-5.0.1-program-summary.md`
- `...\Blender-5.0.1\exports\blender-5.0.1-dcc-modeling-evidence.md`
- `...\Blender-5.0.1\exports\blender-5.0.1-focused-function-relations.md`
- `C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\Ghidra\projects\active\ZBrush-2026.0.1\ghidra_project\ZBrush2026.gpr`
- `...\ZBrush-2026.0.1\exports\{BevelPro,QtNoiseEditor,xremeshlib2,zunwrap}-program-summary.md`
- `...\ZBrush-2026.0.1\exports\{BevelPro,QtNoiseEditor,xremeshlib2,zunwrap}-dcc-modeling-evidence.md`
- `...\ZBrush-2026.0.1\exports\zbrush-2026.0.1-string-surface.json`
- exporter: `C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\Ghidra\scripts\ghidra_scripts\ExportDccModelingEvidence.java`

Representative commands actually used (PowerShell; paths shortened only through variables):

```powershell
$head = 'C:\Users\NewAdmin\Documents\Ghidra\ghidra_12.1.2_PUBLIC\support\analyzeHeadless.bat'
$scripts = 'C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\Ghidra\scripts\ghidra_scripts'
$blender = 'C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\Ghidra\projects\active\Blender-5.0.1'
& $head "$blender\ghidra_project" Blender501 -import 'C:\Program Files\Blender Foundation\Blender 5.0\blender.exe' -overwrite -max-cpu 4 -analysisTimeoutPerFile 1800 -scriptPath $scripts -postScript ExportProgramSummary.java "$blender\exports\blender-5.0.1-program-summary.md"
& $head "$blender\ghidra_project" Blender501 -process blender.exe -noanalysis -readOnly -scriptPath $scripts -postScript ExportDccModelingEvidence.java "$blender\exports\blender-5.0.1-dcc-modeling-evidence.md"

$zbrush = 'C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\Ghidra\projects\active\ZBrush-2026.0.1'
& $head "$zbrush\ghidra_project" ZBrush2026 -import 'C:\Program Files\Maxon ZBrush 2026\ZData\ZPlugs64\zrem\xremeshlib2.dll' -overwrite -max-cpu 2 -analysisTimeoutPerFile 600 -scriptPath $scripts -postScript ExportProgramSummary.java "$zbrush\exports\xremeshlib2-program-summary.md"
& $head "$zbrush\ghidra_project" ZBrush2026 -process xremeshlib2.dll -noanalysis -readOnly -scriptPath $scripts -postScript ExportDccModelingEvidence.java "$zbrush\exports\xremeshlib2-dcc-modeling-evidence.md"
py -3.14 "$zbrush\scripts\extract_zbrush2026_surface.py"
```

The Blender import loaded the matching local PDB normally and recovered 181,323 functions, 176,090 with non-default names. Analysis reached its 1,800-second bound after completing PDB application and most analyzers; the log records an earlier Java-heap warning and the timeout. The saved database and focused exports are therefore strong name/relationship evidence, but not a claim that every indirect or inlined edge was recovered.

## Exact Blender evidence

The following are address-level observations in this exact Blender build. A name and direct call edge prove organization in the analyzed binary; they do not prove every runtime detail.

| Address | Static evidence | Defensible design reading |
| --- | --- | --- |
| `140A31410` | `bmo_extrude_discrete_faces_exec` calls `BM_face_copy`, `BM_face_create_quad_tri`, `BM_elem_attrs_copy`, and selection-history mapping. | Constructive operators sit over a connectivity kernel and explicitly copy attributes/selection identity. |
| `140A31690` | `bmo_extrude_edge_only_exec` calls BMO init/exec/finish, `BM_face_create_verts`, `CustomData_bmesh_get`, and `bm_extrude_copy_face_loop_attributes`. | Edge extrude is a transaction-like operator and loop/corner data propagation is part of the operation, not a later cosmetic fix. |
| `140A319C0` | `bmo_extrude_face_region_exec` calls low-level create/kill/collapse/join routines plus `CustomData_bmesh_get`. | Region extrusion is distinct from single-edge/discrete-face extrusion and maintains connectivity and custom data together. |
| `140A35F60` / `140A360F0` | separate `bmo_inset_individual_exec` and `bmo_inset_region_exec`; the region path calls edge/vertex separation and CustomData copy/free operations. | “Each face” and “region” are different topology policies, not merely one UI toggle over identical math. |
| `140A403C0` | `bmo_bevel_exec` reads float/int/pointer operator slots and calls `BM_mesh_bevel` plus `CustomData_get_offset_named`. | Bevel is parameterized and attribute-aware at the kernel boundary. |
| `1407A3000` | named `blender::bke::pbvh::bmesh_update_topology`; the evidence export resolves 29 direct callees. | Sculpt topology has a spatially partitioned update path instead of treating each stroke as an entire-scene rebuild. |
| `141B0AF10` / `141B0B000` / `141B0B5A0` | sculpt undo has `push_begin`, `push_end`, `push_node`; recovered types map PBVH nodes to undo nodes. | One stroke can be one history command while recording node-local data. |
| `1432C4450` / `1432C4460` | `BKE_undosys_stack_group_begin` and `_group_end`. | Multi-step user gestures have an explicit grouping boundary. |
| `142020FE0` | `view3d_gpu_select_ex` uses draw-select, GPU depth test, selection cache load/end/is-cached, and filtered selection. | Selection is a dedicated cached render/query service, not incidental paint-order hit testing. |
| `143475F80` / `1434763A0` | GPU pick begin/end save/restore depth/write state; end reads depth and evaluates “all” and “nearest” passes. | Occlusion correctness and nearest-result resolution are first-class selection concerns. |
| `140A6B4B0` | `DEG_id_tag_update` has 1,865 xrefs and 1,523 resolved callers, including `EDBM_update`. | Editing marks dependent data stale; a dependency/update layer decides downstream work. |
| `140312460` | `BKE_modifier_deform_verts` calls `GeometrySet::from_mesh`, `get_mesh_for_write`, `MeshTopologyState::same_topology_as`, and `Mesh::tag_positions_changed`. | Evaluated geometry, topology identity, and position-only changes are distinguished. |

## Exact ZBrush 2026 evidence

The latest main executable is a 235,248,312-byte monolith with a 227,371,008-byte `.text` section and no installed matching PDB. Earlier ZBrush 2025 attempts in the local study showed that a full exception-heavy import can grow to multi-gigabyte databases. This pass therefore did not start another unbounded main-binary analysis. It analyzed the small, directly relevant shipped modules in Ghidra and bounded the main executable to plaintext vocabulary.

| Binary/address | Static evidence | Defensible design reading |
| --- | --- | --- |
| `xremeshlib2.dll:180141E20` → `180141D00` | exports `QRLib_start`, `QRLib_startInputMesh`, setters for points/faces/normals/UVs/material IDs/polygon groups/hard edges, `QRLib_endInputMesh`, `QRLib_startOneRemeshing`, and progress/output callbacks. | A remesh stage has an explicit mesh-channel input/output contract and progress/cancellation surface. |
| `xremeshlib2.dll:180140D00` | `QRLib_doQuadRemeshing`; output getters include points, faces, normals, UVs, material IDs, groups, hard edges, and smoothing groups. | Retopology cannot be treated as positions/faces only; channel preservation/remapping must be specified. |
| `QtNoiseEditor.dll:18006EAC0` and `1800714D0` | exported `Perlin` and `SimplexTexture3D`; additional exports include Cell/Voronoi, FBM, turbulence, eroded, grid, brick, wood, and other `Texture3D` generators. | Procedural terrain/material authoring benefits from a composable field library rather than hard-coded brush cases. |
| `zunwrap.dll:18009A8F0` / `18009F290` | exports `DoUnwrap_NoCut`, `GenMeshWithUVTopo`, `GetUV*`, `NewUVs`, `TransferUVs`, `SetUVMapSize`, `SetUVMapBorder`; strings report submeshes, seams/cut nodes, and ARAP failure. | UV topology, seams/charts, solving, and transfer back to the mesh are separate stages with explicit failure reporting. |
| `BevelPro.exe:1408DF178` / `1408DF150` | xref-backed UI strings `Triangulate Bevel Surface` and `Triangulate Bevel Junctions`. | Output topology policy is exposed separately from bevel width. |
| `BevelPro.exe:1408DEFD8` / `1408DEFE8` | xref-backed `Bevel Amount` and `Bevel Smoothness`; `Chamfer`, analysis options, and mesh-output options are also present. | Bevel is a persistent parameter family with analysis and output controls, not a one-value immediate command. |
| `BevelPro.exe:1409F2DE0` (RTTI string) | name contains `makeCreases`, `EdgeSet`, `BevelSurface`, partition, and operand-vertex vocabulary. | The separate plugin exposes evidence of crease-aware boundary/output concepts, but the string alone does not prove its algorithm. |
| `UInterface.zsc` (SHA above) | plaintext vocabulary includes separate point/edge/polygon/curve actions; QMesh targets; edge/PolyLoop targets; “Inset Each Poly” vs “Inset Region”; ALT-tap mode switching; bevel resolution/profile/steps; ZModeler selection/welding tolerance. | ZModeler's teachable unit remains context → action → target → modifiers, with predictive tolerance/parameter controls. |

## What Ghost-Studio already has and should preserve

The present worktree contradicts several old gap reports; these items should not be rebuilt from scratch:

- `GhostRigger.Core.Math/Python/src/core/geometry/mesh_topology.py` is now a seam-aware half-edge/connectivity view with raw and welded geometric indices, connected shells, boundary chains, manifold auditing, stable remaps, material/smoothing groups, and UV-channel discovery.
- Map Studio has depth- and perspective-correct nearest-visible face/edge/vertex picking in `map_studio_hover_context.py`.
- Map Studio's imported-room bevel has live width plus segments, profile, auto/sharp/patch miter, smoothing-angle, UV policy, overlap clamp, manifold validation, and resident preview.
- Extrude and bevel patch one live room-mesh node and avoid `load_model()` during the gesture.
- Terrain sculpt uses a stroke-owned flat buffer, dirty rectangle plus halo, partial normal recomputation, and one commit.
- Combine Meshes and Separate Shells are genuine polygon/shell operations with authored provenance, not merely display groups.

## Remaining actionable Ghost-Studio gaps

Ordered by impact on manual modeling quality:

1. **Unify the operator kernel across studios.** Map Studio's imported-room bevel is much stronger than the general Mesh Tools path: `mesh_tools/mesh_editing.py::bevel_selected` is still implemented as inset and warns that more than one segment is unavailable. Extrude/inset implementations also duplicate channel policy. Put the robust edge/region operators behind one format-neutral core API, then adapt Map Studio, KMAX, Character Studio, and Retarget previews to it.

2. **Make `TopologyChangeSet` real output, not a dormant type.** The type exists, but the current worktree has no constructor use. Every topology operator should return created/deleted/dirty component IDs, old↔new remaps, affected channel ranges, bounds, and preview/commit identity. Selection, renderer residency, WOK staleness, and undo should consume that one record.

3. **Move from whole-array preview patches to range-aware mesh-resource updates.** Map Studio correctly avoids a whole renderer reload, but `apply_component_mesh_preview` still replaces all vertex/face/normal/UV arrays and evicts the node cache each frame. A change-set-driven renderer adapter should update only changed ranges when topology is stable and reallocate only the edited mesh resource when topology changes. Keep the existing safe full-node fallback.

4. **Centralize attribute propagation.** Generated topology needs a channel registry covering point, corner/loop, face, and object domains: UV0, lightmap UV, normals/tangents, smoothing/crease, material, selection/provenance, skin weights, and KOTOR walkmesh ownership. The general extrude currently copies UVs by vertex and disables skinned edits; the stronger Map Studio operator should become the shared reference. A topology edit is not complete until its channel remap is valid.

5. **Add domain-delta undo under the existing command boundary.** Current Map Studio history captures serialized full-KMAP before/after snapshots per committed command. It correctly avoids doing this per pointer frame, but large authored projects still pay whole-project memory/serialization cost. Retain one gesture = one command, while storing mesh change sets, terrain patches, and texture sidecar patches as domain deltas; keep periodic full checkpoints for recovery. Add explicit group begin/end for compound tools.

6. **Keep CPU depth-correct picking now; add an optional ID+depth cache for scale.** The correctness bug is fixed. For very large imported modules, a stable component-ID/depth selection pass can amortize hover queries and resolve gizmo/object/component priority. Invalidate it from topology/transform change sets. Do not regress to draw-order selection and do not replace the CPU path until visible parity tests pass.

7. **Separate authored parameters, evaluated preview, and export bake.** Interactive bevel already has persistent controls during a gesture, but committed edits are destructive arrays. A small KMAP operator/history record for bevel, extrude, remesh, UV unwrap, and terrain procedural fields would allow re-editing parameters, evaluating only the affected mesh, then baking deterministic Odyssey geometry at export. This is the useful architectural idea behind modifier/evaluated-mesh evidence; copying Blender's implementation is neither needed nor authorized.

8. **Use procedural/noise and remesh evidence as interface guidance only.** Build or adopt legally compatible implementations behind GhostRigger-owned field/remesh/UV interfaces. Do not redistribute or call the ZBrush DLLs by default, and do not represent their private exports as a stable SDK.

## Acceptance gates for the next implementation pass

- One cube-edge fixture exercised through Map Studio and general Mesh Tools must produce equivalent, manifold results for 1/3/8 segments and profiles 0.25/0.5/0.75, with explicit expected miter outcomes.
- Attribute checks must cover material IDs, UV0 seams, lightmap UVs, normals/tangents, smoothing, provenance, and (where enabled) normalized/capped skin weights after every topology edit.
- One drag must create exactly one undo command; undo/redo must restore geometry, selection, attributes, readiness/stale-output flags, and resident preview without a whole-project mismatch.
- Renderer instrumentation must prove no `load_model()` during a gesture and distinguish position-only buffer updates from topology reallocations.
- Picking fixtures must include near/far overlapping triangles, edge/vertex thresholds, gizmos, hidden/back-facing geometry, perspective-correct UV interpolation, and cache invalidation after edit.
- Terrain tests should prove dirty rectangle + halo updates, per-stroke undo, slope/WOK consequences, and bounded memory at practical grid sizes.
- KOTOR-facing completion still requires vanilla-structural MDL/MDX/WOK comparison, module package validation, and a manual KOTOR 2 warp/log session. Ghidra or viewport success is not engine proof.

## Unsupported claims (explicitly rejected)

- The pass does **not** recover or reproduce proprietary ZBrush, Blender, or Maxon source code.
- BevelPro is a separate shipped tool; its evidence does **not** prove that ZModeler's internal bevel uses the same algorithm or classes.
- QtNoiseEditor is NoiseMaker/procedural-texture evidence; it does **not** prove ZBrush's core sculpt-brush kernel or stroke scheduler.
- `xremeshlib2` export names do **not** grant redistribution rights, promise ABI stability, or prove safe use inside GhostStudio.
- A symbol/string/xref proves presence and a static relationship, not frame timing, thread policy, numerical behavior, UI feel, or runtime performance.
- Blender's full analysis timed out; indirect calls, inlined functions, and some types may be absent despite the matched PDB.
- No conclusion here proves that a Ghost-Studio result loads or animates in KOTOR. Only vanilla-structural comparison and in-game proof can establish that.
