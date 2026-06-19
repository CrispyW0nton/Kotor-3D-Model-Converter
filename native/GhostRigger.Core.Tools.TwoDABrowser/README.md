# GhostRigger.Core.Tools.TwoDABrowser

Phase 1 native toolbox package boundary for the 2DA Browser.

- Owner surface: 2DA Browser.
- Owner package: `native/GhostRigger.Core.Tools.TwoDABrowser`.
- Bridge method: C ABI DLL.
- Data ownership: C++ owns future 2DA table query diagnostics, row/column
  packet metadata, and filter helper contracts. Python owns 2DA parsing policy,
  game semantics, editing workflow, selections, and visible UI.
- Verification: `GhostRigger.Core.Tools.TwoDABrowser` `Debug|x64` build, targeted Python package
  registry tests, and visible app checks only when UI/workflow behavior changes.

This package is diagnostic-only in Phase 1. It does not parse or edit 2DA files
and does not replace the Python 2DA Browser workflow.
