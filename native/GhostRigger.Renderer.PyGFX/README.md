# GhostRigger.Renderer.PyGFX

Phase 1 native renderer package boundary for the existing PyGFX/WGPU renderer
surface.

- Owner surface: Main Viewport/KMAX renderer backend.
- Owner package: `native/GhostRigger.Renderer.PyGFX`.
- Bridge method: C ABI DLL for version, capability, backend-info, and adapter
  bridge metadata.
- Data ownership: C++ owns future renderer-package diagnostics, backend
  selection metadata, and native bridge contracts. Python owns the current
  PyGFX/WGPU scene, Qt surface integration, renderer objects, and visible
  viewport workflow until a later parity gate moves ownership.
- Verification: `GhostRigger.Renderer.PyGFX` `Debug|x64` build, targeted Python package
  registry tests, and visible app checks only when future slices alter viewport
  behavior.

This package is diagnostic-only in Phase 1. It does not create a PyGFX renderer,
WGPU device, or record draw commands.
