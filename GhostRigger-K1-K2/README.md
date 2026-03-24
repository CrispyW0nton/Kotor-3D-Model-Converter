# GhostRigger-K1-K2

**A KotOR modding pipeline tool for Star Wars: Knights of the Old Republic 1 & 2 (TSL)**

GhostRigger is an open-source Python tool for working with KotOR's Odyssey Engine model format (MDL/MDX). It can parse, visualise, modify, and cross-port 3D models between KotOR 1 and KotOR 2, run integrity audits, render multi-angle previews, and expose all of its capabilities as a Model Context Protocol (MCP) server for use with AI assistants — entirely in Python, with no game installation required for the core library.

It also integrates with **AgentDecompile** — an AI-powered Ghidra reverse-engineering backend that hosts the fully-analysed KotOR Odyssey Engine binaries (`swkotor.exe`, `swkotor2.exe`) on a shared server. This lets an AI assistant decompile any engine function, search symbols, trace data flow, and inspect memory — all without a local Ghidra install.

> **See [ROADMAP.md](ROADMAP.md) for a full breakdown of completed phases, in-progress work, known bugs, and future plans.**
> **Latest: v5.2 (2026-03-24) — Phase 13.1 Texture-Loading Overhaul; 3427 tests passing.**

---

## What's New (v5.2 — 2026-03-24)

### Phase 13.1 — Comprehensive Texture-Loading Overhaul

Thorough audit and systematic repair of every code path involved in KotOR TPC/TGA texture loading, mapping, and rendering. **67 new tests**, full suite at **3427 passed / 0 failures**.

#### Bugs Fixed

| Bug | Location | Description |
|-----|----------|-------------|
| `BUG-BGRA-1` | `src/gui/viewport.py` | `_load_tpc_bytes_legacy`: enc=12 (BGRA uncompressed) was treated as DXT1, returning black pixels instead of correct colors. Fixed: added explicit BGRA branch with B↔R channel swap and V-flip. |
| `BUG-BGRA-2` | `src/gui/tpc_render_utils.py` | Same enc=12 DXT1 misidentification in standalone render utils. Fixed: same BGRA branch added. |
| `BUG-ENC12-1` | Both decoders | `encoding == 12` now only treated as DXT1 when `data_sz != 0` (compressed). When `data_sz == 0`, it is BGRA uncompressed (Aurora engine / Xbox variant) per PyKotor `TPCBinaryReader`. |

#### Architecture Verified Correct

After deep audit against PyKotor (v2.3.3) and HolocronToolset source:

- **V-flip convention**: Uncompressed TPC (enc=1/2/4 with raw data) is stored bottom-up (OpenGL). The loader flips to top-down (PIL). DXT formats (enc=2/4 DXT, enc=10/12/13/14) are top-down. The GPU renderer's `_GlTexCache._upload` always flips the PIL image before GL upload, and the vertex shader applies `1-uv.y`. This is the correct double-flip flow.
- **TXI extraction**: `_load_tpc_bytes` (via pykotor) correctly reads the TXI trailer from `tpc.txi` after all mipmap data. pykotor normalises `blending punchthrough` → `blending 2`. The `_parse_txi_string` function handles both raw TXI (`punchthrough`) and normalised forms (`2`).
- **Alpha-test threshold**: The float at TPC header bytes [4-7] is now reliably attached to loaded images as `_txi_alpha_test`. The GPU renderer passes it as `u_alpha_test` per draw-call.
- **TXI-to-node pipeline**: `_apply_txi_from_textures_to_model` correctly reads `_txi_str` from PIL images and updates `node.txi_blending`, `txi_alpha_test`, `txi_envmaptexture`, `bump_map`, etc. The condition `if txi_str or _alpha_test != 0.5` ensures nodes with only a non-default threshold still receive the correct punchthrough alpha.
- **Override folder priority**: `GameLibrary.get_texture_data` checks the Override/ folder before ERF/BIF archives, matching the KotOR engine's override rule.
- **ERF quality order**: TPA > TPB > TPC > GUI > other ERFs for texture pack selection.
- **Cubemap handling**: `height == 6 * width` cubemaps are correctly detected and the first face is returned.
- **BGRA uncompressed**: Now fully supported in both the pykotor path (native BGRA→RGBA conversion) and legacy fallback decoder.

#### New Test File

| Test File | Tests | Coverage |
|-----------|-------|---------|
| `tests/test_v210_texture_comprehensive.py` | 67 | TPC detection for all encodings; DXT1/DXT5/RGBA/RGB/greyscale/BGRA loading; V-flip orientation; mipmap chains; cubemaps; TXI extraction/parsing; alpha-test attribute; TextureCache pipeline; apply-TXI-to-node integration; legacy decoder; tpc_render_utils |

---

## What's New (v5.1 — 2026-03-23)

### Phase 7.1/7.2/7.3 — Binary MDL Writer; Phase 12.1 — Override Layer; Phase 10.1 — pyproject.toml

Four new modules + pyproject.toml, **164 new tests**, full suite at **3333 passed / 0 failures**.

#### New Modules

| Module | Lines | What It Does |
|--------|-------|-------------|
| `src/core/mdl_writer.py` | ~740 | Binary MDL + MDX writer: two-pass node tree (resolves forward-refs), exact mesh header (332/340 B), skin/dangly/emitter headers, K1/K2 function pointer selection |
| `src/core/override_layer.py` | ~300 | Override/ folder resource layer: scan, has, get, send_to_override, delete, badge, get_or_fallback |

#### pyproject.toml (Phase 10.1)

GhostRigger is now pip-installable:
```bash
pip install -e .[dev]        # development install with test tools
pip install -e .[gui,kotor]  # with GUI + PyKotor support
```

#### New Tests

| Test File | Tests | Coverage |
|-----------|-------|---------|
| `tests/test_v110_mdl_writer.py` | 106 | File/geo/model/name headers, node headers, mesh headers, MDX buffer, controller arrays, skin/dangly/emitter, full round-trip fidelity (parse→write→parse), K1/K2 versions, animations |
| `tests/test_v111_override_layer.py` | 58 | scan, has, get, get_path, list_by_ext, list_all, badge, summary, model helpers, send_to_override, delete_override, get_or_fallback, edge cases |

#### Key Technical Details — Binary MDL Writer

The writer uses a **two-pass approach** for the node tree to handle forward-references (KotOR's binary format stores parent offsets and child pointer arrays inline within the node header, requiring all node offsets to be known before writing pointers):

1. **Pass 1**: Write every node header + type-specific data, record each node's absolute offset. Write child pointer arrays as placeholder zeros.
2. **Pass 2**: Patch root_off, parent_off, and child pointer values now that all offsets are known.

Mesh header layout (332 B K1 / 340 B K2) verified field-by-field against `mdl_parser._parse_mesh`:
- Fixed-size header ends at +332/+340; skin/dangly headers immediately follow.
- Face array and vertex fallback array addressed via `faces_off` and `verts_off` fields (not inline).
- bm3/bm4 texture names are 12 bytes each (not 32 as earlier docs suggested).

#### Usage — MDL Binary Writer

```python
from src.core.mdl_writer import MDLBinaryWriter

mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
# or write to disk:
MDLBinaryWriter().write_files(model, '/path/to/output.mdl')
```

#### Usage — Override Layer

```python
from src.core.override_layer import OverrideLayer

ol = OverrideLayer('/path/to/KotOR', auto_scan=True)
print(ol.summary())
# → "OverrideLayer: 47 files in /path/to/KotOR/Override"
#   ".mdl: 23 file(s)"
#   ".tpc: 15 file(s)" ...

# Override-aware model load
mdl_data = ol.get_model('pfh0') or game_lib.get_model('pfh0')

# Export to Override
ol.send_to_override('mynpc', 'mdl', modified_mdl_bytes)

# UI badge
badge = ol.badge('pfh0', 'mdl')   # → '[Override]' or ''
```

---

## What's New (v5.0 — 2026-03-23)

### Phase 5.1/5.2 + 9.1/9.2 — Scene Manager, Walkmesh Overlay, Module Loader

Three new core modules with 233 new tests added; full suite now at **3169 passed / 0 failures**.

#### New Modules

| Module | Lines | What It Does |
|--------|-------|-------------|
| `src/core/scene_manager.py` | ~880 | Full view-frustum culling (Gribb/Hartmann), SceneGraph, VIS-based room culling, GIT object placement, AREProperties |
| `src/core/walkmesh_renderer.py` | ~480 | Walkmesh overlay with 23-material color table matching KotOR.js, boundary edge detection, draw list generation |
| `src/core/module_loader.py` | ~310 | High-level bridge: loads module directory → SceneGraph + WalkmeshOverlay dict in one call |

#### New Tests

| Test File | Tests | Coverage |
|-----------|-------|---------|
| `tests/test_v100_scene_manager.py` | 75 | Frustum math, SceneGraph API, VIS/ARE/GIT integration |
| `tests/test_v101_walkmesh_renderer.py` | 87 | Surface colors, WalkmeshFace, overlay loading/filtering/AABB/boundary edges, draw list |
| `tests/test_v102_module_loader.py` | 71 | LoadResult, ModelLookup, LYT→rooms, VIS→links, ARE→fog, GIT→objects, WOK→overlays |

#### Key Fixes

- **Frustum `update_from_camera` rewritten**: Original cross-product logic had inverted plane normals — spheres and AABBs always tested as outside. Replaced with Gregory §12.5.1 canonical half-angle formula: `n_side = fwd*cos(h) ± axis*sin(h)`.
- **`ModuleLoader` uses correct SceneGraph API**: `room_by_name()`, `scene.are_props`, direct `scene.objects` list — all aligned with existing `scene_manager.py` contracts.

#### Usage Example

```python
from src.core.module_loader import ModuleLoader

# Load a module from game directory
loader = ModuleLoader(library=game_lib)  # library optional
result = loader.load_from_directory('/path/to/danm13/', game='K1')

# Access the scene graph
print(result.scene.summary())
# → "SceneGraph 'danm13' (K1): 8 rooms (0 loaded, 8 visible), 42 objects, grass=no"

# Get walkmesh overlays for rendering
for room_name, overlay in result.walkmeshes.items():
    print(f"  {room_name}: {overlay.summary()}")

# Frustum culling
visible = result.scene.visible_rooms(
    camera_pos=(5.0, 3.0, 0.0),
    camera_fwd=(0.0, 1.0, 0.0),
    fov_h_deg=90, fov_v_deg=60, near=0.1, far=100
)
```

---

## What's New (v4.4 — 2026-03-20)

### Deep Multi-Repo Research Pass — 10 Reference Repos Audited

This release is a **deep research pass** across every KotOR modding repository.
No new features were added, but the ROADMAP has been completely rewritten with
concrete implementation references for every planned feature.

**Repos audited:**

| Repository | Key Finding |
|-----------|-------------|
| [xoreos](https://github.com/xoreos/xoreos) | Definitive saber blade algorithm (16 quads from 8 verts), emitter struct layout (224 bytes) |
| [KotOR.js](https://github.com/KobaltBlu/KotOR.js) | Full particle system (1,276 lines), walkmesh GL rendering (1,020 lines), area assembly (1,096 lines) |
| [PyKotor/io_mdl.py](https://github.com/OldRepublicDevs/PyKotor) | 4,783-line binary MDL reader+**writer** — primary reference for Phase 7 (binary write) |
| [PyKotor/frustum.py](https://github.com/OldRepublicDevs/PyKotor) | Gribb/Hartmann frustum culling with VP-hash cache — Phase 5 scene culling |
| [PyKotor/InbuiltNCSCompiler](https://github.com/OldRepublicDevs/PyKotor) | Pure-Python NSS→NCS compiler, no external deps — Phase 12.6 script panel |
| [Kotor.NET/MDLBinaryWriter.cs](https://github.com/nicholasgasior/Kotor.NET) | 575-line binary writer (C#) — secondary reference, K1/K2 function pointers confirmed |
| [Kotor.NET/BWM.CalculateAABBs()](https://github.com/nicholasgasior/Kotor.NET) | Median-split AABB tree builder — Phase 9.3 (walkmesh write) |
| [kotorblender](https://github.com/OldRepublicDevs/kotorblender) | WOK co-import with room MDL, LYT/PTH Blender support |
| [HoloPatcher](https://github.com/OldRepublicDevs/PyKotor) | TSLPatcher `changes.ini` format — Phase 12.5 mod packager |
| [bioware-kaitai-formats](https://github.com/OldRepublicDevs/bioware-kaitai-formats) | Formal KSY grammars for all formats; multi-language code generation |

**ROADMAP now includes:**
- Concrete line-level references for every planned feature (e.g., "Phase 7 → PyKotor `io_mdl.py:4783 lines`")
- Surface material color table for walkmesh visualization (20 materials)
- Full emitter struct field list (224 bytes confirmed by xoreos + PyKotor)
- Area assembly flow (LYT→ARE→GIT, from `ForgeArea.ts`)
- Frustum culling algorithm (Gribb/Hartmann, VP-hash, from `PyKotor/frustum.py`)
- Mod packager design (TSLPatcher `changes.ini` format, from HoloPatcher)
- NWScript compile panel design (pure-Python, from `InbuiltNCSCompiler`)

---

## What's New (v4.3 — 2026-03-19)

### Bug Fixes

| Fix | Details |
|-----|---------|
| **`flask` added to requirements.txt** | The IPC/Ghostworks server was always disabled on a fresh install because `flask` was listed nowhere. Now `flask>=2.3.0` is in `requirements.txt`. |
| **`APP_VERSION` corrected** | Code said `2.7.0`; now correctly reports `4.2.0`. |
| **`KotorModel.nodes` property added** | `model.nodes` now works as an alias for `model.all_nodes()`. Previously only `all_nodes()` existed, breaking code that used the natural `model.nodes` pattern. |
| **Source audit + ROADMAP rewrite** | Complete source audit: every module tested end-to-end. ROADMAP now accurately describes what works vs. what's planned. |

### Honest Current-State Assessment

Here is what actually works if you download the tool today:

**✅ Works reliably:**
- Parse any KotOR 1 or 2 binary MDL/MDX (100% success rate on all 5,764 game models)
- View models in the 3D viewport with full textures, skinning, and lighting
- Browse and search the full game library (auto-detected or manually set)
- Export models to OBJ, GLTF/GLB, FBX (ASCII)
- Import models from OBJ or FBX (via pyassimp)
- Play all animations (80+ controller types)
- Edit creature/placeable/door blueprints (UTC/UTP/UTD)
- Compile ASCII MDL → binary via MDLOps (requires separate MDLOps installation)
- Normal map baking, cloth rigging, auto-rigger

**⚠️ Works but requires extra setup:**
- IPC server (Ghostworks pipeline) — needs `pip install flask`
- KotorMCP AI server — needs `pip install mcp uvicorn`
- FBX import — needs system `libassimp` (`sudo apt install libassimp-dev` / `brew install assimp`)
- MDLOps compile/decompile — needs separate [MDLOps](https://github.com/Torlack/MDLOps) installation

**❌ Not yet implemented:**
- Write binary MDL (only ASCII MDL + MDLOps compile; full binary writer is Phase 7)
- Import GLTF (export only; Phase 8)
- Full module scene viewer (room assembly from LYT; Phase 5)
- Particle/emitter visualization (parsed but shown as sphere; Phase 6)
- Walkmesh overlay (parsed but not drawn; Phase 9)

---

## What's New (v4.2 — 2026-03-19)

### Full Visual Audit: All 5,426 Renders Verified — Zero Bugs

A pixel-level analysis of every rendered model confirmed **zero genuine rendering artifacts**
across all 5,426 front-view renders:

| Category | Count | Notes |
|----------|-------|-------|
| ✅ OK renders (textured, correct) | **4,444** | Clean |
| ⬜ Expected flat/invisible | 981 | Skyboxes, waypoints, GUI objects, trigger volumes |
| 🟡 Intentional glow | 1 | `i_drdrepeqp_003` — amber hologram console (correct) |
| 🔴 **Genuine bugs** | **0** | **Zero** |

All "flat" renders are confirmed module skybox tiles, VFX placeholders, or invisible
utility meshes. Self-illuminated models (`i_drdrepeqp_003` amber hologram,
`901malf` Malachor V yellow-green beams) are **working exactly as intended**.

Report: `audit_output/batch_render/visual_audit.json`

### Automatic Game Directory Detection

GhostRigger now **automatically finds and loads your KotOR installation on startup**
with no configuration required.

#### How It Works

On first launch, a background thread runs `detect_kotor_dirs()` from `src/resources/game_detector.py`:

1. Check `~/.ghostrigger/config.json` (saved from previous session)
2. Check `KOTOR1_DIR` / `KOTOR2_DIR` environment variables
3. Scan **Steam** — reads `libraryfolders.vdf`, parses `.acf` manifests
4. Scan **GOG Galaxy** — Windows registry + common GOG paths
5. Check **default install paths** — `Program Files/LucasArts`, macOS App Support, Linux `/opt`/Lutris
6. Check **Wine/Proton prefixes** — `~/.wine`, Proton `compatdata`
7. Fall back to project `game_data/` (developer convenience)

When directories are found, the library **auto-scans and loads models immediately**
— no manual "Set K1/K2 Dir" or "Scan" button clicks needed.

#### Supported Platforms
- **Windows**: Steam + GOG Galaxy (registry) + Program Files on all drive letters
- **Linux**: Native Steam + Proton compatdata + Lutris + `/mnt/` external drives
- **Steam Deck**: `/home/deck/.steam/steam` + Proton
- **macOS**: `~/Library/Application Support/Steam` + `/Applications`
- **WINE**: `~/.wine/drive_c/Program Files*/LucasArts/SWKotOR[2]`

#### On Subsequent Launches
Saved directories are loaded from `settings.json` and the library scan runs automatically
at startup — models are ready to browse within ~2 seconds.

### Corrected Statistics (v4.2)

PC model count corrected from 115 → **239** (previous summary used stale categorization).
`tools/merge_results.py` now always re-computes categories from resref prefix, ignoring
any stale `"category"` field stored in older JSON.

| Category | Total | Rendered | Triangles |
|----------|-------|----------|-----------|
| Modules/Areas | 3,296 | 3,296 (100%) | 8,541,506 |
| Placeables | 634 | 584 (92%) | 242,786 |
| Other/VFX | 448 | 397 (89%) | 414,838 |
| VFX effects | 274 | 59 (22%) | 87,353 |
| NPCs | 250 | 249 (99.6%) | 534,791 |
| **PC models** | **239** | **239 (100%)** | **538,183** |
| Weapons | 177 | 158 (89%) | 24,136 |
| Doors | 165 | 165 (100%) | 73,850 |
| Creatures | 145 | 144 (99.3%) | 336,206 |
| Items | 126 | 125 (99.2%) | 16,183 |
| Supermodels | 10 | 10 (100%) | 14,409 |
| **TOTAL** | **5,764** | **5,426 (94.1%)** | **10,823,245** |

### New Files
- `src/resources/game_detector.py` — cross-platform KotOR install detection
- `tools/run_full_batch.py` — full game batch render runner
- `tools/run_module_batches.sh` — shell script for module batch rendering
- `audit_output/batch_render/visual_audit.json` — pixel-level render quality report

---

## What's New (v4.1 — 2026-03-19)

### Module Viewer Tab + Area Filter

The Library panel now has a **Module** category tab with:
- Area filter dropdown (≈100 unique areas across K1+K2)
- Thumbnail preview strip (128×128 PNGs)
- Rich display labels with area names and model counts

### OOM-Safe Batch Renderer

Memory-safe two-phase batch rendering:
- **Phase 1**: Orchestrator scans library (~514 MB RSS), writes TODO file, exits via `os.execv`
- **Phase 2**: Lightweight coordinator (~15 MB) launches isolated `batch_modules_slice` subprocesses (~330 MB each)
- OOM-retry logic: splits batch on kill (SIGKILL), automatically retries with smaller batches

---

## What's New (v4.0 — 2026-03-19)

### Full-Game Batch Render & Audit: All 5,764 KotOR Models

This is a major milestone: **every single model** in both KotOR 1 and KotOR 2 has been
individually audited for parse integrity, UV correctness, and visual rendering quality.

#### Key Results

| Metric | K1 | K2 | Combined |
|--------|----|----|---------|
| Total models | ~2,900 | ~2,864 | **5,764** |
| Parse failures | 0 | 0 | **0 (100% parse rate)** |
| Structural issues | ~140 | ~136 | ~276 |
| UV artifacts (false positives filtered) | ~1,500 | ~1,037 | ~2,537 |
| Yellow render artifacts | 0 | 0 | **0** |
| Pink render artifacts | 0 | 0 | **0** |
| Empty renders | 0 | 0 | **0** |

**100% parse rate. Zero yellow artifacts. Zero pink artifacts. Zero empty renders.**

#### Batch Render Tool

The new `tools/batch_render_all.py` script renders every model in both games with
front and back views, building contact sheets and a full JSON report:

```bash
# Render all 5,764 models (takes ~90 minutes)
python3 tools/batch_render_all.py

# Creatures only, with progress ETA
python3 tools/batch_render_all.py --category creatures

# Quick structural audit (no renders, ~60 seconds)
python3 tools/batch_render_all.py --no-render

# Single model (debug / verify fix)
python3 tools/batch_render_all.py --filter c_bantha
```

Output: `audit_output/batch_render/renders/` (PNG thumbnails),  
`audit_output/batch_render/sheets/` (contact sheets per category),  
`audit_output/batch_render/summary.txt`, `results_full.json`

#### UV Issue Classification (v2.0 — Smart Filtering)

| Type | Count | Meaning |
|------|-------|---------|
| `WARN_ATLAS` | ~1,543 | UV > 20 — atlas tiling or multi-segment skins (expected) |
| `ERROR_UV` | ~502 | UV > 100 — almost all are walkmesh/AABB helper nodes |
| `CORRUPT_UV` | ~334 | NaN/INF — 3ds Max object-ID artifacts in area geometry |

All UV issues are in non-renderable area/walkmesh nodes. Character, NPC, weapon, item,
door, and placeable models are all visually clean.

#### v3.9.1 Rendering Fixes (Bantha Milestone)

Two critical rendering bugs were fixed that affected all models:

1. **UV V-flip double-application** — `_build_vbo_data` was flipping V coordinates AND the vertex shader was also flipping them, causing atlas-tiled meshes (especially creature horn geometry) to render inverted. Fix: VBO builder no longer flips; shader is the sole flip source.

2. **World-space vertex threshold too aggressive** — the centroid heuristic to detect world-space meshes used 0.5 units, which incorrectly triggered on small local-space meshes near the origin. Raised to 2.0 units.

Both fixes validated via **bantha visual render**: zero yellow artifacts, horn pixels 3,782 (front) / 1,192 (back), 99% coverage, no pink teeth on tail.

#### Test Suite

**2,727 passing, 163 skipped, 0 failed** as of 2026-03-19.

---

## What's New (v3.7 — 2026-03-18)

### Phase 3.7: K2 Dirt/Hologram Fields + Mesh Average Point

Deep reading of **Kotor.NET** `MDLBinaryStructure.cs` and **xoreos** `modelnode.cpp` revealed
two long-standing parsing gaps:

#### FIX-K2DIRT — K2 dirt and hologram mesh fields now stored

Kotor.NET's `TrimeshHeader.TSLUnknown1/2` comment precisely documents the 8-byte K2
extension block (bytes 0–7 after the flag sequence in K2/TSL trimesh headers):

| Byte offset | Field | Type | Description |
|------------|-------|------|-------------|
| +0 | `dirt_enabled` | uint8 | 1 = dirt decal overlay active |
| +1 | padding | uint8 | — |
| +2–3 | `dirt_texture` | uint16 | dirt texture slot index |
| +4–5 | `dirt_coord_space` | uint16 | dirt UV coordinate space |
| +6 | `hide_in_holograms` | uint8 | 1 = do NOT render in hologram mode |
| +7 | padding | uint8 | — |

**Old behaviour:** `o += 8` — all 4 K2-specific values were silently discarded.  
**Fix:** Parser reads and stores all 4 values as new `ModelNode` fields. K1 models default to False/0.

#### FIX-AVGPOINT — Mesh AveragePoint (centroid) stored and used for depth sorting

Kotor.NET `TrimeshHeader.AveragePoint` (confirmed by xoreos `_averagePoint`) is the
engine-computed centroid of all face vertices in the mesh. The old parser discarded it
with `o += 12`. This caused transparent-surface depth sorting to use the node origin
(bounding-box midpoint) instead of the actual mesh centroid.

**Old behaviour:** `o += 12` — mesh centroid discarded; GPU renderer sorted by node origin.  
**Fix:** Parser reads `avg_px/y/z` and stores as `node.mesh_average_point`. GPU renderer's
`_node_sort_depth()` now transforms this mesh-local centroid to world space and uses it
for accurate back-to-front ordering of transparent surfaces. Particularly noticeable for
large meshes offset from their node origin (Mandalorian robes, big glass windows).

| Source | Confirmation |
|--------|-------------|
| Kotor.NET `MDLBinaryStructure.cs` | `TrimeshHeader.TSLUnknown1/2` — exact K2 field layout |
| Kotor.NET `TrimeshHeader.AveragePoint` | Parsed and stored in C# reader |
| xoreos `modelnode.cpp` | `_averagePoint` used for depth-sort render order |
| PyKotor `gl/models/mesh.py` | `_vertex_blob_cache` — performance design pattern |
| PyKotor `gl/scene/scene.py` | Frustum culling with bounding spheres (future Phase 5 reference) |

**New fields on `ModelNode`:** `hide_in_holograms`, `dirt_enabled`, `dirt_texture`,
`dirt_coord_space`, `mesh_average_point`.

**47 new tests** in `tests/test_v250_phase37_k2_fields_avgpoint.py` — all passing.

---

## What's New (v3.6 — 2026-03-18)

### Phase 3.6: Per-Node Alpha-Test Threshold (FIX-ALPHATEST)

Cross-repo research (**Kotor.NET**, **PyKotor**, **xoreos**) revealed that the GPU renderer
was using a global hardcoded `u_alpha_test=0.5` for **all** punchthrough surfaces.
KotOR stores a per-texture discard threshold as a `float` at TPC header bytes `[4-7]`:

| Source | Confirmation |
|--------|-------------|
| Kotor.NET `KotorModelLoader.cs:47` | Reads `TransparencyHint` from mesh header; skips Diffuse/Ambient (commented out) |
| Kotor.NET `TPC.cs` | `TPCTextureFormat` enum; no `alpha_test` field = it comes from raw header bytes |
| PyKotor `gl/shader/texture.py` | `Texture.alpha_cutoff: float = 0.0` — same concept as our fix |
| xoreos `tpc.cpp` | `alpha_test_threshold` float at header offset 4, 0.0 = "no test" |

**Fixes applied:**
- `_extract_alpha_test_from_tpc(raw_bytes)` — reads float at TPC `[4:7]`, defaults to 0.5 when zero
- `ModelNode.txi_alpha_test: float = 0.5` — new per-node field
- `_apply_txi_to_node(node, txi_str, alpha_test=)` — stores threshold from TPC header
- `TextureCache.get_raw_header(name)` — returns first 128 TPC bytes for threshold extraction
- `_load_txi_metadata_for_model()` — calls `get_raw_header()` per texture
- GPU renderer — sets `u_alpha_test` from `node.txi_alpha_test` when `u_blend_mode==2`

**Result:** Hair, foliage, grates, and glass now use their correct per-surface alpha
discard threshold instead of a one-size-fits-all 0.5.

**40 new tests** in `tests/test_v240_phase36_alpha_txi.py` — all passing.

### Qt/UI Layer Assessment

A suggestion was made to adopt `qtpy` + Qt Designer to abstract away PyQt5/Qt6.
**GhostRigger uses Tkinter, not Qt.** The suggestion is technically sound for Qt projects
but is not applicable here — GhostRigger deliberately uses Tkinter for its
zero-dependency, headless-friendly design. See [ROADMAP.md §3.6](ROADMAP.md) for details.

---

## What's New (v3.5 — 2026-03-18)

### Rendering Fixes — Environment Map & Texture Transparency

Three critical rendering bugs uncovered by deep-auditing **Kotor.NET**, **KotOR.js**,
**xoreos**, and **PyKotor**:

| Fix | Description | Reference |
|-----|-------------|-----------|
| **FIX-1 `bumpyshinytexture` alias** | `bumpyshinytexture` in TXI files is an alias for `envmaptexture`, not a bump map. The previous code routed it to `specbumpmap`, causing missing reflections on HK-47, T3-M4, and many metallic surfaces. | xoreos `txi.cpp:96`; KotOR.js `TXI.ts:161` |
| **FIX-2 Env-map BlendedOver** | KotOR uses `renderGeometryEnvMappedOver` (diffuse first, env blended over with `GL_ONE_MINUS_DST_ALPHA, GL_ONE`). The previous shader used a simple `mix()` (BlendedUnder). Single-pass equivalent: `lit_color += env_col * (1.0 - diffuse.a)`. | xoreos `modelnode.cpp:renderGeometryEnvMappedOver()` |
| **FIX-3 Final alpha for env surfaces** | Env-mapped surfaces must be opaque (diffuse alpha consumed by env blend weight, not exposed as transparency). | KotOR.js `ShaderOdysseyModel.ts` |

### Supermodel Skeleton Merge Fix

| Fix | Description |
|-----|-------------|
| **FIX-4 Recursive bone injection** | `merge_supermodel()` previously used a shallow-copy + flat injection: it only injected the **direct children** of the parent root, silently discarding the full bone sub-hierarchy (`pelvis → spine → chest → ...`). The fix replaces this with `_deep_copy_subtree()`, a recursive helper that walks the parent tree depth-first and injects bones at the correct level while still deduplicating against the child's existing nodes. |

### Test Suite

- **428 tests** passing across Phases 1–3.7 (0 failures).
- 47 new tests for Phase 3.7 K2/avg-point fixes (`test_v250_phase37_k2_fields_avgpoint.py`).
- 40 new tests for Phase 3.6 alpha-test fixes (`test_v240_phase36_alpha_txi.py`).
- 75 new tests for Phase 3.5 env-map/TXI fixes (`test_v230_envmap_txi_rendering.py`).

---

## Feature Status

| Feature | Status |
|---|---|
| Binary MDL/MDX parser (K1 + K2/TSL) | ✅ Complete |
| ASCII MDL parser + writer | ✅ Complete |
| Binary MDL writer (K1 ↔ K2 round-trip) | ✅ Complete |
| K1 ↔ K2 cross-game porter | ✅ Complete |
| Animation engine (keyframe interpolation, SLERP) | ✅ Complete |
| UV pipeline (seam-fix, tiling, multi-layer UVs) | ✅ Complete |
| LBS skinning (linear blend skinning, bone weights) | ✅ Complete |
| TPC/TPA/TPB texture loading with ERF priority | ✅ Complete |
| TXI: embedded TPC trailer + standalone `.txi` file | ✅ Complete |
| TXI: `bumpyshinytexture` → `envmaptexture` alias | ✅ Complete (v3.5) |
| TXI: `blending`, `cube`, `proceduretype`, `wateralpha` | ✅ Complete |
| TXI: per-node alpha-test threshold from TPC `[4:7]` | ✅ Complete (v3.6) |
| K2/TSL: `hide_in_holograms`, `dirt_enabled/texture/coord_space` stored | ✅ Complete (v3.7) |
| Mesh `AveragePoint` centroid stored + used for transparent depth sort | ✅ Complete (v3.7) |
| Environment map BlendedOver rendering | ✅ Complete (v3.5) |
| Sphere-map UV projection (matcap) for env maps | ✅ Complete |
| TPC cube-map face extraction | ✅ Complete |
| `_apply_kotor_alpha` DXT5 rules (5 cases) | ✅ Complete |
| 3D viewport (hybrid GPU/CPU renderer, textures, bones) | ✅ Complete |
| GPU renderer (ModernGL/EGL fast-path + PIL CPU fallback) | ✅ Complete |
| Cloth/PBD physics simulation for dangly nodes | ✅ Complete |
| Game library browser (KEY/BIF/ERF/RIM archives) | ✅ Complete |
| OBJ / GLTF 2.0 import & export | ✅ Complete |
| Auto-rigger (humanoid & creature skeletons) | ✅ Complete |
| GFF reader/writer (UTC, UTI, UTD, DLG, JRL, etc.) | ✅ Complete |
| 2DA reader/writer | ✅ Complete |
| MDX multi-UV channel support (UV1–UV4 + tangent space) | ✅ Complete |
| UTC → appearance.2da → body+head creature pipeline | ✅ Complete (Phase 3.3) |
| Supermodel skeleton merge (recursive hierarchy) | ✅ Complete (v3.5) |
| Supermodel animation inheritance | ✅ Complete (Phase 3.4) |
| MDL controller table (80+ IDs, all KotOR.js IDs) | ✅ Complete |
| Embedded MCP server (43 tools, stdio / HTTP / SSE) | ✅ Complete |
| PyKotor integration (installation discovery, resource lookup) | ✅ Complete |
| Ports & Adapters architecture (Khononov coupling principles) | ✅ Complete |
| AgentDecompile / Ghidra bridge (11 engine RE tools) | ✅ Complete |

## Quick Start

### Requirements

```
Python 3.10+
pip install Pillow numpy
pip install pykotor>=2.3.3     # KotOR resource library (optional but recommended)
pip install moderngl            # GPU renderer fast-path (optional, falls back to CPU)
pip install flask               # IPC server for GUI ↔ MCP bridge (optional)
pip install mcp                 # MCP SDK for Claude Desktop integration (optional)
```

For the AgentDecompile bridge, the remote server at `http://170.9.241.140:8080/mcp/` is used directly — no local Ghidra or PyGhidra install needed.

### Run the GUI

```bash
python main.py
```

### Point to your game directories

In the **Library** panel click **Set K1 Dir** / **Set K2 Dir**, or use environment variables:

```bash
export K1_PATH=/path/to/swkotor
export K2_PATH=/path/to/swkotor2
```

Accepted aliases: `KOTOR_PATH`, `KOTOR1_PATH` (K1); `TSL_PATH`, `KOTOR2_PATH` (K2).

### Use the core library (no GUI)

```python
from src.core.mdl_parser import MDLBinaryParser
from src.core.mdl_porter import CrossGamePorter, MDLBinaryWriter

model = MDLBinaryParser.parse_files('c_bantha.mdl', 'c_bantha.mdx')
print(f"{model.name}: {len(list(model.all_nodes()))} nodes")

k2_model = CrossGamePorter().port(model, target_game='K2')
MDLBinaryWriter().write(k2_model, 'c_bantha_k2.mdl', 'c_bantha_k2.mdx')
```

### Use the MCP server

```bash
python -m src.kotormcp                        # stdio (Claude Desktop default)
python -m src.kotormcp --mode http --port 7001 # HTTP
python -m src.kotormcp --mode sse  --port 7001 # SSE (requires uvicorn)
```

Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ghostrigger-kotor": {
      "command": "python",
      "args": ["-m", "src.kotormcp"],
      "cwd": "/path/to/GhostRigger-K1-K2",
      "env": {
        "K1_PATH": "/path/to/swkotor",
        "K2_PATH": "/path/to/swkotor2",
        "AGENTDECOMPILE_MCP_SERVER_URL": "http://170.9.241.140:8080/mcp/",
        "AGENTDECOMPILE_HTTP_GHIDRA_SERVER_HOST": "170.9.241.140",
        "AGENTDECOMPILE_HTTP_GHIDRA_SERVER_PORT": "13100",
        "AGENTDECOMPILE_HTTP_GHIDRA_SERVER_REPOSITORY": "Odyssey",
        "AGENTDECOMPILE_GHIDRA_USERNAME": "OpenKotOR",
        "AGENTDECOMPILE_GHIDRA_PASSWORD": "idekanymore"
      }
    },
    "agdec-proxy": {
      "type": "stdio",
      "command": "uvx",
      "args": [
        "--refresh", "--from",
        "git+https://github.com/bolabaden/AgentDecompile",
        "agentdecompile-proxy",
        "--mcp-server-url", "http://170.9.241.140:8080/mcp/"
      ],
      "env": {
        "AGENTDECOMPILE_PROJECT_PATH": "/projects/agentdecompile_projects/",
        "AGENTDECOMPILE_PROJECT_NAME": "Odyssey.gpr",
        "AGENTDECOMPILE_HTTP_GHIDRA_SERVER_HOST": "170.9.241.140",
        "AGENTDECOMPILE_HTTP_GHIDRA_SERVER_PORT": "13100",
        "AGENTDECOMPILE_HTTP_GHIDRA_SERVER_REPOSITORY": "Odyssey",
        "AGENTDECOMPILE_GHIDRA_USERNAME": "OpenKotOR",
        "AGENTDECOMPILE_GHIDRA_PASSWORD": "idekanymore"
      }
    }
  }
}
```

---

## Systems Architecture

The diagram below shows every major component, how they are layered, and all significant data flows between them.

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                         EXTERNAL CONSUMERS                                       ║
║                                                                                  ║
║   ┌──────────────────────┐    ┌─────────────────────────────────────────────┐   ║
║   │   Human User (GUI)   │    │         AI Assistant (Claude Desktop)        │   ║
║   │   python main.py     │    │   ghostrigger-kotor  │  agdec-proxy (stdio) │   ║
║   └──────────┬───────────┘    └──────────────┬────────────────┬─────────────┘   ║
╚══════════════╪══════════════════════════════╪════════════════╪═════════════════╝
               │ Tkinter events               │ MCP (stdio)    │ MCP (stdio→HTTP)
               │                              │                │
╔══════════════╪══════════════════════════════╪════════════════╪═════════════════╗
║              │     PRESENTATION LAYER       │                │                  ║
║   ┌──────────▼───────────────────────────┐  │                │                  ║
║   │              src/gui/                │  │                │                  ║
║   │  main_window.py  — Tkinter app shell │  │                │                  ║
║   │  viewport.py     — 3D rasteriser     │  │                │                  ║
║   │  gpu_renderer.py — ModernGL/PIL      │  │                │                  ║
║   │  blueprint_editor.py — UV editor     │  │                │                  ║
║   │  tex_atlas.py    — texture atlas     │  │                │                  ║
║   │  tpc_render_utils.py — TPC decode    │  │                │                  ║
║   │  accel.py        — fast rasterise    │  │                │                  ║
║   │  modular_panel.py— dockable panels   │  │                │                  ║
║   └──────────────────┬───────────────────┘  │                │                  ║
║                      │ IPC (HTTP :7001)      │                │                  ║
╚══════════════════════╪══════════════════════╪════════════════╪═════════════════╝
                       │                      │                │
╔══════════════════════╪══════════════════════╪════════════════╪═════════════════╗
║                      │    MCP LAYER         │                │                  ║
║            ┌─────────▼──────────────────────▼──────┐        │                  ║
║            │           src/kotormcp/                │        │                  ║
║            │                                        │        │                  ║
║            │  server.py ← MCP entry point           │        │                  ║
║            │    stdio / HTTP / SSE transports        │        │                  ║
║            │                                        │        │                  ║
║            │  tools/__init__.py                     │        │                  ║
║            │    Tool registry & dispatcher          │        │                  ║
║            │    43 tools across 10 groups:          │        │                  ║
║            │                                        │        │                  ║
║            │  ┌──────────────────────────────────┐  │        │                  ║
║            │  │  installation.py  (3 tools)       │  │        │                  ║
║            │  │  discovery.py     (4 tools)       │  │        │                  ║
║            │  │  gamedata.py      (3 tools)       │  │        │                  ║
║            │  │  ghostrigger.py   (5 tools)  ─────┼──┼──────►IPC client        ║
║            │  │  modules.py       (3 tools)       │  │        │  src/ipc/       ║
║            │  │  gffdata.py       (3 tools)       │  │        │  client.py      ║
║            │  │  decompile.py    (11 tools)  ─────┼──┼──────►HTTP :8080        ║
║            │  │  resource.py      (1 tool)        │  │        │                  ║
║            │  │  quest.py         (1 tool)        │  │        │                  ║
║            │  │  refs.py          (6 tools)       │  │        │                  ║
║            │  │  walkmesh.py      (1 tool)        │  │        │                  ║
║            │  │  archives.py      (2 tools)       │  │        │                  ║
║            │  └──────────────────────────────────┘  │        │                  ║
║            │                                        │        │                  ║
║            │  ports.py          ← abstract contracts│        │                  ║
║            │  adapters.py       ← pykotor knowledge │        │                  ║
║            │  adapters_decompile.py ← HTTP client   │        │                  ║
║            │  state.py          ← compat bridge     │        │                  ║
║            │  mcp_resources.py  ← kotor:// URIs     │        │                  ║
║            │  schemas/          ← input validation  │        │                  ║
║            │  utils/            ← json helpers      │        │                  ║
║            └──────────────┬─────────────────────────┘        │                  ║
╚═══════════════════════════╪══════════════════════════════════╪═════════════════╝
                            │ Python API calls                  │ uvx proxy
                            │                                   │ (native 39 tools)
╔═══════════════════════════╪═══════════════════════════════════╪═════════════════╗
║                           │    CORE PIPELINE LAYER            │                  ║
║   ┌───────────────────────▼─────────────────────────────┐     │                  ║
║   │                     src/core/                        │     │                  ║
║   │  mdl_parser.py    — binary + ASCII MDL/MDX parser    │     │                  ║
║   │  mdl_porter.py    — binary writer + K1↔K2 porter     │     │                  ║
║   │  model_data.py    — KotorModel / ModelNode dataclass │     │                  ║
║   │  animation_engine.py — keyframe interp + SLERP       │     │                  ║
║   │  game_library_ext.py — KEY/BIF/ERF/RIM reader        │     │                  ║
║   │  twoda.py         — 2DA format reader/writer         │     │                  ║
║   │  module_format.py — LYT/VIS/GFF module support       │     │                  ║
║   │  diagnostics.py   — model diagnostics + reporting    │     │                  ║
║   └─────────────────────────────────────────────────────┘     │                  ║
║                                                                 │                  ║
║   ┌─────────────────────────────────────────────────────┐     │                  ║
║   │               src/formats/                           │     │                  ║
║   │  gff_reader.py  — GFF binary format reader          │     │                  ║
║   │  gff_writer.py  — GFF binary format writer          │     │                  ║
║   │  gff_types.py   — GFF field type definitions        │     │                  ║
║   └─────────────────────────────────────────────────────┘     │                  ║
║                                                                 │                  ║
║   ┌─────────────────────────────────────────────────────┐     │                  ║
║   │               src/autorig/                           │     │                  ║
║   │  auto_rigger.py  — bone weight assignment            │     │                  ║
║   │  cloth_rig.py    — cloth/PBD physics simulation      │     │                  ║
║   │  accurig.py      — AccuRIG integration               │     │                  ║
║   │  grig.py         — geometry-based rig utilities      │     │                  ║
║   └─────────────────────────────────────────────────────┘     │                  ║
║                                                                 │                  ║
║   ┌─────────────────────────────────────────────────────┐     │                  ║
║   │               src/converters/                        │     │                  ║
║   │  mesh_converter.py — OBJ / GLTF 2.0 import/export   │     │                  ║
║   │  normal_map.py     — normal map generation           │     │                  ║
║   └─────────────────────────────────────────────────────┘     │                  ║
║                                                                 │                  ║
║   ┌─────────────────────────────────────────────────────┐     │                  ║
║   │               src/resources/                         │     │                  ║
║   │  game_library.py — archive/resource browser API     │     │                  ║
║   └─────────────────────────────────────────────────────┘     │                  ║
║                                                                 │                  ║
║   ┌─────────────────────────────────────────────────────┐     │                  ║
║   │               src/ipc/                               │     │                  ║
║   │  server.py — Flask IPC server (:7001)  ◄────────────┼─────┘ GUI bridge      ║
║   │  client.py — IPC client (:7002, :7003)              │                        ║
║   └─────────────────────────────────────────────────────┘                        ║
╚═════════════════════════════════════════════════════════════════════════════════╝
                            │
╔═══════════════════════════╪═════════════════════════════════════════════════════╗
║                           │    EXTERNAL DATA LAYER                               ║
║   ┌───────────────────────▼─────────────────────────────┐                       ║
║   │           KotOR Game Installation (local)            │                       ║
║   │  KEY/BIF — core game resources                       │                       ║
║   │  ERF/RIM — module archives                           │                       ║
║   │  TGA/TPC — textures                                  │                       ║
║   │  MDL/MDX — 3D models                                 │                       ║
║   │  2DA/TLK/GFF — game data tables                      │                       ║
║   │  (via pykotor >= 2.3.3)                              │                       ║
║   └─────────────────────────────────────────────────────┘                       ║
║                                                                                  ║
║   ┌─────────────────────────────────────────────────────┐                       ║
║   │     AgentDecompile Remote Server  :8080  (HTTP)      │                       ║
║   │  AgentDecompile v1.1.0 — MCP HTTP endpoint           │                       ║
║   │  39 native Ghidra tools (decompile, search, graph…)  │                       ║
║   │       │                                               │                       ║
║   │       ▼                                               │                       ║
║   │  Ghidra Shared Repository  :13100  (RMI)             │                       ║
║   │  "Odyssey" repo:                                      │                       ║
║   │    /K1/k1_win_gog_swkotor.exe  (K1, ~24 000 fns)    │                       ║
║   │    /K2/swkotor2.exe            (K2/TSL)              │                       ║
║   └─────────────────────────────────────────────────────┘                       ║
╚═════════════════════════════════════════════════════════════════════════════════╝
```

### Component Responsibilities

| Component | Responsibility |
|---|---|
| `src/gui/` | Tkinter application window, 3D viewport, GPU/CPU renderer, UV editor, texture utilities |
| `src/core/` | MDL/MDX binary + ASCII parser, binary writer, K1↔K2 porter, animation engine, KEY/BIF/ERF reader, 2DA/GFF/module format support |
| `src/formats/` | Low-level GFF binary reader/writer and type definitions |
| `src/autorig/` | Automatic bone weight assignment, cloth PBD physics simulation, AccuRIG integration |
| `src/converters/` | OBJ / GLTF 2.0 import and export, normal map generation |
| `src/resources/` | High-level archive/resource browser API |
| `src/ipc/` | Flask IPC server (:7001) bridging MCP tool calls to the live GUI viewport |
| `src/kotormcp/` | Embedded MCP server: 43 tools, Ports & Adapters architecture, AgentDecompile HTTP client |
| AgentDecompile :8080 | Remote Ghidra MCP backend; exposes 39 tools against analysed KotOR binaries |

### Data Flow — Model Render Request (MCP tool → PNG)

```
AI calls ghostrigger_render_model {resref, azimuth, elevation}
  │
  ▼
tools/ghostrigger.py  handle_render_model()
  │  resolves resref via CompositeModelLocator (filesystem → installation)
  │
  ▼
src/core/mdl_parser.py  MDLBinaryParser.parse_files()
  │  reads .mdl + .mdx bytes → KotorModel dataclass
  │
  ▼
src/gui/gpu_renderer.py  GpuRenderer  (force_cpu=True by default)
  │  ArcBallCamera.frame_bounds(bb_min, bb_max) → auto-framed camera
  │  ModernGL/EGL fast-path  OR  PIL FrameRenderer CPU fallback
  │
  ▼
audit_output/mcp_render_<resref>_<az>az_<el>el.png
  + JSON response {output_path, backend:"cpu"|"gpu"}
```

### Data Flow — Engine Function Decompile (MCP tool → C pseudocode)

```
AI calls kotor_decompile_function {game:"k1", function:"CResMan::LoadResourceMDL"}
  │
  ▼
tools/decompile.py  handle_decompile_function()
  │  resolves "k1" → "/K1/k1_win_gog_swkotor.exe" via KNOWN_PROGRAMS
  │
  ▼
adapters_decompile.py  AgentDecompileClient.decompile_function()
  │  MCP session init (JSON-RPC initialize)
  │  Ghidra credential headers injected (X-Ghidra-Server-*, Authorization)
  │  POST http://170.9.241.140:8080/mcp/  tools/call decompile-function
  │
  ▼
AgentDecompile server → Ghidra PyGhidra runtime
  │  checks out binary from shared repo
  │  runs Ghidra decompiler on named function
  │
  ▼
JSON response {decompilation: "void CResMan::LoadResourceMDL(...) {...}"}
```

### Ports & Adapters Coupling Diagram (KotorMCP internals)

```
  ┌────────────────────────────────────────────────────────────────────┐
  │                      tools/  (handlers)                            │
  │  installation  discovery  gamedata  ghostrigger  modules  gffdata  │
  │  decompile                                                         │
  └──────────┬─────────────────────────────────────────┬──────────────┘
             │ Contract Coupling                        │ Contract Coupling
             │ (port interfaces only)                   │ (client API only)
             ▼                                          ▼
  ┌──────────────────────┐              ┌───────────────────────────────┐
  │      ports.py        │              │    adapters_decompile.py      │
  │  InstallationPort    │              │    AgentDecompileClient       │
  │  ModelLocatorPort    │              │    (HTTP + MCP session)       │
  │  ModelParserPort     │              └───────────────┬───────────────┘
  │  InstallationRegistry│                              │ HTTP POST
  │  Port                │                              ▼
  │  ResourceEntry       │              ┌───────────────────────────────┐
  │  ModelInfo           │              │  AgentDecompile :8080         │
  │  AuditResult         │              │  (remote Ghidra server)       │
  └──────────┬───────────┘              └───────────────────────────────┘
             │ implements
             ▼
  ┌──────────────────────┐
  │     adapters.py      │
  │  InstallationAdapter │
  │  PyKotorRegistry     │
  │  Adapter             │
  │  FileSystemModel     │
  │  Locator             │
  │  InstallationModel   │
  │  Locator             │
  │  CompositeModel      │
  │  Locator             │
  │  MDLBinaryParser     │
  │  Adapter             │
  │  ModelAnalyzer       │
  └──────────┬───────────┘
             │ calls
             ▼
  ┌──────────────────────┐
  │   pykotor >= 2.3.3   │
  │   (volatile external │
  │    dependency —      │
  │    isolated here)    │
  └──────────────────────┘
```

---

## KotorMCP Tool Reference

**43 tools** registered across 10 groups. All accessible via stdio, HTTP, or SSE.

### Installation (3 tools)

| Tool | Description |
|---|---|
| `detectInstallations` | Auto-discover K1/K2 install paths from env vars and platform defaults |
| `loadInstallation` | Activate a KotOR installation for subsequent tool calls |
| `kotor_installation_info` | Return path, game, module count, override resource count |

### Resource Discovery (4 tools)

| Tool | Description |
|---|---|
| `listResources` | Browse resources across override/core/modules/chitin with pagination |
| `describeResource` | Describe a specific resource (GFF summary, 2DA headers, etc.) |
| `kotor_find_resource` | Full-text search for a resource by name or pattern |
| `kotor_search_resources` | Regex-filtered resource listing across all locations |

### Game Data (3 tools)

| Tool | Description |
|---|---|
| `journalOverview` | Summarise all plot categories and quests from `global.jrl` |
| `kotor_lookup_2da` | Query any 2DA table by row, column, or value search |
| `kotor_lookup_tlk` | Resolve a TLK string reference number to display text |

### Modules (3 tools)

| Tool | Description |
|---|---|
| `kotor_list_modules` | List all `.rim` / `.erf` modules in an installation |
| `kotor_describe_module` | Describe a module: area name, layout, GIT summary |
| `kotor_module_resources` | List all resources inside a specific module |

### Deep Read (3 tools)

| Tool | Description |
|---|---|
| `kotor_read_gff` | Read any GFF (UTC, UTP, UTD, DLG, ARE, IFO…) as structured JSON |
| `kotor_read_2da` | Read a 2DA table as row slices with optional column filter |
| `kotor_read_tlk` | Read a range of TLK string refs with optional text search |

### GhostRigger Model (5 tools)

| Tool | Description |
|---|---|
| `ghostrigger_open_model` | Open an MDL in the live viewport via IPC |
| `ghostrigger_render_model` | Render an MDL to PNG at any azimuth/elevation |
| `ghostrigger_model_info` | Node count, mesh stats, bones, bbox, classification |
| `ghostrigger_list_game_models` | Enumerate all MDL resources in an installation |
| `ghostrigger_audit` | Integrity check: UV/normal mismatches, empty faces, bbox |

### AgentDecompile / Ghidra Engine Analysis (11 tools)

Backed by remote Ghidra server at `http://170.9.241.140:8080/mcp/`. No local Ghidra needed.

| Tool | Description |
|---|---|
| `kotor_binary_ping` | Health-check the AgentDecompile backend |
| `kotor_binary_info` | Binary metadata: language, compiler, function count |
| `kotor_list_engine_funcs` | Page through 24 000+ functions in `swkotor.exe` / `swkotor2.exe` |
| `kotor_decompile_function` | Decompile a named or addressed engine function to C pseudocode |
| `kotor_search_symbols` | Search functions, globals, and labels by name substring |
| `kotor_search_engine_strings` | Search hardcoded string literals in the binary |
| `kotor_get_references` | Find all callers (`to`) or callees (`from`) of a function |
| `kotor_call_graph` | Call graph around a function at configurable depth |
| `kotor_data_flow` | Trace P-code data flow backward/forward from an address |
| `kotor_inspect_memory` | Inspect memory layout, raw bytes, or typed data at an address |
| `kotor_engine_script` | Execute arbitrary Python/PyGhidra against the loaded binary |

### Composite / High-Level (2 tools)

| Tool | Description |
|---|---|
| `get_resource` | Universal resource accessor: returns decoded content (GFF JSON, 2DA rows, TLK entries, MDL summary, NSS source, NCS stub, or base64) for any (game, resref, restype) triple |
| `get_quest` | Composite quest inspector: single Markdown doc with JRL resource, plot number, all journal states (TLK-resolved), referenced scripts, and DLG node excerpts |

### References & Plot (6 tools)

| Tool | Description |
|---|---|
| `kotor_list_references` | List outbound references (scripts, conversations, tags, template resrefs) from any GFF resource |
| `kotor_find_referrers` | Find all resources that reference a given script resref, tag, conversation, or resref |
| `kotor_find_strref_referrers` | Find all resources that use a given TLK string reference ID |
| `kotor_describe_dlg` | DLG structure summary: entry/reply counts, script refs, conversation refs |
| `kotor_describe_jrl` | JRL (journal) summary: category count, entry count |
| `kotor_describe_resource_refs` | Generic GFF reference summary for any resource type |

### Walkmesh (1 tool)

| Tool | Description |
|---|---|
| `kotor_walkmesh_validation_diagram` | Plain-text validation diagram for a BWM/WOK walkmesh: perimeter, transitions, outer boundary |

### Archives (2 tools)

| Tool | Description |
|---|---|
| `kotor_list_archive` | List contents of a KEY/BIF/RIM/ERF/MOD archive with pagination |
| `kotor_extract_resource` | Extract a resolved resource to a validated disk path *(writes to disk)* |

---

## Example MCP Session

```python
# 1. Load K1 installation
await handle_tool('loadInstallation', {'game': 'k1', 'path': '/games/swkotor'})

# 2. Find Sith models
await handle_tool('ghostrigger_list_game_models', {'game': 'k1', 'filter': 'sith', 'limit': 20})
# → l_sithoff_f, l_sithoff_m, n_sithpraet, n_sithcomm ...

# 3. Inspect model
await handle_tool('ghostrigger_model_info', {'resref': 'n_sithpraet'})
# → 82 nodes, 63 mesh nodes, 6,083 vertices, supermodel S_Female02

# 4. Audit integrity
await handle_tool('ghostrigger_audit', {'resref': 'n_sithpraet'})
# → 26 UV-count mismatches on skin/helper nodes

# 5. Render multi-angle preview
await handle_tool('ghostrigger_render_model', {'resref': 'n_sithpraet', 'azimuth': 45, 'elevation': 25})
# → audit_output/mcp_render_n_sithpraet_45az_25el.png  (CPU backend)

# 6. Cross-reference with 2DA and GFF
await handle_tool('kotor_lookup_2da', {'game': 'k1', 'table_name': 'appearance',
                                        'column': 'label', 'value_search': 'sith'})
await handle_tool('kotor_read_gff', {'game': 'k1', 'resref': 'n_sithpraet', 'restype': 'utc'})

# 7. Check engine binary analysis backend
await handle_tool('kotor_binary_ping', {})
# → {"status": "ok", "server_url": "http://170.9.241.140:8080/mcp", ...}

# 8. Find MDL loader in binary
await handle_tool('kotor_search_symbols', {'game': 'k1', 'query': 'MDL'})
# → CResMan::LoadResourceMDL, CMDLObject::Load, CMDLMesh::Render, ...

# 9. Decompile it
await handle_tool('kotor_decompile_function',
    {'game': 'k1', 'function': 'CResMan::LoadResourceMDL'})
# → Full Ghidra C pseudocode: struct header parsing, node-offset resolution, ...

# 10. Trace callers
await handle_tool('kotor_get_references',
    {'game': 'k1', 'address_or_symbol': 'CResMan::LoadResourceMDL', 'direction': 'to'})
# → CMDLObject::Load, CScene::AddRenderable, CAreaLoader::LoadArea, ...
```

---

## Project Structure

```
GhostRigger-K1-K2/
│
├── main.py                         — GUI entry point
├── claude_desktop_config.json      — Ready-to-use Claude Desktop MCP config
├── AGENTDECOMPILE_INTEGRATION.md   — AgentDecompile usage plan (6 workflows)
├── build.bat                       — Windows EXE build script
│
├── src/
│   ├── core/                       — MDL/MDX pipeline (parser, porter, animation)
│   │   ├── mdl_parser.py           MDLBinaryParser, MDLASCIIParser
│   │   ├── mdl_porter.py           CrossGamePorter, MDLBinaryWriter
│   │   ├── model_data.py           KotorModel, ModelNode, SkinMesh, etc.
│   │   ├── animation_engine.py     AnimController, SLERP interpolation
│   │   ├── game_library_ext.py     KEY/BIF/ERF/RIM archive reader
│   │   ├── twoda.py                TwoDA reader/writer
│   │   ├── module_format.py        LYT/VIS/GFF module support
│   │   └── diagnostics.py          Model diagnostics + reporting
│   │
│   ├── gui/                        — Tkinter application + renderers
│   │   ├── main_window.py          Application shell, Library panel, menus
│   │   ├── viewport.py             3D software rasteriser (FrameRenderer)
│   │   ├── gpu_renderer.py         GpuRenderer (ModernGL/EGL + PIL fallback)
│   │   ├── blueprint_editor.py     UV / blueprint editor panel
│   │   ├── tex_atlas.py            Texture atlas builder
│   │   ├── tpc_render_utils.py     TPC/TXI texture decode utilities
│   │   ├── accel.py                Accelerated triangle rasterisation
│   │   └── modular_panel.py        Dockable panel system
│   │
│   ├── autorig/                    — Rigging and physics
│   │   ├── auto_rigger.py          Automatic bone weight assignment
│   │   ├── cloth_rig.py            Cloth/PBD physics simulation
│   │   ├── accurig.py              AccuRIG integration
│   │   └── grig.py                 Geometry-based rig utilities
│   │
│   ├── converters/                 — Import / export
│   │   ├── mesh_converter.py       OBJ / GLTF 2.0 import + export
│   │   └── normal_map.py           Normal map generation
│   │
│   ├── formats/                    — Binary format codecs
│   │   ├── gff_reader.py           GFF binary reader
│   │   ├── gff_writer.py           GFF binary writer
│   │   └── gff_types.py            GFF field type definitions
│   │
│   ├── ipc/                        — GUI ↔ MCP bridge
│   │   ├── server.py               Flask IPC server (port 7001)
│   │   └── client.py               IPC client (ports 7002, 7003)
│   │
│   ├── resources/                  — Archive browser
│   │   └── game_library.py         High-level resource browser API
│   │
│   └── kotormcp/                   — Embedded MCP server (v3.4)
│       ├── __main__.py             python -m src.kotormcp entry point
│       ├── server.py               MCP server (stdio / HTTP / SSE)
│       ├── ports.py                Abstract port contracts (4 ports, 3 DTOs)
│       ├── adapters.py             Concrete implementations + pykotor isolation
│       ├── adapters_decompile.py   AgentDecompileClient HTTP adapter
│       ├── state.py                Backward-compatible bridge layer
│       ├── mcp_resources.py        kotor:// URI templates + resource readers
│       ├── schemas/                Input validation models (Pydantic / fallback)
│       ├── utils/                  json_content helper, output formatting
│       └── tools/                  32 tool handlers across 7 modules
│           ├── __init__.py         Tool registry & dispatcher
│           ├── installation.py     3 tools: detect / load / info
│           ├── discovery.py        4 tools: list / describe / find / search
│           ├── gamedata.py         3 tools: journal / 2da / tlk
│           ├── ghostrigger.py      5 tools: open / render / info / list / audit
│           ├── modules.py          3 tools: list / describe / resources
│           ├── gffdata.py          3 tools: read_gff / read_2da / read_tlk
│           └── decompile.py       11 tools: AgentDecompile / Ghidra bridge
│
├── tests/                          — 2,443+ tests across 58 files, 0 failures
│   │
│   ├── — Core MCP & Architecture —
│   ├── test_agentdecompile_bridge.py     53  AgentDecompile client + handlers
│   ├── test_kotormcp_integration.py      39  Full MCP stack, tools, URI parsing
│   ├── test_kotormcp_architecture.py     39  Ports, adapters, ModelAnalyzer
│   ├── test_gff_roundtrip.py             42  GFF binary read/write round-trips
│   ├── test_gimbal_viewport.py           19  3D gimbal math, skeleton ops
│   ├── test_mdl_parser.py                23  Binary MDL parsing + cloth rig
│   ├── test_rendering_fixes.py           46  UV wrapping, normals, cloth sim
│   ├── test_tpc_tpa_texture_loading.py   27  ERF TPA > TPB > TPC priority
│   ├── test_ipc_server.py                14  (skipped: requires Flask + :7001)
│   │
│   ├── — Versioned Regression Suite (v13 → v200) —
│   ├── test_v33_comprehensive.py        138
│   ├── test_v31_animation.py            105
│   ├── test_v70_texture_txi_uv_improvements.py  99
│   ├── test_v31_animation_engine.py      94
│   ├── test_v29_rigging_rendering.py     89
│   ├── test_v160_deep_audit.py           89
│   ├── test_v51_regression.py            86
│   ├── test_v45_mdl_crash_fixes.py       81
│   ├── test_v100_gpu_renderer.py         72
│   ├── test_v30_pipeline_fixes.py        70
│   ├── test_v90_anim_uv_material_fixes.py 69
│   ├── test_v130_uv_texture_pipeline.py  67
│   ├── test_v28_fixes.py                 63
│   ├── test_v105_perf_improvements.py    61
│   ├── test_v14_deep_audit_unknowns.py   56
│   ├── test_v46_full_crash_audit.py      55
│   ├── test_v150_binary_mdl_harness.py   51
│   ├── test_v29_cloth_rigging.py         50
│   ├── ... (32 additional versioned files)
│   └── conftest.py / render_quality_test.py
│
├── test_assets/                    — Sample MDL/MDX/TGA (N_sithpraet, etc.)
├── game_data/                      — Extracted K1 BIF/RIM/ERF (not committed)
└── audit_output/                   — PNG renders from ghostrigger_render_model
```

---

## GPU Renderer Notes

The `GpuRenderer` (`src/gui/gpu_renderer.py`) provides a **hybrid render path**:

- **GPU fast-path**: ModernGL + EGL headless context. ~1 ms/frame for typical 10k-tri models. Requires `pip install moderngl`. Not available in CI without a display.
- **CPU fallback**: PIL-based triangle rasteriser (`FrameRenderer`). Always available. ~300 ms/frame. Used automatically when ModernGL is absent, EGL fails, or `force_cpu=True`.

The MCP `ghostrigger_render_model` tool uses `force_cpu=True` by default (headless-safe). The camera is auto-framed from the model bounding box via `ArcBallCamera.frame_bounds()`. The response includes `"backend": "cpu"` or `"backend": "gpu"`.

---

## MDL/MDX Format Notes

GhostRigger implements a from-scratch binary MDL/MDX parser based on research from [xoreos](https://github.com/xoreos/xoreos), [KotorBlender](https://github.com/seedhartha/kotorblender), [PyKotor](https://github.com/NickHugi/PyKotor), [MDLOps](https://github.com/ndixUR/mdlops), and [DeadlyStream](https://deadlystream.com).

### MDX Bitmap Flags

| Bit | Flag | Bytes |
|-----|------|-------|
| 0x0001 | VERTEX | 12 — XYZ positions |
| 0x0002 | UV1 | 8 — Texture0 UV |
| 0x0004 | UV2 | 8 — Texture1/lightmap UV |
| 0x0008 | UV3 | 8 — Texture2 UV (rare) |
| 0x0010 | UV4 | 8 — Texture3 UV (rare) |
| 0x0020 | NORMAL | 12 — Vertex normals |
| 0x0040 | COLOR | 4 — Vertex RGBA |
| 0x0080 | TANGENT1 | 36 — Tangent-space Tex0 |
| 0x0100 | TANGENT2 | 36 — Tangent-space Tex1 |
| 0x0200 | TANGENT3 | 36 — Tangent-space Tex2 |
| 0x0400 | TANGENT4 | 36 — Tangent-space Tex3 |

---

## Running Tests

```bash
pip install pytest
pytest tests/
# 2,623+ tests collected — 0 failures
```

Tests run without any game files. Installation-dependent tests skip automatically unless `K1_PATH` / `K2_PATH` are set. IPC tests skip without Flask on port 7001. All AgentDecompile bridge tests are fully offline (network calls are mocked).

**Fast CI (excludes slow model-asset tests):**

```bash
pytest tests/ \
  --ignore=tests/test_v46_full_crash_audit.py \
  --ignore=tests/test_v200_pykotor_gltf_alpha.py -q
# ~2,400 tests, ~45s
```

**Key rendering test suites:**

```bash
pytest tests/test_v210_phase2_rendering.py     # 68 tests  — Phase 2 env-map, supermodel
pytest tests/test_v220_phase3_creature_anim.py # 61 tests  — Phase 3 creature + animation
pytest tests/test_v230_envmap_txi_rendering.py # 56 tests  — Phase 3.5 TXI / env-map
pytest tests/test_v240_phase36_alpha_txi.py    # 40 tests  — Phase 3.6 alpha-test
pytest tests/test_v250_phase37_k2_fields_avgpoint.py  # 47 tests  — Phase 3.7 K2 fields + avg point
```

**Other key suites:**

```bash
pytest tests/test_agentdecompile_bridge.py   # 53 tests — AgentDecompile bridge
pytest tests/test_kotormcp_integration.py    # 39 tests — MCP tools + URIs
pytest tests/test_kotormcp_architecture.py   # 39 tests — ports / adapters
pytest tests/test_gff_roundtrip.py           # 42 tests — GFF read/write
pytest tests/test_mdl_parser.py              # 23 tests — binary MDL parsing
pytest tests/test_rendering_fixes.py         # 46 tests — renderer/UV/cloth
pytest tests/test_tpc_tpa_texture_loading.py # 27 tests — texture priority
```

---

## Changelog

### v3.6 — Phase 3.6 Per-Node Alpha-Test Threshold (2026-03-18)

- **FIX-ALPHATEST**: GPU renderer now uses per-node alpha-test threshold from TPC header [4-7]
  instead of hardcoded 0.5. New functions: `_extract_alpha_test_from_tpc()`,
  `TextureCache.get_raw_header()`. New field: `ModelNode.txi_alpha_test`.
- **UI assessment**: Evaluated Qt/qtpy migration suggestion — declined (project uses Tkinter).
- **Research**: Confirmed Kotor.NET `KotorModelLoader.cs` mesh layout, PyKotor `gl/shader/texture.py`
  `Texture.alpha_cutoff` field, xoreos TPC header structure.
- **Tests**: +40 tests in `test_v240_phase36_alpha_txi.py`. Total: 2,623 passing.

**v3.7 (2026-03-18):**
- **K2 Dirt/Hologram fields**: `hide_in_holograms`, `dirt_enabled`, `dirt_texture`, `dirt_coord_space` now parsed and stored from K2/TSL mesh headers.
- **Mesh AveragePoint**: `mesh_average_point` stored from TrimeshHeader; GPU renderer uses it for accurate transparent-surface depth sorting.
- **Tests**: +47 tests in `test_v250_phase37_k2_fields_avgpoint.py`. Total: 2,670 passing.

### v3.5 — Recursive Supermodel + Env-Map Fixes (2026-03-18)

- **FIX-4 Recursive bone injection**: `_deep_copy_subtree()` replaces flat copy.
- **FIX-1/2/3**: bumpyshinytexture alias, BlendedOver formula, final alpha for env surfaces.
- **Tests**: +75 tests (TXI/env-map) + 2 (supermodel). Total: 185 passing.

- **`walkmesh.py`** — Pass raw bytes directly to `read_bwm()` (its actual type signature, not `BytesIO` wrapper); strip both `.wok` **and** `.bwm` suffixes from resref; prepend `# stats: N faces, M walkable, P perimeter edges` header to give LLMs quick numeric context.
- **`refs.py`** — All error paths now use `_err(msg)` helper that calls `json.dumps({"error": msg})`, making error responses JSON-safe even when exception messages contain `"` or `\` characters (previous f-string interpolation pattern was fragile).  Added `case_sensitive` parameter to `kotor_find_referrers` (PyKotor's `find_referrers()` has supported it).  Changed `file_type` derivation to use `restype.name.upper()` instead of `restype.extension.upper()` for consistency.
- **`schemas/__init__.py`** — `FindReferrersInput` gains `case_sensitive: bool = False` field.
- **`tests/test_v34_refs_walkmesh_archives.py`** — 16 new tests in `TestWalkmeshToolModule` and `TestV341Improvements` class: extension stripping, JSON safety, schema fields, `_err` helper contract.  **160 total tests passing** (was 151 in v3.4).

### v3.4 — Full Upstream Parity + Monorepo Audit

- **`src/kotormcp/tools/refs.py`** — 6 new reference tools ported from upstream `OldRepublicDevs/KotorMCP`: `kotor_list_references`, `kotor_find_referrers`, `kotor_find_strref_referrers`, `kotor_describe_dlg`, `kotor_describe_jrl`, `kotor_describe_resource_refs`. Adapted to GhostRigger's port-contract layer (no common-coupling to global state).
- **`src/kotormcp/tools/walkmesh.py`** — 1 new tool ported from upstream: `kotor_walkmesh_validation_diagram`. Returns text validation diagram (perimeter, transitions, outer boundary) for any BWM/WOK resource.
- **`src/kotormcp/tools/archives.py`** — 2 new tools ported from upstream: `kotor_list_archive` (KEY/BIF/RIM/ERF/MOD listing with pagination), `kotor_extract_resource` (first write-capable tool — extracts resource to validated disk path).
- **`src/kotormcp/utils/formatting.py`** — Fixed circular import (`utils/__init__.py` ↔ `utils/formatting.py`): implementation now lives in `formatting.py`, `__init__.py` re-exports.
- **`tests/test_v34_refs_walkmesh_archives.py`** — 40 offline tests covering tool definitions, handler error paths, result format compliance, and registry dispatch for all 9 new tools.
- Registry expanded to **43 tools** (was 34): full upstream KotorMCP parity plus GhostRigger-exclusive tools (3D model pipeline, AgentDecompile bridge, composite tools).
- **Monorepo alignment**: All 25 upstream KotorMCP tools now present in GhostRigger's embedded KotorMCP. GhostScripter-K1-K2 and GModular confirmed as submodules in `Tools/` of the `OldRepublicDevs/PyKotor` monorepo.

### v3.3 — Composite Tools + System Design (Constantine / Khononov)

- **`src/kotormcp/tools/resource.py`** — `get_resource`: universal context-free resource accessor. Accepts (game, resref, restype) and returns decoded content — GFF JSON tree, 2DA rows, TLK entries, MDL structural summary, NCS hex stub, NSS source, or base64 binary. Nine decoders registered at module load; adding a new format requires only one new function (open/closed principle).
- **`src/kotormcp/tools/quest.py`** — `get_quest`: composite quest inspector. Accepts (game, tag) and returns a single Markdown document containing the JRL resource, quest plot number, all journal states with TLK-resolved text, referenced scripts (NSS source or NCS stub), and DLG node excerpts referencing the quest tag. Structured as a textbook Constantine Chapter 9 transform hierarchy.
- **`tests/test_v33_composite_tools.py`** — 33 offline tests covering schema validation (context-free naming, required fields), registry integration (no duplicates), handler error paths, and the `_extract_path` helper.
- **`SYSTEM_DESIGN.md`** — Comprehensive systems design document: IPC architecture diagram, gap analysis, coupling/cohesion profile table, Constantine transform analysis for `get_quest`, recommended canonical tool naming convention (verb_noun, no app prefix), 5 proposed next tools (get_character, get_item, patch_resource, compile_script, get_module_summary), IPC protocol fixes, and a context analysis table showing how the same tools serve Discord, VS Code, CI/CD, and modder contexts without modification.
- Registry expanded to 34 tools (was 32).
- Fixed `asyncio.get_event_loop()` → `asyncio.run()` in `test_kotormcp_integration.py` and `test_kotormcp_architecture.py` for Python 3.12 compatibility.

### v3.2 — AgentDecompile / Ghidra Engine Bridge

- **`src/kotormcp/adapters_decompile.py`** — `AgentDecompileClient` HTTP adapter: MCP session management, Ghidra credential headers, per-method high-level API
- **`src/kotormcp/tools/decompile.py`** — 11 tool handlers for engine binary analysis
- **`tests/test_agentdecompile_bridge.py`** — 53 fully-offline tests; fixed missing `_patch_client()` helper (was causing 28 `NameError` failures)
- **`claude_desktop_config.json`** — Both `ghostrigger-kotor` and `agdec-proxy` server entries
- **`AGENTDECOMPILE_INTEGRATION.md`** — 6 engine research workflows
- Registry expanded to 34 tools; both `AGENTDECOMPILE_*` and `AGENT_DECOMPILE_*` env prefixes supported

### v3.1 — Deep Audit & Tool Hardening

- `ghostrigger_render_model`: fixed import (`CPURenderer` → `GpuRenderer`), `sys.path` bootstrap, auto-framed camera, `force_cpu=True`, output path sanitisation, `backend` field in response
- `gamedata.py` port-contract compliance: `talktable_string()`, `get_resource()` helpers, `get_cell()` with exception handling, optional `path` arg

### v3.0 — Ports & Adapters Architecture

- `ports.py` — 4 abstract contracts + 3 stable data DTOs
- `adapters.py` — pykotor/filesystem knowledge isolated; `PyKotorRegistryAdapter`, `ModelAnalyzer`, `CompositeModelLocator`
- 6 new tools: `kotor_list_modules`, `kotor_describe_module`, `kotor_module_resources`, `kotor_read_gff`, `kotor_read_2da`, `kotor_read_tlk`

### v2.9 — KotorMCP Integration

- Embedded MCP server with 15 initial tools; stdio / HTTP / SSE transports
- PyKotor 2.3.3 integration; Flask IPC bridge on port 7001

### v2.8 — Rendering & Audit Fixes

- Envmap alpha channel fix; skin mesh normal correction; deformation helper filter

### v2.7 — PyKotor Integration & GLTF Export (public release)

- PyKotor archive reading; GLTF 2.0 round-trip; alpha-kill readback

### Earlier (v1.x – v2.6)

Binary MDL/MDX parser, ASCII round-trip, K1↔K2 porter, 3D viewport, GPU renderer, cloth PBD simulation, texture priority pipeline, GFF/2DA read/write, auto-rigger

---

## Known Limitations

| Limitation | Notes |
|---|---|
| GPU renderer requires EGL | Falls back to CPU/PIL automatically; `force_cpu=True` always works |
| IPC tests skipped in CI | Requires Flask + live port 7001 |
| `ghostrigger_list_game_models` slow on large installs | Enumerates all chitin BIF resources; use `kotor_search_resources` with a filter |
| `kotor_lookup_2da` first call ~10 s | Pykotor BIF key parsing uncached between calls; subsequent calls on same installation are faster |
| Character models render untextured | Textures live in the supermodel (e.g. `S_Female02`); supermodel texture loading is a planned enhancement |
| TLK `talktable_string` parse errors on some entries | Pykotor returns raw error string rather than crashing |
| Ghidra RMI credentials (`OpenKotOR`) | Port 13100 rejects the shared credentials; `kotor_binary_*` tools work via the HTTP :8080 backend; `checkout-program` from the shared repo is not currently available |

---

## Contributing

Issues, PRs, and format research are welcome.

When contributing to `src/kotormcp/`:
- Tool handlers in `tools/` must only import from `ports.py`, `state.py`, `utils/`, `schemas/`, and the relevant `adapters*.py`
- All pykotor API calls belong in `adapters.py`
- All HTTP/external API calls belong in `adapters_*.py`
- Every new handler needs an entry in `tools/__init__.py` (`get_all_tools` + `handle_tool`)
- AgentDecompile bridge tests must be fully offline (`MockClient`, no live network)

---

## Windows EXE Build

```
double-click build.bat
```

Produces `dist/GhostRigger-K1-K2.exe` (portable, no Python install needed).

---

## License

MIT License — see [LICENSE](LICENSE).

Star Wars: Knights of the Old Republic and The Sith Lords are property of LucasArts / Lucasfilm / Disney / Aspyr / Obsidian Entertainment. Game data files are not included in this repository.
