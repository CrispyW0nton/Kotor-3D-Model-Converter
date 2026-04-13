# Deliverable 2: Texture Wrapping Fix
# =====================================
# File: src/gui/viewport.py (~9,323 lines), src/gui/gpu_renderer.py
# Priority: HIGH | Effort: ~16 hours | Risk: MEDIUM

## Problem Statement
Module textures (floors, walls, terrain) that should tile/repeat are broken.
The UV sentinel filter (`_UV_SENTINEL = 100.0`) and `np.clip()` prevent proper tiling.
Textures clamp instead of repeating, causing visible seams and incorrect appearance.

## Root Cause Analysis
1. `_UV_SENTINEL = 100.0`: Any UV coordinate > 100 is filtered out (but module UVs legitimately exceed 1.0 for tiling)
2. `np.clip(uv, 0.0, 1.0)`: Forces all UVs into [0,1] range, destroying repeat information
3. No TXI metadata support: The `.txi` sidecar files specify `clamp 1` or `decal 1` but are ignored
4. Module-specific workaround code adds complexity without fixing the real issue

## Required Fix (from dev brief)
1. **Remove UV sentinel**: Delete the `_UV_SENTINEL = 100.0` constant and all magnitude-based UV filtering
2. **Replace np.clip with frac()**: Use `uv = uv % 1.0` (Python) or `fract(uv)` (GLSL) for repeat behavior
3. **Add TXI clamp support**: Parse TXI metadata; when `clamp 1`, use `np.clip` / `GL_CLAMP_TO_EDGE`
4. **Drop module workaround**: Remove any special-case code for module textures

## Tasks (from roadmap spreadsheet)
| Task | Description | Hours | Files | Acceptance |
|------|------------|-------|-------|------------|
| T201 | Remove UV sentinel logic | 4 | viewport.py | No _UV_SENTINEL constant; no magnitude filter |
| T202 | Implement frac() UV repeat | 4 | viewport.py, gpu_renderer.py | UVs > 1.0 tile correctly |
| T203 | Add TXI clamp/decal support | 4 | viewport.py, model_data.py | TXI `clamp 1` -> clamp mode |
| T204 | Remove module workaround | 4 | viewport.py | No special-case module UV code |

## Cross-Reference Repos to Study BEFORE Coding
1. **KotOR.js** (`resource/tpc/TPCObject.ts`): How TPC textures store wrap mode
   - Look for `clampMode`, `GL_REPEAT`, `GL_CLAMP_TO_EDGE` usage
2. **reone** (`src/libs/graphics/texture.cpp`): TXI parsing and texture parameter setup
3. **PyKotor** (`resource/formats/tpc/io_tpc.py`): TPC/TXI format parsing

## Book Principles (MUST follow)
- **Hayes Ch 7 (Textures)**:
  - GL_REPEAT: `texCoord = fract(texCoord)` — values > 1.0 wrap around
  - GL_CLAMP_TO_EDGE: values outside [0,1] snap to edge texels (no border color)
  - GL_MIRRORED_REPEAT: alternating mirror pattern
  - Mipmap filtering: `GL_LINEAR_MIPMAP_LINEAR` for best quality
- **Hayes Ch 7 (Texture Parameters)**:
  - `glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)`
  - `glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)`
  - Set per-texture based on TXI metadata

## CPU Renderer Fix (viewport.py)
```python
# BEFORE (broken):
_UV_SENTINEL = 100.0
uv = np.clip(uv, 0.0, 1.0)

# AFTER (correct):
# For repeat mode (default):
uv_repeat = np.mod(uv, 1.0)  # equivalent to frac()
# For clamp mode (when TXI says clamp=1):
uv_clamp = np.clip(uv, 0.0, 1.0)
# Choose based on texture's TXI metadata:
uv_final = uv_clamp if texture.txi_clamp else uv_repeat
```

## GPU Renderer Fix (gpu_renderer.py)
```glsl
// In fragment shader - no code change needed if texture parameters are set correctly
// The GPU handles wrap modes via glTexParameteri
// Just ensure proper parameter setting when uploading texture:
// GL_REPEAT for tiling textures (default)
// GL_CLAMP_TO_EDGE for TXI clamp=1 textures
```

## Acceptance Criteria
1. Module floor/wall textures tile correctly (visible repeating pattern)
2. Character textures (skin, armor) still display correctly (no tiling artifacts)
3. TXI `clamp 1` textures use clamp-to-edge behavior
4. No UV sentinel constant exists in codebase
5. No np.clip on UV coordinates for repeat-mode textures
6. Both CPU and GPU renderers produce matching results
