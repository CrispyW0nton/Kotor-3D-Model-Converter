# GhostRigger.Adapters.Qt.Autorig

Owner surface: Qt auto-rig adapters
Owner package: native/GhostRigger.Adapters.Qt.Autorig
Source package: src/adapters/qt_autorig
Bridge method: C ABI DLL
Data ownership:
- C++ owns: Phase 1 module-boundary metadata, dependency-scan metadata, and native-readiness diagnostics.
- Python owns: current implementation, object lifetimes, workflow policy, UI state, and runtime behavior.
Verification:
- Native Debug target: build this project in `Debug|x64` through `GhostRigger.sln`.
- Python adapter test: 	ests/test_native_module_package_sweep.py
- Visible app check: required before enabling native implementation behavior.
