---

# Beneath the Code: KotOR Toolkit Project — A Full Project Retrospective

### *GhostRigger-K1-K2 · Python · Pillow · NumPy · Tkinter · OpenGL · 5 Weeks*

---

> *"The hardest bugs aren't the ones that crash your program. They're the ones that make it look almost right."*

What started as a weekend experiment in reading a proprietary binary format from a 2003 video game turned into a five-week deep dive into 3D rendering pipelines, UV mathematics, software rasterization, and the particular joy of chasing a dark triangle that only appeared on one model out of two thousand. This is the story of **GhostRigger-K1-K2** — a one-stop Python toolkit for modding *Star Wars: Knights of the Old Republic* — and everything I learned building it.

---

## The Premise

*Knights of the Old Republic* (KotOR) uses a proprietary 3D format called **ASCII/Binary MDL** — designed by BioWare, compiled by a third-party Perl script called MDLOps, and thoroughly undocumented. The community has reverse-engineered most of it over two decades, but the tooling gap remains wide: existing tools are fragmented, platform-specific, and unmaintained.

My goal was clear enough on paper: build a **pipeline tool** in Python that could parse KotOR models, display them in a live 3D viewport, handle textures and animations, and export back to game-compatible MDL. Something an artist could actually use alongside Blender.

What I didn't anticipate was how many layers that problem had.

---

## Week 1 — Planning & Architecture

### Defining the Scope

The first week was almost entirely planning. I mapped out the full pipeline on paper before writing a single line of code:

```
Game Archives (KEY/BIF/ERF/RIM)
    ↓
MDL Parser (binary + ASCII)
    ↓
Model Data (nodes, bones, meshes, animations)
    ↓
3D Viewport (software rasterizer, PIL buffer)
    ↓
Texture System (TGA, TPC/DXT, TXI metadata)
    ↓
Auto-Rigger (bone weight assignment)
    ↓
Exporters (OBJ, FBX, ASCII MDL)
```

The key architectural decision was using **Tkinter as the UI shell** with a **PIL ImageDraw software rasterizer** for the viewport — not a real-time GPU context. This was a deliberate tradeoff: Tkinter ships with Python, runs on every platform without a driver, and is easy to embed widgets around. The cost is raw performance, which I knew would become the central engineering challenge.

I planned five main modules:

| Module | Purpose |
|---|---|
| `src/core/mdl_parser.py` | Binary & ASCII MDL parsing |
| `src/core/model_data.py` | KotorModel, ModelNode, animation data |
| `src/gui/viewport.py` | 3D viewport widget (software rasterizer) |
| `src/gui/main_window.py` | Main application shell |
| `src/formats/` | GFF, TPC, TXI format readers/writers |

The project ended at **88 Python source files**, **~55,000 lines of code**, and a test suite of **1,750 collected tests (1,596 passing, 154 skipped)**.

### Choosing the Rasterizer Model

I spent two days evaluating whether to use OpenGL (via `PyOpenGL`) or a pure software path. The eventual answer was: **both**. A pure-PIL software rasterizer would handle the primary viewport — deterministic, cross-platform, easy to debug. A secondary `gpu_renderer.py` using **ModernGL/EGL** would be added later as a fast-path for systems that support it.

The software rasterizer design:
- Single PIL `Image` buffer per frame
- One `Canvas.create_image()` call per frame to Tkinter (no per-triangle Canvas items)
- Painter's algorithm (back-to-front sort) for transparency
- Per-triangle affine UV transforms via `Image.transform(AFFINE)`
- Background thread rendering to keep the UI responsive

---

## Week 2 — Core Development

### Parsing a 23-Year-Old Binary Format

The MDL binary format was humbling. It uses a **file pointer offset scheme** relative to the data section start (not the file start), with separate geometry and animation blocks. Many fields have no community documentation. I worked from PyKotor's source, ndixUR's MDLOps decompilation notes, and a lot of hex editor work.

The TPC texture format taught me a particularly memorable lesson. The 128-byte header has:

```python
# KotOR TPC header layout:
#   [12]  uint8  layers   — colour channel count
#   [13]  uint8  mip_count
#   [14]  uint8  encoding — 0=infer, 1=grey, 2=RGB/DXT1, 4=RGBA/DXT5
#   [15-127] reserved (all zeros in authentic TPC files)
```

I had the encoding byte at offset **12** instead of **14**. Two bytes off. The entire texture classification logic was wrong, and it produced results that were almost plausible — textures loaded, they just had subtly wrong colour channels. Finding this took most of a day.

The fix came from a KotOR community shortcut: **bytes 15–100 of real TPC files are always zero** (reserved header padding). TGA files are not. A fast pre-check on that range became the primary format detector, and the encoding math only runs as a fallback.

### The TXI Problem

KotOR's TPC textures secretly embed a second format at the end of the file — **TXI** — as raw ASCII text:

```
blending additive
numx 4
numy 4
fps 10
proceduretype cycle
bumpmaptexture lava_bump
```

This controls flipbook animation, additive blending (fire, glow effects), UV tiling, bump maps, and more. I had written a function `_extract_txi_from_tpc` early on — but there was no corresponding parser. The TXI bytes were being extracted into a string and then silently discarded. Fire effects rendered as solid opaque planes. Flipbook animations didn't animate. Building `_apply_txi_to_node` to actually parse and apply this metadata unlocked a huge chunk of visual fidelity in a single afternoon.

### Building the Software Rasterizer

`viewport.py` is the heart of the project — **6,077 lines** by the end of week five. The core design:

1. **Projection pass**: transform all vertices to screen space once per frame, cached in `_frame_verts_cache`.
2. **Triangle collection**: iterate all mesh nodes, build triangle list with depth (weighted centroid Z + face-index epsilon).
3. **Sort**: back-to-front painter sort for correct transparency.
4. **Draw**: per-triangle, either flat-shade with `ImageDraw.polygon()` or UV-textured with `Image.transform(AFFINE)`.

The textured path — `_draw_mesh_textured` and its per-triangle helper `_paste_textured_triangle` — became the primary engineering battleground for the rest of the project.

---

## Week 3 — Testing & First Optimization Round

### Building the Test Suite

By week three I had enough code that changes were beginning to break things unexpectedly. The solution was a structured test suite that grew alongside every fix. The final suite contains **37 test files** covering:

- Binary format round-trips (MDL parse → reserialize → re-parse)
- UV wrapping correctness (V-flip, seam crossing, tiling, sentinel filtering)
- Rendering visibility fixes
- Skin vertex transforms and bone weight calculations
- Animation engine controller parsing
- Crash audit tests (loading 2,500+ real game models without crashing)
- Thread safety on the render queue
- GFF reader/writer round-trips

The crash audit test was the most valuable single test. It loaded the full KotOR 1 game library — every model — and checked for zero crashes and zero uncaught exceptions. Running this after any significant change became the first sanity check. It caught dozens of edge cases that targeted unit tests would have missed.

```
tests/test_v46_full_crash_audit.py::test_load_all_k1_models PASSED (2,527 models, 0 crashes)
```

### The First Performance Reckoning

Profiling `_paste_textured_triangle` revealed the breakdown:

| Phase | Time (per triangle) | % of total |
|---|---|---|
| `Image.transform(AFFINE)` | ~276 µs | 72% |
| NumPy mask intersection | ~51 µs | 13% |
| `Image.paste()` | ~50 µs | 13% |
| Mask polygon draw | ~13 µs | 3% |

The affine transform is irreducible — it is doing real pixel work. But the mask pipeline was avoidable overhead. Each triangle was allocating a new `Image.new('L')`, drawing a polygon into it, converting to a NumPy array, running `np.minimum()` against the patch alpha, and converting back. The key insight: **PIL's `Image.transform(AFFINE)` already handles out-of-UV pixels correctly** when you pass `fillcolor=(0,0,0,0)`. The patch's own alpha channel — retrieved instantly with `patch.split()[3]` — is already the correct UV-boundary mask.

```python
# Before: ~64µs of polygon draw + numpy minimum
poly_mask = Image.new('L', patch.size, 0)
ImageDraw.Draw(poly_mask).polygon(screen_pts_local, fill=255)
if _NUMPY:
    arr_mask = np.array(poly_mask)
    arr_alpha = np.array(patch.split()[3])
    final_mask = Image.fromarray(np.minimum(arr_mask, arr_alpha))
else:
    final_mask = poly_mask

# After: ~0µs
final_mask = patch.split()[3]   # affine fillcolor already handles boundary
```

This single change reduced per-triangle time from **259 µs to 187 µs** — a 28% improvement on typical 30px triangles, without any loss of correctness.

---

## Week 4 — Deep Audit & Bug Hunting

### The UV Wrapping Problem

KotOR UV coordinates sometimes straddle the texture seam. A face might have vertices at `u = [0.97, 0.03, 0.50]` — two vertices on the right edge of the texture, one on the left. Without correction, the affine transform interpolates `u=0.97 → 0.03` going the **long way around** (through 0.5), producing a smeared diagonal band instead of a clean edge.

The seam-fix approach: detect a crossing edge, shift the wrapped vertex by ±1.0 so all three UVs are on the same side. The algorithm uses `_uwrap_global(base, other)` — pull `other` to within ±0.5 of `base`:

```python
def _uwrap_global(base: float, other: float) -> float:
    """Pull 'other' to within ±0.5 of 'base' (seam-crossing unwrap)."""
    diff = other - base
    if diff > 0.5:
        return other - 1.0
    if diff < -0.5:
        return other + 1.0
    return other
```

The existing guard for when to accept the fix was:

```python
# Old guard — accept if new span is < 70% of raw span
if new_span < _u_span_raw * 0.70:
    u1, u2 = u1_try, u2_try
```

This failed catastrophically for wide triangles. Take `u = [0.9, 0.1, 0.8]` — a face that genuinely spans 80% of the texture. The seam-detection code flags `u0→u1` as a crossing (distance 0.8 > 0.5). Wrapping `u1=0.1` around `u0=0.9` gives `u1_try = 1.1`. New span = `max(0.9, 1.1, 0.8) - min = 0.30`. Since `0.30 < 0.80 × 0.70 = 0.56`, the fix is accepted. Now PIL samples at `u=1.1 × 64px = 70.4px` — outside the texture — and the `fillcolor=(0,0,0,0)` produces a transparent (dark) corner.

Finding the correct guard required working through many cases systematically. The key insight came from examining where wrapped UVs land:

| Case | `u1_try` | Should fix? | Old guard | New guard |
|---|---|---|---|---|
| Wide: `[0.9, 0.1, 0.8]` | 1.10 | NO | accept ❌ | reject ✅ |
| Seam: `[0.95, 0.02, 0.98]` | 1.02 | YES | accept ✅ | accept ✅ |
| KotOR: `[0.96, 0.01, 0.99]` | 1.01 | YES | accept ✅ | accept ✅ |
| Near-seam: `[0.93, 0.07, 0.5]` | 1.07 | YES | accept ✅ | accept ✅ |

The pattern: genuine seam faces wrap `u1` to just over 1.0 (e.g., 1.01–1.07). Wide faces wrap it to exactly 1.1. The correct guard is an **absolute bounds check**:

```python
# New guard — accept only if wrapped UVs stay within (-0.1, 1.1) strictly
if (u1_try > -0.1 and u1_try < 1.1) and (u2_try > -0.1 and u2_try < 1.1):
    if new_span < _u_span_raw * 0.70:
        u1, u2 = u1_try, u2_try
```

The wide case `u1_try = 1.1` fails the strict `< 1.1` check and is correctly rejected.

### The Invisible Flag

While investigating viewport lag during orbit dragging, I discovered that `_lq_tex_mode` — a flag on `FrameRenderer` that switches full-resolution textures for half-resolution mip1 versions — **had never been set to True** anywhere in the widget code. The mip1 cache, the `get_mip1()` method, the LOD switching logic in `_draw_mesh_textured` — all of it was implemented and dormant.

The intent was a two-pass progressive render: on drag release, show a fast LQ frame using half-res textures (~50% faster), then queue a full-quality HQ frame. But the flag was never wired to the drag release event.

```python
# _release_lmb — what it should have done all along
self._renderer.is_interactive = False
self._renderer._lq_tex_mode = True    # enable mip1 for first post-drag frame
self._lq_pending_hq = True            # flag: schedule HQ follow-up after LQ
self._request_render()

# _schedule_render — after LQ frame arrives
if getattr(self, '_lq_pending_hq', False) and self._renderer._lq_tex_mode:
    self._renderer._lq_tex_mode = False
    self._lq_pending_hq = False
    self._request_render()            # queue the HQ follow-up
```

This meant the viewport was doing a full-resolution textured render immediately after every drag event — the slow path, every time. The fix was three lines in `_release_lmb` and five lines in `_schedule_render`.

### Watchdog, Memory Pressure, and Thread Safety

Week four also addressed several stability issues:

- **Render watchdog**: a background timer resets the `_render_in_progress` flag if a render runs more than 8 seconds, unblocking the UI after complex LBS model first-frame renders (which can legitimately take 4–6 seconds)
- **Memory pressure handling**: if `MemoryError` is raised during a render, the triangle caps are automatically halved (down to a floor of 5,000) and logged — the app degrades gracefully instead of crashing
- **Thread-safe queue**: render results are placed into a capacity-2 queue; if full, the oldest result is dropped before inserting the new one, preventing memory growth during fast interaction

---

## Week 5 — Integration, Final Testing & Reflection

### Closing the Loop

Week five was integration and polish. The GPU renderer (`gpu_renderer.py`, 1,212 lines) was added as an optional fast-path using ModernGL with EGL context creation for headless environments. The auto-rigger (`accurig.py`, 1,114 lines) was validated against the full K1 humanoid skeleton. The OBJ/FBX import and ASCII MDL export paths were stress-tested against community model archives.

The final test run:

```
1596 passed, 154 skipped in 29.19s
```

The 154 skipped tests are GPU-renderer tests that require an EGL context, and full-game audit tests that require an actual game installation — both expected and documented.

### Performance — Where We Landed

| Metric | Week 3 Baseline | Week 5 Final | Delta |
|---|---|---|---|
| Tiny tri (30px), per-triangle | 259 µs | 187 µs | **-28%** |
| Medium tri (100px), per-triangle | 762 µs | 673 µs | **-12%** |
| Non-white shade path | ~270 µs | 184 µs | **-32%** |
| Projected frame (2,000 tris) | ~520 ms | ~374 ms | **-28%** |
| Drag-release LQ frame | ~520 ms | ~260 ms | **-50%** (mip1) |

The practical result: textured viewport rendering at 2,000 triangles runs at roughly 2–3 fps in high-quality mode, which is the expected ceiling for a pure-PIL software rasterizer. During drag, the flat-shaded LOD path runs at ~60 fps. The two-pass progressive render makes the drag-release transition feel instant — the LQ frame arrives in ~260 ms and the HQ frame follows in ~520 ms, rather than a single 520 ms freeze.

---

## Reflection and Gratitude

### What I Actually Learned

Looking back, the five weeks taught me things that I couldn't have predicted going in:

**The value of profiling before optimizing.** The first instinct on a slow renderer is to reach for NumPy or Cython. Profiling revealed that the dominant cost was `Image.transform(AFFINE)` — genuinely irreducible pixel math — and that the second-biggest cost was an entirely unnecessary polygon draw that I could eliminate for free. Without numbers, I would have spent a week on the wrong problem.

**Systematic test design catches what targeted tests miss.** The crash audit test — loading 2,527 game models and checking for zero crashes — found categories of bugs that no amount of targeted unit testing would have surfaced. Edge cases in binary format parsing don't follow a pattern you can predict in advance. Throwing real data at the system is irreplaceable.

**The importance of reading the code you didn't write.** `_lq_tex_mode` was implemented correctly. The mip1 cache was implemented correctly. The flag was just never set. This kind of bug — where all the infrastructure exists but the wiring is missing — only reveals itself when you read the entire call chain from event handler to render thread, not just the function you're currently working on. The discipline of tracing the full path, even when it's 6,000 lines, is non-negotiable.

**Guards and thresholds need proof, not intuition.** The seam fix guard went through five iterations before it was correct. Each iteration was motivated by a case I hadn't considered. Building a systematic table of test cases — wide triangles, seam triangles, near-seam triangles, very-wide triangles, normal triangles — and verifying each one against the expected result before changing any code was what finally produced a guard that was provably correct.

**Clean architecture pays back slowly, then all at once.** The separation between `FrameRenderer` (pure rendering logic) and `ViewportWidget` (Tkinter event handling) made it possible to profile and test rendering in isolation, without a running UI. The background thread design made it possible to add the two-pass progressive render without touching the event loop at all. These decisions felt like overhead in week one. By week five they were load-bearing.

### On the Challenge

The moment that most improved my confidence as a programmer happened at the end of week four. I had a systematic test showing the seam-fix guard failed. I had a table of five cases. I had a clear description of why the ratio-based guard was insufficient. And I had no idea what the correct fix was.

The temptation was to search for a formula — some mathematical property that separates seam faces from wide faces. What actually solved it was accepting that the property I needed was **geometric**, not algebraic: the question isn't "is the span ratio small enough?" but "would the fixed UVs sample inside the texture?" The bounds check `(u1_try > -0.1 and u1_try < 1.1)` is not a clever heuristic. It is a direct statement of what we actually need to be true.

Getting to that answer required being wrong four times first.

### Thank You

To the KotOR modding community — specifically **ndixUR** (MDLOps), the **PyKotor** contributors, and the researchers at **Xoreos** whose reverse-engineering work made binary format parsing possible at all. Twenty years of community knowledge went into the documentation that made this project viable.

To the Pillow and NumPy maintainers, whose libraries underpin everything here.

And to whoever wrote the KotOR TPC format spec comment in the PyKotor source noting that bytes 15–100 of a real TPC file are always zero — you saved me at least a day.

---

## Project Links

- **GitHub**: [github.com/CrispyW0nton/Kotor-3D-Model-Converter](https://github.com/CrispyW0nton/Kotor-3D-Model-Converter)
- **Pull Request v10.3**: [PR #1 — UV wrapping seam guard + drag lag progressive render](https://github.com/CrispyW0nton/Kotor-3D-Model-Converter/pull/1)

---

*GhostRigger-K1-K2 · Python 3.10 · Pillow · NumPy · Tkinter · PyOpenGL · ModernGL*
*1,596 tests passing · 55,000 lines · 88 source files · 5 weeks*

