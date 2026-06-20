# GhostRigger.Core.Tools

Phase 1 native toolbox package boundary for export and validation helpers.

- Owner surface: Export and validation workflow.
- Owner package: `native/GhostRigger.Core.Tools`.
- Bridge method: C ABI DLL.
- Data ownership: C++ owns diagnostic readback, packed-buffer validation, and
  export preflight packet metadata. Python owns export decisions, write prompts,
  file-format policy, game-resource semantics, and final writer orchestration.
- Verification: `GhostRigger.Core.Tools` `Debug|x64` build, targeted Python package
  registry tests, backend truth checks before any native helper becomes
  authoritative, and visible app checks only when UI/workflow behavior changes.

This package is diagnostic-only in Phase 1. It must not write product files or
replace Python export policy until parity gates are defined and passed.
