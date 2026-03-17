# GhostRigger Dev Log — March 10, 2026
## Texture Mapping: Spent All Day Arguing With A 128-Byte Header

*Posted to the GhostRigger-K1-K2 project blog*

---

So. Today was one of those dev days where you feel like you've conquered the universe around 11am, and then the universe reminds you it's 23 years old and was compiled in 2002 and doesn't care about your feelings.

The mission: **full KOTOR texture mapping support**. TPC files, TXI metadata, flipbook UVs, multiple UV sets, the whole enchilada. Let's talk about what we actually shipped, what's working great, and what is still kind of... not.

---

### The TPC Header: A Masterclass In Subtle Wrongness

KotOR stores its textures in a proprietary format called TPC. It has a tidy 128-byte header. What could go wrong?

Well. We had the encoding byte at offset 12. It is at offset 14. Offset 12 is the *layers/channel count*. This single byte being two positions off meant the entire format detection logic was classifying textures wrong. The fix was humbling:

```python
# KotOR TPC header layout (128 bytes, BioWare format):
#   [12]  uint8  layers   – colour channel count (1=L, 2=LA/DXT1, 3=RGB, 4=RGBA/DXT5)
#   [13]  uint8  mip_count
#   [14]  uint8  encoding – 0=infer, 1=grey, 2=RGB or DXT1, 4=RGBA or DXT5, 10/12/13/14=DXT variants
#   [15-127] reserved (all zeros in authentic TPC files)

layers  = data[12]   # was: data[14]  ← the bug
mips    = data[13]
enc     = data[14]   # CORRECTED
```

We also discovered a lovely shortcut courtesy of PyKotor: real TPC files have bytes 15–100 ALL ZERO (it's the reserved header padding). TGA files don't. So now the fast-path detection just checks that, and we only fall back to encoding math if that fails. Clean.

---

### TXI: The Metadata Format That Lives Inside Another Format

TPC files secretly have a second format embedded at the end — after all the mipmap pixel data — called TXI. It's just ASCII text with commands like:

```
blending additive
numx 4
numy 4
fps 10
proceduretype cycle
bumpmaptexture lava_bump
```

The problem: we had a function `_extract_txi_from_tpc` that found the TXI bytes — but nothing that actually *parsed* them into usable data. The TXI string was getting extracted into a void and then politely ignored.

Today we fixed that. Here's the full pipeline now:

```python
def _apply_txi_to_node(node, txi_str: str) -> None:
    """Parse TXI string and apply metadata fields to a ModelNode."""
    if not txi_str:
        return
    meta = _parse_txi_string(txi_str)

    if meta['blending']:
        node.txi_blending = meta['blending']      # 0=none, 1=additive, 2=punchthrough
    if meta['cube']:
        node.txi_cube = True                       # environment/cubemap flag
    if meta['numx'] > 0:
        node.txi_numx = meta['numx']               # flipbook columns
    if meta['numy'] > 0:
        node.txi_numy = meta['numy']               # flipbook rows
    if meta['fps'] > 0.0:
        node.txi_fps = meta['fps']
    if meta['bumpmaptexture']:
        node.txi_bumpmaptexture = meta['bumpmaptexture']
        node.bump_map = meta['bumpmaptexture']     # also update the existing field
    if meta['clamp_s']:
        node.txi_clamp_s = True
    if meta['clamp_t']:
        node.txi_clamp_t = True
```

We added **13 new fields** to `ModelNode` for TXI data, plus 2 new UV set fields (`uvs_2`, `uvs_3`). The dataclass now looks like this in the relevant section:

```python
uvs_2:            List[Tuple[float,float]]  = field(default_factory=list)
uvs_3:            List[Tuple[float,float]]  = field(default_factory=list)
# ...
txi_blending:     int   = 0       # 0=none 1=additive 2=punchthrough
txi_cube:         bool  = False
txi_proceduretype:str   = ''      # 'cycle', 'water', 'arturo', etc.
txi_numx:         int   = 0       # flipbook columns
txi_numy:         int   = 0       # flipbook rows
txi_fps:          float = 0.0
txi_envmaptexture:str   = ''
txi_bumpmaptexture:str  = ''
txi_bumpmapscaling:float= 1.0
txi_rotate:       float = 0.0     # extra UV rotation in degrees from TXI
txi_loop:         bool  = True
txi_clamp_s:      bool  = False   # False=GL_REPEAT, True=clamp-to-edge
txi_clamp_t:      bool  = False
```

---

### UV Sets: Yes, There Are Four Of Them

KOTOR meshes support four UV channels. UV0 is your standard diffuse texture. UV1 is for lightmaps. UV2 and UV3 exist but vanilla KotOR largely ignores them (modding community does use them though).

The MDL parser was already reading the MDX channel offsets for UV2 and UV3 (`mdx_t2_off`, `mdx_t3_off`) but then... doing absolutely nothing with them. They were just logged in a debug string and forgotten. Today we actually wire them through:

```python
# MDX channel offsets (0xFFFFFFFF = absent)
mdx_v_off   = _ru32(d,o); o+=4   # vertex positions
mdx_n_off   = _ru32(d,o); o+=4   # normals
mdx_vc_off  = _ru32(d,o); o+=4   # vertex colors
mdx_t1_off  = _ru32(d,o); o+=4   # UV set 1 (diffuse)
mdx_lm_off  = _ru32(d,o); o+=4   # lightmap UV
mdx_t2_off  = _ru32(d,o); o+=4   # UV set 2  ← now stored on node.uvs_2
mdx_t3_off  = _ru32(d,o); o+=4   # UV set 3  ← now stored on node.uvs_3
mdx_bmp_off = _ru32(d,o); o+=4   # bump map channel
```

---

### Flipbook UVs: When Your Texture Is Actually 16 Textures

Some KOTOR textures (fire, electricity, splash effects) are sprite sheets. They use TXI's `numx`/`numy` to divide the image into a grid of animation frames. We now compute per-frame UV remapping:

```python
def _compute_flipbook_uv(u, v, numx, numy, frame):
    """Remap UV coords to the correct cell in a flipbook sprite sheet."""
    total_frames = numx * numy
    frame = frame % total_frames
    col = frame % numx
    row = frame // numx
    cell_w = 1.0 / numx
    cell_h = 1.0 / numy
    u_out = (col + (u % 1.0)) * cell_w
    v_out = (row + (v % 1.0)) * cell_h
    return u_out, v_out
```

This one had a sneaky off-by-one bug in the test: the expected `v` value for frame 8 in an 8×4 grid (`row = 8 // 8 = 1`, not 2) was wrong in the test itself. Classic.

---

### Test Results: The Part That Actually Felt Good

We shipped **99 new tests** covering all of today's work:

```
============================== 99 passed in 0.39s ==============================
```

Full suite:

```
1425 passed, 154 skipped, 0 failures  (was 1326 before today)
```

The test classes cover: TPC header detection, TPC pixel format loading (DXT1/DXT5/greyscale/RGB/RGBA), TXI string parsing, TXI-to-node application, flipbook UV math, clamp mode logic, UV2/UV3 field storage, additive/punchthrough blending, and TextureCache TXI loading with thread-safety checks.

---

### What's Still Broken (And We're Not Going To Pretend Otherwise)

**Lightmap rendering is not live yet.** We parse the lightmap UV channel (`uvs_lm`), we store the lightmap texture name, we have a `has_lightmap` flag — but the 3D viewport doesn't actually *composite* the lightmap onto the mesh. You get the diffuse texture only. KOTOR uses a classic two-pass lightmap bake and we haven't wired up the second texture pass in the software rasterizer yet.

**Additive blending in the viewport is approximate.** We halve `node_alpha` for additive-blended nodes as a cheap approximation, since our PIL-based rasterizer doesn't natively do GPU-style additive blending. Fire and electricity effects will look dimmer than in-game. It's on the list.

**Cubemaps don't render as cubemaps.** If a TPC is a cubemap (6 faces stacked vertically, height = 6×width), we detect it correctly and set `txi_cube = True` — but then we just... show the flat unwrapped image in the UV viewer. Actual cubemap sampling in a software renderer is a whole project on its own.

**K1 vs K2 header offset drift.** KOTOR 2 adds 8 extra bytes to the mesh node header (`dirt_enabled`, `dirt_texture`, `dirt_coord_space`, `hide_in_holograms`). We handle that now, but there are still edge cases where K2 models shift the read cursor and produce garbage UV offsets for a handful of node types. You'll notice it on some K2 creature models where the mouth texture wraps around somewhere anatomically creative.

---

### The File That Contains Multitudes

`src/gui/viewport.py` is now **5,677 lines**. It started as a simple "draw some triangles" module. It now contains: a software rasterizer, a TPC decoder, a TXI parser, a flipbook UV engine, an arcball camera, texture and mip caches with threading, a UV viewer window, a bone skeleton overlay, an animation playback system, and HUD rendering. It is one Python file and it is thriving and we are fine.

---

### What's Next

- **Lightmap compositing** — two-texture pass in the rasterizer
- **ERF archive loading** — load TPC directly from `.erf`/`.bif` without unpacking
- **Additive blend pass** — proper back-buffer compositing for fire/FX nodes  
- **Validate on actual game files** — extract `drroo.mdl` + its textures, modify a UV, repack, verify in-game

Commits are clean, tests are green, the 128-byte header is finally respected. See you in the next devlog when we inevitably discover the lightmap UV channel is stored upside down.
