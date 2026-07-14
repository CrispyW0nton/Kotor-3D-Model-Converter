# Map Studio PIE clean-room contract (2026-07-12)

## Purpose and proof boundary

Map Studio's first Play-in-Editor slice is a deterministic authoring aid for
checking player start placement, walkable WOK continuity, ramps, boundary
blocking, click-to-move reachability, and approximate third-person camera
occlusion. Its permanent user-facing label is:

> **Simulation — not KOTOR proof**

The current bounded preview extends that WOK preflight with a retained
body/head player DAG, inherited idle/walk/run animation, retained idle creature
DAGs, documented KOTOR-style controls, and ambient UTS playback. These are
editor previews of authored resources and intent; they do not turn PIE into an
Odyssey VM or establish behavioral parity with the game.

PIE is not an embedded Odyssey runtime. It must not claim exact KOTOR
pathfinding, locomotion acceleration, camera recovery, AI, combat, NWScript,
dialogue, animation state, triggers, save-state behavior, lightmaps, or module
loading. The only release-grade runtime proof remains Map Studio UI export,
transactional install, and a user-performed `warp plcaa` in KOTOR 2 with the
live logger armed. A successful headless or visible PIE check may never promote
an asset to “works in KOTOR.” This agrees with the earlier two-mode decision in
`docs/audits/map_studio_holocron_ghostscripter_pie_crosscheck_2026-07-12.md`.

## Evidence used

All retail extraction was read-only through the installed games' `chitin.key`
and PyKotor. The relevant source resources and payload hashes are recorded so a
future pass can distinguish retail data from Override data.

| Evidence | Local source | Result |
| --- | --- | --- |
| K1 `surfacemat.2da` | `C:\Program Files (x86)\Steam\steamapps\common\swkotor\data\2da.bif` | 779-byte resource, SHA-256 `db38df7b30443851ea84d150fb1979725fe90f08d16fdfcb6e91aaee05278915` |
| K2 `surfacemat.2da` | `C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II\data\2da.bif` | 779-byte resource, SHA-256 `a234152a33da2bf818d0661da871a1b0efd6c07905ecdf3e538cc72cad2ecb32` |
| K1/K2 `creaturespeed.2da` | each game's retail `data\2da.bif` | K1 SHA-256 `77d4b0117b891f567b50b033eb3aaa02805ab30f0d92199fb3e99ca3e455f608`; K2 SHA-256 `e1d35a5e6f2e4576d9db13a690f3f32d0e0496fc4e7714b5c8aa8e644afb620c` |
| K1/K2 `camerastyle.2da` | each game's retail `data\2da.bif` | K1 SHA-256 `b1f3d321414f16c5768b5453b803d10a2605cc3c2799da65426122f8ec6f99a0`; K2 SHA-256 `1725a57dc4491de84291a110c35b42e91c1934573273f4e467f546c8b0820b5a` |
| K2 PC manual, PDF page index 3 / printed pages 4-5 | `C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II\Docs\Manual.pdf` | 6,834,664 bytes, SHA-256 `2fb54994184bbeaf6ead2c7fbf5138ea1917a50caba2bf7b227ae4f25545b20b`; documents W/S, Z/C, A/D, Caps Lock, and Ctrl/Mouse Button 2 camera controls |
| Installed K1/K2 INI camera values | each installed game's `swkotor.ini` / `swkotor2.ini` | Both record `Keyboard Camera DPS=200`, acceleration `500`, and deceleration `2000`; K1 INI SHA-256 `b5aff110100dc0eb48a29da78db317ec3ffd45a0c82e8509318a1d958e35902b`, K2 INI SHA-256 `e47e22b959f57f5f47041add7c9e52dac38923a527ebef4f73b76b7ffa8f0424` |
| K2 camera reverse engineering | `C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\ghidra\projects\active\kotor-2\findings.md` | Projection and stored camera-field plumbing recovered at address level |
| K2 camera type-name inventory | `C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\ghidra\projects\active\kotor-2\exports\strings.txt` | RTTI names include `CAurBehaviorCameraFollow`, `CSWBehaviorCamera`, `CSWCameraOnAStick`, `CSWCameraFreeLook`, and `CSWCameraNavigate`; names alone do not prove behavior |

The Ghidra findings establish that `FUN_0047f320` calls `gluPerspective` at
`0047f6d7`; camera `+0x204`, `+0x210`, and `+0x214` provide vertical FOV, near,
and far. The base constructor at `0047ecd0` initializes 45.0/0.1/100.0, the
configuration path at `0083db30` has 65.0/0.1/100.0 fallbacks, and setters reach
`0047f190` and `0047f160`. Retail `camerastyle.2da`, rather than either fallback,
provides the normal DEFAULT gameplay FOV of 55 degrees. No exact follow-camera
or locomotion update routine has been recovered, so PIE must not describe its
camera or movement response as a port of those routines.

The K2 manual supplies input semantics, not an implementation. PIE therefore
maps W/S to forward/backward movement, Z/C to strafe, A/D to camera rotation,
Caps Lock to the free-look toggle, and Ctrl or middle mouse to look-about. It
consumes the wheel instead of inventing an undocumented follow-camera zoom.
Shift-to-run is retained only as a labeled editor convenience. The installed
INI target of 200 degrees per second informs keyboard camera turn. PIE now uses
a clean-room approach-to-target step with the recorded 500 acceleration and
2000 deceleration values, but those constants do not reveal Odyssey's timestep,
state machine, easing, clamping, or integration order. This remains a bounded
editor approximation, not a recovered engine routine.

## Verified retail constants

### Surface-material flags

These are literal row IDs whose retail `surfacemat.2da` column is `1`:

| Game | `walk` | `walkcheck` | `lineofsight` |
| --- | --- | --- | --- |
| K1 | 1, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14, 18, 30 | 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 30 | 1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17, 19 |
| K2 | 1, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14, **16**, 18, 30 | 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 30 | 1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17, 19 |

The K2-only `walk` flag on surface 16 is significant. PIE must select the table
by target game and must not reuse a single historical “walkable IDs” set.
`walkcheck` and `lineofsight` are distinct contracts; neither is a synonym for
`walk`.

### Player rates

Retail `creaturespeed.2da` row 0 (`label=PC_Movement`, `2daname=PLAYER`) gives:

| Game | Walk rate | Run rate |
| --- | ---: | ---: |
| K1 | 3.20 | 5.40 |
| K2 | 1.70 | 5.40 |

PIE may use these as constant target speeds. Constant-speed camera-relative
WASD, acceleration shape, capsule radius, step height, slope response, sliding,
and fixed-step integration are clean-room approximations until engine behavior
is separately recovered and verified.

### DEFAULT gameplay camera style

The common retail DEFAULT row is distance 3.2, pitch 83 degrees, height 0.45,
speed 20, tilt speed 30, rotation 180, vertical view angle 55, maximum turn rate
1500, minimum turn rate 150, free-look up 15, and free-look down 20. K1 has
`tiltup=0` and `tiltdown=0`; K2 has `tiltup=10` and `tiltdown=-10` plus separate
PC/Xbox free-look speeds of 100/180. PIE may initialize from the common distance,
height, pitch, and FOV. Its obstruction ray, collision margin, easing, orbit
controls, and recovery timing remain approximations, not recovered Odyssey
semantics.

### Documented PC camera controls

| Action | Retail K2 manual binding used by PIE |
| --- | --- |
| Move forward/backward | W / S |
| Move left/right (strafe) | Z / C |
| Rotate camera left/right | A / D |
| Toggle free look | Caps Lock |
| Look about | Hold Ctrl or Mouse Button 2; PIE treats middle mouse as that button |

The manual does not document mouse-wheel follow distance. DEFAULT camera
distance 3.2, height 0.45, pitch 83 degrees, FOV 55 degrees, free-look up 15,
and free-look down 20 are retail table values. The current center-segment
obstruction ray, 0.12-unit padding, and eased recovery are editor choices and
must remain labeled approximations.

## 207TEL WOK coordinate provenance

This is a verified import contract, not a visual guess:

- Retail K2 `207tel.lyt` from `data\layouts.bif` is 516 bytes, SHA-256
  `88f4c5cf9a2eb3021f1f5c74b71779a8f8213ea537132957cee70deee99891c0`.
  It places `207TEL_1` at `(8.41032, -44.2675, 0)` and `207TEL_2` at `(0,0,0)`.
- Retail `207tel_1.wok` was forced to `SearchLocation.CHITIN`, excluding the
  installed Override copy. The `data\models.bif` resource is 63,960 bytes,
  SHA-256 `5d67d036854ce231692acd7fd5a1180671f20b5591b5ff5c24e1e5e5e8c80d2b`,
  with 472 faces and bounds X `[-2.156799, 30.816200]`, Y
  `[-36.660400, -9.147701]`, Z `[10.200470, 14.500400]`.
- Stock `207tel.pth` in `Modules\207TEL_s.rim` is 5,252 bytes, SHA-256
  `9313f6e3c5811eebc7f2c51abb7f366e5341f690947e4a349fd71e7a8397b48c`.
  The installed `207tel.mod` contains the identical PTH payload. It has 37
  points, 74 directed edges, bounds X `[1.676970, 29.950214]`, Y
  `[-34.562233, -10.930918]`, and two disconnected components of 25 and 12
  points.

The raw WOK XY bounds align directly with the PTH XY bounds. Applying the LYT
translation to that WOK would move it to approximately X `[6.2535, 39.2265]`,
Y `[-80.9279, -53.4152]`, destroying that alignment. Therefore imported stock
room WOK vertices are already module-coordinate data for this workflow and must
not receive the room's LYT translation a second time. Newly authored room-local
WOK may still require its authored room transform; provenance must be explicit
instead of guessed. The two stock PTH components must also remain disconnected;
PIE must not fabricate links merely to make a destination reachable.

## PIE behavior contract

The current bounded slice may:

- project the authored player start onto the nearest compatible walkable face;
- sample stacked floors by current Z, preserve ramp height, and reject invalid
  or non-walkable faces using the target game's retail surface table;
- move a finite-radius player proxy across welded adjacent faces, block or slide
  at boundaries, and report the face/surface responsible for a block;
- find click routes only through real face/PTH connectivity and report
  disconnected destinations instead of inventing links;
- follow the simulated player with a DEFAULT-like third-person camera and clip
  its desired eye segment against resident static room geometry;
- attach a runtime-only copy of a BAS-composed KOTOR body/head Odyssey DAG,
  follow the simulated WOK player, and select inherited `pause1`, `walk`, or
  `run` without mutating the source MDL graph or KMAP. Body, head, and
  `SuperModelResolver` chain loads are target-game strict so one game's missing
  resource cannot be silently filled from the other install;
- obtain creature and UTS placements from the controller's public
  authored-placement snapshot, including when the visible project is a
  `KMapProject` shell around the authored module rather than the authored object
  itself. The worker API
  deep-copies only the placement collection, not the complete mutable authored
  project, room geometry, or texture-paint payload;
- prepare creature UTC appearance/body/head recipes, BAS composition, retained
  DAG copies, and initial idle poses away from the Qt thread while leaving the
  flattened authoring previews visible; replace the complete static set only
  through one atomic promotion after preparation succeeds. A cooperative
  `Event` is checked between bounded model-load, composition, hierarchy-copy,
  and idle-evaluation phases so Stop/restart can cancel a running preparation
  without publishing stale actors; safe idle clips then run at a bounded 30 Hz
  while preserving source NCS and DLG references;
- resolve audio through the target game's explicit
  overlay > Override > module > StreamSounds > BIF precedence. `StreamSounds`
  WAV filenames are indexed lazily and case-insensitively as paths, with clip
  bytes read only on demand. Raw loose `.mp3` is excluded because the PIE
  decoder accepts WAV payloads and nondeterministic directory order must not
  let MP3 shadow a valid WAV resref. Voice creation/decoding is staggered in
  12 ms event-loop slices; decoded preview supports interval/variation
  scheduling, looping, volume, positional attenuation, and a 32-voice cap;
- render transient route, destination, collision, and WOK diagnostics without
  mutating KMAP or rebuilding the loaded room model each frame. Atomic creature
  promotion issues one scene/resources/animation render request without a
  viewport `load_model`/reset; initial Simulate and Stop still intentionally
  perform one full load/reload each. An NPC-only retained batch is already the
  frame presentation when the optional player actor is unavailable, so it must
  not be followed by a duplicate camera-only present; and
- suppress the full-size Qt/PIL sibling overlay while the asynchronous native
  pygfx/WGPU surface owns PIE presentation, then restore the exact authoring
  overlays and camera/tool states on Stop.

The native-host post-build delivery contract is manifest-driven rather than a
directory wildcard. `scripts/stage_native_payload_dlls.ps1` reads
`native/GhostRigger.PythonPayloadManifest.json`, validates every exact source
before changing either destination, prunes only manifest-owned DLL names,
snapshots the source set, stages it to the repository root and host `OutDir`,
and SHA-256 verifies both destinations. Invalid platform/configuration or
manifest rows, duplicate projects, missing sources, copy mismatches, and hash
mismatches fail the build. This keeps an unsuccessful staging attempt from
silently presenting a partial PIE payload as the latest build.

The retained creature layer may report faction and explicitly authored movement
intent, but it must not convert either into behavior. The current slice must not
execute NCS/NWScript or DLG dialogue state, run an Odyssey action queue, decide
faction hostility, simulate perception or combat, pretend creature free-roam is
engine AI, or assert that doors, placeables, triggers, encounters, puzzles, and
transitions function in-game. Ambient UTS playback likewise does not reproduce
Odyssey room acoustics, occlusion, mixer priority, or script-triggered sounds.
Later PIE layers may visualize and deterministically exercise authored intent,
but need their own explicit “approximation” diagnostics and dependency checks.
Real script/dialog/AI behavior still requires export closure plus KOTOR runtime
proof.

## Current focused proof (2026-07-13)

- The final post-hardening and actor-palette checkpoint passes 78 unique focused
  cases: 74 across the isolated PIE, audio, creature, 207TEL hydration,
  visual-proof, and animation-slot files; two renderer palette cases; and two
  native payload identity/staging cases. The files are intentionally run in
  isolated pytest processes because their Qt/audio teardown state is not a
  product behavior under test. Targeted `py_compile` also passes.
- The focus-safe real Debug executable ran the custom `plcaa` KMAP on the
  pygfx/WGPU D3D12 path. Direct native-surface capture retained content in all
  12 stationary frames and the short-motion frame, attached the runtime player,
  observed `pause1` then `walk`, moved 0.878333 m, and did not take foreground
  focus. Evidence is under
  `Saved/VisibleProof/2026-07-13_pie_retained_runtime_ipc/`.
- A subsequent ModernGL proof fixed and rechecked the visibly deformed
  PMBAM/PMHC01 player. The old path built the body palette from the complete map
  (71 nodes in the captured log), which changed a 61-node human G5 qBone/tBone
  contract into the unknown/F1 fallback and produced roughly 76x maximum edge
  stretch. PIE now retains the actor model as the palette authority across
  ModernGL, PyGFX, WGPU, CPU fallback, and parity overlays. The real Debug app
  passed with no blockers, 12/12 continuous frames, `pause1` then `walk`,
  2.295 m movement, clean runtime presentation, and no foreground activation;
  direct frame inspection confirms that the stretched torso/arms are gone.
  Evidence is under
  `Saved/VisibleProof/2026-07-13_pie_player_palette_final/`, and the zero-warning,
  zero-error rebuild is
  `Saved/BuildLogs/2026-07-13_pie_player_palette_debug_rebuild.log`.
- A K2:207TEL probe prepared and attached 32/32 retained creature recipes with
  zero failures. Cold preparation took 11.842 seconds off the Qt thread; a warm
  prototype-cache pass took 1.783 seconds. Flattened static previews remained
  present until the complete result was ready, and their atomic structural swap
  took 3.17 ms. Promotion skipped a measured 536.54 ms full bounds pass, made
  one scene/resources/animation request, and made no viewport `load_model` or
  reset call. Initial Simulate and Stop still each perform their intentional
  full load/reload.
- Steady retained animation evaluation for all 32 207TEL idle actors measured
  mean 16.56 ms, p95 17.72 ms, and max 19.61 ms per sample. These are CPU-side
  evaluation measurements, not a guarantee of final presented frame rate on
  every renderer or map.
- The public authored-snapshot path exposes both creature and UTS placements
  through a `KMapProject` shell. On the real 207TEL data it produced 14/14
  active ambient UTS specs and decoded all 28/28 unique referenced clips with
  zero plan warnings, missing resources, or decode failures. The lazy,
  case-insensitive resource scan indexed 832 `StreamSounds` paths in
  approximately 1.02 ms without reading every clip into memory.
- Focused contracts have been added for target-game-strict supermodel/resource
  selection, placement-only worker snapshots, cooperative preparation
  cancellation, NPC-only single presentation, sliced voice startup, WAV-only
  `StreamSounds` indexing, manifest-owned native staging, and retained
  actor-local G5 palette selection. The installed-K2 deformation regression
  supplies the complete map as the normal renderer argument and still requires
  PMBAM's 61-node source model, G5 formula, and bounded edge stretch.
- These results do **not** prove audible playback, a visible animated 207TEL
  creature/audio acceptance pass, arbitrary NCS/DLG/AI behavior, exact KOTOR
  camera or collision response, or KOTOR engine acceptance. The 12/12 result
  specifically proves that the former native-surface/Qt-overlay blank-frame
  race did not recur in that bounded `plcaa` capture; it is not a universal
  rendering-performance claim.

## Verification ladder

1. **Headless simulation proof:** focused tests cover K1/K2 surface differences,
   rates, flat/ramp/stacked WOK sampling, boundary blocking, disconnected routes,
   camera clipping, deterministic fixed-step behavior, and zero KMAP mutation.
2. **Visible GhostStudio proof:** launch the real Debug executable, enter/exit
   Simulate, drive and click-move on a loaded module, observe green/red
   diagnostics and camera blocking, verify native-surface continuity and the
   expected retained player/creature animation and audible UTS content, and
   confirm creature promotion adds no viewport reset/reload while the one
   intentional initial Simulate load and one Stop reload restore the expected
   authoring state.
3. **Structural export proof:** export `plcaa`, read it back, and compare its
   MDL/MDX/WOK/LYT/VIS/PTH/GIT/ARE/IFO structures against loadable vanilla
   equivalents and the established gameplay matrix.
4. **KOTOR proof:** transactionally install the exact staged hashes, arm the live
   logger, have the user manually run `warp plcaa`, and record movement, camera,
   walkmesh, and gameplay observations. Only this step supports “works in KOTOR
   2.”

Confidence is high for the retail table values, projection field plumbing, and
207TEL coordinate provenance; high for the bounded retained-actor recipe and
attachment probe; medium for DEFAULT-style visual matching; and explicitly
unproven for audible UTS acceptance, visible 207TEL animation, exact Odyssey
locomotion, follow-camera collision, pathfinding heuristics, AI, dialogue,
combat, and script execution. Only a user-performed, live-logged `warp plcaa`
can close the KOTOR 2 engine-proof step.
