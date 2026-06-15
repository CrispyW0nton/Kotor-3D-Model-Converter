# GhostRigger.Windows.Shell.Main

Phase 1 native window package boundary for main-window host services.

- Owner surface: Main window composition shell.
- Owner package: `native/GhostRigger.Windows.Shell.Main`.
- Bridge method: C ABI DLL first; host module registration may follow only when
  the Python/Qt main window has a narrow native service to call.
- Data ownership: C++ owns future host-owned service discovery, native command
  routing metadata, and application-shell diagnostics. Python owns current Qt
  widgets, docks, menus, themes, layouts, window state, and user workflow
  orchestration.
- Verification: `GhostRigger.Windows.Shell.Main` `Debug|x64` build, targeted Python package
  registry tests, and visible app checks only when future slices change startup,
  theming, layout, docking, menus, or visible main-window workflow.

This package is diagnostic-only in Phase 1. It must not replace the Python/Qt
main window, mutate visible shell state, or own product workflow until a future
slice defines and verifies that bridge.
