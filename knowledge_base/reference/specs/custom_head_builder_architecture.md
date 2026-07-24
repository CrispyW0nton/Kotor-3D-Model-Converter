# Ghost Studio Custom Head Builder Architecture

Date: 2026-07-23
Owner: LordVaderCW
Status: Active implementation — full single-head workflow and stock modular
component recipes implemented; current component release still requires
visible Debug-app and user-confirmed retail proof
Roadmap alignment: T1701-T1705, T1801-T1805, T1901-T1905,
T2001-T2005, and T2201-T2205
Capability stage: the production 11-step custom OBJ/FBX route, save/reopen,
UV/material contract, attachment preview, binary readback, package,
transactional test install/restore, and retail-evidence gate are implemented.
The stock route additionally inventories and combines compatible vanilla face,
mouth, eye, eyelid/lash, and hair payloads without changing the carrier DAG.

## 1. Product boundary

Head Builder is a distinct Ghost Studio product surface for creating modular
KOTOR I and KOTOR II heads from either custom OBJ/FBX art or compatible
vanilla component recipes. It reuses the existing
standalone `QtCharacterBuilderWindow` shell, viewport, renderer settings,
theme/layout integration, undo history, and window lifecycle. It does not
create a second character viewport or a docked mini-builder.

The product owns one production workflow with two geometry-source lanes:

1. create or open a head project;
2. import custom art, or choose a vanilla component recipe;
3. select an installed-game native donor;
4. align the custom neck seam in the body's real `headhook` composition;
5. replace only the donor's rendered geometry and transfer skin weights;
6. resolve UV, texture, and material policy;
7. preview attachment and inherited animation;
8. optionally author hair/accessory physics from a recoverable rigid baseline;
9. run blocking binary preflight;
10. merge game records and build a reversible package;
11. prepare, observe, and record a safe retail test.

Completion still requires a head built from a clean UI session and explicitly
accepted by the user in retail KOTOR during idle, movement, combat,
conversation, save/load, and warp. Editor playback is never promoted to retail
proof.

## 2. Evidence baseline

The accepted K2 Xaria fixture is the first retail control. It proves a coherent
set of contracts, not a reusable hardcoded recipe:

- modular head resource paired with a headless body;
- donor-native PFHA04 DAG, order, node types, parentage, sparse node-header
  identities, and dense name indices;
- geometry root separate from the model-header `neck_g` attachment target;
- 38 local nodes while preserving the raw inherited declaration `564`;
- donor `S_Female03` inheritance with zero local head animations;
- one direct-root donor skin named `head`;
- exact 16-slot donor palette, local qBone/tBone/bone-map convention, normalized
  rows, and at most four influences;
- donor-preserved retail model envelope separate from tight preview bounds;
- source-authored UV orientation stored once, without also flipping the image;
- barycentric donor-surface weights for face/neck and a rigid `head_g` fallback
  for distant hair/accessories;
- explicit user-observed retail acceptance.

Xaria's values are regression data. No application service may hardcode
PFHA04, `S_Female03`, `neck_g`, `564`, one gender, one heads/appearance row, or
one skin palette as a universal rule. All such values come from the selected
donor contract.

## 3. Current system findings

The existing Character Studio shell is reusable, but Head mode is not yet a
Head Builder:

- `QtCharacterBuilderWindow._workflow_module()` always returns
  `headless_body_workflow`;
- `_on_load_model_requested()` requires a body skeleton, labels the operation
  `Load Body Model`, and dispatches `load_body`;
- `_on_export_requested()` derives identity from `PartSlot.HEADLESS_BODY`;
- `head_workflow.py` validates existing names and facial groupings but returns
  `not_implemented` for KOTOR, FBX, glTF, and OBJ export;
- current tests explicitly accept those export stubs;
- the main shell opens a two-card Character Builder selector and has no direct
  Head Builder action;
- Getting Started and external command aliases route to generic Character
  Builder;
- `tool_integration_registry.py` describes generic Character Builder but not
  the Head Builder capability surface.

The uncommitted writer/loader work present on 2026-07-23 already provides the
retail-proven low-level prerequisites:

- named `super_root_node_name` read/write preservation;
- missing/duplicate attachment-target rejection;
- raw `geometry_node_count` preservation and undersized-value rejection;
- sparse native node identity preservation;
- raw retail model envelope separated from `_gr_render_bounds`.

Head Builder consumes these contracts. It must not duplicate binary offset
logic in Workflow or GUI code.

## 4. Ownership decision

No new native DLL project is justified. Head Builder is a product spanning
existing canonical owners; creating `GhostRigger.HeadBuilder.*` projects would
add manifest, RCDATA, build, registry, and identity-test cost without an
independent ABI or deployment lifecycle.

| Responsibility | Canonical owner | Planned surface |
|---|---|---|
| Project domain state and multi-step policy | Core Workflow | `src/core/characters/head_builder_project.py`, `head_builder_service.py` |
| Project file repository, dirty/save/open policy | Core Project | JSON repository adapter for `.ghosthead.json` |
| Donor discovery and stock/effective provenance | Core Resources | searchable installed-game head/body catalog |
| OBJ/FBX import and MDL/MDX/TGA/TPC/TXI/2DA/package IO | Core IO | source-preserving readers/writers and transactional outputs |
| Seam, hook, barycentric, skin, and UV math | Core Math | named-space value objects and algorithms |
| Binary/readback/export rules | Core Validation | Head Builder validation report and blocking preflight |
| Workflow commands and user-facing orchestration | Core Tools | Head Builder controller and view models |
| Actions, menus, workflow controls, panels, labels | GUI Display | reused Character Studio window plus main-shell routes |
| Viewport seam pickers, weight brushes, hook gizmos | GUI Helpers | interaction objects only |
| Preview rendering and resource residency | Core Rendering | existing renderer-neutral viewport contracts |

Dependency direction is:

```text
GUI Display -> Core Tools -> Core Workflow
                     |            |
                     v            v
               Resources/IO   Math/Validation
                     \            /
                      -> Rendering
```

Workflow owns no Qt classes and performs no direct filesystem mutation.
Validation owns no dialogs. GUI Display never parses MDL bytes or implements
weight transfer.

### Coupling assessment

The state exchanged between Workflow and Tools has name/type coupling and a
shared application lifecycle. It stays in the existing Core Workflow payload.
The project repository and exporter have separate reasons to change and use
small upstream contracts rather than sharing internal model instances.

| Boundary | Strength | Distance | Volatility | Type | Cost | Decision |
|---|---:|---:|---:|---:|---:|---|
| Workflow state -> Tools controller | 2 | 3 | 2 | data | 3 | Keep explicit typed state |
| Tools -> GUI widgets | 2 | 3 | 4 | data/control | 3 | Controller/view-model boundary |
| Workflow -> Resources donor catalog | 2 | 3 | 3 | data | 4 | Provider port; no resource internals |
| Workflow -> IO exporter | 2 | 3 | 3 | data | 4 | Export-plan/result port |
| Validation -> IO readback | 3 | 3 | 2 | data/algorithm | 4 | Validation owns rules; IO exposes facts |
| New Head Builder DLL project | 1 | 4 | 4 | common environment | 5 | Rejected as accidental lifecycle cost |

## 5. Project contract

The project extension is `.ghosthead.json`. Schema v2 is
`ghostrigger.head_builder_project`.

The implemented Qt-free state is
`src/core/characters/head_builder_project.py`, mirrored in the Core Workflow
payload. It records:

- stable project ID and timestamps;
- K1/K2 target and stock-only/effective-Override view;
- current workflow step plus status/evidence for all 11 steps;
- game and project locations plus output head resref;
- player/companion and body context;
- durable appearance mode plus vanilla carrier/component selections or custom
  mesh provenance;
- custom art, donor, body, texture, and generated-resource provenance;
- import axes, units, topology, source hashes, and reimport policy;
- donor DAG/root/attachment/supermodel/node-span/bounds/skin contracts;
- source, body, and hook-local alignment anchors and transform evidence;
- transfer method, threshold, palette/bind preservation, required coverage,
  excluded parts, and rigid fallback;
- UV orientation and material/texture decisions;
- optional physics settings and rigid-baseline recovery identity;
- validation results with evidence level and artifacts;
- export plan, dynamic game-record merge state, package/install/restore state;
- retail checklist, observer session, candidate/installed/backup hashes;
- warning acknowledgements and forward-compatible unknown metadata.

The state module does not save files. Core Project will own atomic save/open,
dirty state, recent files, schema migration, and path relocation.

### Evidence invariant

Every result is one of:

- `structural`;
- `editor_visual`;
- `retail_observed`;
- `not_tested`.

A `retail_observed/pass` record is invalid unless it includes both:

- `confirmed_by_user=true`;
- a nonempty observer session identifier.

This invariant is enforced in the domain state so neither a GUI color nor an
export success can silently claim retail acceptance.
The Safe Retail Test workflow step cannot be marked complete unless it
references such a passing retail-observed record.

## 6. Workflow service design

`HeadBuilderService` will be the headless facade called by the controller. Its
public commands return typed results and change the project through one command
path:

```text
new_project / open_project / save_project
configure_game
import_custom_art / reimport_custom_art
search_donors / select_donor / compare_donor_contract
inspect_component_source / configure_vanilla_component_recipe
rehydrate_vanilla_component_recipe
select_preview_body
set_seam_anchors / solve_alignment / apply_alignment_delta / reset_alignment
replace_donor_geometry
transfer_donor_surface_weights / edit_weights / restore_donor_defaults
set_uv_orientation / assign_material / configure_texture_output
preview_attachment / preview_animation
create_rigid_baseline / configure_physics / return_to_rigid_baseline
validate_preflight
build_export_plan / export_candidate
preview_2da_merge / build_package
prepare_test_install / restore_previous_test
record_retail_observation
```

Long-running commands expose progress, cancellation, and immutable snapshots to
the Tools controller. The controller never calls private Workflow helpers.

### Infrastructure ports

The Workflow service depends on narrow contracts supplied by owning packages:

- `HeadProjectRepository`;
- `HeadDonorCatalog`;
- `HeadArtImporter`;
- `HeadAlignmentSolver`;
- `HeadSkinTransfer`;
- `HeadValidationRunner`;
- `HeadExportGateway`;
- `HeadPackageBuilder`;
- `HeadTestInstaller`;
- `HeadPreviewGateway`.

These are behavior-oriented ports. They must not mirror every field of
`KotorModel`, Qt widgets, or a filesystem implementation.

## 7. Donor snapshot and transplant contract

Selecting a donor creates an immutable snapshot before custom geometry changes:

- resource provenance and SHA-256;
- game and stock/effective source view;
- geometry root and named model-header attachment target;
- supermodel chain and local animation inventory;
- exact node preorder, types, parent relationships, local transforms, sparse
  identities, dense name indices, and hooks;
- raw inherited node declaration and local node count;
- rendered donor skin identity, direct parent, palette order, dense node
  indices, qBone rows, tBone rows, bone-map layout, and bind-row count;
- raw retail bounds/radius and computed preview bounds;
- texture/material/UV facts;
- heads/appearance/body compatibility facts.

The safe transplant path clones this snapshot, removes or replaces only the
selected rendered donor payload, transfers face/neck weights, rigid-binds
excluded/distant parts, then runs a structural diff. A changed DAG requires an
explicit advanced decision for inherited node declaration and cannot inherit
the donor's “unchanged DAG” proof.

### 7.1 Vanilla component recipe contract

A vanilla recipe is a complete baked head, not a retail-game morph slider.
The user first selects one verified native head as the carrier. The carrier
continues to own every node identity, parent/child edge, local transform,
supermodel, sparse number, palette order, qBone/tBone array, attachment root,
and raw retail bound. Compatible source heads contribute only payload data:

- face skin plus its upper/lower mouth payload;
- left/right eye meshes and their texture, enabling stock eye-color changes;
- left/right eyelid or lash meshes;
- one or more hair, ponytail, or head-tail payloads.

Source vertices, normals, and tangents are rebased from source-node local space
into the matching carrier-node local space. Skin influences are resolved by
bone name and remapped into the carrier palette; a source palette index is
never copied blindly. Source hair may occupy only the carrier's existing hair
slots. Unused carrier hair slots are cleared without removing their nodes.
Stock dangly constraints are topology/order-specific, so mixed hair starts as
the recoverable rigid baseline; optional physics remains Slice 9.

Compatibility is capability-driven:

- K1 and K2 never mix;
- face, mouth, eyes, and eyelids remain within the same verified supermodel
  family;
- face sources expose the carrier's exact facial-control set;
- paired eye and eyelid slots must resolve left and right;
- component meshes must use the expected `head_g` local space;
- modular alien parts stay inside one verified modular alien family.

Installed-game inspection on 2026-07-23 established three alien lanes:

- directly supported modular families: Twi'lek heads such as `twilek_f*` and
  `twilek_m*`;
- extraction/neck-retarget required: full-body Rodian, Duros, Bith,
  Trandoshan, Selkath, and similar resources;
- explicitly unsupported: Ithorian body replacements, which do not fit the
  player headless-body contract.

Each role's MDL/MDX fingerprint, inventory, selection, compatibility report,
target ordinals, and assembled payload hash are saved in project schema v2.
Reopen resolves all source bytes again, rejects drift, rebuilds the candidate,
and requires the identical assembled payload hash before later workflow state
can be restored.

## 8. Named coordinate spaces

All alignment data and APIs name their spaces:

- source object;
- imported object;
- donor object/bind;
- body object/bind;
- headhook local;
- body world/pose;
- head local;
- preview world;
- MDX UV;
- source image.

The default seam solution uses:

1. one custom head seam anchor;
2. one body seam anchor or ring;
3. optional left/right orientation anchors;
4. the fitted source-to-body transform;
5. the inverse body `headhook` bind transform.

The output geometry is stored in runtime headhook-local space. The body hook is
not moved to compensate for custom geometry, and the approximate body-hook
translation is never blindly baked into already attached vertices.

## 9. Validation architecture

Validation produces stable check IDs, severity, evidence level, human-readable
message, fix target, raw facts, and artifacts. Red structural checks block
export. Acknowledged warnings remain in the manifest.

Minimum blocking groups:

- target game function-pointer family;
- unique geometry root and attachment target;
- root/link distinction when required by donor;
- local DAG order, sparse identities, name indices, and acyclic parentage;
- donor-preserved raw inherited node declaration;
- donor-appropriate local animation count and supermodel;
- valid MDL/MDX offsets, sizes, faces, batches, controllers, and finite values;
- exact palette/bind-array convention and donor target identities;
- palette <= 16, influences <= 4, normalized finite nonnegative weights;
- required face/neck influence coverage;
- donor raw retail envelope retained separately from preview bounds;
- serialized UV orientation equals the project decision;
- write/reload critical-field parity;
- package plan does not overwrite unrelated 2DA rows or files.

Validation compares facts exposed by IO and Resources. It does not reimplement
binary readers inside the validator.

## 10. UI and lifecycle integration

The existing `QtCharacterBuilderWindow` gains a public:

```python
open_mode(CharacterMode.HEAD)
```

The method is the only lifecycle entry used outside the window. It applies
mode, selects the appropriate first incomplete Head Builder step, and focuses
the reused window. Callers never invoke `_apply_mode()`.

Main-shell routing adds `native_kotor_head` and aliases `head_builder`,
`custom_head`, and `modular_head`. Direct routes:

- main command-strip **Head Builder** action;
- `Tools -> Head Builder...`;
- command/external tool search;
- Getting Started Head Builder page;
- Character Builder mode selector.

All routes call one lifecycle method that creates at most one window and one
controller. Reopening raises and activates the existing session.

Head mode receives its own workflow adapter. Load, validate, and export dispatch
must not derive from `PartSlot.HEADLESS_BODY`. The body is preview/alignment
context; the modular head resource is the product output.

The final Head Builder layout follows the handoff:

- top project/undo/import/validate/export/test toolbar;
- left 11-step navigator plus project assets;
- center Character Studio viewport and animation controls;
- right context-sensitive properties;
- bottom filterable validation/evidence model;
- status bar with game, donor, output resref, evidence, and dirty state.

All visible work uses theme/layout tokens, keyboard-accessible actions, high-DPI
layouts, and nonmodal cancellable workers. UI implementation requires actual
GhostRigger Debug-app proof in Default/native, Matrix, Droid, Dark, Light, and
Classic.

## 11. Delivery slices

### Slice 0 — project and evidence foundation (implemented)

- versioned Qt-free project contract;
- 11 stable workflow steps;
- resource provenance;
- structural/editor/retail/not-tested evidence;
- explicit user-confirmation invariant;
- native Core Workflow payload integration;
- focused round-trip and boundary tests;
- this architecture specification.

### Slice 1 — direct product entry and mode-correct dispatch

- add `open_mode(CharacterMode.HEAD)`;
- add/reuse `native_kotor_head` lifecycle route;
- add main-shell, Tools, Getting Started, selector, and alias entry points;
- register Head Builder capabilities;
- make `_workflow_module`, load, validate, default resref, and export
  mode-correct;
- replace the export-stub acceptance tests with route/blocked-state tests;
- visible Debug-app proof that every route focuses one separate window.

Implementation status (2026-07-23): the public entry, lifecycle aliases,
main-shell/menu/Getting Started/selector routes, mode-correct workflow
dispatch, and truthful five-stage Head-mode bridge are implemented. A staged
Debug x64 run proved the command-strip route, all five inspector stages, Head
selection, suppression of body-only controls, and one-window reuse. Focused
source contracts cover the remaining entry routes. The exact active-Visual-
Studio launch condition and full six-theme route matrix remain open validation
gates because this machine currently has Build Tools only and no active IDE
session.

### Slice 2 — project repository and donor catalog

- Core Project atomic `.ghosthead.json` repository and migrations;
- K1/K2 install fingerprint and read-only resource checks;
- stock-only/effective-Override resource policy;
- searchable native head/body donor catalog with thumbnails and provenance;
- donor snapshot/diff service;
- save/reopen and stock-provenance tests.

Implementation status (2026-07-23): the headless Slice 2 boundary is
implemented. Core Project now saves strict UTF-8 `.ghosthead.json` documents
through same-directory atomic replacement, optimistic SHA-256 concurrency,
bounded reads, v0-to-v1 migration, duplicate/non-finite JSON rejection,
forward-compatible unknown fields, and portable project-relative paths.
Core Resources exposes deterministic stock-only/effective-Override MDL/MDX
pairing with exact address provenance and hashes, mixed-layer/container
warnings, advanced nonstandard-resref search, and a read-only install gate that
fingerprints the game executable and `chitin.key` before reading one stock head
pair.

Core Workflow now provides `HeadBuilderService`, immutable donor snapshots,
eligibility reports, saved-donor rehydration, and donor-structure comparison.
The snapshot freezes geometry root versus attachment target, supermodel and
local animations, node preorder/parentage/transforms/types, sparse and dense
identities, inherited node declaration, model/node retail bounds, hooks,
palette target identities, qBone/tBone/bone-map layout, source hashes, and
preview bounds. Only the selected direct-root skin named `head` may change its
geometry/material/UV/per-vertex-weight payload; edits to other meshes or any
frozen contract are blocking. An explicit output resref may rename only the
model and geometry root.

Real installed-game base/BIF probes passed for K1 `PMHC01` (33 local nodes,
inherited declaration 366) and K2 `PFHA04` (38/564), each with a 16-slot
palette, local qBone/tBone rows, zero eligibility issues, and zero self-diff.
The current installed K2 edition's base-file SHA-256 differs from the earlier
handoff fixture while retaining the same critical structural contract; both
byte identity and structural identity are therefore recorded rather than
assuming all retail editions are byte-identical.

Donor thumbnails and project/catalog widgets remain presentation work for the
full Head Builder workspace. This slice deliberately exposes typed headless
commands first so GUI Display does not own persistence, resource resolution,
or MDL validation.

### Slice 3 — import and seam/hook alignment

- OBJ/FBX import records axes, units, hashes, normals, UVs, and topology facts;
- source seam and body seam picking helpers;
- rigid solve with optional orientation anchors and manual delta;
- actual runtime-style headhook composition;
- targeted seam round-trip math tests and visible viewport proof.

Implementation status (2026-07-23): the headless import/alignment boundary is
implemented. Core IO now provides a deterministic `HeadArtDocument` for OBJ
and Blender-backed FBX art. It records source byte identity, format, explicit
axis conversion, unit scale, V policy, stable part and imported-vertex
identity basis, authored/generated UV and normal state, source control-point
indices where available, bounds, materials, topology facts, and compact
warnings. Runtime vertex/face/channel arrays remain in memory; the project
projection contains only paths, hashes, settings, counts, bounds, and audit
facts. Reopened projects reimport only when both the source SHA-256 and decoded
structural fingerprint still match.

The import gate blocks non-finite channels, invalid face indices, degenerate
faces, non-manifold edges, and misaligned vertex channels. Open boundaries are
warnings because a modular head intentionally has a neck opening; the user
must identify that intended seam later. Missing authored UVs/normals,
inconsistent winding, duplicate faces, isolated vertices, and branched
boundaries remain visible warnings rather than being silently repaired.
Rejected art cannot overwrite a previously accepted import.

Core Math now solves the explicit transform chain
`head_art_imported_object -> body_bind -> headhook_local`. One anchor produces
an honest translation-only result, two anchors use the minimum direction
rotation and report underdetermined roll, and three or more non-collinear
anchors use a weighted Kabsch rigid/similarity solve. Reflection is corrected,
singular hook transforms and degenerate anchor sets are rejected, and every
result records proper-rotation determinant, anchor rank, pair errors, RMS/max
error, all three affine matrices, warnings, and a stable transform hash.

Core Workflow exposes import/rehydrate/alignment commands through the existing
`HeadBuilderService`. It requires an accepted donor, accepted runtime art, a
valid body ResRef, the exact terminal node name `headhook`, and an explicit
RMS tolerance before advancing to geometry replacement. The saved body
context, anchors, matrices, and structural evidence remain blob-free.

An installed K2 proof imported the eight-vertex/ten-face open-neck OBJ fixture,
accepted its single four-edge boundary, selected base/BIF `PFHA04`, and loaded
stock base `PFBAM`. Its exact native hook chain was
`PFBAM/cutscenedummy/rootdummy/torso_g/torsoUpr_g/headhook`, with bind
translation approximately `(-0.00007749, 0.000000066, 1.44925393)`. Three
anchors solved to a proper rotation (`det ~= 1`) with RMS error
`2.24e-16`; the composed imported-to-headhook matrix was identity within
floating-point tolerance. The 88,459-byte `.ghosthead.json` saved portable
art/output paths, contained no raw vertex or face arrays, reopened cleanly in
a fresh service, rehydrated matching art and donor structural fingerprints,
and advanced to `replace_geometry_and_skin` with no blocked steps.

Interactive seam/ring picking, manual alignment delta controls, a real
Blender-FBX fixture run, viewport composition, and actual Debug-app/six-theme
proof remain open presentation gates for this slice. The current evidence is
structural and does not claim visible or retail acceptance.

### Slice 4 — donor-preserving geometry and skin transplant

- exact donor DAG clone;
- one selected rendered-skin replacement;
- nearest-triangle/barycentric transfer;
- rigid fallback and part exclusions;
- weight heatmap/painting;
- donor palette and inverse-bind preservation;
- Xaria-equivalent service fixture readback.

Implementation status (2026-07-23): the headless geometry/skin boundary is
implemented. Core Math owns exact nearest-donor-triangle sampling with AABB
lower-bound pruning, closest-point barycentrics, deterministic row
interpolation, four-influence normalization, explicit rigid and bounded
distance-fallback modes, and an attachment-bone floor for the selected neck
ring. Every row remains within the immutable donor palette; zero rows,
non-finite weights, palette overflow, degenerate donor triangles, and
out-of-threshold vertices block acceptance.

Core Workflow clones the pristine donor and permits one mutable direct-root
skin named `head`. It replaces only that node's rendered vertices, faces,
normals, UVs, and per-vertex skin rows. DAG order, node names/types/parents,
local transforms, sparse and dense identities, hooks, supermodel declaration,
local animation inventory, inherited node count, bone palette and target
indices, qBone/tBone/bone-map arrays, and raw retail model/node bounds remain
byte-independent structural invariants. Tight custom-art bounds are stored
only as preview metadata. Part policy is explicit
`surface_transfer`/`rigid_head_g`/`exclude`; neck selections require at least
three stable boundary-vertex identities.

The project stores transfer settings, sparse manual edits by stable vertex ID
and donor bone name, compact reports, and hashes—never geometry or weight
arrays. Manual edits are deterministically reapplied over the transfer
baseline, normalized to four influences, limited to the frozen palette, and
rejected if they reduce a selected neck vertex below its attachment-bone
floor. Reopening reimports the source art, rehydrates the exact stock donor and
alignment, rebuilds the payload, reapplies edits, and compares geometry,
weight-row, and combined payload hashes before allowing the workflow to
continue.

The installed K2 proof used the stock base/BIF `PFHA04` donor: one native
`head` skin at node ordinal 37 with 563 vertices, 849 faces, and its exact
16-slot palette. The eight-vertex/ten-face custom fixture transferred all
eight vertices by donor-surface barycentrics with no distance fallback, no
zero rows, at most two influences, and four `neck_g` floor adjustments. One
manual `head_g`/`f_jaw_g` edit survived a fresh service reopen. The reopened
candidate matched its geometry, weight, and combined payload hashes and
reported no blocking donor-contract differences; only the selected skin
payload and preview bounds appeared in the allowed diff. Its 100,648-byte
`.ghosthead.json` remained free of raw vertex/face arrays and advanced to
`uv_textures_and_materials`.

Interactive seam selection, weight heatmap/painting, undoable viewport tools,
and actual Debug-app/six-theme proof remain open presentation gates. This
slice is structural evidence and does not claim visible or retail acceptance.

### Slice 5 — UV, material, and texture workflow

- UV/image overlay and explicit serialized V orientation;
- material-to-texture mapping;
- TGA/TPC/TXI options and metadata;
- preview/serialized orientation mismatch gate;
- packaged-file preview and UV round-trip tests.

Implementation status (2026-07-23): the headless UV/material boundary is
implemented. Core Math owns an explicit three-stage UV contract: source-import
V handling, serialized MDX orientation, and preview orientation. It audits
finite/channel-complete UVs, degenerate faces, range, winding, and overlap,
and blocks preview/serialized disagreement. Core IO fingerprints and decodes
TGA/TPC sources, preserves TXI provenance, validates dimensions/mips/alpha,
and produces deterministic TGA/TPC plus sidecar/embedded-TXI package policy
with KOTOR-safe ResRefs. The MDX writer now accepts an explicit serialized UV
transform independent of renderer preview state.

Core Workflow assigns the texture only to the donor's mutable rendered head
skin and rechecks the complete immutable donor contract. The project stores
source/output policy, hashes, UV audit, and compact material facts rather than
image bytes or UV arrays. Reopening redecodes the source texture, rebuilds the
same policy, and requires matching decoded-RGBA, serialized-UV, and material
payload hashes.

The installed K2 proof applied a 64x64 TGA/TXI checker as `P_CDH01` to the
PFHA04 transplant. Preview and serialized UV hashes matched; binary MDL/MDX
write/readback returned `p_cdh01` and all eight UVs with maximum error
`2.384e-8`. The donor diff had no blocking changes. The saved project was
108,941 bytes, contained no raw mesh/image arrays, and reopened with identical
material hashes. Its intentional mirrored UVs produce warning-level winding
and overlap diagnostics, so unique-surface baking remains gated. Interactive
UV editing and actual six-theme viewport proof remain presentation work.

### Slice 6 — attachment and inherited-animation preview

- head/body composition on a selected compatible body;
- facial and body animation presets;
- seam separation sampling through a clip;
- head/root/link/supermodel/node-span diagnostics;
- no silent materialization of local body clips into modular heads.

Implementation status (2026-07-23): the renderer-neutral attachment and
animation contract is implemented. Core Workflow deep-copies body and head
for preview, requires exactly one native `headhook`, parents only the
disposable head root beneath it, and leaves both source models untouched. It
requires matching non-null body/head supermodels, resolves the full chain with
cycle and missing-resource gates, applies local-first animation override
semantics, and identifies effective clips that target facial nodes actually
owned by the head. The report records hook path/world position, source versus
preview parent, local animation inventories, selected presets, chain members,
and a stable contract hash. No inherited or body clip is copied into the head.

Body and every supermodel MDL/MDX are stock-view fingerprinted in the project.
The durable projection keeps animation names and detailed rows for selected
presets but omits the repeated target list for every clip. Reopening resolves
the same resources and must reproduce both fingerprints and the complete
in-memory contract hash. Optional hair/accessory physics is explicitly
recorded as not requested and the workflow advances directly to binary
preflight.

The installed K2 proof combined transplanted PFHA04 with stock PFBAM at
`PFBAM/cutscenedummy/rootdummy/torso_g/torsoUpr_g/headhook`. Both reference
`S_Female03`; the resolved chain continues through `S_Female02`,
`S_Female01`, `S_Male02`, and `S_Male01`. It exposed 473 effective clips,
411 with facial targets; `tlknorm`, `talk`, `listen`, and `walk` resolved as
inherited presets. Source and preview head local-animation inventories both
remained empty, the preview parent was exactly `headhook`, and the export
candidate retained zero blocking donor differences. The compact 178,742-byte
project contains no raw vertex or texture arrays and reproduced the same
attachment contract after a fresh service reopen. This is structural evidence:
visible animation playback, seam sampling through a clip, Debug-app/six-theme
proof, and retail proof are still required.

### Slice 7 — binary preflight, export, game records, and package

- Core Validation preflight;
- KOTOR MDL/MDX writer gateway and readback;
- idempotent heads/appearance/portraits merge by stable labels;
- package preview, uninstall metadata, rollback records;
- temporary-tree transaction tests.

### Slice 8 — safe test install and retail evidence

- running-game/launcher refusal;
- atomic install, timestamped verified backups, constrained cache clearing;
- restore previous test;
- launcher/observer integration;
- manual retail checklist and explicit user acceptance.

### Slice 9 — opt-in hair/accessory physics

- immutable rigid baseline;
- selected/pinned vertices and supported KOTOR dangly/cloth representation;
- A/B candidate identity;
- return-to-rigid action;
- no changes to head link, donor DAG, UV, bounds, or facial skin contracts;
- separate editor and retail evidence.

### Slice 10 — stock modular component customization (implemented headless/UI)

- classify vanilla face, mouth, eyes, eyelids/lashes, and hair payloads;
- assign a highlighted installed-game head to any component slot;
- preserve carrier DAG/bind identities and rebase source mesh channels;
- persist and deterministically rehydrate schema-v2 component recipes;
- hash every certified component payload through MDL/MDX write/reload;
- support verified modular alien families while routing full-body aliens to a
  future extraction lane and blocking Ithorians.

## 12. Focused verification strategy

Each slice uses the cheapest authoritative gate first:

- pure project, math, and service tests without Qt;
- MCP/loader comparisons when model/texture/skin facts change;
- targeted MDL/MDX write/reload and raw-header tests;
- temporary-game-tree transaction tests for packaging;
- source-contract tests for entry routing and payload ownership;
- actual Debug-app testing for every visible workflow change;
- user-confirmed retail testing only after structural and editor gates pass.

No full 6,078-model scan or broad `pytest tests/` run is part of the default
workflow.

## 13. Current unclaimed capability

The current system does not claim:

- arbitrary cross-supermodel face mixing;
- direct modular use of full-body Rodian, Duros, Bith, Trandoshan, Selkath, or
  similar resources before a dedicated extraction/neck-retarget lane exists;
- Ithorian player-head compatibility;
- in-game runtime morph sliders—the KOTOR engine consumes baked head
  resources, so each saved recipe produces a complete head;
- batch allocation of several saved recipes into one appearance package;
- copied stock dangly-hair physics without explicit re-authoring from the rigid
  baseline;
- user-confirmed retail acceptance of a newly mixed component candidate.

The component feature is complete only after the actual Debug workbench shows
a real installed-game combination in all six themes and the user confirms the
result in retail KOTOR.
