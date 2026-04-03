# GhostRigger – KotOR 1 & 2 Model Viewer & Pipeline

> **Odyssey Engine Pipeline** — A full-featured 3D model viewer, converter, auto-rigger,
> and modding toolkit for *Star Wars: Knights of the Old Republic* (K1) and
> *The Sith Lords* (K2 / TSL).

![GhostRigger v5.5 UI – Phase 18](render_check/ghostrigger_phase18_final.png)

*Above: Phase 18 UI — dark theme · library panel with category icons · 3-D viewport
with walkmesh overlay · skeleton tree · 2DA/GFF resource browser · status bar.*

---

## Latest Release — v5.5 (2026-04-03) · Phase 18 — UI Cleanup & PyKotor Integration

| Area | What's new |
|------|-----------|
| **Test suite** | **4 372 tests passing**, 11 skipped, 0 failures (117 s on CPython 3.12) |
| **Status bar** | Live model info: game tag · mesh count · anim count · renderer mode |
| **Library panel** | Category emoji tabs (🐲 Cre / 👤 Chr / 🗡 Itm / 🏛 Mod) · colour-coded K1/K2 rows · `Ctrl+F` search focus · `Ctrl+L` library focus |
| **Viewport HUD** | Model-name badge · shade-mode badge · axis gizmo (X/Y/Z) · FPS/render-time counter · walkmesh walkable/blocked legend |
| **ResourceManager** | `pykotor` ResourceManager is the **primary** backend; `KotorInstallation` is fallback only |
| **2DA viewer** | `pykotor.resource.formats.twoda.read_2da` primary · internal reader fallback · TSV/CSV export |
| **GFF viewer** | Full PyKotor struct/list/field tree with recursion-depth guard |
| **Keyboard shortcuts** | `Ctrl+F` focus search · `F3` model info · `F5` refresh-all · tooltip card in Props panel |

### Version history

| Version | Date | Highlights |
|---------|------|-----------|
| **v5.5** | 2026-04-03 | Two-pass depth sort · LBS explosion guard tightened (50 → 8 units) · Phase 18 UI cleanup · 4 372 tests |
| v5.4 | 2026-03-xx | Legacy TPC decoder · PyKotor TPC primary pipeline |
| v5.3 | 2026-03-xx | Binary MDL writer · ASCII round-trip fixes |
| v5.2 | 2026-03-xx | GPU renderer (ModernGL) · multi-room scene preview |
| v5.0 | 2026-02-xx | Full PyKotor MDL/TPC/Anim integration · Phase 14 bridge |
| v4.x | 2026-01-xx | Auto-rig v2 · cloth rigging · IPC / GhostRigger MCP server |

---

## Quick-start

```bash
# Clone & install
git clone https://github.com/CrispyW0nton/Kotor-3D-Model-Converter.git
cd Kotor-3D-Model-Converter
pip install -e ".[gui,kotor]"

# Launch GUI
python main.py
# or
python -m src.gui.main_window
```

**Requirements:** Python 3.10 +, Pillow, NumPy, Tkinter (bundled with most Python installs).  
**Optional (strongly recommended):** `pykotor` for native TPC / GFF / 2DA reading — place the
`PyKotor` source tree at `../PyKotor/` relative to the repo root, or install via pip.

---

## Features

### 🖼  3D Viewer & Viewport
- CPU-based PIL renderer with **two-pass depth sorting** and LBS linear-blend skinning
- Bone skeleton overlay with joint spheres and limb lines (toggle `B`)
- Wireframe / solid / textured / both display modes (toggle `W`, `T`)
- **WalkMesh triangle overlay** (`.wok` files) with walkable / blocked colour coding
- Gimbal manipulator (Translate / Rotate / Scale) with `Tab`-cycle
- UV editor panel
- FPS / render-time HUD badge · axis gizmo (X red / Y green / Z blue)
- Frame-all (`F`), zoom (`+` / `-`), orbit (LMB drag), pan (MMB drag)

### 📚  Game Library
- **Auto-detection** of K1 and K2 installation paths (Windows · Linux/Steam · macOS · GOG)
- Category tabs: All · 🐲 Creature · 👤 Character · 🗡 Item/Armor · 🏛 Module · Other
- Live search with `Ctrl+F` focus · Game filter All / K1 / K2
- Module-area filter for `.mod` scenes
- Thumbnail strip with pre-rendered PNG previews
- Batch export (OBJ / ASCII MDL / TGA)

### ⚙  Auto-Rig (`R` / `Ctrl+R`)
- Aurora-compatible skeleton generation
- Supermodel inheritance (`S_Female02`, `S_Male02`, etc.)
- Bone-map remapping for K1 ↔ K2 skeletons
- LBS weight painting with explosion guard (< 8-unit clamp)

### 🔀  K1 ↔ K2 Conversion
- Node-type translation (trimesh, skin, danglymesh, emitter …)
- Texture reference rewriting · supermodel chain update
- Animation curve baking / retargeting

### 🧥  Cloth Rigging
- Danglymesh presets (robe, cape, hair, lekku)
- Per-node period / tightness / displacement parameters
- Cloth panel with live preview

### 📦  MDLOps Bridge
- Compile / decompile via MDLOps (Perl or native binary)
- ASCII MDL round-trip save (`Ctrl+S`)
- **glTF 2.0 export** (`Ctrl+G`) with skin weights

### 📋  Resource Browser
- 2DA table viewer: sort · row-search · TSV/CSV export — **PyKotor primary**
- GFF struct / field tree viewer — **PyKotor primary** with depth guard
- `.rim` / `.erf` / `.mod` container browsing

### 🛠  Model Diagnostics
- Per-node warnings: missing textures · bad UVs · zero-area faces
- Skin-mesh bone-map validation
- Animation curve completeness check

### 🌐  IPC / MCP Server
- GhostRigger JSON-RPC server for external tool integration
- `ping` · `refresh_viewport` · `get_model_info` · `apply_rig` commands
- Notification bus for GModular / ZBrush bridge

---

## Project structure

```
src/
├── core/
│   ├── mdl_parser.py        # Binary MDL reader (Aurora engine format)
│   ├── mdl_writer.py        # Binary MDL writer
│   ├── model_data.py        # In-memory model graph
│   ├── animation_engine.py  # Animation curve interpolation
│   ├── pykotor_bridge.py    # PyKotor MDL/TPC/Anim adapter
│   └── resource_manager.py  # Unified K1/K2 resource lookup
├── gui/
│   ├── main_window.py       # Tkinter main window (16 800+ lines)
│   ├── viewport.py          # CPU PIL renderer + GPU renderer (8 700+ lines)
│   └── tpc_utils.py         # TPC ↔ PIL conversion helpers
├── autorig/
│   └── autorig.py           # Aurora skeleton auto-rigging
├── converters/
│   └── mesh_converter.py    # Mesh geometry utilities
└── kotormcp/
    └── mcp_server.py        # JSON-RPC IPC server

tests/                       # 4 372 tests across 65 files
render_check/                # UI mockup renders (PIL-generated)
audit_output/                # Batch render / diagnostic output
```

---

## Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Phase-specific suites
pytest tests/test_v58_phase17_ui_polish.py tests/test_v58_phase17_ui_pykotor.py
pytest tests/test_v59_phase18_ui_cleanup.py

# Current counts
# 4372 passed, 11 skipped, 0 failures  (Python 3.12, ~118 s)
```

---

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+O` | Open MDL (binary) |
| `Ctrl+I` | Import OBJ |
| `Ctrl+E` | Export OBJ |
| `Ctrl+G` | Export glTF |
| `Ctrl+S` | Save ASCII MDL |
| `Ctrl+W` | Clear model |
| `R` | Auto-rig |
| `Ctrl+D` | Diagnostics tab |
| `Ctrl+A` | Animations tab |
| `Ctrl+P` | Properties tab |
| `Ctrl+F` | Focus library search |
| `Ctrl+L` | Focus library panel |
| `F` | Frame all |
| `F1` | About |
| `F2` | Settings |
| `F3` | Model info |
| `F5` | Refresh all |
| `B` | Toggle bones |
| `T` | Toggle texture |
| `W` | Wireframe |
| `G` | Gimbal |
| `Tab` | Cycle gimbal mode |
| `Esc` | Deselect |

---

## Roadmap

### 🔧 In progress

| Issue | Status |
|-------|--------|
| **CaloNord `usecomp` animation** — head skin `bone_map` points to arm/shoulder bones; LBS guard now clamps cross-region pull < 8 units; full fix needs Aurora `bone_remap` table generation | Identified, partially mitigated |
| **Legacy PIL renderer → PyKotor pipeline** — texture decode, mipmap generation, and normal-map pipeline still have dual paths; consolidating to `pykotor.resource.formats.tpc` throughout | ~70 % migrated |

---

### 🗺 Near-term (v5.6 – v6.0)

#### Walkmesh Editing
| Sub-feature | Description |
|-------------|-------------|
| **In-viewport selection** | Click-select individual `.wok` triangles in the 3-D viewport; multi-select with Shift/Ctrl |
| **Surface-type painting** | Paint brush to assign Aurora walk surface flags: `WALK` · `GRASS` · `STONE` · `DIRT` · `PUDDLE` · `NONWALK` · `TRIGGER` |
| **Height-paint / vertex edit** | Drag walkmesh vertices to reshape terrain elevation |
| **`.wok` export** | Write the modified walkmesh back to a valid Aurora `.wok` binary file |
| **Per-room walkmesh** | Support multi-room `.lyt` layouts; per-room walkmesh stacked in the same viewport |

#### Module / Room Editing
| Sub-feature | Description |
|-------------|-------------|
| **`.lyt` scene graph** | Parse and display the full room-instance list from a module's `.lyt` file |
| **Room placement UI** | Drag-and-drop room MDL instances; snap to grid; live `.lyt` offset preview |
| **Door & trigger editing** | Add / move / remove `git` door/trigger placeables with property inspector |
| **Waypoint editor** | Create / move `dwk` / waypoint objects with typed label; export to `git` |
| **`.mod` / `.erf` round-trip** | Full read-modify-write workflow for module container archives |

#### AcuRig-Style Auto-Rigging
| Sub-feature | Description |
|-------------|-------------|
| **Joint placement handles** | Show draggable joint handles overlaid on the mesh (hip, spine, shoulders, elbows, knees, ankles) — inspired by Autodesk HumanIK / AccuRig |
| **Biped template** | One-click Aurora biped template fit to model bounding box |
| **Quadruped template** | Auto-detect 4-legged models; place spinal chain + 4 limb chains |
| **Geodesic / heat-diffuse weights** | Compute initial LBS blend weights via heat-diffuse; visualise as vertex heat-map overlay |
| **Weight painting brush** | Interactive per-vertex brush to repaint weights; add/subtract/smooth modes |
| **Symmetry mirror** | Mirror joint placement and weights across X axis |
| **Bone roll correction** | Auto-compute roll angles to align local axes with mesh curvature |
| **Export to Aurora MDL** | Bake the resulting rig back into a valid Aurora `skin` node with `bone_map` |

---

### 🔭 Long-term / Full feature parity

| Feature | Description |
|---------|-------------|
| **Shape keys / morph targets** | Preview Aurora MDL morph animations (face expressions, mouth open/close) |
| **Constraint-based rigging** | Pole-vector IK, aim constraints, roll-extraction — export as Aurora `usecomp` animation |
| **GPU renderer (full)** | Complete migration from CPU PIL to ModernGL: PBR lighting, shadow maps, reflection probes |
| **Texture bake pipeline** | ZBrush → high-poly normal map → TPC bake (already stubbed in *Bake* menu) |
| **glTF 2.0 full round-trip** | Import as well as export — material, skin, and animation support |
| **Particle / emitter preview** | Render Aurora `emitter` nodes (billboards, beams, lightning) in CPU and GPU renderers |
| **MDL export improvements** | Full support for `emitter`, `reference`, `aabb`, `patch` node types in the writer |
| **Animation retargeting** | Map animations from one skeleton topology to another (e.g. K1 → K2 biped, creature → PC) |
| **Cloth simulation preview** | Real-time Aurora danglymesh physics simulation in the viewport |
| **Multi-room scene assembly** | Load multiple room MDLs simultaneously; compose a full module area with correct `.lyt` offsets |
| **K1/K2 creature render audit** | Full batch render + diagnostic pass over all creature MDLs; auto-report broken bones / missing textures |
| **Python scripting console** | Expose model graph, viewport, and resource manager to an in-app Python REPL |
| **Undo / redo stack** | Full command-history undo for transforms, rigging, and node edits |
| **Collaborative IPC** | Multi-client GhostRigger server: simultaneous Blender + GhostRigger + ZBrush workflow |

---

## Contributing

```bash
git clone https://github.com/CrispyW0nton/Kotor-3D-Model-Converter.git
cd Kotor-3D-Model-Converter
pip install -e ".[dev]"
pytest                   # all tests must pass before submitting
git checkout -b my-feature
# … make your changes …
pytest                   # verify again
git push origin my-feature
# open a PR to main
```

Please run `pytest` before submitting. Aim for **zero new test failures**.  
Code style: PEP 8, 4-space indents, type hints where practical.  
PR title format: `feat(scope): short description` or `fix(scope): short description`.

---

## License

MIT — see [LICENSE](LICENSE).

---

*GhostRigger is not affiliated with LucasArts, BioWare, Obsidian Entertainment, or Disney.*  
*KotOR and The Sith Lords are trademarks of their respective owners.*
