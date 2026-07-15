# Handoff: Dathomir Rancor MDL-writer render crash (swkotor2+0x4962c)

**Date:** 2026-07-09  **Repo:** `C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\Ghost-Studio`
**Branch:** ghost-studio

## Mission

Get the user's custom high-fidelity Rancor (a BIG boss) rendering in live KOTOR II.
The creature is placed in the working `plcaa` test map. Ultimate deliverable: the
custom mesh loads, textures, animates, and is survivable in combat.

## TL;DR of the current bug

The custom `dat_rancor` model **crashes KOTOR2 at `swkotor2.exe+0x0044962c`
(0xc0000005 access violation) during plcaa area load.** After ~18 live tests this
session, the crash is isolated with high confidence to **our MDL writer's
render-buffer setup for `render=True` LARGE meshes.** Everything else is proven
working. You are very close.

## What is PROVEN (do not re-litigate)

Established by live in-game bisection (screenshots + Windows WER + our debug logger):

1. **The custom UTC / appearance.2da / naming / plcaa placement all work.**
   Proof: shipping VANILLA `c_rancor.mdl` bytes renamed to `dat_rancor` through the
   full custom chain loaded fine with the "DATHOMIR RANCOR" nameplate.
2. **The crash is 100% in OUR MDL writer**, not the mesh/UTC/2DA/appearance.
   Proof: round-tripping VANILLA `c_rancor` geometry through our
   reader→`MDLBinaryWriter` (identical geometry, only our writer differs) crashes.
3. **The writer is CORRECT for Drexl** — round-tripping the known-good July-3
   `c_drexlf` through the current writer yields a byte-near-identical file (delta
   -9 bytes). So it is NOT a general writer regression; it is c_rancor-shaped-data
   specific.
4. **The crash is in the RENDER path for `render=True` LARGE meshes.**
   - Skeleton-only (body skin stripped to dummies) → **LOADS** (eyes render).
   - Body meshes kept with FULL geometry+skin+MDX but **`render=False`** → **LOADS**.
   - Body `render=True` (skin) → **CRASH**. Fresh body `render=True` as rigid
     (non-skin) → **CRASH**. Tiny `render=True` eye meshes (23 verts, non-skin) →
     **render fine**. So: `render=True` + large ⇒ crash; the wrongness scales with
     size (small render meshes survive).
5. **Not the mesh DATA** (render=False with all data present loads),
   **not the MDX layout** (validated: no OOB, no overlap),
   **not the render-batch descriptors** (nbatch/counts/index-counts match vanilla),
   **not the render index buffer** (byte-identical to vanilla for the body node),
   **not bonemap / skin bone indices / node numbering / controllers / node-header
   fields** (all match vanilla or differ only in ways the working Drexl shares).

## TOP HYPOTHESIS for the next step (untested)

The clearest remaining render-path difference between our output and vanilla is the
**MDX vertex format / tangents:**

- Vanilla c_rancor skin meshes: `mdx_data_size=100`, `mdx_data_bitmap=163 (0xA3)`,
  `mdx_tangent_offset=32` — i.e. TANGENT/bump data present.
- Our meshes: `mdx_data_size=64`, `mdx_data_bitmap=35 (0x23)`, `tangent_offset=0xFFFFFFFF`
  — NO tangents.

Drexl also lacks tangents and renders — BUT Drexl's meshes are small (max 1059
verts) and the crash scales with size. Hypothesis: the engine's render-buffer
allocation for a large mesh assumes/reads a vertex stride or tangent block that our
smaller MDX doesn't provide, overrunning for large vertex counts.

**Concrete next test:** make our writer emit tangent data (bitmap 163 / stride 100
/ tangent+bitangent+normal 36 bytes) for skin render meshes so the MDX matches
vanilla, then rebuild + deploy + warp plcaa. If it loads, that's the fix. If not,
the next candidate is the "MDL vertex array" (the XYZ-only fallback array at
`verts_off`, `mdl_writer.py` ~line 1544) or the render-batch "inverted counter"
interaction at large sizes.

Also worth trying the moment it's available: the **Ghidra decompiler was DOWN all
session** — the definitive answer is the C of `FUN_00449450` (the crashing recursive
mesh sizer at `0x00449450`). Retry it; if up, decompile `0x00449450` and its caller
`0x005124d0` to read exactly which field/allocation overruns.

## The crashing function (from disassembly, decompiler was down)

`FUN_00449450(param_1, param_2)` at ghidra `0x00449450` (file offset 0x4962c is the
fault). It is a RECURSIVE model/mesh memory sizer run during area load: reads
`node[+0x48]` and `node[+0x3c]` (controller/data counts) × `param_2`, accumulates a
global size at `[0x00a1dee0]`, then walks `node[+0x2c]` children (`[+0x30]` count),
recursing. Fault instruction: `MOV EDX,[EAX+ECX*4]` where `EAX = node->children`
came out a tiny bad value (e.g. 0x2cac) — a corrupted/garbage pointer, consistent
with a preceding mesh-size overrun. Writer comments reference a sibling crash at
`swkotor2+0x4920e` ("inverted mesh counter … array-grow crash") — same mesh-array
code region.

## Fixes ALREADY applied this session (all in CHANGES.md, newest first: T2548→T2533)

- **T2548** `mdl_writer.py`: removed `uv_dir_x' , 0.0) or 1.0` forced default (wrote
  1.0 where working models have 0). Real regression, fixed, but not THE crash.
- **T2541/T2545** `character_builder.py` + `headless_body_workflow.py`: preserve
  native rendered detail trimeshes (Rancor eyes) instead of dummying them; synthesize
  position(type8)+orientation(type20) bind controllers on split skin nodes
  (`_ensure_skin_node_bind_controllers`).
- **T2538**: geometry-header name (MDL +0x14) renamed to the file resref while root
  node + anim_root stay at the base name (`build_dathomir_rancor.py` resref rename).
- **T2536**: strip pass keeps native non-rendered bone-geometry trimeshes.
- **T2535**: `apply_template_rig` adopts the template's `anim_scale` (root-motion fix).
- **T2534**: `prefer_base_archive` loading so tests/donors read vanilla, not Override
  shadows; restored lost template-rig contracts.
- **T2533**: split-seam weight welding + creature base-bind gate.
- **T2540 (other agent)**: node-header +8 must be 0 — already in the writer.

NOTE: the node+8=0 fix and all the above are baked into the CURRENT writer/pipeline;
the deployed model passes gates for node+8==0, skin controllers present, uv_dir_x==0.

## Build & deploy tools (all headless, in `scripts/`)

- **`scripts/build_dathomir_rancor.py`** — THE builder. fit→weld→(decimate)→rig→
  split→resref-rename→export; also generates appearance.2da (row 671, race=dat_rancor,
  cloned from vanilla row 80) + `dat_rancor01.utc` (clone of g_rancor01 boss,
  tuned to Str16/HP80/CR6 via env `RANCOR_STR`/`RANCOR_HP`/`RANCOR_CR`).
  Flags: `--no-decimate`, `--no-weld`, `--no-anim` (raw-writer, strips anims),
  `--rigid` (strip skin), env `RANCOR_BONE_LIMIT=15`, `RANCOR_DECIMATE_KEEP=0.45`.
  Output dir: `C:\Users\NewAdmin\Documents\KotorMods\Dathomir\Characters\Rancor\MDL`.
- **`scripts/place_rancor_in_tst_light.py`** — GIT-instance placement pattern (Drexl
  example); repackages a module via `module_save_pipeline.build_erf_v1_archive`.
- **`scripts/k2_plcaa_gameplay_matrix.py`** — builds the plcaa test map; env
  `RANCOR_TEST_RESREF` toggles dat_rancor01 vs vanilla g_rancor01 for A/B. S13 asserts
  the rancor is in the packaged GIT. Output:
  `artifacts/map_studio/k2_plcaa_test_map/install/Modules/plcaa.mod`.
- Ad-hoc diff scripts used this session live in `/tmp` (drexl round-trip diff, mdx
  layout, idx diff, skeleton-only, body-norender) — recreate as needed; patterns are
  in the conversation. Key one to re-derive: round-trip vanilla c_rancor through
  `MDLBinaryWriter().write()` and byte-diff mesh headers/arrays vs vanilla.

## Live-test loop (the ONLY acceptance test — parsers all accept the broken model)

1. Build with `build_dathomir_rancor.py` (or a targeted probe script).
2. Deploy: copy `dat_rancor.mdl/.mdx/_t00.tga/appearance.2da/dat_rancor01.utc` to
   `<K2>\Override`; copy `plcaa.mod` to `<K2>\Modules`; **delete `<K2>\currentgame\plcaa*`**.
3. Arm the debug logger BEFORE launch (see below), 1800s window.
4. USER launches via Steam, loads a normal save (**Game4**, not an autosave — plcaa
   autosaves are corrupt/in-area; moved to `Saved/GameTestStaging/bad_plcaa_autosaves`),
   then `warp plcaa`. Entry at (30,30); rancor at (30,48).
5. Read crash: `Saved/KotorLiveLogs/<session>/summary.json` last_exception, OR Windows
   WER (`Get-WinEvent Application id 1000` filtered to swkotor2) for the fault offset
   (add 0x400000 for the ghidra address). The logger only captures if attached before
   the crash and within its window; the user must launch promptly.

## Environment setup (PowerShell, before KotorMCP / Ghidra)

```
$env:GHOSTRIGGER_ROOT="C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\Ghost-Studio"
$env:AGENTDECOMPILE_MCP_SERVER_URL="http://170.9.241.140:8080/mcp/"
$env:AGENTDECOMPILE_HTTP_GHIDRA_SERVER_HOST="170.9.241.140"
$env:AGENTDECOMPILE_HTTP_GHIDRA_SERVER_PORT="13100"
$env:AGENTDECOMPILE_HTTP_GHIDRA_SERVER_REPOSITORY="Odyssey"
$env:AGENTDECOMPILE_GHIDRA_USERNAME="OpenKotOR"
$env:AGENTDECOMPILE_GHIDRA_PASSWORD="revanlives"
$env:AGENTDECOMPILE_MCP_HEADERS_JSON='{"User-Agent":"PyKotorAgent/1.0","X-Agent-Version":"1.0","X-Agent-Server-Username":"OpenKotOR","X-Agent-Server-Password":"revanlives","X-Ghidra-Repository":"Odyssey","X-Agent-Server-Repository":"Odyssey"}'
$env:AGENTDECOMPILE_K2_STEAM_PROGRAM_PATH="/TSL/k2_win_steam_aspyr_swkotor2.exe"
```

## KotorMCP tools (drive as Python, `native/GhostRigger.Core.Automation/Python/src`)

- Decompiler: `kotormcp.tools.decompile` → `handle_decompile_function({'game':
  '/TSL/k2_win_steam_aspyr_swkotor2.exe','function':'0x00449450'})`,
  `handle_get_references({'address_or_symbol':'0x00449450'})`, `handle_ping`.
- Live crash logger: `kotormcp.tools.kotor_live_log` → `handle_start`/`handle_stop`
  (`{'game':'k2','session_label':...,'wait_for_process':True,'duration_seconds':1800,
  'asset_resrefs':[...]}`).
- Input/warp/hook: `kotor_input`, `kotor_dinput_hook`, `game_test`
  (`handle_prepare_save_warp_test`, `handle_list_saves`). DirectInput proxy is
  installed at `<K2>\dinput8.dll` (our build); needed only for automated input.

## Key file paths

- Writer (3 identical copies — fix ALL): `src/core/mdl/mdl_writer.py`,
  `native/GhostRigger.Core.IO/Python/src/core/mdl/mdl_writer.py`,
  `native/GhostRigger.Runtime.Core.Host/Python/src/core/mdl/mdl_writer.py`.
  The render/mesh header write is `_write_mesh_header` (~line 1191); render-batch
  synthesis ~1376-1593; skin header `_write_skin_header` ~1644; MDX/tangent bitmap
  logic — search `mdx_bitmap`, `tvert_offs`, `mdx_stride`.
- Reader: `native/GhostRigger.Core.IO/Python/src/core/mdl/ghostrigger_mdl_reader.py`
  (MDX fields ~line 108-120).
- Pipeline: `native/GhostRigger.Core.Workflow/Python/src/core/characters/`
  `headless_body_workflow.py` (split/seam/controllers), `character_builder.py`
  (apply_template_rig/strip). Loader: `.../src/core/game/kotor_loader.py`.
- Working reference (LOADS in-game): `exports/SAO_Drexl_Working_K2_Package_20260703/
  Override_VERIFIED_REPLACEMENT/c_drexlf.mdl` — use for round-trip diffing.
- Vanilla c_rancor: load via `ResourceManager().get_k2().get_bif('c_rancor', RES_MDL/RES_MDX)`.
- Game: `C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II`.

## Memory & context

- Conversation reference: this session (Fable/Opus). Auto-memory index at
  `C:\Users\NewAdmin\.claude\projects\C--Users-NewAdmin-Documents-GDeveloper-Workspaces-Ghost-Studio\memory\MEMORY.md`,
  esp. `dathomir-rancor-boss-package.md`, `plcaa-mdl-controller-crash.md`,
  `kotor-ghidra-engine-validation.md`, `changes-md-code-drift.md`.
- CHANGES.md entries T2533–T2548 document every fix with verification.
- **Verify-empirically rule:** BOTH our reader and pykotor accept the broken model;
  only live KOTOR2 is a valid acceptance test. Do not trust "the parser loads it."

## Deployed state right now

`<K2>\Override\dat_rancor.mdl` is currently the round-trip `body render=False` PROBE
(loads, invisible body, eyes only) — NOT a shippable model. Before real testing,
rebuild the full model with `python scripts/build_dathomir_rancor.py --no-decimate`
and re-stage. currentgame plcaa cache should be cleared each deploy.
