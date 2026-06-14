# GhostRigger.Tools.ContentBrowser

Phase 1 native toolbox package boundary for the Content Browser.

- Owner surface: Content Browser.
- Owner package: `native/GhostRigger.Tools.ContentBrowser`.
- Bridge method: C ABI DLL.
- Data ownership: C++ owns future catalogue query diagnostics, asset index
  packet metadata, and filter/sort helper contracts. Python owns the current UI,
  resource discovery policy, game semantics, selections, and visible workflow.
- Verification: `GhostRigger.Tools.ContentBrowser` `Debug|x64` build, targeted Python
  package registry tests, and visible app checks only when UI/workflow behavior
  changes.

This package is diagnostic-only in Phase 1. It does not build a native asset
index or replace the Python Content Browser workflow.
