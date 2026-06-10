# GhostRigger.Adapters.QtViewport

Owner surface: Qt viewport adapters
Owner package: native/GhostRigger.Adapters.QtViewport
Source package: src/adapters/qt_viewport
Data ownership:
- C++ owns: viewport contracts, native status metadata, owner/dependency capability metadata.
- Python owns: UI-state compatibility shims and test coverage only.
- Phase: P2 native completion.
- Native implementation contract: `native_implementation_enabled=true`, `python_fallback_required=false`.
Verification:
- Native DEBUG: $name.DEBUG.exe
- Python adapter test: tests/test_native_module_package_sweep.py
- Visible app check: required before enabling native implementation behavior.
