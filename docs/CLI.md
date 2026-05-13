# GhostRigger — Exhaustive CLI Reference

Every command-line surface in the repo, with full flag tables, defaults,
hard-coded constants, output paths, and example invocations.

This document is the **authoritative CLI reference**. The README's section 5
is a developer-friendly summary of the same material; this file is what you
consult when you need every flag of every script.

> **Working directory:** all examples assume you are at the repo root.
> **Python version:** 3.10–3.12 (3.12 recommended; `build.bat` pins `py -3.12`).
> **Output convention:** `<repo>/exports/` for tracked artefacts,
> `<repo>/diagnostics/skinning/2026_05/` for audit dumps (gitignored).

---

## Table of contents

- [1. Application](#1-application)
  - [1.1 `python main.py`](#11-python-mainpy)
- [2. Headless inspector](#2-headless-inspector)
  - [2.1 `python -m tools.model_inspector`](#21-python--m-toolsmodel_inspector)
- [3. Build](#3-build)
  - [3.1 `build.bat` (Windows)](#31-buildbat-windows)
  - [3.2 `python -m PyInstaller GhostRigger-K1-K2.spec`](#32-python--m-pyinstaller-ghostrigger-k1-k2spec)
- [4. Tests](#4-tests)
  - [4.1 `pytest`](#41-pytest)
- [5. Validation suite (MCP-backed)](#5-validation-suite-mcp-backed)
  - [5.1 `python scripts/generate_manifest.py`](#51-python-scriptsgenerate_manifestpy)
  - [5.2 `python scripts/full_scan.py`](#52-python-scriptsfull_scanpy)
  - [5.3 `python scripts/validate_all_models.py`](#53-python-scriptsvalidate_all_modelspy)
  - [5.4 `python scripts/analyze_scan.py`](#54-python-scriptsanalyze_scanpy)
- [6. Diagnostic scripts](#6-diagnostic-scripts)
  - [6.1 `python scripts/diagnose_bonemap.py`](#61-python-scriptsdiagnose_bonemappy)
  - [6.2 `python scripts/diagnose_k2_geometry.py`](#62-python-scriptsdiagnose_k2_geometrypy)
  - [6.3 `python scripts/diagnose_transforms.py`](#63-python-scriptsdiagnose_transformspy)
- [7. Skinning audit reproducers (3j + 3i)](#7-skinning-audit-reproducers-3j--3i)
  - [7.1 `python scripts/dump_qbone_byte_parity.py`](#71-python-scriptsdump_qbone_byte_paritypy)
  - [7.2 `python scripts/dump_qbone_consumption_replay.py`](#72-python-scriptsdump_qbone_consumption_replaypy)
  - [7.3 `python scripts/dump_qbone_single_vertex_replay.py`](#73-python-scriptsdump_qbone_single_vertex_replaypy)
  - [7.4 `python scripts/dump_qbone_full_vertex_replay_3j4.py`](#74-python-scriptsdump_qbone_full_vertex_replay_3j4py)
  - [7.5 `python scripts/dump_qbone_renderer_parity_3j4.py`](#75-python-scriptsdump_qbone_renderer_parity_3j4py)
  - [7.6 `python scripts/regen_skin_3i_step6_dump.py`](#76-python-scriptsregen_skin_3i_step6_dumppy)
  - [7.7 `python scripts/reduce_skin_3i_step6.py`](#77-python-scriptsreduce_skin_3i_step6py)
  - [7.8 `python scripts/skin_3i_step7_visual_gate.py`](#78-python-scriptsskin_3i_step7_visual_gatepy)
- [8. Visual QA pipeline](#8-visual-qa-pipeline)
  - [8.1 `python scripts/render_baseline.py`](#81-python-scriptsrender_baselinepy)
  - [8.2 `python scripts/visual_audit_k2.py`](#82-python-scriptsvisual_audit_k2py)
  - [8.3 `python scripts/visual_review.py`](#83-python-scriptsvisual_reviewpy)
- [9. Template builder](#9-template-builder)
  - [9.1 `python build_game_templates.py`](#91-python-build_game_templatespy)
- [10. Library helpers (not invoked directly)](#10-library-helpers-not-invoked-directly)
- [11. Environment variables that modify CLI behaviour](#11-environment-variables-that-modify-cli-behaviour)
- [12. Exit codes](#12-exit-codes)

---

## 1. Application

### 1.1 `python main.py`

Launches the full GhostRigger Tk UI.

| Aspect | Value |
|--------|-------|
| **Arguments** | none |
| **Reads** | `settings.json` (auto-created in CWD on first launch; gitignored) |
| **Writes** | `Logs/ghostrigger_<YYYY-MM-DD_HHMMSS>.log` (rotated; newest 20 kept) |
| **Side effects** | Embedded MCP server may autostart (port 7401) — disable with `GHOSTRIGGER_NO_MCP_AUTOSTART=1` |
| **Exit codes** | `0` on clean shutdown · non-zero from `traceback.format_exc()` on fatal startup failure |

```bash
python main.py
```

The `dist\GhostRigger-K1-K2.exe` produced by `build.bat` is functionally
identical to running `python main.py` from a frozen Python.

---

## 2. Headless inspector

### 2.1 `python -m tools.model_inspector`

Dump the parsed node hierarchy of a KotOR MDL without opening the GUI.
Intended for "is this a parser bug or a render bug?" diagnostics, regression
diffs, and CI.

| Flag | Type | Default | Required | Description |
|------|------|---------|----------|-------------|
| `--mdl PATH` | str | — | one of `--mdl` / `--resref` | Path to a `.mdl` file on disk |
| `--resref RESREF` | str | — | one of `--mdl` / `--resref` | Resref name to resolve via `--game-dir` |
| `--mdx PATH` | str | sibling of `--mdl` | optional | Path to a `.mdx` file |
| `--game-dir DIR` | str | — | required with `--resref` | KotOR installation root |
| `--json` | flag | off | optional | Emit JSON instead of the human-readable report |
| `--bones` | flag | off | optional | Append a dedicated bone-map resolution section per skin node (mirrors xoreos `fillBoneNodeMap`) |
| `--bones-only` | flag | off | optional | Print only the bone-map section (implies `--bones`, suppresses the full node dump) |
| `--output PATH`, `-o PATH` | str | stdout | optional | Write output to this file instead of stdout |
| `--verbose`, `-v` | flag | off | optional | Enable DEBUG logging |

**Per-node fields printed (text mode):** index · DFS depth · name · type
(`dummy` / `trimesh` / `skin` / `danglymesh` / `light` / `emitter` / ...) ·
flags · vertex space (`NODE_LOCAL` / `WORLD` / `AABB_WALK`) · local position ·
local rotation (xyzw quaternion) · computed `world_position` /
`world_transform` · vertex / face / UV counts · `bone_map` for skin nodes ·
inner-geometry world-position block for eye / teeth / tongue / gum / jaw nodes.

**Exit codes:** `0` ok · `2` model load failed · `3` model loaded as None ·
`4` `inspect_model` raised.

```bash
python -m tools.model_inspector --mdl path/to/pfhc01.mdl
python -m tools.model_inspector --resref pfhc01 --game-dir "C:/GOG/KotOR"
python -m tools.model_inspector --mdl pfhc01.mdl --json -o pfhc01.json
python -m tools.model_inspector --resref c_drexlf --game-dir "C:/GOG/TSL" --bones-only
```

---

## 3. Build

### 3.1 `build.bat` (Windows)

One-command installer + PyInstaller wrapper. Produces a self-contained
`dist\GhostRigger-K1-K2.exe`.

| Aspect | Value |
|--------|-------|
| **Arguments** | none |
| **Requires** | Windows · `py -3.12` on `PATH` · internet on first run (~600 MB wheels + Assimp DLL) |
| **Reads / writes** | Appends every step's stdout + stderr to `build_log.txt` next to the script |
| **Output** | `dist\GhostRigger-K1-K2.exe` (~117 MB; gitignored) |
| **Steps** | 1/6 verify Python · 2/6 upgrade pip · 3/6 install runtime deps · 4/6 fetch & install Assimp DLL · 5/6 verify icon · 6/6 run PyInstaller |

```bat
build.bat
```

### 3.2 `python -m PyInstaller GhostRigger-K1-K2.spec`

Manual PyInstaller invocation. `build.bat` step 6 calls this with `--clean
--noconfirm`. Use directly when you've already installed deps and just want to
re-package.

| Flag | Effect |
|------|--------|
| `--clean` | Wipe PyInstaller's cache (`build/`) before assembling |
| `--noconfirm` | Skip the "overwrite `dist/`?" prompt |
| `--log-level=DEBUG` | Print every collected module / data file / binary |

**Spec contents** (`GhostRigger-K1-K2.spec`):
- Hidden imports: `tkinter` + submodules, `PIL._tkinter_finder`, every
  submodule of `src.{core,gui,ipc,converters,autorig,formats,resources,kotormcp}`,
  `moderngl`, `numpy`.
- Optional Assimp bundling: prefers `pyassimp` (full bone import) over
  `assimp_py` (geometry-only fallback). Skips silently if neither is installed.
- Excludes from frozen exe: `pytest`, `unittest`, `pydantic`, `mcp`, plus
  `pyassimp` / `assimp_py` if not importable.
- Single-file output, no console window, icon `assets/icons/ghostrigger.ico`,
  UPX compression on (Windows only).

```bash
python -m PyInstaller GhostRigger-K1-K2.spec --clean --noconfirm
```

---

## 4. Tests

### 4.1 `pytest`

Standard pytest. Test markers come from `pyproject.toml`:

| Marker | Meaning |
|--------|---------|
| `slow` | Full 6 272-model MCP parity scan (`tests/test_mcp_full_scan.py`); excluded by `-m "not slow"` |

| Suite | What it covers |
|-------|----------------|
| `tests/test_core_contracts.py` | `vertex_space`, `render_constants`, `INNER_GEO_SUBSTRINGS` invariants |
| `tests/test_regression.py` | All bug-fix regressions, including the F11 / G5 env-switch tests |
| `tests/test_pykotor_patch_compat.py` | Guards the K2 trimesh-header monkey-patch against PyKotor version drift |
| `tests/test_mcp_full_scan.py` | Full 6 272-model parity scan (marked `slow`) |
| `tests/test_mcp_skinning.py` | MCP skinning ground-truth comparisons |
| `tests/test_mcp_textures.py` | MCP texture pipeline checks |

```bash
pytest tests/ -m "not slow" -v                              # default fast tier
pytest tests/test_regression.py -k "skin_node_palette" -v   # one regression group
pytest tests/test_mcp_full_scan.py -v                       # full slow suite
pytest tests/ -x -v                                         # stop on first failure
```

---

## 5. Validation suite (MCP-backed)

### 5.1 `python scripts/generate_manifest.py`

Enumerate every K1+K2 MDL resource via paged `KotorMCP listResources` and
write the result as a single manifest JSON.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--output PATH` | Path | `exports/scan_manifest.json` | Manifest output path |
| `--limit N` | int | `50` | KotorMCP `listResources` page size; max `500`, `< 1` rejected |

**Manifest schema:**
```json
{
  "generated": "2026-04-29T12:34:56Z",
  "k1": {"count": 3036, "models": ["...", ...]},
  "k2": {"count": 3236, "models": ["...", ...]},
  "total": 6272
}
```

```bash
python scripts/generate_manifest.py
python scripts/generate_manifest.py --output /tmp/manifest.json --limit 200
```

### 5.2 `python scripts/full_scan.py`

Tiered MCP-driven model-scan runner with isolated subprocess support and
per-model timeout. Results land in
`exports/full_scan_results_<tier>.json` (tracked).

| Flag | Type / choices | Default | Description |
|------|----------------|---------|-------------|
| `--game` | `k1` · `k2` · `all` | `all` | Restrict to one game's models |
| `--tier` | `fast` · `modules` · `full` | `fast` | `fast` = non-module, full PyKotor diff; `modules` = module rooms with load + node-count check; `full` = isolated subprocess per model with hard timeout |
| `--category` | `creatures` · `players` · `npcs` · `modules` · `all` | `all` | Restrict to one resref category |
| `--resume` | flag | off | Skip resrefs already present in the result JSON |
| `--diag` | flag | off | Print every model's start time (use to locate stalls) |
| `--timeout SECONDS` | float | `60.0` | Per-model hard timeout for `--tier full` and `--tier modules` |
| `--max-models N` | int | `0` | Hard cap after `--resume` filtering (`0` = no cap) |

**Output paths:**
- `--tier fast`    → `exports/full_scan_results_fast.json`
- `--tier modules` → `exports/full_scan_results_modules.json`
- `--tier full`    → `exports/full_scan_results.json`

```bash
python scripts/full_scan.py                                          # K1+K2 fast tier
python scripts/full_scan.py --game k2 --tier fast
python scripts/full_scan.py --game all --tier modules --resume
python scripts/full_scan.py --game k2 --tier full --diag --timeout 90
python scripts/full_scan.py --game k1 --category creatures --max-models 50
```

### 5.3 `python scripts/validate_all_models.py`

Structural validation only (load + node-count parity); faster than
`full_scan.py` because it skips the per-model PyKotor diff. Uses the shared
`add_common_args` helper.

| Flag | Type / choices | Default | Description |
|------|----------------|---------|-------------|
| `--game` | `all` · `k1` · `k2` | `all` | Restrict to one game's models |
| `--limit N` | int | none | Limit number of models for smoke tests |

**Output:** `exports/structural_validation.json` (gitignored).

**Exit code:** `0` if all models pass, `1` if any failed.

**Print line per model:** `[i] <game>:<resref> {PASS|FAIL} (<duration_ms> ms)`.

```bash
python scripts/validate_all_models.py
python scripts/validate_all_models.py --game k2
python scripts/validate_all_models.py --game all --limit 100
```

### 5.4 `python scripts/analyze_scan.py`

Categorise tiered full-scan failures into Phase-4 triage classes
(`load_error`, `texture_error`, `geometry_mismatch`, ...).

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--input PATH` | Path (repeatable) | auto-detect (see below) | Scan result JSON to analyse; may be passed more than once |
| `--output PATH` | Path | `exports/failure_analysis.json` | Output JSON |

**Auto-detect order** when no `--input` is supplied:
1. `exports/full_scan_results_fast.json` and
   `exports/full_scan_results_modules.json` if either exists.
2. Otherwise `exports/full_scan_results.json`.

```bash
python scripts/analyze_scan.py
python scripts/analyze_scan.py --input exports/full_scan_results_fast.json
python scripts/analyze_scan.py --input scan_a.json --input scan_b.json --output combined.json
```

---

## 6. Diagnostic scripts

These are per-model deep-dive scripts. None are intended for batch use; they
print to stdout for human reading.

### 6.1 `python scripts/diagnose_bonemap.py`

Deep diagnosis of PyKotor `skin.bonemap` -> GhostRigger `bone_map` conversion.

| Flag | Type / choices | Default | Description |
|------|----------------|---------|-------------|
| `--game` | `k1` · `k2` | `k2` | Game to load from |
| `--resref RESREF` | str | `c_bantha` | Resref to diagnose |
| `--print-source` | flag | off | Also print the raw PyKotor `bonemap` source array |

```bash
python scripts/diagnose_bonemap.py
python scripts/diagnose_bonemap.py --game k1 --resref c_drexlf --print-source
```

### 6.2 `python scripts/diagnose_k2_geometry.py`

Diagnose K2 skin/render transform issues against MCP inspection data.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--models RESREF [RESREF ...]` | list[str] | `DEFAULT_K2_MODELS` (see below) | K2 model resrefs to diagnose |
| `--limit N` | int | `0` | Limit to first N models (`0` = no limit) |
| `--output PATH` | str | `exports/k2_geometry_diagnosis.json` | Report output |

**`DEFAULT_K2_MODELS`** (from `scripts/diagnose_k2_geometry.py` lines 31–42):
`c_bantha`, `c_cannok`, `c_zakkeg`, `n_darthsion`, `n_darthtraya`, `p_hk47`,
`PFHB01`–`PFHB05`, `PMHB01`–`PMHB05`, `PFHC01`–`PFHC10`, `PMHC01`–`PMHC10`.

```bash
python scripts/diagnose_k2_geometry.py
python scripts/diagnose_k2_geometry.py --models c_drexlf c_brith --output /tmp/diag.json
python scripts/diagnose_k2_geometry.py --limit 10
```

### 6.3 `python scripts/diagnose_transforms.py`

Dump current bind-pose transforms for skin vs trimesh nodes. Useful as a
quick before/after when changing skin_bind handling.

| Flag | Type / choices | Default | Description |
|------|----------------|---------|-------------|
| `--game` | `k1` · `k2` | `k2` | Game to load from |
| `--resref RESREF` | str | `c_bantha` | Resref to diagnose |

```bash
python scripts/diagnose_transforms.py
python scripts/diagnose_transforms.py --game k1 --resref c_drexlf
```

---

## 7. Skinning audit reproducers (3j + 3i)

All of the audit reproducers in this section take **no command-line
arguments**. They hard-code the three audit creatures
(`c_drexlf`, `c_brith`, `c_bomabeast`) and the output directory
`diagnostics/skinning/2026_05/` (gitignored). Edit the `TARGETS` tuple at
the top of each file to point at different models.

Each script's purpose is documented in
[`docs/skinning_parity_audit_2026_05.md`](skinning_parity_audit_2026_05.md);
the table here covers what each one writes and what numerical fact it
proves.

### 7.1 `python scripts/dump_qbone_byte_parity.py`

| Aspect | Value |
|--------|-------|
| **Audit step** | 3j-1 |
| **Arguments** | none |
| **Hard-coded targets** | `c_drexlf` (K2), `c_brith` (K2), `c_bomabeast` (K1) |
| **Outputs** (one per target) | `diagnostics/skinning/2026_05/qbone_byte_parity_<resref>.jsonl` |
| **Proves** | qBone/tBone bytes import faithfully (0.0 max-abs delta on 546 slots) |

```bash
python scripts/dump_qbone_byte_parity.py
```

### 7.2 `python scripts/dump_qbone_consumption_replay.py`

| Aspect | Value |
|--------|-------|
| **Audit step** | 3j-2 |
| **Arguments** | none |
| **Inputs** | `diagnostics/skinning/2026_05/qbone_byte_parity_<resref>.jsonl` (run 7.1 first) |
| **Outputs** (one per target) | `diagnostics/skinning/2026_05/qbone_consumption_replay_<resref>.jsonl` |
| **Proves** | Two compounding convention bugs vs xoreos / KotOR.js / reone (W-first qBone byte order; no T*R inversion) |

```bash
python scripts/dump_qbone_byte_parity.py    # required first (input dependency)
python scripts/dump_qbone_consumption_replay.py
```

### 7.3 `python scripts/dump_qbone_single_vertex_replay.py`

| Aspect | Value |
|--------|-------|
| **Audit step** | 3j-3 |
| **Arguments** | none |
| **Outputs** (one per target) | `diagnostics/skinning/2026_05/qbone_single_vertex_replay_<resref>.jsonl` |
| **Proves** | Bind-pose self-test on 50 probe vertices; identifies DFS-indexing as the third compounding bug; introduces `G5_FULL_REF` candidate |

```bash
python scripts/dump_qbone_single_vertex_replay.py
```

### 7.4 `python scripts/dump_qbone_full_vertex_replay_3j4.py`

| Aspect | Value |
|--------|-------|
| **Audit step** | 3j-4 / Goal 1 |
| **Arguments** | none |
| **Runs both** | F1 (production baseline) **and** G5_FULL_REF (env-gated) per target |
| **Outputs** (one per target) | `diagnostics/skinning/2026_05/qbone_full_vertex_replay_3j4_<resref>.jsonl` |
| **Proves** | G5 collapses bind-pose self-test on **2 546 / 2 546 weighted vertices** (max disp ≤ 2.169e-6); F1 fails 0 / 2546 |

```bash
python scripts/dump_qbone_full_vertex_replay_3j4.py
```

### 7.5 `python scripts/dump_qbone_renderer_parity_3j4.py`

| Aspect | Value |
|--------|-------|
| **Audit step** | 3j-4 / Goal 3 |
| **Arguments** | none |
| **Side effects** | Sets `GHOSTRIGGER_SKIN_FORMULA=G5_FULL_REF` and `GHOSTRIGGER_SKIN_DUMP` for each render; renders headlessly at 256×256 |
| **Outputs** (per target) | `diagnostics/skinning/2026_05/qbone_renderer_parity_3j4_<resref>.jsonl` (parity report) and `diagnostics/skinning/2026_05/skin_dump_g5_<resref>.jsonl` (uploaded-SSBO trace) |
| **Summary** | `diagnostics/skinning/2026_05/qbone_renderer_parity_3j4_summary.json` |
| **Proves** | **121 / 121** in-renderer SSBO palette slots bit-exact to offline G5 replay (max delta ≤ 5.4e-7); bind-pose self-test holds in the live renderer (max delta ≤ 1.971e-6) |

```bash
python scripts/dump_qbone_renderer_parity_3j4.py
```

### 7.6 `python scripts/regen_skin_3i_step6_dump.py`

| Aspect | Value |
|--------|-------|
| **Audit step** | 3i-6 |
| **Arguments** | none |
| **Outputs** (per target) | `diagnostics/skinning/2026_05/skin_<resref>_3i.jsonl` |
| **Proves** | Pre-qBone basis is loader/VBO passthrough, not pre-baked; closes the "raw vertex space mismatch" hypothesis |

```bash
python scripts/regen_skin_3i_step6_dump.py
```

### 7.7 `python scripts/reduce_skin_3i_step6.py`

| Aspect | Value |
|--------|-------|
| **Audit step** | 3i-6 / 3i-7 reduction |
| **Arguments** | none |
| **Inputs** | `diagnostics/skinning/2026_05/skin_<resref>_3i.jsonl` (run 7.6 first) |
| **Outputs** | Reduction tables to stdout (and optional summary JSON in `diagnostics/skinning/2026_05/`) |
| **Proves** | Reduces the per-creature dumps to a single structural decision table |

```bash
python scripts/regen_skin_3i_step6_dump.py    # required first (input dependency)
python scripts/reduce_skin_3i_step6.py
```

### 7.8 `python scripts/skin_3i_step7_visual_gate.py`

| Aspect | Value |
|--------|-------|
| **Audit step** | 3i-7 |
| **Arguments** | none |
| **Hard-coded targets** | `c_bomabeast` (K1, animated), `c_drexlf` (K2, bind-pose only) |
| **Render specs** | 512×512, three orthogonal-ish views per model |
| **Outputs** | `exports/skin_3i_step7_visual_gate/*.png` and `exports/skin_3i_step7_visual_gate/report.json` (gitignored) |
| **Proves** | F11 rotation-only outer-wrapper does **not** improve `c_bomabeast` anatomy → closed B-translation branch |

```bash
python scripts/skin_3i_step7_visual_gate.py
```

---

## 8. Visual QA pipeline

### 8.1 `python scripts/render_baseline.py`

Generate baseline PNG renders of every model, then re-render later and
compare against the baseline. Modes are mutually exclusive.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--generate` | flag (mode) | one mode required | Generate baseline PNGs |
| `--compare` | flag (mode) | one mode required | Re-render and compare against baseline |
| `--all-angles` | flag | off | Render front / right / top / diagonal instead of diagonal only |
| `--game` | `all` · `k1` · `k2` | `all` | (from `add_common_args`) Restrict to one game |
| `--limit N` | int | none | (from `add_common_args`) Limit models for smoke tests |

**Outputs** (gitignored):
- `exports/baseline_renders/` — baseline PNGs (~116 MB at full coverage)
- `exports/baseline_renders_metadata.json` — per-render manifest (resref, angle, hash, timestamp)
- `exports/current_renders/` — `--compare` re-render output
- `exports/render_diff_report.json` — per-model diff classification consumed by `visual_review.py`

```bash
python scripts/render_baseline.py --generate
python scripts/render_baseline.py --generate --all-angles --game k2
python scripts/render_baseline.py --compare
python scripts/render_baseline.py --compare --limit 20
```

### 8.2 `python scripts/visual_audit_k2.py`

Headless visual audit on a representative K2 sample. Renders every selected
model and writes both PNGs and a JSON summary.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--limit N` | int | `50` | Number of K2 models to audit |
| `--out-dir DIR` | Path | `exports/visual_audit_k2` | Output directory |

**Outputs:** PNGs under `--out-dir/` and `exports/visual_audit_k2.json`
(gitignored).

```bash
python scripts/visual_audit_k2.py
python scripts/visual_audit_k2.py --limit 100 --out-dir /tmp/audit
```

### 8.3 `python scripts/visual_review.py`

Human-in-the-loop reviewer for `render_diff_report.json` failures. Calls the
GhostRigger IPC server (Flask, port 7001) to display each failed model and
prompts you for a verdict.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--report PATH` | Path | `exports/render_diff_report.json` | Diff report to review |
| `--output PATH` | Path | `exports/visual_review_verdicts.json` | Verdict JSON to write |
| `--base-url URL` | str | `http://127.0.0.1:7001` | IPC server URL |
| `--include-minor` | flag | off | Include `MINOR` category (default reviews `REGRESSION`, `EXPLODED`, `DISAPPEARED`, `ERROR`) |
| `--delay SECONDS` | float | `2.0` | Delay between models so the IPC viewport has time to redraw |

**Prerequisite:** GhostRigger UI must be running (so the IPC server is up on
port 7001) **and** `render_baseline.py --compare` must have been run to
produce the diff report.

```bash
python scripts/visual_review.py
python scripts/visual_review.py --include-minor --delay 3.0
python scripts/visual_review.py --report /tmp/diff.json --output /tmp/verdicts.json
```

---

## 9. Template builder

### 9.1 `python build_game_templates.py`

Regenerate the four template MDLs that back the Character Builder's
"new body" / "new head" actions. Strips geometry from real KotOR game models
while preserving the bone hierarchy, node names, positions, rotations, and
supermodel references.

| Aspect | Value |
|--------|-------|
| **Arguments** | none |
| **Reads** | `K1_DIR` / `K2_DIR` from the script's hard-coded paths (Steam defaults) |
| **Writes** | `templates/gr_body_k1.mdl` · `gr_body_k2.mdl` · `gr_head_k1.mdl` · `gr_head_k2.mdl` plus matching `_manifest.json` files plus `templates/README.md` |
| **Source resrefs** | `pfbcm` (body, both games) · `pfhc01` (head, both games) |

```bash
python build_game_templates.py
```

---

## 10. Library helpers (not invoked directly)

These files live in `scripts/` but are not CLIs — they're imported by the
other scripts. Listed for completeness so nothing in the repo is unaccounted
for.

| File | Purpose |
|------|---------|
| `scripts/qa_common.py` | Shared helpers for structural and render QA scripts (`add_common_args`, `iter_models`, `load_ghostrigger_model`, `write_json`) |

---

## 11. Environment variables that modify CLI behaviour

All variables are off / unset by default. Unknown values silently fall back
to the production code path. See `README.md` section 9 for full descriptions.

### Skinning pipeline (consumed by every render path)

| Variable | Effect on CLI |
|----------|---------------|
| `GHOSTRIGGER_SKIN_FORMULA=F1_current_TR_inverse` | Production baseline (default) |
| `GHOSTRIGGER_SKIN_FORMULA=F11_rotation_only_skin_bind_wrapper` | 3i-7 rotation-only outer-wrapper diagnostic |
| `GHOSTRIGGER_SKIN_FORMULA=G5_FULL_REF` | 3j-4 reference-backed pipeline (DFS-indexed, W-first qBone, no T*R inversion) |
| `GHOSTRIGGER_SKIN_DUMP=<path>.jsonl` | Append uploaded SSBO matrices per skin draw |

### PyKotor patch guard

| Variable | Effect on CLI |
|----------|---------------|
| `GHOSTRIGGER_ALLOW_UNPATCHED_PYKOTOR=1` | Bypass the K2 trimesh-header signature check. **Diagnostics-only.** Reintroduces silent K2 geometry corruption — never set in production. |

### Renderer / GPU diagnostics

| Variable | Effect on CLI |
|----------|---------------|
| `GHOSTRIGGER_GL_BACKEND=egl|wgl|...` | Force a specific GL context backend |
| `GHOSTRIGGER_GL_STATE_TRACE=<path>` | Append per-draw GL state to a JSONL trace |
| `GHOSTRIGGER_VIEWPORT_PROBE=1` | Enable extra head-pose probe printouts |
| `GHOSTRIGGER_DEBUG_VIZ=<path>` | Write per-skin debug-visualisation PNGs |
| `GHOSTRIGGER_LM_DATA_DUMP=<path>` | Dump lightmap data per draw |
| `GHOSTRIGGER_LM_COMPOSITE_MODE=...` | Override the lightmap composite formula |

### Embedded MCP server (only affects `python main.py`)

| Variable | Default | Effect on CLI |
|----------|---------|---------------|
| `GHOSTRIGGER_NO_MCP_AUTOSTART=1` | unset | Disable embedded MCP server autostart |
| `GHOSTRIGGER_MCP_PORT=<n>` | `7401` | Override the MCP HTTP port |

---

## 12. Exit codes

Repo-wide convention:

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | At least one model failed validation (used by `validate_all_models.py`) |
| `2` | Model load failed (used by `tools/model_inspector.py`) |
| `3` | Model loaded as `None` (used by `tools/model_inspector.py`) |
| `4` | `inspect_model` raised (used by `tools/model_inspector.py`) |
| non-zero (other) | Fatal Python exception (re-raised after logging) |

Audit scripts in section 7 return `0` on completion regardless of numerical
result — the proof is in the JSONL output, not the exit code.
