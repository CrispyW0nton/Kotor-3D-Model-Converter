# GhostRigger.Renderer.Backend.ModernGL

Phase 1 native renderer package boundary for the existing ModernGL renderer
surface.

- Owner surface: Main Viewport/KMAX renderer backend.
- Owner package: `native/GhostRigger.Renderer.Backend.ModernGL`.
- Bridge method: C ABI DLL for version, capability, backend-info, and adapter
  bridge metadata.
- Data ownership: C++ owns future renderer-package diagnostics, backend
  selection metadata, and native bridge contracts. Python owns the current
  ModernGL context, Qt surface integration, shader/runtime objects, and visible
  viewport workflow until a later parity gate moves ownership.
- Verification: `GhostRigger.Renderer.Backend.ModernGL` `Debug|x64` build, targeted Python package
  registry tests, and visible app checks only when future slices alter viewport
  behavior.

This package is diagnostic-only in Phase 1. It does not create a ModernGL
context or record draw commands.
