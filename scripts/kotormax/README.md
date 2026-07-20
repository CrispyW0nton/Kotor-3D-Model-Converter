# 3ds Max/NWMax recovery bridges for `vul803`

This folder contains deliberately guarded 3ds Max bridges for recovering the
surviving `vul803` room geometry. Neither bridge opens or saves a `.max` file by
itself, and every export refuses to overwrite an existing file or sidecar.

Use `vul803_nwmax_loader.ms` and `vul803_nwmax_recovery_bridge.ms` for the first
export from the original Max 9 scenes. They preserve the exact legacy NWMax
0.8 b60 scripted-plugin classes that were present when those scenes were saved. Use
`vul803_recovery_bridge.ms` with KOTORMax only as a geometry-recovery fallback
or second-stage normalization path.

## Proven source and room-role map

The source scenes under
`C:\Users\NewAdmin\Documents\KotorMods\Modules\Q_SellOut\Extracted\LavaPlanet_2011-12-26\LavaPlanet\LavaPlanet\3DsMax_Files`
were saved by **3ds Max 9.0, build M114**. Their embedded
document summaries and the surviving NWMax sanity reports establish this map:

| Room | Source | Evidence and intended use |
|---|---|---|
| `Vul803_01a` | `LavaTemple023.max` | Saved AuroraBase plus all 356 reported names; updated visual candidate |
| `Vul803_01b` | surviving `Vul803_01b.mdl` from `LavaTemple011.max` | Authoritative collision source: one dummy plus one AABB |
| `Vul803_01c` | `LavaTemple023.max` | 34/34 non-root sanity-manifest names survive; visual room listed by the ARE |
| `Vul803_01d` | `LavaTemple023.max` | 84/84 non-root sanity-manifest names survive; not listed by the ARE |
| `Vul803_01e` | `LavaTemple025Sky.max` | Saved sky AuroraBase and all 24 unique reported names; not listed by the ARE |

The surviving `Vul803.are` names exactly three rooms: `Vul803_01a`,
`Vul803_01b`, and `Vul803_01c`. The older ASCII exported from
`LavaTemple011.max` confirms their different roles: `01a` contains 292 trimeshes,
4 lights, and one dummy, while `01b` contains only one dummy and one AABB.

Do **not** replace that collision-only `01b` with a visible export from
`LavaTemple024.max`. The later `01a` and `01b` sanity manifests overlap on 354
of 356 node names, and the two late Max scenes are near-duplicate full visual
states. Loading both late exports as rooms would duplicate and z-fight almost
the entire map. Treat `LavaTemple024.max` as forensic history unless a mod author
deliberately chooses a different room partition.

The `01c` and `01d` base helpers were not saved, but their node membership was
recorded in the NWMax sanity reports. The bridge temporarily reconstructs those
roots in memory, preserves internal parent hierarchies, exports, restores every
changed parent, and deletes the temporary base. It never invokes `saveMaxFile`.
No saved `01c`/`01d` base transform survives. The temporary base is therefore
created at the origin while reparenting preserves each node's world placement;
this intentionally bakes the surviving scene placement into the recovered room.
Keep those reconstructed rooms at `(0, 0, 0)` in the provisional LYT unless
independent source evidence establishes a different original base offset.

## Why legacy NWMax must be the first choice

NWMax and KOTORMax intentionally reuse the old numeric scripted-plugin class
IDs so most saved geometry can migrate. That is not sufficient for every
Vul803 node. Legacy `AuroraDLight` is a scripted **helper** extending `Dummy`;
KOTORMax's class with the same numeric ID is an Odyssey scripted **light**
extending `omniLight`. 3ds Max identifies a scripted class by superclass plus
class ID, so this is not a lossless class match. `LavaTemple023.max` and
`LavaTemple024.max` each contain 15 legacy light helpers, and
`LavaTemple025Sky.max` contains 3.

The safe conversion is consequently two isolated stages:

1. Load only NWMax 0.8 b60, open a copy of the old scene, and export faithful
   NWMax ASCII with `vul803_nwmax_recovery_bridge.ms`.
2. Close 3ds Max. Start a clean process with only KOTORMax if its import or
   cleanup tools are needed, then compile the recovered NWMax ASCII through
   `scripts/compile_nwmax_room_candidate.py`. Never load both toolsets in one
   process.

The NWMax bundle's `nwnmdlcomp.exe` targets Neverwinter Nights and is not the
final KOTOR compiler. The Ghost Studio compiler runs the audited MDLOps 1.0.2
binary at `Saved/ExternalTools/mdlops/mdlops.exe` as an independent check, but
promotes Ghost Studio's controller-free writer output. MDLOps 1.0.2 synthesizes
606 static transform controllers for the surviving `01a`; known-loadable
vanilla rooms use none.

A full scripted-plugin cross-check found seven numeric class IDs shared by the
two toolsets. Five retain the same superclass, while two do not:

| Saved NWMax class | KOTORMax class | Compatibility |
|---|---|---|
| `AuroraBase` helper | `OdysseyBase` helper | Superclass matches; 11/13 old saved parameter names remain |
| `AuroraTrimesh` modifier | `OdysseyTrimesh` modifier | Superclass matches; 14/15 old names remain (`tilefadeprop` is dropped) |
| `AuroraFlex` modifier | `OdysseyFlex` modifier | Superclass and all 5 saved names match |
| `AuroraWalkmesh` modifier | `OdysseyWalkmesh` modifier | Superclass matches, but only 1/4 old names remains; legacy `ig_boxes`, `ig_multimode`, and `ig_recalc` are dropped |
| `AuroraEmitter` helper | `OdysseyEmitter` helper | Superclass matches; 63/67 old names remain |
| `AuroraDLight` helper | `OdysseyLight` light | **Superclass mismatch; not a saved-class match** |
| `AuroraReference` helper | `OdysseyReference` geometry | **Superclass mismatch; not a saved-class match** |

The three audited Vul803 scenes contain the legacy DLight class and no embedded
`AuroraReference` or `AuroraEmitter` class name. The parameter losses still make
KOTORMax a poorer first opener for the saved walkmesh and tile metadata.

## Required tool configuration

1. Use the licensed Autodesk 3ds Max 2019 installation at
   `C:\Program Files\Autodesk\3ds Max 2019`. Version `21.0.0.845` has now opened
   and exported all four registered legacy room partitions through the isolated
   `3dsMaxMCP` workflow.
2. For the preferred legacy pass, copy the complete preserved folder
   `C:\Users\NewAdmin\Documents\KotorMods\Modules\Marius_Things\Extracted\NWMAX\NWMAX\NWmax`
   into the active 3ds Max scripts directory returned by `getDir #scripts` as
   `NWmax`. Keep the complete folder structure; `nwmax.ms` resolves its includes
   and INI files through that exact location. In the staged copy, set
   `[init] usemax=1`, `visible=0`, and `dock=0` in `NWmax.ini`; the recovery
   bridge does not need the legacy floater UI. Then run
   `vul803_nwmax_loader.ms`, call `ghostVul803LoadLegacyNwmax()`, and do this
   **before** opening a copy of the source scene. The loader uses the staged
   `NWmax\nwmax.ms` but verifies the exporter core even if an obsolete optional
   UI call fails late in the original script.
3. For the fallback/normalization pass, use the local KOTORMax tree at
   `Saved/ExternalTools/kotormax/KOTORMax`, or install it into the selected
   3ds Max scripts directory. That tree is byte-identical to the audited
   OpenKotOR `v0.4.2` source revision
   `384213f733396618e38b8691dcfa9a82a6aefe47`. Its UI/version global still
   reports `0.4.1`; that stale label does not mean the detonate/export fixes
   are absent.
4. Do **not** autoload KOTORMax and NWMax in the same process. They reuse the
   same permanent scripted-plugin class IDs and globals. Loading both corrupts
   the exporter state.
5. Whichever toolset is used, load it before opening a copy of the old scene.
   Never save over the source scene.
6. Create a new, empty export directory. Both bridges refuse overwrites.

The supported automated route now lives at
`C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\3dsMaxMCP`. Its typed
recipes stage the source scene and NWMax tree into a private run directory,
pin every executable/input hash, supervise the complete Max process tree, and
publish only verified outputs. The original `.max` scenes and NWMax tree stayed
hash-identical across every successful run. `gmax` remains unsuitable because
it cannot open the `.max` source scenes.

For Max 2019, select compatibility profile `nwmax_0_8_b60_max2019`. It applies
exactly three compatibility edits to the run-owned NWMax copy and records the
final staged-tree hash
`808977a31868f202cf38778a3a4f9b1c23477bbc89a75a03465f99d09136147f`.
It also disables only NWMax's optional legacy weld advisory; all other selected
sanity checks remain enabled. Vul801 `01c` additionally registers four exact
static nodes (`Line04`, `Cylinder02`, `Cylinder03`, `Cylinder04`) for a
fail-closed in-memory `resetXForm`. The bridge requires static allowlisted
controllers, leaf/single-instance isolation, and preservation of evaluated
vertices, topology, material IDs, smoothing groups, edge visibility, every map
channel, world bounds, and every non-target room node. Its ordered evidence
report is hash-validated before publication; the staged scene is never saved.

## Operator calls

For the preferred legacy route, first run `vul803_nwmax_loader.ms` from
**Scripting > Run Script**, then enter this in the MAXScript listener:

```maxscript
ghostVul803LoadLegacyNwmax()
```

Only after it reports that the legacy core is ready should you open a copy of
the indicated scene and run `vul803_nwmax_recovery_bridge.ms`.

Audit a manifest without changing the scene:

```maxscript
ghostVul803NwmaxAuditManifest \
    @"C:\Users\NewAdmin\Documents\KotorMods\Modules\Marius_Things\Extracted\NWMAX\NWMAX\NWmax\sanity\Vul803_01c_sanitycheck.txt" \
    "Vul803_01c"
```

Export the historical `01a` partition from `LavaTemple023.max` (recommended):

```maxscript
ghostVul803NwmaxExportManifest \
    "Vul803_01a" \
    @"C:\Users\NewAdmin\Documents\KotorMods\Modules\Marius_Things\Extracted\NWMAX\NWMAX\NWmax\sanity\Vul803_01a_sanitycheck.txt" \
    @"C:\Users\NewAdmin\Documents\KotorMods\Modules\Converted\Candidates\vul803\MaxRecovery\ASCII" \
    replaceExistingRoot:true
```

`replaceExistingRoot:true` does not overwrite or delete the saved root. It
temporarily renames that root, creates an exact manifest-only base, exports,
restores every parent, deletes the temporary base, and restores the original
root name. This prevents the saved all-in-one scene hierarchy from pulling the
later `01c`/`01d` partitions into the `01a` visual export.

Forensic whole-root export remains available, but it is not the module recipe:

```maxscript
ghostVul803NwmaxExportExistingRoot \
    "Vul803_01a" \
    @"C:\Users\NewAdmin\Documents\KotorMods\Modules\Converted\Candidates\vul803\MaxRecovery\Forensics_WholeRoot"
```

Temporarily reconstruct and export `01c` from `LavaTemple023.max`:

```maxscript
ghostVul803NwmaxExportManifest \
    "Vul803_01c" \
    @"C:\Users\NewAdmin\Documents\KotorMods\Modules\Marius_Things\Extracted\NWMAX\NWMAX\NWmax\sanity\Vul803_01c_sanitycheck.txt" \
    @"C:\Users\NewAdmin\Documents\KotorMods\Modules\Converted\Candidates\vul803\MaxRecovery\ASCII"
```

Repeat the manifest call for `Vul803_01d` only as an optional recovery artifact;
it is not in the surviving ARE room roster. Open `LavaTemple025Sky.max` for the
optional `01e` sky candidate. `LavaTemple024.max` may be exported into a separate
forensics directory for comparison, but its late `01b` root must not replace the
authoritative collision-only `01b` in the provisional module.

The historical `01a`, `01c`, and `01d` manifests share only `W_Pilllar` and
`ignore_NGon01`. NWMax skips the `ignore_*` node by convention. Inspect the
remaining shared `W_Pilllar` node after live export to confirm whether it is the
intended collision helper before packaging more than one partition.

The historical sanity reports contain duplicate/weld warnings, which probably
explains why the later ASCII exports were not retained. The bridge blocks on a
failed NWMax sanity result by default. After reviewing the newly written sanity
report, create a second empty output directory and explicitly recover ASCII for
cleanup with:

```maxscript
ghostVul803NwmaxExportManifest \
    "Vul803_01c" \
    @"C:\Users\NewAdmin\Documents\KotorMods\Modules\Marius_Things\Extracted\NWMAX\NWMAX\NWmax\sanity\Vul803_01c_sanitycheck.txt" \
    @"C:\Users\NewAdmin\Documents\KotorMods\Modules\Converted\Candidates\vul803\MaxRecovery\ASCII_ReviewedOverride" \
    allowSanityFailure:true
```

That override marks the result as recovery input only. It does not waive the
topology, AABB, WOK, vanilla-structure, or retail-game proof gates below.

If legacy NWMax cannot load in the selected licensed 3ds Max version, restart
3ds Max without NWMax, load only KOTORMax, and run
`vul803_recovery_bridge.ms`. Its equivalent functions omit `Nwmax` from the
names (`ghostVul803ExportExistingRoot`, `ghostVul803ExportManifest`). Treat that
route as visual-geometry recovery: audit/recreate the legacy lights separately.

The KOTORMax fallback can be preflighted and then batch-run non-destructively:

```powershell
py -3.14 scripts/recover_vul803_max_scenes.py --preflight
py -3.14 scripts/recover_vul803_max_scenes.py
```

Every batch run receives a new evidence directory and hashes the source scenes
before and after. The fallback whole-root `01a` plus reconstructed `01c`/`01d`
exports are forensic; use the legacy manifest recipe above for actual room
partitioning.

## Required proof after export

Both bridges produce ASCII MDL, not final engine binaries. For each room:

1. Compile separate K1 and K2 controller-free candidates with
   `scripts/compile_nwmax_room_candidate.py`. Its MDLOps result is audit-only.
2. For the final `01a` visual room, use the surviving `01b` AABB only as recovery
   evidence/input; generate a floor-only external WOK and embed a validated AABB
   in the actual room MDL. Do not treat any visual export as a walkmesh or ship
   the collision source as a duplicate visible room without retail proof.
3. Compare MDL/MDX/WOK structure with a known-loadable vanilla room.
4. Import, save, and reopen the KMAP in Map Studio.
5. Package non-destructively, then manually warp and walk the module in each
   target game. Parsing alone is not engine proof.

The current Max-2019 recovery merges `01a` and `01c` as one visual shell and
uses collision-only `01b` once; `01c` has no independent collision proof and
must not receive a duplicate overlapping WOK. Vul803 now passes the K1 and K2
headless gates with 370 visual meshes, 17,113 visual vertices, 27,792 visual
faces, 17 textures, one 127-vertex/145-face embedded AABB, an identical
145-face external WOK, 11 closed perimeter loops, zero controllers, and zero
nonzero node-header `+8` values. Vul801 passes with 287 meshes, 12,754 vertices,
18,010 faces, 17 textures, a 314-vertex/336-face WOK, three closed perimeter
loops, zero controllers, and zero nonzero node-header `+8` values. Evidence is
under each module's `Max2019NWMaxCompileHardened` directory. These remain
structural candidates, not claims that either complete module or a retail K1/K2
warp has been proven.

Fresh `Max2019NWMaxMergedHardened` K1/K2 MOD packages for both modules now pass
serialized engine-contract validation, package readback, Map Studio import,
editable-room conversion, KMAP save, and fresh KMAP reopen. The proof retained
27,792 render faces/145 WOK faces for Vul803 and 18,010 render faces/336 WOK
faces for Vul801. Vul801 K1 includes its nine required K2 stock texture ports.
Vul801's WOK has three closed but disconnected components, which is structurally
valid but requires deliberate retail movement/pathing inspection. Nothing was
installed into either game; the user's manual warp, movement, camera, texture,
and transition test is still the final proof gate.
