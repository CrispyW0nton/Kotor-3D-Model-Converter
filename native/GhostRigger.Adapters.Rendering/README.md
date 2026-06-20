# GhostRigger.Adapters.Rendering

Owner surface: Renderer adapter layer
Owner package: native/GhostRigger.Adapters.Rendering
Source package: src/adapters/rendering
Bridge method: C ABI DLL
Data ownership:
- C++ owns: C++ and native-readiness metadata, dependency scans, and function contracts.
- Python role: compatibility payload and test fixtures only.
Verification:
- Native Debug target: build this project in `Debug|x64` through `GhostRigger.sln`.
- Python adapter test: tests/test_native_module_package_sweep.py
- Visible app check: already deferred until native runtime parity remains stable.
