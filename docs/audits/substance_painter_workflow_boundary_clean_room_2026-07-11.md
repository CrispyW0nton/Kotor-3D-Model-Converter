# Substance Painter workflow-boundary deep pass for GhostStudio

Date: 2026-07-11  
Owner: LordVaderCW  
Scope: texture-paint input, undo, layer architecture, dirty-region updates,
resource residency, and bake jobs

## Evidence and limits

The locally installed Adobe Substance 3D Painter 11.1.1 executable (SHA-256
`e0f1b67db8b824003d3cc1fc90ac66a58c0da80489f6b882b9636b9d1d8c39ad`)
and its bundled 9.2.5 CPU blend, linker, and Vulkan SAL libraries were inspected
with Ghidra 12.1.2. Exact component hashes and representative addresses are in
`C:/Users/NewAdmin/Documents/GDeveloper/Workspaces/Ghidra/projects/active/substance-painter-11-main-triage/exports/clean-room-synthesis.md`.

No Adobe code, shaders, structures, or assets were copied. The large Painter
host does not yield trustworthy static control flow in this build; host imports
and read-only names are used only as boundary evidence. The smaller engine DLLs
provide the reliable named lifecycle/control-flow surface.

## Strong observations

- Pointer/tablet pressure, device type, and timestamps exist at the Qt input
  boundary.
- Qt exposes mergeable commands, undo macros, multiple undo stacks/groups, and
  clean/dirty history state to the host.
- The CPU and Vulkan engines share a context/handle API with explicit init,
  start/stop, input/output submission, state, flush, synchronization labels,
  texture release, and cache transfer.
- The linker separates a graph assembly from output selection/format and exposes
  graph connections, input fusion/constification, metrics, backend enumeration,
  and cache mapping.
- The baker surface separates mesh/texture registries and revisions from bake
  job create/begin/status/wait/cancel/output/release.
- Tiled texture descriptor/residency-provider APIs exist at the bake/resource
  boundary.

These observations justify architecture boundaries. They do not reveal the
proprietary brush kernel, layer schema, or exact tile policy.

## Required GhostStudio behavior

1. Preserve four distinct owners:
   - authored texture/layer document;
   - global transaction/history journal;
   - material/bake evaluation graph;
   - backend texture residency/cache.
2. A drag is a `StrokeTransaction`: timestamped/pressure-bearing pointer samples
   are deterministically resampled into stamps, previewed incrementally, and
   committed as one undo record on release. Undo must remain chronological with
   terrain, modeling, placement, and lighting actions.
3. Dirty texels are accumulated into revisioned rectangles/tiles. The renderer
   receives targeted region uploads; it must not rebuild room meshes, clear the
   scene, reset the camera, or invalidate unrelated materials.
4. Add a non-destructive layer document above the existing flattened diffuse
   paint target: stable IDs, paint/fill/group/mask types, visibility, opacity,
   blend mode, channel enablement, reorder, duplicate, merge, and mask links.
   Flatten only for preview/export.
5. Bake jobs consume immutable mesh/material revisions and expose progress,
   cancellation, diagnostics, and outputs. Stale results are discarded if the
   mesh, UVs, material, or layer graph changed while the job ran.
6. CPU image data is authoritative. ModernGL, Vulkan/WGPU, software, and future
   native renderers consume the same update contract and must pass parity tests.
7. Texture resource identity is explicit from discovery through decode,
   authoring, cache, and export. Stock game assets remain read-only; painting
   creates project-owned resrefs.

## KOTOR export boundary

Modern authoring still terminates in KOTOR's supported data: diffuse UV0,
lightmap UV1, TGA/TPC plus TXI metadata, safe resrefs, MDL material references,
and MOD/RIM resources. Layer/channel flattening must be deterministic and
validated. Headless archive readback is required, and a manual game warp remains
the final proof for any "works in KOTOR" claim.

## Explicitly unsupported

This study does not establish Painter's exact dab spacing, smoothing, pressure
curve, blend equations, color pipeline, layer file format, tile dimensions,
residency eviction, shader code, bake algorithm, thread count, frame timing, or
undo grouping. GhostStudio must specify and benchmark those behaviors itself.

