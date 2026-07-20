---
name: ghostrigger-native-bridge
description: >
  Work on GhostRigger's C++ native host and embedded-Python boundary. Use for
  the embedded CPython launch flow, DLL-embedded RCDATA Python payload loading,
  the GhostRiggerNativeDependencies audit chain, renderer backend adapters
  (D3D12/ModernGL/PyGFX/Null), ABI boundary design, ctypes bridges, and
  performance-critical native code. Covers the main.cpp launch sequence,
  PyConfig initialization, gr_python_payload_file_count, and the
  _DllPythonPayloadImporter meta-path finder.
---

# GhostRigger Native Bridge

GhostRigger's native host is a thin C++ `.exe` (`GhostRigger.Native.Core.Host`)
that bootstraps embedded CPython and hands control to `main.py`. The real
Python source (1,162 files) lives as DLL-embedded RCDATA resources loaded
through a custom meta-path importer.

## When to Use

- Modifying the C++ host launch flow (`main.cpp`)
- Working on the embedded Python payload import system (`main.py`)
- Adding or modifying renderer backend adapters
- Designing C++↔Python ABI boundaries
- Debugging DLL dependency resolution
- Performance-critical native code (culling, command buffers, fixed-step update)
- Native package creation or migration (see templates at `native/templates/`)

## The Native Host Launch Flow

Verify against current `main.cpp`, but the sequence is:

1. **Resolve repo root** — walk up from cwd/executable directory looking for
   `GhostRigger.sln` or `pyproject.toml` + `native/`
2. **Discover Python 3.13 home** — probe `GHOSTRIGGER_PYTHON_HOME`,
   `GHOSTRIGGER_PYTHON`, `%LOCALAPPDATA%\Programs\Python\Python313`,
   `%ProgramFiles%\Python313`, `%ProgramW6432%\Python313`
3. **Audit native DLL dependencies (pre-Python)** — iterate
   `kNativeDependencySpecs[]` from `GhostRiggerNativeDependencies.h`,
   `LoadLibraryExW` each DLL, resolve `gr_python_payload_file_count` via
   `GetProcAddress`, classify as OK / NO_PAYLOAD / MISSING, publish to
   `GHOSTRIGGER_NATIVE_PREPYTHON_AUDIT` env var
4. **Configure and start embedded Python** — build `PyConfig`, set home/program
   paths, append argv, initialize interpreter, run `main.py`

## The Python Payload Import System

`main.py` installs `_DllPythonPayloadImporter` at `sys.meta_path[0]`:

1. Glob `*.dll` in the build output directory
2. For each DLL, call `gr_python_payload_manifest_json()` to get the file list
3. Register each `.py` file as an RCDATA resource keyed by `resource_name`
4. `find_spec()` → look up module by dotted name → return `ModuleSpec`
5. `exec_module()` → `FindResourceA` → `LoadResource` → `LockResource` →
   `SizeofResource` → `ctypes.string_at` → `compile` → `exec`

Fallback chain: DLL RCDATA → `GhostRiggerPythonPayload/` dir → `sys.path` with
root `src/` + every `native/<Project>/Python/src/`.

## Source-of-Truth Reality

- Root `src/` has only **23 Python files** (nearly vestigial)
- The real source lives under `native/<Project>/Python/src/` (**1,162 files**)
- The "byte identity" test only enforces parity for the ~23 files with root twins
- **Edit the native payload dirs in place** — that is the source of truth
- Payload regeneration (`scripts/native_python_payload_generator.py`) only
  matters for the ~18 Core.* DLL projects

## Renderer Backend Adapters

| Backend | Identifier | Purpose |
|---------|-----------|---------|
| ModernGL | `MODERNGL_GL330` | OpenGL 3.3 software fallback |
| WGPU D3D12 | `WGPU_D3D12` | Direct3D 12 via WGPU |
| PyGFX | `PYGFX_WGPU` | Modern pygfx pipeline |
| Null | `NULL_DIAGNOSTIC` | Headless diagnostic-only |

The renderer must launch when optional GPU packages (wgpu, pygfx) are absent
and fall back to ModernGL/OpenGL 3.3.

## Native Package Creation Rules

- Read `native/README.md`, `native/templates/README.md`,
  `knowledge_base/cpp_integration_phases.md`, and
  `knowledge_base/native_migration_plan.md` first
- Start from `native/templates/` — do not copy an existing project and strip it
- Do not add parallel `.DEBUG` application projects
- Use canonical Visual Studio project names directly
- Keep ABI/package names stable unless a batch updates all surfaces together
- Python availability checks live through
  `src.adapters.native_core.package_registry`

## Embedded Python Payload Rules

- Edit canonical root `src/...` first when a matching source exists there
- Regenerate payload copies after canonical Python changes
- Do not manually patch `native/<Project>/Python/src/...` to diverge from root
  `src/...` (though in practice most files only exist in native payloads now)
- Use `python scripts/native_python_payload_generator.py <Project>` for one
  package, `--all` for many, `--write-project-generators` for wrapper repair

## Deep Reference

- `docs/knowledgebase/learned/gamecppskill.md` — native host launch flow,
  ABI boundary, renderer backends, game algorithms, performance patterns
- `docs/knowledgebase/learned/cppnativeskill.md` — C++ correctness at the
  boundary: RAII, smart pointers, ABI checklist, DLL exports, C interfaces
- `docs/knowledgebase/learned/cgameprogrammingskill.md` — runtime architecture,
  kernel/subsystem split, scene composition, resource lifecycle
- `docs/knowledgebase/learned/pythonengineeringskill.md` — Python profiling,
  concurrency, ctypes, packaging for the embedded payload system
