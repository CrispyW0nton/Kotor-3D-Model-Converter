# GhostRigger.Core.Gizmo

Owner surface: Transform gizmo services
Owner package: native/GhostRigger.Core.Gizmo
Source package: src/core/gizmo
Bridge method: C ABI DLL
Data ownership:
- C++ owns: gizmo mode/space contracts, native gizmo-origin resolution, module-boundary metadata, dependency-scan metadata, and native-readiness diagnostics.
- Python owns: TransformGizmo object state, TransformController drag math, viewport event routing, draw data, picking, object lifetimes, workflow policy, UI state, and runtime mutation.
Verification:
- Native Debug target: build this project in `Debug|x64` through `GhostRigger.sln`.
- Python adapter test: `tests/test_native_gizmo_mode.py`, `tests/test_gizmo_follows_object.py`.
- Visible app check: required before porting this behavior to D3D or PyGFX.
