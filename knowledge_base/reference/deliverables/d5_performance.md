# Deliverable 5: Performance & Memory
# ======================================
# File: src/resources/resource_manager.py, src/gui/gpu_renderer.py
# Priority: MEDIUM | Effort: ~24 hours | Risk: MEDIUM

## Problem Statement
Multiple cache layers (raw bytes, PIL images, NumPy arrays, GL textures) cause memory duplication.
Override files are pre-loaded fully. GPU texture cache (MAX_ENTRIES=512) uses ~341 MB VRAM.
No lazy loading, no eviction, no memory budgets.

## Tasks (from roadmap spreadsheet)
| Task | Description | Hours | Files | Acceptance |
|------|------------|-------|-------|------------|
| T601 | Texture cache with LRU eviction | 8 | resource_manager.py, gpu_renderer.py | Evicts least-recently-used when budget exceeded |
| T602 | Lazy loading | 6 | resource_manager.py | Textures loaded on first access, not startup |
| T603 | Frustum culling | 4 | gpu_renderer.py | Off-screen meshes not rendered |
| T604 | Background decoding | 6 | resource_manager.py | Texture decode on separate thread |

## Book Principles (Gregory Ch 7.2 - Resource Manager)
- **Lazy loading**: Don't load until first reference; placeholder texture until ready
- **Reference counting**: Track active users; eligible for eviction when refcount=0
- **LRU eviction**: When memory budget exceeded, evict least-recently-used unreferenced resources
- **Memory budgets**: Set limits per tier (CPU RAM for textures, VRAM for GL textures)
- **Streaming**: Decode/upload textures asynchronously to avoid frame hitches

## Cache Architecture
```
Tier 1: Disk (game data files) - unlimited
  |
  v [lazy load on first access]
Tier 2: CPU Memory (decoded PIL/NumPy arrays) - budget: 512 MB
  |
  v [upload to GPU on first render]
Tier 3: GPU Memory (OpenGL textures) - budget: 256 MB VRAM
```

## Acceptance Criteria
1. Memory usage stays within budgets under sustained use
2. No frame hitches during texture loading (background decode)
3. LRU eviction correctly frees oldest unreferenced textures
4. Frustum culling skips off-screen meshes (measurable fps gain)
