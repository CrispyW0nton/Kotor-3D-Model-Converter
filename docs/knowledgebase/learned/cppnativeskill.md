# C++ Native Integration Skill

Use this skill for GhostRigger native packages, C++ code, DLL ABI boundaries,
embedded Python host behavior, memory ownership, RAII, and systems-level
integration.

## Book Grounding

- `Professional_C_6th_Edition_-_Marc_Gregoire.pdf`: professional C++ design,
  classes, reuse, memory management, smart pointers, templates, standard
  library, exceptions, concurrency, filesystem, and testing/debugging concerns.
- `Programming_C_C++.pdf`: C/C++ declarations vs definitions, preprocessor,
  headers, file I/O, variadic functions, STL, strings, exceptions, and C99
  library behavior.
- `Systems_Programming_-_John_J_Donovan.pdf`: present in the local library but
  not machine-readable via the current PDF extractor; inspect manually before
  deriving detailed systems rules from it.
- GhostRigger-native docs: `AGENTS.md`, `native/README.md`,
  `native/templates/README.md`, `knowledge_base/cpp_integration_phases.md`, and
  `knowledge_base/native_migration_plan.md`.

## Current Native Shape

- Current solution shape: 19 native projects total, 18 non-debug Python-payload
  DLL projects, and 1,145 packaged Python file references in
  `native/GhostRigger.PythonPayloadManifest.json`.
- Current aggregate project owners include `GhostRigger.Core.Automation`,
  `GhostRigger.Core.Bridge`, `GhostRigger.Core.GUI.Display`,
  `GhostRigger.Core.GUI.Helpers`, `GhostRigger.Core.IO`,
  `GhostRigger.Core.Math`, `GhostRigger.Core.Project`, `GhostRigger.Core.Qt`,
  `GhostRigger.Core.Rendering`, `GhostRigger.Core.Resources`,
  `GhostRigger.Core.Scene`, `GhostRigger.Core.Tools`,
  `GhostRigger.Core.Validation`, `GhostRigger.Core.Workflow`,
  `GhostRigger.Native.Core.Foundation`, `GhostRigger.Native.Core.Host`,
  `GhostRigger.Runtime.Core`, `GhostRigger.Runtime.Core.Host`, and
  `GhostRigger.Runtime.Shared`.

## Workflow

1. Define the boundary before coding: C++ owns what, Python owns what, and how
   data crosses the ABI.
2. Prefer narrow C ABI exports for Python/ctypes/package availability checks.
   Keep exported structs/payloads versioned, plain, and stable.
3. Use RAII for native resource lifetime. Avoid raw owning pointers; prefer
   values, `std::unique_ptr`, `std::shared_ptr` only for shared ownership, and
   clear move semantics.
4. Keep headers small and explicit. Public headers define ABI/contracts; private
   files own implementation details.
5. Keep exceptions inside C++ boundaries unless the bridge explicitly translates
   them to error codes/status JSON.
6. Treat build files as source: `.vcxproj`, `.filters`, payload manifests, `.rc`
   resources, and package registry entries must move together.
7. Do not migrate behavior into C++ just because a package exists. Native
   migration must prove ownership, parity, validation, and visible workflow.

## ABI Checklist

- Exported functions should have stable names, explicit calling convention where
  needed, and C-compatible types.
- Return status, version, capabilities, or JSON payloads through narrow ABI
  surfaces; keep complex C++ objects private.
- Document string ownership: static string, caller-provided buffer, allocated
  buffer, or JSON copied by Python.
- Never let C++ exceptions escape a C ABI. Convert to status/error payloads at
  the boundary.
- Version every payload shape that Python or tests parse.
- Keep fallback DLL names only when preserving an existing compatibility path.
  Remove stale fallbacks during canonical rename batches.

## C++ Hygiene

- Separate declaration and definition deliberately; headers are contracts, not
  dumping grounds.
- Avoid dangerous macros for behavior. Prefer constants, templates, functions,
  or build-system definitions.
- Use smart pointers to express ownership and references/values for non-owning
  or value-like relationships.
- Watch for double-delete, use-after-free, stale references, iterator
  invalidation, and object lifetime across DLL boundaries.
- Prefer pre-increment for iterators and profile before making performance
  changes.
- Treat `.vcxproj` and `.filters` XML validity as part of the change.

## GhostRigger Native Rules

- Canonical Python remains under root `src/` unless a package explicitly owns
  package-local Python.
- Embedded copies under `native/<Project>/Python/src/...` must be regenerated,
  not hand-edited, when root sources change.
- New native packages start from `native/templates/`.
- Do not add parallel `.DEBUG` application projects.
- Update package registry and native tests when package names, exports, DLL
  lookup, or capabilities change.
- Keep aggregate package owners aligned with `AGENTS.md` and the current root
  payload manifest.

## Validation

- For payload changes, run focused tests from `tests/test_native_python_payloads.py`.
- For package registry changes, run focused tests from
  `tests/test_native_core_package_registry.py`.
- For project/template changes, run focused tests from
  `tests/test_native_project_templates.py` and related package-sweep tests.
- Build the owning project in `Debug|x64` or `Release|x64` when C++ code or
  project metadata changes.
