# Character Builder Native KOTOR Pipeline Roadmap

**Date:** 2026-05-19
**Branch:** `qt-ghostrigger`
**Purpose:** revise the Character Builder launch path around KOTOR's native
Odyssey model architecture: generic scene nodes, mesh-objects-as-bones, exact
name-bound animation, and hook-based equipment attachment.

This roadmap supersedes the older "modern armature" mental model in the M12
launch path.  The goal is not to build a Blender/Unreal-style skeleton and then
convert it.  The goal is to clone and preserve a known-good KOTOR node DAG,
skin the imported mesh against that DAG, preview inherited supermodel
animations, and export MDL/MDX with the same semantics the game expects.

---

## Core Rules

1. **No separate armature abstraction in the export path.**
   KOTOR exports must be a named Odyssey node hierarchy.  A node may be a
   transform, mesh, skin, attachment hook, or several of those at once.

2. **Base model DAG is authoritative.**
   The selected KOTOR base model or supermodel provides node names, parent-child
   relationships, local transforms, hook nodes, and supermodel metadata.

3. **Node names are sacred.**
   Animation binding is by node name.  Build Skeleton must not rename, invent,
   title-case, or normalize KOTOR node names except for explicit user-created
   custom nodes that are not expected to inherit stock animations.

4. **Viewport hiding is not export deletion.**
   The editor may hide or stylize internal `_g` bone-meshes, but the export DAG
   must preserve the KOTOR node contract unless a test proves the change is
   safe.

5. **Hooks are sockets, not decorations.**
   `headhook`, `rhand`, `lhand`, `impact`, `impact_bolt`, `gogglehook`, and
   `maskhook` must be validated and previewable.

6. **Every code change that touches MDL loading, transforms, textures, skinning,
   or rendering starts with MCP ground truth.**
   Use real game models such as `s_male02`, `s_female02`, `pmbam`,
   `n_mandalorian03`, `n_darthmalak`, and representative head models before
   editing logic.

---

## Launch Definition

A KOTOR modder should be able to:

1. Pick a K1/K2 base model from game data.
2. Load an external FBX/OBJ/glTF mesh.
3. Align the mesh to the base model in the AccuRig-inspired HUD.
4. Adjust KOTOR node guide positions where needed without corrupting names or
   hierarchy.
5. Build a native KOTOR skin mesh against the cloned DAG.
6. Preview inherited stock animations from the supermodel chain.
7. Preview heads, weapons, masks, goggles, and item sockets.
8. Export MDL/MDX that reloads in GhostRigger/PyKotor and behaves in game.

---

## M17 - Native KOTOR Build Skeleton Contract

**Goal:** make Build Skeleton preserve KOTOR's mesh-object-as-bone architecture
instead of downgrading the base model into a generic helper skeleton.

| ID | Task | Acceptance |
|----|------|------------|
| T1701 | Add `NativeSkeletonSnapshot` capture for selected base models. | Snapshot records node name, parent name, flags, local transform, render/skin bits, hook classification, mesh presence, and supermodel string. Tests compare `s_male02`, `s_female02`, `pmbam`, and `n_mandalorian03` snapshots against MCP model info. |
| T1702 | Separate editor display state from export DAG state. | Hiding/stylizing `_g` nodes in the viewport no longer strips or mutates the export DAG. Tests prove `apply_template_rig()` keeps exact node names and parent chains while the viewport can hide reference geometry. |
| T1703 | Rework Build Skeleton to clone the native DAG first, then attach imported skin meshes. | Result model contains the base DAG plus imported skin node(s); prior external armatures are removed; exact base node names remain available for animation binding. |
| T1704 | Preserve KOTOR node flags intentionally. | `_g`/trimesh nodes keep native mesh identity unless explicitly marked non-renderable for editor-only display. Hook dummies remain dummies. Tests assert flags for representative nodes. |
| T1705 | Add structural diff report after Build Skeleton. | Inspector shows added imported skin nodes, removed external armature nodes, preserved KOTOR nodes, missing hooks, changed transforms, and skin row counts. |

**Bug-prevention gate:** no Build Skeleton patch merges unless:
- MCP confirms the base model node/hook facts used by the test.
- `tests/test_character_builder_template_rig.py` passes.
- A new native-DAG preservation test passes.
- Validation does not emit false `SKIN_MESH_UNRIGGED` for generated skins.

---

## M18 - Bind Pose and Weighting Correctness

**Goal:** make generated skin data match the Odyssey MDL/MDX contract well
enough to reload and animate.

| ID | Task | Acceptance |
|----|------|------------|
| T1801 | Audit and document current `skeleton_builder.py` bind tables. | Confirm whether `bone_map_floats`, `qbone_list`, and `tbone_list` match writer and loader expectations using exported/reloaded fixture models. |
| T1802 | Compute bone influence candidates from native skin maps and animation targets, not only `_g` suffixes. | Candidate list includes real deform nodes such as `rootdummy`, `lforearm`, `rhand`, and `lhand` when present, while excluding non-deform hooks such as `headhook` and `impact_bolt`. |
| T1803 | Add Library Rig transfer from selected base model. | For humanoid imports, user can copy weights from a vanilla/custom base mesh by nearest surface or nearest vertex. This becomes preferred over pure nearest-bone weighting. |
| T1804 | Keep nearest-bone auto-rig as fallback. | Auto-rig still works when no comparable base mesh exists, with clear warnings about first-pass quality. |
| T1805 | Round-trip generated skin through writer and loader. | Exported test MDL/MDX reloads with matching node count, skin rows, bone map counts, and no zero-weight vertices. |

**Bug-prevention gate:** every weighting change must run:
- focused Character Builder tests,
- regression export tests where available,
- an MCP/loader comparison on at least one humanoid body and one full-body disguise/creature-style model.

---

## M19 - Animation Assignment Through Supermodel Semantics

**Goal:** make Assign Animations behave like KOTOR: inherited supermodel chains
first, local overrides only when needed.

| ID | Task | Acceptance |
|----|------|------------|
| T1901 | Build `SupermodelChainResolver`. | Given a base model, returns ordered chain, inherited animation names, source model per animation, and missing-node warnings. |
| T1902 | Integrate LordVaderCW's Core Animation Workbench into Character Builder Step 3. | User can pick inherited animations, preview them, and optionally bake/override imported or retargeted clips. |
| T1903 | Add chain visualization in the Assign Animations tab. | UI shows active model -> supermodel chain, with each animation's source highlighted. |
| T1904 | Validate animation target node names. | Export blocks local animation overrides that target nodes missing from self or the inherited supermodel chain. |
| T1905 | Add animation smoke exports. | Reference character exports with inherited idle/walk/combat animations and reloads with animation metadata intact. |

**Bug-prevention gate:** animation work must not alter node names or pivots in
the Build Skeleton output unless the structural diff explicitly records it and
tests prove reload correctness.

---

## M20 - Native Attachment and Preview Parity

**Goal:** make Preview reflect KOTOR's parent-child hook attachment rules.

| ID | Task | Acceptance |
|----|------|------------|
| T2001 | Centralize canonical hook rules in `src/core/hooks.py`. | Body/head/weapon hooks are defined once and used by validation, preview, export, and UI labels. |
| T2002 | Implement head/body composition preview from `appearance.2da` and `heads.2da`. | Body models with `headhook` can preview real head models; head models can preview compatible body models. |
| T2003 | Build equipment/weapon library picker. | User can browse weapon/item resrefs, filter by slot, and attach to `rhand`, `lhand`, `gogglehook`, or `maskhook` as appropriate. |
| T2004 | Animate attachments through parent hierarchy. | Weapons and head equipment follow socket transforms while animations play. |
| T2005 | Add socket validation overlay. | Missing or misplaced hooks are visible in viewport and listed in the inspector. |

**Bug-prevention gate:** preview attachments are editor-only until export tests
confirm they do not accidentally become skinned into the character body.

---

## M21 - UX Guardrails for Safe Skeleton Editing

**Goal:** let modders adjust fit without accidentally breaking stock KOTOR
animation binding.

| ID | Task | Acceptance |
|----|------|------------|
| T2101 | Rename UI language from "Build Armature" concepts to native KOTOR language. | Buttons and inspector text explain "Build KOTOR Skeleton" as cloning the named node hierarchy and binding the imported skin mesh. |
| T2102 | Add safe edit modes: Mesh Fit, Guide Edit, Node Pivot Locked. | Users can move imported mesh and guide dots freely, but pivot-changing node edits are explicit and warned. |
| T2103 | Add symmetry controls that actually report their state. | Symmetry on/off is visible, testable, and affects only selected compatible left/right guide pairs. |
| T2104 | Add multi-select bone/guide editing with bounding selection. | User can drag-select multiple guide nodes and move them together for hands/arms/feet alignment. |
| T2105 | Add "revert to base DAG" and "recompute bind only" actions. | Users can recover from bad guide edits without reloading everything. |

**Bug-prevention gate:** all guide edits must be persisted in sidecar state and
must be undoable. No direct destructive mutation of the base snapshot without a
recorded diff.

---

## M22 - Export Readiness and In-Game Confidence

**Goal:** move from "previews in GhostRigger" to "works as a KOTOR mod asset."

| ID | Task | Acceptance |
|----|------|------------|
| T2201 | Add export preflight for native KOTOR character assets. | Blocks missing required hooks, missing skin rows, invalid bone-map sizes, unnormalized weights, and missing supermodel string. |
| T2202 | Add generated appearance/head 2DA helper output. | Export can produce optional patch rows or instructions for placing the model in game. |
| T2203 | Add golden exports for representative cases. | Include headless body, head, full-body disguise/creature-style model, and the continual Bendak FBX -> `n_mandalorian03` external-import fixture documented in `knowledge_base/validation/character_builder_bendak_fixture.md`. |
| T2204 | Add external reload smoke tests. | Exported MDL/MDX reloads through GhostRigger/PyKotor, then runs model info and validation. |
| T2205 | Add modder beta checklist. | Document exact test steps: import, select base, fit, bind, assign animation, preview weapon, export, install to Override, load in game. |

**Bug-prevention gate:** no "launch ready" claim until golden export, reload,
and preview tests pass on clean checkout.

---

## Immediate Next Sprint

Start with M17 because it protects every later phase.

1. T1701 - capture and test native base-model DAG snapshots.
2. T1702 - split viewport display hiding from export DAG preservation.
3. T1703 - revise Build Skeleton around "clone native DAG, attach imported skin".
4. T1705 - show a structural diff after Build Skeleton so users and tests can
   see what changed.

This sprint should not touch animation retargeting or export UI until the native
DAG contract is locked.  That keeps the blast radius small and prevents us from
debugging animation/export symptoms caused by an incorrect skeleton foundation.

---

## Required Test Matrix

Minimum focused tests for every M17-M22 patch:

- `tests/test_character_builder_template_rig.py`
- `tests/test_skeleton_template_picker.py`
- `tests/test_skeleton_template_hud_wiring.py`
- `tests/test_headless_body_workflow.py`
- `tests/test_asset_preview.py`
- relevant writer/loader regression tests when MDL/MDX output changes

Representative MCP ground-truth models:

- `s_male02`
- `s_female02`
- `pmbam`
- `n_mandalorian03`
- `n_darthmalak`
- one head model with `gogglehook`/`maskhook`
- one full-body/disguise-style model with baked head geometry
