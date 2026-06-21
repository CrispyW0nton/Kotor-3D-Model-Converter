# GhostRigger.Core.Tools

Phase 1 native window package boundary for the Level Editor window.

- Owner surface: Level Editor
- Owner package: `native/GhostRigger.Core.Tools`
- Bridge method: C ABI DLL
- Owner: LordVaderCW
- Intersects: Phase 1 native window/package boundaries, Level Editor host-service metadata, Visual Studio solution packaging, and future native window-shell adoption.

This package is diagnostic-only in Phase 1. It exports version, capability, owner-boundary, and host-service schema metadata while Python/Qt continues to own the visible Level Editor workflow.
