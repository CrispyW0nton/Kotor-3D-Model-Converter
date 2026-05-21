# GhostRigger — KotOR 1 & 2 Model Pipeline

> **Odyssey Engine Toolkit** — a 3-D model viewer, skeletal-animation
> playground, rigging tool, and modding pipeline for *Star Wars: Knights of the
> Old Republic* (K1) and *The Sith Lords* (K2 / TSL).

![GhostRigger UI](assets/icons/ghostrigger_1024x1024.png)

| | |
|---|---|
| **Project version** | `6.0.0` (`pyproject.toml`) — five-pillar UI baseline + active 2026-05 skinning audit |
| **Runtime** | Python **3.12** (3.10–3.12 supported), Tkinter UI, ModernGL GPU path with PIL CPU fallback |
| **License** | MIT — see [`LICENSE`](LICENSE) |
| **Repository** | <https://github.com/CrispyW0nton/Kotor-3D-Model-Converter> |
| **Active branch** | `genspark_ai_developer` |

---

## Table of contents

1. [What is GhostRigger?](#1-what-is-ghostrigger)
2. [What it does — five pillars](#2-what-it-does--five-pillars)
3. [Tech stack](#3-tech-stack)
4. [Setup tutorial](#4-setup-tutorial)
   - [Windows: build the standalone `.exe` with `build.bat`](#41-windows-build-the-standalone-exe-with-buildbat)
   - [Run from source (any OS)](#42-run-from-source-any-os)
   - [First launch](#43-first-launch)
5. [Command-line usage](#5-command-line-usage)
6. [Architecture overview](#6-architecture-overview)
7. [Project layout](#7-project-layout)
8. [Tests & validation](#8-tests--validation)
9. [Diagnostic env switches](#9-diagnostic-env-switches)
10. [Active audit — 2026-05 skinning pipeline (3j)](#10-active-audit--2026-05-skinning-pipeline-3j)
11. [Roadmap](#11-roadmap)
12. [Contributing](#12-contributing)

---

## 1. What is GhostRigger?

GhostRigger is a desktop application that loads, inspects, edits and re-exports
the 3-D model files (`.mdl` / `.mdx`) used by BioWare's Odyssey engine in
*Knights of the Old Republic* and *The Sith Lords*. It is built around three
goals:

1. **Faithful round-trip.** Every model in both K1 and K2 should be loadable,
   renderable, and re-writable without geometry corruption. The 6 272-model
   MCP scan suite (`scripts/full_scan.py`) is the contract.
2. **Modder ergonomics.** UI for the everyday tasks — loading characters,
   swapping heads onto bodies, painting bone weights, editing walkmeshes,
   compiling/decompiling MDL — without dropping out to MDLOps or the CLI.
3. **Reproducible audits.** When a render bug is found, the project's
   "audit-first, document-then-fix" workflow produces a JSONL trace under
   `diagnostics/`, a Markdown audit doc under `knowledge_base/audits/`, and an env-gated
   diagnostic formula in code so the fix can be validated numerically before
   it is allowed near production. See section 10.

GhostRigger is **not** affiliated with LucasArts, BioWare, Obsidian or
Disney. KotOR and The Sith Lords are trademarks of their respective owners.

---

## 2. What it does — five pillars

The UI surface is intentionally small. Five tabs / panels cover the entire
modding pipeline.

| # | Pillar | What you can do | Open it with |
|---|--------|-----------------|--------------|
| 1 | **Model Viewer** | Auto-detect K1/K2 installs · category-tabbed library (Creature / Character / Item / Module / Other) · live search · CPU PIL renderer with depth-sorted LBS skinning **and** ModernGL GPU path · skeleton overlay · walkmesh overlay (`.wok`) · gimbal manipulator (T/R/S) · UV editor | Launch app · `Ctrl+L` to focus library |
| 2 | **Animation** | Browse every animation in the model · Play / Stop / Pause / Loop / Seek · 15–60 fps selector · export as JSON or BVH · import JSON · supermodel chain resolution (`S_Female02`, `S_Female03`) | `Ctrl+A` |
| 3 | **Character Builder** | Auto-Rig (Aurora skeleton) · Library Rig (copy any model's rig) · GRig (manual + brush weight paint) · AcuRig (guide-based biped) · head/body assembly via the `headhook` node · separate `.mdl` + `.mdx` export per piece | `Ctrl+B` |
| 4 | **Module Editor** | Inspect `.lyt` / `.vis` / `.are` / `.git` / `.ifo` · view `.wok` walkmesh stats and auto-generate `NON_WALK` walls · one-step binary K1↔K2 porter (no MDLOps round-trip) · scaffold new module starter files · batch room MDL+texture export for Blender | Modules toolbar button or left-panel **Modules** tab |
| 5 | **Resource Browser** | 2DA viewer (PyKotor `read_2da`, sort, row-search, TSV/CSV export) · `.rim`/`.erf`/`.mod`/`.bif` container browser · GFF struct/field tree viewer · MDLOps bridge for ASCII↔Binary MDL compile/decompile | Left-panel **2DAs** / **Resources** tabs · MDLOps menu |

UI map:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Toolbar: Open  Auto-Rig  Character Builder  Modules  Tex Dir       │
│           ⬆ Import ▾   ⬇ Export ▾   [model name]  Anims  Diag  ⚙  │
├──────────────┬──────────────────────────────────┬───────────────────┤
│ LEFT PANEL   │         3-D VIEWPORT             │  RIGHT PANEL      │
│  Library     │  orbit / pan / zoom              │  Props            │
│  Nodes       │  skeleton + walkmesh overlays    │  Anims            │
│  2DAs        │  gimbal manipulator              │  Char Builder     │
│  Resources   │  HUD: model badge, FPS, gizmo    │  Textures         │
│  Modules     │                                  │                   │
├──────────────┴──────────────────────────────────┴───────────────────┤
│  Log panel (collapsible)                                            │
└─────────────────────────────────────────────────────────────────────┘
```

**Hidden access:** Diagnostics (`Ctrl+D` popup) · Cloth (Model menu).
**Top menus:** File · Model · MDLOps · Bake · Modular · IPC · Help.

---

## 3. Tech stack

| Layer | Technology | Notes |
|-------|------------|-------|
| Language | **Python 3.10+** (Python 3.12 recommended; `build.bat` pins `py -3.12`) | |
| GUI | **Tkinter** (`tk` / `ttk`) | bundled with CPython; no Qt dependency |
| 3-D rendering | **ModernGL ≥ 5.8** (GPU palette skinning, std430 SSBOs) with **Pillow + NumPy** CPU fallback (`src/gui/viewport.py`) | both backends share `src/core/gpu_skinning.py` |
| KotOR I/O | **PyKotor 2.3.1** (pinned) — MDL/MDX/TPC/TXI/ERF/BIF reader+writer; monkey-patched by `src/core/pykotor_mdl_io_fix.py` for K2 trimesh layout and `mdx_data_offset==0` quirks | bumping the pin requires re-validating the patch (`tests/test_pykotor_patch_compat.py`) |
| Owned MDL reader | **`src/core/ghostrigger_mdl_reader.py`** — GhostRigger's own binary reader for cases where PyKotor's reader can't be safely patched | always invoked through `src/core/mdl_reader_wrapper.py:read_mdl_safe` |
| Mesh I/O | **trimesh ≥ 3.15** (OBJ / DAE / fallback GLTF), **pygltflib ≥ 1.15** (GLTF 2.0 / GLB), **pyassimp ≥ 5.2** + **assimp-py ≥ 1.0** (FBX with optional bone import) | |
| IPC | **Flask ≥ 2.3** + **requests ≥ 2.28** (port 7001, used by the Ghostworks pipeline) | |
| MCP | **mcp ≥ 1.0** + **pydantic ≥ 2.0** + **uvicorn[standard] ≥ 0.20** | embedded MCP server exposes KotOR resources to AI agents (`src/kotormcp/`) |
| Packaging | **PyInstaller ≥ 5.0** + `pyinstaller-hooks-contrib`; spec at `GhostRigger-K1-K2.spec` | bundles Assimp DLL when available |
| Misc | `opencv-python-headless` (Matrix-style animated background) | |

**Native binary that gets bundled at build time:**
`assimp-vc143-mt.dll` v6.0.4 — auto-downloaded by `build.bat` step 4 if `pyassimp` is installed but its DLL is missing.

---

## 4. Setup tutorial

### 4.1 Windows: build the standalone `.exe` with `build.bat`

`build.bat` is a one-command, fully-logged installer + PyInstaller wrapper. It
produces a single self-contained `dist\GhostRigger-K1-K2.exe` that ships with
all Python and native dependencies — no Python or pip required to run the
result.

**One-time prerequisites:**

1. Install **Python 3.12** from
   <https://python.org/downloads/release/python-31210/>. **Tick "Add Python to
   PATH"** during install — otherwise `py -3.12` in the next step fails.
2. Install **Git for Windows** (or download the repo as a ZIP).
3. Windows 10 or later. The first build needs internet access for ~600 MB
   of wheels plus a one-time Assimp DLL download.

**Build steps:**

```bat
git clone https://github.com/CrispyW0nton/Kotor-3D-Model-Converter.git
cd Kotor-3D-Model-Converter
build.bat
```

You can also just double-click `build.bat` from File Explorer. The first build
takes 3–6 minutes. Subsequent builds are 30–90 s because pip uses its cache.

**What `build.bat` does, step by step:**

| Step | Action | If it fails |
|------|--------|-------------|
| 1 / 6 | Verifies `py -3.12` is on `PATH` | Re-run the Python installer with "Add Python to PATH" ticked |
| 2 / 6 | `py -3.12 -m pip install --upgrade pip` | Continues with a warning |
| 3 / 6 | Installs core deps: `Pillow` · `numpy` · `PyOpenGL` · `trimesh` · `pygltflib` · `flask` · `requests` · `mcp` · `pydantic` · `uvicorn` · `pyassimp` · `assimp-py` · `pykotor` · `moderngl` · `pyinstaller` | Only the PyInstaller failure is fatal; everything else is best-effort with a `[WARN]` line |
| 4 / 6 | If `pyassimp` is installed but its DLL is missing, downloads `assimp-vc143-mt.dll` v6.0.4 from GitHub and copies it into the `pyassimp` package folder so FBX bone import works | `assimp-py` (geometry-only FBX) still works as a fallback |
| 5 / 6 | Verifies `assets/icons/ghostrigger.ico` exists; generates a placeholder if not | Auto-recovers |
| 6 / 6 | Runs `py -3.12 -m PyInstaller GhostRigger-K1-K2.spec --clean --noconfirm` | Open `build_log.txt` for the full PyInstaller traceback |

When the build succeeds:

```
============================================================
 BUILD COMPLETE!
 Executable: dist\GhostRigger-K1-K2.exe
============================================================
```

**Run it:** double-click `dist\GhostRigger-K1-K2.exe`.

**Troubleshooting:** every step's stdout and stderr is appended to
`build_log.txt` next to `build.bat`. The window stays open and `pause`s on any
error — read the last lines of `build_log.txt` first.

### 4.2 Run from source (any OS)

```bash
git clone https://github.com/CrispyW0nton/Kotor-3D-Model-Converter.git
cd Kotor-3D-Model-Converter
pip install -r requirements.txt
python main.py
```

`main.py` boots the same UI the packaged `.exe` does. Use this path for
day-to-day development; use `build.bat` only when you need a redistributable
binary.

For a `pip install -e .` development install, see the optional dependency
groups in [`pyproject.toml`](pyproject.toml):
`ghostrigger[gui]`, `[kotor]`, `[mesh]`, `[mcp]`, `[all]`.

### 4.3 First launch

1. Open **Settings → Game Paths** to point GhostRigger at your KotOR / TSL
   install. Steam-default install paths auto-detect.
2. The library panel populates from your installs and from any `Override/`
   folder.
3. Session logs land in `Logs/ghostrigger_<date>.log` (rotated; newest 20
   kept). Crashes — including Tkinter callback exceptions — are captured by
   the global hook in `main.py`.

### 4.4 Themes and layouts

GhostRigger now has XML-driven theme and layout support across the Qt shell and
major tool windows. The original green high-contrast look is preserved as the
selectable **Matrix** theme, but it is no longer hardcoded as the only
application style.

Packaged themes live in `config/themes/themes/`: `matrix.xml`, `dark.xml`,
`light.xml`, and `classic.xml`. Packaged layouts live in
`config/themes/layouts/`: `default.xml`, `compact.xml`, `wide.xml`, and
`cinematic.xml`.

Use **Settings -> Theme/Layout** to choose a manual theme, follow the native OS
light/dark mode through `darkdetect`, select a layout, override toolbar button
modes, adjust icon sizing, and enable XML hot reload during theme development.
The Theme tab uses **Apply Theme** for full-application application; lightweight
preview editing lives in the Theme Editor.

The Theme Editor can duplicate, validate, preview, and save theme colour/font
tokens and layout density metrics without hand-editing XML. Its preview pane is
local to the editor until **Apply Theme** or **Apply Layout** is clicked, so
colour and size experiments do not repeatedly restyle the entire app.

Layouts are:

- **Default**: balanced 1080p/1440p tool layout.
- **Compact**: tighter margins, shorter rows/buttons, and icon-forward toolbars
  for more viewport room.
- **Wide**: wider side panels and viewport proportions for ultrawide displays.
- **Cinematic**: viewport/camera workspace priority with less surrounding
  clutter.

Community themes and layouts can be placed in the platform-specific
GhostRigger user config directory under `GhostRigger/themes/` and
`GhostRigger/layouts/`; user files with matching ids intentionally override
packaged defaults. The editor writes backups before overwriting user XML.

---

## 5. Command-line usage

### 5.1 Application entry point

```bash
python main.py            # launches the full Tk UI
```

`main.py` takes no command-line arguments. All configuration lives in
`settings.json` (auto-created in the working directory on first launch and
gitignored — never commit yours).

### 5.2 Headless model inspector

`tools/model_inspector.py` dumps the parsed node hierarchy of any MDL without
opening the GUI — useful for "is this a parser bug or a render bug?"
diagnostics, regression diffs, and CI.

```bash
# Inspect a raw MDL (+ optional MDX) on disk
python -m tools.model_inspector --mdl path/to/pfhc01.mdl

# Resolve a resref through a full game install (KEY/BIF + Override)
python -m tools.model_inspector --game-dir "C:/GOG/KotOR" --resref pfhc01

# JSON output for diffing / regression tests
python -m tools.model_inspector --mdl pfhc01.mdl --json > pfhc01.json
```

Per node it prints index, DFS depth, name, type, flags, vertex space (one of
`NODE_LOCAL` / `WORLD` / `AABB_WALK`), local position + xyzw rotation, computed
world transform, vertex / face / UV counts, and the `bone_map` for skin nodes.
Inner-geometry nodes (eyes / teeth / tongue / gum / jaw) get an explicit
world-position block.

### 5.3 Validation suite (MCP-backed)

| Tool | Purpose | Default output |
|------|---------|----------------|
| `python scripts/generate_manifest.py` | Enumerate every K1+K2 MDL resource (~6 272) via paged `KotorMCP listResources` | `exports/scan_manifest.json` |
| `python scripts/full_scan.py` | Tiered MCP-driven parity scan vs PyKotor ground truth | `exports/full_scan_results_<tier>.json` |
| `python scripts/validate_all_models.py` | Structural validation only (load + node-count); faster than full_scan | `exports/structural_validation.json` (gitignored) |
| `python scripts/analyze_scan.py` | Categorise scan failures into Phase-4 triage classes | `exports/failure_analysis.json` |

```bash
# Generate the manifest of every K1+K2 MDL resource (~6 272 entries)
python scripts/generate_manifest.py [--output PATH] [--limit 50]

# Run the full pipeline parity scan against PyKotor ground truth
python scripts/full_scan.py --game all --tier fast              # non-module models, full comparison
python scripts/full_scan.py --game all --tier modules --resume  # module models, resume previous run
python scripts/full_scan.py --game k2 --tier full --diag        # verbose isolated full scan
python scripts/full_scan.py --game k1 --category creatures --max-models 50

# Structural-only validation (no PyKotor diff)
python scripts/validate_all_models.py --game all [--limit N]

# Summarise + classify the most recent scan results
python scripts/analyze_scan.py [--input PATH ...] [--output PATH]
```

`full_scan.py` flags:

| Flag | Choices / type | Default | Effect |
|------|---------------|---------|--------|
| `--game` | `k1` · `k2` · `all` | `all` | Restrict to one game's models |
| `--tier` | `fast` · `modules` · `full` | `fast` | `fast` = non-module models with full diff; `modules` = module rooms with load + node-count check; `full` = isolated subprocess per model with hard timeout |
| `--category` | `creatures` · `players` · `npcs` · `modules` · `all` | `all` | Restrict to one resref category |
| `--resume` | flag | off | Skip resrefs already present in the result JSON |
| `--diag` | flag | off | Print every model's start time (locate stalls) |
| `--timeout` | float (s) | `60.0` | Per-model timeout for `--tier full` and `--tier modules` |
| `--max-models` | int | `0` | Hard cap after `--resume` filtering (`0` = no cap) |

Tracked result files (kept in git): `exports/scan_manifest.json`,
`exports/full_scan_results.json`, `exports/full_scan_results_fast.json`,
`exports/full_scan_results_modules.json`, `exports/failure_analysis.json`,
`exports/texture_analysis.json`, `exports/load_error_classification.json`.
Everything else in `exports/` is gitignored.

### 5.4 Diagnostic scripts (per-model deep dives)

| Tool | Purpose |
|------|---------|
| `python scripts/diagnose_bonemap.py` | Deep diagnosis of PyKotor `skin.bonemap` -> GhostRigger `bone_map` conversion |
| `python scripts/diagnose_k2_geometry.py` | Diagnose K2 skin/render transform issues against MCP inspection data |
| `python scripts/diagnose_transforms.py` | Dump current bind-pose transforms for skin vs trimesh nodes |

```bash
python scripts/diagnose_bonemap.py        --game k2 --resref c_bantha [--print-source]
python scripts/diagnose_k2_geometry.py    [--models RESREF ...] [--limit N] [--output PATH]
python scripts/diagnose_transforms.py     --game k2 --resref c_bantha
```

### 5.5 Skinning audit reproducers (3j-1 -> 3j-4 + 3i)

These scripts reproduce the numerical proofs that gate the env-switched
`G5_FULL_REF` skinning formula (see section 10). They write JSONLs into
`diagnostics/skinning/2026_05/` (gitignored). All accept no required arguments
- they hard-code the three audit creatures (`c_drexlf`, `c_brith`, `c_bomabeast`).

| Tool | Audit step | Proves |
|------|-----------|--------|
| `python scripts/dump_qbone_byte_parity.py` | 3j-1 | qBone/tBone bytes import faithfully (0.0 max-abs delta on 546 slots) |
| `python scripts/dump_qbone_consumption_replay.py` | 3j-2 | Convention divergence vs xoreos / KotOR.js / reone (W-first qBone, no T*R inversion) |
| `python scripts/dump_qbone_single_vertex_replay.py` | 3j-3 | Bind-pose self-test on 50 probe vertices; identifies DFS-indexing as the third compounding bug |
| `python scripts/dump_qbone_full_vertex_replay_3j4.py` | 3j-4 / Goal 1 | Self-test collapses on 2 546 / 2 546 weighted vertices under G5 (max disp <= 2.169e-6); F1 fails 0/2546 |
| `python scripts/dump_qbone_renderer_parity_3j4.py` | 3j-4 / Goal 3 | 121 / 121 in-renderer SSBO palette slots bit-exact to offline G5 replay (max delta <= 5.4e-7) |
| `python scripts/regen_skin_3i_step6_dump.py` | 3i-6 | Pre-qBone basis provenance dump (loader/VBO passthrough vs pre-baked) |
| `python scripts/reduce_skin_3i_step6.py` | 3i-6 / 3i-7 reduction | Reduce the per-creature dumps to a structural decision table |
| `python scripts/skin_3i_step7_visual_gate.py` | 3i-7 | F1-vs-F11 visual-gate captures (closed B-translation branch) |

### 5.6 Visual QA pipeline

| Tool | Purpose |
|------|---------|
| `python scripts/render_baseline.py --generate` | Generate baseline PNG renders of every model (writes to `exports/baseline_renders/`, gitignored) |
| `python scripts/render_baseline.py --compare`  | Re-render and compare against the baseline; writes `exports/render_diff_report.json` |
| `python scripts/visual_audit_k2.py` | Headless visual audit on a representative K2 sample (default 50 models) |
| `python scripts/visual_review.py` | Human-in-the-loop reviewer for `render_diff_report.json` failures (talks to the IPC server on `127.0.0.1:7001`) |

```bash
# Baseline workflow
python scripts/render_baseline.py --generate [--all-angles]
python scripts/render_baseline.py --compare  [--all-angles]

# K2 visual audit
python scripts/visual_audit_k2.py [--limit 50] [--out-dir DIR]

# Review render-diff failures
python scripts/visual_review.py [--report PATH] [--output PATH] \
                                [--base-url http://127.0.0.1:7001] \
                                [--include-minor] [--delay 2.0]
```

### 5.7 Character Builder skeleton bases

```bash
python main.py                            # Character Builder loads real KOTOR base MDLs from the configured game install
```

The Character Builder no longer ships generated `templates/gr_*` skeleton-only
MDLs. Pick a real game base model or supermodel first, then import the custom
OBJ/FBX/glTF mesh so it is fit to that selected KOTOR skeleton.

### 5.8 At-a-glance index

Every CLI surface in the repo, by category:

| Category | Command |
|----------|---------|
| **Application** | `python main.py` |
| **Headless inspector** | `python -m tools.model_inspector --mdl PATH` · `--resref RESREF --game-dir DIR` · `--json` · `--bones` · `--bones-only` · `--output PATH` · `-v` |
| **Validation** | `python scripts/generate_manifest.py` · `full_scan.py` · `validate_all_models.py` · `analyze_scan.py` |
| **Diagnostics** | `python scripts/diagnose_bonemap.py` · `diagnose_k2_geometry.py` · `diagnose_transforms.py` |
| **Skinning audit** | `python scripts/dump_qbone_byte_parity.py` · `dump_qbone_consumption_replay.py` · `dump_qbone_single_vertex_replay.py` · `dump_qbone_full_vertex_replay_3j4.py` · `dump_qbone_renderer_parity_3j4.py` · `regen_skin_3i_step6_dump.py` · `reduce_skin_3i_step6.py` · `skin_3i_step7_visual_gate.py` |
| **Visual QA** | `python scripts/render_baseline.py --generate\|--compare` · `visual_audit_k2.py` · `visual_review.py` |
| **Character Builder bases** | Real KOTOR install resrefs such as `pmbam`, `pfbcm`, `n_sithsoldier`, `s_female02`, `s_female03` |
| **Tests** | `pytest tests/ -m "not slow"` · `pytest tests/test_mcp_full_scan.py` · `pytest tests/test_regression.py -k SUBSTR` |
| **Build** | `build.bat` (Windows) · `python -m PyInstaller GhostRigger-K1-K2.spec --clean --noconfirm` |

---

## 6. Architecture overview

```
                ┌──────────────────────────────────┐
                │            main.py               │  Logging, exception hooks, Tk root
                └──────────────────┬───────────────┘
                                   │ run()
                ┌──────────────────▼───────────────┐
                │       src/gui/main_window.py     │  Five-pillar UI (~10 k lines)
                │   ┌──────────┐  ┌──────────────┐ │
                │   │ Library  │  │ Char Builder │ │
                │   │ Nodes    │  │ Module Editor│ │
                │   │ 2DAs     │  │ Anims · Tex  │ │
                │   │ Resources│  │ Props · UVs  │ │
                │   └──────────┘  └──────────────┘ │
                └──────────────────┬───────────────┘
                                   │
       ┌───────────────────────────┼───────────────────────────────┐
       │                           │                               │
┌──────▼──────┐         ┌──────────▼─────────┐           ┌─────────▼──────────┐
│ Viewport    │         │ Resource layer     │           │ Tools / autorig    │
│ ┌──────────┐│         │ ┌────────────────┐ │           │ ┌────────────────┐ │
│ │ GPU path ││         │ │ ResourceManager│ │           │ │ Auto-Rig       │ │
│ │ ModernGL ││         │ │ K1/K2 dirs +   │ │           │ │ AcuRig / GRig  │ │
│ │ + SSBO   ││         │ │ Override/ scan │ │           │ │ Cloth Rig      │ │
│ └──────────┘│         │ └────────┬───────┘ │           │ │ Mesh Converter │ │
│ ┌──────────┐│         │          │         │           │ └────────────────┘ │
│ │ CPU path ││◀────────┤  read_mdl_safe()   │           └────────────────────┘
│ │ PIL+LBS  ││         │ (mdl_reader_wrapper.py)
│ └──────────┘│         │          │
└─────────────┘         │  ┌───────▼────────┐  ┌──────────────────────────────┐
                        │  │ PyKotor reader │  │ GhostRigger MDL reader       │
                        │  │ + K2 patches   │  │ (ghostrigger_mdl_reader.py)  │
                        │  └───────┬────────┘  └────────────┬─────────────────┘
                        │          │                        │
                        │  ┌───────▼────────────────────────▼───┐
                        │  │ src/core/model_data.py             │
                        │  │ ModelNode graph, vertex_space enum │
                        │  └────────────────────────────────────┘
                        └────────────────────────────────────┐
                                                             │
                              ┌──────────────────────────────▼─────┐
                              │ src/core/animation_engine.py +     │
                              │ src/core/gpu_skinning.py           │
                              │  · MatrixPaletteUploader            │
                              │  · F1 production / F11 / G5 formula │
                              │  · env-gated diagnostic switches   │
                              └────────────────────────────────────┘
```

Key invariants (see `.cursor/rules/project-identity.mdc`):

- All MDL loads go through **`src/core/mdl_reader_wrapper.py:read_mdl_safe`**.
- `src/core/vertex_space.py` defines the canonical `VertexSpace` enum
  (`NODE_LOCAL` / `WORLD` / `AABB_WALK`). Skin-node vertices are **always
  `NODE_LOCAL`** — never world-space.
- Quaternion convention is **xyzw (W-last)** throughout.
- The K2 trimesh-header monkey-patch is in
  `src/core/pykotor_mdl_io_fix.py` and protected by a startup signature check.
  `GHOSTRIGGER_ALLOW_UNPATCHED_PYKOTOR=1` bypasses it for raw-PyKotor A/B
  diagnostics only.

---

## 7. Project layout

```
Kotor-3D-Model-Converter/
├── main.py                       # entry point (logging, Tk root, exception hooks)
├── build.bat                     # one-command Windows installer + PyInstaller build
├── GhostRigger-K1-K2.spec        # PyInstaller spec (hiddenimports, Assimp DLL bundling)
├── build_game_templates.py       # legacy helper; generated template MDLs are no longer shipped
├── pyproject.toml                # PEP 621 metadata + optional dep groups
├── requirements.txt              # pinned runtime deps for `pip install -r`
├── AGENTS.md                     # MCP-driven workflow rules for AI contributors
├── LICENSE                       # MIT
├── README.md                     # this file
│
├── src/
│   ├── core/                     # MDL parsing, model graph, animation, skinning
│   │   ├── ghostrigger_mdl_reader.py    # owned binary MDL reader
│   │   ├── mdl_reader_wrapper.py        # read_mdl_safe() — single MDL ingress
│   │   ├── pykotor_mdl_io_fix.py        # K2 trimesh + mdx_offset patches for PyKotor
│   │   ├── kotor_loader.py              # high-level model loader
│   │   ├── model_data.py                # ModelNode graph, vertex_space enum
│   │   ├── animation_engine.py          # AnimPose evaluation, supermodel resolution
│   │   ├── gpu_skinning.py              # MatrixPaletteUploader + F1/F11/G5 env-gated formulas
│   │   ├── render_constants.py          # INNER_GEO_SUBSTRINGS, FACE_MESH_SUBSTRINGS
│   │   ├── vertex_space.py              # NODE_LOCAL / WORLD / AABB_WALK enum
│   │   ├── resource_manager.py          # K1/K2 install detection, KEY/BIF + Override scanning
│   │   ├── creature_appearance.py       # head/body assembly via headhook
│   │   ├── diagnostics.py               # session-start diagnostics
│   │   └── template_builder.py          # legacy generated-template helper
│   ├── gui/
│   │   ├── main_window.py               # five-pillar Tk UI (~10 k lines)
│   │   ├── viewport.py                  # CPU PIL renderer + camera + LBS skinning
│   │   ├── gpu_renderer.py              # ModernGL GPU path, SSBO palette, skin dump trace
│   │   ├── modular_panel.py             # Module Editor panel
│   │   ├── tpc_render_utils.py          # TPC/TXI texture decode helpers
│   │   ├── accel.py                     # OpenGL accelerator helpers
│   │   └── (other panels: Char Builder, Anim Tab, etc.)
│   ├── autorig/
│   │   ├── auto_rigger.py               # Aurora skeleton auto-rig
│   │   ├── accurig.py                   # AcuRig guide-based biped
│   │   ├── grig.py                      # GRig manual + brush weight paint
│   │   └── cloth_rig.py                 # Danglymesh cloth rig
│   ├── converters/
│   │   ├── mesh_converter.py            # OBJ / FBX / glTF import + export
│   │   └── normal_map.py                # ZBrush → TPC normal-map bake
│   ├── ipc/                             # Flask JSON-RPC server (Ghostworks pipeline, port 7001)
│   ├── kotormcp/                        # embedded MCP server (KotOR resources for AI agents)
│   ├── formats/                         # KotOR file-format helpers
│   ├── resources/                       # static resources used by the UI
│   └── infra/                           # MCP autostart, etc.
│
├── tests/                        # pytest; see section 8
│   ├── conftest.py
│   ├── test_core_contracts.py           # vertex_space, render_constants, etc.
│   ├── test_regression.py               # bug-fix regressions (incl. F11/G5 env switch)
│   ├── test_pykotor_patch_compat.py     # PyKotor pin guard (block silent K2 corruption)
│   ├── test_mcp_full_scan.py            # 6 272-model parity scan (slow marker)
│   ├── test_mcp_skinning.py             # MCP skinning ground-truth comparisons
│   └── test_mcp_textures.py             # MCP texture pipeline checks
│
├── tools/
│   └── model_inspector.py        # headless node-tree dump (CI / regression diffing)
│
├── scripts/                      # validation runners + audit reproducers (gitignored except allow-list)
│   ├── generate_manifest.py             # build the 6 272-model manifest
│   ├── full_scan.py                     # MCP-backed parity scan
│   ├── analyze_scan.py                  # classify scan results
│   └── dump_qbone_*.py                  # 3j-1 → 3j-4 audit reproducers
│
├── templates/                    # gr_body / gr_head MDL templates (Character Builder)
├── knowledge_base/               # consolidated docs (roadmap, audits, CLI, reference specs)
│   ├── roadmap/                  # active Qt-branch roadmap (2026-05, Character Builder)
│   ├── audits/2026-05/           # active audit Markdown (3j skinning, lightmap, GPU transparency, ...)
│   ├── cli/                      # CLI reference
│   └── reference/                # historical specs, deliverables, protocol, mandatory checklist
├── exports/                      # tracked: scan results / failure analysis only (rest gitignored)
├── assets/                       # icons + screenshots used by the UI and README
└── .cursor/                      # Cursor rules (project identity, cleanup policy)
```

**Gitignored on disk**: `Logs/`, `dist/`, `build/`, `build_log.txt`,
`settings.json`, `GhostRigger-K1-K2.exe`, `diagnostics/`, every
`exports/baseline_renders*` / `exports/skin_*` / `exports/visual_*` artefact
(reproducible from the audit scripts).

---

## 8. Tests & validation

```bash
# Fast: core contracts + regressions (default tier; should be green on every PR)
pytest tests/ -m "not slow" -v

# Single regression test
pytest tests/test_regression.py -k "skin_node_palette_env_switch" -v

# Full MCP validation (requires K1 + K2 installs and KotorMCP-Ghost; long-running)
pytest tests/test_mcp_full_scan.py -v
```

Test markers are declared in `pyproject.toml`:

| Marker | Meaning |
|--------|---------|
| `slow` | Runs the full 6 272-model MCP parity scan; gate behind `-m "not slow"` for fast feedback |

Validation against PyKotor ground truth — see the latest tracked scan results
under `exports/full_scan_results_fast.json` and `exports/failure_analysis.json`.

---

## 9. Diagnostic env switches

Every switch is **off by default** and unset values, unknown values, and
wrong casing all silently fall back to the production code path — a typo can
never affect normal use.

### Skinning pipeline (`src/core/gpu_skinning.py`)

| Variable | Default | What it does |
|----------|---------|--------------|
| `GHOSTRIGGER_SKIN_FORMULA=F1_current_TR_inverse` | F1 (3f baseline) — production | Slot-indexed, X-first quaternion, inverted T*R |
| `GHOSTRIGGER_SKIN_FORMULA=F11_rotation_only_skin_bind_wrapper` | — | 3i Step 7 diagnostic; rotation-only outer-wrapper variant |
| `GHOSTRIGGER_SKIN_FORMULA=G5_FULL_REF` | — | 3j Step 4 reference-backed pipeline (DFS-indexed, W-first quaternion, no inversion) — **collapses bind-pose self-test on 2 546 / 2 546 weighted vertices across c_drexlf, c_brith, c_bomabeast** |
| `GHOSTRIGGER_SKIN_DUMP=<path>.jsonl` | unset | Per skin draw, append the uploaded SSBO matrices for offline parity reconciliation |

### PyKotor patch guard (`src/core/pykotor_mdl_io_fix.py`)

| Variable | Default | What it does |
|----------|---------|--------------|
| `GHOSTRIGGER_ALLOW_UNPATCHED_PYKOTOR=1` | unset | Bypass the K2 trimesh-header patch signature check. **Diagnostics-only.** Reintroduces silent K2 geometry corruption — never set in production. |

### Renderer / GPU diagnostics (`src/gui/gpu_renderer.py`)

| Variable | What it does |
|----------|--------------|
| `GHOSTRIGGER_GL_BACKEND=egl|wgl|...` | Force a specific GL context backend |
| `GHOSTRIGGER_GL_STATE_TRACE=<path>` | Append per-draw GL state to a JSONL trace |
| `GHOSTRIGGER_VIEWPORT_PROBE=1` | Enable extra head-pose probe printouts in viewport / GPU renderer |
| `GHOSTRIGGER_DEBUG_VIZ=<path>` | Write per-skin debug visualization PNGs |
| `GHOSTRIGGER_LM_DATA_DUMP=<path>` | Dump lightmap data per draw |
| `GHOSTRIGGER_LM_COMPOSITE_MODE=...` | Override the lightmap composite formula for A/B testing |

### Embedded MCP server (`src/infra/mcp_autostart.py`)

| Variable | Default | What it does |
|----------|---------|--------------|
| `GHOSTRIGGER_NO_MCP_AUTOSTART=1` | unset | Disable embedded MCP server autostart |
| `GHOSTRIGGER_MCP_PORT=<n>` | `7401` | Override the MCP HTTP port |

---

## 10. Active audit — 2026-05 skinning pipeline (3j)

Animated K1/K2 creatures (humanoids and beasts) are under an
**audit-first, document-then-fix** review. Production rendering remains pinned
to the **3f baseline** (F1) until the visual-gate stage clears. The full
ground-truth findings are tracked in
[`knowledge_base/audits/2026-05/skinning_parity.md`](knowledge_base/audits/2026-05/skinning_parity.md).

| Step | Status | Result |
|------|--------|--------|
| **3j-1** byte-for-byte qBone/tBone parity | complete | 0.0 max-abs delta across 546 slots — bytes import faithfully |
| **3j-2** consumption-convention audit (xoreos / KotOR.js / reone) | complete | Identified 2 compounding convention bugs vs reference engines |
| **3j-3** single-vertex bind-pose replay | complete | Identified 3rd compounding bug (DFS indexing); `G5_FULL_REF` collapses self-test on 50 / 50 probes |
| **3j-4** env-gated G5 implementation + full numerical proofs | complete | 2 546 / 2 546 weighted vertices on `c_drexlf` / `c_brith` / `c_bomabeast` collapse under G5; 121 / 121 in-renderer palette slots bit-exact to offline replay |
| **3j-5** joint visual gate + 50-model render-diff | pending | Final ship gate before production flip |

Other 2026-05 audits in `knowledge_base/audits/2026-05/`:

| File | Subject |
|------|---------|
| `lightmap_composite.md` | Lightmap composite blend modes (multiplicative vs additive) |
| `lightmap_data.md` | Lightmap UV layout and data parity |
| `gl_state_recorder.md` | GL state recorder used by GPU diagnostics |
| `gpu_transparency_depth.md` | Transparency / depth-test ordering |
| `debug_visualization.md` | Per-skin debug-visualisation PNG pipeline |
| `visual_performance.md` | Frame-time and pass-count regression trace |
| `../k2_skin_transform.md` | K2-specific skin transform notes (referenced from 3j) |

---

## 11. Roadmap

### In progress

| Issue | Status |
|-------|--------|
| **3j-5 visual gate** for the corrected `G5_FULL_REF` skinning pipeline | pending; production stays on F1 |
| **CaloNord `usecomp` animation** — LBS guard clamps cross-region pull < 8 units; full fix needs Aurora `bone_remap` table generation | partially mitigated |
| **PyKotor pipeline consolidation** — texture decode + normal-map dual paths consolidating to `pykotor.resource.formats.tpc` | ~70 % migrated |

### Near-term

- Walkmesh editor: in-viewport `.wok` triangle select + surface-type paint brush + writeback to valid Aurora `.wok`
- `.lyt` scene-graph room-instance editor with snap-to-grid and door / trigger / waypoint editing
- AcuRig: draggable joint handles overlaid on mesh; geodesic / heat-diffuse weight initialisation; smoothing brush

### Long-term

| Feature | Description |
|---------|-------------|
| Shape keys / morph targets | Preview Aurora MDL morph animations (face expressions) |
| Full glTF round-trip | Import as well as export — materials, skin, animations |
| Particle / emitter preview | Render Aurora `emitter` nodes (billboards, beams) |
| Multi-room scene assembly | Load multiple room MDLs; compose a full module area |
| Python scripting console | In-app REPL with access to model graph and viewport |
| Undo / redo stack | Command-history undo for transforms, rigging, node edits |

---

## 12. Contributing

```bash
git clone https://github.com/CrispyW0nton/Kotor-3D-Model-Converter.git
cd Kotor-3D-Model-Converter
pip install -e ".[all]"          # see optional dep groups in pyproject.toml
pytest -m "not slow"             # fast tier — must pass before any PR
git checkout -b my-feature
# ... make your changes ...
pytest -m "not slow"             # verify again
git push origin my-feature
# open a PR to genspark_ai_developer
```

**Commit message format** (matches the existing history):

```
feat(scope): short description
fix(scope): short description
chore(cleanup): short description
test(scope): short description
docs(scope): short description
audit(scope): short description
```

**Code style:** PEP 8 · 4-space indents · type hints where practical ·
ruff with E/F/W/I rule sets (`pyproject.toml [tool.ruff]`).

**Audit-first workflow.** When fixing rendering or skinning bugs, follow the
project rule in `AGENTS.md`:

1. Use the MCP tools to confirm the bug exists against PyKotor ground truth.
2. Ship a diagnostic dump script (`scripts/dump_*.py`) that reproduces the
   numerical evidence.
3. Add an audit Markdown under `knowledge_base/audits/` documenting the finding.
4. Land any fix behind an env switch (see section 9), keep production on
   the baseline until the visual-gate suite clears.

**Hard constraints** (`.cursor/rules/project-identity.mdc`) — never:

1. Modify any file in the PyKotor workspace.
2. Modify `src/core/creature_appearance.py:snap_head_onto_body` (Bug B was
   misdiagnosed; the current behaviour is correct).
3. Reintroduce centroid-magnitude heuristics for vertex-space classification.
4. Treat skin-node vertices as world-space — they are always `NODE_LOCAL`.
5. Change the xyzw quaternion convention.
6. Bypass `read_mdl_safe` for MDL ingress.

---

## License

MIT — see [`LICENSE`](LICENSE).

*GhostRigger is not affiliated with LucasArts, BioWare, Obsidian Entertainment,
or Disney.*
*KotOR and The Sith Lords are trademarks of their respective owners.*
