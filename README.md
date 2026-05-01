# GhostRigger – KotOR 1 & 2 Model Pipeline

> **Odyssey Engine Toolkit** — A focused 3D model viewer, rigging tool, and modding
> pipeline for *Star Wars: Knights of the Old Republic* (K1) and *The Sith Lords* (K2/TSL).

![GhostRigger v5.1 UI](assets/icons/ghostrigger_1024x1024.png)

*Dark theme · Library panel with game-installed models · 3-D viewport with skeleton overlay
· Node tree · Module Editor · status bar.*

---

## Latest Release — v5.1.0 (2026-04-05) · Streamlined Five-Pillar UI

The codebase has been **audited and trimmed** to focus on five core capabilities.
~2 400 lines of legacy dead code were removed; the right panel was reduced from eight
tabs to four, and the Module Editor was promoted to a first-class left-panel tab.

| Area | What changed |
|------|-------------|
| **Test suite** | **13 fast tests passing** plus 6,272-model MCP validation suite |
| **Right panel** | Reduced from 8 tabs → 4 focused tabs: Props · Anims · Char Builder · Textures |
| **Diagnostics** | Moved from tab to popup window (Ctrl+D / Model menu) — less clutter |
| **Cloth rigging** | Panel still available via Model menu; no longer occupies a permanent tab |
| **Module Editor** | Promoted to a first-class left-panel tab (was a hidden bottom toggle) |
| **Legacy panels** | Removed `RetargetPanel` and `HeadSnapPanel` (~2 400 lines); functionality merged into `CharacterBuilderPanel` |
| **Toolbar** | Cleaned — Open · Auto-Rig · Character Builder · Modules · Tex Dir · Import ▾ · Export ▾ |

---

## Five Core Pillars

### 1. Model Viewer — load K1/K2 models from the game directory

- **Auto-detection** of K1 and K2 installation paths (Windows · Linux/Steam · macOS · GOG)
- Category tabs: All · 🐲 Creature · 👤 Character · 🗡 Item/Armor · 🏛 Module · Other
- Live search with `Ctrl+F` · Game filter All / K1 / K2
- CPU-based PIL renderer with two-pass depth sorting and LBS linear-blend skinning
- Bone skeleton overlay · wireframe / solid / textured display modes
- WalkMesh triangle overlay (`.wok`) with walkable / blocked colour coding
- Gimbal manipulator (Translate / Rotate / Scale) · UV editor panel

### 2. Animation — browse, play, seek, and export all model animations

- Full animation list with name · length · key count · node count · event count
- Play / Stop / Pause / Loop controls with real-time viewport playback
- Seek bar and FPS selector (15, 24, 25, 30, 60)
- Export animations as **JSON** or **BVH** · Import JSON animations
- SuperModel animation chain resolution (K1 `S_Female02`, K2 `S_Female03`)
- Keyboard: `Ctrl+A` opens Animations panel · Space to play/pause

### 3. Character Builder — K1/K2 templates, skeleton rigging, head/body assembly

- **Auto-Rig** (`R`): Aurora-compatible skeleton generation for humanoid / creature / prop
- **Library Rig**: copy any model's rig directly onto the current mesh
- **GRig**: manual bone assignment with brush-mode weight painting
- **AcuRig**: guide-based biped rig with symmetry enforcement
- **Head/Body Assembly**: snap separate head and body models via the `headhook` node
  - Quick-pick tables for common K1/K2 heads and bodies
  - K1/K2 supermodel defaults (`S_Female02` / `S_Female03`)
- **Export**: write separate `.mdl` + `.mdx` files for head and body
- Toolbar button: **Character Builder** · Keyboard: `Ctrl+B`

### 4. Module Editor — walkmesh editing and community tools

Accessible as the **Modules tab** in the left panel (or toolbar button).

| Tool | Description |
|------|-------------|
| **Module Info** | Load & inspect `.lyt` / `.vis` / `.are` / `.git` / `.ifo` |
| **Walkmesh Editor** | View `.wok` stats · auto-generate `NON_WALK` walls for custom modules |
| **K1 ↔ K2 Porter** | One-step binary port; no MDLOps / ASCII round-trip needed |
| **Module Builder** | Scaffold new custom module starter files (LYT + VIS + ARE + GIT + IFO templates) |
| **Quick Export** | Batch-export room models + textures for Blender import |

Key capabilities:
- Auto-generate walkmesh walls (fixes camera clipping in Quanon-style modules)
- Supermodel name auto-remapping (`S_Female02 ↔ S_Female03`)
- Direct binary K1 ↔ K2 porter with no external tools

### 5. Resource Browser — 2DA viewer, game resource browser, MDL compile/decompile

- **2DA Browser** (left panel): PyKotor `read_2da` primary · sort · row-search · TSV/CSV export
- **Resource Browser** (left panel): `.rim` / `.erf` / `.mod` / `.bif` container browsing
  - GFF struct / field tree viewer with recursion-depth guard
- **MDLOps Bridge**: Compile ASCII MDL → Binary · Decompile Binary MDL → ASCII
- Menu: *MDLOps → Set MDLOps Path · Compile · Decompile*

---

## UI Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  Toolbar: Open  Auto-Rig  Character Builder  Modules  Tex Dir       │
│           ⬆ Import ▾   ⬇ Export ▾   [model name]  Anims  Diag  ⚙  │
├──────────────┬──────────────────────────────────┬───────────────────┤
│ LEFT PANEL   │         3-D VIEWPORT             │  RIGHT PANEL      │
│ ┌──────────┐ │  (orbit / pan / zoom)            │ ┌───────────────┐ │
│ │ Library  │ │  skeleton overlay                │ │ Props         │ │
│ │ Nodes    │ │  walkmesh overlay                │ │ Anims         │ │
│ │ 2DAs     │ │  gimbal manipulator              │ │ Char Builder  │ │
│ │ Resources│ │  HUD: model badge, FPS, gizmo    │ │ Textures      │ │
│ │ Modules  │ │                                  │ └───────────────┘ │
│ └──────────┘ │                                  │                   │
├──────────────┴──────────────────────────────────┴───────────────────┤
│  Log panel (collapsible)                                            │
└─────────────────────────────────────────────────────────────────────┘
```

**Left panel tabs:** Library · Nodes · 2DAs · Resources · Modules  
**Right panel tabs (4 only):** Props · Anims · Char Builder · Textures  
**Hidden (menu/keyboard access):** Diagnostics (Ctrl+D popup) · Cloth (Model menu)  
**Menus:** File · Model · MDLOps · Bake · Modular · IPC · Help

---

## Quick-start

### Windows

```bat
git clone https://github.com/CrispyW0nton/Kotor-3D-Model-Converter.git
cd Kotor-3D-Model-Converter
```

Then double-click **`build.bat`** — it installs all dependencies and builds
`dist\GhostRigger-K1-K2.exe` automatically. Double-click the exe to launch.

**Requirements:** Python 3.10+ (tick "Add Python to PATH" during install), Windows 10+.

### Run from source (any OS)

```bash
git clone https://github.com/CrispyW0nton/Kotor-3D-Model-Converter.git
cd Kotor-3D-Model-Converter
pip install -r requirements.txt
python main.py
```

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+O` | Open MDL (binary) |
| `Ctrl+Shift+O` | Open MDL (ASCII) |
| `Ctrl+I` | Import OBJ |
| `Ctrl+E` | Export OBJ |
| `Ctrl+G` | Export glTF |
| `Ctrl+M` | Export Binary MDL |
| `Ctrl+S` | Save ASCII MDL |
| `Ctrl+W` | Clear model |
| `R` | Auto-rig current model |
| `Ctrl+D` | Run diagnostics (popup) |
| `Ctrl+A` | Animations panel |
| `Ctrl+P` | Properties panel |
| `Ctrl+F` | Focus skeleton search |
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
| `Tab` | Cycle gimbal mode (T/R/S) |
| `Esc` | Deselect |

---

## Project Structure

```
src/
├── core/
│   ├── mdl_parser.py         # Binary MDL reader (Aurora engine format)
│   ├── mdl_writer.py         # Binary MDL writer
│   ├── model_data.py         # In-memory model graph
│   ├── animation_engine.py   # Animation curve interpolation & playback
│   ├── pykotor_bridge.py     # PyKotor MDL/TPC/Anim adapter
│   ├── diagnostics.py        # Per-node model diagnostics
│   └── resource_manager.py   # Unified K1/K2 resource lookup
├── gui/
│   ├── main_window.py        # Main window: five-pillar pipeline UI (~10 000 lines)
│   ├── viewport.py           # CPU PIL renderer + GPU renderer (~9 000 lines)
│   └── modular_panel.py      # Module Editor panel (~1 200 lines)
├── autorig/
│   ├── auto_rigger.py        # Aurora skeleton auto-rigging
│   ├── cloth_rig.py          # Danglymesh cloth rigging
│   ├── accurig.py            # AcuRig guide-based bigging
│   └── grig.py               # GRig manual bone assignment
├── converters/
│   ├── mesh_converter.py     # OBJ/FBX/glTF import & export
│   └── normal_map.py         # ZBrush → TPC normal-map bake
└── ipc/
    ├── server.py             # GhostRigger JSON-RPC IPC server
    └── client.py             # IPC client (GModular / GhostScripter)

tests/                        # Core contracts, regressions, and MCP validation
```

---

## Tests

```bash
# Fast tests (core contracts + regressions)
pytest tests/ -m "not slow" -v

# Full MCP validation (requires game installations + KotorMCP)
pytest tests/test_mcp_full_scan.py -v
```

Current results: 13 core tests passing, 6,272-model MCP validation suite available.

---

## Validation

GhostRigger's model pipeline is validated against every MDL resource in both
KotOR 1 and KotOR 2 using [KotorMCP](https://github.com/CrispyW0nton/KotorMCP-Ghost)
ground-truth comparison tools.

| Metric | Result |
|--------|--------|
| Total models scanned | 6,272 |
| Pipeline match (GhostRigger == PyKotor) | 6,224 (99.2%) |
| Upstream load failures (PyKotor) | 48 |
| GhostRigger-only failures | 0 |
| Skinning issues | 0 |
| Texture references classified | 198 (lightmaps, cut content) |

To reproduce:

```bash
# Generate model manifest
python scripts/generate_manifest.py

# Run tiered scan (non-module models, full comparison)
python scripts/full_scan.py --game all --tier fast

# Run module models (load + node-count check)
python scripts/full_scan.py --game all --tier modules --resume

# Analyze results
python scripts/analyze_scan.py
```

---

## Roadmap

### In Progress

| Issue | Status |
|-------|--------|
| **CaloNord `usecomp` animation** — LBS guard clamps cross-region pull < 8 units; full fix needs Aurora `bone_remap` table generation | Partially mitigated |
| **PyKotor pipeline consolidation** — texture decode and normal-map pipeline dual paths; consolidating to `pykotor.resource.formats.tpc` | ~70% migrated |

### Near-term (v5.2 – v6.0)

#### Walkmesh Editing (Module Editor enhancement)
- In-viewport click-select of individual `.wok` triangles
- Surface-type paint brush (`WALK` / `NONWALK` / `GRASS` / `STONE` / etc.)
- Drag walkmesh vertices to reshape terrain elevation
- Write modified walkmesh back to a valid Aurora `.wok` binary file

#### Module / Room Editing
- `.lyt` scene graph: parse and display full room-instance list
- Drag-and-drop room MDL instances with snap-to-grid
- Door / trigger / waypoint editing with GIT export

#### AcuRig Improvements
- Draggable joint handles overlaid on mesh (hip, spine, shoulders, elbows, knees)
- Geodesic / heat-diffuse LBS weight initialisation
- Interactive weight-painting brush with smooth mode

### Long-term

| Feature | Description |
|---------|-------------|
| **Shape keys / morph targets** | Preview Aurora MDL morph animations (face expressions) |
| **GPU renderer** | Full migration from CPU PIL to ModernGL: PBR lighting, shadow maps |
| **Full glTF round-trip** | Import as well as export — materials, skin, animations |
| **Particle / emitter preview** | Render Aurora `emitter` nodes (billboards, beams) |
| **Multi-room scene assembly** | Load multiple room MDLs; compose a full module area |
| **Python scripting console** | In-app Python REPL with access to model graph and viewport |
| **Undo / redo stack** | Command-history undo for transforms, rigging, and node edits |

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
