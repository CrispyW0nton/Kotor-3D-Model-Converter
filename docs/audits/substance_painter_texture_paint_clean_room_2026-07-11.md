# Substance Painter clean-room study for Map Studio texture painting

Date: 2026-07-11  
Owner: LordVaderCW  
Scope: Map Studio diffuse-texture painting, viewport feedback, undo, and KOTOR export

## Evidence inspected

The locally installed `Adobe Substance 3D Painter.exe` 11.1.1 was inspected
with Ghidra 12.1.2 as a clean-room product/architecture study. The analyzed
main executable has SHA-256
`e0f1b67db8b824003d3cc1fc90ac66a58c0da80489f6b882b9636b9d1d8c39ad`.
The study also covered its shipped Substance CPU blend, Vulkan abstraction,
and graph-linker libraries. Ghidra project summaries are retained under
`C:/Users/NewAdmin/Documents/GDeveloper/Workspaces/Ghidra/projects/active/`
in the `substance-painter-11-*` projects.

No Adobe code, data structures, shaders, or assets were copied. The useful
interoperability lessons came from program boundaries, exported engine APIs,
resource ownership, scheduling structure, and observed editor behavior.

## Product lessons applied

1. A pointer drag is one paint transaction. Samples are distance-resampled
   into deterministic stamps, live feedback is incremental, and the complete
   drag becomes one undo item.
2. The editable paint document is separate from renderer residency. Painting
   changes only dirty UV tiles; it does not rebuild the mesh, reload the scene,
   clear unrelated textures, or reset the camera/framebuffer.
3. A 3D brush begins with the closest visible surface hit. Perspective-correct
   barycentric UV interpolation drives the stamp, so geometry behind the front
   surface cannot receive the stroke.
4. Diffuse RGB is composited in linear light and stored as sRGB. Alpha remains
   a data channel. The authored diffuse UV channel is independent from KOTOR
   lightmap UVs, which are preserved.
5. Expensive flattening and serialization happen at the transaction boundary,
   not for every pointer sample. The viewport receives small dirty-region
   uploads while the KMAP stores references and compact metadata rather than
   image blobs.
6. Imported and game-library textures can act as brush stamps, but painting
   targets a unique project-owned texture so stock game resources are never
   silently overwritten.

## Ghost Studio implementation

- `map_studio_texture_paint.py` owns the headless stamp engine, 64-pixel dirty
  tiles, pressure, opacity, flow, hardness, spacing, UV wrapping, linear-light
  compositing, and stroke undo/redo.
- `map_studio_texture_assets.py` owns reference-heavy KMAP sidecars, image
  import, atomic TGA/TXI persistence, safe KOTOR resrefs, and export resources.
- The Map Studio paint tab exposes target import/assignment, game or project
  stamp sources, brush controls, paint activation, and status guidance.
- The depth-correct hover service supplies the nearest visible face and
  perspective-correct UV. Backdrop/skybox preview geometry is intentionally
  visible but non-pickable.
- Renderer backends expose targeted texture-region updates. ModernGL writes
  only the affected bytes and regenerates mipmaps; other backends invalidate
  only the named texture/material dependency.
- Authored module export bundles the painted TGA/TXI and the room MDL retains
  the matching texture resref. K1 and K2 archive readback tests cover the
  custom texture resource.

## Current boundary

This pass is the first usable diffuse-paint workflow, not a claim of complete
Substance parity. It intentionally starts with one active flattened paint
layer and diffuse UV0. A future phase can add a non-destructive layer DAG,
masks, channel sets, projection modes, clone/heal tools, and bake workflows.
Those additions must keep the same dirty-tile, one-transaction-per-drag, and
KOTOR export/readback contracts.

Headless and archive readback tests prove the implemented data path. A visible
Debug-app pass also opened the Paint controls, created and sculpted a terrain
heightfield, regenerated its 32-triangle WOK through the real Walkmesh action,
validated it, and exited cleanly. A manual KOTOR warp remains the separate
required proof before the workflow is described as in-game verified.

## Transaction and export hardening

The initial workflow was subsequently integrated into Map Studio's global
command history through a project-bound sidecar journal. A same-size texture
stroke records only changed TGA byte spans over one lazily captured baseline;
full payload snapshots are reserved for create, delete, resize, and import
operations. Undo and redo therefore remain chronological after Paint mode or
the active target changes, while sparse large-texture strokes do not duplicate
the full image. The journal verifies expected file existence, size, SHA-256,
span bounds, 32-bit uncompressed top-left TGA layout, and dimensions before it
mutates a sidecar. Incomplete dirty hints fall back to a complete changed-block
diff, and any external edit or apply failure rejects the operation atomically
and restores the history/session state.

Closest-visible picking now consumes KOTOR per-corner `face_uvs`, rather than
assuming one UV per geometric vertex, so a brush crossing a duplicated UV seam
cannot be projected through an unrelated corner. Export preflight validates
only custom project textures actually referenced by rooms, but treats invalid
resrefs, unreadable/empty image or TXI resources, duplicate used resrefs, and
generated-versus-extra `(resref, restype)` collisions as blocking errors.
Distinct TGA and TXI resources sharing one valid resref remain the supported
material pair. The final merged K1/K2 resource map is checked against engine
resource contracts before the archive is written.
