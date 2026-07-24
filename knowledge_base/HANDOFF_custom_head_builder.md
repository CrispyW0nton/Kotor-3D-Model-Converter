# Handoff: Ghost Studio Custom Head Builder

You are taking over an active Ghost Studio feature project. Read this entire
document before editing. Preserve all uncommitted work in Ghost Studio and
Kotor-Patch-Manager.

## The single most important instruction

Build a real **Custom Head Builder** product surface, not another Xaria-only
script and not a thin dialog over hidden command-line steps. A manual modder
must be able to import, align, rig, texture, animate, validate, export, package,
and prepare an in-game test for a KOTOR I or KOTOR II modular head entirely
through Ghost Studio's UI.

Do not call the feature complete until a head produced from a clean UI session
passes all structural checks and the user visibly confirms it remains attached
and correctly textured through idle, walking, combat, and conversation in the
retail game. Editor animation is evidence, but it is not retail proof.

## Product outcome

Add **Head Builder** as a separate Ghost Studio module:

- A clearly labeled **Head Builder** button/action is visible from the main
  viewport shell.
- Clicking it opens the dedicated, independently resizable Character Studio
  window directly in Head mode; it must not replace the main viewport or
  become a cramped dock panel.
- It is also reachable from `Tools -> Head Builder...`, command search,
  Getting Started, and the Character Builder mode selector.
- Reopening the command focuses the existing window rather than creating
  duplicate editing sessions.
- The window follows the current Ghost theme, layout, renderer settings,
  shortcut, lifecycle, and payload-ownership conventions.
- The workflow supports both K1 and K2 and never hardcodes Xaria, PFHA04,
  `S_Female03`, node span 564, or any one appearance row.
- A saved project format such as `.ghosthead.json` records source paths,
  hashes, game, donor provenance, alignment, skin-transfer settings, texture
  decisions, optional hair physics, validation results, output resrefs, and
  test-package state.

The user should never need to run Python, edit 2DA files by hand, inspect MDL
hex, type node names into a console, or manually copy files into Override.
Advanced diagnostics may show the underlying values, but every required action
must have a UI control and a plain-language explanation.

### Current integration blockers that must be fixed first

The repository already shows a **Head** mode, but it is not an end-to-end head
builder. Do not mistake the visible mode selector for a working product:

- `qt_character_builder_panel.py::_workflow_module()` currently returns
  `headless_body_workflow` in every mode.
- `_on_load_model_requested()` always presents **Load Body Model**, requires a
  KOTOR base body skeleton, and dispatches `headless_body_workflow.load_body`
  even when Head mode is selected.
- `_on_export_requested()` derives its resref from
  `PartSlot.HEADLESS_BODY` and invokes the body exporter.
- `head_workflow.py` is presently a milestone facade. `rig_head()` validates
  names and can inspect a body headhook, `rig_face()` partitions already
  existing bone names, and its KOTOR/FBX/glTF/OBJ export path returns
  `not_implemented`.
- Existing tests explicitly accept that stub export result. Those tests do not
  prove donor transfer, a binary write/reload, body attachment, textures, or
  retail behavior.

Make Head Builder a separate **workflow module and direct user entry**, but
reuse the established standalone `QtCharacterBuilderWindow` shell. Add a
public `open_mode(CharacterMode.HEAD)` API and route the main viewport, Tools
menu, Getting Started, and command search directly to it. This opens/reuses the
separate Character Studio window already owned by the application while
avoiding a second competing implementation of its viewport, project state,
theme, undo, and lifecycle systems.

## Read these sources first

Ghost Studio:

- `CHANGES.md`, section **Preserve KOTOR modular-head neck_g attachment links**
- `knowledge_base/roadmap/03_character_builder_native_kotor_pipeline.md`
- `knowledge_base/reference/specs/character_builder_spec.md`
- `native/GhostRigger.Core.Tools/Python/src/gui/windows/qt_character_builder_window.py`
- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/window_lifecycle.py`
- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/window_chrome.py`
- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/qt_character_builder_mode_selector.py`
- `native/GhostRigger.Core.Workflow/Python/src/core/characters/character_builder.py`
- `native/GhostRigger.Core.Workflow/Python/src/core/characters/headless_body_workflow.py`
- `native/GhostRigger.Core.Math/Python/src/core/geometry/model_data.py`
- `native/GhostRigger.Core.Resources/Python/src/core/game/kotor_loader.py`
- `src/core/mdl/mdl_writer.py` and its synchronized native payload copies
- `tests/test_mdl_super_root_link.py`
- `tests/test_mdl_animation_override_roundtrip.py`
- `tests/test_external_fit_render_bounds.py`

The successful retail fixture and full failure history:

- `Kotor-Patch-Manager/knowledge_base/xaria_companion_k2.md`
- `Kotor-Patch-Manager/tools/build_k2_xaria_companion.py`
- `Kotor-Patch-Manager/Patches/XariaCompanionK2/build-report.json`

## Proven retail control

Xaria is the first accepted end-to-end custom-head fixture. The user visibly
confirmed **“She finally works!”** in observer session
`20260723-082802-custom-animation-flurry-plcaa`.

Accepted files:

- `p_xariah.mdl`
  `9D5CC62585FE805CF7934E78FCC9E4BAE24D54C2A440BCD133A1366DA2F556B9`
- `p_xariah.mdx`
  `ABF54D1E93CCAA39F51A9B446F13B950FABC0A6A6E4C381BD2668635FCA1E539`
- `p_xariabb.mdl`
  `95E0CB52E52820477B46459240E9BDBC77D1640286C17C5D34C90F89EB181309`
- `p_xariabb.mdx`
  `B546F20A50A783DB5D0ECD5C6D52D3AA4CAF85FDE5ACD78F6C9F94190AFA52E0`

Authoritative K2 donor `PFHA04` was extracted from stock `models.bif`, not
Override:

- MDL SHA-256
  `2CF460A543DB2D8F847F628154FC1BDB7746731DBC30D0F151D9084A4132780F`
- geometry root `PFHA04`
- distinct model-header secondary root `neck_g`
- supermodel `S_Female03`
- 38 physically serialized nodes
- raw geometry `+44` declaration 564
- zero local animation clips
- raw model envelope `(-5,-5,-1)..(5,5,10)`, radius 7

Use Xaria as a regression fixture, not as product logic. A clean UI-built
fixture may use a different output resref and therefore a different full-file
hash, but its donor-derived structural contracts must compare correctly.

## What finally made the head work

All of the following were required. The Head Builder must preserve and validate
them as one coherent workflow.

### 1. Use a modular head and a headless body

A combined full-body model cannot use the normal KOTOR equipment/outfit path.
The head must be a separate model selected through `heads.2da`; the body must
provide the compatible `headhook`. Head Builder owns the head resource but
must preview it against a selected body and expose the body hook as alignment
context.

### 2. Maya/OBJ pivot history is not the runtime attachment contract

OBJ does not carry Maya object-pivot history. The reliable inputs are mesh
coordinates, a selected seam/anchor pair, the donor head hierarchy, and the
body's real `headhook` transform. The UI must let the user click the head's
neck-seam anchor and the matching body vertex, solve their transform, and
preview the result through the actual hook composition.

Never “fix” a floating head by blindly baking the body's approximately
1.45-unit hook translation into head vertices. Once the correct runtime link
exists, that produces a double transform.

### 3. Preserve a real native head DAG

Keep the selected donor's node hierarchy, order, node types, parent/child
relationships, sparse native node-header `+2` identities, dense name indices,
facial controls, and animation inheritance. Replace the donor's rendered skin
payload with custom geometry; do not construct a synthetic face skeleton from
mesh regions.

For the Xaria fixture this means PFHA04's exact 38-node DAG and one direct
root-child skin named `head`.

### 4. Preserve the donor skin contract

KOTOR skin data is not just four weights per vertex. Preserve:

- donor bone-palette order, with no more than 16 slots;
- qBone/tBone inverse-bind rows and their native indexing convention;
- bone-map floats and dense node indices;
- finite normalized weights, at most four influences per vertex;
- required face, jaw, eyelid, brow, eye, mouth, head, neck, and lower-neck
  influence coverage;
- donor node identities and palette targets after export/readback.

For Xaria, barycentric interpolation from PFHA04's actual facial surface gave
nearby face/neck vertices donor-authentic weights. Distant hair/horns were
rigid-bound to `head_g` for the first retail baseline. That rigid baseline must
remain available as a rollback option before enabling physics.

Do not expand the local qBone/tBone or bone-map arrays to match an inherited
node declaration. PFHA04 declares 564 at geometry `+44` but still has 38 local
bind rows.

### 5. Preserve the distinct `neck_g` model-header link

KOTOR modular heads have two different root references:

- absolute file offset `0x34` (`BASE+0x28`) points to the real geometry root;
- absolute file offset `0xB4` (`BASE+0xA8`,
  `offset_to_super_root`) points to the nested `neck_g` node.

The failed writer set both to the geometry root. The head could animate, but it
animated near actor/world origin and moved wildly instead of following the
body. The writer must resolve a unique named attachment target and reject
missing or duplicate targets. The UI should display this as:

`Geometry root: <resref> | Body attachment link: neck_g`

It should not ask ordinary users to type a binary offset.

### 6. Preserve raw geometry `+44`

Geometry-header `BASE+44` is an opaque serialized declaration. Stock PFHA04's
family uses the cumulative supermodel-chain value 564 while containing 38
local nodes. Collapsing Xaria to 38 after restoring the `neck_g` link produced
a Microsoft Visual C++ Runtime termination.

Do not implement a universal “local count” or “cumulative count” rule. Both
representations occur in valid modded character assets. Generic load/write
must preserve an existing raw value exactly. A donor transplant with an
unchanged DAG should copy the donor value. A workflow that changes the local
DAG must explicitly calculate and validate a family-appropriate value or leave
it as a documented advanced decision.

The UI should call this **Inherited node declaration**, default it from the
donor, show local nodes separately, and prevent invalid values smaller than the
local tree.

### 7. Preserve raw model-header bounds separately from preview bounds

Stock PFHA04 declares broad retail bounds:

- `bb_min (-5,-5,-1)` at absolute offsets `0x74..0x7F`;
- `bb_max (5,5,10)` at `0x80..0x8B`;
- radius `7` at `0x8C..0x8F`.

Ghost Studio previously read these correctly and then overwrote them with
tight geometry bounds for viewport framing. The fixed loader stores tight
values in `_gr_render_bounds` / `_gr_render_radius`, marks them prepared, and
restores the raw retail header values for round-trip writing.

Head Builder must show both:

- **Retail model envelope** — donor-preserved, serialized;
- **Preview geometry bounds** — computed, editor-only.

Export validation must compare the raw output header block with the selected
donor contract, not compare against already-mutated preview fields.

### 8. Inherit facial animation instead of baking arbitrary clips

The working head keeps `S_Female03` and zero local head clips. Facial
controllers target the donor DAG through the supermodel chain. Head Builder
must offer preview buttons for:

- neutral idle;
- blink;
- generic talk;
- several dialogue emotions;
- head tracking;
- walking and combat while composited on the selected headless body.

The output must not silently materialize hundreds of local body animations
into the head. A different donor family may legitimately differ; preserve and
explain its native behavior.

### 9. Preserve authored UVs and explicit texture orientation

Xaria's early builds used the right image with incorrectly transformed UVs and
appeared black/fragmented. OBJ/FBX texture orientation, Ghost Studio preview
orientation, MDX UV convention, and bottom-origin TGA data must be treated
explicitly.

The UI needs:

- textured, unlit, lit, UV-checker, and wireframe views;
- UV island view with the source image behind it;
- an explicit V-orientation decision with before/after preview;
- material-to-texture assignment;
- texture resref validation;
- TGA/TPC/TXI export options;
- alpha/environment/bump metadata where applicable;
- a warning when preview and serialized UV orientations differ.

Do not “fix” UVs by modifying the source image and the UV channel at the same
time.

### 10. Separate structural, editor-visual, and retail evidence

Every validation result must carry an honest evidence label:

- **Structural** — binary/readback checks;
- **Editor visual** — Ghost Studio preview;
- **Retail observed** — the user confirmed the behavior in KOTOR;
- **Not tested**.

No green editor preview may be reported as an in-game pass.

## Required manual UI workflow

Use a numbered navigator down the left side of the Head Builder window. The
user can revisit completed steps without losing work.

### Step 1 — Project and game

Controls:

- New/Open/Save Head Project;
- KOTOR I or KOTOR II;
- installed game directory with EXE fingerprint/read-only resource check;
- output project folder;
- new head resref with game length/character validation;
- character/body context: male/female/custom, player/companion;
- stock-only versus effective Override resource view.

Show provenance for every selected game resource: CHITIN/BIF, module, Override,
or project file. Never silently use an Override donor when the user selected
stock.

### Step 2 — Import custom art

Controls:

- Import OBJ or FBX head;
- import one or more textures;
- choose source forward/up axes and units;
- triangulate, weld, recalculate normals, or preserve authored normals;
- material assignment;
- mesh-part list for face, scalp, hair, horns, accessories, and neck;
- source hash and reimport button.

Validation:

- finite vertices/normals/UVs;
- triangles and valid index ranges;
- no empty render parts;
- no degenerate neck seam;
- texture files resolve;
- changes remain undoable.

### Step 3 — Select native donor

Provide a searchable, thumbnail-backed library of compatible heads from the
chosen game. Show:

- donor appearance/heads row and body compatibility;
- supermodel chain;
- local node count and raw `+44`;
- geometry root and attachment link;
- facial control inventory;
- skin palette and bind-row count;
- raw model envelope;
- stock/Override provenance.

Suggest donors by game/body/gender, but let an advanced user choose. A
**Compare donor contracts** panel should explain any mismatch before allowing
the workflow to continue.

### Step 4 — Align neck seam and head hook

Use a split or overlaid textured viewport:

- custom head;
- donor head;
- selected preview body;
- visible body `headhook`;
- donor/custom neck seam.

The user must be able to click:

1. a custom head neck-seam vertex;
2. its matching body seam vertex or ring;
3. optional left/right orientation anchors.

Provide automatic rigid alignment, axis/scale correction, snap, gizmo
fine-tuning, reset, and numerical transform fields. Report seam distance,
anchor round-trip error, scale, and orientation. Preview actual runtime-style
headhook composition, not a simple visual translation.

### Step 5 — Replace donor geometry and skin

Controls:

- donor surface weight transfer;
- nearest-triangle/barycentric distance;
- maximum transfer distance;
- required facial-bone coverage;
- rigid fallback bone, normally `head_g`;
- palette view and four-weight normalization;
- weight heatmap and per-vertex paint/fix tools;
- exclude accessory parts from facial transfer;
- restore donor defaults.

The default safe path is:

1. keep the native DAG;
2. remove/replace only rendered donor skin geometry;
3. retain donor bind arrays and palette order;
4. transfer face/neck weights;
5. rigid-bind distant hair/accessories;
6. prove the rigid baseline before enabling physics.

### Step 6 — UVs, textures, and materials

Provide:

- UV/image overlay;
- V-flip preview and serialized orientation;
- texture-resref renaming;
- TGA/TPC/TXI settings;
- alpha and environment-map preview;
- material diagnostics;
- packaged-file preview.

The serialized MDX UVs must read back and compare with the user's chosen
orientation.

Do not “repair” exported UVs to compensate for the current Pygfx preview.
`mesh_cache.py::_pygfx_uvs` presently applies `1.0 - V` unconditionally.
Xaria's accepted retail model stores the authored OBJ orientation directly, so
that renderer path displays a triangular mosaic even for the user-approved
rigid head. A no-flip runtime probe immediately renders the accepted head
coherently. Head Builder must carry an explicit UV-orientation contract from
import through renderer and serializer, and the renderer must honor it rather
than applying a backend-global flip.

The Xaria regression audit is suitable for a focused test: accepted rigid and
four-dangly candidates match all 1,871 root-space faces one-for-one with
maximum position error `2.61e-8`, UV error `0.0`, and maximum normal-angle
error `3.72e-6` degrees. It is stored at
`Kotor-Patch-Manager/.tmp_xaria/preview/hair_native_candidate/xaria_rigid_vs_four_dangly_uv_audit.json`.

### Step 7 — Attachment and animation preview

Show the head composited on the chosen body. Controls:

- neutral/talk/blink/emotion/head-track animation presets;
- body walk/run/combat/dialogue presets;
- play/pause/scrub/loop;
- textured/wireframe/weights/bones;
- frame head, seam, hook, or whole character;
- slow motion for attachment debugging.

Diagnostics visible beside the viewport:

- geometry root;
- `neck_g` or donor-specific attachment target;
- supermodel;
- local clip count;
- raw node declaration;
- headhook world transform;
- maximum seam separation over the preview clip.

### Step 8 — Optional hair/accessory physics

This is a separate opt-in phase with a one-click **Return to rigid baseline**.
The user selects hair geometry/vertices, roots, pinned regions, and allowed
motion. Expose the supported KOTOR dangly/cloth representation in plain
language and preview it against head motion.

Requirements:

- face, scalp, horns, neck seam, and hair roots remain pinned;
- physics affects only explicitly selected hair/clothing vertices;
- front/face-framing locks are independently selectable and visibly identified
  so a broad “long hair” mask cannot silently omit them;
- no new palette entry silently displaces a required facial bone;
- the original rigid output remains versioned and recoverable;
- validation distinguishes editor simulation from the runtime DLL's universal
  cloth behavior;
- physics can be exported as its own A/B candidate without changing the proven
  head link, donor DAG, UVs, bounds, or facial weights.

For native Odyssey dangly meshes, the UI and writer must implement the actual
retail binary contract rather than treating the last field as an unknown
runtime pointer. The 28-byte header following the K2 mesh header is:

- `+0`: constraint-array MDL offset;
- `+4` and `+8`: matching constraint counts;
- `+12`: displacement;
- `+16`: tightness;
- `+20`: period;
- `+24`: mesh-local rest-position-array MDL offset.

Both pointers use the normal absolute-file-offset-minus-12 convention. There
must be exactly one constraint float and one rest-position `vec3` for every
render vertex, including UV-seam duplicates. The rest array must reproduce the
mesh-local vertex array exactly. In retail semantics an exact constraint value
of zero is the static/pinned sentinel; it is not a freely moving vertex.
Nonzero authored UI values are serialized in the native `0..255` scale.

The Head Builder should:

1. show a paintable simulated mask and a separate pinned/root mask;
2. show connected components, UV seams, partition boundaries, and vertex
   counts before export;
3. preserve the donor's existing dangly node names, parents, sparse identities,
   transforms, and order when suitable nodes are available;
4. split selected geometry when needed so every native dangly node remains
   below the engine-safe vertex ceiling, with partition seams pinned;
5. preserve position, normal, texture, face material, face winding, and UV
   corner data when faces move from the facial skin to dangly nodes;
6. write and raw-reparse both arrays and compare every rest position to the
   written mesh vertices;
7. render a color-coded front/three-quarter/side/back proof showing simulated,
   pinned-transition, and excluded geometry;
8. prevent simultaneous enablement of native dangly motion and the runtime DLL
   solver for the same geometry.

Xaria is a useful regression fixture, not a hardcoded production rule. Her
accepted candidate reuses PFHA04's four dormant `head_g` children
`Plane06`, `Object01`, `Object27`, and `Object15`; two carry the central/back
sections and two carry both face-framing front locks. Her exact reviewed mask
contains 589 faces with connected-component sizes
`404, 85, 81, 8, 7, 4`, while 104 transition/root faces remain rigid. The
candidate uses displacement/tightness/period `.025 / 1 / 1`, exact-zero root
and partition anchors, and conservative nonzero constraints between 220 and
248 on the native 0..255 scale. These values must appear as editable defaults
or a donor-derived preset, never as universal constants.

Until the installed PyKotor dangly reader's extra `+12` constraint seek is
corrected, do not use its decoded constraint values as the export oracle.
Ghost Studio's raw verifier must read the two MDL pointers directly. Likewise,
the current editor `DanglySimulator` reverses the retail zero/nonzero meaning;
fix that preview path before presenting simulated viewport motion as accurate.
Static geometry/UV inspection remains useful, but the retail game is the final
motion authority.

### Step 9 — Binary preflight

Present a checklist with human-readable fixes and an expandable raw view:

- correct K1/K2 function-pointer family;
- unique geometry root;
- unique attachment target;
- root and attachment offsets distinct when donor requires it;
- donor-derived raw `+44`;
- local node count and sparse identities;
- valid parent/child arrays with no cycles;
- name-table indices in range;
- zero or donor-appropriate local head clips;
- MDL/MDX pointers and sizes in range;
- finite vertices, normals, UVs, weights, bounds, and controllers;
- valid faces and batches;
- palette <= 16 and influences <= 4;
- normalized weights;
- qBone/tBone/bone-map sizes remain local and donor-compatible;
- required facial controls receive weights;
- raw retail bounds preserved;
- serialized UV orientation matches the UI choice;
- loader/writer round-trip preserves all critical fields.

Export is blocked on red structural errors. Warnings require explicit user
acknowledgment and are written into the manifest.

### Step 10 — Game records and package

The UI must create or merge, without hardcoded row numbers:

- `heads.2da` row;
- appropriate `appearance.2da` head/body reference;
- optional `portraits.2da` row and portrait texture;
- head MDL/MDX;
- texture/TXI files;
- optional UTC test actor;
- mod-install metadata/TSLPatcher-compatible package if selected.

Use stable labels and re-find rows on rebuild. Show a before/after table and
support uninstall/rollback metadata. Do not overwrite an unrelated modder's
rows.

### Step 11 — Safe retail test

Provide a separate **Prepare Test Install** action:

- refuse while the game or launcher is running;
- never edit the EXE;
- show exact destination files;
- make verified timestamped backups;
- install atomically;
- clear only proven stale module caches;
- record candidate, backup, and installed hashes;
- offer Restore Previous Test;
- launch through the configured patch launcher when required;
- start an observer when available;
- display a manual retail checklist.

Retail checklist:

1. load outside the test module;
2. enter/warp into it;
3. inspect neutral idle and camera rotation;
4. walk/run;
5. enter combat and play several attacks;
6. begin conversation and exercise talk/emotion/head tracking;
7. change party/equipment if applicable;
8. save/load and warp once;
9. confirm texture, seam, attachment, facial movement, and stability;
10. mark each item Pass/Fail and attach screenshots/video.

Only the user can mark **Retail observed: pass**.

## Window layout

Use the established Ghost Studio desktop language:

- top toolbar: New, Open, Save, Undo, Redo, Import, Validate, Export, Prepare
  Test, Restore Test, Help;
- left: numbered workflow navigator and project asset tree;
- center: real Ghost Studio viewport with textured/wireframe/weight/bone
  overlays and animation controls;
- right: context-sensitive properties for import, donor, seam, weights, UVs,
  physics, and export;
- bottom: validation/evidence panel with filterable errors, warnings, hashes,
  and fix buttons;
- status bar: game, donor, output resref, current evidence level, and dirty
  state.

Support keyboard navigation, accessible labels, high-DPI layouts, persistent
window geometry, and nonmodal long-running progress with cancellation. No
critical control may exist only in a tooltip or right-click menu.

## Suggested ownership and integration

Follow current payload ownership; do not create duplicate modules under
multiple component trees.

- Core Workflow: reusable, Qt-free head-project state, donor selection,
  alignment, geometry replacement, weight transfer, physics selection,
  validation orchestration, export plan, and manifest.
- Core Resources: installed-game donor discovery and raw source-preserving
  load contracts.
- Core IO: binary writing and raw output verification.
- Core Math: model/skin data structures and geometry calculations.
- Core Tools: the Head Builder controller, workflow view models, and
  packaging/test orchestration. Reuse `QtCharacterBuilderWindow` as the
  standalone presentation shell and open it directly in Head mode.
- Core GUI Display: only the main-shell action, lifecycle bridge, theme/layout
  registration, command routing, Getting Started route, and icon mapping.

Likely new modules:

- `src/core/characters/head_builder_project.py`
- `src/core/characters/head_builder_service.py`
- `src/core/characters/head_builder_validation.py`
- `src/gui/controllers/head_builder_controller.py`

Route them through the owning native payload directories used by this repo.
Add a `native_kotor_head` route beside the existing Character Builder lifecycle
methods, retain one window instance, and register command aliases such as
`head_builder`, `custom_head`, and `modular_head`. The lifecycle must call the
public `open_mode()` API, never a private `_apply_mode()` implementation detail.
Register the tool in `tool_integration_registry.py` with scene, viewport,
renderer, selection, bone/animation, mesh/material, and texture capabilities.

## Required tests

Unit:

- raw donor root/attachment-link preservation;
- missing/duplicate attachment target rejection;
- raw `+44` preservation and undersized-value rejection;
- raw model envelope versus `_gr_render_bounds` separation;
- sparse native node-identity preservation;
- donor palette/qBone/tBone round-trip;
- four-weight normalization and required facial influence coverage;
- UV orientation round-trip;
- seam transform and headhook composition;
- project save/reopen;
- dynamic 2DA merge/idempotence;
- transactional install/restore and running-game refusal.

UI:

- main viewport Head Builder action exists and opens a separate window;
- Tools menu, command search, selector, and Getting Started routes work;
- every workflow step is reachable without a CLI;
- import/donor/seam/weight/texture/animation/export controls update state;
- validation errors focus the relevant control;
- theme/layout/high-DPI/window persistence;
- closing/reopening does not leak duplicate controllers or windows.

Fixture integration:

- build Xaria or an equivalent separated custom OBJ/texture fixture from a
  clean project through the same public services the UI invokes;
- re-read the exported MDL/MDX and compare all critical donor contracts;
- create a package in a temporary game tree, verify backups, then restore;
- produce textured front/three-quarter/side and talk/combat preview captures.

Manual acceptance:

- use only the UI from New Project through Prepare Test;
- launch the real game;
- require visible attached head, correct texture/UVs, inherited facial/body
  animation, combat stability, conversation stability, and save/warp behavior;
- retain the observer session, manifest, hashes, screenshots/video, and user's
  explicit confirmation.

## Failure history that must remain regression coverage

Do not repeat these invalidated approaches:

- treating a Maya pivot as if OBJ preserved it;
- using a full-body combined model when outfit swapping is required;
- creating a synthetic face/hair skeleton instead of preserving a working
  native head DAG;
- changing donor palette order or inverse-bind row indexing;
- assigning face weights by crude bounding boxes;
- putting preview hair helpers into the facial skin palette before the rigid
  baseline works;
- setting model `offset_to_super_root` to the geometry root;
- deriving raw geometry `+44` solely from local node count;
- expanding local bind arrays to a cumulative node declaration;
- overwriting retail model bounds with preview-computed bounds;
- flipping both UVs and the source image;
- writing native dangly constraints without the per-vertex rest-position array;
- interpreting a zero native dangly constraint as free instead of pinned;
- enabling native dangly motion and the runtime DLL cloth solver on the same
  vertices;
- materializing arbitrary body clips into a modular head;
- staging while the game is running;
- declaring an editor preview to be retail proof.

## Completion gate

The Head Builder is complete only when:

1. the feature is directly clickable from the main viewport shell and opens a
   separate window;
2. a manual user can perform the entire workflow without code or a terminal;
3. all structural and UI tests pass;
4. a clean UI-built custom head exports with donor-correct binary contracts;
5. transactional install and restore work with the game-closed guard;
6. the head visibly passes idle, movement, combat, dialogue, save/load, and
   warp in retail K1 or K2;
7. evidence labels and the user confirmation are recorded honestly.

Preserve Xaria's accepted rigid-hair files as the control until the new Head
Builder reproduces a retail success of its own.
