# T2909 — Full KOTOR I/II Vanilla Geometry Reconstruction in the Pascal Builder

**Roadmap task:** T2909
**Date:** 2026-07-23
**Owner:** ShaolinGhost
**Status:** Active; this is the canonical completion contract for the full geometry-first K1/K2 rollout. Korriban tomb/cave construction and mixed vanilla-room assembly remain the current graduation slice.

## Goal Statement

> Build a complete Pascal-style construction system that recreates the actual
> architectural and environmental geometry language of every visually distinct
> module-area style in KOTOR I and KOTOR II. Generated rooms must be editable
> parametric reconstructions derived from measured vanilla meshes: beveled,
> layered, contoured, trimmed, and detailed to match the source area's
> silhouette, proportions, openings, structural cadence, exterior envelope, or
> organic terrain forms. Flat boxes, simple extrusions, and texture-swapped
> graybox geometry are not finished build kits.
>
> Materials must retain the source texture scale, orientation, and surface
> cadence as geometry is drawn, resized, turned, or joined. No completed style
> may exhibit stretched textures, distorted corners, mismatched UV scale, or
> one texture tile normalized across an arbitrary room footprint.
>
> Selecting a style must automatically populate its Content Browser with
> categorized click-and-drag environmental props, terrain and dressing pieces,
> and compatible vanilla module rooms. Procedural rooms and vanilla rooms must
> remain separate editable room objects while magnet-snapping through measured
> portals, creating clean openings and sealed geometry, and installing the
> authentic working door and frame used by that area style.
>
> Walkmesh and module connectivity are part of construction, not a later repair
> step. Per-room WOK, reciprocal room transitions, PTH, LYT, VIS, and connection
> validation must regenerate as rooms are drawn, resized, moved, duplicated, or
> connected. The result must be immediately selectable, traversable in the
> viewport and PIE, exportable as a valid KOTOR module, and verifiable after
> readback and a retail-game warp.
>
> This goal is complete only when every unique KOTOR I and KOTOR II module-area
> style has passed the same measured-geometry, beveled-detail, undistorted-UV,
> style-browser, drag-placement, seamless-snap, authentic-door, live-walkmesh,
> export/readback, and manual user-experience proof gates. A few demonstration
> kits do not complete the goal.

This contract supersedes the earlier starter-slice goal that focused primarily
on Endar Spire and Taris Apartments. Those kits are reference implementations,
not the finish line. The deliverable is the finished library for all visually
distinct module-area families in both games, with no style marked complete on
the strength of textures or screenshots alone.

“Learned” or “trained” in this roadmap means deterministic analysis of
serialized geometry, topology, materials, UVs, dimensions, repeated structures,
and room connections from the user's installed games. It does not mean an
opaque model inventing geometry at export time, and it never permits bundling
or redistributing the user's vanilla game assets.

Each kit must be trained and derived from serialized, measured evidence from
the user's installed vanilla modules. A style is not a texture palette applied
to flat or simply extruded geometry: it must generate beveled, layered,
silhouette-accurate walls, corners, floors, ceilings, arches, openings,
structural rhythms, exterior envelopes, and organic terrain forms
characteristic of that area. Work proceeds through all distinct KOTOR I styles
before the KOTOR II rollout, and every style must graduate through the same
ordered workflow:

1. **Matching procedural architecture:** serialize and measure the area's
   vanilla room/exterior meshes, then make Pascal-style drawing reproduce their
   characteristic contour, bevels, stepped profiles, proportions, structural
   rhythm, openings, materials, and terrain language. Flat or palette-swapped
   geometry does not satisfy this gate.
2. **Undistorted stock materials:** recover per-material texel density and UV
   orientation from the source meshes. Generated surfaces use world-scale,
   repeating UVs and validated seams; texture stretching, one-tile-across-room
   mapping, and visibly distorted corners are blockers.
3. **Style-owned vanilla room browser:** when the author selects that style,
   the Content Browser automatically shows every compatible room tile and
   environmental prop from that module family, categorized by room topology,
   architectural role, foliage, rock/terrain role, or dressing purpose and
   ready for click-drag placement.
4. **Seamless LEGO assembly:** procedural rooms and vanilla tiles magnet-snap on
   every valid doorway/edge, cut the matching opening, place the authentic
   area-specific working door and frame where appropriate, regenerate room WOK
   continuously as rooms are drawn or moved, compile reciprocal WOK/PTH
   transitions, refresh LYT/VIS, and reject cracked, clipped, obstructed, or
   mismatched joins before commit/export. Every connected section remains a
   separate room rather than collapsing the map into one monolithic mesh.

## Definition of Complete

The required deliverable is the complete K1/K2 style library, not a collection
of demonstrations. A style is not marked complete unless all of these are
present and visibly proven:

- a measured procedural architecture recipe with bevels, relief, trims,
  structural cadence, openings, and exterior/organic forms appropriate to that
  location;
- world-scale UV and texel-density rules that remain stable when rooms are
  resized, joined, or turned around corners;
- a style-filtered Content Browser containing draggable environmental props,
  terrain pieces, dressing assets, and compatible vanilla module rooms;
- portal magnets and authentic working doors/frames for that area;
- live per-room WOK generation and reciprocal room transitions that update
  while the map is built; and
- visible Map Studio and PIE evidence that the authored and vanilla geometry
  join cleanly, remain selectable/editable, export successfully, and can be
  traversed without collision or walkmesh breaks.

Flat walls, generic boxes, texture-only resemblance, stretched UVs, open seams,
clipping joins, manually aligned stock rooms, generic doors, monolithic
walkmeshes, or navigation that requires a separate repair pass are explicit
failure conditions.

The K1 sequence must cover each unique Endar Spire and Taris family first,
including Upper City, Lower City, Undercity, apartments, sewers, and bases;
then Dantooine's Jedi Enclave, estates such as Sandral, courtyards, fields,
caves, and ruins; Tatooine; Kashyyyk and the terrain-wall/vegetation-heavy
Shadowlands; Manaan; Korriban; Leviathan; Yavin; Ebon Hawk; Unknown World; and
Star Forge. A style is not complete until its detailed procedural kit,
automatically filtered vanilla room/prop catalog, area-authentic working doors,
live walkmesh generation, seamless mixed-room assembly, export/readback, and
manual user-experience proof all pass. KOTOR II follows only after that K1
coverage gate is complete, using the identical evidence and acceptance process.

## Outcome

Map Studio should let a level designer choose a recognizable KOTOR location
style, draw a floor plan with the Pascal workflow, and receive editable,
snapping architecture that carries the proportions, silhouette language,
surface rhythm, and installed-game materials of that location. The same
evidence pipeline will supply terrain pieces such as bluffs, canyon walls,
ruins, roots, foliage, and distant vistas.

The production builder is deterministic. It does not invent opaque meshes at
export time and it does not redistribute BioWare or Obsidian assets. It learns
repeatable measurements and patterns from the user's installed games, records
those observations in a local text corpus, and compiles editable parametric
recipes to Ghost Studio room geometry, MDL/MDX, WOK, LYT/VIS, and MOD output.

## Evidence-to-Kit Workflow

1. Discover every room model referenced by a module's LYT and retain game,
   module, room, model-node, material, and transform provenance.
2. Serialize rendered surfaces as readable OBJ-compatible text: `v`, `vt`,
   `vn`, `usemtl`, and `f`, plus semantic labels, bounds, confidence, and
   source identifiers. This follows the useful representation principle from
   LLaMA-Mesh while keeping KOTOR conversion deterministic.
3. Classify surfaces as floor, wall, ceiling/roof, trim, structural rib,
   light, door surround, window surround, terrain, foliage, prop, or review.
   Orientation, dimensions, topology, names, materials, lightmaps, and repeated
   placement patterns all contribute evidence.
4. Detect modular measurements: wall-bay cadence, floor height, ceiling
   profile, corner treatment, door/window magnets, trim bands, column spacing,
   material families, and exterior terrain seams.
5. Compile a reusable style recipe that adapts those observations to arbitrary
   footprints, openings, levels, and exterior envelopes. Generated pieces stay
   individually selectable and preserve semantic roles.
6. Verify the style through the real Map Studio workflow: choose the style,
   draw and revise a plan, place openings, snap pieces, select/delete/move the
   results, export, reload MDL/MDX/WOK/MOD, and manually warp into the module.

High-confidence classification is automatic. Low-confidence or conflicting
surfaces are written to a small review queue; the user does not need to
pre-split whole modules into walls, floors, and ceilings. A manually isolated
reference is useful only when a genuinely ambiguous art asset needs a design
decision.

## Implemented Starter Slice

| Style | Evidence rooms | Compiled vocabulary | Status |
|---|---|---|---|
| Endar Spire corridor | `m01aa_01a`, `m01aa_06a`, `m01aa_08a`, `m01ab_09a` | swept structural cross-section with side deck, sloped lower bulkhead, light belt, canted upper wall, shoulder/cove, recessed ceiling, and contour-following ribs | Implemented; `m01aa_08c` is style-browser attachable, cuts its measured doorway, compiles a reciprocal WOK seam, and passed one-player staged PIE traversal |
| Endar Spire quarters/junctions | same corpus, expanded by room archetype | vertical cabin bays, bed/console alcoves, central dividers, circular doorway frames, junction caps | Pending; separate archetypes must not inherit the corridor tunnel blindly |
| Taris Apartments | `m02aa_01a`, `m02aa_03a`, `m02aa_06a`, `m02ad_01a`, `m02ad_06a` | swept 2.55 m apartment shell with measured service/light/panel stations, inset shoulder/cove, recessed ceiling, opening-aware structural ribs, apartment recesses, and utility rails | Implemented; `m02aa_01a` is style-browser attachable with its measured 4.5 m threshold and authentic `dor_lts02` door, and passed one-player staged PIE traversal into the stock room |
| Kashyyyk Shadowlands | `m24aa_02a`, `m24aa_09a`, `m24aa_13a`, `m24aa_16a`, `m25aa_01a`, `m25aa_04a`, `m25aa_11a`, `m25aa_12a` | open-air irregular floor plans with eroded earth banks, interwoven root walls, ancient-root crowns/buttresses, narrow hanging root vines, organic passage lintels, and Upper/Lower vanilla foliage/terrain shelves | Implemented in code; 8-room/115-surface/14,530-triangle local corpus and focused geometry/WOK/export/browser tests pass. Staged-app drag/build visual proof remains the graduation gate. |
| K1 Korriban tomb corridor | `m37aa_02`, `m37aa_03`, `m37aa_11`, `m38aa_07`, `m38aa_08`, `m38ab_01`, `m38ab_07`, `m39aa_02`, `m39aa_18` | measured 3.90 m carved shell, stepped lower/upper masonry, closed beveled relief courses, 1.50 m structural cadence, recessed ceiling, and a deep three-tier `DOR_LKO04` stone surround | Partial; the style browser groups the installed `m37aa`, `m38aa`, `m38ab`, and `m39aa` room families across straight, bend, T, four-way, cross, dead-end, and chamber topologies. A generated room, retail `m39aa_16` hub, and retail `m38aa_05` bend remain three separate rooms, compile two reciprocal WOK portals, place two authentic tomb doors, and passed staged PIE traversal across the retail-to-retail threshold. The fresh 17-resource MOD structural readback proves all three MDL/MDX/WOK triples, ARE/GIT/IFO/PTH/LYT/VIS, two working joins, five unique LYT door hooks, bundled non-static appearance-40 working/sealed Korriban UTDs, correct `Mod_Entry_Area`, 98 walkable faces, and exact preservation of all 70 imported diffuse-UV surfaces with zero texture mismatches. The three otherwise-unused stock portals are now explicitly marked and covered by locked area-style doors instead of being silently left open. Full topology-by-topology visual acceptance, prop coverage, and retail warp proof are still required. |
| K1 Korriban reliquary chamber | `m37aa_12`, `m37aa_16`, `m38aa_08`, `m38aa_11`, `m39aa_07` | separate measured 10.35 m chamber contour with 3 m relief cadence, tiled world-scale UVs, corbel courses, vault shoulders, beveled ledges, massive two-stage corner buttresses/capitals, and a closed reliquary vault | Implemented as a distinct Room shape instead of stretching the corridor shell. Focused geometry proof records 333 helper meshes, a maximum geometry height of exactly 10.35 m, nondegenerate triangles, tiled UV spans, and live WOK output. The staged application loaded the proof KMAP, selected the chamber from the real Builder UI, and rendered a playable interior in PIE with two walkable WOK faces and 684 camera-collision triangles. Compatible stock-room topology coverage, full prop dressing, snapping proof, and retail warp remain part of the Korriban graduation gate. |
| K1 Korriban cross-vault junction | `m38aa_06`, `m38aa_08`, `m39aa_16` | separate 10.24 m junction contour with 4.5 m measured stations, closed cross-vault crown/cap, cross piers, vault capitals, relief courses, and a closed junction ceiling | Implemented and visibly selected in the staged Builder. PIE rendered the generated interior with 254 helper meshes, 526 camera-collision triangles, two live walkable WOK faces, and a 6 x 5 tiled floor UV span. Stock junction attachment and retail warp remain part of the Korriban graduation gate. |
| K1 Korriban burial alcove | `m37aa_12`, `m38aa_11`, `m39aa_13` | separate 10.28 m burial contour with 3 m cadence, opening-aware recessed niche backs, closed jamb/lintel prisms, sarcophagus plinths, buttresses, relief bands, and a closed vault | Implemented and visibly selected in the staged Builder. PIE rendered the generated interior with 557 helper meshes, 1,116 camera-collision triangles, two live walkable WOK faces, and a 5 x 4 tiled floor UV span. Stock burial-room attachment, dressing coverage, and retail warp remain open. |
| K1 Korriban monumental tomb hall | `m39aa_07` | separate 22.08 m playable rise, 42 x 31.5 m evidence footprint, 10.5 m pylon cadence, giant closed pylons/capitals, relief courses, corner supports, and a closed monumental vault | Implemented and visibly selected in the staged Builder. PIE rendered 417 helper meshes, 852 camera-collision triangles, and two live walkable WOK faces. The shared UV correction repeats the 42 x 31.5 m stock floor at 14 x 10.5 UV tiles instead of stretching one texture across the hall. Compatible stock hall attachment, complete props, and retail warp remain open. |
| K1 Korriban measured dressing library | `m37aa_12`, `m39aa_07` | twelve categorized stock-derived dressing classes, including carved relief/buttress/rock pieces plus measured sarcophagus, offerings, floor and ritual daises, vault pier/ring, monument pylon, and fallen monument rock | First visible shelf pass implemented. All eight new assets resolve directly from installed K1 geometry, retain stock diffuse textures and UVs, strip baked lightmaps for authored relighting, and use visual-only zero-face WOKs. Actual staged-app proof physically dragged two cards into the viewport, Shift-selected both authored-room objects, deleted them with the pinned shelf command, and verified live one-command undo/redo plus correct 3 → 1 → 3 → 1 room-count HUD transitions. Additional tomb-specific props and retail module proof remain part of the Korriban graduation gate. |

The starter interior corpus contains nine room examples, 416 classified surfaces,
and 47,172 triangles. The Shadowlands organic corpus adds eight evidence rooms,
115 classified surfaces, and 14,530 triangles from Upper and Lower Shadowlands.
The current K1 Korriban tomb corpus adds 23 nonempty rendered rooms across
`m37aa`, `m38aa`, `m38ab`, and `m39aa`; zero-surface layout/group nodes are
excluded from geometric training.
Direct model-pipeline comparisons for Taris evidence rooms
`m02aa_03a` and `m02aa_06a` match PyKotor node ground truth with zero
discrepancies. The corpus is stored beneath the user's local Ghost Studio cache,
not in the repository or the game installation.

## Rollout Waves

Each line is a style family, but every source warp remains separately tagged
in the corpus so visibly different subareas can graduate into their own kit.

### KOTOR I

1. **Endar Spire and Taris:** finish `end_m01aa`/`end_m01ab`; then Taris upper
   and lower apartments/city, Undercity, sewers, cantinas, estates, Sith/Vulkar/
   Bek bases, and the swoop platform (`tar_m02*` through `tar_m11*`).
2. **Dantooine:** enclave/estate interiors, courtyard and field architecture,
   groves, caves, and Rakatan ruins (`danm13` through `danm16`).
3. **Tatooine:** Anchorhead civic kits, docking/interior variants, Dune Sea
   cliffs and dunes, Sand People enclave, temple, and surviving cut content
   (`tat_m17*`, `tat_m18*`, `tat_m20aa`, `m19aa`, `m45mg`).
4. **Kashyyyk:** landing port, Great Walkway, Wookiee village/interiors, Upper
   and Lower Shadowlands terrain/vegetation, and cut area (`kas_m22*` through
   `m25ab`).
5. **Manaan:** Ahto City exteriors/interiors, Sith base, Hrakert industrial
   station, underwater structures, and rift terrain (`manm26*` through
   `manm28*`).
6. **Korriban:** Dreshdae, academy, Shyrack caves, Valley monuments, distinct
   tomb families, and cut Czerka depot (`korr_m33*` through `korr_m39aa`,
   `m21aa`).
7. **Leviathan, Yavin, and Ebon Hawk:** prison, command, hangar, bridge,
   station, and ship-interior families (`lev_m40*`, `liv_m99aa`, `ebo_m12aa`,
   `ebo_m46ab`).
8. **Unknown World and Star Forge:** beaches/terrain, settlements, temple,
   catacombs, and all Forge decks (`unk_m41*` through `unk_m44*`, `sta_m45*`).

### KOTOR II

1. **Ebon Hawk, Peragus, and Harbinger:** `001EBO`-`007EBO`, `101PER`-`107PER`,
   and `151HAR`-`154HAR`.
2. **Telos:** station interior/civic families, Restoration Zone terrain,
   underground base, Czerka site, polar terrain, and academy (`201TEL`-`262TEL`).
3. **Nar Shaddaa:** landing pad, refugee/dock architecture, Jekk'Jekk Tarr,
   promenade, yacht, and track (`301NAR`-`371NAR`).
4. **Dxun and Onderon:** jungle/ruin terrain, tombs, Iziz exterior/interior
   civic kits, palace, and sky ramps (`401DXN`-`421DXN`, `501OND`-`512OND`).
5. **Dantooine and Korriban:** plains, Khoonda, cave, enclave states, academy,
   valley, and tomb/cave families (`601DAN`-`650DAN`, `701KOR`-`711KOR`).
6. **Ravager and Malachor V:** ship decks plus surface, depths, academy, core,
   crescent, and proving grounds (`851NIH`-`853NIH`, `901MAL`-`907MAL`).
7. **Optional installed content:** Coruscant (`950COR`, `952COR`-`954COR`) and
   M4-78 (`703KOR`, `705KOR`, `801DRO`-`811DRO`) are indexed only when those
   resources are installed and their use is redistribution-safe.

## Per-Style Acceptance Gate

- A new user can find the style by planet/location rather than a raw resref.
- An interior room and, where applicable, an exterior building can be drawn,
  resized, duplicated, multi-selected, moved, and deleted.
- Wall, corner, doorway, window, floor, ceiling/roof, and terrain magnets align
  without manual coordinate entry; openings never receive obstructing dressing.
- The open viewport visibly communicates the source style from silhouette and
  detail, not just texture swaps on boxes.
- Materials and lightmaps resolve from the selected installed game; no game
  asset bytes are committed to Ghost Studio.
- Complexity is budgeted for Odyssey and supports LOD/culling where required.
- KMAP reload and MDL/MDX/WOK/MOD readback retain geometry, materials,
  provenance, gameplay placement, and walkability with no blocking errors.
- Drawing, resizing, or doorway-snapping rooms regenerates the affected WOKs;
  connected portal hooks must coincide, face opposite directions, and retain
  walkable faces without requiring a separate walkmesh-authoring pass.
- Actual K1/K2 manual-warp proof is recorded before the style is marked Done.

## Immediate Next Slice

1. Continue visual acceptance for the indexed K1 Korriban `m37aa`, `m38aa`,
   `m38ab`, and `m39aa` topologies. Corridor, reliquary, cross-vault junction,
   burial-alcove, and monumental-hall shapes now have distinct measured recipes
   and staged PIE proof. Next inspect every stock/generated join for clipping
   and void exposure, visibly inspect the newly classified
   sealed/external/available stock openings, expand the now-proven twelve-class
   measured tomb dressing shelf with remaining topology-specific props, and
   complete a retail warp through the structurally verified connected-room
   package.
2. Graduate the K1 Shyrack cave connection set from `m34aa`, then verify the K2
   `710KOR` cave and `711KOR` Secret Tomb variants using their own geometry and
   material evidence rather than inheriting the K1 shell blindly.
3. Finish the Shadowlands staged-app proof: choose the combined organic style,
   draw an irregular clearing/path, drag Upper and Lower Shadowlands roots,
   foliage, and landforms from their categorized shelves, verify selection and
   deletion, then export/read back the generated MDL/MDX/WOK/MOD.
4. Complete the Endar/Taris automatic extraction report with repeated-bay,
   cross-section, and magnet statistics, then expose the low-confidence review
   queue in the Architecture Kit inspector.
5. Add corner, doorway, window, and ceiling-piece thumbnails derived locally
   from each recipe; keep raw game meshes outside project files.
6. Add explicit Endar Corridor, Quarters, Junction, and Doorway archetypes so
   choosing one style does not force one room contour onto unrelated spaces.
   Prove each through draw, drag, snap, edit, delete, export/readback, and a
   manual K1 warp.
7. Expand Taris into Upper City, Lower City, and Undercity families before
   starting Dantooine; this validates both constructed and terrain-heavy kits.
8. Reuse the same corpus roles for Terrain mode categories: cliffs and rocks,
   canyon walls, ground forms, ruins, foliage, water-edge pieces, and vistas.
