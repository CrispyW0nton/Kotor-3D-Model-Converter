# GhostRigger.Special

Owner surface: Special-case model support
Owner package: native/GhostRigger.Special
Source package: src/core/special
Bridge method: C ABI DLL
Data ownership:
- C++ owns: Phase 1 module-boundary metadata, dependency-scan metadata, and native-readiness diagnostics.
- Python owns: current implementation, object lifetimes, workflow policy, UI state, and runtime behavior.
Verification:
- Native Debug target: build this project in `Debug|x64` through `GhostRigger.sln`.
- Python adapter test: 	ests/test_native_module_package_sweep.py
- Visible app check: required before enabling native implementation behavior.
