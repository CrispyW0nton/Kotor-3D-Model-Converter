# Fable 5 Handoff: Map Studio ZModeler/Terrain Revamp

You are Fable 5, continuing GhostRigger Map Studio development for
LordVaderCW. Your mission is to make Map Studio feel intuitive and professional:
real textured rendering first, PolyFrame as a viewport mode, overlays only for
invisible gameplay/export systems, ZModeler-style contextual geometry editing as
the primary modeling workflow, and a terrain builder that feels like Photoshop
painting plus ZBrush sculpting while still exporting working KOTOR 1 and KOTOR 2
modules.

Do not build a beautiful viewport that cannot produce valid `.mod` files. Every
UI and modeling decision must remain engine-facing: MDL/MDX visual geometry,
WOK walkmesh, LYT/VIS room layout, ARE/GIT/IFO/PTH metadata/gameplay resources,
texture/material references, and live KOTOR proof.

## 0. Load These First

Read these before editing code:

1. `AGENTS.md`
2. `.codex/skills/ghostrigger-map-authoring/SKILL.md`
3. `docs/knowledgebase/skills.md`
4. `docs/knowledgebase/mapstudioskill.md`
5. `docs/knowledgebase/terrainsculptskill.md`
6. `docs/knowledgebase/toolbeltskill.md`
7. `docs/knowledgebase/objectseparationskill.md`
8. `docs/knowledgebase/uvtextureskill.md`
9. `docs/knowledgebase/learned/renderingshaderskill.md`
10. `docs/knowledgebase/learned/meshprocessingskill.md`
11. `docs/knowledgebase/learned/qtuiskill.md`
12. `docs/knowledgebase/learned/kotormcp_live_game_proofskill.md`
13. `knowledge_base/package_ownership_model.md`

Then read the ZBrush research artifacts. Corrected source-of-truth path:

`C:/Users/NewAdmin/Documents/GDeveloper/Workspaces/Ghidra/ZBrush/findings/00_zbrush_re_synthesis.md`

Also read:

- `C:/Users/NewAdmin/Documents/GDeveloper/Workspaces/Ghidra/ZBrush/findings/MAP_STUDIO_REVAMP_HANDOFF.md`
- `C:/Users/NewAdmin/Documents/GDeveloper/Workspaces/Ghidra/ZBrush/Saved/Codex/brief_terrain_brush_kernel.md`
- `C:/Users/NewAdmin/Documents/GDeveloper/Workspaces/Ghidra/ZBrush/Saved/Codex/brief_marking_menu.md`
- `C:/Users/NewAdmin/Documents/GDeveloper/Workspaces/Ghidra/ZBrush/Saved/Codex/brief_viewport_modes.md`
- `C:/Users/NewAdmin/Documents/GDeveloper/Workspaces/Ghidra/ZBrush/Saved/Codex/brief_final_marking_menu.md`
- `C:/Users/NewAdmin/Documents/GDeveloper/Workspaces/Ghidra/ZBrush/excerpts/excerpt_zmodeler_complete.txt`
- `C:/Users/NewAdmin/Documents/GDeveloper/Workspaces/Ghidra/ZBrush/excerpts/excerpt_brush.txt`
- `C:/Users/NewAdmin/Documents/GDeveloper/Workspaces/Ghidra/ZBrush/excerpts/excerpt_noise.txt`
- `C:/Users/NewAdmin/Documents/GDeveloper/Workspaces/Ghidra/ZBrush/excerpts/excerpt_polyframe.txt`

Important: use the ZBrush RE as behavioral/design inspiration. Do not copy
proprietary implementation code verbatim into GhostRigger. Re-express the
workflow in GhostRigger-owned code and adapt it to KOTOR constraints.

## 1. Working Test Map Foundation

Use this known-good KOTOR2 map as the proof fixture:

- Handoff zip: `handoff/map_studio_revamp_fable5/tst_light_fullbright_k2.zip`
- Raw module: `handoff/map_studio_revamp_fable5/tst_light.mod`
- Original user-facing zip: `C:/Users/NewAdmin/Downloads/tst_light_fullbright_k2.zip`
- Original user-facing module: `C:/Users/NewAdmin/Downloads/tst_light.mod`
- Warp command: `warp tst_light`
- Zip SHA-256: `dc4686bebf409d9537c73c7e672382736d8067a5fceedde275febc8ceccaf78f`
- Module SHA-256: `a88230bd515dc9e14d2ab55b56d1599160982a6c5eb52cf1a664237eeaa15ab8`

This map loaded in KOTOR2 after lighting repair. It is the minimum-good
developer fixture for Map Studio. Keep it available as a "does the map load and
look usable?" sanity target.

Runtime proof evidence:

- Original bad warp session:
  `Saved/KotorLiveLogs/20260704-092149-tst-light-k2-fullbright-test`
  - Failure: `0xC0000005` access violation in `nvoglv32.dll`
    offset `0x008802ec`
  - Windows events: NVIDIA OpenGL out-of-memory
  - Cause found in module artifact: 12 duplicate zero-radius `colorlight1` MDL
    light nodes with dynamic/shadow fields enabled.
- Fixed-light/inert-light session:
  `Saved/KotorLiveLogs/20260704-095933-tst-light-k2-inert-lights-warp-test`
  - User confirmed map loaded and lighting was fixed.
  - Later close while attempting screenshot was different: `0xE06D7363`,
    `KERNELBASE.dll`, stack including `DiscordHook.dll`. Treat this as
    post-load overlay/runtime triage, not the map-load crash.

Map Studio already has a fullbright MDL light sanitizer. Do not regress it:
fullbright exports must neutralize MDL light-node `dynamic_type`,
`affect_dynamic`, `shadow`, `flare`, and `fading_light`.

## 2. Ghidra/KOTOR Verification Status

KotorMCP crash-log analysis works and was used on the KOTOR2 sessions above.
However, direct Ghidra binary queries are currently timing out:

- `kotor_binary_info(game="k1")` timed out.
- `kotor_binary_info(game="k2")` timed out.
- `kotor_search_symbols(game="k1"|"k2", query="MDL")` timed out.
- `kotor_log_analyze(... annotate_with_ghidra=True)` returned crash summaries
  but Ghidra annotation timed out.

Do not claim new Ghidra symbol/function verification until the backend responds.
When it does, rerun these gates before declaring engine-facing certainty:

1. `kotor_binary_info(k1)` and `kotor_binary_info(k2)`
2. Symbol searches for resource/model/module surfaces:
   `MDL`, `WOK`, `LYT`, `VIS`, `Res`, `Resource`, `Module`
3. If a live crash occurs, run `kotor_log_analyze` with:
   - K1: `/K1/k1_win_gog_swkotor.exe`
   - K2 Steam/Aspyr: `/TSL/k2_win_steam_aspyr_swkotor2.exe`

KOTOR1 and KOTOR2 are separate proof targets. Do not assume a package that
loads in one game is valid in the other.

## 3. Product Direction

Map Studio should feel like this:

- Photoshop-like for painting visible surfaces: brush, size, strength, falloff,
  opacity, layer/mask/material intent.
- ZBrush-like for terrain sculpting: raise/lower, smooth, flatten, pinch, clay,
  trim, noise, terrace, ramp, lazy mouse, stroke spacing.
- ZModeler-like for geometry: hover the thing, press the marking menu, choose
  Action + Target + Modifier.
- KOTOR compiler-like for output: every edit explains what MDL/MDX/WOK/LYT/VIS/
  PTH/GIT/ARE/IFO resource it affects and what proof state is stale.

Keep the UI uncluttered:

- ZModeler-style radial/marking menu is the primary geometry builder.
- Tool belts become compact presets, brush settings, viewport modes, and
  validation/export controls, not giant banks of buttons.
- Visible room/terrain geometry should render as real textured surfaces.
- PolyFrame is a viewport render mode, not a debug overlay.
- Overlays are only for invisible systems: WOK, PTH, triggers, encounters, VIS
  links, collision, selection diagnostics, and validation.

## 4. Ownership Boundaries

Use existing package ownership:

- Scene/core authored state:
  `native/GhostRigger.Core.Scene/Python/src/core/modules/`
- Tools mirror/orchestration:
  `native/GhostRigger.Core.Tools/Python/src/core/modules/`
- Map Studio window/panels:
  `native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py`
  and
  `native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/`
- Rendering contracts/backend work:
  `GhostRigger.Core.Rendering` ownership, or the existing viewport renderer
  owner if the current implementation has not been migrated there yet.
- Hover picking, gizmos, radial interaction helpers:
  GUI Helpers ownership conceptually; if no live package exists, add focused
  modules under the current split GUI/Tools surface and document the owner.
- Validation/export readiness:
  validation/core modules, not window-local logic.

Do not dump algorithms into `module_editor_window.py`. GUI files wire actions,
signals, widgets, theme/layout, and visible state only.

## 5. Implementation Priorities

### Priority 0: Audit Current State

Before code:

- Use `rg` to find current Map Studio action IDs, viewport mode enums, terrain
  brush scaffolds, authored terrain builder, WOK overlay, and existing marking
  menu signals.
- Confirm Scene and Tools copies are byte-identical before mirrored edits.
- Identify which files are canonical versus payload copies.
- Record package owner and tests before editing.

### Priority 1: Truthful Textured Rendering + PolyFrame

Build viewport modes:

1. `Textured`
2. `Textured + PolyFrame`
3. `PolyFrame Only`
4. `Walkmesh View`

Rules:

- Textured mode shows real KOTOR texture references, UV scale, material slots,
  and lighting state.
- PolyFrame mode draws topology/material island information as part of the
  visible render mode.
- Walkmesh/PTH/trigger/VIS/collision are separate overlays, off unless the user
  asks for them or enters that workflow.
- Avoid z-fighting: overlays should use separate passes with depth-write off or
  a deliberate bias.
- Do not hardcode colors. Use theme tokens or renderer debug-view palettes.
- Treat texture decode/upload, material slot identity, UV channel truth, and
  lighting as separate debug points.

Engine-facing acceptance:

- A room from `tst_light.mod` renders with texture and fullbright state visible.
- PolyFrame reveals topology without hiding texture readability.
- Walkmesh view clearly shows walkable/non-walkable WOK faces and does not
  pretend to be final textured geometry.

### Priority 2: Hover Picker + ZModeler Radial Menu

Build the interaction foundation:

- `HoverContext`: component type, object/room ID, vertex/edge/face ID, face
  normal, material/group ID, WOK surface/walkable flag, screen distance, world
  hit point.
- Picker targets: vertex, edge, face, walkmesh face, room/island/material group.
- Screen-space tolerance around 5 px for vertex/edge pickup.
- Visual feedback must be subtle and theme-aware.

Replace flat `QMenu` marking menus with a QPainter radial widget:

- Center: Do Nothing/cancel.
- Outer ring: actions.
- Inner ring: targets/modifiers.
- Modifier labels: Shift/Ctrl/Alt behavior.
- Build menu dynamically from `HoverContext`.

Start with a KOTOR-relevant subset before importing the whole ZModeler
vocabulary:

- Face: Extrude, Move, Inset, Bevel, Delete, Polygroup/Material Region, Mask.
- Edge: Move, Bevel, Split, Bridge, Slide, Crease.
- Vertex: Move, Weld/Stitch, Delete, Split.
- Walkmesh: Toggle Walkable, Set Surface, Split by Slope, Validate.

The action registry belongs in core/tool orchestration data, not hardcoded in
the widget.

### Priority 3: Terrain Brush Kernel

Build one reusable terrain brush engine:

`cursor sample -> stroke/lazy-mouse sampler -> brush stamp -> footprint/falloff
-> affected height/material/walkability cells -> undo stroke -> dirty GPU update`

Required controls:

- radius/draw size
- focal shift/falloff
- z intensity/strength
- opacity for material paint
- alpha footprint
- mask/locked regions
- lazy mouse and spacing
- deterministic noise seed

Required operations:

- Raise
- Lower
- Smooth
- Flatten
- Plateau
- Ramp
- Terrace
- Pinch
- Clay/build-up
- Trim
- Noise
- Erode/relaxation as post-MVP if needed

Performance contract:

- Live stroke update must not rebuild the whole module.
- Dirty regions only during pointer movement.
- Full MDL/WOK rebuild only on stroke commit, validation, or export.
- Brush math must be deterministic and undoable as one stroke entry.

KOTOR contract:

- Terrain live data is not the final export blob.
- KMAP stores compact authored intent, not huge baked terrain data.
- Export compiles terrain to room MDL/MDX and WOK.
- Every terrain edit has a walkmesh consequence: walkable, blocked, ramp,
  transition, water, or explicit visual-only.

### Priority 4: Texture Projection / Material Painting

Build after rendering, picker, and brush kernel are stable.

Adapt SpotLight-like behavior to KOTOR-safe materials:

- Select source texture/material.
- Position/scale/rotate projection in viewport.
- Project onto selected UV-mapped faces or terrain cells.
- Bake to material slots / UV intent, not polypaint.
- Support clone/sample material from face.
- Preserve KOTOR texture references as resref-like names.
- Respect TGA/TPC/TXI behavior and texture-size constraints.

Do not let texture projection discard UVs, lightmap UVs, material slots, or
object identity without explicit warning and undo.

## 6. KOTOR Export Contracts

Every implementation slice must preserve these:

- Resrefs are short KOTOR identifiers; keep module/room/resource names
  export-safe.
- MDL visual geometry and WOK walkmesh are related but independently auditable.
- WOK triangles cannot be degenerate, inverted, disconnected from entry/pathing,
  or silently out of sync with visible floors/ramps/stairs.
- LYT/VIS must reflect room layout and visibility.
- PTH, entry point, transitions, doors, triggers, waypoints, encounters, and
  placeables are gameplay proof gates.
- Fullbright exports must keep ARE lighting and MDL light-node behavior safe.
- K1 and K2 need separate game proof, even if the same KMAP authoring data is
  used.
- Safe save never overwrites source game data without an explicit export/write
  operation.

## 7. Verification Plan

Use targeted checks only unless the user asks for broad sweeps.

For each slice:

1. `python -m py_compile` on touched files.
2. Focused pytest for the owning layer.
3. If canonical Python is packaged into native payloads, regenerate only
   affected package payloads.
4. Visible Debug-app test for UI/viewport/workflow changes.
5. For export-affecting changes, build/install a module and prove in game.

Minimum tests to create/extend:

- Hover picker returns correct vertex/edge/face/walkmesh context.
- Radial menu builds different action trees for face/edge/vertex/walkmesh.
- Action registry preserves stable action IDs and KOTOR guardrails.
- Terrain brush kernel changes only expected samples and dirty regions.
- Terrain commit invalidates MDL/WOK readiness.
- PolyFrame mode shows topology without enabling invisible overlays.
- Texture rendering distinguishes missing texture from valid UVs.
- Exported fullbright package keeps MDL light sanitizer manifest evidence.

Game proof:

- K2: use `tst_light` fixture first.
- K1: stage a K1-specific package and prove separately.
- Use KotorMCP DirectInput hook and live logger.
- Clear stale `currentgame/<module>.mod` before warp.
- Record screenshots/video if the game remains stable.
- If overlays cause post-load closes, disable Discord/Steam overlays and retry,
  but do not misclassify that as map-load failure.

## 8. Recommended First Work Package

Start with a small, shippable slice:

1. Audit current viewport mode and marking menu code.
2. Add `HoverContext` data model and a read-only picker for room mesh face hits.
3. Add subtle hover highlight in textured view.
4. Add radial menu scaffold that opens from the existing marking-menu signal and
   displays face actions from the registry without mutating geometry yet.
5. Add tests for picker context and menu tree generation.

This gives Map Studio the ZModeler interaction spine without risking export
breakage. Then add terrain brush kernel and PolyFrame mode in focused slices.

## 9. What Success Looks Like

The user should be able to:

- Open Map Studio and see a textured KOTOR-like room, not a debug wireframe.
- Switch to Textured + PolyFrame and understand topology density immediately.
- Hover a face/edge/vertex/walkmesh face and get obvious but non-cluttered
  feedback.
- Open a radial menu and see actions that make sense for the hovered thing.
- Sculpt terrain with smooth, undoable brush strokes that update locally.
- Paint/project materials without losing UV/export intent.
- Export a `.mod`, install it, warp into it in KOTOR2 and KOTOR1 proof passes,
  and know exactly which resources were generated.

Build toward that experience deliberately.
