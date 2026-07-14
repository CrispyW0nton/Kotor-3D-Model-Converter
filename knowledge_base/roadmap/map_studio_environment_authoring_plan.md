# Map Studio Environment Authoring Plan

Status: active design and implementation plan (2026-07-11)

Owner: LordVaderCW

Roadmap: T2908 / T3007 / T3103

Supporting evidence:

- `docs/audits/map_studio_lightmap_apply_contract_2026-07-11.md`
- `docs/audits/map_studio_sky_traffic_vanilla_contract_2026-07-11.md`

## Outcome

Map Studio must let a modder author the complete visible environment of a KOTOR
area without confusing editor preview with engine output:

- ARE world lighting, fog, shadow, and ambient settings;
- individually placed room lights with explicit lightmap influence;
- preserved or generated room lightmaps with UV2 and packaged texture assets;
- loaded stock/custom sky geometry rendered with its real textures;
- a static skybox authored from a panorama or HDR source;
- looping sky traffic such as ships, shuttles, and flying creatures;
- validation that distinguishes previewable, export candidate, installed, and
  manually game-tested states.

The game is the final oracle. PyKotor parsing, GhostStudio rendering, and a
successful package readback are necessary gates, not proof that K1/K2 will load
or render the result correctly.

## Vanilla Evidence And Current Truth

| Area | Vanilla evidence | Current GhostStudio state | Required correction |
|---|---|---|---|
| World lighting | ARE stores `SunAmbientColor`, `SunDiffuseColor`, `DynAmbientColor`, fog, shadows, and shadow opacity. | Stock import normalizes and the compiler round-trips sampled K1/K2 values, including nonzero `SunShadows`; legacy `metadata['are']` remains compatible. A Map Studio-only Environment tab applies Standard/Fullbright/Custom values as one undoable ARE/MOD edit without invalidating geometry/pathing. | Complete manual K1/K2 game proof; separately fix stock modules whose module root differs from their ARE/entry resref. |
| Placed lights | Room MDLs and baked lightmaps carry the final visual result; malformed active light nodes can crash K2. | Point/spot/ambient lights have stable IDs and persist enabled, color/intensity/radius, shadow/diffuse/lightmap flags, direction, cone, bake group, and room ownership. They render as viewport nodes and drive the lightmap baker; export still records dynamic-light intent only. | Keep the honest viewport/bake-only status. Make dynamic MDL lights a later opt-in, vanilla-compared feature; do not infer engine support from viewport parity. |
| Lightmaps | K2 `001ebo1` lightmapped meshes use `tex_count=2`, `has_lightmap=1`, one UV2 per exported vertex, MDX stride 40/bitmap `0x27`, and 64x64 RGBA TPCs with lightmap TXI metadata. | A selected imported surface can now be baked and applied transactionally. The workflow keeps xatlas seam vertex remaps, preserves unrelated mesh/WOK/material state, assigns UV2/slot 2, writes a project-owned RGBA TPC with TXI, records hashes/package metadata, and fully undoes the sidecar and surface edit. Generated 64x64 TPC bytes matched installed `001ebo1_lm0/lm1`; a built MOD readback contained the resource and material manifest. | Extend the proven transaction to multi-surface rooms, Bake All/multi-atlas management, and manual K1/K2 visual game proof before changing `Applied lightmap candidate` to game-tested. |
| K1 sky | `tar_m02aa/m02aa_sky` is a roughly 1200-unit, five-surface textured room using `lts_sky0001..0005`; pure sky WOKs may be valid and empty. | A live Debug-app proof of `tar_m02aa` resolved/decoded/cached all five 512x512 textures, verified their visible backdrop-node material bindings, and visibly retained foreground geometry. Sky-on changed 320,896 pixels (`0.866144`, mean delta `4.1923`). Background geometry now draws in a dedicated tier before foreground. | Preserve empty-WOK/no-AABB exceptions only for explicit visual-only backdrops and obtain manual K1 game proof; viewport proof is not engine proof. |
| K2 sky | `231TEL/231telSB` mixes five giant sky panels with ground, water, effects, and 32 walkable WOK faces. `151HAR/151harSB` similarly mixes ordinary room meshes with stars. | Imported surfaces persist a stable backdrop role; mixed-room preview hides only those surfaces, keeps them non-pickable when shown, and export retains playable WOK/pathing. Map Studio can also create a deterministic inward-facing five-panel visual-only skybox with manual texture resrefs and an exact empty WOK. | Complete a named K2 visible/game proof, non-render/controller preservation, and panorama/HDR/dome generation. The authored five-face candidate is not yet game-tested. |
| Sky animation | `231telSB` contains `animloop2`, an emitter, and alpha-controller lightning surfaces. | Reference-model identity, `reattachable`, zero transition, and required Bezier metadata now survive focused conversions, but flattening an editable stock room still does not preserve its complete runtime graph. An audited static-room rebuild waiver is available only for an explicit intentional flatten. | Add a retained non-mesh/controller sidecar or source-MDL patch workflow and preserve full animation/emitter/arbitrary-controller graphs before claiming lossless round-trip. |
| Sky traffic | K1 Taris `m02ab_02l` has a 33.333-second `animloop1`; Dantooine `m14aa_01f` drives a `C_Brith` reference in `animloop2`; K2 `201TEL15` uses three shuttle dummies in a 50-second `animloop1`. Local K2 disassembly shows the engine starting `animloop1/2/3` itself. | KMAP now stores stable traffic/control-point IDs, owning room/model/clip, `animloop#`, closed-loop path, offsets, facing mode, and duration-or-speed timing. Preview shows the resolved model plus cyan path/direction arrows. Readiness/export block enabled authored traffic because no verified room-animation compiler exists. | Preserve the complete vanilla runtime graph and compile authored tracks deterministically into room MDL/MDX `animloop#`; never lower them to fake GIT placeables. Apply static header rules only to static data. |

## Environment Workspace

Add a Map Studio-only `Environment` workspace with four sections. It must not
appear in the main model viewer or Character Studio.

### World

- Lighting profile: Standard, Fullbright Graybox, Custom.
- Sun ambient, sun diffuse, dynamic ambient, shadow opacity, sun shadows.
- Fog enabled, color, near, and far distances, with K1/K2 field differences
  visible in the tooltip and export preview.
- A `Match loaded module` action that restores imported ARE values.
- A compact `Engine fields` disclosure showing the exact ARE fields that will
  change.

Edits update KMAP state, viewport lighting/fog, ARE readiness, undo history,
and proof invalidation together.

### Lights And Lightmaps

Current implemented slice: authored point/spot/ambient lights expose their
room, direction/cone, shadow, diffuse, lightmap, and bake-group properties to
the viewport and baker. The Environment tab can choose one imported room
surface, a final resref and 64/128/256/512/1024 resolution, include ARE ambient
and authored-light shadows, then `Bake & Apply Selected Surface`. Apply is
transactional, collision-safe, packaged, and undoable. Its readiness state is
`Applied lightmap candidate` until a manual game proof exists.

The remaining complete-room workflow is:

- Place Point, Spot, and Ambient light actors in the viewport.
- Move/rotate lights with the normal gizmo; show radius/cone helpers.
- Properties: color, intensity, radius/cone, casts shadows, affects diffuse,
  affects lightmap, room ownership.
- Per-room UV2 validation and generation.
- Bake Preview, Bake Selected Room, Bake All Rooms, Apply Lightmaps, Revert.
- Show each room as `Original preserved`, `Preview only`, `Baked candidate`, or
  `Game tested`.

`Apply Lightmaps` is an explicit transaction. It assigns final resrefs, copies
texture sidecars into the staged resource map, updates the room MDL material
contract, and makes every previous package/game proof stale.

### Sky

Current implemented slice: loaded-module backdrop surfaces retain their source
textures, stay non-pickable, can be toggled independently, and have a live K1
Taris textured-render proof. `Create Five-Face Skybox` generates deterministic
north/east/south/west/top inward panels from manual texture resrefs as a
visual-only, no-shadow backdrop with an empty WOK. It does not yet convert an
image source.

The planned panorama/HDR authoring slice is:

- Loaded-module mode lists sky/backdrop surfaces and their source textures.
- Toggle sky visibility without making backdrop surfaces selectable.
- Extend the existing five-face box with `Dome (experimental)` later.
- Source: equirectangular panorama, HDR, or EXR stored as a project-relative
  reference plus SHA-256; never embed the image blob in KMAP.
- Controls: exposure, white balance, tone mapper, yaw/horizon, resolution,
  face resref prefix, preview seams.
- Output: five sRGB, power-of-two KOTOR texture sidecars and an inward-facing
  static backdrop room. HDR/EXR is an authoring source only; KOTOR receives
  8-bit TGA/TPC assets.

The first supported projection follows the vanilla K2 five-panel convention
(four sides plus top). Exact face orientation and UV mirroring must be verified
with a labeled asymmetrical panorama before a generated sky is called correct.
A TXI cubic environment map is not a skybox substitute.

### Sky Traffic

The viewport interaction may feel like placing an Unreal actor, but the export
contract is a room-model animation.

Current implemented slice: a traffic actor stores a resolved source model,
owning room, `animloop#`/optional model clip, stable editable control points,
loop/closed state, offsets, facing policy, and either loop duration or travel
speed. The viewport renders the source model at the start plus a cyan path and
direction arrows. Readiness and export intentionally block enabled traffic;
there is no authored room-MDL/MDX animation compiler yet.

The remaining authoring/compiler workflow is:

- Choose a resolved model or retained vanilla node group.
- Draw/edit a path spline with a visible start arrow and direction arrows.
- Properties: loop mode, speed or duration, start offset, pause, path-relative
  orientation, banking, scale, animation clip, visibility distance, and owning
  room/backdrop.
- Scrub/play the exact loop in Map Studio.
- Optional linked spatial sound is authored as a real UTS/GIT sound placement,
  not hidden inside the visual path.

KMAP stores stable track IDs, source resource references, room-local path
points, timing/orientation policy, and proof state. Export compiles deterministic
position/orientation controllers into a named room `animloop#`. It must never
emit a GIT creature/placeable unless a separately verified vanilla workflow
uses one.

## Data And Resource Boundaries

- KMAP stays human-readable and reference-based.
- Source panorama/HDR, generated sky faces, and baked lightmaps are project
  sidecars with hashes and revisions.
- Texture bytes, decoded linear images, tone-map policy, UVs, lightmap UV2,
  renderer residency, and final package resources remain separate layers.
- Lightmap assignments key by stable room resref plus surface role/ID, never by
  mesh name alone; vanilla rooms may repeat node names. Any per-corner UV2 seam
  must split/remap the exported vertex stream because the KOTOR writer consumes
  one secondary UV per vertex rather than `face_uvs_lm`.
- Imported stock room source bytes and non-render nodes/controllers remain
  available as preservation data; flattened editable geometry is not a
  substitute for the original animation graph.
- Static room-node `+8=0` and static-controller `unknown0=0xFFFF` are not
  blanket animation rules. Vanilla traffic animation nodes point `+8` at the
  owning animation geometry; position/orientation controllers use observed
  values `16`/`28`, and may retain compressed quaternion or Bezier metadata.
- Backdrop is a surface role. Whole-room `backdrop_only` is legal only when all
  render surfaces are backdrop and the WOK is empty/non-walkable or explicitly
  marked visual-only.
- Playable room AABB/WOK rules remain strict. Empty WOK/no-AABB exceptions are
  scoped to vanilla-compared `backdrop_only` rooms, never applied globally.
- Flattening stock runtime graphs is blocked by default. The versioned
  `authored_static_room_rebuild` waiver requires an explicit reason, records
  source runtime counts, rejects stale/tampered counts, and is valid only when
  the user intentionally replaces that room with static authored geometry.

## Delivery Slices

1. **Preservation baseline — partial**
   - Retain untouched stock MDL/MDX and non-mesh/controller provenance.
   - Add surface-level backdrop roles with stable indices.
   - Add role-aware WOK/AABB/VIS validation against vanilla sky fixtures.
   - Backdrop roles are implemented; complete runtime-graph preservation is not.
2. **World lighting — implemented, game proof pending**
   - Map imported ARE values into authored environment state.
   - Add the World editor and exact K1/K2 ARE round-trip tests.
3. **Applied lightmaps — selected-surface candidate implemented**
   - Connect room UV2, authored lights, baker output, final resrefs, MDL slot 2,
     TPC resources with embedded TXI metadata, manifest, undo/revert, and
     readiness.
   - UV2 seam remap, TPC/TXI, assignment, undo, and MOD readback are complete
     for one selected surface; Bake All/multi-atlas and game proof remain.
4. **Static panorama skybox — manual five-face geometry implemented**
   - Implement linear decode, tone map, equirectangular-to-five-face projection,
     labeled seam tests, generated room model, and package inventory.
   - The generated five-panel room/empty WOK exists; panorama/HDR/EXR decode,
     projection, tone mapping, dome output, and engine proof remain.
5. **Vanilla sky-traffic preservation — partial**
   - Re-export named Taris, Dantooine, and Telos animated rooms without losing
     animation length, animated node names, controller types/keys, emitters, or
     source textures.
   - Reference-node and some controller metadata survive, but the complete
     runtime animation/emitter graph does not.
6. **New sky-traffic authoring — preview implemented, compiler blocked**
   - Add path/arrow/speed UX and deterministic room-animation compilation.
   - Stable actor/path data, arrows, and duration-or-speed UX exist; deterministic
     room-animation compilation remains absent and export blocks honestly.
7. **Game proof — pending for new environment outputs**
   - Manual K1 and K2 warp, visible sky seams/horizon, correct fog/lighting,
     working walkmesh, lightmap appearance, and one looping sky actor.

## Required Fixtures And Gates

- World/lightmap: K2 `001ebo1`, K1 `plcaa`, and `tst_light/r00_test`.
- Pure sky: K1 `m02aa_sky`, K1 `m13aa_99z`, K2 `352narsb`.
- Mixed sky/playable: K2 `231telsb`, K2 `151harsb`.
- Animated traffic: K1 `m02ab_02l`, K1 `m14aa_01f`, and K2 `201TEL15`.

For each writer change:

1. Compare the raw structure with the named vanilla fixture.
2. Read back the staged MOD and verify the exact resource inventory.
3. Render it in the actual GhostStudio Debug application.
4. Install to a test-safe output and have the user perform the manual warp.
5. Record proof before changing readiness to `Game tested`.

## Verification Snapshot (2026-07-11)

- K2 `001ebo1_lm0/lm1`: generated 64x64 uncompressed RGBA TPC/TXI bytes matched
  both installed vanilla fixtures exactly.
- Applied-lightmap workflow: real TPC creation, surface assignment, material/
  UV2 manifest, MOD package readback, collision rejection, and undo sidecar
  deletion passed focused tests.
- Environment/lightmap/sky/traffic/backdrop/visual-proof battery: 72/72 passed.
- Native embedded-Python payload contracts: 19/19 passed with the relevant
  Scene/Tools and GUI Display/Tools mirrors byte-identical.
- K2 `plcaa` vanilla-derived gameplay/package/engine-contract matrix: 19/19.
- K1 Taris Debug-app sky proof: all five 512x512 textures resolved/decoded/
  cached; sky-on changed 320,896 pixels (`0.866144`, mean delta `4.1923`) while
  retaining foreground geometry. Captures are in
  `Saved/VisibleProof/map_studio_sky_environment_2026-07-12_final/`. The proof
  also passed expected material binding, the 1% pixel-change gate, and focus
  safety with zero blockers after the full five-second residency window.
- Debug x64 rebuilt successfully as `GhostStudio` 6.1.0.0 with all 18 payload
  DLLs present. This build and viewport evidence do not replace a game warp.

## Explicit Non-Claims

- Viewport/authored room lights are not compiled as vanilla-compared, proven
  dynamic KOTOR MDL light nodes.
- The selected-surface lightmap is now a structurally validated, packaged KOTOR
  candidate, but it has not been visually inspected after a manual K1/K2 warp.
- The Taris proof establishes GhostStudio textured-sky renderer parity for that
  fixture only; it does not establish KOTOR engine output for an authored sky.
- Only manual-resref five-face skybox geometry exists. Panorama/HDR/EXR
  conversion, automatic face generation, and dome authoring are absent.
- Authored traffic has model/path/direction/timing preview data but no verified
  room-MDL/MDX animation compiler, so enabled traffic remains export-blocked.
- Converted stock room meshes do not preserve the full animated traffic,
  emitter, compressed-orientation, sparse animation-tree, or arbitrary
  controller graph. The static-rebuild waiver explicitly accepts replacement;
  it is not preservation.
- A stock module root that differs from its ARE/entry resref (for example
  `danm13` versus `m13aa`) still blocks a valid untouched full-module rebuild;
  the world-lighting field round-trip does not solve that naming contract.
- No manual KOTOR warp/log session has proved the new authored room-light,
  applied-lightmap, five-face skybox, or sky-traffic behavior. No in-game claim
  is made for those features until that evidence is recorded.
