# GhostRigger.Core.Tools

Phase 1 native toolbox package boundary for the Resource Browser.

- Owner surface: Resource Browser.
- Owner package: `native/GhostRigger.Core.Tools`.
- Bridge method: C ABI DLL.
- Data ownership: C++ owns future resource catalogue diagnostics, resource row
  packet metadata, and filter helper contracts. Python owns resource discovery,
  game semantics, selections, previews, and visible workflow.
- Verification: `GhostRigger.Core.Tools` `Debug|x64` build, targeted Python
  package registry tests, and visible app checks only when UI/workflow behavior
  changes.

This package is diagnostic-only in Phase 1. It does not replace Python resource
discovery or the visible Resource Browser workflow.
