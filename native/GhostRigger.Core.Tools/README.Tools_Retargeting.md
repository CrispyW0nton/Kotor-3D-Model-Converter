# GhostRigger.Core.Tools

Owner surface: Retarget Workbench
Owner package: `native/GhostRigger.Core.Tools`
Bridge method: C ABI DLL first; `.pyd` only if the C ABI contract proves too narrow.

Data ownership:
- C++ owns: hot pose-palette blending helpers, numeric retarget solve packets, solver diagnostics, and future batch validation helpers.
- Python owns: KOTOR animation source selection, UI state, user workflow, export policy, project/session persistence, and MCP-backed truth checks.

Verification:
- Native Debug target: build `GhostRigger.Core.Tools` in `Debug|x64` through `GhostRigger.sln`.
- Python adapter test: targeted package availability and missing-DLL fallback checks.
- Visible app check: skipped for this Phase 1 package-boundary slice because no UI/workflow behavior changes.
