# GhostRigger.GUI.Rendering

Owner surface: GUI rendering helpers
Owner package: native/GhostRigger.GUI.Rendering
Source package: src/gui/rendering
Bridge method: C ABI DLL
Data ownership:
- C++ owns: Phase 1 module-boundary metadata, dependency-scan metadata, and native-readiness diagnostics.
- Python owns: current implementation, object lifetimes, workflow policy, UI state, and runtime behavior.
Verification:
- Native DEBUG: $name.DEBUG.exe
- Python adapter test: 	ests/test_native_module_package_sweep.py
- Visible app check: required before enabling native implementation behavior.