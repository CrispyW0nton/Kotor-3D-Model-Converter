# GhostRigger.Adapters.QtViewport

Owner surface: Qt viewport adapters
Owner package: native/GhostRigger.Adapters.QtViewport
Source package: src/adapters/qt_viewport
Bridge method: C ABI DLL
Data ownership:
- C++ owns: Phase 1 module-boundary metadata, dependency-scan metadata, and native-readiness diagnostics.
- Python owns: current implementation, object lifetimes, workflow policy, UI state, and runtime behavior.
Verification:
- Native DEBUG: $name.DEBUG.exe
- Python adapter test: 	ests/test_native_module_package_sweep.py
- Visible app check: required before enabling native implementation behavior.