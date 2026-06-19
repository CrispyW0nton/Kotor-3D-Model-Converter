# GhostRigger.Core.Game

Owner surface: Game-domain services
Owner package: native/GhostRigger.Core.Game
Source package: src/core/game
Bridge method: C ABI DLL
Data ownership:
- C++ owns: Phase 1 module-boundary metadata, dependency-scan metadata, and native-readiness diagnostics.
- Python owns: current implementation, object lifetimes, workflow policy, UI state, and runtime behavior.
Verification:
- Native Debug target: build this project in `Debug|x64` through `GhostRigger.sln`.
- Python adapter test: 	ests/test_native_module_package_sweep.py
- Visible app check: required before enabling native implementation behavior.
